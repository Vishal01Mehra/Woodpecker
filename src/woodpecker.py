import time
import math
import subprocess
import os
import json
from macimu import IMU

# Version information
VERSION = "1.0.0"
AUTHOR = "Vishal Mehra"

# Safely get the actual macOS user
# 1. Force identify the user from Environment or Fallback
ACTUAL_USER = os.environ.get('WOODPECKER_USER')

if not ACTUAL_USER or ACTUAL_USER == 'root':
    # Search for the .user file in /Users as a last resort
    for name in os.listdir('/Users'):
        if name in ['Shared', '.localized']: continue
        test_path = f"/Users/{name}/.woodpecker/.user"
        if os.path.exists(test_path):
            with open(test_path, 'r') as f:
                ACTUAL_USER = f.read().strip()
            break

# 2. Critical Safety: Exit if detection failed to avoid "~None" error
if not ACTUAL_USER or ACTUAL_USER == 'None':
    print("FATAL: Woodpecker could not determine the target user.")
    exit(1)

# 3. Use Absolute Paths (Avoids ~ expansion issues in background daemons)
USER_HOME = f"/Users/{ACTUAL_USER}"
CONFIG_PATH = f"{USER_HOME}/.woodpecker/config.json"

# If still None, get the owner of ~/.woodpecker if it exists
if not ACTUAL_USER:
    try:
        woodpecker_path = os.path.expanduser('~/.woodpecker')
        if os.path.exists(woodpecker_path):
            stat_info = os.stat(woodpecker_path)
            import pwd
            ACTUAL_USER = pwd.getpwuid(stat_info.st_uid).pw_name
    except (OSError, KeyError, Exception):
        pass

if not ACTUAL_USER:
    print("Error: Could not determine the target user. Please check installation.")
    exit(1)

USER_HOME = os.path.expanduser(f"~{ACTUAL_USER}")
CONFIG_PATH = os.path.join(USER_HOME, ".woodpecker", "config.json")

DEFAULT_CONFIG = {
    "settings": {
        "tap_threshold": 0.095,
        "tap_cooldown": 0.15,
        "multi_tap_window": 0.6
    },
    "actions": {
        "2": "shortcuts run 'Shortcut0' && echo 'Shortcut 0 executed!'",
        "3": "shortcuts run 'Shortcut1' && echo 'Shortcut 1 executed!'",
        "4": "shortcuts run 'Shortcut2' && echo 'Shortcut 2 executed!'",
        "5": "shortcuts run 'Shortcut3' && echo 'Shortcut 3 executed!'",
    }
}

def load_config():
    """Loads the JSON config, or creates it if it doesn't exist."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Warning: config.json has a syntax error. Using previous settings.")
        return None

def get_config_mtime():
    """Gets the last modified time of the config file to detect changes."""
    try:
        return os.path.getmtime(CONFIG_PATH)
    except OSError:
        return 0

def execute_action(tap_count, actions_dict):
    """Looks up the tap count in the config and runs the mapped command."""
    command = actions_dict.get(str(tap_count))

    if command:
        print(f"Executing action for {tap_count} taps: {command}")
        subprocess.run(['sudo', '-u', ACTUAL_USER, 'sh', '-c', command])

def detect_taps():
    print(f"🪵 Woodpecker v{VERSION} - Starting with Live-Reload...")
    config = load_config()
    settings = config["settings"]
    actions = config["actions"]

    # Track file modification to auto-reload settings
    last_config_check = time.time()
    last_config_mtime = get_config_mtime()

    if not IMU.available():
        print("Error: IMU sensor not found. Woodpecker requires an Apple Silicon Mac.")
        return

    print(f"IMU available. Listening for taps (Threshold: {settings['tap_threshold']}g)...")

    tap_count = 0
    last_tap_time = 0

    with IMU(accel=True, gyro=False, decimation=8) as imu:
        try:
            for sample in imu.stream_accel():
                current_time = time.time()

                # --- LIVE RELOAD LOGIC ---
                # Check if the config file was modified (run this check once every 2 seconds)
                if current_time - last_config_check > 2.0:
                    current_mtime = get_config_mtime()
                    if current_mtime > last_config_mtime:
                        print("🔄 config.json changed! Reloading new settings...")
                        new_config = load_config()
                        if new_config:  # Only apply if there were no JSON syntax errors
                            config = new_config
                            settings = config["settings"]
                            actions = config["actions"]
                        last_config_mtime = current_mtime
                    last_config_check = current_time
                # -------------------------

                # 1. Check if our listening window has closed
                if tap_count > 0 and (current_time - last_tap_time) > settings["multi_tap_window"]:
                    if tap_count >= 2:
                        execute_action(tap_count, actions)
                    tap_count = 0

                # 2. Check for new physical knocks
                current_magnitude = math.sqrt(sample.x**2 + sample.y**2 + sample.z**2)
                vibration = abs(current_magnitude - 1.0)

                if vibration > settings["tap_threshold"]:
                    if current_time - last_tap_time > settings["tap_cooldown"]:
                        tap_count += 1
                        last_tap_time = current_time

        except KeyboardInterrupt:
            print("\nWoodpecker sleeping...")

if __name__ == "__main__":
    detect_taps()

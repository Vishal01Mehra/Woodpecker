import time
import math
import subprocess
import os
import json
from collections import deque
from macimu import IMU

VERSION = "1.1.0"
AUTHOR = "Vishal Mehra"

# ---------------- User detection (unchanged logic, simplified) ----------------
ACTUAL_USER = os.environ.get('WOODPECKER_USER')
if not ACTUAL_USER or ACTUAL_USER == 'root':
    for name in os.listdir('/Users'):
        if name in ['Shared', '.localized']:
            continue
        test_path = f"/Users/{name}/.woodpecker/.user"
        if os.path.exists(test_path):
            with open(test_path, 'r') as f:
                ACTUAL_USER = f.read().strip()
            break

if not ACTUAL_USER or ACTUAL_USER == 'None':
    print("FATAL: Woodpecker could not determine the target user.")
    exit(1)

USER_HOME = f"/Users/{ACTUAL_USER}"
CONFIG_PATH = f"{USER_HOME}/.woodpecker/config.json"

# Sample rate of the IMU stream (macimu with decimation=8 ≈ 100 Hz)
SAMPLE_RATE_HZ = 100

DEFAULT_CONFIG = {
    "settings": {
        # Absolute minimum peak magnitude (g) — anything below is never a tap.
        # Raise to ~0.22 if you type heavily, lower to ~0.12 for lighter taps.
        "min_peak": 0.18,

        # Peak must be at least this many times the recent noise floor.
        # Higher = stricter (fewer false positives, may miss soft taps).
        "prominence_ratio": 8.0,

        # How long to wait after a peak before accepting another (seconds).
        # Prevents chassis ringing from registering as multiple taps.
        "refractory_s": 0.15,

        # How long after the last tap before we fire the tap-group event.
        "multi_tap_window": 0.6,

        # Window (seconds) around a peak used to judge "is it really isolated?"
        # Samples in this window (outside the peak itself) must be mostly quiet.
        "quiet_check_window_s": 0.15,

        # Samples in the quiet window louder than (quiet_ratio * peak) count as
        # "loud". If more than quiet_max_loud_fraction of them are loud, reject.
        "quiet_ratio": 0.30,
        "quiet_max_loud_fraction": 0.25,

        # Rolling window (seconds) used to estimate noise floor.
        "noise_window_s": 0.6
    },
    "actions": {
        "2": "shortcuts run 'Shortcut0' && echo 'Shortcut 0 executed!'",
        "3": "shortcuts run 'Shortcut1' && echo 'Shortcut 1 executed!'",
        "4": "shortcuts run 'Shortcut2' && echo 'Shortcut 2 executed!'",
        "5": "shortcuts run 'Shortcut3' && echo 'Shortcut 3 executed!'"
    }
}


def load_config():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_PATH, 'r') as f:
            cfg = json.load(f)
        # Merge defaults for any missing new settings (forwards compat)
        merged_settings = {**DEFAULT_CONFIG["settings"], **cfg.get("settings", {})}
        cfg["settings"] = merged_settings
        cfg.setdefault("actions", DEFAULT_CONFIG["actions"])
        return cfg
    except json.JSONDecodeError:
        print("⚠️ config.json has a syntax error. Using previous settings.")
        return None


def get_config_mtime():
    try:
        return os.path.getmtime(CONFIG_PATH)
    except OSError:
        return 0


def execute_action(tap_count, actions_dict):
    command = actions_dict.get(str(tap_count))
    if command:
        print(f"Executing action for {tap_count} taps: {command}")
        subprocess.run(['sudo', '-u', ACTUAL_USER, 'sh', '-c', command])


# ---------------- Robust tap detector ----------------

class TapDetector:
    """
    Two-stage detector:

    Stage 1 – PROMINENCE: a candidate peak must exceed both an absolute
    minimum AND a multiple of the recent noise floor (median of the last
    ~0.6s). The noise floor adapts to your environment (quiet room vs.
    laptop-on-lap vs. typing). This rejects small jitters and lets the
    same code work with different typing habits.

    Stage 2 – ISOLATION: once we've tracked the true peak, we check that
    the surroundings are mostly quiet relative to the peak. A real
    knock stands out from its neighbourhood; a typing-burst peak is
    embedded in a noisy neighbourhood and gets rejected.

    Chassis ringing (the physical echo after a knock) is handled by the
    refractory period plus the peak-tracking logic, so one knock can
    never register as several.
    """

    def __init__(self, settings, sample_rate_hz=SAMPLE_RATE_HZ):
        s = settings
        self.sr = sample_rate_hz
        self.min_peak = s["min_peak"]
        self.prom_ratio = s["prominence_ratio"]
        self.refractory = s["refractory_s"]
        self.multi_tap_window = s["multi_tap_window"]

        # Pre-compute sample counts from time windows
        self.noise_n = int(s["noise_window_s"] * sample_rate_hz)
        self.quiet_n = int(s["quiet_check_window_s"] * sample_rate_hz)
        self.confirm_n = max(3, int(0.05 * sample_rate_hz))  # 50ms peak confirmation

        self.quiet_ratio = s["quiet_ratio"]
        self.quiet_max_loud_fraction = s["quiet_max_loud_fraction"]

        # Ring buffer holds enough history to run all checks
        maxlen = self.noise_n + 2 * self.quiet_n + self.confirm_n + 10
        self.hist = deque(maxlen=maxlen)

        # Candidate peak we're currently tracking (if any)
        self.candidate = None

        # Tap counting state
        self.tap_count = 0
        self.last_tap_time = 0.0
        self.in_refractory_until = 0.0

    def update_settings(self, settings):
        """Live-reload support."""
        self.__init__(settings, self.sr)

    def _noise_floor(self):
        if len(self.hist) < 10:
            return 0.01
        # Median is robust to outliers (i.e. the peaks themselves)
        sorted_vals = sorted(v for _, v in self.hist)
        mid = len(sorted_vals) // 2
        return max(0.005, sorted_vals[mid])

    def _is_isolated(self, peak_t, peak_v):
        exclusion_s = 0.05  # ignore ±50ms right around the peak (its own decay)
        significant = self.quiet_ratio * peak_v
        loud = 0
        total = 0
        for t, v in self.hist:
            dt = abs(t - peak_t)
            if dt < exclusion_s:
                continue
            if dt > self.quiet_n / self.sr:
                continue
            total += 1
            if v > significant:
                loud += 1
        if total == 0:
            return True
        return (loud / total) < self.quiet_max_loud_fraction

    def process(self, t, vibration):
        """
        Feed one sample (timestamp, |accel|-1.0). Returns tap_count to fire
        (>=2) if a multi-tap window just closed, else 0.
        """
        # 1. Close expired multi-tap window → fire event if ≥2 taps accumulated
        fire = 0
        if self.tap_count > 0 and (t - self.last_tap_time) > self.multi_tap_window:
            if self.tap_count >= 2:
                fire = self.tap_count
            self.tap_count = 0

        self.hist.append((t, vibration))

        # 2. Still in refractory from a previous peak? Do nothing else.
        if t < self.in_refractory_until:
            return fire

        # 3. Peak tracking
        if self.candidate is None:
            floor = self._noise_floor()
            required = max(self.min_peak, self.prom_ratio * floor)
            if vibration >= required:
                # Begin tracking a new candidate peak
                self.candidate = {'t': t, 'v': vibration, 'post': 0}
        else:
            if vibration > self.candidate['v']:
                # New higher sample is the real peak — reset counter
                self.candidate = {'t': t, 'v': vibration, 'post': 0}
            else:
                self.candidate['post'] += 1
                # Wait until we have enough look-ahead to judge isolation
                if self.candidate['post'] >= self.quiet_n:
                    if self._is_isolated(self.candidate['t'], self.candidate['v']):
                        # Register a real tap!
                        self.tap_count += 1
                        self.last_tap_time = self.candidate['t']
                        self.in_refractory_until = self.candidate['t'] + self.refractory
                    self.candidate = None

        return fire


# ---------------- Main loop ----------------

def detect_taps():
    print(f"🪵 Woodpecker v{VERSION} - Starting with Live-Reload...")
    config = load_config()
    if config is None:
        print("Could not load config on startup.")
        return

    settings = config["settings"]
    actions = config["actions"]

    last_config_check = time.time()
    last_config_mtime = get_config_mtime()

    if not IMU.available():
        print("Error: IMU sensor not found. Woodpecker requires an Apple Silicon Mac.")
        return

    detector = TapDetector(settings, sample_rate_hz=SAMPLE_RATE_HZ)
    print(f"IMU available. Listening for taps "
          f"(min_peak={settings['min_peak']}g, prominence×{settings['prominence_ratio']})...")

    with IMU(accel=True, gyro=False, decimation=8) as imu:
        try:
            for sample in imu.stream_accel():
                current_time = time.time()

                # --- Live reload ---
                if current_time - last_config_check > 2.0:
                    current_mtime = get_config_mtime()
                    if current_mtime > last_config_mtime:
                        print("🔄 config.json changed! Reloading settings...")
                        new_config = load_config()
                        if new_config:
                            settings = new_config["settings"]
                            actions = new_config["actions"]
                            detector.update_settings(settings)
                        last_config_mtime = current_mtime
                    last_config_check = current_time

                # --- Detection ---
                magnitude = math.sqrt(sample.x**2 + sample.y**2 + sample.z**2)
                vibration = abs(magnitude - 1.0)

                fire_count = detector.process(current_time, vibration)
                if fire_count:
                    execute_action(fire_count, actions)

        except KeyboardInterrupt:
            print("\nWoodpecker sleeping...")


if __name__ == "__main__":
    detect_taps()

# 🪵 Woodpecker

![macOS](https://img.shields.io/badge/macOS-Apple_Silicon_Only-000000?style=flat-square&logo=apple)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-Commons%20Clause%20%2B%20MIT-orange?style=flat-square)

Turn your entire Apple Silicon MacBook into a giant, customizable macro-pad by detecting physical taps and knocks on your laptop chassis.

Woodpecker runs silently in the background and uses the hardware-level accelerometer (IMU) in Apple Silicon Macs to detect physical knocks or taps on your laptop. By default, a triple-tap instantly takes a silent screenshot, but you can map any tap sequence to execute custom terminal commands or AppleScript.

---

## ⚠️ Prerequisites & Compatibility

### System Requirements
- **Apple Silicon Mac (M2, M3, M4, M5+):** Requires the Sensor Processing Unit (SPU)
  - ❌ Not compatible with Intel Macs
  - ❌ Not compatible with M1 MacBook Pro (2020)
- **Python 3.9+**: Must be installed on your system
- **macOS 13+**: Requires recent macOS version

### Check Your Compatibility
To verify your Mac has the required hardware:

```bash
sysctl -a | grep arm64
```

If you see output, you have an Apple Silicon Mac and should be compatible.

---

## 🚀 Installation

Woodpecker requires elevated privileges to access rawIOKit hardware sensors. It runs seamlessly as a native macOS background daemon (`launchd`).

### Quick Install (Recommended)

Paste this single command into your Terminal:

```bash
curl -sSL https://raw.githubusercontent.com/Vishal01Mehra/Woodpecker/main/install.sh | bash
```

The installer will automatically:
- ✅ Download the Woodpecker Python script
- ✅ Create a Python virtual environment
- ✅ Install the `macimu` dependency (IMU hardware access)
- ✅ Create a configuration file at `~/.woodpecker/config.json`
- ✅ Set up the background daemon service
- ✅ Start listening for taps immediately

### Manual Installation

If you prefer to install manually:

1. **Create the installation directory:**
   ```bash
   mkdir -p ~/.woodpecker
   ```

2. **Download the script:**
   ```bash
   curl -sSL -o ~/.woodpecker/woodpecker.py \
     https://raw.githubusercontent.com/Vishal01Mehra/Woodpecker/main/woodpecker.py
   ```

3. **Set up Python virtual environment:**
   ```bash
   python3 -m venv ~/.woodpecker/.venv
   ```

4. **Install dependencies:**
   ```bash
   ~/.woodpecker/.venv/bin/pip install macimu
   ```

5. **Create the launchd daemon file:**
   ```bash
   cat > /tmp/com.mac.woodpecker.plist << 'EOF'
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.mac.woodpecker</string>
       <key>ProgramArguments</key>
       <array>
           <string>/Users/$USER/.woodpecker/.venv/bin/python3</string>
           <string>/Users/$USER/.woodpecker/woodpecker.py</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   EOF
   ```

6. **Install and start the daemon:**
   ```bash
   sudo mv /tmp/com.mac.woodpecker.plist /Library/LaunchDaemons/
   sudo chown root:wheel /Library/LaunchDaemons/com.mac.woodpecker.plist
   sudo launchctl load /Library/LaunchDaemons/com.mac.woodpecker.plist
   ```

7. **Test the installation:**
   Give your MacBook a gentle tap to verify it's working!

---

## ⚙️ Configuration

Woodpecker stores its configuration in `~/.woodpecker/config.json`. This file is automatically created with default settings during installation.

### Default Configuration

```json
{
    "settings": {
        "tap_threshold": 0.07,
        "tap_cooldown": 0.15,
        "multi_tap_window": 0.6
    },
    "actions": {
        "2": "echo 'Double tap detected!'",
        "3": "screencapture -x ~/Desktop/woodpecker_shot_$(date +%s).png"
    }
}
```

### Configuration Reference

#### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `tap_threshold` | `0.07` | Sensitivity for detecting taps (lower = more sensitive). Range: 0.01 - 0.2 |
| `tap_cooldown` | `0.15` | Minimum seconds between consecutive taps (debounce). Prevents double-detection |
| `multi_tap_window` | `0.6` | Time window (in seconds) to register consecutive taps as multi-tap sequences |

#### Actions

Actions are mapped by the number of taps. The key is the tap count, the value is the command to execute.

| Tap Count | Default Command | Description |
|-----------|-----------------|-------------|
| `"2"` | `echo 'Double tap detected!'` | Executes on double-tap |
| `"3"` | Screenshot to Desktop | Executes on triple-tap |

### Customizing Actions

Edit `~/.woodpecker/config.json` to map tap sequences to custom commands:

#### Example: Custom Actions

```json
{
    "settings": {
        "tap_threshold": 0.07,
        "tap_cooldown": 0.15,
        "multi_tap_window": 0.6
    },
    "actions": {
        "2": "open -a 'Spotlight'",
        "3": "screencapture -x ~/Desktop/woodpecker_shot_$(date +%s).png",
        "4": "say 'Woodpecker activated'",
        "5": "open https://github.com"
    }
}
```

#### Example: Terminal Commands

```json
{
    "actions": {
        "2": "open -a 'Visual Studio Code'",
        "3": "shortcuts run 'Screenshot'",
        "4": "afplay /System/Library/Sounds/Glass.aiff"
    }
}
```

#### Example: AppleScript

```json
{
    "actions": {
        "2": "osascript -e 'display notification \"Test\" with title \"Woodpecker\"'",
        "3": "open /Applications/System\\ Preferences.app"
    }
}
```

### Live Reload

Woodpecker automatically detects changes to `config.json` and reloads settings without requiring a restart. Simply save your configuration changes and they take effect within 2 seconds.

You'll see output like:
```
🔄 config.json changed! Reloading new settings...
```

---

## 📖 Usage

Once installed, Woodpecker runs automatically in the background. Simply tap or knock on your MacBook chassis:

- **Give your laptop 2 taps** → Executes the action mapped to `"2"` (default: opens Spotlight)
- **Give your laptop 3 taps** → Executes the action mapped to `"3"` (default: takes a screenshot)
- **Give your laptop 4+ taps** → Executes custom actions you've configured

### Tips for Using Woodpecker

1. **Find the sweet spot:** Different MacBook models may respond differently. Experiment with tapping on the aluminum chassis.
2. **Comfortable taps:** You don't need to hit hard—gentle taps work best.
3. **Avoid false triggers:** If you're getting unintended detections, increase `tap_threshold` in the config.
4. **Silent operation:** All actions are executed in the background without notifications (unless you configure them).

---

## ✅ Checking Status

### Verify the Daemon is Running

```bash
launchctl list | grep com.mac.woodpecker
```

If running, you'll see output similar to:
```
- 0 com.mac.woodpecker
```

The first number is the process ID (or `0` if recently started). A presence in the list means the daemon is active.

### View Recent Logs

See what Woodpecker has detected and executed:

```bash
log show --predicate 'process == "woodpecker"' --last 1h
```

This shows logs from the last hour. Adjust `--last` as needed:
- `--last 30m` - Last 30 minutes
- `--last 3h` - Last 3 hours
- ...or remove `--last` to see all logs

### Check if Config File Exists

```bash
cat ~/.woodpecker/config.json
```

---

## 🔧 Troubleshooting

### Issue: "Error: IMU sensor not found"

**Cause:** Your Mac doesn't have the required hardware (SPU).

**Solution:**
- Verify you have an Apple Silicon Mac (M2 or newer, not M1)
- Check compatibility with `sysctl -a | grep arm64`

### Issue: Woodpecker not starting

**Check the daemon status:**
```bash
sudo launchctl load /Library/LaunchDaemons/com.mac.woodpecker.plist
```

**View error logs:**
```bash
log show --predicate 'process == "woodpecker"' --level debug
```

### Issue: Taps not being detected

**Possible solutions:**

1. **Adjust sensitivity** - Increase `tap_threshold` in config.json:
   ```json
   "tap_threshold": 0.1
   ```

2. **Check IMU is working** - Try a firmer tap on the aluminum chassis

3. **Restart the daemon:**
   ```bash
   sudo launchctl unload /Library/LaunchDaemons/com.mac.woodpecker.plist
   sudo launchctl load /Library/LaunchDaemons/com.mac.woodpecker.plist
   ```

### Issue: Actions not executing

1. **Verify the command works manually:**
   ```bash
   # Test the command directly
   echo 'Double tap detected!'
   ```

2. **Check file permissions:**
   ```bash
   ls -la ~/.woodpecker/
   ```

3. **Review the config syntax:**
   ```bash
   python3 -m json.tool ~/.woodpecker/config.json
   ```
   (If there are JSON errors, it will show them)

---

## 🗑️ Uninstall

### Quick Uninstall (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/Vishal01Mehra/Woodpecker/main/uninstall.sh | bash
```

This will:
- ✅ Stop the background daemon
- ✅ Remove the launchd configuration
- ✅ Delete all Woodpecker files and configuration

### Manual Uninstall

If you prefer to uninstall step-by-step:

1. **Stop the daemon:**
   ```bash
   sudo launchctl unload /Library/LaunchDaemons/com.mac.woodpecker.plist
   ```

2. **Remove the service file:**
   ```bash
   sudo rm /Library/LaunchDaemons/com.mac.woodpecker.plist
   ```

3. **Delete the installation directory:**
   ```bash
   rm -rf ~/.woodpecker
   ```

4. **Verify removal:**
   ```bash
   launchctl list | grep com.mac.woodpecker
   ```
   (Should produce no output)

---

## 🛠️ Development & Contributing

### Project Structure

```
Woodpecker/
├── woodpecker.py          # Main detection and action execution script
├── install.sh             # Automated installation script
├── uninstall.sh           # Automated uninstallation script
└── README.md              # This file
```

### How It Works

1. **Hardware Access:** Uses the `macimu` library to access the IMU sensor
2. **Tap Detection:** Monitors accelerometer data for vibrations exceeding the threshold
3. **Multi-tap Recognition:** Groups consecutive taps within the `multi_tap_window`
4. **Action Execution:** Maps tap counts to configured commands and executes them
5. **Live Reload:** Monitors the config file and reloads settings automatically

### Key Components

- **IMU Stream:** Continuously reads accelerometer data from the Sensor Processing Unit
- **Vibration Detection:** Calculates the magnitude of acceleration to detect physical taps
- **Config Loader:** Handles JSON configuration parsing and auto-reload
- **Command Executor:** Safely executes shell commands with user privileges

### Dependencies

- **macimu** - Library for accessing IMU sensor data on Apple Silicon Macs
- **Python 3.9+** - Core language
- **macOS 13+** - Operating system

### Contributing

We welcome contributions! Here's how to help:

1. **Report Issues:** If you find a bug or have a feature request, open an issue
2. **Improve Documentation:** Help improve this README or add examples
3. **Submit Pull Requests:** Bug fixes, new features, or improvements are always welcome

---

## ⚖️ License

Woodpecker is released under the **Commons Clause + MIT License**.

### What This Means

**MIT License (Open Source)**
- ✅ You can use, modify, and distribute Woodpecker freely
- ✅ You can use it for personal and non-commercial projects
- ✅ You can modify the source code for your own needs
- ✅ You must include the original license and copyright notice

**Commons Clause (Non-Commercial Restriction)**
- ❌ You cannot sell Woodpecker as a product or service
- ❌ You cannot charge users to use Woodpecker
- ❌ You cannot offer Woodpecker as a SaaS (Software as a Service)
- ✅ You can use it on your own hardware for personal use
- ✅ You can share it freely with others

### Summary

Woodpecker is **free for personal, educational, and non-commercial use**. If you want to use Woodpecker commercially, please contact the author for a commercial license.

---

## 📝 Notes & Disclaimers

- **Hardware Sensor Access:** Woodpecker requires elevated privileges to access the IMU sensor
- **Background Execution:** The daemon runs with system privileges; ensure you trust the source
- **Performance Impact:** Minimal resource usage—only processes when accelerometer detects motion
- **Privacy:** All processing happens locally on your machine; no data is sent anywhere

---

## 🐛 Support & Feedback

- **Issues & Feedback:** Report bugs or request features at [github.com/Vishal01Mehra/Woodpecker](https://github.com/Vishal01Mehra/Woodpecker)
- **Documentation:** Check the config examples and troubleshooting section above
- **Community:** Share your creative tap macros and custom actions!

Happy tapping! 🪵

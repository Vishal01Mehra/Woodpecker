# Woodpecker

![Woodpecker Logo](Resources/Logo.png)

![macOS](https://img.shields.io/badge/macOS-Apple_Silicon_Only-000000?style=flat-square&logo=apple)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-Commons%20Clause%20%2B%20MIT-orange?style=flat-square)

Turn your Apple Silicon MacBook into a customizable macro-pad. Woodpecker runs silently in the background and uses the hardware-level accelerometer (IMU) to detect physical knocks or taps on your laptop chassis. Map any tap sequence to custom terminal commands, AppleScript, or native macOS Shortcuts.

Tap the palm rest twice to toggle Do Not Disturb. Knock three times on the lid to start your Focus shortcut. Whatever you want.

---

## Prerequisites & Compatibility

**Hardware:**
- Apple Silicon Mac with the Sensor Processing Unit (SPU) — M2, M3, M4, M5+
- Not compatible with Intel Macs
- Not compatible with M1 (no SPU access)

**Software:**
- macOS 13 or later
- Python 3.9 or later

To verify your Mac has the required hardware, run:

```bash
sysctl -a | grep arm64
```

If that returns anything, you're on Apple Silicon. The SPU check happens at runtime — if your chip doesn't expose it, Woodpecker will tell you clearly and exit.

---

## Installation

Clone the repo and run the installer:

```bash
git clone https://github.com/Vishal01Mehra/Woodpecker.git
cd Woodpecker
chmod +x scripts/install.sh scripts/uninstall.sh
./scripts/install.sh
```

The installer will:

1. Set up a Python virtual environment at `~/.woodpecker/.venv`
2. Install the `macimu` dependency
3. Copy the main program and calibration script to `~/.woodpecker/`
4. Create a LaunchDaemon so Woodpecker starts automatically at boot
5. Offer to run calibration (strongly recommended — see next section)

The install prompts for your sudo password because the IMU sensor requires root access, and because LaunchDaemons live in `/Library/LaunchDaemons/`.

**Upgrading?** Re-running `install.sh` after a `git pull` will preserve your calibrated `config.json` and skip the recalibration prompt. You don't need to re-tune after updates.

---

## Calibration

Every MacBook chassis rings a little differently, and every user types and taps with different force. Running calibration teaches Woodpecker what *your* tap feels like vs. what *your* typing looks like, then writes well-tuned values into `~/.woodpecker/config.json` automatically.

Calibration runs automatically at the end of the first install. To re-run it later (e.g. after changing where you tap, or after buying a louder keyboard):

```bash
sudo ~/.woodpecker/.venv/bin/python3 ~/.woodpecker/calibrate.py
```

The interactive flow takes about 30 seconds:

1. **Ambient noise** — leave the laptop still for 3 seconds
2. **Typing noise** — type normally for 5 seconds (pass `--quick` to skip)
3. **Tap signature** — perform 2-, 3-, 4-, then 5-tap bursts as prompted

Woodpecker then computes:
- **`min_peak`** — the minimum magnitude for a tap candidate, sized so it stays comfortably above your typing but catches your softest tap
- **`prominence_ratio`** — how much louder than the noise floor a peak must be to count
- **`multi_tap_window`** — how long to wait after the last tap before firing, based on your actual inter-tap timing

It shows a summary and any warnings (e.g. "your softest tap is below the chosen threshold — try tapping more consistently"), and asks before writing to `config.json`. The daemon picks up the new values live via its file-watch reload.

**Flag:** `--quick` skips the typing measurement (useful if you've already calibrated once and just want to re-measure your taps).

---

## Configuration

Woodpecker stores its configuration in `~/.woodpecker/config.json`. After calibration, yours will look something like this:

```json
{
    "settings": {
        "min_peak": 0.18,
        "prominence_ratio": 8.0,
        "refractory_s": 0.15,
        "multi_tap_window": 0.6,
        "quiet_check_window_s": 0.15,
        "quiet_ratio": 0.30,
        "quiet_max_loud_fraction": 0.25,
        "noise_window_s": 0.6
    },
    "actions": {
        "2": "shortcuts run 'Shortcut0' && echo 'Shortcut 0 executed!'",
        "3": "shortcuts run 'Shortcut1' && echo 'Shortcut 1 executed!'",
        "4": "shortcuts run 'Shortcut2' && echo 'Shortcut 2 executed!'",
        "5": "shortcuts run 'Shortcut3' && echo 'Shortcut 3 executed!'"
    }
}
```

### Settings Reference

| Setting | What it does |
|---|---|
| `min_peak` | Minimum magnitude (g) for a tap to count. Raise if you get false positives from typing; lower if soft taps don't register. |
| `prominence_ratio` | A peak must be this many times louder than the recent noise floor. 8 is the sweet spot; 5–6 for noisy environments. |
| `refractory_s` | Silence enforced after a registered tap. Suppresses chassis ringing from double-counting. |
| `multi_tap_window` | Time after the last tap before Woodpecker fires the action. Shorter = more responsive, longer = easier to do slow taps. |
| `quiet_check_window_s` | How far around a peak to check for "is this really isolated?" The core typing-rejection mechanism. |
| `quiet_ratio` / `quiet_max_loud_fraction` | What counts as "loud surroundings." Used to reject typing bursts that contain a high spike. |
| `noise_window_s` | Rolling window for the adaptive noise-floor estimate. |

You almost never need to touch the bottom five. Calibration handles the top two.

### Mapping Taps to Shortcuts

**Step 1** — In **Shortcuts.app**, create your shortcut (e.g. `PlayMusic`, `ToggleDoNotDisturb`). Give it a descriptive name and save.

**Step 2** — Edit `~/.woodpecker/config.json` and add it to `actions`:

```json
"actions": {
    "2": "shortcuts run 'PlayMusic' && echo 'Music started!'",
    "3": "shortcuts run 'ToggleDoNotDisturb'",
    "4": "osascript -e 'display notification \"4 taps!\" with title \"Hello\"'"
}
```

The key is the number of taps (as a string), the value is any shell command — Shortcuts, AppleScript, bash, whatever. Changes take effect within 2 seconds thanks to live reload; no restart needed.

---

## Monitoring & Troubleshooting

### Service Status

Check if the service is running:

```bash
launchctl list | grep com.mac.woodpecker
```

### Live Monitoring

Watch live tap detection:

```bash
tail -f ~/.woodpecker/woodpecker.log
```

You should see `IMU available. Listening for taps...` on startup, and `Executing action for N taps: ...` whenever an action fires.

### Common Issues

**Typing triggers phantom taps.** Your `min_peak` is too low. Re-run calibration and type *firmly* during the typing-measurement step — that teaches Woodpecker your upper-bound keystroke strength. Or edit `config.json` and raise `min_peak` by 0.02 at a time.

**My taps don't fire.** Your `min_peak` is too high, or your taps are very soft. Re-run calibration, or tap the *lid* instead of the palm rest — the lid resonates more. Or manually lower `min_peak` by 0.02.

**Nothing works / logs show "IMU sensor not found."** Your Mac doesn't expose the SPU. This is expected on Intel Macs and original M1s — Woodpecker simply can't work on that hardware.

---

## Uninstallation

```bash
./scripts/uninstall.sh
```

You'll be asked to confirm, and offered a one-click backup of your calibrated config (written to `~/woodpecker-config-backup-<date>.json`) in case you decide to reinstall later. Then the daemon is stopped, the LaunchDaemon config removed, and `~/.woodpecker/` deleted.

---

## License

Woodpecker is released under the **Commons Clause License Condition v1.0**, based on the MIT License.

**Free for:** personal, educational, and non-commercial use. You can modify the source for your own needs.

**Not allowed:** Selling the software, or services whose value derives substantially from its functionality, to third parties for a fee.

**Distribution:** Any redistribution must include the original copyright notice and the Commons Clause condition.

Copyright © 2026 Vishal Mehra. The software is provided "as is", without warranty of any kind.

---

# For Developers

This section is for people who want to understand how Woodpecker works internally, modify it, or contribute.

## Repository Layout

```
Woodpecker/
├── src/
│   └── woodpecker.py           # The daemon — runs 24/7, reads IMU, fires actions
├── scripts/
│   ├── install.sh              # Sets up venv, LaunchDaemon, runs calibration
│   ├── uninstall.sh            # Removes everything (with confirmation + backup)
│   └── calibrate.py            # Interactive calibration tool
├── Resources/
│   └── Logo.png
├── LICENSE
└── README.md
```

After install, files land at:

```
~/.woodpecker/
├── .venv/                       # Python virtual environment
├── .user                        # Cached username (for root→user handoff)
├── woodpecker.py                # Copied from src/
├── calibrate.py                 # Copied from scripts/
├── config.json                  # User settings
└── woodpecker.log               # stdout + stderr of the daemon
```

The LaunchDaemon plist lives at `/Library/LaunchDaemons/com.mac.woodpecker.plist`.

## How It Runs

Woodpecker runs as a **LaunchDaemon**, not a LaunchAgent. This is because `macimu` (the IMU library) requires root to access the sensor. The plist boots the daemon at login, sets `WOODPECKER_USER` so the Python code can find the right home directory, and has `KeepAlive` so the daemon respawns if it crashes.

When the daemon needs to run a user-side command (e.g. `shortcuts run`), it drops privileges with `sudo -u $ACTUAL_USER sh -c "..."`. This is necessary so that Shortcuts.app and AppleScript have access to the user's GUI session.

## How Tap Detection Works

The core algorithm is a two-stage filter. For every IMU sample (~100 Hz):

1. **Compute vibration** as `|accel_magnitude - 1g|`. Gravity is subtracted so a stationary laptop reads ~0.
2. **Track candidate peaks** — once a sample clears `min_peak` and the adaptive prominence threshold, enter "peak tracking" mode. Watch the next ~50ms to see if something even higher comes along; update the candidate to the highest sample seen.
3. **Prominence gate** — the candidate peak must exceed `prominence_ratio × recent_noise_floor`. The noise floor is a rolling median (robust to outliers, adapts to environment).
4. **Isolation gate** — once the peak is committed, check the surrounding ±150ms window. If more than 25% of those samples are louder than 30% of the peak, reject it as typing noise. Real knocks are surrounded by near-silence; typing peaks are embedded in continuous activity.
5. **Refractory period** — after a registered tap, ignore samples for 150ms. This kills the chassis ring that follows a physical knock.
6. **Multi-tap accumulation** — count taps. When `multi_tap_window` elapses without another tap, fire the corresponding action (if tap count ≥ 2).

The isolation check is what separates this from a naive threshold detector. A raw threshold can't tell "one firm knock" from "random keystroke that happens to be loud today" — but a raw threshold plus a "what does the neighbourhood look like" check can.

See the `TapDetector` class in `src/woodpecker.py` for the implementation. The class is stateless w.r.t. time — it's fed one sample at a time, so it's easy to unit-test by synthesizing accelerometer data.

## How Calibration Works

`scripts/calibrate.py` is a self-contained tool that:

1. **Stops the daemon** (via `launchctl unload`) so the IMU is free.
2. **Opens the IMU directly** and runs three measurement steps:
   - 3 seconds of "sit still" → ambient noise floor (median, 95th %ile)
   - 5 seconds of "type normally" → typing spike distribution (99th %ile)
   - 2-, 3-, 4-, 5-tap bursts → peak magnitudes + inter-tap intervals
3. **Computes recommended settings.** `min_peak` is the max of four constraints: `0.7 × median_tap` (catch soft taps), `1.3 × typing_p99` (stay above typing), `4 × ambient_p95` (stay above room noise), and an adaptive absolute floor. `prominence_ratio` is scaled so `ratio × ambient_median ≤ min_peak`. `multi_tap_window` is `1.8 × slowest_inter_tap_interval`, capped to a sensible range.
4. **Writes `config.json`** after user confirmation, `chown`s it back to the real user (since the script runs as root), and restarts the daemon.

The tap-peak detection inside calibration uses the same peak-tracking logic as the runtime detector, so the numbers we record match what the daemon will see later.

## Live Config Reload

The daemon polls `config.json`'s mtime once every 2 seconds. If it changed, settings are reloaded and the `TapDetector` is reinitialized without restarting the process. This is how calibration's config write takes effect immediately.

## Building and Testing Locally

You can exercise the detector without any hardware by feeding it synthesized samples:

```python
from woodpecker import TapDetector, DEFAULT_CONFIG

det = TapDetector(DEFAULT_CONFIG["settings"], sample_rate_hz=100)

# Feed samples: (timestamp_seconds, vibration_magnitude_g)
for i in range(1000):
    t = i / 100.0
    v = 0.25 if i == 500 else 0.002  # one knock at t=5s
    fire_count = det.process(t, v)
    if fire_count:
        print(f"Would fire {fire_count}-tap action at t={t}")
```

This is how the detector was developed and tuned — by building a synthetic signal generator with typing, handling, and knock signatures, then optimizing the parameters on simulated data. See commit history for the simulation scripts.

## Modifying the Detection Algorithm

The main places to touch:

- **`TapDetector.process()`** in `src/woodpecker.py` — per-sample logic
- **`TapDetector._is_isolated()`** — the neighbourhood check
- **`TapDetector._noise_floor()`** — how we estimate ambient

Before shipping a change, it's wise to:

1. Stress-test against synthetic data with known ground truth (typing + deliberate knocks at known times). Count TPs, FPs, FNs.
2. Re-run calibration on your actual Mac and spot-check that recommended values didn't change wildly.
3. Watch `~/.woodpecker/woodpecker.log` for 10–15 minutes of normal use to make sure there are no regressions.

## Modifying Calibration

The `recommend_settings()` function in `scripts/calibrate.py` is pure math — no IMU needed — so it's easy to unit-test. Pass in sample `ambient_med`, `typing_p99`, `tap_peaks`, and inspect the output.

When changing the recommendation logic, walk through the "problematic" user profiles:
- Light tapper in a quiet room (taps ~0.09g, typing ~0.04g — the tightest case)
- Heavy typist (typing p99 ~0.20g)
- Laptop on lap (ambient ~0.02g, more handling noise)
- Wildly inconsistent taps (big spread)

## Known Limitations

- **Time-domain detection has theoretical limits.** Under enough typing activity, random keystroke alignment can produce peaks statistically indistinguishable from soft knocks. A frequency-domain check (short-time FFT — knocks on the chassis palm-rest produce different spectral signatures than keystroke vibrations propagated through the deck) would close this gap, but requires `numpy` and isn't currently included.
- **Root requirement.** Would love to run as a user LaunchAgent for simplicity, but `macimu` needs root. If Apple exposes IMU access via a user-space API in a future macOS version, the whole privilege-dropping dance goes away.
- **Ringing models are assumed-universal.** Calibration doesn't measure chassis decay time; a 16" MBP rings longer than a 13" MBA. Could theoretically auto-tune `refractory_s` from observed peak shapes.
- **No `calibrate --verify` mode.** Would be nice: run the detector live for 15s while the user types and taps, report detection stats.
- **Haptic feedback on tap registration** — would make the device feel more responsive. Possible via AppKit / private APIs.

## Contributing

Issues and PRs welcome. The code aims to be boring and readable over clever. When adding a feature, match the existing style: docstrings explain the *why*, not the *what*; parameters over magic numbers; comments for non-obvious constraints.
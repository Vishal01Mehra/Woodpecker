#!/usr/bin/env python3
"""
Woodpecker Calibration Tool

Interactively measures the user's tap strength and ambient noise floor,
then writes well-tuned values into ~/.woodpecker/config.json.

Usage:
    python3 calibrate.py            # full calibration (recommended)
    python3 calibrate.py --quick    # skip the typing test

This script must run as the logged-in user (not root), because it briefly
takes over the IMU. It will:
  1. Stop the background daemon
  2. Record samples from the IMU
  3. Update config.json
  4. Restart the daemon
"""
import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time

try:
    from macimu import IMU
except ImportError:
    print("ERROR: macimu not installed. Run this from the Woodpecker venv:")
    print("  ~/.woodpecker/.venv/bin/python3 calibrate.py")
    sys.exit(1)


# ---------- Paths ----------
# When run under sudo, we need the real user's home, not /var/root
REAL_USER = os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"
if REAL_USER == "root":
    # Fallback: find the user by looking for an existing .woodpecker dir in /Users
    for name in os.listdir("/Users"):
        if name in ("Shared", ".localized"):
            continue
        if os.path.exists(f"/Users/{name}/.woodpecker"):
            REAL_USER = name
            break

USER_HOME = f"/Users/{REAL_USER}"
CONFIG_PATH = os.path.join(USER_HOME, ".woodpecker", "config.json")
DAEMON_LABEL = "com.mac.woodpecker"
DAEMON_PLIST = "/Library/LaunchDaemons/com.mac.woodpecker.plist"


# ---------- Sampling helpers ----------

def _vibration(sample):
    mag = math.sqrt(sample.x**2 + sample.y**2 + sample.z**2)
    return abs(mag - 1.0)


def record_for(imu, duration_s, description=None):
    """Collect vibration samples for a fixed duration."""
    if description:
        print(f"   {description}")
    samples = []
    start = time.time()
    for s in imu.stream_accel():
        samples.append(_vibration(s))
        if time.time() - start >= duration_s:
            break
    return samples


def record_tap_burst(imu, expected_count, window_s=3.0,
                     min_trigger=0.04, refractory_s=0.12):
    """
    Record a burst of taps. Returns (peak_list, timing_list).

    Uses the same peak-tracking logic as the runtime detector:
      - wait for sample ≥ min_trigger
      - watch next 150ms for the true peak (sample may keep rising)
      - impose a refractory period so chassis ring doesn't double-count
      - keep going until window_s elapses since the last tap OR 6s total

    Returns lists of length ≤ expected_count of peak magnitudes and the
    timestamps they occurred at.
    """
    peaks = []
    times = []
    start = time.time()
    last_tap_time = None
    total_timeout = 8.0  # hard cap on waiting

    in_peak = False
    candidate_peak = 0.0
    candidate_time = 0.0
    peak_tracking_start = 0.0

    for s in imu.stream_accel():
        now = time.time()
        v = _vibration(s)

        # Global timeout
        if now - start > total_timeout:
            break

        # End-of-burst detection: N taps in, then window_s of quiet
        if len(peaks) > 0 and last_tap_time is not None:
            if now - last_tap_time > window_s:
                break

        # In refractory from a just-committed tap?
        if last_tap_time is not None and (now - last_tap_time) < refractory_s:
            continue

        if not in_peak:
            # Looking for the start of a new tap
            if v >= min_trigger:
                in_peak = True
                candidate_peak = v
                candidate_time = now
                peak_tracking_start = now
        else:
            # Currently tracking a peak
            if v > candidate_peak:
                candidate_peak = v
                candidate_time = now
            # Commit after 150ms of tracking
            if now - peak_tracking_start >= 0.15:
                peaks.append(candidate_peak)
                times.append(candidate_time)
                last_tap_time = candidate_time
                in_peak = False
                candidate_peak = 0.0
                # Stop early if we've collected everything we expected
                if len(peaks) >= expected_count:
                    # But keep listening briefly to see if they over-tapped
                    # No — just return what we got
                    # Actually we should return to let caller decide; but we also
                    # want to finish after seeing expected_count + a short wait
                    pass

    return peaks, times


def step_multi_tap_calibration(imu):
    """
    Ask the user to do 2, 3, 4, and 5 taps in sequence. Record each
    burst and collect all the individual peak magnitudes.
    """
    print()
    print("─" * 60)
    print("STEP 3 / 3: Tap calibration (2, 3, 4, 5 taps)")
    print("─" * 60)
    print("Tap on your MacBook the way you want to trigger actions.")
    print("Aim for consistent firmness. The palm rest, lid, or side work well.")
    print()

    all_peaks = []
    all_intervals = []  # time between consecutive taps in a burst
    burst_results = {}  # count -> (peaks, times)

    for expected in [2, 3, 4, 5]:
        attempts = 0
        while attempts < 3:
            attempts += 1
            print(f"   Do {expected} taps now... ", end="", flush=True)
            # Brief pause so their input() keystroke doesn't get recorded
            time.sleep(0.4)
            peaks, times = record_tap_burst(imu, expected_count=expected)

            if len(peaks) == expected:
                print(f"got {len(peaks)}: {[round(p, 3) for p in peaks]}")
                all_peaks.extend(peaks)
                # Compute inter-tap intervals
                if len(times) >= 2:
                    intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
                    all_intervals.extend(intervals)
                burst_results[expected] = (peaks, times)
                break
            elif len(peaks) < expected:
                print(f"only got {len(peaks)}. Try again — tap a bit firmer.")
            else:
                print(f"got {len(peaks)} (expected {expected}). "
                      "Try again — one tap at a time, same rhythm.")
                # Still record the peaks though; they're real taps
                all_peaks.extend(peaks)

        if expected not in burst_results and attempts >= 3:
            print(f"   Couldn't get a clean {expected}-tap burst. Moving on.")

    if not all_peaks:
        print("   No taps were successfully recorded.")
        return None, None, None

    return all_peaks, all_intervals, burst_results


# ---------- Daemon control ----------

def daemon_is_loaded():
    try:
        out = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5
        )
        return DAEMON_LABEL in out.stdout
    except Exception:
        return False


def _launchctl(*args, **kwargs):
    """Run launchctl, using sudo only if we're not already root."""
    cmd = list(args)
    if os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    return subprocess.run(cmd, **kwargs)


def stop_daemon():
    if not daemon_is_loaded():
        return False
    print("⏸  Stopping Woodpecker daemon so we can use the IMU...")
    try:
        _launchctl("launchctl", "unload", DAEMON_PLIST,
                   check=False, timeout=10)
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"   (couldn't stop daemon: {e})")
        return False


def start_daemon():
    print("▶️  Restarting Woodpecker daemon...")
    try:
        _launchctl("launchctl", "load", DAEMON_PLIST,
                   check=False, timeout=10)
    except Exception as e:
        print(f"   (couldn't restart daemon: {e})")
        print(f"   You can start it manually: sudo launchctl load {DAEMON_PLIST}")


# ---------- Config read/write ----------

DEFAULT_SETTINGS = {
    "min_peak": 0.18,
    "prominence_ratio": 8.0,
    "refractory_s": 0.15,
    "multi_tap_window": 0.6,
    "quiet_check_window_s": 0.15,
    "quiet_ratio": 0.30,
    "quiet_max_loud_fraction": 0.25,
    "noise_window_s": 0.6
}

DEFAULT_ACTIONS = {
    "2": "shortcuts run 'Shortcut0' && echo 'Shortcut 0 executed!'",
    "3": "shortcuts run 'Shortcut1' && echo 'Shortcut 1 executed!'",
    "4": "shortcuts run 'Shortcut2' && echo 'Shortcut 2 executed!'",
    "5": "shortcuts run 'Shortcut3' && echo 'Shortcut 3 executed!'"
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        return {"settings": dict(DEFAULT_SETTINGS), "actions": dict(DEFAULT_ACTIONS)}
    with open(CONFIG_PATH) as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError:
            print("⚠️  config.json has syntax errors; replacing with defaults.")
            return {"settings": dict(DEFAULT_SETTINGS), "actions": dict(DEFAULT_ACTIONS)}
    cfg.setdefault("settings", {})
    cfg.setdefault("actions", dict(DEFAULT_ACTIONS))
    # Fill in any missing setting keys (forwards compat)
    for k, v in DEFAULT_SETTINGS.items():
        cfg["settings"].setdefault(k, v)
    return cfg


def save_config(cfg):
    import pwd
    config_dir = os.path.dirname(CONFIG_PATH)
    os.makedirs(config_dir, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)

    # When running as root on behalf of a user, hand ownership back so the
    # daemon's non-root config reads/writes keep working.
    if os.geteuid() == 0 and REAL_USER != "root":
        try:
            pw = pwd.getpwnam(REAL_USER)
            os.chown(config_dir, pw.pw_uid, pw.pw_gid)
            os.chown(CONFIG_PATH, pw.pw_uid, pw.pw_gid)
        except (KeyError, OSError) as e:
            print(f"   ⚠️  Couldn't chown config back to {REAL_USER}: {e}")


# ---------- Calibration steps ----------

def step_ambient_noise(imu):
    print()
    print("─" * 60)
    print("STEP 1 / 3: Ambient noise floor")
    print("─" * 60)
    print("Please leave your laptop completely still for 3 seconds.")
    print("Do not touch the keyboard, trackpad, or chassis.")
    input("Press ENTER when ready...")
    samples = record_for(imu, 3.0, "   Recording...")
    # Median is robust; 95th percentile gives us the "busy" baseline
    med = statistics.median(samples)
    p95 = sorted(samples)[int(len(samples) * 0.95)]
    print(f"   Ambient median: {med:.4f}g   (95th %ile: {p95:.4f}g)")
    return med, p95


def step_typing_noise(imu):
    print()
    print("─" * 60)
    print("STEP 2 / 3: Typing noise (optional but recommended)")
    print("─" * 60)
    print("Type normally for 5 seconds — anything you like, as heavy as you'd")
    print("realistically type. We need to see how loud your typing gets so we")
    print("can set a threshold that won't trigger on keystrokes.")
    input("Press ENTER when ready to start typing...")
    samples = record_for(imu, 5.0, "   Recording — type away...")
    # What matters: the top-end of typing spikes
    p95 = sorted(samples)[int(len(samples) * 0.95)]
    p99 = sorted(samples)[int(len(samples) * 0.99)]
    peak = max(samples)
    print(f"   Typing peaks — 95th: {p95:.4f}g  99th: {p99:.4f}g  max: {peak:.4f}g")
    return p99, peak


def step_tap_strength(imu, n_taps=5):
    """Deprecated — kept as a fallback only."""
    return step_multi_tap_calibration(imu)[0] or []


# ---------- Recommendation logic ----------

def recommend_settings(ambient_med, ambient_p95,
                       typing_p99, typing_max,
                       tap_peaks):
    """
    Given what we measured, produce good settings.

    Key reasoning:
      - min_peak should be LOW enough to catch the user's softest tap:
        set it to 0.7 × (median tap peak), which tolerates a soft tap.
      - But it must also be HIGHER than typing_p99 (else typing triggers).
        If those two constraints conflict, warn the user.
      - prominence_ratio of 8 usually works; drop to 6 for unusually noisy
        environments where 8 × ambient would already exceed min_peak.
    """
def recommend_settings(ambient_med, ambient_p95,
                       typing_p99, typing_max,
                       tap_peaks, tap_intervals=None):
    """
    Given what we measured, produce good settings.

    Key reasoning:
      - min_peak should be LOW enough to catch the user's softest tap:
        set it to 0.7 × (median tap peak), which tolerates a soft tap.
      - But it must also be HIGHER than typing_p99 (else typing triggers).
        If those two constraints conflict, warn the user.
      - prominence_ratio of 8 usually works; drop to 6 for unusually noisy
        environments where 8 × ambient would already exceed min_peak.
      - multi_tap_window should cover the user's slowest natural gap
        between taps, with margin — otherwise a slow 5-tap is read as
        two separate groups.
    """
    median_tap = statistics.median(tap_peaks)
    min_tap = min(tap_peaks)

    # Target: catch 70% of the median tap strength
    from_taps = 0.70 * median_tap

    # Floor: well above typing (if measured)
    from_typing = typing_p99 * 1.3 if typing_p99 is not None else 0.0

    # Absolute floor — adaptive to actual tap strength
    # For soft tappers, use a lower absolute floor since their taps
    # genuinely are that soft. For firm tappers, enforce a higher floor
    # to reject spurious noise.
    abs_floor = max(0.05, min(0.10, 0.5 * median_tap))
    from_ambient = ambient_p95 * 4.0

    min_peak = max(from_taps, from_typing, from_ambient, abs_floor)
    min_peak = round(min_peak, 3)

    # Sanity: prominence_ratio × ambient_median should not exceed min_peak
    if ambient_med > 0:
        implied_ratio = min_peak / max(ambient_med, 0.005)
        prominence_ratio = min(8.0, max(5.0, implied_ratio * 0.7))
    else:
        prominence_ratio = 8.0
    prominence_ratio = round(prominence_ratio, 1)

    # Multi-tap window from actual inter-tap intervals
    result = {"min_peak": min_peak, "prominence_ratio": prominence_ratio}
    if tap_intervals and len(tap_intervals) >= 2:
        max_interval = max(tap_intervals)
        # Window = slowest natural gap × 1.8 safety, capped to sensible range
        recommended_window = min(1.2, max(0.4, max_interval * 1.8))
        result["multi_tap_window"] = round(recommended_window, 2)

    # Warnings
    warnings = []
    if typing_p99 is not None and from_typing > from_taps:
        warnings.append(
            f"Your typing is loud (99th %ile {typing_p99:.3f}g) relative to "
            f"your taps (median {median_tap:.3f}g). Threshold raised to "
            f"{min_peak:.3f}g to prevent typing triggers. "
            "You may need to tap a bit firmer."
        )
    if min_tap < min_peak:
        warnings.append(
            f"Your softest tap ({min_tap:.3f}g) is below the chosen threshold "
            f"({min_peak:.3f}g). That tap might not register. Try tapping "
            "more consistently, or lower min_peak manually if it feels off."
        )
    tap_spread = max(tap_peaks) - min(tap_peaks)
    if tap_spread > 0.5 * median_tap:
        warnings.append(
            f"Your taps varied a lot ({min(tap_peaks):.3f}g to {max(tap_peaks):.3f}g). "
            "More consistent taps would give better calibration."
        )

    return result, warnings


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="skip the typing measurement")
    args = parser.parse_args()

    print("🪵 Woodpecker Calibration")
    print()

    if os.geteuid() != 0:
        print("❌ macimu requires root to access the IMU sensor.")
        print("   Re-run with sudo, keeping the venv Python:")
        print()
        print("     sudo ~/.woodpecker/.venv/bin/python3 calibrate.py")
        print()
        sys.exit(1)

    if REAL_USER == "root":
        print("❌ Could not determine the real (non-root) user.")
        print("   Make sure you ran the command with 'sudo', not as root directly.")
        sys.exit(1)

    print(f"   Running as root on behalf of user: {REAL_USER}")
    print(f"   Config will be written to: {CONFIG_PATH}")
    print()

    if not IMU.available():
        print("ERROR: IMU sensor not found. Apple Silicon M2+ required.")
        sys.exit(1)

    daemon_was_running = stop_daemon()

    tap_peaks = []
    tap_intervals = []
    burst_results = {}

    try:
        with IMU(accel=True, gyro=False, decimation=8) as imu:
            ambient_med, ambient_p95 = step_ambient_noise(imu)

            if args.quick:
                typing_p99, typing_max = None, None
                print("\n(Skipping typing measurement)")
            else:
                typing_p99, typing_max = step_typing_noise(imu)

            tap_peaks, tap_intervals, burst_results = step_multi_tap_calibration(imu)
    finally:
        if daemon_was_running:
            start_daemon()

    if not tap_peaks:
        print("\n❌ No taps recorded. Calibration aborted.")
        sys.exit(1)

    # Compute settings
    new_values, warnings = recommend_settings(
        ambient_med, ambient_p95,
        typing_p99, typing_max,
        tap_peaks, tap_intervals
    )

    # Show summary
    print()
    print("=" * 60)
    print("CALIBRATION RESULTS")
    print("=" * 60)
    print(f"  Ambient noise (median):  {ambient_med:.4f}g")
    if typing_p99 is not None:
        print(f"  Typing 99th percentile:  {typing_p99:.4f}g")
    print(f"  Tap peaks recorded:      {len(tap_peaks)} across 2/3/4/5-tap bursts")
    if burst_results:
        for count, (peaks, times) in sorted(burst_results.items()):
            p_str = [round(p, 3) for p in peaks]
            print(f"    {count}-tap burst: peaks={p_str}")
    print(f"  Tap median:              {statistics.median(tap_peaks):.3f}g")
    print(f"  Tap max:                 {max(tap_peaks):.3f}g")
    if tap_intervals:
        print(f"  Inter-tap intervals:     "
              f"min={min(tap_intervals):.2f}s, "
              f"max={max(tap_intervals):.2f}s, "
              f"median={statistics.median(tap_intervals):.2f}s")
    print()
    print("  Recommended settings:")
    for k, v in new_values.items():
        print(f"    {k}: {v}")

    if warnings:
        print()
        print("  ⚠️  Notes:")
        for w in warnings:
            print(f"    - {w}")

    print()
    confirm = input("Write these to ~/.woodpecker/config.json? [Y/n] ").strip().lower()
    if confirm in ("", "y", "yes"):
        cfg = load_config()
        cfg["settings"].update(new_values)
        save_config(cfg)
        print(f"✅ Saved to {CONFIG_PATH}")
        print("   The running daemon will pick up the new settings within 2 seconds.")
    else:
        print("❌ Not saved. Your existing config is unchanged.")


if __name__ == "__main__":
    main()

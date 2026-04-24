#!/bin/bash
set -e

echo "🪵 Installing Woodpecker..."
echo ""

# Cache sudo credentials up front so they don't expire mid-install
# (otherwise the user might be re-prompted during calibration).
sudo -v

# Get the actual user context
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME="/Users/$ACTUAL_USER"
INSTALL_DIR="$USER_HOME/.woodpecker"
DAEMON_PLIST="/Library/LaunchDaemons/com.mac.woodpecker.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Stop the daemon if it's running (but don't nuke the dir yet — we want
#    to preserve a user's tuned config.json across reinstalls)
sudo launchctl unload "$DAEMON_PLIST" 2>/dev/null || true
sudo rm -f "$DAEMON_PLIST" 2>/dev/null || true

# 2. Preserve existing config.json if present (upgrade path)
PRESERVED_CONFIG=""
if [ -f "$INSTALL_DIR/config.json" ]; then
    PRESERVED_CONFIG=$(mktemp)
    cp "$INSTALL_DIR/config.json" "$PRESERVED_CONFIG"
    echo "📦 Existing config.json found — will preserve it across reinstall."
fi

# 3. Wipe old install dir (except what we just saved)
sudo rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# 4. Copy program files
cp "$SCRIPT_DIR/../src/woodpecker.py" "$INSTALL_DIR/woodpecker.py"
cp "$SCRIPT_DIR/calibrate.py"         "$INSTALL_DIR/calibrate.py"
chmod +x "$INSTALL_DIR/calibrate.py"

# 5. Restore preserved config (if any)
HAD_EXISTING_CONFIG=0
if [ -n "$PRESERVED_CONFIG" ]; then
    cp "$PRESERVED_CONFIG" "$INSTALL_DIR/config.json"
    rm -f "$PRESERVED_CONFIG"
    HAD_EXISTING_CONFIG=1
    echo "✅ Restored your previous config.json."
fi

# 6. Setup venv + dependencies
echo "📦 Setting up Python venv and installing dependencies..."
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet macimu
echo "$ACTUAL_USER" > "$INSTALL_DIR/.user"

# Ownership: ensure everything in $INSTALL_DIR belongs to the real user
# so calibrate.py (run via sudo) can write config.json and have it stay
# user-owned, and so the daemon's non-root config reads keep working.
sudo chown -R "$ACTUAL_USER" "$INSTALL_DIR"

# 7. Create LaunchDaemon
sudo bash << SUDOSCRIPT
cat > "$DAEMON_PLIST" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mac.woodpecker</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/python3</string>
        <string>$INSTALL_DIR/woodpecker.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>WOODPECKER_USER</key>
        <string>$ACTUAL_USER</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/woodpecker.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/woodpecker.log</string>
</dict>
</plist>
PLIST
chown root:wheel "$DAEMON_PLIST"
chmod 644 "$DAEMON_PLIST"
launchctl load "$DAEMON_PLIST"
SUDOSCRIPT

echo ""
echo "✅ Installation complete for $ACTUAL_USER!"
echo ""

# 8. Offer to run calibration
# Only prompt if this is an interactive terminal — skip in CI/automated runs
if [ -t 0 ] && [ -t 1 ]; then
    if [ "$HAD_EXISTING_CONFIG" = "1" ]; then
        echo "ℹ️  Your existing calibration was preserved — skipping recalibration."
        echo "   To re-calibrate later, run:"
        echo "     sudo $INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/calibrate.py"
    else
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Calibration is strongly recommended for best accuracy."
        echo "  It takes ~30 seconds and teaches Woodpecker what your"
        echo "  taps feel like vs. your typing."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        read -r -p "Run calibration now? [Y/n] " RUN_CAL
        RUN_CAL=${RUN_CAL:-Y}
        if [[ "$RUN_CAL" =~ ^[Yy] ]]; then
            echo ""
            # Refresh sudo in case time passed waiting on the prompt
            sudo -v
            # Pass SUDO_USER through so calibrate.py knows the real user.
            sudo -E SUDO_USER="$ACTUAL_USER" \
                "$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/calibrate.py" || {
                echo ""
                echo "⚠️  Calibration didn't complete. You can run it later with:"
                echo "     sudo $INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/calibrate.py"
            }
        else
            echo ""
            echo "Skipped. To calibrate later, run:"
            echo "  sudo $INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/calibrate.py"
        fi
    fi
else
    echo "ℹ️  Non-interactive install detected — skipping calibration prompt."
    echo "   To calibrate, run:"
    echo "     sudo $INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/calibrate.py"
fi

echo ""
echo "🪵 Woodpecker is running. Happy tapping!"

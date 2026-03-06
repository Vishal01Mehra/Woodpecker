#!/bin/bash

set -e

echo "🪵 Installing Woodpecker..."
echo ""

# Get the actual user
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$ACTUAL_USER)
INSTALL_DIR="$USER_HOME/.woodpecker"
DAEMON_PLIST="/Library/LaunchDaemons/com.mac.woodpecker.plist"

# 1. Clean up any old installations
if [ -f "$DAEMON_PLIST" ]; then
    echo "🧹 Cleaning up old installation..."
    sudo launchctl unload "$DAEMON_PLIST" 2>/dev/null || true
    sudo rm "$DAEMON_PLIST" || true
fi

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

# 2. Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# 3. Download the main script
echo "⬇️  Downloading Woodpecker script..."
curl -sSL -o "$INSTALL_DIR/woodpecker.py" \
  https://raw.githubusercontent.com/Vishal01Mehra/Woodpecker/main/src/woodpecker.py

# 4. Create Python virtual environment
echo "🐍 Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/.venv"

# 5. Install dependencies
echo "📦 Installing dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install --quiet macimu

# 6. Create default config
echo "⚙️  Creating configuration..."
cat > "$INSTALL_DIR/config.json" << 'EOF'
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
EOF

# 7. Write username for daemon
echo "$ACTUAL_USER" > "$INSTALL_DIR/.user"

# 8. Create LaunchDaemon plist (requires sudo)
echo "🔧 Setting up system service..."
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

# 9. Verify installation
sleep 2
echo ""
if launchctl list | grep -q com.mac.woodpecker; then
    echo "✅ Installation Complete!"
    echo ""
    echo "Woodpecker is now running in the background."
    echo ""
    echo "📋 Quick Commands:"
    echo "   Status:  launchctl list | grep com.mac.woodpecker"
    echo "   Logs:    tail -f $INSTALL_DIR/woodpecker.log"
    echo "   Config:  nano $INSTALL_DIR/config.json"
    echo "   Stop:    sudo launchctl unload $DAEMON_PLIST"
    echo ""
    echo "Try tapping your MacBook to test it!"
    echo ""
else
    echo "⚠️  Installation may have issues. Check logs:"
    echo "    tail -f $INSTALL_DIR/woodpecker.log"
    exit 1
fi

echo "Happy tapping! 🪵"

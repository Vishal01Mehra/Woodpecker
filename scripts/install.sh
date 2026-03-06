#!/bin/bash

set -e  # Exit on error

echo "🪵 Installing Woodpecker..."
echo ""

# Get the actual user (in case running with sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$ACTUAL_USER)
INSTALL_DIR="$USER_HOME/.woodpecker"

# 1. Create installation directory
echo "📁 Creating installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# 2. Download the main script
echo "⬇️  Downloading Woodpecker script..."
curl -sSL -o "$INSTALL_DIR/woodpecker.py" \
  https://raw.githubusercontent.com/Vishal01Mehra/Woodpecker/main/src/woodpecker.py

# 3. Create Python virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/.venv"

# 4. Install dependencies
echo "📦 Installing dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install --quiet macimu

# 5. Create default config if it doesn't exist
echo "⚙️  Creating configuration file..."
if [ ! -f "$INSTALL_DIR/config.json" ]; then
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
fi

# 6. Create launchd plist file
echo "🔧 Setting up daemon service..."
PLIST_PATH="/tmp/com.mac.woodpecker.plist"
cat > "$PLIST_PATH" << EOF
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
EOF

# 7. Install and start the daemon
echo "🚀 Installing and starting daemon service..."
sudo mv "$PLIST_PATH" /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.mac.woodpecker.plist
sudo chmod 644 /Library/LaunchDaemons/com.mac.woodpecker.plist

# Load the daemon
sudo launchctl load /Library/LaunchDaemons/com.mac.woodpecker.plist

echo ""
echo "✅ Installation Complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Give your MacBook a gentle tap to test it"
echo "   2. Check status: launchctl list | grep com.mac.woodpecker"
echo "   3. View logs: log show --predicate 'process == \"woodpecker\"' --last 1h"
echo "   4. Edit config: nano $INSTALL_DIR/config.json"
echo ""
echo "📖 Documentation: https://github.com/Vishal01Mehra/Woodpecker"
echo ""
echo "Happy tapping! 🪵"

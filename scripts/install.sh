#!/bin/bash
set -e

echo "🪵 Installing Woodpecker Locally..."

# Get the actual user context
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME="/Users/$ACTUAL_USER"
INSTALL_DIR="$USER_HOME/.woodpecker"
DAEMON_PLIST="/Library/LaunchDaemons/com.mac.woodpecker.plist"

# 1. Clean up old installation
sudo launchctl unload "$DAEMON_PLIST" 2>/dev/null || true
sudo rm -rf "$INSTALL_DIR" "$DAEMON_PLIST" || true

# 2. Create directory and COPY local file
mkdir -p "$INSTALL_DIR"
# This line assumes you are running the script from the 'scripts' folder
cp "$(dirname "$0")/../src/woodpecker.py" "$INSTALL_DIR/woodpecker.py"

# 3. Setup Env and Config
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet macimu
echo "$ACTUAL_USER" > "$INSTALL_DIR/.user"

# 4. Create LaunchDaemon with injected Environment Variable
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

echo "✅ Local Installation Complete for $ACTUAL_USER!"
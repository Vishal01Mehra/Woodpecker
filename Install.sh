#!/bin/bash

echo "🪵 Installing Woodpecker (MacBook Accelerometer Tap Detection)..."

# 1. Ask for sudo password upfront
sudo -v

# 2. Create the hidden application folder
INSTALL_DIR="$HOME/.woodpecker"
mkdir -p "$INSTALL_DIR"

# 3. Download the Python script from GitHub
echo "📥 Downloading woodpecker.py..."
# CHANGE THIS URL if your GitHub username or repository name is different!
curl -sSL -o "$INSTALL_DIR/woodpecker.py" "https://raw.githubusercontent.com/TeravoltLabs/Woodpecker/main/woodpecker.py"

# 4. Setup virtual environment & install dependencies securely
echo "📦 Installing macimu dependency..."
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install macimu --quiet

# 5. Create the macOS Launch Daemon file for background execution
PLIST_PATH="/tmp/com.mac.woodpecker.plist"
cat <<EOF > "$PLIST_PATH"
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
</dict>
</plist>
EOF

# 6. Move the service file to the system folder and activate it
echo "⚙️ Setting up background service..."
sudo mv "$PLIST_PATH" /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.mac.woodpecker.plist
sudo launchctl load /Library/LaunchDaemons/com.mac.woodpecker.plist

echo ""
echo "✅ Installation Complete!"
echo "Woodpecker is now running silently in the background."
echo "Config file generated at: ~/.woodpecker/config.json"
echo "Give your MacBook a triple-tap to test it out!"
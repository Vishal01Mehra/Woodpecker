#!/bin/bash

echo "🪵 Uninstalling Woodpecker..."
echo ""

# 1. Stop the daemon if it's running
echo "⏹️  Stopping Woodpecker daemon..."
sudo launchctl stop com.mac.woodpecker 2>/dev/null

# 2. Unload the launch daemon
echo "🔌 Unloading launchd service..."
sudo launchctl unload /Library/LaunchDaemons/com.mac.woodpecker.plist 2>/dev/null

# 3. Remove the plist file
echo "🗑️  Removing daemon configuration..."
sudo rm -f /Library/LaunchDaemons/com.mac.woodpecker.plist

# 4. Remove the installation directory
echo "🗑️  Removing Woodpecker files..."
rm -rf ~/.woodpecker

# 5. Verify removal
echo ""
echo "✅ Uninstall Complete!"
echo ""

# Check if daemon is still present
if launchctl list | grep -q "com.mac.woodpecker"; then
    echo "⚠️  Warning: Daemon still appears in launchctl list. You may need to restart your Mac."
else
    echo "✓ Woodpecker has been completely removed"
fi

echo "📁 Config directory and all files deleted from ~/.woodpecker"
echo ""
echo "Your MacBook is back to normal! 👋"

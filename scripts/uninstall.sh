#!/bin/bash

echo "🪵 Uninstalling Woodpecker..."
echo ""

# Figure out the real user (same logic as install.sh)
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME="/Users/$ACTUAL_USER"
INSTALL_DIR="$USER_HOME/.woodpecker"
DAEMON_PLIST="/Library/LaunchDaemons/com.mac.woodpecker.plist"

# Confirmation prompt (skip in non-interactive shells)
if [ -t 0 ] && [ -t 1 ]; then
    echo "This will:"
    echo "  • Stop the Woodpecker background daemon"
    echo "  • Remove the launch configuration at $DAEMON_PLIST"
    echo "  • Delete $INSTALL_DIR and everything in it"
    echo ""
    read -r -p "Continue? [y/N] " CONFIRM
    CONFIRM=${CONFIRM:-N}
    if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
        echo "Aborted."
        exit 0
    fi

    # Offer to back up config.json in case they reinstall later
    if [ -f "$INSTALL_DIR/config.json" ]; then
        BACKUP_PATH="$USER_HOME/woodpecker-config-backup-$(date +%Y%m%d-%H%M%S).json"
        read -r -p "Back up your calibrated config to ${BACKUP_PATH}? [Y/n] " BACKUP
        BACKUP=${BACKUP:-Y}
        if [[ "$BACKUP" =~ ^[Yy] ]]; then
            cp "$INSTALL_DIR/config.json" "$BACKUP_PATH"
            chown "$ACTUAL_USER" "$BACKUP_PATH"
            echo "📦 Config backed up to $BACKUP_PATH"
        fi
    fi
    echo ""
fi

# 1. Stop the daemon
echo "⏹️  Stopping Woodpecker daemon..."
sudo launchctl stop com.mac.woodpecker 2>/dev/null

# 2. Unload the launch daemon
echo "🔌 Unloading launchd service..."
sudo launchctl unload "$DAEMON_PLIST" 2>/dev/null

# 3. Remove the plist file
echo "🗑️  Removing daemon configuration..."
sudo rm -f "$DAEMON_PLIST"

# 4. Remove the installation directory
#    (calibrate.py, woodpecker.py, .venv, config.json, logs — all go)
echo "🗑️  Removing Woodpecker files..."
sudo rm -rf "$INSTALL_DIR"

echo ""
echo "✅ Uninstall Complete!"
echo ""

# 5. Verify removal
if launchctl list 2>/dev/null | grep -q "com.mac.woodpecker"; then
    echo "⚠️  Warning: Daemon still appears in launchctl list."
    echo "   You may need to restart your Mac to fully clear it."
else
    echo "✓ Woodpecker has been completely removed"
fi

echo "📁 Config directory and all files deleted from $INSTALL_DIR"
echo ""
echo "Your MacBook is back to normal! 👋"

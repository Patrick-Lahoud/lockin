#!/bin/bash
# Lock In: remove the laptop guard and any block it left behind.
set -uo pipefail
DIR="/Library/Application Support/LockIn"
sudo launchctl bootout system/ca.lockin.guard 2>/dev/null
launchctl bootout "gui/$(id -u)/ca.lockin.tabs" 2>/dev/null
launchctl bootout "gui/$(id -u)/ca.lockin.screen" 2>/dev/null
if [ -f "$DIR/lockin_guard.py" ]; then
  sudo python3 "$DIR/lockin_guard.py" clear
fi
sudo rm -f /Library/LaunchDaemons/ca.lockin.guard.plist
rm -f "$HOME/Library/LaunchAgents/ca.lockin.tabs.plist"
rm -f "$HOME/Library/LaunchAgents/ca.lockin.screen.plist"
sudo rm -rf "$DIR"
echo "Lock In guard removed. /etc/hosts is clean."

#!/bin/bash
# Lock In: install the laptop guard on macOS (one admin password, once).
#   ./install_mac.sh http://lockin.local:8000
# After this, the laptop follows the box automatically. No more password prompts.
set -euo pipefail

PI_URL="${1:-http://lockin.local:8000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="/Library/Application Support/LockIn"
SYS_LABEL="ca.lockin.guard"
TAB_LABEL="ca.lockin.tabs"
SYS_PLIST="/Library/LaunchDaemons/$SYS_LABEL.plist"
TAB_PLIST="$HOME/Library/LaunchAgents/$TAB_LABEL.plist"

[[ "$PI_URL" =~ ^https?://[A-Za-z0-9.:-]+$ ]] || { echo "PI_URL looks wrong: $PI_URL (example: http://lockin.local:8000)"; exit 1; }

# Root runs this Python, so it must not be writable by a normal user (otherwise any app
# could swap it and get root). Prefer Apple's SIP-protected /usr/bin/python3.
PY=""
if xcode-select -p >/dev/null 2>&1 && /usr/bin/python3 -c 'import sys; assert sys.version_info >= (3, 9)' 2>/dev/null; then
  PY="/usr/bin/python3"
else
  PY="$(python3 -c 'import sys; print(sys.executable)')"
  [[ -x "$PY" ]] || { echo "python3 not found. Install Apple's: xcode-select --install"; exit 1; }
  "$PY" -c 'import sys; assert sys.version_info >= (3, 9)' || { echo "Need Python 3.9+"; exit 1; }
  if [[ "$(stat -f %Su "$PY")" != "root" ]]; then
    echo "WARNING: $PY is owned by $(stat -f %Su "$PY"), not root. Fine for the hackathon;"
    echo "         for real use run 'xcode-select --install' and re-run this script."
  fi
fi
echo "Using Python: $PY"

echo "Checking the Pi at $PI_URL ..."
if curl -s -m 3 "$PI_URL/state" >/dev/null; then echo "  Pi reachable ✓"; else echo "  WARNING: can't reach the Pi right now. Installing anyway; it will connect when the Pi is up."; fi

echo "Installing (macOS will ask for your password once)..."
sudo mkdir -p "$DIR"
sudo cp "$HERE/lockin_guard.py" "$DIR/lockin_guard.py"
printf '{"pi_url": "%s"}\n' "$PI_URL" | sudo tee "$DIR/config.json" >/dev/null
sudo chown -R root:wheel "$DIR"
sudo chmod 755 "$DIR"
sudo chmod 644 "$DIR/lockin_guard.py" "$DIR/config.json"

# 1) root daemon: hosts file + quitting apps. Runs at boot, restarts if killed.
sudo tee "$SYS_PLIST" >/dev/null <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$SYS_LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$DIR/lockin_guard.py</string><string>system</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/var/log/lockin-guard.log</string>
  <key>StandardErrorPath</key><string>/var/log/lockin-guard.log</string>
</dict></plist>
EOF
sudo chown root:wheel "$SYS_PLIST"
sudo chmod 644 "$SYS_PLIST"
sudo launchctl bootout "system/$SYS_LABEL" 2>/dev/null || true
sudo launchctl bootstrap system "$SYS_PLIST"

# 2) user agent: kicks already-open tabs to the Locked In page.
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$TAB_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$TAB_LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$DIR/lockin_guard.py</string><string>tabs</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/lockin-tabs.log</string>
  <key>StandardErrorPath</key><string>/tmp/lockin-tabs.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$TAB_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$TAB_PLIST"

echo
echo "Installed ✓  The laptop now follows the box at $PI_URL"
echo "  Logs:       tail -f /var/log/lockin-guard.log /tmp/lockin-tabs.log"
echo "  Uninstall:  ./uninstall_mac.sh"
echo
echo "First lock only: macOS asks 'python3 wants to control Safari / Google Chrome / Yandex'. Click OK."

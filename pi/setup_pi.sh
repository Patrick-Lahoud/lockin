#!/bin/bash
# Lock In: one-time Raspberry Pi setup.
# Run ON THE PI from the repo:  cd ~/lock-in/pi && ./setup_pi.sh
# Does: Python venv, a systemd service that starts the server at boot,
#       Chromium kiosk on the touchscreen at login, no screen blanking.
set -euo pipefail

PI_DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"
LOCK_ANGLE="${LOCKIN_LOCK_ANGLE:-90}"
UNLOCK_ANGLE="${LOCKIN_UNLOCK_ANGLE:-0}"
HAS_LID="${LOCKIN_HAS_LID:-0}"

echo "==> Python venv (with system packages so gpiozero/lgpio from Pi OS are visible)"
sudo apt-get install -y python3-venv python3-gpiozero curl >/dev/null
python3 -m venv --system-site-packages "$PI_DIR/.venv"
"$PI_DIR/.venv/bin/pip" install -q -r "$PI_DIR/requirements.txt"

echo "==> systemd service: lockin.service"
sudo tee /etc/systemd/system/lockin.service >/dev/null <<EOF
[Unit]
Description=Lock In Pi server
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$PI_DIR
Environment=LOCKIN_LOCK_ANGLE=$LOCK_ANGLE
Environment=LOCKIN_UNLOCK_ANGLE=$UNLOCK_ANGLE
Environment=LOCKIN_HAS_LID=$HAS_LID
ExecStart=$PI_DIR/.venv/bin/python $PI_DIR/server.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now lockin.service

echo "==> kiosk launcher"
chmod +x "$PI_DIR/kiosk.sh"
# Raspberry Pi OS Bookworm uses labwc (newer) or wayfire (older); X11 uses LXDE autostart.
mkdir -p ~/.config/labwc
grep -q "kiosk.sh" ~/.config/labwc/autostart 2>/dev/null || echo "$PI_DIR/kiosk.sh &" >> ~/.config/labwc/autostart
if [ -f ~/.config/wayfire.ini ] && ! grep -q "kiosk.sh" ~/.config/wayfire.ini; then
  printf '\n[autostart]\nlockin = %s/kiosk.sh\n' "$PI_DIR" >> ~/.config/wayfire.ini
fi
mkdir -p ~/.config/lxsession/LXDE-pi
grep -q "kiosk.sh" ~/.config/lxsession/LXDE-pi/autostart 2>/dev/null || echo "@$PI_DIR/kiosk.sh" >> ~/.config/lxsession/LXDE-pi/autostart

echo "==> keep the screen on"
sudo raspi-config nonint do_blanking 1 || true

IP="$(hostname -I | awk '{print $1}')"
echo
echo "Done. Server: http://$(hostname).local:8000  (or http://$IP:8000)"
echo "Reboot to see the kiosk:  sudo reboot"
echo "Logs:                     journalctl -u lockin -f"

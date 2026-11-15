#!/bin/bash
# Lock In on the Pi, one command. The laptop runs the brain (server); the Pi shows the screen
# and moves the servo. Nothing to install.
#
#   ./start_pi.sh 192.168.43.20        (the LAPTOP's IP address)
#
set -u
LAPTOP="${1:-}"
if [ -z "$LAPTOP" ]; then
  echo "Usage: ./start_pi.sh <laptop-ip>    e.g. ./start_pi.sh 192.168.43.20"
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
URL="http://$LAPTOP:8000"

echo "→ Checking the laptop at $URL ..."
for i in $(seq 1 15); do
  if curl -s -m 2 "$URL/state" >/dev/null; then echo "  laptop reachable ✓"; break; fi
  [ "$i" = 15 ] && { echo "  ❌ Can't reach $URL. Same Wi-Fi/hotspot? Is the server running on the laptop? Mac firewall allowing Python?"; exit 1; }
  sleep 1
done

# An old Pi-side server would hold the servo pin: stop it.
sudo systemctl stop lockin 2>/dev/null
sudo systemctl disable lockin 2>/dev/null
pkill -f servo_follower.py 2>/dev/null
pkill -f "server.py" 2>/dev/null

echo "→ Starting the servo follower (log: /tmp/servo.log)"
nohup /usr/bin/python3 "$HERE/servo_follower.py" "$LAPTOP" > /tmp/servo.log 2>&1 &
sleep 1
head -3 /tmp/servo.log

echo "→ Opening the box screen"
BROWSER="$(command -v chromium-browser || command -v chromium)"
pkill -f "chromium.*--kiosk" 2>/dev/null
# Works from the Pi's own terminal AND over SSH (Raspberry Pi OS uses Wayland or X11)
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
nohup "$BROWSER" --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --autoplay-policy=no-user-gesture-required --overscroll-history-navigation=0 \
  --disable-pinch --check-for-update-interval=31536000 --disable-features=Translate \
  "$URL/" > /tmp/kiosk.log 2>&1 &

echo
echo "Done. Screen: $URL   Servo log: tail -f /tmp/servo.log"
echo "Exit the full-screen browser: Alt+F4 (keyboard) or: pkill chromium"

#!/bin/bash
# Opens the box screen full-screen on the Pi touchscreen. Started at login by setup_pi.sh.
until curl -s -o /dev/null http://localhost:8000/state; do sleep 1; done
BROWSER="$(command -v chromium-browser || command -v chromium)"
# Clear the "Chromium didn't shut down correctly" bubble after a power cut.
PREFS=~/.config/chromium/Default/Preferences
[ -f "$PREFS" ] && sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --autoplay-policy=no-user-gesture-required --overscroll-history-navigation=0 \
  --disable-pinch --check-for-update-interval=31536000 --disable-features=Translate \
  http://localhost:8000/

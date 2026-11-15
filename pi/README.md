# B: Pi server + box screen

## ⚡ FASTEST SETUP (demo day): the laptop is the brain, the Pi only shows the screen
The Pi doesn't run the server at all. The laptop runs it; the Pi runs a browser + a 60-line servo script.
```bash
# on the LAPTOP (Mac):
cd lock-in/pi && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python server.py
# on the PI (use the laptop's IP; on the Mac: System Settings → Wi-Fi → Details, or `ipconfig getifaddr en0`):
cd ~/lock-in && git pull && cd pi && chmod +x start_pi.sh && ./start_pi.sh <LAPTOP-IP>
```
Everything else (laptop blocker, agent) points at `http://127.0.0.1:8000` on the laptop.
The Android phone's MacroDroid URL becomes `http://<LAPTOP-IP>:8000/inbox`.

---

The server is the boss. It owns the state, runs the timer, moves the servo, and serves three pages:

| URL | Who sees it |
|---|---|
| `/` | the box touchscreen: clock, to-do, music, alarm, start buttons; when locked: countdown, face, messages, digest |
| `/setup` | you, from the laptop: pick sites, apps, number of exits |
| `/blocked` | the laptop, when you try to open a blocked site |

## Run it on your laptop first (fake hardware)
```bash
cd lock-in/pi
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```
Open http://localhost:8000. Tap **1 min**. It locks, counts down, unlocks with a chime.

Try the agent's calls by hand:
```bash
curl -X POST localhost:8000/todo    -H 'content-type: application/json' -d '{"text":"Buy bread","from":"Mom"}'
curl -X POST localhost:8000/message -H 'content-type: application/json' -d '{"from":"Mom","text":"CALL ME NOW","urgent":true}'
curl -X POST localhost:8000/digest  -H 'content-type: application/json' -d '{"text":"Mom wants bread (added to to-do)."}'
curl -X POST localhost:8000/unlock  -H 'content-type: application/json' -d '{"reason":"emergency"}'
curl -X POST localhost:8000/dev/lid -H 'content-type: application/json' -d '{"closed":false}'   # fake an open lid
```

## Put it on the Pi
```bash
# on the Pi (SSH in: ssh <user>@lockin.local)
git clone <repo-url> ~/lock-in
cd ~/lock-in/pi
chmod +x setup_pi.sh kiosk.sh
LOCKIN_LOCK_ANGLE=90 LOCKIN_UNLOCK_ANGLE=0 LOCKIN_HAS_LID=0 ./setup_pi.sh   # angles from A
sudo reboot
```
After reboot the server runs on its own (`journalctl -u lockin -f` for logs) and the touchscreen opens the box UI.

Change a setting later (e.g. the lid switch is built):
```bash
sudo systemctl edit lockin   # add: [Service]  Environment=LOCKIN_HAS_LID=1
sudo systemctl restart lockin
```

## Screen size
The UI scales to any screen; it's designed for **800×480** (official 7" screen). Check yours:
`kmsprint | grep -i connector` or look at the screen's label.

## Music
Put copyright-free MP3s (lo-fi from Pixabay / YouTube Audio Library) in `pi/static/music/`.
They show up automatically. They're not committed to git (too big), so copy them with
`scp *.mp3 <user>@lockin.local:~/lock-in/pi/static/music/`.

### Speaker
* **Best:** a wired speaker in the Pi 4's **3.5 mm headphone jack**. Then right-click the speaker icon on the Pi desktop → choose "Headphones / AV jack".
* **Bluetooth:** click the Bluetooth icon on the Pi desktop → Add device → pick the speaker → then choose it in the speaker icon menu. Or in a terminal:
  ```bash
  bluetoothctl
  power on
  scan on            # wait for your speaker's MAC address, e.g. 12:34:56:78:9A:BC
  pair 12:34:56:78:9A:BC
  trust 12:34:56:78:9A:BC
  connect 12:34:56:78:9A:BC
  exit
  ```
  Heads-up: on the Pi 4, Bluetooth and Wi-Fi share one radio. Test music + locking together before the demo.

## Wi-Fi + fixed name
```bash
sudo raspi-config        # System Options → Hostname → lockin   (then reboot)
sudo nmcli dev wifi connect "HotspotName" password "hotspot-password"   # join the hotspot
hostname -I              # the Pi's IP, if lockin.local doesn't work
```

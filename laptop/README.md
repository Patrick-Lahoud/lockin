# C: Laptop lock (every browser, every app)

No browser extension. When the box locks, the guard writes the blocked sites into the laptop's
**hosts file**, the file the whole operating system checks before connecting anywhere. So
Safari, Chrome, Yandex, Firefox, Edge, Arc and desktop apps all fail to reach Instagram, TikTok and
LinkedIn. Blocked apps (Discord, Steam…) get quit. When the box unlocks, the section is removed.

This builds on your Shutout code (same marked hosts section, same atomic write + DNS flush).
The one big change: Shutout asked for the admin password on every start/stop. Lock In installs a
**background service once**, so locking is instant and there's no password prompt to bypass.

```
box locks ──► Pi state: mode=locked
                 ▲  GET /state every 2 s
   lockin_guard.py system   (root)  → /etc/hosts gets:
                                        # LOCKIN-BEGIN
                                        0.0.0.0 instagram.com
                                        0.0.0.0 www.instagram.com …
                                        # LOCKIN-END
                                      → flush DNS → quit blocked apps
   lockin_guard.py tabs     (you)   → tabs already on instagram.com → http://lockin.local:8000/blocked
```

## 1. Test without installing anything (no sudo, fake hosts file)
With the Pi server running (on the Pi, or on your laptop with `cd ../pi && .venv/bin/python server.py`):
```bash
cd lock-in/laptop
cp /etc/hosts /tmp/fake-hosts
python3 lockin_guard.py system --pi http://localhost:8000 --hosts-file /tmp/fake-hosts --cache /tmp/lockin-cache.json --no-flush
```
Tap **1 min** on the box screen, then `cat /tmp/fake-hosts`. The LOCKIN section shows up, and
it's gone a minute later.

## 2. Install for real (demo laptop, macOS)
```bash
cd lock-in/laptop
chmod +x install_mac.sh uninstall_mac.sh
./install_mac.sh http://lockin.local:8000      # or http://<pi-ip>:8000
```
One password prompt, once. Then lock the box and open instagram.com in Safari, Chrome and Yandex:
all blocked. On the first lock, macOS asks "python3 wants to control <browser>". Click **OK**
(System Settings → Privacy & Security → Automation if you missed it).

Logs: `tail -f /var/log/lockin-guard.log /tmp/lockin-tabs.log`
Remove: `./uninstall_mac.sh`

## Windows
PowerShell as Administrator: `powershell -ExecutionPolicy Bypass -File install_windows.ps1 -PiUrl http://lockin.local:8000`
(hosts block + quitting apps; the open-tab kicker is macOS-only).

## Demo tips
* Open Instagram **after** pressing start. Browsers keep already-open connections alive for a bit; the tab kicker handles open tabs within 2 s.
* Firefox with "DNS over HTTPS" still respects the hosts file by default.
* If a site still loads, check `cat /etc/hosts` and the log. A missing subdomain goes in `EXTRA_HOSTS` in `lockin_guard.py`.
* Don't block `web.telegram.org`: that's how you text the agent "emergency" from the laptop.

## "Can't I just edit the hosts file?"
You'd need the admin password, and the guard rewrites it within 2 s anyway. In the product, a
device-management (MDM) profile that only the box can remove replaces the hosts file.

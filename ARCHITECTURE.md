# Lock In: architecture and build plan

> Lock both. The key is in the box.

Lock In is a desk box. Your phone goes inside, you press start, the latch locks, and for the
same amount of time **your laptop can't open the sites you picked, in any browser**. While you
study, a Telegram agent answers the people who text you, puts their tasks on the box to-do list,
sends you a short digest every 5 minutes if something matters, and lets real emergencies through.

---

## 1. The big picture

```
                         ┌────────────────────────── THE BOX (Raspberry Pi 4) ──────────────────────────┐
                         │                                                                              │
  you tap the            │   Touchscreen (Chromium kiosk)          FastAPI server :8000                 │
  touchscreen  ───────►  │   GET / (box screen)    ◄── polls ───   ┌──────────────────────┐             │
                         │   clock · to-do · music · alarm  1 s    │  state (the ONLY copy)│──► state.json│
                         │   countdown · face · messages           │  timer loop (0.5 s)   │  (survives   │
                         │                         ─── POST /lock ►│                      │   a reboot)  │
                         │                                         └──────────┬───────────┘             │
                         │                                                    │ lock() unlock()         │
                         │                                                    │ lid_closed()            │
                         │                                             hardware.py (gpiozero)           │
                         │                                        SG90 servo GPIO18 · foil lid GPIO23   │
                         │   Bluetooth / 3.5 mm speaker ◄── music                                       │
                         └──────────────────────────────────────▲───────────────────────────────────────┘
                                                                │ Wi-Fi (same network / hotspot)
                                       GET /state every 2 s     │      GET /state + POST /todo /message /digest /unlock /lock
                     ┌──────────────────────────────────────────┴──────────┐
                     │                                                     │
        ┌──────────── LAPTOP ─────────────────────────┐        ┌──────── LAPTOP (any one) ─────────────┐
        │ lockin_guard.py system   (root, launchd)    │        │ agent/bot.py  (Telegram + Gemini)      │
        │  • writes a LOCKIN block in /etc/hosts      │        │  • friends' messages → triage          │
        │    → every browser & app can't reach them   │        │  • auto-reply, to-dos, urgent alerts   │
        │  • quits blocked apps (Discord, Steam…)     │        │  • digest every 5 min + final digest   │
        │ lockin_guard.py tabs     (you, launchd)     │        │  • study Q&A with a rate limit         │
        │  • kicks already-open tabs in Safari,       │        │  • "emergency …" → POST /unlock        │
        │    Chrome, Yandex, Edge, Brave, Arc         │        └───────────────▲────────────────────────┘
        └─────────────────────────────────────────────┘                        │ Telegram Bot API
                                                                Mom texts you / you text the bot
```

**One rule makes the team fast: the Pi is the boss.** Only the Pi knows whether a session is
running. The laptop guard and the agent just ask `GET /state` and react. That's why four people
can build four parts at the same time: everyone codes against `CONTRACT.md`, and the server
runs on any laptop with fake hardware.

---

## 2. Decisions and why

| Decision | Why |
|---|---|
| **Wi-Fi + HTTP**, not Bluetooth | The Pi runs a web server; everything else is a `fetch`. Bluetooth pairing eats hours and gives nothing for the demo. |
| **Laptop blocking = hosts file + system service**, not a browser extension | An extension only works in one browser. The hosts file is checked by the whole OS, so Safari, Chrome, Yandex, Firefox and desktop apps all lose those sites. It's your Shutout code with one change: instead of asking for the admin password every session, it's installed **once** as a root service that follows the box. **No password to bypass during a session.** |
| **Telegram bot** (not WhatsApp) | No phone number to buy, official API, 10 minutes to set up, and you've built bots before. |
| **Gemini** for the brain | You already have the key. One call per message returns JSON (`urgent`, `important`, `task`). If Gemini fails, simple keyword rules take over, so the demo never stalls. |
| **Digest every 5 min, only if something matters** | Urgent messages go through instantly; tasks and questions wait for the digest; memes only show up in the end-of-session summary. Demo: set `DIGEST_SECONDS=30`. |
| **No separate website** | The Pi serves the box screen, `/setup` and the laptop's "Locked In" page. |
| **No lid sensor yet → foil switch** | Two foil pads + one foil strip on the lid = a switch. Until it's built, `LOCKIN_HAS_LID=0` and the lid always counts as closed. |
| **No separate power → SG90 only** | One SG90 runs off the Pi's 5 V pin if you use the official 3 A Pi supply. The code turns the servo signal off after every move, so it doesn't buzz or brown-out the Pi. |

### How "messages from Mom" reach the agent

A Telegram **bot** only sees messages sent **to the bot**. There are two ways to use it:

1. **Demo mode (works today, free):** the "Mom" teammate opens your bot and texts it.
   The bot treats anyone who isn't you as "someone texting you". It auto-replies as your assistant.
2. **Real mode (Telegram Business, needs Telegram Premium on your account):** Settings →
   Telegram Business → Chatbots → add your bot. Now the bot sees your *real* private chats and
   replies *as you*. The code already supports this (`business_message` updates). Say it in the
   pitch: "In the product it's connected to your real account through Telegram Business."

---

## 3. What each demo feature uses

| # | Feature | Flow |
|---|---|---|
| 1 | **Box lock** | Tap `1 min` → `POST /lock` → Pi checks lid → `hardware.lock()` (servo swings over the lid tab) → screen shows countdown + face → timer loop hits `ends_at` → `hardware.unlock()` → chime. |
| 2 | **Laptop lock** | Guard sees `mode: locked` within 2 s → writes `0.0.0.0 instagram.com …` between `# LOCKIN-BEGIN/END` → flushes DNS → quits blocked apps → tab guard sends open Instagram tabs to `http://lockin.local:8000/blocked` (countdown page). Unlock → section removed. |
| 3 | **Desk screen** | Idle: big clock, to-do list (tap to tick), music player (MP3s from `pi/static/music`), alarm. Locked: countdown, animated face, exits left, messages, digest. |
| 4 | **Agent + emergency exit** | "Mom" texts "buy bread" → Gemini: not urgent, task = "Buy bread" → auto-reply + `POST /todo` → appears on the box. "URGENT call me" → `POST /message urgent` → box turns red with **Unlock free** → `POST /unlock {"reason":"urgent"}`. You text the bot `emergency sick dog` → `POST /unlock {"reason":"emergency"}` → "Unlocked. 4 exits left." |
| + | **Study buddy** | During a session you text the bot "what's the derivative of x²?" → answer. "Who won the game?" → refused. 20 questions per session. |
| + | **Digest** | Every 5 min (if anything important came in): "Mom wants bread (added to to-do). Prof moved the meeting to 4pm." On the box and in Telegram. Session end: full summary. |

---

## 4. Repo layout (one folder per person)

```
lock-in/
  CONTRACT.md          the only shared file
  CLAUDE.md            "read CONTRACT.md, only edit your folder"
  ARCHITECTURE.md      this file
  hardware/            A  hardware.py: lock(), unlock(), lid_closed()
  pi/                  B  server.py + static/index.html (box) + setup.html + blocked.html
  laptop/              C  lockin_guard.py + install_mac.sh / uninstall_mac.sh / install_windows.ps1
  agent/               D  bot.py (Telegram) + brain.py (Gemini) + pi_client.py
```

---

## 5. Step-by-step build plan

### Step 0: first 15 minutes (everyone)
1. One person: create GitHub repo `lock-in`, push this folder, add everyone.
2. **Network test.** Pi and laptop on the same Wi-Fi. On the Pi: `hostname -I`. On the laptop:
   open `http://<pi-ip>:8000/state` (after B starts the server, or just `python3 -m http.server 8000` on the Pi).
   Doesn't load? Hackathon Wi-Fi blocks devices from seeing each other → **use a teammate's hotspot**.
3. Rename the Pi so the address never changes: `sudo raspi-config` → System → Hostname → `lockin`
   → reboot → now it's `http://lockin.local:8000`.
4. Everyone clones, opens Claude Code **in their own folder**.

### Step 1: everyone builds against fake data (11:30–1:30)
Everyone can run the real server on their own laptop with fake hardware:
```bash
cd pi && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python server.py
```
Now `http://localhost:8000` is the box screen and `PI_URL=http://localhost:8000` works for everything.

* **A: hardware** → see `hardware/README.md`. Wire servo, glue the tab, build the foil lid switch,
  run `python3 hardware.py` on the Pi until lock/unlock/lid all work alone.
* **B: Pi server + screen** → see `pi/README.md`. It's already built: tune the UI on the real
  touchscreen (check resolution), add MP3s, set up kiosk mode with `pi/setup_pi.sh`, pair the speaker.
* **C: laptop blocker** → see `laptop/README.md`. Test with a fake hosts file first, then install
  for real on the demo laptop. Test Safari, Chrome and Yandex. Allow the Automation prompts.
* **D: agent** → see `agent/README.md`. BotFather token + Gemini key in `.env`, run it, test with a
  teammate texting the bot.

**12:30 checkpoint:** everyone shows one working thing.

### Step 2: 1:00 decision point
* Servo latch working? If not, keep the fallback: screen says LOCKED, someone holds the lid.
* Agent replying? If Gemini is flaky, the keyword fallback still works. Keep going.

### Step 3: connect everything (1:30–2:30)
1. Server on the Pi (`sudo systemctl status lockin`), kiosk on the touchscreen.
2. Laptop guard installed with `./install_mac.sh http://lockin.local:8000`.
3. Agent running on a laptop with `PI_URL=http://lockin.local:8000`.
4. Run the full demo script **3 times** end to end.

### Step 4: polish (2:30–3:30). No new features after 2:30.
Face, sounds, copy. Record a backup demo video. Stretch: webcam nudge → `POST /nudge`.

### Step 5: submit (3:30–4:30)
Devpost page, 5 slides, practice the pitch twice with a timer, submit by 4:30.

---

## 6. Wiring (Pi 4 Model B)

| Part | Wire | Pi pin |
|---|---|---|
| SG90 servo | brown (GND) | pin 6 (GND) |
| | red (5 V) | pin 2 (5 V) |
| | orange (signal) | pin 12 (GPIO 18) |
| Foil lid switch | pad A | pin 16 (GPIO 23) |
| | pad B | pin 14 (GND) |
| Speaker | 3.5 mm jack (most reliable) or Bluetooth | none |

---

## 7. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Wi-Fi isolates devices | Teammate's phone hotspot (not the phone going in the box). |
| `lockin.local` doesn't resolve | Use the IP: `./install_mac.sh http://192.168.x.x:8000`, `PI_URL=…` in agent `.env`. |
| Servo fails on stage | Screen still shows LOCKED, laptop still blocks. Keep going. |
| Instagram already open in a tab | Tab guard redirects it within 2 s (allow the Automation prompt once, in prep). |
| Browser cached the old connection | Guard quits blocked apps and kicks tabs; for the demo, open Instagram **after** locking. |
| Gemini error / no key | Keyword rules take over automatically. |
| Pi reboots mid-session | `state.json` is reloaded and the servo re-locks. The key is still in the box. |
| Live demo breaks | Play the backup video. Never debug on stage. |
| Judge: "can't I just delete the hosts line?" | "You'd need the admin password, and the guard rewrites it within 2 s. The product version uses an MDM profile that only the box can remove." |

---

## 8. Security notes (honest version for judges)
* The guard validates every domain and app name before writing to `/etc/hosts`, so the Pi can't inject junk.
* If the laptop can't reach the Pi mid-session, the guard **keeps blocking until `ends_at`** (fail closed), then opens.
* Hackathon build has no auth between laptop and Pi. Roadmap: a pairing key shown on the box screen.

# Your steps (Dimitri)

Tick these off in order. Everything else is already built. Details for each part are in that folder's README.

---

## Right now (15 min)

- [ ] **1. Get push access.** Ask Patrick: GitHub → `Patrick-Lahoud/lockin` → Settings → Collaborators → add **dbronnikov07**.
  (The repo is **public**, so the key must never go in it. The pre-commit hook blocks that.)
- [ ] **2. Create the Telegram bot.** Telegram → **@BotFather** → `/newbot` → name `Lock In` → username ending in `bot`.
  Copy the token it gives you.
- [ ] **3. Put the token in `agent/.env`.** Open the file and paste it after `TELEGRAM_BOT_TOKEN=`.
  **Never paste it in chat.** The Gemini key is already there and tested (`gemini-3.5-flash`, ~1 s replies).
- [ ] **4. Run the agent:**
  ```bash
  cd lock-in/agent
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  .venv/bin/python bot.py
  ```
- [ ] **5. Claim the bot.** In Telegram Desktop on the laptop, open your bot and send `/start`. You're the owner.
- [ ] **6. Team network test.** Pi + laptop on the same Wi-Fi → open `http://<pi-ip>:8000/state` from the laptop.
  Doesn't load → everyone switches to a phone hotspot.

## Send to the team (5 min)

- [ ] Share the repo. Everyone runs `./scripts/install_hooks.sh` once after cloning (blocks secret leaks).
- [ ] Assign parts. Each person reads their folder's README and opens Claude Code **in their own folder**:

| Who | Folder | First goal |
|---|---|---|
| A | `hardware/` | servo locks/unlocks from `python3 hardware.py` |
| B | `pi/` | `./setup_pi.sh` on the Pi → touchscreen shows the box UI |
| C | `laptop/` | blocker tested with the fake hosts file, then `./install_mac.sh` on the demo laptop |
| D (you) | `agent/` | bot replies to "buy bread", "URGENT", "emergency" |

## By 12:30 checkpoint

- [ ] Agent works against a local server (`PI_URL=http://localhost:8000` in `.env` + `cd pi && .venv/bin/python server.py`).
- [ ] A teammate texts the bot `buy bread on the way home` → auto-reply + to-do on the box screen.
- [ ] A teammate texts `URGENT call me` → box turns red with **Unlock free**.
- [ ] You text `emergency test` → box unlocks, "4 exits left".

## 1:00 decision point

- [ ] Servo working? If not → fallback: screen says LOCKED, hold the lid on stage.
- [ ] Bot working? It is if step 5 passed. (Gemini down → keyword rules take over automatically.)

## 1:30–2:30 connect everything

- [ ] In `agent/.env`: `PI_URL=http://lockin.local:8000` (or the Pi's IP), `DIGEST_SECONDS=30` for the demo.
- [ ] Laptop guard installed on the **demo laptop**: `cd laptop && ./install_mac.sh http://lockin.local:8000`.
  On the first lock, click **OK** on "python3 wants to control Safari/Chrome/Yandex".
- [ ] Put 3–4 lo-fi MP3s in `pi/static/music/` on the Pi. Speaker connected (3.5 mm jack is most reliable).
- [ ] **Run the full demo 3 times** (script in `ARCHITECTURE.md`). Open Instagram **after** pressing start.
- [ ] Before each run: `/setup` → **Refill exits (demo)**.

## 2:30–3:30 polish (no new features)

- [ ] Record a backup video of the whole flow.
- [ ] Set `OWNER_ID` in `.env` (your Telegram ID is in the agent log after `/start`) so nobody else can claim the bot.

## 3:30–4:30 submit

- [ ] Devpost: team, repo link, video, "built with Copilot" screenshot. **Check nothing on Devpost shows a key.**
- [ ] 5 slides, practice the pitch twice with a timer.
- [ ] **4:30: Submit.** Every teammate joins the Devpost project.

## After the hackathon (don't skip)

- [ ] **Rotate the Gemini key** (aistudio.google.com/apikey → delete + create new). It was pasted in a chat.
- [ ] **Rotate the bot token** (@BotFather → `/revoke`).
- [ ] Restrict the new key to "Generative Language API" + a budget alert in Google Cloud.
- [ ] Patrick: repo Settings → Code security → enable secret scanning + push protection.
- [ ] Remaining items in `SECURITY.md` → "Fix before launch".

---

## Design sprint (after the MVP works)

Only start once the demo runs end to end 3 times. Ideas to work through, highest impact first:

1. **Box face**: more expressions (sleepy when idle at night, celebrating at the end), smoother transitions, maybe eyes that follow taps.
2. **Box screen**: real typography pass at the exact screen resolution, a nicer locked layout, progress ring instead of a bar.
3. **"Locked In" page on the laptop**: this is what judges see when Instagram is blocked, so make it beautiful.
4. **Setup / onboarding**: a 3-step first-run flow (pick sites → connect laptop → connect Telegram).
5. **Physical box**: clean acrylic cuts, a logo, a slot or LED that shows locked/unlocked.
6. **Telegram replies**: friendlier auto-reply copy, maybe a weekly "focus report".
7. **Slides + Devpost visuals**: architecture diagram, before/after screenshots.

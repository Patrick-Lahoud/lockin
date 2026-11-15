# Lock In (ONHacks 2026)

**Lock both. The key is in the box.** A desk box that locks your phone *and* your laptop with
one timer, while a Telegram agent answers your messages.

* `SIMPLE_PLAN.md`: **start here.** The whole plan in super simple words (no hardware experience needed)
* `STEPS.md`: the step-by-step checklist for today
* `ARCHITECTURE.md`: the full blueprint (diagram, decisions, build plan, wiring, fallbacks)
* `CONTRACT.md`: the API everyone builds against
* `SECURITY.md`: security review + what's fixed / still open
* `agent/ANDROID_SETUP.md`: the Android phone in the box forwards Instagram, Snapchat, WhatsApp, Telegram… notifications (15 min setup)
* One folder per person: `hardware/` (A), `pi/` (B), `laptop/` (C), `agent/` (D). Each has its own README.

**After cloning, everyone runs `./scripts/install_hooks.sh` once.** It blocks commits that contain API keys.
Secrets live only in `agent/.env` (git-ignored). Never paste keys into code, chat, or Devpost.

## Run the whole thing on one laptop in 3 terminals (no hardware needed)
```bash
# 1. the "box" (fake servo + lid)
cd pi && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python server.py
#    → open http://localhost:8000 (box screen) and http://localhost:8000/setup

# 2. the laptop blocker, against a fake hosts file (no sudo)
cd laptop && cp /etc/hosts /tmp/fake-hosts && python3 lockin_guard.py system --pi http://localhost:8000 --hosts-file /tmp/fake-hosts --cache /tmp/lockin-cache.json --no-flush

# 3. the agent (needs a bot token + Gemini key in agent/.env)
cd agent && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && cp .env.example .env && .venv/bin/python bot.py
```
Tap **1 min** on the box screen and watch all three react.

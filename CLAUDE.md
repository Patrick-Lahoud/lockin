# Rules for Claude Code in this repo

1. Read `CONTRACT.md` first. It is the only interface between the parts.
2. Only edit files inside your own folder:
   * `hardware/`: A (servo + lid)
   * `pi/`: B (server + box screen + setup page)
   * `laptop/`: C (device-wide blocker for the laptop)
   * `agent/`: D (Telegram + Gemini agent)
3. Never change `CONTRACT.md` without the whole team agreeing out loud.
4. Small steps: build one piece, run it, then the next.
5. Never commit secrets (`.env`, `.owner.json`).

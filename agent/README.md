# D: Telegram agent (Dmitrii)

**You don't need to buy a phone number.** A Telegram bot is free and is created inside Telegram in 2 minutes.

## 1. Create the bot (2 min)
1. In Telegram, search **@BotFather** (blue check mark) → **Start**.
2. Send `/newbot`.
3. Name: `Lock In` → username: something ending in `bot`, e.g. `lockin_onhacks_bot`.
4. BotFather replies with a **token** like `7412345678:AAH...`. That's the bot's password. Don't share it or commit it.
5. Optional: `/setuserpic` (logo), `/setdescription` ("I answer your messages while you're locked in").

## 2. Get the Gemini key
https://aistudio.google.com/apikey → Create API key. (You have one already.)

## 3. Configure and run
```bash
cd lock-in/agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then open .env and paste the token + Gemini key
.venv/bin/python bot.py
```
Before the Pi is ready, point it at a local server: run `cd ../pi && .venv/bin/python server.py`
in another terminal and set `PI_URL=http://localhost:8000` in `.env`.

## 4. Claim the bot
Open your bot in Telegram (Telegram Desktop or web.telegram.org on the laptop, since your phone is in the box)
and send `/start`. You're now the owner (saved in `.owner.json`). Everyone else is "someone texting you".

## 5. Test the whole feature
| Who | Sends | What happens |
|---|---|---|
| teammate ("Mom") | `buy bread on the way home` | auto-reply "Dimitri is locked in until 15:00…", **Buy bread** shows on the box to-do |
| teammate | `URGENT call me` | box turns red with **Unlock free**, you get 🚨 in Telegram |
| you | `what's the derivative of x^2?` | answer |
| you | `who won the leafs game` | refused, "N min left" |
| you | `emergency my dog is sick` | box unlocks, "Unlocked. 4 exits left." |
| you | `start 1` | box locks for 1 min |
| nobody | (wait `DIGEST_SECONDS`) | 🗞 digest in Telegram + on the box |
| nobody | (timer ends) | ✅ full summary in Telegram + popup on the box |

For the demo set `DIGEST_SECONDS=30` so judges see a digest.

## Real mode: Telegram Business (optional)
Needs **Telegram Premium** on your account. The bot then sees your *real* private chats and replies as you.
1. @BotFather → `/mybots` → your bot → Bot Settings → **Business Mode** → Turn on.
2. In your Telegram: Settings → **Telegram Business** → **Chatbots** → enter your bot's username → allow "reply to messages".
3. Now if Mom texts *you*, the agent handles it. When you're not locked in, it stays silent.

## How it decides (`brain.py`)
One Gemini call per message returns JSON: `{urgent, important, task, summary}`.
* `urgent` → `POST /message urgent:true` right away
* `task` → `POST /todo`
* `important` → goes in the next 5-minute digest (`POST /digest`)
* everything → in the end-of-session summary

If Gemini fails or there's no key, keyword rules take over ("urgent", "hospital", "call me now" → urgent;
"buy …", "call …", "send …" → task). The study buddy falls back to a calculator.
If `gemini-3.8-flash` isn't available on your key, it automatically tries `gemini-3.5-flash`, then `gemini-2.5-flash`.

## Where it runs
On a laptop (not the Pi). Keep the terminal open during the demo. If it crashes, rerun `bot.py`: the
owner is remembered, and the session state is re-read from the Pi.

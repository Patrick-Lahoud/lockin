# Lock In: the contract

**The Pi is the boss.** It holds the only copy of the session state. Everything else
(the laptop guard, the Telegram agent, the box screen) either **reads** `GET /state` or
**asks** the Pi to change something. Nobody else keeps its own copy of "am I locked?".

Before changing anything in this file, tell the whole team out loud.

Pi server: Python FastAPI on port **8000** → `http://lockin.local:8000` (or `http://<pi-ip>:8000`).

## Endpoints

| Method | Path | Body | Who calls it | What it does |
|---|---|---|---|---|
| GET | `/state` | none | laptop guard (every 2 s), box screen (every 1 s), agent (every 2 s) | Returns the state JSON below |
| POST | `/lock` | `{"minutes": 25}` | box screen start button, agent (`start 25`) | Checks the lid is closed, locks the latch, starts the timer. `409` if already locked or lid open |
| POST | `/unlock` | `{"reason": "timer" \| "emergency" \| "urgent"}` | Pi itself (timer), agent, box screen | Opens the latch, mode → idle. `emergency` uses 1 exit (`403` if none left). `urgent` is free but only works while an urgent message is pending (`403` otherwise) |
| POST | `/todo` | `{"text": "Buy bread", "from": "Mom"}` | agent, box screen | Adds a to-do |
| POST | `/todo/{id}/toggle` | none | box screen | Ticks / unticks a to-do |
| DELETE | `/todo/{id}` | none | box screen | Removes a to-do |
| POST | `/message` | `{"from": "Mom", "text": "Call me now", "urgent": true}` | agent | Shows the message on the box. `urgent: true` offers the free unlock |
| POST | `/digest` | `{"text": "Mom wants bread…", "final": false}` | agent | Shows the 5-minute digest (`final: true` = end-of-session summary) |
| POST | `/settings` | `{"blocked_sites": [...], "blocked_apps": [...], "max_exits": 5}` | setup page | Saves what to block. `409` while locked (you can't unblock Instagram mid-session) |
| POST | `/inbox` | plain text `app\ntitle\ntext` (or JSON / form with `app`, `title`, `text`, optional `package`) | **the Android phone in the box** (MacroDroid) | Stores one phone notification for the agent. While locked, counts it in `held` |
| GET | `/inbox?after=<id>` | none | agent (every 2 s) | `{"items": [{"id", "at", "app", "package", "title", "text"}], "last_id": 42}` |
| POST | `/nudge` | none | webcam script (stretch) | Makes the box face sad for 30 s |
| POST | `/reset` | none | setup page | Demo helper: exits back to max, clears messages and digests |
| GET | `/`, `/setup`, `/blocked` | none | browsers | Box screen, setup page, "Locked In" page shown on the laptop |

All POSTs reply with the full new state (same shape as `GET /state`), or `{"detail": "why"}` on error.

## The state JSON

```json
{
  "mode": "locked",
  "started_at": 1763223300,
  "ends_at": 1763224800,
  "minutes": 25,
  "session_id": 7,
  "server_time": 1763223912,
  "exits_left": 5,
  "max_exits": 5,
  "lid_closed": true,
  "blocked_sites": ["instagram.com", "tiktok.com", "linkedin.com"],
  "blocked_apps": ["Discord"],
  "todos": [{"id": "a1b2c3", "text": "Buy bread", "from": "Mom", "done": false}],
  "last_message": {"from": "Mom", "text": "Call me now", "urgent": true, "at": 1763223800},
  "urgent_pending": true,
  "last_digest": {"text": "Mom wants bread (added to to-do).", "final": false, "at": 1763223900},
  "last_unlock": {"reason": "timer", "at": 1763222000},
  "held": {"Instagram": 4, "WhatsApp": 2},
  "face": "focused"
}
```

* `mode`: `"idle"` or `"locked"`.
* `ends_at`, `started_at`, `server_time`, every `at`: Unix timestamps in **seconds**.
* `session_id`: goes up by 1 on every lock. The agent uses it to know a new session started.
* `held`: phone notifications caught this session, per app (reset on every lock).
* `face`: `"happy"`, `"focused"`, `"worried"` (urgent message), `"sad"` (nudge), `"proud"` (just finished).

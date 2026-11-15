"""Lock In: Telegram agent (feature 4 + study buddy + digests).

Who talks to the bot
  * YOU (the owner): study questions, "emergency <reason>", "start 25", /status
  * Everyone else ("Mom"): their messages get triaged by Gemini while you're locked in:
      urgent     → shown on the box right away, free unlock offered
      important  → auto-reply once, task goes on the box to-do list, included in the 5-min digest
      noise      → only in the end-of-session summary
  * Telegram Business (optional, needs Premium): the same logic runs on your REAL private chats.

Run:  python bot.py   (settings in .env, see .env.example)
"""
import json
import logging
import os
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import AIORateLimiter, Application, CommandHandler, ContextTypes, MessageHandler, filters

from brain import Brain
from limits import GeminiBudget, SlidingWindow, install_redaction
from pi_client import Pi

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PI_URL = os.getenv("PI_URL", "http://lockin.local:8000")
OWNER_NAME = os.getenv("OWNER_NAME", "Your friend")
DIGEST_SECONDS = int(os.getenv("DIGEST_SECONDS", "300"))
QUESTIONS_PER_SESSION = int(os.getenv("QUESTIONS_PER_SESSION", "20"))
QUESTIONS_PER_HOUR_IDLE = int(os.getenv("QUESTIONS_PER_HOUR_IDLE", "30"))
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OWNER_CLAIM_CODE = os.getenv("OWNER_CLAIM_CODE", "").strip()
OWNER_FILE = HERE / ".owner.json"

# Per-person limits (protect the Gemini key from strangers spamming the bot)
SENDER_PER_MINUTE = SlidingWindow(int(os.getenv("SENDER_PER_MINUTE", "5")), 60)
SENDER_PER_SESSION = int(os.getenv("SENDER_PER_SESSION", "40"))
OWNER_PER_MINUTE = SlidingWindow(int(os.getenv("OWNER_PER_MINUTE", "6")), 60)
FORWARDS_PER_HOUR = SlidingWindow(20, 3600)
MAX_MESSAGE_CHARS = 1000

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx INFO logs include the bot token in URLs
install_redaction(TOKEN, GEMINI_KEY)  # belt and braces: secrets can never reach a log line
log = logging.getLogger("agent")

pi = Pi(PI_URL)
budget = GeminiBudget(
    per_minute=int(os.getenv("GEMINI_MAX_PER_MINUTE", "12")),
    per_day=int(os.getenv("GEMINI_MAX_PER_DAY", "400")),
    usage_file=HERE / ".usage.json",
)
brain = Brain(
    GEMINI_KEY or None,
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"],
    budget,
)


# ---------------------------------------------------------------- owner
def owner_id() -> int | None:
    if os.getenv("OWNER_ID", "").strip():
        return int(os.getenv("OWNER_ID"))
    try:
        return int(json.loads(OWNER_FILE.read_text())["owner_id"])
    except Exception:
        return None


def set_owner(uid: int) -> None:
    OWNER_FILE.write_text(json.dumps({"owner_id": uid}))


def is_owner(update: Update) -> bool:
    u = update.effective_user
    return bool(u and owner_id() == u.id)


# ---------------------------------------------------------------- session memory
class Session:
    def __init__(self):
        self.reset(None)

    def reset(self, sid):
        self.sid = sid                 # Pi session_id we're tracking (None = not in a session)
        self.inbox: list[dict] = []    # every message received during the session
        self.replied: set[str] = set() # senders who already got the auto-reply
        self.questions = 0             # owner's study questions this session
        self.next_digest = time.time() + DIGEST_SECONDS


S = Session()
idle_questions: deque[float] = deque()
pi_down_logged = 0.0


def until_text(st: dict) -> str:
    return datetime.fromtimestamp(st["ends_at"]).strftime("%H:%M") if st.get("ends_at") else "later"


def minutes_left(st: dict) -> int:
    return max(0, round(((st.get("ends_at") or 0) - st.get("server_time", time.time())) / 60))


async def tell_owner(ctx: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    oid = owner_id()
    if oid:
        try:
            await ctx.bot.send_message(oid, text)
        except Exception as e:
            log.warning("couldn't message owner: %s", e)


# ---------------------------------------------------------------- commands
HELP = (
    "Lock In agent\n\n"
    "During a session I answer study questions only ({q} per session).\n\n"
    "Commands:\n"
    "start 25: lock the box for 25 min\n"
    "emergency <reason>: leave early (uses 1 exit)\n"
    "/free: free unlock when there's an urgent message\n"
    "/status: what's going on\n\n"
    "Anyone else who messages me gets triaged while you're locked in."
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if owner_id() is None and update.effective_chat.type == "private":
        if OWNER_CLAIM_CODE and (ctx.args or [""])[0] != OWNER_CLAIM_CODE:
            await update.message.reply_text("This bot isn't set up yet.")
            return
        set_owner(user.id)
        log.info("owner set to %s (%s)", user.id, user.full_name)
        await update.message.reply_text(f"You're the owner now, {user.first_name}. 🔒\n\n" + HELP.format(q=QUESTIONS_PER_SESSION))
        return
    if is_owner(update):
        await update.message.reply_text(HELP.format(q=QUESTIONS_PER_SESSION))
    else:
        await update.message.reply_text(f"Hi! I'm {OWNER_NAME}'s Lock In assistant. Send me a message and I'll make sure they get it.")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if is_owner(update):
        await update.message.reply_text(HELP.format(q=QUESTIONS_PER_SESSION))


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        return
    st = await pi.state()
    if not st:
        await update.message.reply_text(f"❌ Can't reach the box at {PI_URL}")
        return
    if st["mode"] == "locked":
        text = (
            f"🔒 Locked in until {until_text(st)} ({minutes_left(st)} min left)\n"
            f"Exits left: {st['exits_left']}/{st['max_exits']}\n"
            f"Messages this session: {len(S.inbox)}\n"
            f"Study questions left: {max(0, QUESTIONS_PER_SESSION - S.questions)}"
        )
    else:
        open_todos = [t["text"] for t in st.get("todos", []) if not t["done"]]
        text = f"🟢 Box idle. Exits: {st['exits_left']}/{st['max_exits']}\nTo-do: " + (", ".join(open_todos) or "nothing")
    await update.message.reply_text(text)


async def cmd_lock(update: Update, ctx: ContextTypes.DEFAULT_TYPE, minutes: float | None = None) -> None:
    if not is_owner(update):
        return
    if minutes is None:
        try:
            minutes = float(ctx.args[0]) if ctx.args else 25
        except ValueError:
            minutes = 25
    ok, data = await pi.lock(minutes)
    if ok:
        await update.message.reply_text(f"🔒 Locked in until {until_text(data)}. Phone in the box, go.")
    else:
        await update.message.reply_text(f"Couldn't lock: {data.get('detail')}")


async def cmd_emergency(update: Update, ctx: ContextTypes.DEFAULT_TYPE, reason: str = "") -> None:
    if not is_owner(update):
        return
    st = await pi.state()
    if not st:
        await update.message.reply_text(f"❌ Can't reach the box at {PI_URL}")
        return
    if st["mode"] != "locked":
        await update.message.reply_text("You're not locked in right now. Nothing to unlock.")
        return
    ok, data = await pi.unlock("emergency")
    if ok:
        log.info("emergency exit: %s", reason or "(no reason)")
        await update.message.reply_text(f"🔓 Unlocked. {data['exits_left']} exit{'s' if data['exits_left'] != 1 else ''} left. Take care of it.")
    else:
        await update.message.reply_text(f"🔒 {data.get('detail')}. {minutes_left(st)} min to go. You've got this.")


async def cmd_emergency_slash(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_emergency(update, ctx, " ".join(ctx.args or []))


async def cmd_free(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        return
    ok, data = await pi.unlock("urgent")
    await update.message.reply_text("🔓 Unlocked for free because of the urgent message." if ok else f"🔒 {data.get('detail')}")


# ---------------------------------------------------------------- owner chat
EMERGENCY_RE = re.compile(r"^\s*emergency\b[:\s-]*(.*)$", re.I | re.S)
START_RE = re.compile(r"^\s*(?:start|lock)(?:\s+in)?\s+(\d+(?:\.\d+)?)\s*(?:m|min|mins|minutes)?\s*$", re.I)


async def owner_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()[:MAX_MESSAGE_CHARS]
    if m := EMERGENCY_RE.match(text):
        return await cmd_emergency(update, ctx, m.group(1).strip())
    if m := START_RE.match(text):
        return await cmd_lock(update, ctx, float(m.group(1)))
    if text.lower() in ("free", "unlock urgent"):
        return await cmd_free(update, ctx)

    if not OWNER_PER_MINUTE.allow("owner"):
        await update.message.reply_text("Slow down a little: max a few questions per minute. Try again in a moment.")
        return
    st = await pi.state()
    locked = bool(st and st["mode"] == "locked")
    if locked:
        if st.get("session_id") != S.sid:
            S.reset(st.get("session_id"))
        if S.questions >= QUESTIONS_PER_SESSION:
            await update.message.reply_text(f"You've used all {QUESTIONS_PER_SESSION} questions this session. {minutes_left(st)} min left. Back to it 💪")
            return
        S.questions += 1
    else:
        now = time.time()
        while idle_questions and now - idle_questions[0] > 3600:
            idle_questions.popleft()
        if len(idle_questions) >= QUESTIONS_PER_HOUR_IDLE:
            await update.message.reply_text("That's a lot of questions this hour. Give me a minute 🙂")
            return
        idle_questions.append(now)

    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    ans = await brain.study(text, locked, minutes_left(st) if st else 0, OWNER_NAME)
    reply = ans["answer"]
    left = QUESTIONS_PER_SESSION - S.questions
    if locked and left <= 5:
        reply += f"\n\n({left} question{'s' if left != 1 else ''} left this session)"
    await update.message.reply_text(reply)


# ---------------------------------------------------------------- incoming from others
async def incoming(update: Update, ctx: ContextTypes.DEFAULT_TYPE, business: bool) -> None:
    msg = update.business_message if business else update.message
    if not msg or not msg.text:
        return
    sender = (msg.from_user.first_name if msg.from_user else "Someone")[:40]
    sender_key = str(msg.from_user.id) if msg.from_user else sender
    text = msg.text.strip()[:MAX_MESSAGE_CHARS]

    # Rate limits: a spammer can't burn the Gemini key or flood the box.
    if not SENDER_PER_MINUTE.allow(sender_key):
        log.info("rate-limited %s (per minute)", sender)
        return

    st = await pi.state()
    if not st:
        log.warning("Pi unreachable; can't triage message from %s", sender)
        return
    if st["mode"] != "locked":
        if not business and FORWARDS_PER_HOUR.allow():  # demo mode: pass it straight on
            await msg.reply_text(f"{OWNER_NAME} isn't locked in right now. I've passed it on 👍")
            await tell_owner(ctx, f"💬 {sender}: {text}")
        return  # business mode + idle: stay out of your real chats

    if st.get("session_id") != S.sid:
        S.reset(st.get("session_id"))
    if sum(1 for i in S.inbox if i.get("key") == sender_key) >= SENDER_PER_SESSION:
        log.info("rate-limited %s (per session)", sender)
        return

    said_urgent = sender in S.replied and re.search(r"\burgent\b", text, re.I)
    t = await brain.triage(sender, text, OWNER_NAME)
    urgent = t["urgent"] or bool(said_urgent)
    item = {"key": sender_key, "from": sender, "text": text, "summary": t["summary"], "task": t["task"], "important": t["important"] or urgent, "urgent": urgent, "digested": urgent}
    S.inbox.append(item)
    log.info("%s → %s", sender, {k: item[k] for k in ("urgent", "important", "task")})

    if urgent:
        await pi.message(sender, text, True)
        await msg.reply_text(f"🚨 Got it. I put this on {OWNER_NAME}'s desk box right now.")
        await tell_owner(ctx, f"🚨 URGENT from {sender}: {text}\n\nTap 'Unlock free' on the box, or send /free")
        return

    if t["task"]:
        await pi.todo(t["task"], sender)
    if t["important"]:
        await pi.message(sender, t["summary"], False)

    if sender not in S.replied:
        S.replied.add(sender)
        reply = f"🔒 {OWNER_NAME} is locked in until {until_text(st)}. I'll pass this on then."
        if t["task"]:
            reply += f" Added “{t['task']}” to their to-do."
        reply += " Reply URGENT if it can't wait."
        await msg.reply_text(reply)
    elif t["task"]:
        await msg.reply_text(f"Added “{t['task']}” to their to-do ✅")


async def on_private(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if is_owner(update):
        await owner_text(update, ctx)
    elif owner_id() is None:
        await update.message.reply_text("Not set up yet. The owner needs to send /start first.")
    else:
        await incoming(update, ctx, business=False)


async def on_business(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    m = update.business_message
    if m and m.from_user and m.from_user.id == owner_id():
        return  # that's you typing in your own chats
    await incoming(update, ctx, business=True)


# ---------------------------------------------------------------- watcher: digests + session end
async def watch(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global pi_down_logged
    st = await pi.state()
    if not st:
        if time.time() - pi_down_logged > 60:
            pi_down_logged = time.time()
            log.warning("can't reach the Pi at %s", PI_URL)
        return
    now = time.time()

    if st["mode"] == "locked":
        if st.get("session_id") != S.sid:
            S.reset(st.get("session_id"))
            await tell_owner(ctx, f"🔒 Locked in until {until_text(st)}. Text me study questions, or 'emergency <reason>' to leave early.")
        if now >= S.next_digest:
            S.next_digest = now + DIGEST_SECONDS
            fresh = [i for i in S.inbox if i["important"] and not i["digested"]]
            if fresh:
                text = await brain.digest(fresh, final=False, owner=OWNER_NAME)
                for i in fresh:
                    i["digested"] = True
                await pi.digest(text, final=False)
                span = f"{DIGEST_SECONDS // 60} min" if DIGEST_SECONDS >= 60 else f"{DIGEST_SECONDS} s"
                await tell_owner(ctx, f"🗞 Last {span}:\n{text}")
        return

    # idle: if we were tracking a session, it just ended → final digest
    if S.sid is not None:
        items = S.inbox
        if items:
            text = await brain.digest(items, final=True, owner=OWNER_NAME)
        else:
            text = "No messages. Clean session 💪"
        await pi.digest(f"{len(items)} message{'s' if len(items) != 1 else ''}. {text}" if items else text, final=True)
        reason = (st.get("last_unlock") or {}).get("reason", "timer")
        head = "✅ Session done!" if reason == "timer" else "🔓 Session ended early."
        await tell_owner(ctx, f"{head} While you were locked in:\n{text}")
        S.reset(None)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in agent/.env (get it from @BotFather). See README.md.")
    app = (
        Application.builder()
        .token(TOKEN)
        .rate_limiter(AIORateLimiter(max_retries=2))  # stays under Telegram's own send limits
        .concurrent_updates(8)  # a slow Gemini call doesn't block other people's messages
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("lock", cmd_lock))
    app.add_handler(CommandHandler("emergency", cmd_emergency_slash))
    app.add_handler(CommandHandler("free", cmd_free))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE & filters.TEXT, on_business))
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE & filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, on_private))
    app.job_queue.run_repeating(watch, interval=2, first=1)
    log.info("agent running. Pi: %s, owner: %s, digest every %ss", PI_URL, owner_id() or "not set (send /start)", DIGEST_SECONDS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

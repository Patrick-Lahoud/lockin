"""Lock In: Pi server.

The Pi is the boss: this process holds the only copy of the session state.
Everything else (laptop guard, Telegram agent, box screen) reads GET /state or asks
this server to change it. See ../CONTRACT.md.

Run:  python server.py          (port 8000, all interfaces)
Fake hardware is used automatically when there is no GPIO (e.g. on a laptop).
"""
import asyncio
import json
import os
import re
import secrets
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MUSIC = STATIC / "music"
STATE_FILE = Path(os.getenv("LOCKIN_STATE_FILE", str(ROOT / "state.json")))
PORT = int(os.getenv("LOCKIN_PORT", "8000"))

# ---------------------------------------------------------------- hardware
sys.path.insert(0, str(ROOT.parent / "hardware"))
try:
    import hardware as hw  # A's file: lock(), unlock(), lid_closed()
except Exception as e:  # file missing or broken: never block B's work on A's
    print(f"[server] could not import hardware.py ({e}); using built-in fake")

    class _FakeHW:
        REAL = False
        _lid = True

        def lock(self):
            print("[fake] LOCK")

        def unlock(self):
            print("[fake] UNLOCK")

        def lid_closed(self):
            return self._lid

        def set_fake_lid(self, closed):
            self._lid = bool(closed)

    hw = _FakeHW()

# ---------------------------------------------------------------- state
DEFAULT_STATE = {
    "mode": "idle",
    "started_at": None,
    "ends_at": None,
    "minutes": None,
    "session_id": 0,
    "exits_left": 5,
    "max_exits": 5,
    "lid_closed": True,
    "blocked_sites": ["instagram.com", "tiktok.com", "linkedin.com"],
    "blocked_apps": [],
    "todos": [],
    "last_message": None,
    "urgent_pending": False,
    "last_digest": None,
    "last_unlock": None,
    "nudge_at": None,
}

DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
APP_RE = re.compile(r"^[A-Za-z0-9 ._-]{1,40}$")
MAX_TODOS = 30

state: dict = {}
state_lock = asyncio.Lock()


def now() -> int:
    return int(time.time())


def load_state() -> dict:
    s = json.loads(json.dumps(DEFAULT_STATE))
    try:
        stored = json.loads(STATE_FILE.read_text())
        if isinstance(stored, dict):
            s.update({k: v for k, v in stored.items() if k in DEFAULT_STATE})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[server] state.json unreadable ({e}); starting fresh")
    return s


def save_state() -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_FILE)  # atomic: a crash never leaves half a file


def face() -> str:
    t = now()
    if state["mode"] == "locked":
        if state.get("nudge_at") and t - state["nudge_at"] < 30:
            return "sad"
        if state.get("urgent_pending"):
            return "worried"
        return "focused"
    lu = state.get("last_unlock")
    if lu and lu.get("reason") == "timer" and t - lu.get("at", 0) < 120:
        return "proud"
    return "happy"


def public_state() -> dict:
    s = dict(state)
    s.pop("nudge_at", None)
    s["lid_closed"] = bool(hw.lid_closed())
    s["server_time"] = now()
    s["face"] = face()
    return s


async def run_hw(fn) -> None:
    # servo moves take ~0.7 s; run them in a thread so the server keeps answering
    try:
        await asyncio.to_thread(fn)
    except Exception as e:
        print(f"[server] hardware error: {e}")


async def do_unlock(reason: str) -> None:
    """Caller must hold state_lock."""
    state["mode"] = "idle"
    state["ends_at"] = None
    state["urgent_pending"] = False
    state["last_unlock"] = {"reason": reason, "at": now()}
    save_state()
    await run_hw(hw.unlock)
    print(f"[server] unlocked ({reason})")


async def timer_loop() -> None:
    while True:
        await asyncio.sleep(0.5)
        if state.get("mode") == "locked" and state.get("ends_at") and now() >= state["ends_at"]:
            async with state_lock:
                if state["mode"] == "locked" and now() >= state["ends_at"]:
                    await do_unlock("timer")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.update(load_state())
    # A reboot must never open the box early: re-lock if the session is still running.
    if state["mode"] == "locked":
        if state.get("ends_at") and now() < state["ends_at"]:
            print("[server] resuming locked session after restart")
            await run_hw(hw.lock)
        else:
            await do_unlock("timer")
    save_state()
    task = asyncio.create_task(timer_loop())
    yield
    task.cancel()


app = FastAPI(title="Lock In", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# No CORS on purpose: the box pages are same-origin, and the agent + laptop guard aren't browsers.
# Allowing "*" would let ANY website open on the laptop call /unlock in the background.

# ---------------------------------------------------------------- rate limits (per IP)
# GET /state is polled constantly and stays unlimited. Changes are limited:
RATE_LIMITS = {
    "/lock": (6, 60),        # 6 per minute
    "/unlock": (6, 60),
    "/settings": (10, 60),
    "/reset": (5, 60),
    "*": (60, 60),           # every other POST/DELETE: 60 per minute
}
MAX_BODY_BYTES = 16 * 1024
_hits: dict = defaultdict(deque)


@app.middleware("http")
async def guard_requests(request: Request, call_next):
    if request.method in ("POST", "DELETE", "PUT", "PATCH"):
        if int(request.headers.get("content-length") or 0) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        path = request.url.path
        limit, window = RATE_LIMITS.get(path, RATE_LIMITS["*"])
        bucket = path if path in RATE_LIMITS else "*"
        key = (request.client.host if request.client else "?", bucket)
        q, t = _hits[key], time.monotonic()
        while q and t - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"detail": "Too many requests, slow down"}, status_code=429, headers={"Retry-After": str(window)})
        q.append(t)
        if len(_hits) > 5000:  # don't let the table grow forever
            _hits.clear()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ---------------------------------------------------------------- helpers
async def body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def clean_text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def clean_domain(value) -> str | None:
    d = str(value or "").strip().lower()
    d = re.sub(r"^[a-z]+://", "", d).split("/")[0].split(":")[0]
    d = d.removeprefix("www.")
    return d if DOMAIN_RE.match(d) else None


# ---------------------------------------------------------------- API
@app.get("/state")
async def get_state():
    return public_state()


@app.post("/lock")
async def post_lock(request: Request):
    data = await body(request)
    try:
        minutes = float(data.get("minutes", 25))
    except (TypeError, ValueError):
        raise HTTPException(400, "minutes must be a number")
    if not 0 < minutes <= 240:
        raise HTTPException(400, "minutes must be between 0 and 240")
    async with state_lock:
        if state["mode"] == "locked":
            raise HTTPException(409, "Already locked in")
        if not hw.lid_closed():
            raise HTTPException(409, "Close the lid first")
        t = now()
        state.update(
            mode="locked",
            started_at=t,
            ends_at=t + max(5, int(round(minutes * 60))),
            minutes=minutes,
            session_id=state["session_id"] + 1,
            last_message=None,
            urgent_pending=False,
            last_digest=None,
            nudge_at=None,
        )
        save_state()
        await run_hw(hw.lock)
        print(f"[server] locked for {minutes} min (session {state['session_id']})")
        return public_state()


@app.post("/unlock")
async def post_unlock(request: Request):
    reason = (await body(request)).get("reason", "timer")
    if reason not in ("timer", "emergency", "urgent"):
        raise HTTPException(400, "reason must be timer, emergency or urgent")
    async with state_lock:
        if state["mode"] != "locked":
            return public_state()  # already open: nothing to do
        if reason == "timer" and now() < (state["ends_at"] or 0):
            raise HTTPException(403, "Timer is still running")
        if reason == "emergency":
            if state["exits_left"] <= 0:
                raise HTTPException(403, "No emergency exits left")
            state["exits_left"] -= 1
        if reason == "urgent" and not state.get("urgent_pending"):
            raise HTTPException(403, "No urgent message waiting")
        await do_unlock(reason)
        return public_state()


@app.post("/todo")
async def post_todo(request: Request):
    data = await body(request)
    text = clean_text(data.get("text"), 120)
    if not text:
        raise HTTPException(400, "text is required")
    async with state_lock:
        state["todos"].append(
            {"id": secrets.token_hex(3), "text": text, "from": clean_text(data.get("from"), 40) or "Me", "done": False}
        )
        state["todos"] = state["todos"][-MAX_TODOS:]
        save_state()
        return public_state()


@app.post("/todo/{todo_id}/toggle")
async def toggle_todo(todo_id: str):
    async with state_lock:
        for t in state["todos"]:
            if t["id"] == todo_id:
                t["done"] = not t["done"]
                save_state()
                return public_state()
    raise HTTPException(404, "No such to-do")


@app.delete("/todo/{todo_id}")
async def delete_todo(todo_id: str):
    async with state_lock:
        state["todos"] = [t for t in state["todos"] if t["id"] != todo_id]
        save_state()
        return public_state()


@app.post("/message")
async def post_message(request: Request):
    data = await body(request)
    text = clean_text(data.get("text"), 300)
    if not text:
        raise HTTPException(400, "text is required")
    urgent = bool(data.get("urgent"))
    async with state_lock:
        state["last_message"] = {"from": clean_text(data.get("from"), 40) or "Someone", "text": text, "urgent": urgent, "at": now()}
        if urgent and state["mode"] == "locked":
            state["urgent_pending"] = True
        save_state()
        return public_state()


@app.post("/digest")
async def post_digest(request: Request):
    data = await body(request)
    text = str(data.get("text") or "").strip()[:800]
    if not text:
        raise HTTPException(400, "text is required")
    async with state_lock:
        state["last_digest"] = {"text": text, "final": bool(data.get("final")), "at": now()}
        save_state()
        return public_state()


@app.post("/settings")
async def post_settings(request: Request):
    data = await body(request)
    async with state_lock:
        if state["mode"] == "locked":
            raise HTTPException(409, "You can't change what's blocked during a session")
        if "blocked_sites" in data:
            sites = [clean_domain(d) for d in (data["blocked_sites"] or [])]
            if any(s is None for s in sites):
                raise HTTPException(400, "One of the sites is not a valid domain")
            state["blocked_sites"] = list(dict.fromkeys(sites))[:30]
        if "blocked_apps" in data:
            apps = [clean_text(a, 40) for a in (data["blocked_apps"] or [])]
            if any(not APP_RE.match(a) for a in apps):
                raise HTTPException(400, "App names can only use letters, numbers, spaces, . _ -")
            state["blocked_apps"] = list(dict.fromkeys(apps))[:20]
        if "max_exits" in data:
            try:
                m = int(data["max_exits"])
            except (TypeError, ValueError):
                raise HTTPException(400, "max_exits must be a number")
            if not 0 <= m <= 20:
                raise HTTPException(400, "max_exits must be 0..20")
            state["max_exits"] = m
            state["exits_left"] = min(state["exits_left"], m)
        save_state()
        return public_state()


@app.post("/nudge")
async def post_nudge():
    async with state_lock:
        state["nudge_at"] = now()
        save_state()
        return public_state()


@app.post("/reset")
async def post_reset():
    """Demo helper: refill exits and clear messages. Doesn't touch an active lock."""
    async with state_lock:
        state.update(exits_left=state["max_exits"], last_message=None, urgent_pending=False, last_digest=None, last_unlock=None)
        save_state()
        return public_state()


@app.post("/dev/lid")
async def dev_lid(request: Request):
    """Testing without the box: {"closed": false} simulates an open lid."""
    if getattr(hw, "REAL", False):
        raise HTTPException(400, "Real lid sensor in use")
    hw.set_fake_lid(bool((await body(request)).get("closed", True)))
    return public_state()


@app.get("/music")
async def list_music():
    MUSIC.mkdir(exist_ok=True)
    files = sorted(p.name for p in MUSIC.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".ogg", ".wav"))
    return [{"title": Path(f).stem.replace("_", " ").replace("-", " "), "url": "/static/music/" + quote(f)} for f in files]


# ---------------------------------------------------------------- pages
NO_CACHE = {"Cache-Control": "no-store"}


@app.get("/")
async def page_box():
    return FileResponse(STATIC / "index.html", headers=NO_CACHE)


@app.get("/setup")
async def page_setup():
    return FileResponse(STATIC / "setup.html", headers=NO_CACHE)


@app.get("/blocked")
async def page_blocked():
    return FileResponse(STATIC / "blocked.html", headers=NO_CACHE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

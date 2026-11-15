"""Lock In agent: is everything it needs actually connected?

    .venv/bin/python doctor.py            (Windows: .venv\\Scripts\\python.exe doctor.py)

It checks, in order: the .env file, the Telegram token (getMe), the Gemini key
and model (one tiny real call), and the Pi (GET /state). PASS/FAIL per line.
No key is ever printed.
"""
from __future__ import annotations  # keeps the `X | None` hints working on Python 3.9

import asyncio
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    load_dotenv(HERE / ".env")
except Exception:  # deps not installed yet: fall back to the real environment
    pass

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
PI_URL = os.getenv("PI_URL", "http://lockin.local:8000").rstrip("/")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

ALL_OK = True


def check(name: str, ok: bool, detail: str = "") -> None:
    global ALL_OK
    ALL_OK = ALL_OK and ok
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


async def main() -> int:
    print("Lock In agent check\n")

    has_env = (HERE / ".env").exists()
    check(".env file", has_env, "" if has_env else "cp .env.example .env, then fill it in")
    check("TELEGRAM_BOT_TOKEN", bool(TOKEN), "" if TOKEN else "from @BotFather")
    check("GEMINI_API_KEY", bool(GEMINI), "" if GEMINI else "from aistudio.google.com/apikey")

    try:
        import httpx
    except Exception:
        check("dependencies", False, "pip install -r requirements.txt")
        return print_result()

    if TOKEN:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                data = (await client.get(f"https://api.telegram.org/bot{TOKEN}/getMe")).json()
            if data.get("ok"):
                check("Telegram token", True, "@" + data["result"]["username"])
            else:
                check("Telegram token", False, str(data.get("description"))[:80])
        except Exception as e:
            check("Telegram token", False, f"{type(e).__name__}: can't reach api.telegram.org")

    if GEMINI:
        try:
            from google import genai

            client = genai.Client(api_key=GEMINI)
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL, contents='Reply with JSON only: {"ok": true}'),
                timeout=20,
            )
            check("Gemini key + model", bool(resp.text), MODEL)
        except Exception as e:
            check("Gemini key + model", False, f"{type(e).__name__}: {str(e)[:90]}")

    try:
        async with httpx.AsyncClient(timeout=4) as client:
            state = (await client.get(f"{PI_URL}/state")).json()
        check(
            "Pi reachable",
            True,
            f"{PI_URL} · {state.get('mode')} · {state.get('exits_left')}/{state.get('max_exits')} exits",
        )
    except Exception as e:
        check("Pi reachable", False, f"{PI_URL} ({type(e).__name__})")

    return print_result()


def print_result() -> int:
    print()
    if ALL_OK:
        print("Everything is connected. Start the agent:  .venv/bin/python bot.py")
        print('Then send your bot "start 25" on Telegram and watch the box lock.')
    else:
        print("Fix the FAIL lines above and run this again.")
    return 0 if ALL_OK else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass

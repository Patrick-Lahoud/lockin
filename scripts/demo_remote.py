#!/usr/bin/env python3
"""Demo remote: press a number + Enter at the moment your teammate sends the message on stage.

    python3 scripts/demo_remote.py

Each key sends one phone notification into the box (same path the Android forwarder uses);
everything after that is real: Gemini sorting, to-do, red alert, Telegram alert, summary.
Say on stage that on iPhone the notification is fed in by hand.
"""
import json
import sys
import urllib.request

_args = [a for a in sys.argv[1:] if not a.startswith("--")]
PI = (_args[0] if _args else "http://127.0.0.1:8000").rstrip("/")
SCRIPT = {
    "1": ("Snapchat", "Alex", "can u buy a bread on the way home?"),
    "2": ("WhatsApp", "Mom", "grandma fell, call me when u see it"),
    "3": ("Instagram", "jess", "liked your photo"),            # shows noise being ignored
    "4": ("WhatsApp", "Study Group", "Ben: lol did anyone do q3"),
}
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def send(app, title, text):
    req = urllib.request.Request(f"{PI}/inbox", data=f"{app}\n{title}\n{text}".encode(),
                                 headers={"Content-Type": "text/plain; charset=utf-8"}, method="POST")
    with DIRECT.open(req, timeout=5) as r:
        return json.load(r)


def mode():
    with DIRECT.open(f"{PI}/state", timeout=5) as r:
        return json.load(r)["mode"]


# --auto: every time the box locks, send these on a timer (seconds after the lock starts)
TIMELINE = [
    (35, ("Snapchat", "Alex", "can u buy a bread on the way home?")),
    (50, ("WhatsApp", "Mom", "grandma fell, come home right away!! call me when u see it")),
]

if "--auto" in sys.argv:
    import time
    print("Lock In demo remote: AUTO mode")
    for t, (app, who, text) in TIMELINE:
        print(f"  +{t}s after locking → {app}: {who}: {text}")
    print("  (Ctrl+C to stop)\n")
    done = set()
    while True:
        try:
            with DIRECT.open(f"{PI}/state", timeout=5) as r:
                st = json.load(r)
            if st["mode"] == "locked" and st.get("started_at"):
                sid = st["session_id"]
                if (sid, "clean") not in done:  # fresh demo each time: remove old "bread" to-dos
                    done.add((sid, "clean"))
                    for t in st.get("todos", []):
                        if "bread" in t["text"].lower():
                            DIRECT.open(urllib.request.Request(f"{PI}/todo/{t['id']}", method="DELETE"), timeout=5).read()
                elapsed = st.get("server_time", time.time()) - st["started_at"]
                for i, (t, msg) in enumerate(TIMELINE):
                    if (sid, i) not in done and elapsed >= t:
                        done.add((sid, i))
                        if elapsed < t + 15:  # don't fire old ones if we joined late
                            send(*msg)
                            print(time.strftime("%H:%M:%S"), f"session {sid}: +{t}s sent {msg[0]}: {msg[2]}", flush=True)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("  can't reach the box:", e, flush=True)
            time.sleep(2)
        time.sleep(0.5)
    sys.exit(0)

print("Lock In demo remote")
for k, (app, who, text) in SCRIPT.items():
    print(f"  {k} + Enter → {app:9} {who}: {text}")
print("  q + Enter → quit\n")
while True:
    try:
        k = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        break
    if k == "q":
        break
    if k not in SCRIPT:
        continue
    try:
        if mode() != "locked":
            print("  ⚠️  the box isn't locked: lock it first, or the agent ignores phone messages")
        res = send(*SCRIPT[k])
        print(f"  ✅ sent ({SCRIPT[k][0]}): the box shows it within ~2 s" if res.get("ok") else f"  ❌ {res}")
    except Exception as e:
        print(f"  ❌ can't reach the box at {PI}: {e}")

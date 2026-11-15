#!/usr/bin/env python3
"""Runs ON THE PI. The only program the Pi needs besides the browser.

The Lock In server runs on the laptop (the "brain"). This tiny script just asks the laptop
"are we locked?" 3 times a second and turns the servo when the answer changes.
No server, no pip install: Python standard library + gpiozero (already on Raspberry Pi OS).

    python3 servo_follower.py 192.168.43.20          # the laptop's IP
    python3 servo_follower.py http://192.168.43.20:8000
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hardware"))
import hardware  # lock(), unlock()  (falls back to printing if there's no GPIO)

if len(sys.argv) < 2:
    sys.exit("Usage: python3 servo_follower.py <laptop-ip>")
target = sys.argv[1].rstrip("/")
URL = (target if target.startswith("http") else f"http://{target}:8000") + "/state"
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via a proxy


def mode_now():
    try:
        with DIRECT.open(URL, timeout=2) as r:
            return json.load(r).get("mode")
    except Exception:
        return None


def move(fn, name):
    for attempt in range(3):  # retry: the latch matters
        try:
            fn()
            return
        except Exception as e:
            print(f"servo {name} failed (try {attempt + 1}/3): {e}", flush=True)
            time.sleep(0.3)


if not hardware.REAL:
    print(f"⚠️  No GPIO ({hardware.FAKE_REASON}) — the servo won't move. Is something else using the pin?", flush=True)

print(f"Following {URL}", flush=True)
current = None
offline_since = None
while True:
    mode = mode_now()
    if mode is None:
        # Laptop unreachable: keep the latch exactly as it is (fail closed). Just say so once.
        if offline_since is None:
            offline_since = time.time()
            print("can't reach the laptop, keeping the latch as it is…", flush=True)
    else:
        if offline_since is not None:
            print("laptop reachable again", flush=True)
            offline_since = None
        if mode != current:
            if mode == "locked":
                move(hardware.lock, "lock")
            else:
                move(hardware.unlock, "unlock")
            print(time.strftime("%H:%M:%S"), "→", mode, flush=True)
            current = mode
    time.sleep(0.3)

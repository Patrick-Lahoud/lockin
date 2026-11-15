#!/usr/bin/env python3
"""Pretend to be the Android phone in the box: sends realistic notifications to the Pi.

Use it to test the agent without the phone, or as a backup on stage.
    python3 scripts/simulate_phone.py --pi http://lockin.local:8000            # full demo story
    python3 scripts/simulate_phone.py --pi http://localhost:8000 --fast       # 1 s between notifications
    python3 scripts/simulate_phone.py --pi http://localhost:8000 --one "WhatsApp|Mom|call me now"

It sends the same formats MacroDroid does (plain text lines, JSON, form), so it tests the parser too.
"""
import argparse
import json
import time
import urllib.parse
import urllib.request

# (app, title, text, seconds to wait after). Noise and signal mixed like a real phone.
STORY = [
    ("Instagram", "jess.m", "liked your photo", 2),
    ("Instagram", "alex.chen", "yo are you coming to the party tonight?", 2),
    ("TikTok", "TikTok", "creator_daily posted a new video", 2),
    ("Snapchat", "maya", "sent you a Snap", 2),
    ("WhatsApp", "Mom", "Can you buy bread on the way home?", 3),
    ("WhatsApp", "Study Group", "Ben: lol did anyone do q3", 2),
    ("LinkedIn", "LinkedIn", "Sarah Lee viewed your profile", 2),
    ("Telegram", "Prof. Kim", "Midterm room changed to MC 105, see you at 4pm", 3),
    ("WhatsApp", "Mom", "Can you buy bread on the way home?", 2),  # Android re-post → deduped
    ("Snapchat", "maya", "maya is typing...", 2),
    ("Instagram", "Instagram", "alex.chen: also bring the speaker if you can", 3),
    ("WhatsApp", "Mom", "Grandpa fell, call me right now please", 2),
    ("Phone", "Missed call", "Mom", 2),
]


def send(pi: str, app: str, title: str, text: str, fmt: str) -> str:
    url = f"{pi.rstrip('/')}/inbox"
    if fmt == "text":  # what we recommend in MacroDroid: one field per line
        body, ctype = f"{app}\n{title}\n{text}".encode(), "text/plain; charset=utf-8"
    elif fmt == "json":
        body, ctype = json.dumps({"app": app, "title": title, "text": text}).encode(), "application/json"
    else:
        body, ctype = urllib.parse.urlencode({"app": app, "title": title, "text": text}).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read().decode()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pi", default="http://lockin.local:8000")
    p.add_argument("--fast", action="store_true", help="1 s between notifications")
    p.add_argument("--one", help='send one: "App|Title|Text"')
    a = p.parse_args()
    if a.one:
        app, title, text = (a.one.split("|", 2) + ["", ""])[:3]
        print(send(a.pi, app, title, text, "text"))
        return
    formats = ["text", "json", "form"]
    for n, (app, title, text, wait) in enumerate(STORY):
        res = send(a.pi, app, title, text, formats[n % 3])
        print(f"📱 {app:9} {title:12} {text[:50]:50} → {res}")
        time.sleep(1 if a.fast else wait)


if __name__ == "__main__":
    main()

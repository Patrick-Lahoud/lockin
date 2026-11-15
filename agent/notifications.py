"""Phone notifications → clean messages the brain can judge.

The Android phone in the box forwards EVERY notification (MacroDroid → Pi POST /inbox).
Most of them are noise. This module throws away the junk for free, before Gemini:

  1. normalize   package names → "Instagram", "WhatsApp"…; who sent it; the text
  2. ignore      system apps, MacroDroid itself, and our own bot (no feedback loops)
  3. noise       likes, follows, "is typing", "posted a story", "5 new messages" summaries…
  4. dedupe      Android re-posts the same notification many times
  5. bursts      the same person 3× in 2 min = important; repeated missed calls = urgent

Only what survives goes to Gemini, in one batch call.
"""
from __future__ import annotations  # keeps the `X | None` hints working on Python 3.9

import re
import time
from collections import defaultdict, deque

APP_NAMES = {
    "com.instagram.android": "Instagram",
    "com.instagram.barcelona": "Threads",
    "com.snapchat.android": "Snapchat",
    "com.whatsapp": "WhatsApp",
    "com.whatsapp.w4b": "WhatsApp Business",
    "org.telegram.messenger": "Telegram",
    "org.telegram.messenger.web": "Telegram",
    "org.thunderdog.challegram": "Telegram",
    "com.zhiliaoapp.musically": "TikTok",
    "com.ss.android.ugc.trill": "TikTok",
    "com.linkedin.android": "LinkedIn",
    "com.facebook.orca": "Messenger",
    "com.facebook.katana": "Facebook",
    "com.discord": "Discord",
    "com.google.android.apps.messaging": "Messages",
    "com.samsung.android.messaging": "Messages",
    "com.android.mms": "Messages",
    "com.google.android.dialer": "Phone",
    "com.samsung.android.dialer": "Phone",
    "com.android.server.telecom": "Phone",
    "com.google.android.gm": "Gmail",
    "com.slack": "Slack",
    "com.microsoft.teams": "Teams",
}
# Apps we send to Gemini. Anything else is counted, never judged (saves the API key).
MESSAGING_APPS = {
    "Instagram", "Snapchat", "WhatsApp", "WhatsApp Business", "Telegram", "TikTok", "LinkedIn",
    "Messenger", "Facebook", "Discord", "Messages", "Phone", "Slack", "Teams", "Threads", "Gmail",
}
IGNORE_PACKAGES = {
    "android", "com.android.systemui", "com.arlosoft.macrodroid", "com.google.android.gms",
    "com.android.vending", "com.google.android.googlequicksearchbox", "com.android.providers.downloads",
    "com.android.settings", "com.google.android.apps.wellbeing",
}
IGNORE_APP_NAMES = {"macrodroid", "android system", "system ui", "google play store", "google play services", "settings"}

# Free, instant noise rules (checked on "title text", lowercased)
NOISE_PATTERNS = [
    r"\bliked your\b", r"\bliked a\b", r"\breacted\b", r"\bstarted following you\b", r"\bfollowed you\b",
    r"\bis live\b", r"\bwent live\b", r"\bposted (a|an|new|their)\b", r"\badded to (their|his|her) story\b",
    r"\bshared a (post|reel|video|story)\b", r"\bnew (post|reel|video)s?\b", r"\bsuggested for you\b",
    r"\bviewed your (profile|story)\b", r"\bappeared in \d+ searches\b", r"\bis typing\b", r"\btyping\.\.\.",
    r"\bsent you a snap\b", r"\bsent a snap\b", r"\bnew snap\b", r"\bsnap streak\b",
    r"^\d+ (new )?messages?( from \d+ chats?)?$", r"\b\d+ new messages\b", r"\bmessages from \d+ chats\b",
    r"\bchecking for new messages\b", r"\bbackup in progress\b", r"\bdownloading\b", r"\buploading\b",
    r"\bwhatsapp web is currently active\b", r"\bwaiting for this message\b",
    r"\b(trending|recommended|you might like|people you may know|job alert|jobs? for you)\b",
    r"\bcongratulate\b", r"\bwork anniversary\b", r"\bbirthday\b.*\bwish\b",
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.I)
URGENT_HINT = re.compile(r"\b(urgent|emergency|asap|hospital|accident|call me|right now|help)\b", re.I)
# School/work logistics are always worth knowing (deterministic: the model sometimes misses them)
LOGISTICS = re.compile(
    r"\b(room|moved|changed|cancel(l)?ed|resched\w*|deadline|due|exam|midterm|final|quiz|test|class|lecture|"
    r"tutorial|lab|meeting|interview|shift|assignment|submission|office hours|prof(essor)?|teacher|boss|manager)\b",
    re.I,
)


def looks_important(n: dict) -> bool:
    return n["messaging"] and bool(LOGISTICS.search(f"{n['sender']} {n['text']}"))


def app_name(raw: dict) -> str:
    pkg = (raw.get("package") or "").strip()
    name = (raw.get("app") or "").strip()
    if pkg in APP_NAMES:
        return APP_NAMES[pkg]
    if name in APP_NAMES:  # someone sent the package as "app"
        return APP_NAMES[name]
    for known in MESSAGING_APPS:  # "WhatsApp Messenger" → WhatsApp
        if name.lower().startswith(known.lower()):
            return known
    return name or (pkg.split(".")[-1].title() if pkg else "Phone")


def normalize(raw: dict, ignore_titles: set[str]) -> dict | None:
    """-> {"app", "sender", "text", "key", "at"} or None if it should be ignored completely."""
    pkg = (raw.get("package") or "").strip()
    app = app_name(raw)
    if pkg in IGNORE_PACKAGES or app.lower() in IGNORE_APP_NAMES:
        return None
    title = (raw.get("title") or "").strip()
    text = (raw.get("text") or "").strip()
    if not (title or text):
        return None
    if title.lower() in ignore_titles:  # our own bot's messages → no feedback loop
        return None
    sender = title or app
    # "Mom: buy bread" style text with the app name as title
    if (not title or title.lower() == app.lower()) and ":" in text[:40]:
        sender, text = [x.strip() for x in text.split(":", 1)]
    # Dialer: title "Missed call", text "Mom" → sender Mom
    if app == "Phone" and re.search(r"missed call", title, re.I):
        sender, text = (text or "Unknown number"), "Missed call"
    # WhatsApp/Telegram group titles look like "Study Group: Ben" or "Ben @ Study Group"
    return {
        "app": app,
        "sender": sender[:60],
        "text": text[:600] or title,
        "key": f"{app}|{sender.lower()}",
        "at": raw.get("at") or time.time(),
        "messaging": app in MESSAGING_APPS,
    }


def is_noise(n: dict) -> bool:
    if not n["messaging"]:
        return True
    return bool(NOISE_RE.search(f"{n['sender']} {n['text']}"))


class Deduper:
    """Android re-posts the same notification (updates, summaries). Drop repeats for 10 min."""

    def __init__(self, ttl: float = 600):
        self.ttl = ttl
        self.seen: dict[str, float] = {}

    def is_new(self, n: dict) -> bool:
        now = time.time()
        if len(self.seen) > 2000:
            self.seen = {k: t for k, t in self.seen.items() if now - t < self.ttl}
        key = f"{n['key']}|{n['text'].lower()}"
        if key in self.seen and now - self.seen[key] < self.ttl:
            return False
        self.seen[key] = now
        return True

    def reset(self):
        self.seen.clear()


class Bursts:
    """Same person messaging again and again = they really want you."""

    def __init__(self):
        self.times: dict[str, deque] = defaultdict(deque)

    def bump(self, n: dict) -> dict:
        """Returns {"important": bool, "urgent": bool} forced by repetition."""
        now = time.time()
        q = self.times[n["key"]]
        q.append(now)
        while q and now - q[0] > 300:
            q.popleft()
        in_2_min = sum(1 for t in q if now - t <= 120)
        missed_call = n["app"] == "Phone" and re.search(r"missed", f"{n['sender']} {n['text']}", re.I)
        return {
            "important": in_2_min >= 3 or bool(missed_call),
            "urgent": bool(missed_call and len(q) >= 2) or (in_2_min >= 3 and bool(URGENT_HINT.search(n["text"]))),
        }

    def reset(self):
        self.times.clear()

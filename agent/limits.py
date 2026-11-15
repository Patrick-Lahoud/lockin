"""Rate limits, a spend budget for Gemini, a small cache, and log redaction.

Everything here protects the Gemini key and the bot from being abused:
  * GeminiBudget   hard caps per minute / per day (+ max 3 calls at once). Over the cap → keyword rules, no API call.
  * SlidingWindow  per-person limits (strangers spamming the bot, owner asking 100 questions).
  * TTLCache       the same message text isn't sent to Gemini twice within 10 minutes.
  * RedactSecrets  a logging filter: the bot token and API key can never appear in logs.
"""
import asyncio
import json
import logging
import time
from collections import OrderedDict, defaultdict, deque
from datetime import date
from pathlib import Path


class SlidingWindow:
    """At most `limit` events per `seconds`, tracked per key."""

    def __init__(self, limit: int, seconds: float):
        self.limit, self.seconds = limit, seconds
        self.events: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str = "_") -> bool:
        now = time.monotonic()
        q = self.events[key]
        while q and now - q[0] > self.seconds:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self.events.clear()
        else:
            self.events.pop(key, None)


class GeminiBudget:
    """Global caps for every Gemini call. The daily count survives restarts (.usage.json)."""

    def __init__(self, per_minute: int, per_day: int, usage_file: Path, concurrency: int = 3):
        self.minute = SlidingWindow(per_minute, 60)
        self.per_day = per_day
        self.usage_file = usage_file
        self.sem = asyncio.Semaphore(concurrency)
        self._warned = 0.0
        self.day, self.count = self._load()

    def _load(self):
        try:
            d = json.loads(self.usage_file.read_text())
            if d.get("day") == date.today().isoformat():
                return d["day"], int(d["count"])
        except Exception:
            pass
        return date.today().isoformat(), 0

    def _save(self):
        try:
            self.usage_file.write_text(json.dumps({"day": self.day, "count": self.count}))
        except Exception:
            pass

    def take(self) -> bool:
        today = date.today().isoformat()
        if today != self.day:
            self.day, self.count = today, 0
        if self.count >= self.per_day or not self.minute.allow():
            if time.monotonic() - self._warned > 60:
                self._warned = time.monotonic()
                logging.getLogger("limits").warning(
                    "Gemini budget reached (%d/%d today, or >%d/min). Using keyword rules.", self.count, self.per_day, self.minute.limit
                )
            return False
        self.count += 1
        self._save()
        return True


class TTLCache:
    def __init__(self, ttl: float = 600, size: int = 200):
        self.ttl, self.size = ttl, size
        self.data: OrderedDict = OrderedDict()

    def get(self, key):
        item = self.data.get(key)
        if not item or time.monotonic() - item[0] > self.ttl:
            self.data.pop(key, None)
            return None
        return item[1]

    def put(self, key, value):
        self.data[key] = (time.monotonic(), value)
        self.data.move_to_end(key)
        while len(self.data) > self.size:
            self.data.popitem(last=False)


class RedactSecrets(logging.Filter):
    """Replaces secrets in every log line (including library logs and tracebacks)."""

    def __init__(self, *secrets: str):
        super().__init__()
        self.secrets = [s for s in secrets if s and len(s) >= 8]

    def _clean(self, text: str) -> str:
        for s in self.secrets:
            text = text.replace(s, "[REDACTED]")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if self.secrets:
            record.msg = self._clean(record.getMessage())
            record.args = ()
            if record.exc_info and not record.exc_text:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            if record.exc_text:
                record.exc_text = self._clean(record.exc_text)
        return True


def install_redaction(*secrets: str) -> None:
    f = RedactSecrets(*secrets)
    for h in logging.getLogger().handlers:
        h.addFilter(f)

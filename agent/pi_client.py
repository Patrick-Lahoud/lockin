"""Tiny client for the Pi server (see ../CONTRACT.md). Every call returns (ok, data)."""
from __future__ import annotations  # keeps the `X | None` hints working on Python 3.9

import httpx


class Pi:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.http = httpx.AsyncClient(timeout=4)

    async def _call(self, method: str, path: str, body: dict | None = None):
        try:
            r = await self.http.request(method, f"{self.url}{path}", json=body)
            data = r.json() if r.content else {}
            return r.is_success, data
        except Exception as e:
            return False, {"detail": f"Can't reach the box ({e.__class__.__name__})"}

    async def state(self) -> dict | None:
        ok, data = await self._call("GET", "/state")
        return data if ok else None

    async def lock(self, minutes: float):
        return await self._call("POST", "/lock", {"minutes": minutes})

    async def unlock(self, reason: str):
        return await self._call("POST", "/unlock", {"reason": reason})

    async def todo(self, text: str, sender: str):
        return await self._call("POST", "/todo", {"text": text, "from": sender})

    async def message(self, sender: str, text: str, urgent: bool):
        return await self._call("POST", "/message", {"from": sender, "text": text, "urgent": urgent})

    async def digest(self, text: str, final: bool):
        return await self._call("POST", "/digest", {"text": text, "final": final})

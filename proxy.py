#!/usr/bin/env python3
"""CloudChecker v3.1 – Proxy manager with rotation, cooldowns, and scoring."""

from __future__ import annotations

import asyncio
import itertools
import random
import re
import time
from urllib.parse import urlparse

import aiohttp

from config import ENDPOINT

# Quick proxy-URL sanity check (same logic as wizard._PROXY_RE)
_VALID_PROXY = re.compile(
    r"^https?://(?:[^@\s]+@)?[a-zA-Z0-9](?:[a-zA-Z0-9\-.]*[a-zA-Z0-9])?:\d{1,5}$"
)


class ProxyManager:
    """Manages proxy rotation with per-proxy ratelimit cooldowns.

    For a single proxy (rotating gateway) every request gets a fresh
    IP from the pool — the proxy itself is never marked dead.
    """

    def __init__(
        self,
        proxies: list[str],
        remove_on_fail: bool = True,
        scored: bool = False,
    ) -> None:
        cleaned = [p.strip() if p else None for p in proxies]
        self._proxies: list[str | None] = cleaned if cleaned else [None]
        self._proxyless = all(p is None for p in self._proxies)
        self._cycle = itertools.cycle(self._proxies)
        self._dead: set[str] = set()
        self._cooldowns: dict[str, float] = {}
        self.remove_on_fail = remove_on_fail
        self._lock = asyncio.Lock()

        # ── scoring (scraped free proxies only) ──
        self._scored = scored
        self._scores: dict[str, int] = {}
        self._rate_limited_until: dict[str, float] = {}
        if scored:
            for raw in self._proxies:
                if raw and raw.strip():
                    key = self._format(raw) or raw.strip()
                    self._scores[key] = 1

    # ── Properties ──

    @property
    def is_proxyless(self) -> bool:
        return self._proxyless

    @property
    def is_single(self) -> bool:
        """True if exactly one proxy (rotating gateway)."""
        return len(self._proxies) == 1 and not self._proxyless

    @property
    def alive_count(self) -> int:
        """Number of proxies that are not dead (for display)."""
        if self.is_single:
            return 1  # rotating gateway is always "alive"
        return max(0, len(self._proxies) - len(self._dead))

    @property
    def total_count(self) -> int:
        return len(self._proxies)

    # ── Formatting ──

    @staticmethod
    def _format(raw: str | None) -> str | None:
        if raw is None:
            return None
        raw = raw.strip()
        return f"http://{raw}" if not raw.startswith("http") else raw

    # ── Core: next proxy ──

    async def next(self) -> str | None:
        """Return the next ready proxy.

        - Proxyless → None (valid).
        - Rotating gateway → always returns the proxy immediately.
        - Static list → skips dead & cooldown proxies, waits if all busy.
        - Scored (free) → weighted random pick from live proxies.
        """
        if self._proxyless:
            return None

        # Rotating gateway – never block
        if self.is_single:
            return self._format(self._proxies[0])

        # Scored path (scraped free proxies) – weighted random
        if self._scored:
            while True:
                async with self._lock:
                    live = {
                        k: v for k, v in self._scores.items()
                        if k and v > 0
                        and k not in self._dead
                        and (k not in self._cooldowns or time.time() >= self._cooldowns.get(k, 0))
                        and (k not in self._rate_limited_until or time.time() >= self._rate_limited_until.get(k, 0))
                    }
                    if not live:
                        return None
                    keys = list(live.keys())
                    weights = [live[k] for k in keys]
                    total_w = sum(weights)
                    pick = random.uniform(0, total_w) if total_w > 0 else 0
                    acc = 0
                    for i, k in enumerate(keys):
                        acc += weights[i]
                        if acc >= pick:
                            return k
                    return keys[-1]

        # Static multi-proxy path
        while True:
            async with self._lock:
                if len(self._dead) >= len(self._proxies):
                    return None

                for _ in range(len(self._proxies) * 2):
                    raw = next(self._cycle)
                    proxy = self._format(raw) if raw else None
                    key = proxy or ""
                    if key in self._dead:
                        continue
                    if key in self._cooldowns and time.time() < self._cooldowns[key]:
                        continue
                    return proxy

                # All proxies are in cooldown — wait for the earliest one
                now = time.time()
                earliest = min(
                    (v for v in self._cooldowns.values() if v > now),
                    default=now + 1,
                )
                wait = max(earliest - now, 0.2)

            await asyncio.sleep(wait)

    # ── Scoring API (called by Checker for scraped proxies) ──

    def score_hit(self, proxy: str | None) -> None:
        """+5 points for a working proxy."""
        if not self._scored or not proxy:
            return
        key = proxy
        if key in self._scores:
            self._scores[key] = min(self._scores[key] + 5, 100)

    def set_rate_limit(self, proxy: str | None, seconds: float) -> None:
        """Mark proxy as rate-limited until *now + seconds*."""
        if not self._scored or not proxy:
            return
        key = proxy
        if key in self._scores:
            self._rate_limited_until[key] = time.time() + seconds

    def score_miss(self, proxy: str | None) -> None:
        """-1 point for a failed proxy.  Score ≤ 0 → removed."""
        if not self._scored or not proxy:
            return
        key = proxy
        if key in self._scores:
            self._scores[key] -= 1
            if self._scores[key] <= 0:
                self._dead.add(key)
                del self._scores[key]

    async def mark_dead(self, proxy: str | None) -> None:
        if not self.remove_on_fail or proxy is None:
            return
        async with self._lock:
            self._dead.add(proxy)

    async def set_cooldown(self, proxy: str | None, seconds: float) -> None:
        if proxy is None:
            return
        async with self._lock:
            self._cooldowns[proxy] = time.time() + seconds

    # ── Validation (for testing proxies) ──

    async def validate(
        self,
        timeout: float = 15.0,
        concurrency: int = 200,
        sample: int | None = None,
    ) -> tuple[int, int]:
        """Test proxies concurrently. Returns (working, total).

        - *timeout* per-proxy (default 15 s).
        - *concurrency* limits parallel tests via semaphore.
        - *sample*: number of proxies to test (None → all).
        """

        async def _test_one(proxy_raw: str | None) -> bool:
            proxy = self._format(proxy_raw) if proxy_raw else None
            # Skip obviously malformed URLs before aiohttp prints warnings
            if proxy and not _VALID_PROXY.match(proxy):
                return False
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    trust_env=False,
                ) as sess:
                    async with sess.post(
                        ENDPOINT,
                        json={"username": "a"},
                        proxy=proxy,
                        headers={"Content-Type": "application/json"},
                    ) as resp:
                        return resp.status in (200, 201, 204)
            except Exception:
                return False

        sem = asyncio.Semaphore(concurrency)

        async def _test_with_limit(p: str) -> bool:
            async with sem:
                return await _test_one(p)

        pool = self._proxies[:]
        if sample is not None:
            pool = random.sample(pool, min(sample, len(pool)))

        tasks = [_test_with_limit(p) for p in pool]
        results = await asyncio.gather(*tasks)
        return sum(results), len(pool)

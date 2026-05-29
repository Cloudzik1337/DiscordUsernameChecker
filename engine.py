#!/usr/bin/env python3
"""CloudChecker v3.1 – Checker engine, circuit breaker, error aggregation, webhook."""

from __future__ import annotations

import asyncio
import sys
import time

import aiohttp

from proxy import ProxyManager

# ---------------------------------------------------------------------------
# Debug control
# ---------------------------------------------------------------------------

_debug: bool = False


def set_debug(enabled: bool) -> None:
    global _debug
    _debug = enabled


def dbg(*args, **kwargs) -> None:
    """Debug print – only when --debug is active."""
    if _debug:
        print(*args, file=sys.stderr, flush=True, **kwargs)


# ---------------------------------------------------------------------------
# Circuit breaker – prevents thundering herd on rotating proxy
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Shared across all workers using a single rotating proxy.

    When too many connection failures happen in a short window,
    the circuit opens and all workers pause briefly before retrying.
    This prevents hammering a struggling gateway while still ensuring
    every username eventually gets checked.
    """

    def __init__(
        self,
        threshold: int = 8,
        window: float = 2.0,
        cooldown: float = 2.0,
        on_open = None,
    ) -> None:
        self.threshold = threshold
        self.window = window
        self.cooldown = cooldown
        self._failures: list[float] = []
        self._lock = asyncio.Lock()
        self._open_until: float = 0.0
        self._on_open = on_open  # async callback when circuit opens

    async def record_failure(self) -> None:
        """Record a failure and open the circuit if threshold crossed."""
        async with self._lock:
            now = time.time()
            self._failures.append(now)
            # Purge old failures
            self._failures = [t for t in self._failures if now - t < self.window]
            if len(self._failures) >= self.threshold:
                self._open_until = now + self.cooldown
                if self._on_open:
                    # fire-and-forget (don't await inside lock)
                    import asyncio as _asyncio
                    _asyncio.ensure_future(self._on_open())

    async def wait_if_open(self) -> None:
        """Block until the circuit closes."""
        now = time.time()
        if now < self._open_until:
            wait = self._open_until - now
            dbg(f"[cb] circuit open, waiting {wait:.1f}s")
            await asyncio.sleep(wait)


# ---------------------------------------------------------------------------
# ErrorAggregator – batch error counting
# ---------------------------------------------------------------------------

class ErrorAggregator:
    """Aggregates error counts instead of spamming logs."""

    def __init__(
        self,
        flush_interval: float = 30.0,
        flush_count: int = 500,
    ) -> None:
        self.flush_interval = flush_interval
        self.flush_count = flush_count
        self._lock = asyncio.Lock()
        self._counters: dict[str, int] = {}
        self._last_flush = time.time()

    async def inc(self, category: str) -> None:
        async with self._lock:
            self._counters[category] = self._counters.get(category, 0) + 1
            total = sum(self._counters.values())
            if total >= self.flush_count or (time.time() - self._last_flush) >= self.flush_interval:
                await self._flush_locked()

    async def flush(self) -> None:
        async with self._lock:
            await self._flush_locked()

    async def _flush_locked(self) -> None:
        self._counters.clear()
        self._last_flush = time.time()


# ---------------------------------------------------------------------------
# Checker – the core async checking loop
# ---------------------------------------------------------------------------

from config import ENDPOINT


class Checker:
    """Async username checker with keep-alive sessions and retry loop.

    Key behaviour:
    - Rotating proxy: retries until Discord gives a definitive answer.
      Connection errors get progressive backoff + circuit breaker.
      The only hard stop is Discord returning 200/201/204/400.
    - Static proxy list: cooldowns, 20 retries, 120 s total timeout.
    - Scraped free proxies: one shot per proxy, no retry.
    """

    MAX_RETRIES = 20                # hard cap for static list
    MAX_RETRIES_ROTATING = 100      # generous cap for rotating (should never hit)
    STATIC_TOTAL_TIMEOUT = 120.0    # total timeout for static list

    def __init__(
        self,
        proxy_manager: ProxyManager,
        timeout: int = 10,
        scraped: bool = False,
        circuit_breaker: CircuitBreaker | None = None,
        stats = None,
    ) -> None:
        self.pm = proxy_manager
        self.timeout = timeout
        self._err = ErrorAggregator()
        self._rotating = proxy_manager.is_single
        self._scraped = scraped
        self._cb = circuit_breaker
        self._stats = stats  # Stats object for live counters

        if scraped:
            self._max_retries = 1
        elif self._rotating:
            self._max_retries = self.MAX_RETRIES_ROTATING
        else:
            self._max_retries = self.MAX_RETRIES

    async def check(
        self,
        session: aiohttp.ClientSession,
        username: str,
    ) -> tuple[bool | str, dict | None, int | None]:
        """Check a single username.

        Returns:
            (True, data, code)  – available
            (False, data, code) – taken or invalid
            ("EXHAUSTED", None, None) – all proxies dead
            ("ERROR", None, None) – max retries exceeded
        """
        attempt = 0
        started = time.time()

        while True:
            proxy = await self.pm.next()
            if proxy is None and not self.pm.is_proxyless:
                return ("EXHAUSTED", None, None)

            attempt += 1
            if attempt > self._max_retries:
                return ("ERROR", None, None)

            # Total timeout — static proxy list only
            if not self._rotating and time.time() - started > self.STATIC_TOTAL_TIMEOUT:
                return ("ERROR", None, None)

            # Count every HTTP attempt (including 429 retries) for RPS
            if self._stats:
                await self._stats.inc_requests()

            try:
                # ── per-request timeout ──
                if self._scraped:
                    _timeout = aiohttp.ClientTimeout(total=5, sock_connect=5)
                elif self._rotating:
                    _timeout = aiohttp.ClientTimeout(
                        total=min(self.timeout, 5), sock_connect=5,
                    )
                else:
                    _timeout = aiohttp.ClientTimeout(
                        total=self.timeout, sock_connect=8,
                    )

                async with session.post(
                    ENDPOINT,
                    json={"username": username},
                    proxy=proxy,
                    headers={"Content-Type": "application/json"},
                    timeout=_timeout,
                ) as resp:
                    dbg(f"  [{attempt}] {username} → HTTP {resp.status}")

                    # ── 429 Rate Limited ──
                    if resp.status == 429:
                        try:
                            data = await resp.json()
                            cooldown = data.get("retry_after", 5)
                        except Exception:
                            cooldown = 5

                        if self._scraped:
                            if proxy:
                                self.pm.set_rate_limit(proxy, cooldown)
                            if self._stats:
                                await self._stats.inc_ratelimited()
                            continue

                        if self._rotating:
                            # Fresh IP on next request — no point waiting
                            if self._stats:
                                await self._stats.inc_ratelimited()
                            continue

                        if self._stats:
                            await self._stats.inc_ratelimited()
                        if proxy:
                            await self.pm.set_cooldown(proxy, cooldown)
                        else:
                            await self._err.inc("429_proxyless")
                            await asyncio.sleep(cooldown)
                        continue

                    # ── Success (taken/available) ──
                    if resp.status in (200, 201, 204):
                        try:
                            data = await resp.json()
                        except Exception:
                            data = {}
                        taken = data.get("taken", True)
                        if self._scraped and proxy:
                            self.pm.score_hit(proxy)
                        return (not taken, data, resp.status)

                    # ── Invalid username (Discord says so) ──
                    if resp.status == 400:
                        try:
                            data = await resp.json()
                        except Exception:
                            data = {}
                        return (False, data, resp.status)

                    # ── Unknown status – brief wait, retry ──
                    await self._err.inc(f"http_{resp.status}")
                    await asyncio.sleep(0.5)
                    continue

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                OSError,
            ) as exc:
                dbg(f"  [{attempt}] {username} → {type(exc).__name__}")

                # ── Scraped free proxies: one-shot ──
                if self._scraped:
                    if proxy:
                        self.pm.score_miss(proxy)
                    continue

                # ── Rotating proxy: progressive backoff + circuit breaker ──
                if self._rotating:
                    if self._cb:
                        await self._cb.record_failure()
                        await self._cb.wait_if_open()
                    # Per-worker progressive backoff
                    backoff = min(attempt * 0.25, 3.0)
                    await asyncio.sleep(backoff)
                    continue

                # ── Static proxy list: cooldown + backoff ──
                await self._err.inc("proxy_conn_err")
                await self.pm.set_cooldown(proxy, 3)
                backoff = min(attempt * 0.15, 5.0)
                await asyncio.sleep(backoff)
                continue

            except Exception as exc:
                dbg(f"  [{attempt}] {username} → {type(exc).__name__}: {exc!s:.100}")
                await asyncio.sleep(0.3)
                continue


# ---------------------------------------------------------------------------
# WebhookSender – async webhook dispatcher
# ---------------------------------------------------------------------------

from config import Stats


class WebhookSender:
    """Sends found usernames to Discord webhook in batches to avoid rate-limits.

    Discord webhook limit: 5 requests / 2 seconds, 2000 chars / message.
    Strategy: accumulate hits, flush batch every 3s or when 15 names / 1800 chars.
    """

    DISCORD_MAX_CHARS = 1950  # leave 50 char margin
    BATCH_SIZE = 15
    FLUSH_INTERVAL = 3.0  # seconds

    def __init__(
        self,
        webhook_url: str,
        message_template: str,
        session: aiohttp.ClientSession,
        start_time: float = 0.0,
    ) -> None:
        self.url = webhook_url
        self.template = message_template
        self.session = session
        self.start_time = start_time
        self._sent: set[str] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._buffer: list[str] = []
        self._buffer_lock = asyncio.Lock()

    def enqueue(self, username: str) -> None:
        """Called by workers when a hit is found."""
        if username not in self._sent:
            self._sent.add(username)
            self._queue.put_nowait(username)

    async def run(self) -> None:
        """Background task: accumulate hits, flush in batches."""
        last_flush = time.time()

        while True:
            try:
                username = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Timeout – flush if buffer has items and enough time passed
                async with self._buffer_lock:
                    if self._buffer and time.time() - last_flush >= self.FLUSH_INTERVAL:
                        await self._flush_locked()
                        last_flush = time.time()
                continue

            async with self._buffer_lock:
                self._buffer.append(username)
                count = len(self._buffer)

                # Build preview to check message length
                hit_lines = [self.template.replace("<name>", n) for n in self._buffer]
                preview = "\n".join(hit_lines)

                should_flush = (
                    count >= self.BATCH_SIZE
                    or len(preview) >= self.DISCORD_MAX_CHARS
                    or (count > 0 and time.time() - last_flush >= self.FLUSH_INTERVAL)
                )

                if should_flush:
                    await self._flush_locked()
                    last_flush = time.time()

    async def _flush_locked(self) -> None:
        """Send buffered hits. Must be called with _buffer_lock held."""
        if not self._buffer:
            return

        names = list(self._buffer)
        self._buffer.clear()

        # Build message – resolve placeholders, truncate at newline boundary
        now = time.time()
        elapsed = int(now - self.start_time)
        ts_discord = f"<t:{int(now)}:R>"

        def _fill(n: str) -> str:
            return (
                self.template
                .replace("<name>", n)
                .replace("<t:time:R>", ts_discord)
                .replace("<time>", ts_discord)
                .replace("<elapsed>", str(elapsed))
            )

        lines = [_fill(n) for n in names]
        msg = "\n".join(lines)
        if len(msg) > self.DISCORD_MAX_CHARS:
            # Truncate at last complete line to avoid cutting a name mid-word
            safe = msg[: self.DISCORD_MAX_CHARS - 3]
            last_nl = safe.rfind("\n")
            if last_nl > 0:
                msg = safe[:last_nl] + "\n..."
            else:
                msg = safe + "..."

        payload = {
            "content": msg,
            "username": "CloudChecker",
            "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Burning_Yellow_Sunset.jpg/1280px-Burning_Yellow_Sunset.jpg",
        }

        # Send with retry on 429
        for attempt in range(3):
            try:
                async with self.session.post(self.url, json=payload) as resp:
                    if resp.status == 429:
                        try:
                            data = await resp.json()
                            wait = data.get("retry_after", 5)
                        except Exception:
                            wait = 5
                        await asyncio.sleep(wait)
                        continue
                    if resp.status in (200, 204):
                        return
                    # Other error – give up
                    return
            except Exception:
                await asyncio.sleep(1)

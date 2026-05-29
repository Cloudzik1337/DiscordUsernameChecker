#!/usr/bin/env python3
"""CloudChecker v3.1 – Configuration, constants, helpers, and data models."""

from __future__ import annotations

import json
import string
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths – resolved relative to project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
RESULTS_DIR = PROJECT_ROOT / "results"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "3.1.0"
ENDPOINT = "https://discord.com/api/v9/unique-username/username-attempt-unauthed"
USERNAME_CHARS = string.ascii_lowercase + string.digits + "_" + "."
MAX_CONCURRENCY = 2000  # hard cap — beyond this asyncio/aiohttp stalls


# ---------------------------------------------------------------------------
# Colour palette (Rich hex codes)
# ---------------------------------------------------------------------------

class C:
    """Semantic colour constants – vibrant terminal-optimized palette."""
    PRIMARY   = "#0A84FF"   # bright blue – headers, accents, borders
    SUCCESS   = "#30D158"   # bright green – available, hits
    DANGER    = "#FF453A"   # bright red – taken, errors
    WARNING   = "#FF9F0A"   # bright orange – warnings, rate-limits
    MUTED     = "#98989D"   # light gray – secondary text
    BORDER    = "#48484A"   # subtle border – cards


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dir(*paths: str | Path) -> None:
    """Create directories if they don't exist."""
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def ensure_file(filepath: str | Path, *, clean: bool = False) -> None:
    """Create a file (and its parents). If *clean*, truncate it."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    if clean or not path.exists():
        path.write_text("", encoding="utf-8")


def load_lines(filepath: str | Path) -> list[str]:
    """Read non-empty lines from a file. Returns [] if missing."""
    path = Path(filepath)
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_valid_username(name: str) -> bool:
    """Check whether a username passes Discord's basic client-side rules.

    - 2–32 characters
    - only a–z, 0–9, '_', '.'
    - no consecutive dots ('..')
    - cannot start or end with a dot
    """
    if not (2 <= len(name) <= 32):
        return False
    if ".." in name:
        return False
    if name.startswith(".") or name.endswith("."):
        return False
    return all(c in USERNAME_CHARS for c in name)


# ---------------------------------------------------------------------------
# Persistent JSON config
# ---------------------------------------------------------------------------

class Config:
    """JSON-backed persistent config with in-memory caching."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else DATA_DIR / "config.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists() and self._path.stat().st_size > 0:
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._path.write_text("{}", encoding="utf-8")

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._path.write_text(
            json.dumps(self._data, indent=2), encoding="utf-8"
        )

    def get_all(self) -> dict:
        return dict(self._data)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AppSettings:
    """Application-level settings (from CLI args)."""
    debug: bool = False
    verbose: bool = False
    no_wizard: bool = False


@dataclass
class RunConfig:
    """All user choices gathered during setup."""
    proxies: list[str]
    remove_bad_proxies: bool
    usernames: list[str]
    concurrency: int
    timeout: int
    scraped: bool = False
    webhook_url: str | None = None
    webhook_message: str | None = None


@dataclass
class Stats:
    """Thread-safe stats counter."""
    requests: int = 0
    works: int = 0
    taken: int = 0
    ratelimited: int = 0
    circuit_opens: int = 0
    rps: float = 0.0
    checks_rps: float = 0.0
    peak_rps: float = 0.0
    best_streak: int = 0
    _streak: int = 0
    _lock: field(default_factory=lambda: __import__("asyncio").Lock) = field(default=None, init=False, repr=False)  # type: ignore

    def __post_init__(self) -> None:
        import asyncio
        self._lock = asyncio.Lock()

    async def inc_requests(self) -> None:
        async with self._lock:
            self.requests += 1

    async def inc_works(self) -> None:
        async with self._lock:
            self.works += 1
            self._streak += 1
            if self._streak > self.best_streak:
                self.best_streak = self._streak

    async def inc_taken(self) -> None:
        async with self._lock:
            self.taken += 1
            self._streak = 0

    async def inc_ratelimited(self) -> None:
        async with self._lock:
            self.ratelimited += 1

    async def inc_circuit_open(self) -> None:
        async with self._lock:
            self.circuit_opens += 1

    async def set_rps(self, value: float) -> None:
        async with self._lock:
            self.rps = value
            if value > self.peak_rps:
                self.peak_rps = value

    async def set_checks_rps(self, value: float) -> None:
        async with self._lock:
            self.checks_rps = value

    async def snapshot(self) -> dict:
        async with self._lock:
            return {
                "requests": self.requests,
                "works": self.works,
                "taken": self.taken,
                "ratelimited": self.ratelimited,
                "circuit_opens": self.circuit_opens,
                "rps": self.rps,
                "checks_rps": self.checks_rps,
                "peak_rps": self.peak_rps,
                "best_streak": self.best_streak,
            }

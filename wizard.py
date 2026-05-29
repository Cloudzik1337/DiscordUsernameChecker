#!/usr/bin/env python3
"""CloudChecker v3.1 – Setup wizard and proxy scraper."""

from __future__ import annotations

import asyncio
import itertools
import random
import re
import sys
from pathlib import Path

import aiohttp
from rich.prompt import Confirm, IntPrompt, Prompt

from config import (
    DATA_DIR,
    MAX_CONCURRENCY,
    PROJECT_ROOT,
    USERNAME_CHARS,
    AppSettings,
    Config,
    RunConfig,
    ensure_dir,
    ensure_file,
    is_valid_username,
    load_lines,
)
from ui import (
    C,
    banner,
    card,
    config_summary,
    console,
    fail,
    info,
    info_card,
    ok,
    progress_steps,
    section,
    warn_card,
)

# Default file paths (absolute, under DATA_DIR)
DEFAULT_PROXY_FILE = str(DATA_DIR / "proxies.txt")
DEFAULT_NAMES_FILE = str(DATA_DIR / "names_to_check.txt")

# Clean display versions (shown in prompts, not full absolute paths)
_PROXY_FILE_DISPLAY = "data/proxies.txt"
_NAMES_FILE_DISPLAY = "data/names_to_check.txt"


def _resolve_input_path(raw: str) -> str:
    """Resolve user input to an absolute path.

    If *raw* is relative it is resolved against PROJECT_ROOT so the
    script works regardless of the current working directory.
    """
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)

# Regex: matches host:port with optional http:// and optional user:pass@
#   "1.2.3.4:8080"                                 ✓
#   "http://1.2.3.4:8080"                           ✓
#   "user:pass@1.2.3.4:8080"                         ✓
#   "http://user:pass@1.2.3.4:8080"                  ✓
#   "domain.com:8080"                                ✓
#   '"ip":"1.2.3.4"' (JSON cruft from geonode)       ✗
_PROXY_RE = re.compile(
    r"^(?:https?://)?(?:[^@\s]+@)?[a-zA-Z0-9](?:[a-zA-Z0-9\-.]*[a-zA-Z0-9])?:\d{1,5}$"
)


# ---------------------------------------------------------------------------
# Setup wizard – main entry
# ---------------------------------------------------------------------------

async def setup_wizard(config: Config, settings: AppSettings) -> RunConfig:
    """Walk the user through a clean 4-step setup."""

    console.clear()
    console.print(banner())
    console.print()
    console.print(progress_steps(0))

    # ── Step 1: Proxies ──
    warn_card(
        f"[{C.WARNING}]Proxies strongly recommended[/]",
        f"[{C.MUTED}]Without them Discord will rate-limit you.[/]",
        f"[{C.MUTED}]Format: login:pass@host:port[/]",
    )
    proxies, remove_bad, scraped = await _step_proxies(config)

    # ── Step 2: Usernames ──
    console.print()
    console.print(progress_steps(1))
    usernames = _step_usernames()

    # ── Step 3: Speed ──
    console.print()
    console.print(progress_steps(2))
    concurrency, timeout = _step_speed(proxies, scraped)

    # ── Step 4: Webhook ──
    console.print()
    console.print(progress_steps(3))
    webhook_url, webhook_msg = _step_webhook(config)

    config.set("timeout", timeout)
    config.set("concurrency", concurrency)
    config.set("remove_proxies", remove_bad)

    # ── Summary ──
    config_summary(
        proxy_count=len(proxies),
        scraped=scraped,
        remove_bad=remove_bad,
        username_count=len(usernames),
        concurrency=concurrency,
        timeout=timeout,
        webhook=bool(webhook_url),
    )

    if not Confirm.ask(f"\n[{C.PRIMARY}]Start checking?[/]", default=True):
        console.print(f"[{C.MUTED}]Aborted.[/]")
        sys.exit(0)

    return RunConfig(
        proxies=proxies,
        remove_bad_proxies=remove_bad,
        usernames=usernames,
        concurrency=concurrency,
        timeout=timeout,
        scraped=scraped,
        webhook_url=webhook_url,
        webhook_message=webhook_msg,
    )


# ---------------------------------------------------------------------------
# Step 1: Proxies
# ---------------------------------------------------------------------------

async def _step_proxies(config: Config) -> tuple[list[str], bool, bool]:
    """Guide user through proxy setup. Returns (proxies, remove_bad, scraped)."""
    proxies: list[str] = []
    remove_bad = False
    scraped = False

    # Check for proxies from last session
    existing = load_lines(DEFAULT_PROXY_FILE)
    reuse_cfg = config.get("reuse_proxies")  # None=ask, True=auto, False=skip

    if existing and reuse_cfg is None:
        console.print()
        info_card(f"Found {len(existing)} proxies from last session.")
        if Confirm.ask("Reuse them?", default=False):
            proxies = existing
            ok(f"Reusing {len(proxies)} proxies")
            if Confirm.ask("Always reuse without asking?", default=False):
                config.set("reuse_proxies", True)
        else:
            if Confirm.ask("Always skip and ask for new ones?", default=False):
                config.set("reuse_proxies", False)
    elif existing and reuse_cfg:
        proxies = existing
        ok(f"Auto-reusing {len(proxies)} proxies")

    if not proxies:
        # Present all proxy sources as first-class options
        console.print()
        mode = Prompt.ask(
            f"[{C.PRIMARY}]Proxy source:[/] (f)ile  (p)aste  (s)crape  (n)one",
            choices=["f", "p", "s", "n"],
            default="f",
        )

        if mode == "f":
            proxy_path = Prompt.ask("Path to proxy file", default=_PROXY_FILE_DISPLAY)
            proxies = load_lines(_resolve_input_path(proxy_path))
            if not proxies:
                fail("No proxies found in that file.")
        elif mode == "p":
            console.print(f"\n[{C.PRIMARY}]Paste your proxies[/] [dim](one per line, empty line to finish)[/]")
            console.print(f"[{C.MUTED}]Format: login:pass@host:port[/]")
            lines_pasted = []
            while True:
                line = Prompt.ask("", default="")
                if not line.strip():
                    break
                lines_pasted.append(line.strip())
            if lines_pasted:
                ensure_file(DEFAULT_PROXY_FILE)
                Path(DEFAULT_PROXY_FILE).write_text("\n".join(lines_pasted), encoding="utf-8")
                proxies = lines_pasted
            else:
                fail("No proxies provided.")
        elif mode == "s":
            console.print()
            scraped_proxies = await _scrape_proxies()
            if scraped_proxies:
                proxies = scraped_proxies
                scraped = True
        # mode "n" -> proxies stays empty (proxyless)

    if proxies:
        tag = f" [{C.MUTED}](free)[/]" if scraped else ""
        ok(f"{len(proxies)} proxies loaded{tag}")

        # Always ask about removing dead proxies (scraped or file)
        if len(proxies) > 1:
            remove_bad = Confirm.ask(
                "Auto-remove dead proxies?", default=True
            )
    else:
        warn_card(
            f"[{C.WARNING}]Running proxyless — expect heavy rate-limiting.[/]",
            f"[{C.MUTED}]Tip: close your Discord client to free up requests.[/]",
        )

    return proxies, remove_bad, scraped



# ---------------------------------------------------------------------------
# Step 2: Usernames
# ---------------------------------------------------------------------------


def _step_usernames() -> list[str]:
    """Guide user through username list setup."""
    raw = Prompt.ask(
        f"[{C.PRIMARY}](f)ile[/] or [{C.PRIMARY}](g)enerate[/] usernames?",
        choices=["f", "g"],
        default="f",
    )
    mode = "generate" if raw == "g" else "file"
    usernames: list[str] = []

    if mode == "file":
        names_path = Prompt.ask("Path to username file", default=_NAMES_FILE_DISPLAY)
        usernames = load_lines(_resolve_input_path(names_path))
        if not usernames:
            fail("File is empty — switching to generate mode.")
            mode = "generate"
        else:
            ok(f"Loaded {len(usernames)} usernames")

    if mode == "generate":
        length = IntPrompt.ask("Username length", default=4, choices=["2", "3", "4", "5"])
        total = len(USERNAME_CHARS) ** length

        if length >= 5:
            # Too many combos for itertools.product (79M for 5 chars)
            ok(f"Generating 50000 random {length}-char usernames (of {total:,} possible)...")
            seen: set[str] = set()
            usernames = []
            while len(usernames) < 50000:
                cand = "".join(random.choices(USERNAME_CHARS, k=length))
                if cand not in seen and is_valid_username(cand):
                    seen.add(cand)
                    usernames.append(cand)
        else:
            combos = ["".join(c) for c in itertools.product(USERNAME_CHARS, repeat=length)]
            usernames = [c for c in combos if is_valid_username(c)]
            usernames = random.sample(usernames, min(50000, len(usernames)))

        ensure_file(DEFAULT_NAMES_FILE)
        Path(DEFAULT_NAMES_FILE).write_text("\n".join(usernames), encoding="utf-8")
        ok(f"Generated {len(usernames)} usernames (of {total:,} possible)")

    return usernames


# ---------------------------------------------------------------------------
# Step 3: Speed
# ---------------------------------------------------------------------------

def _step_speed(proxies: list[str], scraped: bool = False) -> tuple[int, int]:
    """Guide user through concurrency and timeout settings."""
    if not proxies:
        info("Proxyless mode — 1 worker with delay.")
        delay = IntPrompt.ask("Delay between requests (seconds)", default=5)
        return 1, delay

    if scraped:
        info("Free proxy mode — high concurrency, short timeout.")
        conc = IntPrompt.ask("Concurrent workers", default=50)
        if conc > MAX_CONCURRENCY:
            warn_card(f"Capped at {MAX_CONCURRENCY} — beyond this the program freezes.")
            conc = MAX_CONCURRENCY
        timeout = IntPrompt.ask("Request timeout (seconds)", default=5)
        return conc, timeout

    default_conc = min(MAX_CONCURRENCY, max(10, len(proxies) * 5))
    concurrency = IntPrompt.ask("Concurrent workers", default=default_conc)
    if concurrency > MAX_CONCURRENCY:
        warn_card(f"Capped at {MAX_CONCURRENCY} — beyond this the program freezes.")
        concurrency = MAX_CONCURRENCY
    timeout = IntPrompt.ask("Request timeout (seconds)", default=10)
    return concurrency, timeout


# ---------------------------------------------------------------------------
# Step 4: Webhook
# ---------------------------------------------------------------------------

def _step_webhook(config: Config) -> tuple[str | None, str | None]:
    """Guide user through optional webhook setup."""

    # Already saved and set to always use
    saved_url = config.get("webhook")
    saved_msg = config.get("webhook_message", "**<name>** available | <t:time:R>")
    always = config.get("webhook_always", False)

    if always and saved_url:
        ok(f"Using saved webhook")
        return saved_url, saved_msg

    # Ask if they want webhook
    if saved_url and not always:
        if not Confirm.ask(
            f"Use webhook? [dim](saved from last session)[/]", default=True
        ):
            if Confirm.ask("Forget saved webhook?", default=False):
                config.set("webhook", "")
                config.set("webhook_message", "")
            return None, None
        webhook_url = saved_url
        webhook_msg = config.get("webhook_message", "**<name>** available | <t:time:R>")
    else:
        if not Confirm.ask("Send hits to a Discord webhook?", default=False):
            return None, None

        webhook_url = Prompt.ask("Webhook URL")
        if not webhook_url.strip():
            info("Empty URL — webhook disabled.")
            return None, None

        console.print(f"[{C.MUTED}]Hits are sent in batches to avoid rate-limits.[/]")
        webhook_msg = Prompt.ask(
            "Message template per hit [dim](<name> <time> <elapsed>)[/]",
            default="**<name>** available | <t:time:R>",
        )

    # Save & always-use
    config.set("webhook", webhook_url)
    config.set("webhook_message", webhook_msg)

    if not always:
        if Confirm.ask("Always use this webhook? (skip asking next time)", default=True):
            config.set("webhook_always", True)

    return webhook_url, webhook_msg


# ---------------------------------------------------------------------------
# Proxy scraper
# ---------------------------------------------------------------------------

async def _scrape_proxies() -> list[str]:
    """Fetch free HTTP proxies from multiple sources, deduplicate."""

    SOURCES = [
        ("TheSpeedX",           "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
        ("monosans",            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"),
        ("proxifly",            "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt"),
        ("ShiftyTR-http",       "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
        ("ShiftyTR-https",      "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt"),
        ("roosterkid",          "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"),
        ("sunny9577",           "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt"),
        ("rdavydov",            "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt"),
        ("Anonym0usWork12",     "https://raw.githubusercontent.com/Anonym0usWork12/Proxy-List/master/http.txt"),
        ("officialputuid",      "https://raw.githubusercontent.com/officialputuid/rules/master/proxies.txt"),
        ("mmpx12-http",         "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt"),
        ("mmpx12-https",        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt"),
        ("iplocate-http",       "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt"),
        ("iplocate-https",      "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt"),
        ("openproxylist.xyz",   "https://api.openproxylist.xyz/http.txt"),
        ("proxyscrape.com",     "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"),
        ("geonode.com",         "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps"),
    ]

    console.print(f"[{C.MUTED}]Scraping {len(SOURCES)} sources...[/]")

    async def _fetch_one(name: str, url: str) -> list[str]:
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                trust_env=False,
            ) as sess:
                async with sess.get(url) as resp:
                    if resp.status != 200:
                        console.print(f"  [{C.DANGER}]✗[/] {name} HTTP {resp.status}")
                        return []
                    text = await resp.text()
                    found = [p.strip() for p in text.splitlines()
                             if _PROXY_RE.match(p.strip())]
                    console.print(f"  [{C.SUCCESS}]✓[/] {name} {len(found)} proxies")
                    return found
        except Exception as e:
            console.print(f"  [{C.DANGER}]✗[/] {name} {e}")
            return []

    tasks = [_fetch_one(name, url) for name, url in SOURCES]
    results = await asyncio.gather(*tasks)

    seen: set[str] = set()
    all_proxies: list[str] = []
    for batch in results:
        for p in batch:
            key = p.split("@")[-1] if "@" in p else p
            if key not in seen:
                seen.add(key)
                all_proxies.append(p)

    if not all_proxies:
        fail("All sources failed — no proxies.")
        return []

    ok(f"{len(all_proxies)} unique proxies [{C.MUTED}](~2-5% usually work)[/]")
    return all_proxies

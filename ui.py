#!/usr/bin/env python3
"""CloudChecker v3.1 – terminal UI."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from config import C, VERSION


console = Console()

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def banner() -> Panel:
    """Banner."""
    inner = Text()
    inner.append("CloudChecker", style=f"bold {C.PRIMARY}")
    inner.append(f"  v{VERSION}", style=f"{C.MUTED}")
    return Panel(
        inner,
        box=box.ROUNDED,
        border_style=C.BORDER,
        padding=(1, 4),
    )


# ---------------------------------------------------------------------------
# Progress indicator
# ---------------------------------------------------------------------------

def progress_steps(current: int, total: int = 4) -> str:
    """Render a step progress indicator: ● Proxies  ○ Usernames  ○ Speed  ○ Webhook"""
    steps = ["Proxies", "Usernames", "Speed", "Webhook"]
    parts: list[str] = []
    for i, label in enumerate(steps):
        if i < current:
            parts.append(f"[{C.SUCCESS}]✓[/] {label}")
        elif i == current:
            parts.append(f"[{C.PRIMARY}]●[/] {label}")
        else:
            parts.append(f"[{C.MUTED}]○[/] {label}")
    return "  ".join(parts)


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a clean section header."""
    console.print()
    console.print(Text(title, style=f"bold {C.PRIMARY}"))
    console.print("─" * 40, style=C.MUTED)


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

def card(title: str | None, *lines: str, border: str = C.PRIMARY) -> None:
    """Print a rounded-card panel."""
    body = "\n".join(lines) if lines else ""
    console.print(Panel(
        body,
        title=title,
        title_align="left",
        box=box.ROUNDED,
        border_style=border,
        padding=(1, 2),
    ))


def info_card(*lines: str) -> None:
    """Print an informational card (muted border)."""
    card(None, *lines, border=C.MUTED)


def warn_card(*lines: str) -> None:
    """Print a warning card."""
    card(None, *lines, border=C.WARNING)


# ---------------------------------------------------------------------------
# Summary table (config)
# ---------------------------------------------------------------------------

def config_summary(
    proxy_count: int,
    scraped: bool,
    remove_bad: bool,
    username_count: int,
    concurrency: int,
    timeout: int,
    webhook: bool,
) -> None:
    """Print a clean configuration summary."""
    console.print()
    t = Table(box=box.ROUNDED, border_style=C.BORDER, show_header=False, padding=(0, 2))
    t.add_column(style=C.MUTED, width=16)
    t.add_column(style="white")

    tag = f" [{C.MUTED}](free)[/]" if scraped else ""
    t.add_row("Proxies", f"[{C.PRIMARY}]{proxy_count}[/] loaded{tag}")
    if proxy_count > 1 and not scraped:
        t.add_row("Auto-remove", "Yes" if remove_bad else "No")
    t.add_row("Usernames", str(username_count))
    t.add_row("Workers", str(concurrency))
    t.add_row("Timeout", f"{timeout}s")
    t.add_row("Webhook", f"[{C.SUCCESS}]on[/]" if webhook else f"[{C.MUTED}]off[/]")
    console.print(Panel(t, title="Summary", title_align="left", box=box.ROUNDED, border_style=C.PRIMARY))


# ---------------------------------------------------------------------------
# Live checker card builder
# ---------------------------------------------------------------------------

def live_card(
    done: int,
    total: int,
    works: int,
    taken: int,
    requests: int,
    ratelimited: int,
    circuit_opens: int,
    rps: float,
    elapsed: float,
    proxy_alive: int,
    checks_rps: float = 0.0,
    paused: bool = False,
    recent: list[str] | None = None,
    feed: list[str] | None = None,
) -> Panel:
    """Build the live display panel for the checker runner."""

    pct = done / max(total, 1) * 100

    inner = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    inner.add_column(style=C.MUTED, width=14, no_wrap=True)
    inner.add_column(style="white")
    inner.add_column(style=C.MUTED, width=14, no_wrap=True)
    inner.add_column(style="white")

    inner.add_row(
        "Available", f"[{C.SUCCESS}]{works}[/]",
        "Taken", f"[{C.DANGER}]{taken}[/]",
    )
    inner.add_row(
        "Req/s", f"[{C.PRIMARY}]{rps:.0f}[/]",
        "Requests", str(requests),
    )

    # Rate-limited row
    if ratelimited > 0:
        inner.add_row(
            f"[{C.WARNING}]Rate limited[/]", f"[{C.WARNING}]{ratelimited}[/]",
            "Elapsed", f"{elapsed:.0f}s",
        )
    else:
        inner.add_row(
            "Progress", f"{done}/{total} ({pct:.0f}%)",
            "Elapsed", f"{elapsed:.0f}s",
        )

    # Circuit breaker / paused
    if circuit_opens > 0 or paused:
        inner.add_row(
            f"[{C.WARNING}]Circuit breaks[/]", f"[{C.WARNING}]{circuit_opens}[/]",
            "Proxies", f"{proxy_alive} alive",
        )
    else:
        inner.add_row(
            "Proxies", f"{proxy_alive} alive",
            "Workers", "active",
        )

    content = Table(box=None, show_header=False, padding=(0, 0), expand=True)
    content.add_row(inner)

    # Status banner for heavy rate-limiting
    if ratelimited > 0 and (done == 0 or ratelimited > done * 2):
        content.add_section()
        content.add_row(Text(
            f"⚠ Discord is rate-limiting — {ratelimited} requests blocked. Workers are alive, just waiting.",
            style=C.WARNING,
        ))

    if paused:
        content.add_section()
        content.add_row(Text(
            f"⏸ Circuit breaker active — all workers paused briefly to protect the proxy.",
            style=C.WARNING,
        ))

    # Recent hits
    if recent:
        content.add_section()
        recent_str = "  ".join(f"[{C.SUCCESS}]{n}[/]" for n in recent[-6:])
        content.add_row(Text("Recent  ", style=C.MUTED) + Text.from_markup(recent_str))

    # Live feed (only last 8 entries)
    if feed:
        content.add_section()
        feed_str = "  ".join(feed[-8:])
        content.add_row(Text.from_markup(feed_str))

    status = f"⌛ rate-limited" if (ratelimited > 0 and done == 0) else f"{done}/{total} ({pct:.0f}%)"
    return Panel(
        content,
        title=f"[{C.PRIMARY}]CloudChecker[/] · {status} · [dim]{elapsed:.0f}s[/]",
        title_align="left",
        box=box.ROUNDED,
        border_style=C.BORDER if not paused else C.WARNING,
        padding=(1, 2),
    )


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------

def final_summary(
    requests: int,
    works: int,
    taken: int,
    ratelimited: int,
    circuit_opens: int,
    elapsed: float,
    peak_rps: float = 0.0,
    best_streak: int = 0,
) -> None:
    """Print the final results card."""
    console.print()

    avg_rps = requests / max(elapsed, 0.1)

    t = Table(box=box.ROUNDED, border_style=C.BORDER, show_header=False, padding=(0, 2))
    t.add_column(style=C.MUTED, width=16)
    t.add_column(style="white")
    t.add_row("Available", f"[{C.SUCCESS} bold]{works}[/]")
    t.add_row("Taken", f"[{C.DANGER} bold]{taken}[/]")
    t.add_row("Requests", str(requests))
    if ratelimited > 0:
        t.add_row("Rate limited", f"[{C.WARNING}]{ratelimited}[/]")
    if circuit_opens > 0:
        t.add_row("Circuit breaks", str(circuit_opens))
    t.add_row("Elapsed", f"{elapsed:.0f}s")
    t.add_row("Avg req/s", f"{avg_rps:.1f}")
    if peak_rps > 0:
        t.add_row("Peak req/s", f"[{C.PRIMARY}]{peak_rps:.0f}[/]")
    if best_streak > 1:
        t.add_row("Best streak", f"[{C.SUCCESS}]{best_streak}[/] hits")
    if works > 0:
        t.add_row("Saved to", "results/hits.txt")

    console.print(Panel(
        t,
        title=f"[{C.SUCCESS}]Done[/] · {elapsed:.0f}s",
        title_align="left",
        box=box.ROUNDED,
        border_style=C.SUCCESS,
    ))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def ok(msg: str) -> None:
    console.print(f"  [{C.SUCCESS}]✓[/] {msg}")

def fail(msg: str) -> None:
    console.print(f"  [{C.DANGER}]✗[/] {msg}")

def info(msg: str) -> None:
    console.print(f"  [{C.MUTED}]ℹ[/] {msg}")

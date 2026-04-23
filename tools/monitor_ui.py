#!/usr/bin/env python3
from __future__ import annotations

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GRAY = "\033[90m"


def style(enabled: bool, text: str, *codes: str) -> str:
    if not enabled or not codes:
        return text
    return "".join(codes) + text + RESET


def progress_bar(done: int, total: int, *, width: int = 24, color: bool = False, bar_color: str = CYAN) -> str:
    if total <= 0:
        return style(color, "[" + ("·" * width) + "]", DIM)
    frac = max(0.0, min(1.0, done / total))
    filled = int(frac * width)
    cells = [("█" if idx < filled else "·") for idx in range(width)]
    return style(color, "[" + "".join(cells) + "]", bar_color)


def human_duration(seconds: float | None, *, include_days: bool = True) -> str:
    if seconds is None or seconds < 0:
        return "unknown"
    sec = int(round(seconds))
    days, sec = divmod(sec, 86400)
    hours, sec = divmod(sec, 3600)
    mins, sec = divmod(sec, 60)
    parts: list[str] = []
    if include_days and days:
        parts.append(f"{days}d")
    elif days:
        hours += days * 24
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if sec or not parts:
        parts.append(f"{sec}s")
    return " ".join(parts[:3])


def shorten(text: str, limit: int = 120) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."

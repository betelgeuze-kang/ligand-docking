#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ORIGINAL_XDG_OPEN = "/usr/bin/xdg-open"


def normalized_target(raw: str) -> str:
    if not raw:
        return raw
    parts = urlsplit(raw)
    if parts.scheme and parts.scheme != "file":
        return raw
    if parts.scheme == "file":
        if parts.query or parts.fragment:
            return raw
        if parts.netloc not in {"", "localhost"}:
            return raw
        decoded_path = unquote(parts.path)
        if decoded_path and Path(decoded_path).exists():
            return decoded_path
        return raw
    if "://" in raw or "%" not in raw:
        return raw
    decoded = unquote(raw)
    if decoded != raw and Path(decoded).exists():
        return decoded
    return raw


def main(argv: list[str]) -> int:
    args = argv[1:]
    if len(args) != 1 or (args and args[0].startswith("-")):
        os.execv(ORIGINAL_XDG_OPEN, [ORIGINAL_XDG_OPEN, *args])
    normalized = normalized_target(args[0])
    if os.environ.get("XDG_OPEN_WRAPPER_PRINT_ONLY") == "1":
        print(normalized)
        return 0
    os.execv(ORIGINAL_XDG_OPEN, [ORIGINAL_XDG_OPEN, normalized])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

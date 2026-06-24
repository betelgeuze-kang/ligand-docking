from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path_like: str | Path, data: bytes, *, mode: int = 0o600) -> Path:
    """Atomically replace a file using a same-directory temporary file.

    The write is flushed before ``os.replace`` and the parent directory is
    synced afterwards. This avoids exposing partial JSON, status, or encrypted
    payload files after process interruption.
    """

    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    temp_path = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    fd: int | None = None
    try:
        fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        try:
            os.chmod(path, mode)
        except OSError:
            pass
        _fsync_directory(path.parent)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return path


def atomic_write_text(
    path_like: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
) -> Path:
    return atomic_write_bytes(path_like, text.encode(encoding), mode=mode)


def atomic_write_json(
    path_like: str | Path,
    payload: Any,
    *,
    mode: int = 0o600,
    indent: int = 2,
    sort_keys: bool = True,
) -> Path:
    text = json.dumps(
        payload,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=False,
    ) + "\n"
    return atomic_write_text(path_like, text, mode=mode)

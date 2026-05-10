from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def artifact(path_like: str | Path) -> str:
    if str(path_like).strip() == "":
        return ""
    path = resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def text(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return text(value).lower() in {"1", "true", "t", "yes", "y"}


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return artifact(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    return value


def read_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary", {})
    return value if isinstance(value, dict) else {}


def short_error(exc: BaseException | str, limit: int = 900) -> str:
    message = str(exc) if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    return message if len(message) <= limit else message[: limit - 3] + "..."

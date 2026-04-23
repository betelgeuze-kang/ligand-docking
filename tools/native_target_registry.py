#!/usr/bin/env python3
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

_TARGET_ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "T. cruzi PDE": (
        "T. cruzi PDE",
        "t_cruzi_pde",
        "tcruzi_pde",
        "Trypanosoma cruzi PDE",
        "Trypanosoma cruzi phosphodiesterase",
        "TcrPDEC",
        "TcrPDEC1",
    ),
    "Cathepsin K": (
        "Cathepsin K",
        "cathepsin_k",
        "CTSK",
        "Human Cathepsin K",
    ),
    "SARS-CoV-2 Mpro": (
        "SARS-CoV-2 Mpro",
        "sars_cov_2_mpro",
        "sarscov2_mpro",
        "SARS-CoV-2 main protease",
        "SARS-CoV-2 3CLpro",
        "COVID-19 Mpro",
    ),
}


def normalize_target_key(text: Any) -> str:
    return "".join(ch.lower() for ch in str(text or "") if ch.isalnum())


def _normalize_alias_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_tokens = [str(item or "").strip() for item in value]
    else:
        raw_tokens = [
            token.strip()
            for token in str(value or "").replace("|", ";").replace(",", ";").split(";")
        ]
    tokens: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        if not token:
            continue
        key = normalize_target_key(token)
        if not key or key in seen:
            continue
        seen.add(key)
        tokens.append(token)
    return tokens


def canonicalize_target_name(text: Any) -> str:
    normalized = normalize_target_key(text)
    if not normalized:
        return str(text or "").strip()
    for canonical_name, aliases in _TARGET_ALIAS_GROUPS.items():
        if normalized in {normalize_target_key(alias) for alias in aliases}:
            return canonical_name
    return str(text or "").strip()


def candidate_target_keys(text: Any, *, extra_aliases: Any = None) -> list[str]:
    normalized = normalize_target_key(text)
    keys: list[str] = []
    seen: set[str] = set()

    def _push(value: Any) -> None:
        key = normalize_target_key(value)
        if not key or key in seen:
            return
        seen.add(key)
        keys.append(key)

    _push(text)
    canonical = canonicalize_target_name(text)
    _push(canonical)
    aliases = list(_TARGET_ALIAS_GROUPS.get(canonical, ()))
    aliases.extend(_normalize_alias_tokens(extra_aliases))
    for alias in aliases:
        _push(alias)
    return keys


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def read_target_native_rows(path_like: str) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row or {}) for row in csv.DictReader(handle)]


def find_matching_target_row(rows: list[dict[str, Any]], target_id: Any) -> dict[str, Any]:
    target_keys = set(candidate_target_keys(target_id))
    if not target_keys:
        return dict(rows[0] or {}) if rows else {}
    for row in rows:
        row_keys = set(
            candidate_target_keys(
                row.get("target"),
                extra_aliases=row.get("target_aliases"),
            )
        )
        if target_keys & row_keys:
            return dict(row or {})
    return dict(rows[0] or {}) if rows else {}


@lru_cache(maxsize=1)
def load_repo_native_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    config_dir = ROOT / "config"
    if not config_dir.exists():
        return registry
    for path in sorted(config_dir.glob("*.csv")):
        try:
            rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
        except Exception:
            continue
        for row in rows:
            target = str(row.get("target") or "").strip()
            native_path = str(row.get("native_pdb_path") or "").strip()
            if not target or not native_path:
                continue
            resolved_native = _resolve(native_path)
            ready = bool(resolved_native.exists() and resolved_native.is_file())
            entry = {
                "target": target,
                "canonical_target": canonicalize_target_name(target),
                "native_pdb_path": str(resolved_native) if ready else native_path,
                "native_pdb_ready": ready,
                "native_format": resolved_native.suffix.lstrip(".").lower()
                if ready
                else Path(native_path).suffix.lstrip(".").lower(),
                "pdb_id": str(row.get("pdb_id") or "").strip(),
                "notes": str(row.get("notes") or "").strip(),
                "source_csv": str(path.resolve()),
                "target_aliases": _normalize_alias_tokens(row.get("target_aliases")),
                "pocket_x": str(row.get("pocket_x") or "").strip(),
                "pocket_y": str(row.get("pocket_y") or "").strip(),
                "pocket_z": str(row.get("pocket_z") or "").strip(),
            }
            for key in candidate_target_keys(target, extra_aliases=row.get("target_aliases")):
                existing = registry.get(key)
                if existing is None:
                    registry[key] = dict(entry)
                    continue
                existing_ready = bool(existing.get("native_pdb_ready"))
                if ready and not existing_ready:
                    registry[key] = dict(entry)
    return registry


def resolve_repo_native_entry(target_id: Any) -> dict[str, Any]:
    registry = load_repo_native_registry()
    for key in candidate_target_keys(target_id):
        entry = registry.get(key)
        if entry:
            return dict(entry)
    return {}

"""Repo-wide guard: retired proxy-energy names stay out of the active surface (P0-5).

``deltaG_*_kcal_mol`` proxy names are retired. Reader-side compatibility is
allowed in exactly two places (the schema module that declares the aliases and
the physics module that reads historical artifacts), plus tests that assert the
contract. Anything else reintroducing those names is a regression: a reader
would see a calibrated-looking kcal/mol free energy where the value is an
uncalibrated internal proxy score.

Names that really are free energies in kcal/mol are not retired:
``deltaG_experimental_kcal_mol`` (a measurement) and ``deltaG_rmse_kcal_mol`` /
``deltaG_rmse_kT`` (RMSE between reference and predicted free-energy profiles).
"""

from __future__ import annotations

import re
from pathlib import Path

from betelgeuze_product.proxy_energy_schema import RETIRED_PROXY_ENERGY_FIELDS

ROOT = Path(__file__).resolve().parents[2]

#: Files allowed to mention a retired name, and why.
COMPATIBILITY_ALLOWLIST = {
    "betelgeuze_product/proxy_energy_schema.py": "declares the retired aliases",
    "betelgeuze_engine/physics/mm_gbsa.py": "reads pre-rename engine artifacts",
}

#: Retired names owned by the engine surface but declared outside the schema module.
ENGINE_RETIRED_FIELDS = ("deltaG_mm_gbsa_kcal_mol", "deltaG_mmpbsa_proxy_kcal_mol")

SCANNED_DIRECTORIES = (
    "api",
    "betelgeuze_cameo",
    "betelgeuze_engine",
    "betelgeuze_product",
    "core",
    "tools",
    "scripts",
    "config",
    "docs",
)

SCANNED_SUFFIXES = {".py", ".json", ".csv", ".md", ".yml", ".yaml", ".toml", ".sh"}

_RETIRED_PATTERN = re.compile(
    "|".join(
        re.escape(name)
        for name in sorted({*RETIRED_PROXY_ENERGY_FIELDS, *ENGINE_RETIRED_FIELDS})
    )
)


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for directory in SCANNED_DIRECTORIES:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in SCANNED_SUFFIXES:
                files.append(path)
    return files


def _offending_files() -> dict[str, list[str]]:
    offenders: dict[str, list[str]] = {}
    for path in _scanned_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in COMPATIBILITY_ALLOWLIST:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = sorted(set(_RETIRED_PATTERN.findall(text)))
        if hits:
            offenders[rel] = hits
    return offenders


def test_retired_proxy_energy_names_absent_from_active_surface() -> None:
    offenders = _offending_files()

    assert offenders == {}, f"retired proxy-energy field names reintroduced: {offenders}"


def test_allowlisted_compatibility_files_exist_and_are_reader_only() -> None:
    for rel in COMPATIBILITY_ALLOWLIST:
        path = ROOT / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        assert _RETIRED_PATTERN.search(text) is not None, rel


def test_scan_actually_covers_the_active_surface() -> None:
    files = _scanned_files()

    assert len(files) > 200
    covered = {path.relative_to(ROOT).parts[0] for path in files}
    for directory in ("api", "betelgeuze_product", "tools", "config"):
        assert directory in covered


def test_true_free_energy_names_are_not_treated_as_retired() -> None:
    for name in (
        "deltaG_experimental_kcal_mol",
        "deltaG_rmse_kcal_mol",
        "deltaG_rmse_kT",
    ):
        assert _RETIRED_PATTERN.search(name) is None

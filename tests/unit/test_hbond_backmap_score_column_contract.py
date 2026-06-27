"""Drift contract: the backmapping scoring runner must keep emitting every
per-candidate column that ``build_hbond_backmap_report`` reads.

The H-Bond BackMap report surface depends on a fixed column vocabulary in the
backmapping-scoring scores CSV. If
``betelgeuze_engine/product/runners/backmapping_scoring.py`` renames or drops a
column, the builder would silently fall back / mis-map instead of failing
loudly. This dependency-free test pins that contract by asserting each
builder-consumed column literal is still present in the runner source, plus a
synthetic round-trip and a fail-closed assertion on a drifted CSV.
"""

from __future__ import annotations

import csv
from pathlib import Path

from tools.product import build_hbond_backmap_report as mod

ROOT = Path(__file__).resolve().parents[2]
RUNNER_SOURCE = ROOT / "betelgeuze_engine" / "product" / "runners" / "backmapping_scoring.py"


def test_required_any_columns_are_subset_of_builder_columns() -> None:
    assert set(mod.REQUIRED_ANY_COLUMNS).issubset(set(mod.BUILDER_SCORE_COLUMNS))


def test_runner_source_emits_every_builder_column() -> None:
    """Every column the builder reads must appear as a string literal emitted
    by the runner. Catches a rename/drop on the runner side."""

    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    missing = [column for column in mod.BUILDER_SCORE_COLUMNS if f'"{column}"' not in source]
    assert not missing, (
        "backmapping_scoring.py no longer emits builder-required columns "
        f"{missing}; update the runner or BUILDER_SCORE_COLUMNS together."
    )


def test_builder_consumes_only_declared_columns(tmp_path: Path) -> None:
    """A scores CSV that contains exactly the declared columns round-trips to a
    ready report (guards that the declared set is sufficient to build)."""

    scores_csv = tmp_path / "scores.csv"
    with scores_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mod.BUILDER_SCORE_COLUMNS))
        writer.writeheader()
        writer.writerow(
            {
                "target": "ADRB2",
                "ligand_id": "LIG-1",
                mod.COL_CLAIM_SAFE: "True",
                mod.COL_STATUS: "ok",
                mod.COL_SOURCE: "rdkit_etkdg",
                mod.COL_BLOCKED_REASON: "",
                mod.COL_SITE_COUNT: 4,
                mod.COL_MAPPED_SITE_COUNT: 3,
                mod.COL_DONOR: 2,
                mod.COL_ACCEPTOR: 1,
                mod.COL_HBOND_BLOCKED_REASON: "",
                mod.COL_ANGLE_FRACTION: 0.75,
            }
        )

    artifact = mod.build_hbond_backmap_report_artifact(scores_csv)
    assert artifact["status"] == mod.STATUS_OK
    assert artifact["summary"]["candidate_count"] == 1
    assert artifact["summary"]["claim_safe_count"] == 1


def test_builder_fail_closed_when_signature_columns_renamed(tmp_path: Path) -> None:
    """If the runner drifts so none of the signature columns are present, the
    builder must fail closed rather than emit a fabricated ready report."""

    scores_csv = tmp_path / "drifted.csv"
    drifted_columns = [f"{column}_v2" for column in mod.REQUIRED_ANY_COLUMNS]
    with scores_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target", "ligand_id", *drifted_columns])
        writer.writeheader()
        writer.writerow(
            {"target": "ADRB2", "ligand_id": "LIG-1", **{c: "x" for c in drifted_columns}}
        )

    artifact = mod.build_hbond_backmap_report_artifact(scores_csv)
    assert artifact["status"] == mod.STATUS_BLOCKED_SCHEMA
    assert artifact["summary"]["claim_safe_rate"] == 0.0

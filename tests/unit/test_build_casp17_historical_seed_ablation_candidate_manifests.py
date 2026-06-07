from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_ablation_candidate_manifests as mod


FIELDS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
    "ablation_manifest_ref",
]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n",
        encoding="utf-8",
    )
    return str(path)


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--manifest-dir",
        str(tmp_path / "manifests"),
        "--out-json",
        str(tmp_path / "ablation.json"),
        "--out-csv",
        str(tmp_path / "ablation.csv"),
        "--out-md",
        str(tmp_path / "ABLATION.md"),
    ]


def test_ablation_candidate_manifest_fingerprints_selected_native_and_step_candidate(tmp_path: Path) -> None:
    prediction = _pdb(tmp_path / "run" / "visual_post_internal_post_chignolin_sample000_step00020.pdb")
    _pdb(tmp_path / "run" / "visual_post_internal_post_chignolin_sample000_step00010.pdb")
    native = _pdb(tmp_path / "native" / "chignolin.pdb")
    row = {
        "seed_rank": "1",
        "batch_slot": "1",
        "benchmark_id": "hist_seed_chignolin",
        "target_id": "HIST_CHIGNOLIN",
        "scope": "monomer",
        "prediction_pdb": prediction,
        "native_pdb": native,
        "ablation_manifest_ref": "REQUIRED_ABLATION_MANIFEST_REF",
    }
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["ablation_candidate_status"] == "operator_ablation_review_required"
    assert payload["summary"]["candidate_manifest_count"] == 1
    assert payload["summary"]["selected_prediction_present_count"] == 1
    assert payload["summary"]["native_reference_present_count"] == 1
    assert payload["summary"]["baseline_candidate_present_count"] == 1
    assert payload["summary"]["layer_evidence_gap_count"] == 0
    assert payload["summary"]["ready_for_operator_reference_count"] == 0
    assert payload["rows"][0]["candidate_manifest_status"] == "operator_ablation_review_required"
    assert payload["rows"][0]["baseline_candidate_count"] == 1
    assert "operator_ablation_review_required" in payload["rows"][0]["blockers"]

    manifest_path = Path(payload["rows"][0]["candidate_manifest_csv"])
    if not manifest_path.is_absolute():
        manifest_path = mod.ROOT / manifest_path
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    roles = {row["role"] for row in rows}
    assert roles == {"selected_prediction", "native_reference", "same_run_step_candidate"}
    assert all(row["sha256_16"] for row in rows if row["exists"] == "True")

    written = json.loads((tmp_path / "ablation.json").read_text(encoding="utf-8"))
    assert written["summary"]["claim_boundary"].startswith("Local CASP17 historical seed ablation")


def test_ablation_candidate_manifest_keeps_missing_baseline_as_operator_gap(tmp_path: Path) -> None:
    prediction = _pdb(tmp_path / "run" / "visual_post_internal_post_bba5_sample000_step00020.pdb")
    native = _pdb(tmp_path / "native" / "bba5.pdb")
    row = {
        "seed_rank": "1",
        "batch_slot": "1",
        "benchmark_id": "hist_seed_bba5",
        "target_id": "HIST_BBA5",
        "scope": "monomer",
        "prediction_pdb": prediction,
        "native_pdb": native,
        "ablation_manifest_ref": "REQUIRED_ABLATION_MANIFEST_REF",
    }
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["ablation_candidate_status"] == "operator_ablation_review_required"
    assert payload["summary"]["baseline_candidate_present_count"] == 0
    assert payload["summary"]["layer_evidence_gap_count"] == 1
    assert payload["rows"][0]["candidate_manifest_status"] == "operator_ablation_layer_evidence_missing"
    assert "ablation_layer_evidence_missing" in payload["rows"][0]["blockers"]


def test_ablation_candidate_manifest_blocks_missing_selected_prediction(tmp_path: Path) -> None:
    native = _pdb(tmp_path / "native" / "bba5.pdb")
    row = {
        "seed_rank": "1",
        "batch_slot": "1",
        "benchmark_id": "hist_seed_bba5",
        "target_id": "HIST_BBA5",
        "scope": "monomer",
        "prediction_pdb": str(tmp_path / "missing_step00020.pdb"),
        "native_pdb": native,
        "ablation_manifest_ref": "REQUIRED_ABLATION_MANIFEST_REF",
    }
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["ablation_candidate_status"] == "blocked_core_candidate_inputs"
    assert payload["summary"]["blocked_core_candidate_input_count"] == 1
    assert payload["rows"][0]["candidate_manifest_status"] == "blocked_core_candidate_inputs"
    assert "selected_prediction_missing_or_invalid" in payload["rows"][0]["blockers"]

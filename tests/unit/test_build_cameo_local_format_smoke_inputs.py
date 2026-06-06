from __future__ import annotations

import csv
import json
from pathlib import Path

from betelgeuze_cameo.format_validation import build_format_validation_packet, validate_model_file
from betelgeuze_cameo.operator_inputs import build_operator_input_validation
from betelgeuze_cameo.selector import build_selection_packet
from tools.cameo import build_cameo_local_format_smoke_inputs as mod


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def test_build_cameo_local_format_smoke_inputs_writes_ready_artifacts(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs" / "cameo_local_format_smoke_inputs_current"

    mod.main(["--out-dir", str(out_dir), "--base-dir", str(tmp_path)])

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["summary"]
    model_path = tmp_path / summary["model_path"]

    assert summary["status"] == "cameo_local_format_smoke_inputs_ready"
    assert summary["source_kind"] == "cameo_dry_run"
    assert summary["native_local_accuracy_used"] is False
    assert summary["official_cameo_results_used"] is False
    assert model_path.exists()
    assert (out_dir / "candidates.csv").exists()
    assert (out_dir / "models.csv").exists()
    assert "CAMEO Local Format Smoke Inputs" in (out_dir / "manifest.md").read_text(encoding="utf-8")

    format_payload = validate_model_file(model_path, target_id=summary["target_id"], candidate_id=summary["candidate_id"], cameo_model_rank=1)
    assert format_payload["summary"]["format_validation_status"] == "pass"
    assert format_payload["summary"]["atom_count"] == 6


def test_cameo_local_format_smoke_inputs_drive_validation_selection_and_format(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs" / "cameo_local_format_smoke_inputs_current"
    payload = mod.build_smoke_inputs(out_dir=out_dir, base_dir=tmp_path, target_id="CAMEO_SMOKE", candidate_id="smoke1")
    mod.write_smoke_inputs(payload)

    candidate_rows = _read_csv_rows(out_dir / "candidates.csv")
    model_rows = _read_csv_rows(out_dir / "models.csv")
    input_payload = build_operator_input_validation(
        candidates_rows=candidate_rows,
        model_rows=model_rows,
        official_result_rows=[],
        base_dir=tmp_path,
    )
    selection_payload = build_selection_packet(candidate_rows, target_id="CAMEO_SMOKE")
    selected_rows = selection_payload["rows"]
    format_payload = build_format_validation_packet(selected_rows, target_id="CAMEO_SMOKE", base_dir=tmp_path)

    assert input_payload["summary"]["status"] == "cameo_operator_inputs_ready_pending_official_results"
    assert selection_payload["summary"]["selection_status"] == "cameo_model1_selection_ready"
    assert format_payload["summary"]["status"] == "cameo_format_validation_ready"
    assert format_payload["summary"]["model1_format_pass"] is True

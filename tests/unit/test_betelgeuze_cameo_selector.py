from __future__ import annotations

import csv
import json
from pathlib import Path

from betelgeuze_cameo.selector import build_selection_packet
from tools import build_cameo_model1_selection_packet as tool


def test_cameo_selector_picks_internal_model1_and_blocks_external_pool() -> None:
    payload = build_selection_packet(
        [
            {
                "target_id": "CAMEO001",
                "candidate_id": "external_best_looking",
                "model_path": "external/model.pdb",
                "source_kind": "massivefold_external_pool",
                "validation_status": "pass",
                "confidence_mean": "99",
                "continuity_fraction": "1.0",
                "ca_clash_count": "0",
                "shape_penalty": "0",
                "rank_hint": "1",
            },
            {
                "target_id": "CAMEO001",
                "candidate_id": "internal_model_a",
                "model_path": "runs/cameo/internal_model_a.pdb",
                "source_kind": "internal_prediction",
                "validation_status": "pass",
                "confidence_mean": "80",
                "continuity_fraction": "0.9",
                "ca_clash_count": "1",
                "shape_penalty": "0.1",
                "rank_hint": "2",
            },
        ],
        target_id="CAMEO001",
    )

    summary = payload["summary"]
    rows = {row["candidate_id"]: row for row in payload["rows"]}
    assert summary["selection_status"] == "cameo_model1_selection_ready"
    assert summary["model1_candidate_id"] == "internal_model_a"
    assert rows["external_best_looking"]["selector_eligible"] is False
    assert "source_kind_not_internal_prediction" in rows["external_best_looking"]["selector_blockers"]
    assert summary["native_or_external_accuracy_used"] is False
    assert summary["outbound_email_enabled"] is False


def test_build_cameo_model1_selection_packet_tool(tmp_path: Path) -> None:
    candidates_csv = tmp_path / "candidates.csv"
    with candidates_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target_id",
                "candidate_id",
                "model_path",
                "source_kind",
                "validation_status",
                "confidence_mean",
                "continuity_fraction",
                "ca_clash_count",
                "shape_penalty",
                "rank_hint",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "target_id": "CAMEO002",
                "candidate_id": "internal_model_b",
                "model_path": "runs/cameo/internal_model_b.pdb",
                "source_kind": "local_pipeline",
                "validation_status": "pass",
                "confidence_mean": "75",
                "continuity_fraction": "1",
                "ca_clash_count": "0",
                "shape_penalty": "0.05",
                "rank_hint": "1",
            }
        )
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"

    payload = tool.build_selection_packet(tool._read_csv_rows(candidates_csv), target_id="CAMEO002")
    tool._write_json(out_json, payload)
    tool.write_csv_rows(out_csv, payload["rows"])
    tool._write_markdown(out_md, payload)

    assert json.loads(out_json.read_text())["summary"]["model1_candidate_id"] == "internal_model_b"
    assert "CAMEO Model1 Selection Packet" in out_md.read_text()
    assert out_csv.read_text().startswith("target_id,")


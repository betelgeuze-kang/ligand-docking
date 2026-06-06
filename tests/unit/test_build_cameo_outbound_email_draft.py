from __future__ import annotations

import json
from pathlib import Path

from tools.cameo import build_cameo_outbound_email_draft as mod


def test_build_cameo_outbound_email_draft_tool_writes_outputs(tmp_path: Path) -> None:
    model = tmp_path / "model1.pdb"
    model.write_text("ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 20.00           C\nEND\n", encoding="utf-8")
    handoff = tmp_path / "handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "cameo_handoff_dry_run_ready",
                    "target_id": "CAMEO_TEST_001",
                    "outbound_email_enabled": False,
                },
                "rows": [
                    {
                        "target_id": "CAMEO_TEST_001",
                        "candidate_id": "model1",
                        "cameo_model_rank": 1,
                        "model_path": str(model),
                        "attachment_filename": "model_1_model1.pdb",
                        "detected_format": "pdb",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "draft.json"
    out_csv = tmp_path / "draft.csv"
    out_md = tmp_path / "draft.md"
    draft_eml = tmp_path / "draft.eml"

    mod.main(
        [
            "--handoff-json",
            str(handoff),
            "--recipient-email",
            "results@example.invalid",
            "--sender-email",
            "operator@example.invalid",
            "--draft-eml",
            str(draft_eml),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "cameo_outbound_email_draft_ready"
    assert draft_eml.is_file()
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,candidate_id,")
    assert "CAMEO Outbound Email Draft" in out_md.read_text(encoding="utf-8")

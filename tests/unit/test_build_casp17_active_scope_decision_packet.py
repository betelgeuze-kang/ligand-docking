from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_active_scope_decision_packet as mod


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_active_scope_decision_defers_capri_and_keeps_casp17_active(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--out-json",
            str(tmp_path / "scope.json"),
            "--out-csv",
            str(tmp_path / "scope.csv"),
            "--out-md",
            str(tmp_path / "scope.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["scope_decision_status"] == "casp17_only_active"
    assert payload["summary"]["active_competition_scope"] == "casp17_only"
    assert payload["summary"]["casp17_continuation_status"] == "active"
    assert payload["summary"]["capri_round65_participation_status"] == "deferred_pi_required"
    assert payload["summary"]["capri_round65_not_active_blocker"] is True
    assert payload["summary"]["active_lane_count"] == 3
    assert payload["summary"]["deferred_lane_count"] == 1
    assert payload["rows"][0]["lane"] == "casp17_historical_benchmark"
    assert payload["rows"][-1]["lane"] == "capri_round65"
    assert payload["rows"][-1]["participation_status"] == "deferred_pi_required"

    written = json.loads((tmp_path / "scope.json").read_text(encoding="utf-8"))
    assert written["summary"]["capri_round65_artifact_policy"] == "preserve_context_no_registration_no_submission"
    csv_rows = _read_csv(tmp_path / "scope.csv")
    assert csv_rows[-1]["priority"] == "0"
    md = (tmp_path / "scope.md").read_text(encoding="utf-8")
    assert "CAPRI Round 65 participation: `deferred_pi_required`" in md

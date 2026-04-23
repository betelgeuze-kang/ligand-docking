from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_ligand_cascade_speedup_envelope(tmp_path: Path) -> None:
    kpi_json = tmp_path / "kpi.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    kpi_json.write_text(
        json.dumps(
            {
                "summary": {"mean_stage2_share_pct": 86.0},
                "rows": [
                    {
                        "task_id": "gpcr_core_full",
                        "set_id": "set1",
                        "domain": "gpcr",
                        "priority": "P1",
                        "stage2_share_pct": 83.41,
                        "projected_100k_wall_min": 27.96,
                        "projected_1m_wall_hr": 4.66,
                    },
                    {
                        "task_id": "ion_trpv1_chembl50_full",
                        "set_id": "set2",
                        "domain": "ion_channel",
                        "priority": "P0",
                        "stage2_share_pct": 89.93,
                        "projected_100k_wall_min": 97.31,
                        "projected_1m_wall_hr": 16.22,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_ligand_cascade_speedup_envelope.py"),
            "--kpi-json",
            str(kpi_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["task_count"] == 2
    assert payload["summary"]["scenario_count"] == 10
    gpcr_90 = next(
        row
        for row in payload["envelope_rows"]
        if row["task_id"] == "gpcr_core_full" and row["avoided_stage2_fraction"] == 0.9
    )
    assert gpcr_90["overall_speedup_x"] > 3.0
    gpcr_3x = next(
        row
        for row in payload["route_rows"]
        if row["task_id"] == "gpcr_core_full" and row["target_speedup_x"] == 3.0
    )
    assert gpcr_3x["feasible_with_stage2_only_avoidance"] == "yes"

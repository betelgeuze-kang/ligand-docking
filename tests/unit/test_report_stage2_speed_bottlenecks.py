import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from tools import report_stage2_speed_bottlenecks as rep


def test_report_stage2_speed_bottlenecks_outputs(tmp_path):
    in_csv = Path(tmp_path) / "stage2.csv"
    out_csv = Path(tmp_path) / "bottlenecks.csv"
    out_json = Path(tmp_path) / "bottlenecks.json"
    out_md = Path(tmp_path) / "bottlenecks.md"

    df = pd.DataFrame(
        [
            {
                "target": "A",
                "throughput_on": 1000.0,
                "throughput_off": 200.0,
                "speedup_on_vs_off": 5.0,
                "force_ms_off": 4.0,
                "integrator_ms_off": 1.0,
                "neighbor_ms_off": 0.1,
                "step_ms_off": 5.5,
            },
            {
                "target": "B",
                "throughput_on": 1000.0,
                "throughput_off": 100.0,
                "speedup_on_vs_off": 10.0,
                "force_ms_off": 0.4,
                "integrator_ms_off": 1.2,
                "neighbor_ms_off": 0.1,
                "step_ms_off": 1.7,
            },
            {
                "target": "C",
                "throughput_on": 1000.0,
                "throughput_off": 60.0,
                "speedup_on_vs_off": 16.0,
                "force_ms_off": 0.2,
                "integrator_ms_off": 0.3,
                "neighbor_ms_off": 0.6,
                "step_ms_off": 1.1,
            },
        ]
    )
    df.to_csv(in_csv, index=False)

    args = SimpleNamespace(
        input_csv=str(in_csv),
        speedup_threshold=12.0,
        out_csv=str(out_csv),
        out_json=str(out_json),
        out_md=str(out_md),
    )
    payload = rep.run_report(args)

    assert payload["summary"]["targets"] == 3
    assert payload["summary"]["failed_targets_count"] == 2
    assert payload["summary"]["pass"] is False
    assert Path(out_csv).exists()
    assert Path(out_json).exists()
    assert Path(out_md).exists()

    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert "rows" in saved
    assert len(saved["rows"]) == 3
    # sorted by speedup asc: A(5), B(10), C(16)
    assert saved["rows"][0]["target"] == "A"
    assert saved["rows"][0]["bottleneck_cause"] == "pytorch_force_backend_dominant"
    assert saved["rows"][1]["bottleneck_cause"] == "integrator_overhead_dominant"
    assert saved["rows"][2]["bottleneck_cause"] == "neighbor_list_overhead_dominant"


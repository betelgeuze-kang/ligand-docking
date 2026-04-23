import json

from tools import build_commercial_readiness_report as cr


def test_build_commercial_readiness_report_pass(tmp_path):
    nightly = tmp_path / "nightly.json"
    strict = tmp_path / "strict.json"
    dash = tmp_path / "dashboard.json"
    packet = tmp_path / "packet.json"
    stage2 = tmp_path / "stage2.csv"
    acc = tmp_path / "accuracy_external.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    nightly.write_text(
        json.dumps(
            {
                "pass": True,
                "long_stability_status": {"pass": True},
                "claim_status": {"initial_claim_ready_for_allatom": True},
                "special_case_status": {"pass": True},
                "ood_measured20_status": {"pass": True},
            }
        ),
        encoding="utf-8",
    )
    strict.write_text(
        json.dumps(
            {
                "summary": {"pass": True},
                "gates": {
                    "accuracy_gate": {"pass": True},
                    "speed": {"avg_speedup_on_vs_off": 15.0},
                },
            }
        ),
        encoding="utf-8",
    )
    dash.write_text(
        json.dumps({"summary": {"metric_count": 8, "run_count": 2, "pdb_count": 3}}),
        encoding="utf-8",
    )
    packet.write_text(
        json.dumps({"global_summary": {"external_md_accuracy": {"external_targets_with_reference": 10}}}),
        encoding="utf-8",
    )
    stage2.write_text(
        "target,speedup_on_vs_off\nA,20.0\nB,16.0\nC,13.0\n",
        encoding="utf-8",
    )
    acc.write_text(
        "target,avg_rmsd\nA,2.0\nB,3.5\nC,4.0\n",
        encoding="utf-8",
    )

    args = cr.build_parser().parse_args(
        [
            "--nightly-summary-json",
            str(nightly),
            "--strict-release-summary-json",
            str(strict),
            "--dashboard-json",
            str(dash),
            "--external-packet-json",
            str(packet),
            "--stage2-csv",
            str(stage2),
            "--accuracy-external-csv",
            str(acc),
            "--disable-auto-discovery",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )
    payload = cr.build_report(args)
    cr._write_outputs(payload, out_json=str(out_json), out_csv=str(out_csv), out_md=str(out_md))

    assert out_json.exists()
    assert out_csv.exists()
    assert out_md.exists()
    assert payload["summary"]["readiness_tier"] in {
        "commercial_candidate",
        "pilot_ready",
        "prototype_ready",
        "research_only",
    }
    assert payload["summary"]["failed_checks"] == 0


def test_build_commercial_readiness_report_handles_missing_sources(tmp_path):
    args = cr.build_parser().parse_args(
        [
            "--nightly-summary-json",
            str(tmp_path / "missing_nightly.json"),
            "--strict-release-summary-json",
            str(tmp_path / "missing_strict.json"),
            "--dashboard-json",
            str(tmp_path / "missing_dash.json"),
            "--external-packet-json",
            str(tmp_path / "missing_packet.json"),
            "--disable-auto-discovery",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
        ]
    )
    payload = cr.build_report(args)
    assert payload["summary"]["considered_checks"] == 0
    assert payload["summary"]["readiness_tier"] == "insufficient_evidence"

import argparse
import json

import pandas as pd
import pytest

from tools import build_external_eval_packet as packet_mod


def _write_minimal_required_inputs(tmp_path):
    gate_json = tmp_path / "gate.json"
    gate_json.write_text(
        json.dumps(
            {
                "summary": {
                    "pass": True,
                    "targets": 10,
                    "samples": 8,
                    "thresholds": {"jaccard": 1.0},
                },
                "parity_summary": {
                    "avg_neighbor_jaccard": 1.0,
                    "avg_force_rmse_raw": 0.1,
                    "avg_force_rel_rmse_clipped200": 1e-6,
                },
                "performance_summary": {
                    "avg_throughput_on": 100.0,
                    "avg_throughput_off": 10.0,
                    "avg_speedup_on_vs_off": 10.0,
                },
                "overflow_events": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    parity_csv = tmp_path / "parity.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "neighbor_jaccard_mean": 1.0,
                "e2e_rmse_mean_raw": 0.2,
                "e2e_rel_rmse_mean_clipped": 1e-6,
                "force_rmse_mean_raw": 0.1,
                "rs_neighbor_saturated_samples": 0,
                "rs_cell_overflow_samples": 0,
            }
        ]
    ).to_csv(parity_csv, index=False)

    stage2_csv = tmp_path / "stage2.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "throughput_on": 120.0,
                "throughput_off": 12.0,
                "speedup_on_vs_off": 10.0,
                "step_ms_on": 0.5,
                "step_ms_off": 5.0,
            }
        ]
    ).to_csv(stage2_csv, index=False)

    fidelity_csv = tmp_path / "fidelity.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "restrained_rmsd": 1.2,
                "unrestrained_rmsd": 1.4,
                "restrained_rg_delta": 0.3,
                "unrestrained_rg_delta": 0.4,
                "restrained_sasa_delta": 10.0,
                "unrestrained_sasa_delta": 12.0,
                "restrained_proxy_energy_drift_ratio": 0.02,
                "unrestrained_proxy_energy_drift_ratio": 0.03,
                "restrained_energy_drift_ratio": 0.01,
                "unrestrained_energy_drift_ratio": 0.015,
            }
        ]
    ).to_csv(fidelity_csv, index=False)
    return gate_json, parity_csv, stage2_csv, fidelity_csv


def test_build_packet_with_optional_external_and_quality_sources(tmp_path):
    gate_json, parity_csv, stage2_csv, fidelity_csv = _write_minimal_required_inputs(tmp_path)

    external_csv = tmp_path / "accuracy_external.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "reference_source": "external",
                "reference_engine": "openmm",
                "reference_label": "teacher",
                "avg_rmsd": 0.6,
                "avg_rmsd_raw": 0.6,
                "avg_rmsd_aligned": 0.3,
                "avg_rmsd_vs_native": 0.8,
                "avg_rmsd_vs_native_aligned": 0.5,
                "avg_reference_vs_native_rmsd": 0.4,
                "avg_reference_vs_native_rmsd_aligned": 0.2,
                "avg_rg": 4.2,
            }
        ]
    ).to_csv(external_csv, index=False)

    quality_csv = tmp_path / "quality.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "source_file": "/tmp/a.pdb",
                "quality_tier": "high",
                "plddt_mean": 92.0,
                "include": 1,
                "sample_weight": 1.0,
                "exclude_reason": "ok",
            },
            {
                "target": "Chignolin",
                "source_file": "/tmp/b.pdb",
                "quality_tier": "low",
                "plddt_mean": 55.0,
                "include": 0,
                "sample_weight": 0.0,
                "exclude_reason": "low_plddt_mean",
            },
        ]
    ).to_csv(quality_csv, index=False)

    args = argparse.Namespace(
        packet_version="v1",
        gate_json=str(gate_json),
        parity_target_csv=str(parity_csv),
        stage2_csv=str(stage2_csv),
        fidelity_csv=str(fidelity_csv),
        feature_csv=None,
        q_low=0.10,
        q_high=0.90,
        min_obs=64,
        accuracy_external_csv=str(external_csv),
        quality_curation_csv=str(quality_csv),
        strict_optional_sources=False,
        out_json=str(tmp_path / "out.json"),
    )
    packet = packet_mod.build_packet(args)

    assert packet["sources"]["accuracy_external_csv"] == str(external_csv)
    assert packet["sources"]["quality_curation_csv"] == str(quality_csv)
    assert packet["global_summary"]["external_md_accuracy"]["targets_with_external_reference"] == 1
    assert packet["global_summary"]["structure_quality_curation"]["total_rows"] == 2
    assert packet["global_summary"]["structure_quality_curation"]["included_rows"] == 1
    assert packet["global_summary"]["external_md_accuracy"]["avg_rmsd_vs_external_ref_aligned_A"] == pytest.approx(
        0.3, rel=0.0, abs=1e-6
    )

    chig = [x for x in packet["proteins"] if x["target"] == "Chignolin"][0]
    assert chig["external_md_accuracy"]["available"] is True
    assert chig["external_md_accuracy"]["reference_engine"] == "openmm"
    assert chig["external_md_accuracy"]["rmsd_vs_external_ref_aligned_A"] == pytest.approx(
        0.3, rel=0.0, abs=1e-6
    )
    assert chig["structure_data_quality"]["available"] is True
    assert chig["structure_data_quality"]["include_recommended"] is True


def test_build_packet_without_optional_sources(tmp_path):
    gate_json, parity_csv, stage2_csv, fidelity_csv = _write_minimal_required_inputs(tmp_path)
    args = argparse.Namespace(
        packet_version="v1",
        gate_json=str(gate_json),
        parity_target_csv=str(parity_csv),
        stage2_csv=str(stage2_csv),
        fidelity_csv=str(fidelity_csv),
        feature_csv=None,
        q_low=0.10,
        q_high=0.90,
        min_obs=64,
        accuracy_external_csv=None,
        quality_curation_csv=None,
        strict_optional_sources=False,
        out_json=str(tmp_path / "out.json"),
    )
    packet = packet_mod.build_packet(args)
    assert packet["global_summary"]["external_md_accuracy"]["source_present"] is False
    assert packet["global_summary"]["structure_quality_curation"]["source_present"] is False

    chig = [x for x in packet["proteins"] if x["target"] == "Chignolin"][0]
    assert chig["external_md_accuracy"]["available"] is False
    assert chig["structure_data_quality"]["available"] is False


def test_build_packet_strict_optional_sources_missing_raises(tmp_path):
    gate_json, parity_csv, stage2_csv, fidelity_csv = _write_minimal_required_inputs(tmp_path)
    args = argparse.Namespace(
        packet_version="v1",
        gate_json=str(gate_json),
        parity_target_csv=str(parity_csv),
        stage2_csv=str(stage2_csv),
        fidelity_csv=str(fidelity_csv),
        feature_csv=None,
        q_low=0.10,
        q_high=0.90,
        min_obs=64,
        accuracy_external_csv=str(tmp_path / "missing_external.csv"),
        quality_curation_csv=None,
        strict_optional_sources=True,
        out_json=str(tmp_path / "out.json"),
    )
    with pytest.raises(FileNotFoundError):
        packet_mod.build_packet(args)


def test_build_packet_v3_includes_dashboard_summary_from_nightly(tmp_path):
    gate_json, parity_csv, stage2_csv, fidelity_csv = _write_minimal_required_inputs(tmp_path)
    feature_csv = tmp_path / "feature.csv"
    pd.DataFrame(
        [
            {"target": "Chignolin", "step": 0, "energy": -10.0, "Rg": 5.1},
            {"target": "Chignolin", "step": 1, "energy": -9.8, "Rg": 5.0},
        ]
    ).to_csv(feature_csv, index=False)

    dashboard_json = tmp_path / "dashboard.json"
    dashboard_html = tmp_path / "dashboard.html"
    dashboard_html.write_text("<html></html>", encoding="utf-8")
    dashboard_json.write_text(
        json.dumps(
            {
                "title": "Nightly Dashboard",
                "metrics": ["energy", "Rg"],
                "runs": [{"label": "r1"}],
                "pdb_entries": [{"name": "a.pdb"}],
                "target_filters": ["Chignolin"],
                "thresholds": {"energy": -8.0},
            }
        ),
        encoding="utf-8",
    )

    nightly_json = tmp_path / "nightly.json"
    nightly_json.write_text(
        json.dumps(
            {
                "pass": True,
                "dashboard_status": {"metrics_count": 2, "run_count": 1, "pdb_count": 1},
                "paths": {"dashboard_json": str(dashboard_json), "dashboard_html": str(dashboard_html)},
            }
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        packet_version="v3",
        gate_json=str(gate_json),
        parity_target_csv=str(parity_csv),
        stage2_csv=str(stage2_csv),
        fidelity_csv=str(fidelity_csv),
        feature_csv=str(feature_csv),
        q_low=0.10,
        q_high=0.90,
        min_obs=1,
        accuracy_external_csv=None,
        quality_curation_csv=None,
        strict_release_summary_json=None,
        nightly_summary_json=str(nightly_json),
        reproducibility_json=None,
        baseline_config_json=None,
        claim_correction_summary_json=None,
        dashboard_json=None,
        dashboard_html=None,
        strict_optional_sources=False,
        out_json=str(tmp_path / "out_v3.json"),
    )
    packet = packet_mod.build_packet(args)

    assert packet["sources"]["dashboard_json"] == str(dashboard_json)
    assert packet["sources"]["dashboard_html"] == str(dashboard_html)
    assert packet["global_summary"]["dashboard"]["available"] is True
    assert packet["global_summary"]["dashboard"]["metrics_count"] == 2
    assert packet["global_summary"]["dashboard"]["run_count"] == 1
    assert packet["global_summary"]["dashboard"]["pdb_count"] == 1
    assert packet["global_summary"]["dashboard"]["target_filters"] == ["Chignolin"]
    assert (
        packet["global_summary"]["validation_evidence_v3"]["dashboard"]["dashboard_html"]
        == str(dashboard_html)
    )

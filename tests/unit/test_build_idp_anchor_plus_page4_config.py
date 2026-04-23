from __future__ import annotations

from tools import build_idp_anchor_plus_page4_config as mod


def test_build_idp_anchor_plus_page4_config() -> None:
    out_cfg, payload = mod.build_payload(
        {
            "version": "subset",
            "description": "subset",
            "runtime": {"device": "cuda"},
            "gate": {"min_dominant_state_accuracy": 0.7},
            "targets": [
                {"name": "alpha_synuclein_full", "suffix": "base"},
                {"name": "tau_k18", "suffix": "base"},
            ],
        },
        {
            "version": "full",
            "description": "full",
            "runtime": {"device": "cuda"},
            "gate": {"min_dominant_state_accuracy": 0.7},
            "targets": [
                {"name": "page4", "suffix": "base"},
                {"name": "page4", "suffix": "ph_low"},
                {"name": "amyloid_beta_40", "suffix": "base"},
            ],
        },
    )
    s = payload["summary"]
    assert s["status"] == "anchor_plus_page4_config_ready"
    assert s["validated_subset_target_count"] == 2
    assert s["additional_anchor_target_count"] == 1
    assert s["additional_anchor_target_name"] == "page4"
    assert s["total_target_row_count"] == 4
    assert s["unique_target_count"] == 3
    names = [row["name"] for row in out_cfg["targets"]]
    assert names == ["alpha_synuclein_full", "tau_k18", "page4", "page4"]
    assert out_cfg["version"] == "idp_3bead_benchmark_v7_anchor_plus_page4"

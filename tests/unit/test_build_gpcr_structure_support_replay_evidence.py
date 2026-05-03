import csv
import json
from pathlib import Path

from tools import build_gpcr_structure_support_replay_evidence as mod


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_replay_evidence_evaluates_linear_rescore_without_claim_promotion(tmp_path: Path) -> None:
    ranking_rows = tmp_path / "ranking.csv"
    stage3_scores = tmp_path / "scores.csv"
    spec_json = tmp_path / "spec.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    _write_csv(
        ranking_rows,
        [
            {"ligand_id": "decoy_a", "is_binder": "0", "role": "far_ood_eval"},
            {"ligand_id": "binder_a", "is_binder": "1", "role": "far_ood_eval"},
            {"ligand_id": "decoy_b", "is_binder": "0", "role": "far_ood_eval"},
            {"ligand_id": "binder_b", "is_binder": "1", "role": "far_ood_eval"},
        ],
    )
    _write_csv(
        stage3_scores,
        [
            {"ligand_id": "decoy_a", "binding_score_composite_v7": "-10.0", "ligand_logp": "0.2"},
            {"ligand_id": "binder_a", "binding_score_composite_v7": "-8.0", "ligand_logp": "4.0"},
            {"ligand_id": "decoy_b", "binding_score_composite_v7": "-7.0", "ligand_logp": "0.1"},
            {"ligand_id": "binder_b", "binding_score_composite_v7": "-6.0", "ligand_logp": "3.8"},
        ],
    )
    _write_json(
        spec_json,
        {
            "summary": {"prototype_variant": "gpcr_core_structure_support_rescore_v1"},
            "prototype": {
                "constraints": {
                    "structure_support_gate": {
                        "enabled": True,
                        "required_before_claim": True,
                        "full_100k_gate_green": False,
                    }
                },
                "linear_rescore": {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7", "weight": 1.0},
                        {"feature": "z_ligand_logp", "weight": -3.0},
                    ],
                },
            },
        },
    )

    payload = mod.build_payload(
        stage3_scores_csv=stage3_scores,
        ranking_rows_csv=ranking_rows,
        spec_json=spec_json,
        out_json=out_json,
        out_md=out_md,
        topk_k=2,
        pr_auc_min=0.8,
        topk_hit_rate_min=0.5,
    )

    assert payload["summary"]["status"] == "replay_gate_passed"
    assert payload["summary"]["claim_safe_assertion_allowed"] is False
    assert payload["summary"]["claim_text_locked_until_full_100k_gate_green"] is True
    assert payload["summary"]["topk_hit_rate"] == 1.0
    assert payload["summary"]["positive_ranks"] == [1, 2]
    assert payload["rows"][0]["ligand_id"] == "binder_a"
    assert out_json.exists()
    assert out_md.exists()

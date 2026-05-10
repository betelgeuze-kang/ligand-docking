from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.build_wetlab_tcruzi_pde_replicate_evidence import build_payload


def _write_scores(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "ligand_id",
                "mean_min_distance_A",
                "contact_fraction",
                "binding_energy_proxy",
                "score_json",
                "backmapped_pdb",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_attempt_state(attempt_dir: Path, fingerprint: str) -> None:
    (attempt_dir / "allatom_rescue_state.json").write_text(
        json.dumps(
            {
                "summary": {
                    "attempt_id": attempt_dir.name,
                    "input_fingerprint_sha256": fingerprint,
                    "execution_mode": "pseudo_allatom_backmapping_scoring_executed",
                    "clash_relief_mode": "translate",
                    "clash_relief_target_min_distance_A": 2.12,
                }
            }
        ),
        encoding="utf-8",
    )


def test_build_wetlab_tcruzi_pde_replicate_evidence_groups_attempt_observations(
    tmp_path: Path,
) -> None:
    attempts_root = tmp_path / "attempts"
    distances = [2.1, 2.2, 2.3, 2.4]
    for idx, distance in enumerate(distances):
        rows: list[dict[str, object]] = [
            {
                "ligand_id": "lig_a",
                "mean_min_distance_A": distance,
                "contact_fraction": 0.5 + 0.1 * idx,
                "binding_energy_proxy": -1.0 - 0.1 * idx,
                "score_json": f"a_{idx}.json",
                "backmapped_pdb": f"a_{idx}.pdb",
            }
        ]
        if idx == 0:
            rows.append(
                {
                    "ligand_id": "lig_a",
                    "mean_min_distance_A": 9.9,
                    "contact_fraction": 0.1,
                    "binding_energy_proxy": 9.9,
                    "score_json": "duplicate.json",
                    "backmapped_pdb": "duplicate.pdb",
                }
            )
        _write_scores(attempts_root / f"attempt_{idx}" / "allatom_rescue_scores.csv", rows)

    _write_scores(
        attempts_root / "single_attempt" / "allatom_rescue_scores.csv",
        [
            {
                "ligand_id": "lig_b",
                "mean_min_distance_A": 3.0,
                "contact_fraction": 0.4,
                "binding_energy_proxy": -0.2,
                "score_json": "b.json",
                "backmapped_pdb": "b.pdb",
            }
        ],
    )
    runner_json = tmp_path / "runner.json"
    runner_json.write_text(json.dumps({"summary": {"attempt_id": "current_attempt"}}), encoding="utf-8")

    payload = build_payload(
        attempts_root=str(attempts_root),
        runner_json=str(runner_json),
        selected_threshold_A=2.5,
    )

    summary = payload["summary"]
    assert summary["observation_count"] == 5
    assert summary["ligand_count"] == 2
    assert summary["robust_ligand_count"] == 1
    assert summary["strict_replicate_ligand_count"] == 1
    assert summary["source_runner_attempt_id"] == "current_attempt"
    row = payload["rows"][0]
    assert row["ligand_id"] == "lig_a"
    assert row["replicate_count"] == 4
    assert row["replicate_pass_count"] == 4
    assert row["replicate_pass_fraction"] == 1.0
    assert row["median_mean_min_distance_A"] == 2.25
    assert row["mean_min_distance_iqr_A"] == 0.15
    assert row["median_contact_fraction"] == 0.65
    assert row["replicate_evidence_score_csv_count"] == 4
    assert row["replicate_evidence_policy"] == "count_current_input_fingerprint_attempt_observations_only"


def test_build_wetlab_tcruzi_pde_replicate_evidence_filters_to_current_fingerprint(
    tmp_path: Path,
) -> None:
    attempts_root = tmp_path / "attempts"
    for idx, distance in enumerate([2.12, 2.13, 2.14]):
        attempt_dir = attempts_root / f"current_{idx}"
        _write_scores(
            attempt_dir / "allatom_rescue_scores.csv",
            [
                {
                    "ligand_id": "lig_a",
                    "mean_min_distance_A": distance,
                    "contact_fraction": 0.6,
                    "binding_energy_proxy": -0.1,
                    "score_json": f"current_{idx}.json",
                    "backmapped_pdb": f"current_{idx}.pdb",
                }
            ],
        )
        _write_attempt_state(attempt_dir, "current-fingerprint")
    old_attempt_dir = attempts_root / "old"
    _write_scores(
        old_attempt_dir / "allatom_rescue_scores.csv",
        [
            {
                "ligand_id": "lig_a",
                "mean_min_distance_A": 0.67,
                "contact_fraction": 0.6,
                "binding_energy_proxy": 0.1,
                "score_json": "old.json",
                "backmapped_pdb": "old.pdb",
            }
        ],
    )
    _write_attempt_state(old_attempt_dir, "old-fingerprint")
    runner_json = tmp_path / "runner.json"
    runner_json.write_text(
        json.dumps({"summary": {"attempt_id": "current_2", "input_fingerprint_sha256": "current-fingerprint"}}),
        encoding="utf-8",
    )

    payload = build_payload(attempts_root=str(attempts_root), runner_json=str(runner_json))

    summary = payload["summary"]
    assert summary["cohort_mode"] == "current_input_fingerprint"
    assert summary["observation_count"] == 3
    assert summary["excluded_noncohort_observation_count"] == 1
    row = payload["rows"][0]
    assert row["replicate_count"] == 3
    assert row["replicate_pass_fraction"] == 1.0
    assert row["mean_min_distance_iqr_A"] < 0.5
    assert row["replicate_evidence_input_fingerprint_sha256"] == "current-fingerprint"

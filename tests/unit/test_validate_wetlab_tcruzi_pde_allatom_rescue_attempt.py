from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.validate_wetlab_tcruzi_pde_allatom_rescue_attempt import main, validate


GOOD_SHA = "a" * 64


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ledger(tmp_path: Path) -> dict:
    trajectory = tmp_path / "traj" / "lig_a.npz"
    _touch(trajectory, "trajectory")
    return {
        "schema_version": "pde_allatom_rescue_input_fingerprint_v1",
        "lane_json": {"present": True, "sha256": GOOD_SHA},
        "stage1_queue_csv": {"present": True, "sha256": "b" * 64},
        "stage2_manifest_csv": {"present": True, "sha256": "c" * 64},
        "selected_manifest_rows_sha256": "d" * 64,
        "selected_queue_rows_sha256": "e" * 64,
        "selected_stage2_rows_sha256": "f" * 64,
        "selected_ligand_ids": ["lig_a"],
        "selected_stage2_trajectory_files": [
            {
                "ligand_id": "lig_a",
                "trajectory_npz": "lig_a.npz",
                "path": str(trajectory),
                "present": True,
                "size": len("trajectory"),
                "sha256": hashlib.sha256(b"trajectory").hexdigest(),
            }
        ],
    }


def _input_fingerprint(summary: dict, ledger: dict, *, execute: bool) -> str:
    basis = {
        "schema_version": "pde_allatom_rescue_attempt_v1",
        "settings": {
            "target_id": summary["target_id"],
            "shard_id": summary["shard_id"],
            "requested_top_k": summary["requested_top_k"],
            "actual_top_k": summary["top_k_effective"],
            "filter_mode_requested": summary["filter_mode_requested"],
            "filter_mode_applied": summary["filter_mode_applied"],
            "execute": execute,
            "selected_command_kind": summary["selected_command_kind"],
            "allatom_ligand_model": summary["allatom_ligand_model"],
            "clash_relief_mode": summary.get("clash_relief_mode", "off"),
            "clash_relief_target_min_distance_A": (
                summary.get("clash_relief_target_min_distance_A")
                if summary.get("clash_relief_mode", "off") != "off"
                else None
            ),
            "clash_relief_max_translation_A": (
                summary.get("clash_relief_max_translation_A")
                if summary.get("clash_relief_mode", "off") != "off"
                else None
            ),
            "clash_relief_max_steps": (
                summary.get("clash_relief_max_steps")
                if summary.get("clash_relief_mode", "off") != "off"
                else None
            ),
        },
        "inputs": ledger,
    }
    return _canonical_sha256(basis)


def _base_payload(tmp_path: Path, *, execute: bool = True, scoring_summary_present: bool = True) -> tuple[Path, dict]:
    ledger = _ledger(tmp_path)
    attempt_mode = "exec" if execute else "noexec"
    attempt_dir_base = tmp_path / "runs" / "wetlab_tcruzi_pde_allatom_rescue" / "t_cruzi_pde" / "20_of_20" / "top_1" / "attempts"
    current_json = tmp_path / "runs" / "wetlab_tcruzi_pde_allatom_rescue_current.json"
    summary = {
        "status": "wetlab_tcruzi_pde_allatom_rescue_ready",
        "target_id": "T. cruzi PDE",
        "shard_id": "20_of_20",
        "requested_top_k": 1,
        "top_k_effective": 1,
        "filter_mode_requested": "strict_then_near_fill",
        "filter_mode_applied": "strict_then_near_fill",
        "selected_command_kind": "pseudo_allatom_backmapping_rescore",
        "allatom_ligand_model": "3bead_implicit_hbond",
        "clash_relief_mode": "off",
        "clash_relief_target_min_distance_A": None,
        "clash_relief_max_translation_A": None,
        "clash_relief_max_steps": None,
        "attempt_id_source": "deterministic_input_fingerprint_sequence",
        "attempt_sequence": 1,
        "current_artifact_is_pointer": True,
        "execution_mode": "pseudo_allatom_backmapping_scoring_executed" if execute else "controller_manifest_only",
        "scoring_status": "pass" if execute and scoring_summary_present else ("error" if execute else "not_executed"),
        "scoring_returncode": 0 if execute and scoring_summary_present else (1 if execute else None),
        "scoring_summary_present": scoring_summary_present if execute else False,
        "scoring_expected_jobs": 1 if execute else 1,
        "processed_jobs": 1 if execute and scoring_summary_present else 0,
    }
    input_fp = _input_fingerprint(summary, ledger, execute=execute)
    attempt_id = f"inputfp_{input_fp[:12]}__{attempt_mode}__0001"
    attempt_dir = attempt_dir_base / attempt_id
    attempt_state_json = attempt_dir / "allatom_rescue_state.json"
    manifest_csv = attempt_dir / "allatom_rescue_manifest.csv"
    queue_csv = attempt_dir / "allatom_rescue_queue.csv"
    stage2_manifest_csv = attempt_dir / "allatom_rescue_stage2_manifest.csv"
    scoring_log = attempt_dir / "allatom_rescue_scoring.log"
    summary_json = attempt_dir / "allatom_rescue_summary.json"
    summary_md = attempt_dir / "allatom_rescue_summary.md"
    scores_csv = attempt_dir / "allatom_rescue_scores.csv"
    delivery_dir = attempt_dir / "allatom_delivery"

    for artifact in [manifest_csv, queue_csv, stage2_manifest_csv]:
        _touch(artifact, "ligand_id\nlig_a\n")
    if execute:
        _touch(scoring_log, "scoring log\n")
        _touch(summary_md, "# summary\n")
        delivery_dir.mkdir(parents=True, exist_ok=True)
        if scoring_summary_present:
            _write_json(summary_json, {"queue_rows": 1, "processed_jobs": 1})
            _touch(scores_csv, "ligand_id,score\nlig_a,1\n")

    summary.update(
        {
            "attempt_id": attempt_id,
            "input_fingerprint_sha256": input_fp,
            "attempt_dir": str(attempt_dir),
            "attempt_state_json": str(attempt_state_json),
            "current_pointer_json": str(current_json),
            "allatom_state_json": str(current_json),
            "attempt_artifacts": {
                "manifest_csv": str(manifest_csv),
                "queue_csv": str(queue_csv),
                "stage2_manifest_csv": str(stage2_manifest_csv),
                "state_json": str(attempt_state_json),
                "scoring_log": str(scoring_log),
                "summary_json": str(summary_json),
                "summary_md": str(summary_md),
                "scores_csv": str(scores_csv),
                "delivery_dir": str(delivery_dir),
            },
            "current_artifacts": {"state_json": str(current_json)},
        }
    )
    payload = {
        "summary": summary,
        "input_fingerprints": json.loads(json.dumps(ledger)),
        "input_fingerprint_ledger": json.loads(json.dumps(ledger)),
        "rows": [{"ligand_id": "lig_a", "rescue_execution_status": "execute_requested" if execute else "ready_manifest_only"}],
    }
    _write_json(attempt_state_json, payload)
    _write_json(current_json, payload)
    return current_json, payload


def _failed_checks(result: dict) -> set[str]:
    return {row["check"] for row in result["checks"] if row["status"] == "fail"}


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_pass_case(tmp_path: Path) -> None:
    current_json, _ = _base_payload(tmp_path, execute=True)
    out_json = tmp_path / "validation.json"
    out_md = tmp_path / "validation.md"

    assert main(["--rescue-json", str(current_json), "--out-json", str(out_json), "--out-md", str(out_md)]) == 0

    result = json.loads(out_json.read_text(encoding="utf-8"))
    assert result["summary"]["status"] == "pass"
    assert result["summary"]["rescue_attempt_validation"] == "pass"
    assert result["summary"]["overall_ok"] is True
    assert result["summary"]["failed_check_count"] == 0
    assert result["summary"]["input_fingerprint_recomputed_ok"] is True
    assert out_md.read_text(encoding="utf-8").startswith("# Wet-Lab T. cruzi PDE All-Atom Rescue Attempt Validation")


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_missing_artifact_fails(tmp_path: Path) -> None:
    current_json, payload = _base_payload(tmp_path, execute=True)
    Path(payload["summary"]["attempt_artifacts"]["queue_csv"]).unlink()

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "attempt_artifact_queue_csv_exists_under_attempt_dir" in _failed_checks(result)


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_bad_fingerprint_sha_fails(tmp_path: Path) -> None:
    current_json, payload = _base_payload(tmp_path, execute=True)
    payload["input_fingerprints"]["stage2_manifest_csv"]["sha256"] = "not-a-sha"
    payload["input_fingerprint_ledger"]["stage2_manifest_csv"]["sha256"] = "not-a-sha"
    _write_json(Path(payload["summary"]["attempt_state_json"]), payload)
    _write_json(current_json, payload)

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "fingerprint_stage2_manifest_csv_present_sha256" in _failed_checks(result)


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_no_execute_scoring_optional(tmp_path: Path) -> None:
    current_json, payload = _base_payload(tmp_path, execute=False)
    for key in ["scoring_log", "summary_json", "summary_md", "scores_csv", "delivery_dir"]:
        payload["summary"]["attempt_artifacts"].pop(key)
    _write_json(Path(payload["summary"]["attempt_state_json"]), payload)
    _write_json(current_json, payload)

    result = validate(current_json)

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["failed_check_count"] == 0
    optional_check = [row for row in result["checks"] if row["check"] == "no_execute_scoring_artifacts_optional"]
    assert optional_check == [
        {
            "check": "no_execute_scoring_artifacts_optional",
            "status": "pass",
            "severity": "info",
            "detail": "score/summary/scoring_log not required",
        }
    ]


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_recomputed_fingerprint_mismatch_fails(
    tmp_path: Path,
) -> None:
    current_json, payload = _base_payload(tmp_path, execute=True)
    payload["input_fingerprint_ledger"]["selected_ligand_ids"] = ["other_ligand"]
    payload["input_fingerprints"] = dict(payload["input_fingerprint_ledger"])
    _write_json(Path(payload["summary"]["attempt_state_json"]), payload)
    _write_json(current_json, payload)

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "input_fingerprint_recomputed_matches_summary" in _failed_checks(result)


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_attempt_id_mode_mismatch_fails(
    tmp_path: Path,
) -> None:
    current_json, payload = _base_payload(tmp_path, execute=True)
    bad_id = payload["summary"]["attempt_id"].replace("__exec__", "__noexec__")
    payload["summary"]["attempt_id"] = bad_id
    _write_json(Path(payload["summary"]["attempt_state_json"]), payload)
    _write_json(current_json, payload)

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "attempt_id_mode_matches_execution_mode" in _failed_checks(result)


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_pointer_mismatch_fails(tmp_path: Path) -> None:
    current_json, payload = _base_payload(tmp_path, execute=True)
    payload["summary"]["processed_jobs"] = 99
    _write_json(current_json, payload)

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "current_payload_matches_attempt_state" in _failed_checks(result)


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_execute_incomplete_fails(tmp_path: Path) -> None:
    current_json, _ = _base_payload(tmp_path, execute=True, scoring_summary_present=False)

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "executed_scoring_status_pass" in _failed_checks(result)
    assert "executed_scoring_summary_present" in _failed_checks(result)


def test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt_fingerprint_alias_mismatch_fails(
    tmp_path: Path,
) -> None:
    current_json, payload = _base_payload(tmp_path, execute=True)
    payload["input_fingerprints"]["selected_ligand_ids"] = ["different"]
    _write_json(Path(payload["summary"]["attempt_state_json"]), payload)
    _write_json(current_json, payload)

    result = validate(current_json)

    assert result["summary"]["status"] == "fail"
    assert "input_fingerprint_aliases_match" in _failed_checks(result)

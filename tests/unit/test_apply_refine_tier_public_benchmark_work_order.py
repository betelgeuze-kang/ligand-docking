from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.product import apply_refine_tier_public_benchmark_work_order as mod
from tools.product import build_refine_tier_public_benchmark_readiness as readiness


def _pdb_atom_lines(count: int) -> str:
    return "".join(
        f"ATOM  {idx:5d}  CA  ALA A{idx:4d}    {float(idx):8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C\n"
        for idx in range(1, count + 1)
    )


def _metric_source_payload(
    metric_name: str,
    *,
    target_id: str,
    pose_id: str,
    value: object,
    input_artifacts: list[str],
) -> str:
    return json.dumps(
        {
            "metric_name": metric_name,
            "target_id": target_id,
            "pose_id": pose_id,
            "value": value,
            "method": "fixture_reviewed_local_metric",
            "input_artifacts": input_artifacts,
            "input_artifact_sha256s": [
                hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
                if Path(artifact).is_file()
                else "0" * 64
                for artifact in input_artifacts
            ],
            "operator_id": "fixture_operator",
            "reviewed_at_utc": "2026-06-14T00:00:00Z",
            "license_ok": True,
            "external_engine_calls": 0,
        },
        sort_keys=True,
    ) + "\n"


def _write_work_order(path: Path, rows: list[dict[str, object]], *, source_artifacts: bool = True) -> None:
    if source_artifacts:
        evidence_dir = path.parent / "metric_source_artifacts"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for row in rows:
            target_id = str(row["target_id"])
            pose_id = readiness._pose_id_from_work_order_row(row)
            input_artifact = evidence_dir / f"{target_id}_{pose_id}_inputs.pdb"
            input_artifact.write_text("fixture local metric input\n", encoding="utf-8")
            row["_fixture_metric_input_artifact"] = str(input_artifact)
            input_artifacts = [str(input_artifact)]
            for field, suffix, metric_name, value_field in [
                ("dockq_source_artifact", "dockq.json", "dockq", "dockq"),
                ("lddt_pli_source_artifact", "lddt_pli.json", "lddt_pli", "lddt_pli"),
                (
                    "internal_deltaG_source_artifact",
                    "internal_deltaG.json",
                    "internal_deltaG",
                    "deltaG_mm_gbsa_kcal_mol",
                ),
            ]:
                artifact = evidence_dir / f"{target_id}_{suffix}"
                artifact.write_text(
                    _metric_source_payload(
                        metric_name,
                        target_id=target_id,
                        pose_id=pose_id,
                        value=row[value_field],
                        input_artifacts=input_artifacts,
                    ),
                    encoding="utf-8",
                )
                row[field] = str(artifact)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.WORK_ORDER_COLUMNS)
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in readiness.WORK_ORDER_COLUMNS} for row in rows)


def _write_validation_rows(path: Path, rows: list[dict[str, object]], *, status: str = "pass") -> None:
    validation_rows: list[dict[str, object]] = []
    coordinate_dir = path.parent / "receptor_coordinates"
    if status == "pass":
        coordinate_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        target_id = str(row["target_id"])
        pose_id = readiness._pose_id_from_work_order_row(row)
        receptor_artifact = coordinate_dir / f"{target_id}_{pose_id}_protein.pdb"
        if status == "pass":
            receptor_artifact.write_text(_pdb_atom_lines(40), encoding="utf-8")
            row["_fixture_receptor_coordinate_artifact"] = str(receptor_artifact)
        validation_rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": target_id,
                "pose_id": pose_id,
                "receptor_coordinate_artifact": str(receptor_artifact),
                "receptor_coordinate_artifact_present": status == "pass",
                "receptor_coordinate_artifact_sha256": (
                    hashlib.sha256(receptor_artifact.read_bytes()).hexdigest()
                    if receptor_artifact.is_file()
                    else ""
                ),
                "coordinate_source_kind": "local_file" if status == "pass" else "missing",
                "coordinate_parse_status": "parsed_coordinate_records" if status == "pass" else "missing",
                "coordinate_atom_record_count": 40 if status == "pass" else 0,
                "coordinate_pdb_atom_record_count": 40 if status == "pass" else 0,
                "coordinate_pdb_hetatm_record_count": 0,
                "coordinate_mol2_atom_record_count": 0,
                "coordinate_macromolecule_atom_record_count": 40 if status == "pass" else 0,
                "coordinate_distinct_residue_count": 10 if status == "pass" else 0,
                "coordinate_protein_like_atom_record_count": 40 if status == "pass" else 0,
                "coordinate_protein_like_residue_count": 10 if status == "pass" else 0,
                "coordinate_model_record_count": 0,
                "coordinate_validation_status": status,
                "blockers": "" if status == "pass" else "receptor_coordinate_missing",
                "next_required_science_input": "none" if status == "pass" else "validated_native_receptor_or_complex_coordinate",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.RECEPTOR_COORDINATE_VALIDATION_COLUMNS)
        writer.writeheader()
        writer.writerows(validation_rows)


def _write_metric_evidence_rows(path: Path, rows: list[dict[str, object]], *, status: str = "pass") -> None:
    metric_rows: list[dict[str, object]] = []
    for row in rows:
        pose_id = readiness._pose_id_from_work_order_row(row)
        required_input_artifacts: list[str] = []
        if status == "pass":
            required_input_artifacts = [
                str(
                    row.get("_fixture_metric_input_artifact")
                    or path.parent / "metric_source_artifacts" / f"{row['target_id']}_{pose_id}_inputs.pdb"
                ),
                str(
                    row.get("_fixture_receptor_coordinate_artifact")
                    or path.parent / "receptor_coordinates" / f"{row['target_id']}_{pose_id}_protein.pdb"
                ),
            ]
            for field, metric_name, value_field in [
                ("dockq_source_artifact", "dockq", "dockq"),
                ("lddt_pli_source_artifact", "lddt_pli", "lddt_pli"),
                ("internal_deltaG_source_artifact", "internal_deltaG", "deltaG_mm_gbsa_kcal_mol"),
            ]:
                source_path = Path(str(row.get(field, "")))
                if source_path.is_file():
                    source_path.write_text(
                        _metric_source_payload(
                            metric_name,
                            target_id=str(row["target_id"]),
                            pose_id=pose_id,
                            value=row[value_field],
                            input_artifacts=required_input_artifacts,
                        ),
                        encoding="utf-8",
                    )
        required_input_hashes = [
            hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
            if Path(artifact).is_file()
            else ""
            for artifact in required_input_artifacts
        ]
        metric_rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": row["target_id"],
                "pose_id": pose_id,
                "dockq": row["dockq"] if status == "pass" else "OPERATOR_FILL_DOCKQ",
                "lddt_pli": row["lddt_pli"] if status == "pass" else "OPERATOR_FILL_LDDT_PLI",
                "deltaG_mm_gbsa_kcal_mol": (
                    row["deltaG_mm_gbsa_kcal_mol"] if status == "pass" else "OPERATOR_FILL_INTERNAL_REFINE_DG"
                ),
                "dockq_source_artifact": row.get("dockq_source_artifact", f"fixtures/{row['target_id']}_dockq.json"),
                "lddt_pli_source_artifact": row.get("lddt_pli_source_artifact", f"fixtures/{row['target_id']}_lddt_pli.json"),
                "internal_deltaG_source_artifact": row.get(
                    "internal_deltaG_source_artifact",
                    f"fixtures/{row['target_id']}_internal_deltaG.json",
                ),
                "required_metric_input_artifacts": ";".join(required_input_artifacts),
                "required_metric_input_artifact_sha256s": ";".join(required_input_hashes),
                "missing_required_metric_input_artifacts": (
                    "" if status == "pass" else "ligand_pose_artifact;receptor_coordinate_artifact"
                ),
                "required_metric_source_payload_fields": (
                    "metric_name;target_id;pose_id;value;method;input_artifacts;"
                    "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls"
                ),
                "dockq_source_artifact_present": status == "pass",
                "lddt_pli_source_artifact_present": status == "pass",
                "internal_deltaG_source_artifact_present": status == "pass",
                "dockq_source_payload_valid": status == "pass",
                "lddt_pli_source_payload_valid": status == "pass",
                "internal_deltaG_source_payload_valid": status == "pass",
                "dockq_source_payload_blockers": "" if status == "pass" else "source_artifact_missing",
                "lddt_pli_source_payload_blockers": "" if status == "pass" else "source_artifact_missing",
                "internal_deltaG_source_payload_blockers": "" if status == "pass" else "source_artifact_missing",
                "metric_evidence_status": status,
                "blockers": "" if status == "pass" else "dockq_source_artifact_missing",
                "next_required_science_input": "none" if status == "pass" else "reviewed_local_metric_evidence_artifacts",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.METRIC_EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(metric_rows)


def _valid_work_order_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    proxy = [-9.0, -8.5, -8.0, -7.5, -7.0, -6.5, -6.0, -5.5]
    exp = [-10.0, -9.3, -8.7, -8.1, -7.2, -6.9, -6.1, -5.4]
    for idx, (pred, ref) in enumerate(zip(proxy, exp, strict=True)):
        split = "fit" if idx < 5 else "holdout"
        rows.append(
            {
                "work_order_id": f"refine_tier_public_benchmark_fill_{idx + 1:03d}",
                "target_input_csv": "config/refine_tier_public_benchmark_intake_current.csv",
                "template_row_index": idx + 1,
                "benchmark_id": f"curated_{idx:03d}",
                "target_id": f"T{idx:03d}",
                "benchmark_family": "pdbbind_or_casf_refine_tier_public",
                "split": split,
                "provenance_kind": "operator_curated_public",
                "provenance_id": f"PDB:{idx:04d}",
                "license_ok": "true",
                "external_engine_calls": 0,
                "pose_rmsd_A": 1.2,
                "dockq": 0.65,
                "lddt_pli": 0.82,
                "deltaG_mm_gbsa_kcal_mol": pred,
                "dockq_source_artifact": "",
                "lddt_pli_source_artifact": "",
                "internal_deltaG_source_artifact": "",
                "deltaG_experimental_kcal_mol": ref,
                "operator_action": "append_validated_public_benchmark_row",
                "acceptance_rule": "fixture",
                "external_state_mutated": False,
            }
        )
    return rows


def test_placeholder_work_order_blocks_without_writing_candidate(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    _write_work_order(work_order, readiness._build_operator_work_order_rows(
        input_csv="config/refine_tier_public_benchmark_intake_current.csv",
        existing_row_count=0,
        valid_row_count=0,
        pose_pass_count=0,
        free_energy_pair_count=0,
        fit_split_present=False,
        holdout_or_test_split_present=False,
        min_total_rows=8,
        min_pose_rows=5,
        min_free_energy_pairs=5,
    ))
    rows = _valid_work_order_rows()
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["candidate_intake_written"] is False
    assert summary["candidate_readiness_checked"] is False
    assert "blocked_work_order_rows_present" in summary["blockers"]
    assert "Fill or repair blocked work-order rows" in summary["next_required_step"]
    assert not candidate.exists()


def test_valid_work_order_writes_candidate_and_readiness_can_pass(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_work_order_apply_ready"
    assert summary["apply_ready"] is True
    assert summary["candidate_intake_written"] is True
    assert summary["candidate_readiness_checked"] is True
    assert summary["candidate_claim_grade_public_benchmark_ready"] is True
    assert summary["receptor_coordinate_validation_required"] is True
    assert summary["receptor_coordinate_validation_pass_row_count"] == 8
    assert summary["receptor_coordinate_validation_blocked_row_count"] == 0
    assert summary["metric_evidence_required"] is True
    assert summary["metric_evidence_pass_row_count"] == 8
    assert summary["metric_evidence_blocked_row_count"] == 0
    assert summary["valid_intake_row_count"] == 8
    assert summary["write_intake_command"].endswith(
        "--write-intake --approval-token APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    )
    assert summary["approval_token_required"] == ""
    assert summary["approval_token_accepted"] is False
    assert "Review the candidate intake CSV" in summary["next_required_step"]
    assert candidate.read_text(encoding="utf-8").startswith("benchmark_id,target_id,")

    ready = readiness.build_refine_tier_public_benchmark_readiness(input_csv=candidate)
    assert ready["summary"]["claim_grade_public_benchmark_ready"] is True


def test_valid_numbers_block_without_receptor_coordinate_validation_pass(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="blocked")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["candidate_intake_written"] is False
    assert summary["candidate_readiness_checked"] is False
    assert summary["receptor_coordinate_validation_pass_row_count"] == 0
    assert summary["receptor_coordinate_validation_blocked_row_count"] == 8
    assert "receptor_coordinate_validation_not_pass" in row_blockers
    assert "blocked_work_order_rows_present" in summary["blockers"]
    assert not candidate.exists()


def test_receptor_coordinate_validation_pass_csv_must_match_work_order_target_and_pose(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    validation_rows = list(csv.DictReader(validation.open("r", encoding="utf-8", newline="")))
    validation_rows[0]["target_id"] = "OTHER_TARGET"
    validation_rows[0]["pose_id"] = "OTHER_POSE"
    with validation.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.RECEPTOR_COORDINATE_VALIDATION_COLUMNS)
        writer.writeheader()
        writer.writerows(validation_rows)
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["receptor_coordinate_validation_contract_blocked_row_count"] == 1
    assert "receptor_coordinate_validation_target_mismatch" in row_blockers
    assert "receptor_coordinate_validation_pose_mismatch" in row_blockers
    assert not candidate.exists()


def test_receptor_coordinate_validation_pass_csv_must_bind_coordinate_hash(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    validation_rows = list(csv.DictReader(validation.open("r", encoding="utf-8", newline="")))
    validation_rows[0]["receptor_coordinate_artifact_sha256"] = "0" * 64
    with validation.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.RECEPTOR_COORDINATE_VALIDATION_COLUMNS)
        writer.writeheader()
        writer.writerows(validation_rows)
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["receptor_coordinate_validation_contract_blocked_row_count"] == 1
    assert "receptor_coordinate_validation_artifact_sha256_mismatch" in row_blockers
    assert not candidate.exists()


def test_receptor_coordinate_validation_pass_csv_must_recompute_coordinate_artifact(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    validation_rows = list(csv.DictReader(validation.open("r", encoding="utf-8", newline="")))
    Path(validation_rows[0]["receptor_coordinate_artifact"]).write_text(_pdb_atom_lines(3), encoding="utf-8")
    with validation.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.RECEPTOR_COORDINATE_VALIDATION_COLUMNS)
        writer.writeheader()
        writer.writerows(validation_rows)
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["receptor_coordinate_validation_contract_blocked_row_count"] == 1
    assert "receptor_coordinate_validation_atom_record_count_below_min" in row_blockers
    assert not candidate.exists()


def test_valid_numbers_block_without_metric_evidence_pass(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="blocked")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["candidate_intake_written"] is False
    assert summary["candidate_readiness_checked"] is False
    assert summary["metric_evidence_pass_row_count"] == 0
    assert summary["metric_evidence_blocked_row_count"] == 8
    assert "metric_evidence_not_pass" in row_blockers
    assert "blocked_work_order_rows_present" in summary["blockers"]
    assert not candidate.exists()


def test_metric_evidence_pass_csv_must_match_work_order_target_pose_and_sources(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")
    metric_rows = list(csv.DictReader(metric_evidence.open("r", encoding="utf-8", newline="")))
    metric_rows[0]["target_id"] = "OTHER_TARGET"
    metric_rows[0]["pose_id"] = "OTHER_POSE"
    metric_rows[0]["dockq_source_artifact"] = str(tmp_path / "other_dockq.json")
    with metric_evidence.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.METRIC_EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(metric_rows)

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["metric_evidence_contract_blocked_row_count"] == 1
    assert "metric_evidence_target_mismatch" in row_blockers
    assert "metric_evidence_pose_mismatch" in row_blockers
    assert "metric_evidence_dockq_source_artifact_mismatch" in row_blockers
    assert not candidate.exists()


def test_metric_evidence_pass_csv_must_bind_required_receptor_coordinate_input(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")
    metric_rows = list(csv.DictReader(metric_evidence.open("r", encoding="utf-8", newline="")))
    required_inputs = metric_rows[0]["required_metric_input_artifacts"].split(";")
    required_hashes = metric_rows[0]["required_metric_input_artifact_sha256s"].split(";")
    metric_rows[0]["required_metric_input_artifacts"] = required_inputs[0]
    metric_rows[0]["required_metric_input_artifact_sha256s"] = required_hashes[0]
    with metric_evidence.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.METRIC_EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(metric_rows)

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["metric_evidence_contract_blocked_row_count"] == 1
    assert payload["summary"]["metric_evidence_missing_required_receptor_input_row_count"] == 1
    assert payload["summary"]["metric_evidence_required_input_sha256_blocked_row_count"] == 1
    assert "metric_evidence_required_input_receptor_coordinate_missing" in row_blockers
    assert "metric_evidence_required_input_receptor_coordinate_sha256_missing" in row_blockers
    assert not candidate.exists()


def test_valid_numbers_and_pass_csv_block_without_local_metric_source_artifacts(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows, source_artifacts=False)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["metric_evidence_pass_row_count"] == 8
    assert summary["metric_evidence_missing_dockq_source_row_count"] == 8
    assert summary["metric_evidence_missing_lddt_pli_source_row_count"] == 8
    assert summary["metric_evidence_missing_internal_deltaG_source_row_count"] == 8
    assert "dockq_source_artifact_missing" in row_blockers
    assert "lddt_pli_source_artifact_missing" in row_blockers
    assert "internal_deltaG_source_artifact_missing" in row_blockers
    assert not candidate.exists()


def test_pass_csv_blocks_when_local_metric_source_payload_is_invalid(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")
    Path(str(rows[0]["dockq_source_artifact"])).write_text('{"source":"fixture"}\n', encoding="utf-8")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["metric_evidence_pass_row_count"] == 8
    assert summary["metric_evidence_invalid_dockq_source_payload_row_count"] == 1
    assert "metric_source_payloads_invalid" in row_blockers
    assert payload["rows"][0]["dockq_source_payload_valid"] is False
    assert "source_payload_required_fields_missing" in payload["rows"][0]["dockq_source_payload_blockers"]
    assert not candidate.exists()


def test_pass_csv_blocks_when_metric_payload_input_artifact_is_missing(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")
    Path(str(rows[0]["dockq_source_artifact"])).write_text(
        _metric_source_payload(
            "dockq",
            target_id=str(rows[0]["target_id"]),
            pose_id=readiness._pose_id_from_work_order_row(rows[0]),
            value=rows[0]["dockq"],
            input_artifacts=[str(tmp_path / "missing_inputs" / "pose_or_receptor.pdb")],
        ),
        encoding="utf-8",
    )

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["metric_evidence_invalid_dockq_source_payload_row_count"] == 1
    assert "metric_source_payloads_invalid" in row_blockers
    assert payload["rows"][0]["dockq_source_payload_valid"] is False
    assert "source_payload_input_artifacts_not_found" in payload["rows"][0]["dockq_source_payload_blockers"]
    assert not candidate.exists()


def test_pass_csv_blocks_when_metric_payload_input_artifact_hash_mismatches(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")
    first_payload_path = Path(str(rows[0]["dockq_source_artifact"]))
    first_payload = json.loads(first_payload_path.read_text(encoding="utf-8"))
    first_payload["input_artifact_sha256s"] = ["0" * 64]
    first_payload_path.write_text(json.dumps(first_payload, sort_keys=True) + "\n", encoding="utf-8")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["metric_evidence_invalid_dockq_source_payload_row_count"] == 1
    assert "metric_source_payloads_invalid" in row_blockers
    assert payload["rows"][0]["dockq_source_payload_valid"] is False
    assert "source_payload_input_artifact_sha256_mismatch" in payload["rows"][0]["dockq_source_payload_blockers"]
    assert not candidate.exists()


def test_row_valid_but_aggregate_readiness_blocks_candidate(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()[:5]
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    summary = payload["summary"]

    assert summary["apply_ready"] is False
    assert summary["candidate_intake_written"] is False
    assert summary["candidate_claim_grade_public_benchmark_ready"] is False
    assert "candidate_readiness_gate_not_ready" in summary["blockers"]
    assert "insufficient_total_rows" in summary["candidate_readiness_blockers"]
    assert "aggregate readiness gate" in summary["next_required_step"]
    assert not candidate.exists()


def test_write_intake_requires_all_rows_to_pass(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    target = tmp_path / "intake.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    rows[0]["external_engine_calls"] = 1
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        target_intake_csv=target,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
        write_intake=True,
    )

    assert payload["summary"]["intake_written"] is False
    assert "write_intake_blocked_until_work_order_rows_pass" in payload["summary"]["blockers"]
    assert "write_intake_approval_token_missing_or_invalid" in payload["summary"]["blockers"]
    assert "Fill or repair blocked work-order rows" in payload["summary"]["next_required_step"]
    assert not target.exists()


def test_write_intake_requires_approval_token_even_when_candidate_ready(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    target = tmp_path / "intake.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    for row in rows:
        row["target_input_csv"] = str(target)
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        target_intake_csv=target,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
        write_intake=True,
    )
    summary = payload["summary"]

    assert summary["apply_ready"] is False
    assert summary["candidate_readiness_checked"] is True
    assert summary["candidate_claim_grade_public_benchmark_ready"] is True
    assert summary["approval_token_required"] == "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    assert summary["approval_token_present"] is False
    assert summary["approval_token_accepted"] is False
    assert "write_intake_approval_token_missing_or_invalid" in summary["blockers"]
    assert "required approval token" in summary["next_required_step"]
    assert not target.exists()


def test_write_intake_with_approval_token_writes_target_intake(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    target = tmp_path / "intake.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    for row in rows:
        row["target_input_csv"] = str(target)
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        target_intake_csv=target,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
        write_intake=True,
        approval_token="APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE",
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_intake_written"
    assert summary["apply_ready"] is True
    assert summary["approval_token_present"] is True
    assert summary["approval_token_accepted"] is True
    assert summary["intake_written"] is True
    assert target.read_text(encoding="utf-8").startswith("benchmark_id,target_id,")


def test_apply_blocks_wrong_target_action_mutation_and_duplicate_ids(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    rows[0]["target_input_csv"] = "config/other_intake.csv"
    rows[1]["operator_action"] = "manual_copy_without_validation"
    rows[2]["external_state_mutated"] = "true"
    rows[3]["benchmark_id"] = rows[4]["benchmark_id"]
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        out_csv=candidate,
        receptor_coordinate_validation_csv=validation,
        metric_evidence_csv=metric_evidence,
    )
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["duplicate_benchmark_id_count"] == 1
    assert payload["summary"]["candidate_readiness_checked"] is False
    assert "target_input_csv_mismatch" in row_blockers
    assert "operator_action_unaccepted" in row_blockers
    assert "external_state_mutation_declared" in row_blockers
    assert "duplicate_benchmark_id" in row_blockers
    assert not candidate.exists()


def test_cli_writes_json_candidate_and_markdown(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    out_json = tmp_path / "apply.json"
    candidate = tmp_path / "candidate.csv"
    out_md = tmp_path / "apply.md"
    validation = tmp_path / "validation.csv"
    metric_evidence = tmp_path / "metric_evidence.csv"
    rows = _valid_work_order_rows()
    _write_work_order(work_order, rows)
    _write_validation_rows(validation, rows, status="pass")
    _write_metric_evidence_rows(metric_evidence, rows, status="pass")

    mod.main(
        [
            "--work-order-csv",
            str(work_order),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(candidate),
            "--receptor-coordinate-validation-csv",
            str(validation),
            "--metric-evidence-csv",
            str(metric_evidence),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["apply_ready"] is True
    assert payload["summary"]["candidate_readiness_checked"] is True
    assert candidate.exists()
    assert "Refine Tier Public Benchmark Work Order Apply" in out_md.read_text(encoding="utf-8")
    assert "candidate_readiness_status" in out_md.read_text(encoding="utf-8")

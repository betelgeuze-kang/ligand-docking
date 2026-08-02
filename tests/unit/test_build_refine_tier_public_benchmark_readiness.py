from __future__ import annotations

import csv
import hashlib
import json
import tarfile
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_readiness as mod

SEED_COLUMNS = ["suite_id", "complex_id", "pose_id", "pose_rmsd_A", "blocker_count", "blockers"]


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_seed_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SEED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_affinity_rows(path: Path, rows: dict[str, float]) -> None:
    path.write_text(
        "".join(f"{complex_id}\t{paffinity}\n" for complex_id, paffinity in rows.items()),
        encoding="utf-8",
    )


def _metric_source_payload(
    metric_name: str,
    *,
    target_id: str,
    pose_id: str,
    value: float,
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


def _pdb_atom_lines(count: int) -> str:
    return "".join(
        f"ATOM  {idx:5d}  CA  ALA A{idx:4d}    {float(idx):8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C\n"
        for idx in range(1, count + 1)
    )


def _mol2_atom_lines(count: int, *, residue_count: int = 1, residue_names: list[str] | None = None) -> str:
    lines = ["@<TRIPOS>MOLECULE\n", "fixture\n", f"{count} 0 0 0 0\n", "@<TRIPOS>ATOM\n"]
    for idx in range(1, count + 1):
        residue_id = ((idx - 1) % residue_count) + 1
        residue_name = residue_names[residue_id - 1] if residue_names and residue_id <= len(residue_names) else f"RES{residue_id}"
        lines.append(
            f"{idx:7d} C{idx:<3d} {float(idx):9.4f} 0.0000 0.0000 C.3 {residue_id:4d} {residue_name:<6s} 0.0000\n"
        )
    lines.append("@<TRIPOS>BOND\n")
    return "".join(lines)


def _ready_rows(source_dir: Path) -> list[dict[str, object]]:
    source_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    proxy = [-9.0, -8.5, -8.0, -7.5, -7.0, -6.5, -6.0, -5.5]
    exp = [-10.0, -9.3, -8.7, -8.1, -7.2, -6.9, -6.1, -5.4]
    for idx, (pred, ref) in enumerate(zip(proxy, exp, strict=True)):
        dockq_source = source_dir / f"curated_{idx:03d}_dockq.json"
        lddt_source = source_dir / f"curated_{idx:03d}_lddt_pli.json"
        internal_delta_g_source = source_dir / f"curated_{idx:03d}_internal_deltaG.json"
        target_id = f"T{idx:03d}"
        pose_id = f"{idx:04d}"
        input_artifact = source_dir / f"curated_{idx:03d}_{pose_id}_inputs.pdb"
        input_artifact.write_text(_pdb_atom_lines(20), encoding="utf-8")
        input_artifacts = [str(input_artifact)]
        dockq_source.write_text(
            _metric_source_payload(
                "dockq",
                target_id=target_id,
                pose_id=pose_id,
                value=0.65,
                input_artifacts=input_artifacts,
            ),
            encoding="utf-8",
        )
        lddt_source.write_text(
            _metric_source_payload(
                "lddt_pli",
                target_id=target_id,
                pose_id=pose_id,
                value=0.82,
                input_artifacts=input_artifacts,
            ),
            encoding="utf-8",
        )
        internal_delta_g_source.write_text(
            _metric_source_payload(
                "internal_deltaG",
                target_id=target_id,
                pose_id=pose_id,
                value=pred,
                input_artifacts=input_artifacts,
            ),
            encoding="utf-8",
        )
        rows.append(
            {
                "benchmark_id": f"curated_{idx:03d}",
                "target_id": target_id,
                "benchmark_family": "pdbbind_core_refine_tier_v1",
                "split": "fit" if idx < 5 else "holdout",
                "provenance_kind": "operator_curated_public",
                "provenance_id": f"PDB:{idx:04d}",
                "license_ok": "true",
                "external_engine_calls": 0,
                "pose_rmsd_A": 1.2,
                "dockq": 0.65,
                "lddt_pli": 0.82,
                "internal_refine_proxy_score": pred,
                "dockq_source_artifact": str(dockq_source),
                "lddt_pli_source_artifact": str(lddt_source),
                "internal_deltaG_source_artifact": str(internal_delta_g_source),
                "deltaG_experimental_kcal_mol": ref,
            }
        )
    return rows


def test_missing_input_blocks_without_external_mutation(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=missing,
        work_order_seed_csv=tmp_path / "missing_seed.csv",
        work_order_affinity_tsv=tmp_path / "missing_affinity.tsv",
        work_order_dataset_dir=tmp_path / "missing_dataset",
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_readiness"
    assert summary["claim_grade_public_benchmark_ready"] is False
    assert summary["external_state_mutated"] is False
    assert "input_csv_missing" in summary["blockers"]
    assert summary["operator_work_order_ready"] is True
    assert summary["work_order_row_count"] == 8
    assert summary["work_order_seeded_row_count"] == 0
    assert summary["work_order_prefilled_operator_field_count"] == 0
    assert summary["work_order_pending_operator_field_count"] == 96
    assert summary["work_order_science_input_gap_row_count"] == 8
    assert summary["work_order_science_input_gap_blocked_row_count"] == 8
    assert summary["work_order_local_ligand_pose_artifact_count"] == 0
    assert summary["work_order_missing_ligand_pose_artifact_count"] == 8
    assert summary["work_order_missing_receptor_coordinate_row_count"] == 8
    assert summary["work_order_missing_interaction_metric_source_row_count"] == 8
    assert summary["work_order_missing_internal_deltaG_source_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_matched_row_count"] == 0
    assert summary["work_order_receptor_coordinate_intake_missing_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_suggested_public_url_row_count"] == 0
    assert summary["work_order_receptor_coordinate_intake_suggested_local_path_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_operator_review_required_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_ready_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_blocked_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_missing_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_below_min_macromolecule_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_protein_like_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_min_atom_records"] == 20
    assert summary["work_order_receptor_coordinate_validation_min_macromolecule_atom_records"] == 20
    assert summary["work_order_receptor_coordinate_validation_min_distinct_residues"] == 5
    assert summary["work_order_receptor_coordinate_validation_min_protein_like_residues"] == 5
    assert summary["work_order_metric_evidence_required"] is True
    assert summary["work_order_metric_evidence_row_count"] == 8
    assert summary["work_order_metric_evidence_ready_row_count"] == 0
    assert summary["work_order_metric_evidence_blocked_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_dockq_source_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_lddt_pli_source_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_internal_deltaG_source_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_required_input_artifact_row_count"] == 8
    assert summary["work_order_tar_ligand_pose_member_count"] == 0
    assert summary["work_order_tar_ligand_only_archive_count"] == 0
    assert len(payload["work_order_rows"]) == 8
    assert len(payload["science_input_gap_rows"]) == 8
    assert len(payload["receptor_coordinate_intake_rows"]) == 8
    assert len(payload["receptor_coordinate_validation_rows"]) == 8
    assert len(payload["metric_evidence_rows"]) == 8
    assert payload["metric_evidence_rows"][0]["expected_dockq_source_artifact"].endswith("_dockq.json")
    assert payload["metric_evidence_rows"][0]["expected_lddt_pli_source_artifact"].endswith("_lddt_pli.json")
    assert payload["metric_evidence_rows"][0]["expected_internal_deltaG_source_artifact"].endswith(
        "_internal_deltaG.json"
    )
    assert "reviewed_at_utc" in payload["metric_evidence_rows"][0]["required_metric_source_payload_fields"]
    assert "input_artifact_sha256s" in payload["metric_evidence_rows"][0]["required_metric_source_payload_fields"]
    assert payload["metric_evidence_rows"][0]["required_metric_input_artifacts"] == ""
    assert payload["metric_evidence_rows"][0]["missing_required_metric_input_artifacts"] == (
        "ligand_pose_artifact;receptor_coordinate_artifact"
    )
    assert payload["metric_evidence_rows"][0]["metric_evidence_next_operator_action"] == (
        "place_reviewed_local_metric_evidence_artifacts_and_copy_paths_into_work_order"
    )
    assert payload["work_order_rows"][0]["external_engine_calls"] == 0
    assert {row["split"] for row in payload["work_order_rows"]} == {"fit", "holdout"}
    assert summary["work_order_apply_command"].endswith("apply_refine_tier_public_benchmark_work_order.py")
    assert summary["work_order_apply_write_intake_command"].endswith(
        "--write-intake --approval-token APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    )
    assert summary["write_intake_approval_token_required"] == "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    assert "apply command" in summary["next_required_step"]


def test_ready_rows_pass_claim_grade_public_benchmark_gate(tmp_path: Path) -> None:
    csv_path = tmp_path / "ready.csv"
    _write_rows(csv_path, _ready_rows(tmp_path / "metric_sources"))

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=csv_path,
        work_order_seed_csv=tmp_path / "missing_seed.csv",
        work_order_affinity_tsv=tmp_path / "missing_affinity.tsv",
        work_order_dataset_dir=tmp_path / "missing_dataset",
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_ready"
    assert summary["claim_grade_public_benchmark_ready"] is True
    assert summary["valid_row_count"] == 8
    assert summary["pose_metric_pass_count"] == 8
    assert summary["free_energy_pair_count"] == 8
    assert summary["fit_split_present"] is True
    assert summary["holdout_or_test_split_present"] is True
    assert float(summary["free_energy_spearman"]) > 0.9
    assert summary["operator_work_order_ready"] is False
    assert summary["work_order_row_count"] == 0
    assert payload["work_order_rows"] == []
    assert summary["next_required_step"] == "Public benchmark readiness is ready; no work-order apply step is required."


def test_metric_source_payload_schema_is_required(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid_payload.csv"
    rows = _ready_rows(tmp_path / "metric_sources")
    Path(str(rows[0]["dockq_source_artifact"])).write_text('{"source":"fixture"}\n', encoding="utf-8")
    _write_rows(csv_path, rows)

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=csv_path,
        work_order_seed_csv=tmp_path / "missing_seed.csv",
        work_order_affinity_tsv=tmp_path / "missing_affinity.tsv",
        work_order_dataset_dir=tmp_path / "missing_dataset",
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["claim_grade_public_benchmark_ready"] is False
    assert "insufficient_valid_rows" in summary["blockers"]
    assert "metric_source_payloads_invalid" in row_blockers
    assert payload["rows"][0]["dockq_source_artifact_present"] is True
    assert payload["rows"][0]["dockq_source_payload_valid"] is False
    assert "source_payload_required_fields_missing" in payload["rows"][0]["dockq_source_payload_blockers"]


def test_metric_source_payload_input_artifacts_must_exist(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing_metric_inputs.csv"
    rows = _ready_rows(tmp_path / "metric_sources")
    Path(str(rows[0]["dockq_source_artifact"])).write_text(
        _metric_source_payload(
            "dockq",
            target_id=str(rows[0]["target_id"]),
            pose_id="0000",
            value=0.65,
            input_artifacts=[str(tmp_path / "missing_inputs" / "pose_or_receptor.pdb")],
        ),
        encoding="utf-8",
    )
    _write_rows(csv_path, rows)

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=csv_path,
        work_order_seed_csv=tmp_path / "missing_seed.csv",
        work_order_affinity_tsv=tmp_path / "missing_affinity.tsv",
        work_order_dataset_dir=tmp_path / "missing_dataset",
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["claim_grade_public_benchmark_ready"] is False
    assert "metric_source_payloads_invalid" in row_blockers
    assert payload["rows"][0]["dockq_source_payload_valid"] is False
    assert "source_payload_input_artifacts_not_found" in payload["rows"][0]["dockq_source_payload_blockers"]


def test_metric_source_payload_input_artifact_hash_must_match(tmp_path: Path) -> None:
    csv_path = tmp_path / "mismatched_metric_input_hash.csv"
    rows = _ready_rows(tmp_path / "metric_sources")
    first_payload_path = Path(str(rows[0]["dockq_source_artifact"]))
    first_payload = json.loads(first_payload_path.read_text(encoding="utf-8"))
    first_payload["input_artifact_sha256s"] = ["0" * 64]
    first_payload_path.write_text(json.dumps(first_payload, sort_keys=True) + "\n", encoding="utf-8")
    _write_rows(csv_path, rows)

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=csv_path,
        work_order_seed_csv=tmp_path / "missing_seed.csv",
        work_order_affinity_tsv=tmp_path / "missing_affinity.tsv",
        work_order_dataset_dir=tmp_path / "missing_dataset",
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["claim_grade_public_benchmark_ready"] is False
    assert "metric_source_payloads_invalid" in row_blockers
    assert payload["rows"][0]["dockq_source_payload_valid"] is False
    assert "source_payload_input_artifact_sha256_mismatch" in payload["rows"][0]["dockq_source_payload_blockers"]


def test_external_engine_and_missing_provenance_block(tmp_path: Path) -> None:
    rows = _ready_rows(tmp_path / "metric_sources")
    rows[0]["external_engine_calls"] = 1
    rows[1]["provenance_id"] = ""
    csv_path = tmp_path / "blocked.csv"
    _write_rows(csv_path, rows)

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=csv_path,
        work_order_seed_csv=tmp_path / "missing_seed.csv",
        work_order_affinity_tsv=tmp_path / "missing_affinity.tsv",
        work_order_dataset_dir=tmp_path / "missing_dataset",
    )
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["claim_grade_public_benchmark_ready"] is False
    assert "insufficient_valid_rows" in summary["blockers"]
    assert "external_engine_calls_present" in row_blockers
    assert "provenance_missing_or_unaccepted" in row_blockers


def test_cli_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    input_csv = tmp_path / "ready.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_work_order_csv = tmp_path / "work_order.csv"
    out_science_input_gap_csv = tmp_path / "science_input_gap.csv"
    out_receptor_coordinate_intake_csv = tmp_path / "receptor_coordinate_intake.csv"
    out_receptor_coordinate_validation_csv = tmp_path / "receptor_coordinate_validation.csv"
    out_metric_evidence_csv = tmp_path / "metric_evidence.csv"
    out_md = tmp_path / "out.md"
    _write_rows(input_csv, _ready_rows(tmp_path / "metric_sources"))

    mod.main(
        [
            "--input-csv",
            str(input_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-work-order-csv",
            str(out_work_order_csv),
            "--out-science-input-gap-csv",
            str(out_science_input_gap_csv),
            "--out-receptor-coordinate-intake-csv",
            str(out_receptor_coordinate_intake_csv),
            "--out-receptor-coordinate-validation-csv",
            str(out_receptor_coordinate_validation_csv),
            "--out-metric-evidence-csv",
            str(out_metric_evidence_csv),
            "--work-order-seed-csv",
            str(tmp_path / "missing_seed.csv"),
            "--work-order-affinity-tsv",
            str(tmp_path / "missing_affinity.tsv"),
            "--work-order-dataset-dir",
            str(tmp_path / "missing_dataset"),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["claim_grade_public_benchmark_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("benchmark_id,")
    assert out_work_order_csv.read_text(encoding="utf-8") == ""
    assert out_science_input_gap_csv.read_text(encoding="utf-8") == ""
    assert out_receptor_coordinate_intake_csv.read_text(encoding="utf-8") == ""
    assert out_receptor_coordinate_validation_csv.read_text(encoding="utf-8") == ""
    assert out_metric_evidence_csv.read_text(encoding="utf-8") == ""
    assert "Refine Tier Public Benchmark Readiness" in out_md.read_text(encoding="utf-8")


def test_cli_writes_operator_work_order_for_empty_intake(tmp_path: Path) -> None:
    input_csv = tmp_path / "empty.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_work_order_csv = tmp_path / "work_order.csv"
    out_science_input_gap_csv = tmp_path / "science_input_gap.csv"
    out_receptor_coordinate_intake_csv = tmp_path / "receptor_coordinate_intake.csv"
    out_receptor_coordinate_validation_csv = tmp_path / "receptor_coordinate_validation.csv"
    out_metric_evidence_csv = tmp_path / "metric_evidence.csv"
    out_md = tmp_path / "out.md"
    input_csv.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n", encoding="utf-8")

    mod.main(
        [
            "--input-csv",
            str(input_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-work-order-csv",
            str(out_work_order_csv),
            "--out-science-input-gap-csv",
            str(out_science_input_gap_csv),
            "--out-receptor-coordinate-intake-csv",
            str(out_receptor_coordinate_intake_csv),
            "--out-receptor-coordinate-validation-csv",
            str(out_receptor_coordinate_validation_csv),
            "--out-metric-evidence-csv",
            str(out_metric_evidence_csv),
            "--work-order-seed-csv",
            str(tmp_path / "missing_seed.csv"),
            "--work-order-affinity-tsv",
            str(tmp_path / "missing_affinity.tsv"),
            "--work-order-dataset-dir",
            str(tmp_path / "missing_dataset"),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["operator_work_order_ready"] is True
    assert payload["summary"]["work_order_row_count"] == 8
    assert "work_order_id,target_input_csv" in out_work_order_csv.read_text(encoding="utf-8")
    assert "work_order_id,target_id,pose_id" in out_science_input_gap_csv.read_text(encoding="utf-8")
    assert "accepted_offline_coordinate_patterns" in out_receptor_coordinate_intake_csv.read_text(encoding="utf-8")
    assert "suggested_public_coordinate_urls" in out_receptor_coordinate_intake_csv.read_text(encoding="utf-8")
    assert "coordinate_validation_status" in out_receptor_coordinate_validation_csv.read_text(encoding="utf-8")
    assert "metric_evidence_status" in out_metric_evidence_csv.read_text(encoding="utf-8")
    assert "Operator Work Order" in out_md.read_text(encoding="utf-8")
    assert "receptor-coordinate validation CSV" in out_md.read_text(encoding="utf-8")
    assert "metric-evidence CSV" in out_md.read_text(encoding="utf-8")
    assert "apply_refine_tier_public_benchmark_work_order.py" in out_md.read_text(encoding="utf-8")


def test_empty_intake_uses_pose_benchmark_seed_for_work_order(tmp_path: Path) -> None:
    input_csv = tmp_path / "empty.csv"
    seed_csv = tmp_path / "seed.csv"
    affinity_tsv = tmp_path / "affinity.tsv"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "data_5_sdf").mkdir()
    input_csv.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    seed_rows = [
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": f"C{idx:03d}",
            "pose_id": f"C{idx:03d}_pose",
            "pose_rmsd_A": 1.0 + idx * 0.1,
            "blocker_count": 0,
            "blockers": "",
        }
        for idx in range(8)
    ]
    affinity_rows = {f"c{idx:03d}": 7.0 + idx * 0.1 for idx in range(8)}
    seed_rows.append(
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": "C000",
            "pose_id": "C000_worse_pose",
            "pose_rmsd_A": 2.4,
            "blocker_count": 0,
            "blockers": "",
        }
    )
    _write_seed_rows(seed_csv, seed_rows)
    _write_affinity_rows(affinity_tsv, affinity_rows)
    for idx in range(8):
        (dataset_dir / "data_5_sdf" / f"C{idx:03d}_pose").write_text("ligand", encoding="utf-8")
    with tarfile.open(dataset_dir / "CASF-2016_scoring.tar.xz", "w:xz") as handle:
        handle.add(dataset_dir / "data_5_sdf" / "C000_pose", arcname="data_5_sdf/C000_pose")

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=input_csv,
        work_order_seed_csv=seed_csv,
        work_order_affinity_tsv=affinity_tsv,
        work_order_dataset_dir=dataset_dir,
    )
    summary = payload["summary"]
    first_row = payload["work_order_rows"][0]

    assert summary["operator_work_order_ready"] is True
    assert summary["work_order_row_count"] == 8
    assert summary["work_order_seeded_row_count"] == 8
    assert summary["work_order_seed_candidate_row_count"] == 9
    assert summary["work_order_seed_distinct_target_count"] == 8
    assert summary["work_order_operator_field_count"] == 96
    assert summary["work_order_prefilled_operator_field_count"] == 40
    assert summary["work_order_pending_operator_field_count"] == 56
    assert summary["work_order_pending_license_ok_count"] == 8
    assert summary["work_order_pending_dockq_count"] == 8
    assert summary["work_order_pending_lddt_pli_count"] == 8
    assert summary["work_order_pending_internal_deltaG_count"] == 8
    assert summary["work_order_pending_experimental_deltaG_count"] == 0
    assert summary["work_order_remaining_nonlicense_science_field_count"] == 48
    assert summary["work_order_remaining_receptor_interaction_metric_field_count"] == 32
    assert summary["work_order_remaining_internal_refine_deltaG_field_count"] == 16
    assert summary["work_order_current_local_source_prefill_ready_field_count"] == 0
    assert summary["work_order_science_input_gap_row_count"] == 8
    assert summary["work_order_science_input_gap_blocked_row_count"] == 8
    assert summary["work_order_local_ligand_pose_artifact_count"] == 8
    assert summary["work_order_missing_ligand_pose_artifact_count"] == 0
    assert summary["work_order_receptor_coordinate_ready_row_count"] == 0
    assert summary["work_order_missing_receptor_coordinate_row_count"] == 8
    assert summary["work_order_ligand_pose_only_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_matched_row_count"] == 0
    assert summary["work_order_receptor_coordinate_intake_missing_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_suggested_public_url_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_suggested_local_path_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_operator_review_required_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_ready_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_blocked_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_missing_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_below_min_atom_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_macromolecule_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_protein_like_row_count"] == 0
    assert summary["work_order_metric_evidence_required"] is True
    assert summary["work_order_metric_evidence_row_count"] == 8
    assert summary["work_order_metric_evidence_ready_row_count"] == 0
    assert summary["work_order_metric_evidence_blocked_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_dockq_source_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_lddt_pli_source_row_count"] == 8
    assert summary["work_order_metric_evidence_missing_internal_deltaG_source_row_count"] == 8
    assert summary["work_order_missing_interaction_metric_source_row_count"] == 8
    assert summary["work_order_missing_internal_deltaG_source_row_count"] == 8
    assert summary["work_order_dataset_artifact_present"] is True
    assert summary["work_order_local_receptor_coordinate_file_count"] == 0
    assert summary["work_order_tar_ligand_pose_member_count"] == 1
    assert summary["work_order_tar_receptor_coordinate_member_count"] == 0
    assert summary["work_order_tar_ligand_only_archive_count"] == 1
    assert summary["work_order_seed_interaction_metric_column_count"] == 0
    assert summary["work_order_seed_internal_deltaG_column_count"] == 0
    assert summary["work_order_experimental_deltaG_prefilled_count"] == 8
    assert summary["work_order_experimental_deltaG_source_present"] is True
    assert summary["work_order_experimental_deltaG_source_parsed_count"] == 8
    assert first_row["work_order_id"] == "refine_tier_public_benchmark_seeded_001"
    assert first_row["benchmark_id"] == "PDBBIND_CASF_C000_C000_POSE"
    assert first_row["target_id"] == "C000"
    assert first_row["provenance_kind"] == "pdbbind"
    assert first_row["provenance_id"] == "PDBBind/CASF:C000:C000_pose"
    assert first_row["pose_rmsd_A"] == "1"
    assert abs(float(first_row["deltaG_experimental_kcal_mol"]) - mod.PAFFINITY_TO_DG_KCAL_PER_MOL * 7.0) < 1e-5
    assert first_row["license_ok"] == "OPERATOR_CONFIRM_TRUE"
    assert first_row["dockq"] == "OPERATOR_FILL_DOCKQ"
    assert first_row["dockq_source_artifact"] == "OPERATOR_FILL_DOCKQ_SOURCE_ARTIFACT"
    assert first_row["lddt_pli_source_artifact"] == "OPERATOR_FILL_LDDT_PLI_SOURCE_ARTIFACT"
    assert first_row["internal_deltaG_source_artifact"] == "OPERATOR_FILL_INTERNAL_DELTAG_SOURCE_ARTIFACT"
    assert payload["science_input_gap_rows"][0]["ligand_pose_artifact_present"] is True
    assert payload["science_input_gap_rows"][0]["receptor_coordinate_artifact_present"] is False
    assert payload["receptor_coordinate_intake_rows"][0]["accepted_offline_coordinate_patterns"].startswith(
        "c000_protein.pdb;"
    )
    assert payload["receptor_coordinate_intake_rows"][0]["suggested_public_coordinate_urls"] == (
        "https://files.rcsb.org/download/C000.cif;https://files.rcsb.org/download/C000.pdb"
    )
    suggested_paths = payload["receptor_coordinate_intake_rows"][0]["suggested_local_coordinate_paths"]
    assert "dataset/c000_protein.pdb" in suggested_paths
    assert "dataset/c000/c000_protein.pdb" in suggested_paths
    assert "dataset/CASF-2016_scoring/c000/c000_complex.pdb" in suggested_paths
    assert payload["receptor_coordinate_intake_rows"][0]["operator_coordinate_source_review_required"] == (
        "confirm_public_coordinate_source_license_and_native_receptor_or_complex_chain_assembly_matches_pose_target"
    )
    assert payload["receptor_coordinate_intake_rows"][0]["next_operator_action"] == (
        "place_reviewed_public_receptor_or_complex_coordinate_in_dataset_dir_or_tar_archive"
    )
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_validation_status"] == "blocked"
    assert payload["receptor_coordinate_validation_rows"][0]["blockers"] == "receptor_coordinate_missing"
    assert payload["metric_evidence_rows"][0]["metric_evidence_status"] == "blocked"
    assert payload["metric_evidence_rows"][0]["blockers"] == (
        "dockq_value_missing;lddt_pli_value_missing;internal_deltaG_value_missing;"
        "metric_required_input_artifacts_missing:receptor_coordinate_artifact;"
        "dockq_source_artifact_missing;lddt_pli_source_artifact_missing;internal_deltaG_source_artifact_missing"
    )
    assert payload["metric_evidence_rows"][0]["expected_dockq_source_artifact"] == (
        "runs/refine_tier_public_benchmark_metric_sources/"
        f"{payload['metric_evidence_rows'][0]['work_order_id']}_dockq.json"
    )
    assert {row["split"] for row in payload["work_order_rows"]} == {"fit", "holdout"}


def test_science_input_gap_matches_receptor_coordinates_inside_offline_tar(tmp_path: Path) -> None:
    input_csv = tmp_path / "empty.csv"
    seed_csv = tmp_path / "seed.csv"
    affinity_tsv = tmp_path / "affinity.tsv"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "data_5_sdf").mkdir()
    input_csv.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    seed_rows = [
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": f"C{idx:03d}",
            "pose_id": f"C{idx:03d}_pose",
            "pose_rmsd_A": 1.0 + idx * 0.1,
            "blocker_count": 0,
            "blockers": "",
        }
        for idx in range(8)
    ]
    _write_seed_rows(seed_csv, seed_rows)
    _write_affinity_rows(affinity_tsv, {f"c{idx:03d}": 7.0 + idx * 0.1 for idx in range(8)})
    for idx in range(8):
        (dataset_dir / "data_5_sdf" / f"C{idx:03d}_pose").write_text("ligand", encoding="utf-8")
    receptor_file = tmp_path / "C000_protein.pdb"
    receptor_file.write_text(_pdb_atom_lines(20), encoding="utf-8")
    with tarfile.open(dataset_dir / "PDBbind_receptors.tar.xz", "w:xz") as handle:
        handle.add(receptor_file, arcname="pdbbind/C000/C000_protein.pdb")

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=input_csv,
        work_order_seed_csv=seed_csv,
        work_order_affinity_tsv=affinity_tsv,
        work_order_dataset_dir=dataset_dir,
    )
    summary = payload["summary"]
    first_gap = payload["science_input_gap_rows"][0]

    assert summary["work_order_tar_receptor_coordinate_member_count"] == 1
    assert summary["work_order_receptor_coordinate_ready_row_count"] == 1
    assert summary["work_order_missing_receptor_coordinate_row_count"] == 7
    assert summary["work_order_ligand_pose_only_row_count"] == 7
    assert summary["work_order_receptor_coordinate_intake_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_matched_row_count"] == 1
    assert summary["work_order_receptor_coordinate_intake_missing_row_count"] == 7
    assert summary["work_order_receptor_coordinate_intake_suggested_public_url_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_suggested_local_path_row_count"] == 8
    assert summary["work_order_receptor_coordinate_intake_operator_review_required_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_row_count"] == 8
    assert summary["work_order_receptor_coordinate_validation_ready_row_count"] == 1
    assert summary["work_order_receptor_coordinate_validation_blocked_row_count"] == 7
    assert summary["work_order_receptor_coordinate_validation_missing_row_count"] == 7
    assert summary["work_order_receptor_coordinate_validation_below_min_atom_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_macromolecule_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_protein_like_row_count"] == 0
    assert first_gap["target_id"] == "C000"
    assert first_gap["receptor_coordinate_artifact_present"] is True
    assert first_gap["receptor_coordinate_artifact"].endswith(
        "PDBbind_receptors.tar.xz::pdbbind/C000/C000_protein.pdb"
    )
    assert payload["receptor_coordinate_intake_rows"][0]["next_operator_action"] == "none"
    assert payload["receptor_coordinate_intake_rows"][0]["suggested_public_coordinate_urls"] == (
        "https://files.rcsb.org/download/C000.cif;https://files.rcsb.org/download/C000.pdb"
    )
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_validation_status"] == "pass"
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_atom_record_count"] == 20
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_pdb_atom_record_count"] == 20
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_distinct_residue_count"] == 20
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_protein_like_atom_record_count"] == 20
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_protein_like_residue_count"] == 20
    assert payload["receptor_coordinate_validation_rows"][0]["receptor_coordinate_artifact_sha256"] == (
        hashlib.sha256(receptor_file.read_bytes()).hexdigest()
    )
    assert payload["receptor_coordinate_validation_rows"][1]["receptor_coordinate_artifact_sha256"] == ""


def test_receptor_coordinate_validation_blocks_too_small_coordinate_file(tmp_path: Path) -> None:
    input_csv = tmp_path / "empty.csv"
    seed_csv = tmp_path / "seed.csv"
    affinity_tsv = tmp_path / "affinity.tsv"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "data_5_sdf").mkdir()
    input_csv.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    seed_rows = [
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": f"C{idx:03d}",
            "pose_id": f"C{idx:03d}_pose",
            "pose_rmsd_A": 1.0 + idx * 0.1,
            "blocker_count": 0,
            "blockers": "",
        }
        for idx in range(8)
    ]
    _write_seed_rows(seed_csv, seed_rows)
    _write_affinity_rows(affinity_tsv, {f"c{idx:03d}": 7.0 + idx * 0.1 for idx in range(8)})
    for idx in range(8):
        (dataset_dir / "data_5_sdf" / f"C{idx:03d}_pose").write_text("ligand", encoding="utf-8")
    (dataset_dir / "C000_protein.pdb").write_text(_pdb_atom_lines(1), encoding="utf-8")

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=input_csv,
        work_order_seed_csv=seed_csv,
        work_order_affinity_tsv=affinity_tsv,
        work_order_dataset_dir=dataset_dir,
    )
    summary = payload["summary"]

    assert summary["work_order_receptor_coordinate_ready_row_count"] == 1
    assert summary["work_order_receptor_coordinate_validation_ready_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_atom_row_count"] == 1
    assert payload["receptor_coordinate_validation_rows"][0]["coordinate_validation_status"] == "blocked"
    assert payload["receptor_coordinate_validation_rows"][0]["blockers"] == (
        "receptor_coordinate_atom_record_count_below_min"
    )


def test_receptor_coordinate_validation_blocks_ligand_only_mol2_named_as_receptor(tmp_path: Path) -> None:
    input_csv = tmp_path / "empty.csv"
    seed_csv = tmp_path / "seed.csv"
    affinity_tsv = tmp_path / "affinity.tsv"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "data_5_sdf").mkdir()
    input_csv.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    seed_rows = [
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": f"C{idx:03d}",
            "pose_id": f"C{idx:03d}_pose",
            "pose_rmsd_A": 1.0 + idx * 0.1,
            "blocker_count": 0,
            "blockers": "",
        }
        for idx in range(8)
    ]
    _write_seed_rows(seed_csv, seed_rows)
    _write_affinity_rows(affinity_tsv, {f"c{idx:03d}": 7.0 + idx * 0.1 for idx in range(8)})
    for idx in range(8):
        (dataset_dir / "data_5_sdf" / f"C{idx:03d}_pose").write_text("ligand", encoding="utf-8")
    (dataset_dir / "C000_receptor.mol2").write_text(_mol2_atom_lines(24, residue_count=1), encoding="utf-8")

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=input_csv,
        work_order_seed_csv=seed_csv,
        work_order_affinity_tsv=affinity_tsv,
        work_order_dataset_dir=dataset_dir,
    )
    summary = payload["summary"]
    first_validation_row = payload["receptor_coordinate_validation_rows"][0]

    assert summary["work_order_receptor_coordinate_ready_row_count"] == 1
    assert summary["work_order_receptor_coordinate_validation_ready_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_atom_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_macromolecule_row_count"] == 1
    assert summary["work_order_receptor_coordinate_validation_below_min_protein_like_row_count"] == 0
    assert first_validation_row["coordinate_atom_record_count"] == 24
    assert first_validation_row["coordinate_mol2_atom_record_count"] == 24
    assert first_validation_row["coordinate_distinct_residue_count"] == 1
    assert first_validation_row["coordinate_validation_status"] == "blocked"
    assert first_validation_row["blockers"] == "receptor_coordinate_macromolecule_record_count_below_min"


def test_receptor_coordinate_validation_blocks_nonprotein_mol2_with_many_residues(tmp_path: Path) -> None:
    input_csv = tmp_path / "empty.csv"
    seed_csv = tmp_path / "seed.csv"
    affinity_tsv = tmp_path / "affinity.tsv"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "data_5_sdf").mkdir()
    input_csv.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    seed_rows = [
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": f"C{idx:03d}",
            "pose_id": f"C{idx:03d}_pose",
            "pose_rmsd_A": 1.0 + idx * 0.1,
            "blocker_count": 0,
            "blockers": "",
        }
        for idx in range(8)
    ]
    _write_seed_rows(seed_csv, seed_rows)
    _write_affinity_rows(affinity_tsv, {f"c{idx:03d}": 7.0 + idx * 0.1 for idx in range(8)})
    for idx in range(8):
        (dataset_dir / "data_5_sdf" / f"C{idx:03d}_pose").write_text("ligand", encoding="utf-8")
    (dataset_dir / "C000_receptor.mol2").write_text(_mol2_atom_lines(25, residue_count=5), encoding="utf-8")

    payload = mod.build_refine_tier_public_benchmark_readiness(
        input_csv=input_csv,
        work_order_seed_csv=seed_csv,
        work_order_affinity_tsv=affinity_tsv,
        work_order_dataset_dir=dataset_dir,
    )
    summary = payload["summary"]
    first_validation_row = payload["receptor_coordinate_validation_rows"][0]

    assert summary["work_order_receptor_coordinate_ready_row_count"] == 1
    assert summary["work_order_receptor_coordinate_validation_ready_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_macromolecule_row_count"] == 0
    assert summary["work_order_receptor_coordinate_validation_below_min_protein_like_row_count"] == 1
    assert first_validation_row["coordinate_atom_record_count"] == 25
    assert first_validation_row["coordinate_distinct_residue_count"] == 5
    assert first_validation_row["coordinate_protein_like_residue_count"] == 0
    assert first_validation_row["coordinate_validation_status"] == "blocked"
    assert first_validation_row["blockers"] == "receptor_coordinate_protein_like_residue_count_below_min"

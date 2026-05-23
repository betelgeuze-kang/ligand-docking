from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    sequence_dir = tmp_path / "sequences"
    sequence_dir.mkdir()
    fasta = sequence_dir / "T9000.fasta"
    fasta.write_text(">T9000\nACDE\n", encoding="utf-8")
    work_queue = tmp_path / "runs/work_queue.json"
    sequence_packet = tmp_path / "runs/sequence.json"
    import_packet = tmp_path / "runs/import.json"
    _write_json(
        work_queue,
        {
            "rows": [
                {
                    "target_id": "T9000",
                    "recommended_action": "first_internal_attempt",
                    "work_priority": 260,
                    "days_to_human_expiration": 7,
                    "submission_decision": "submission_no_go",
                    "sequence_path": str(fasta),
                },
                {
                    "target_id": "H9001",
                    "recommended_action": "dry_run_only_deadline_too_close",
                    "work_priority": 40,
                    "days_to_human_expiration": 1,
                    "submission_decision": "submission_no_go",
                },
            ]
        },
    )
    _write_json(sequence_packet, {"rows": [{"target_id": "T9000", "sequence_status": "ready", "sequence_path": str(fasta)}]})
    _write_json(import_packet, {"rows": [{"target_id": "T9000", "prediction_import_status": "missing_candidate"}]})
    return work_queue, sequence_packet, import_packet, fasta


def _write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.write_text(
        ",".join(fieldnames)
        + "\n"
        + "\n".join(",".join(row.get(key, "") for key in fieldnames) for row in rows)
        + "\n",
        encoding="utf-8",
    )


def _run_builder(
    tmp_path: Path,
    work_queue: Path,
    sequence_packet: Path,
    import_packet: Path,
    *,
    intake_csv: Path | None = None,
    target_scope: str = "eligible",
    target_limit: int = 3,
    allow_deadline_close: bool = False,
    backend_supports_multimer: bool = False,
    backend_mode: str = "auto",
    internal_quality_preset: str = "casp17_quality",
    internal_emit_backbone_atoms: bool = False,
    custom_command: str = "",
    provisioning_status: str = "blocked_until_rocm_structure_backend_is_wired",
) -> dict:
    out_json = tmp_path / "runs/launch.json"
    provisioning_json = tmp_path / "runs/provisioning.json"
    _write_json(provisioning_json, {"summary": {"plan_status": provisioning_status}})
    command = [
        "python3",
        str(ROOT / "tools/build_casp17_prediction_launch_packet.py"),
        "--work-queue-json",
        str(work_queue),
        "--sequence-packet-json",
        str(sequence_packet),
        "--prediction-import-json",
        str(import_packet),
        "--target-scope",
        target_scope,
        "--target-limit",
        str(target_limit),
        "--backend-provisioning-json",
        str(provisioning_json),
        "--prediction-dir",
        str(tmp_path / "runs/predictions"),
        "--job-dir",
        str(tmp_path / "runs/jobs"),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(tmp_path / "runs/launch.csv"),
        "--out-md",
        str(tmp_path / "runs/launch.md"),
        "--disable-auto-backend-detection",
    ]
    if backend_mode != "auto":
        command.extend(["--backend-mode", backend_mode])
    if internal_quality_preset != "casp17_quality":
        command.extend(["--internal-quality-preset", internal_quality_preset])
    if internal_emit_backbone_atoms:
        command.append("--internal-emit-backbone-atoms")
    if intake_csv is not None:
        command.extend(["--intake-csv", str(intake_csv)])
    if allow_deadline_close:
        command.append("--allow-deadline-close")
    if backend_supports_multimer:
        command.append("--backend-supports-multimer")
    if custom_command:
        command.extend(["--custom-backend-command", custom_command])
    subprocess.run(command, cwd=ROOT, check=True)
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_casp17_prediction_launch_packet_blocks_without_backend(tmp_path: Path) -> None:
    work_queue, sequence_packet, import_packet, _fasta = _fixtures(tmp_path)

    payload = _run_builder(tmp_path, work_queue, sequence_packet, import_packet)

    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["ready_to_launch_count"] == 0
    assert payload["summary"]["backend_provisioning"]["plan_status"] == "blocked_until_rocm_structure_backend_is_wired"
    row = payload["rows"][0]
    assert row["launch_status"] == "blocked"
    assert "no_supported_prediction_backend_detected" in row["blockers"]
    assert "backend_provisioning:blocked_until_rocm_structure_backend_is_wired" in row["blockers"]


def test_casp17_prediction_launch_packet_renders_custom_backend_command(tmp_path: Path) -> None:
    work_queue, sequence_packet, import_packet, fasta = _fixtures(tmp_path)

    payload = _run_builder(
        tmp_path,
        work_queue,
        sequence_packet,
        import_packet,
        custom_command="predictor --target {target_id} --fasta {fasta} --out {out_dir}",
    )

    assert payload["summary"]["ready_to_launch_count"] == 1
    row = payload["rows"][0]
    assert row["launch_status"] == "ready_to_launch"
    assert row["recommended_backend"] == "custom"
    assert "run_casp17_custom_backend_job.py" in row["command"]
    assert "--command-template" in row["command"]
    assert "predictor --target {target_id} --fasta {fasta} --out {out_dir}" in row["command"]
    assert "validate_casp17_backend_contract.py" in row["contract_command"]
    assert "--require-gpu" in row["contract_command"]
    assert "convert_casp17_ts_prediction_from_pdb.py" in row["conversion_command"]
    assert "<CASP_AUTHOR_CODE>" in row["conversion_command"]


def test_casp17_prediction_launch_packet_skips_imported_prediction(tmp_path: Path) -> None:
    work_queue, sequence_packet, import_packet, _fasta = _fixtures(tmp_path)
    _write_json(import_packet, {"rows": [{"target_id": "T9000", "prediction_import_status": "imported"}]})

    payload = _run_builder(
        tmp_path,
        work_queue,
        sequence_packet,
        import_packet,
        custom_command="predictor --target {target_id} --fasta {fasta} --out {out_dir}",
    )

    assert payload["summary"]["skipped_count"] == 1
    row = payload["rows"][0]
    assert row["launch_status"] == "skipped_prediction_already_imported"
    assert row["command"] == ""
    assert row["contract_command"] == ""


def test_casp17_prediction_launch_packet_plans_all_protein_targets_when_backend_supports_multimer(tmp_path: Path) -> None:
    work_queue, sequence_packet, import_packet, fasta = _fixtures(tmp_path)
    h_fasta = tmp_path / "sequences/H9002.fasta"
    h_fasta.write_text(">H9002_A\nACDE\n>H9002_B\nFGHI\n", encoding="utf-8")
    intake_csv = tmp_path / "runs/intake.csv"
    _write_intake(
        intake_csv,
        [
            {
                "target_id": "T9000",
                "target_name": "mono",
                "due_date": "2026-05-26",
                "sequence_path": str(fasta),
                "stoichiometry": "A1",
            },
            {
                "target_id": "H9002",
                "target_name": "complex",
                "due_date": "2026-05-20",
                "sequence_path": str(h_fasta),
                "stoichiometry": "A1B1",
            },
            {
                "target_id": "R9003",
                "target_name": "rna",
                "due_date": "2026-05-20",
                "sequence_path": str(h_fasta),
                "stoichiometry": "A1",
            },
        ],
    )

    payload = _run_builder(
        tmp_path,
        work_queue,
        sequence_packet,
        import_packet,
        intake_csv=intake_csv,
        target_scope="all_protein",
        target_limit=0,
        allow_deadline_close=True,
        backend_supports_multimer=True,
        custom_command="predictor --target {target_id} --fasta {fasta} --raw-pdb {raw_pdb}",
    )

    assert payload["summary"]["target_scope"] == "all_protein"
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["ready_to_launch_count"] == 2
    by_target = {row["target_id"]: row for row in payload["rows"]}
    assert by_target["T9000"]["target_kind"] == "protein_monomer_homomer"
    assert by_target["T9000"]["fasta_entry_count"] == 1
    assert by_target["H9002"]["target_kind"] == "protein_complex"
    assert by_target["H9002"]["fasta_entry_count"] == 2


def test_casp17_prediction_launch_packet_blocks_complex_when_custom_multimer_support_not_declared(tmp_path: Path) -> None:
    work_queue, sequence_packet, import_packet, _fasta = _fixtures(tmp_path)
    h_fasta = tmp_path / "sequences/H9002.fasta"
    h_fasta.write_text(">H9002_A\nACDE\n>H9002_B\nFGHI\n", encoding="utf-8")
    intake_csv = tmp_path / "runs/intake.csv"
    _write_intake(
        intake_csv,
        [
            {
                "target_id": "H9002",
                "target_name": "complex",
                "due_date": "2026-05-26",
                "sequence_path": str(h_fasta),
                "stoichiometry": "A1B1",
            }
        ],
    )

    payload = _run_builder(
        tmp_path,
        work_queue,
        sequence_packet,
        import_packet,
        intake_csv=intake_csv,
        target_scope="all_protein",
        target_limit=0,
        allow_deadline_close=True,
        custom_command="predictor --target {target_id} --fasta {fasta} --raw-pdb {raw_pdb}",
    )

    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["ready_to_launch_count"] == 0
    row = payload["rows"][0]
    assert row["launch_status"] == "blocked"
    assert "backend_multimer_support_not_declared" in row["blockers"]


def test_casp17_prediction_launch_packet_renders_internal_physics_backend_for_all_protein(tmp_path: Path) -> None:
    work_queue, sequence_packet, import_packet, fasta = _fixtures(tmp_path)
    h_fasta = tmp_path / "sequences/H9002.fasta"
    h_fasta.write_text(">H9002_A\nACDE\n>H9002_B\nFGHI\n", encoding="utf-8")
    intake_csv = tmp_path / "runs/intake.csv"
    _write_intake(
        intake_csv,
        [
            {
                "target_id": "T9000",
                "target_name": "mono",
                "due_date": "2026-05-26",
                "sequence_path": str(fasta),
                "stoichiometry": "A1",
            },
            {
                "target_id": "H9002",
                "target_name": "complex",
                "due_date": "2026-05-26",
                "sequence_path": str(h_fasta),
                "stoichiometry": "A1B1",
            },
        ],
    )

    payload = _run_builder(
        tmp_path,
        work_queue,
        sequence_packet,
        import_packet,
        intake_csv=intake_csv,
        target_scope="all_protein",
        target_limit=0,
        allow_deadline_close=True,
        backend_supports_multimer=True,
        backend_mode="internal_physics",
        internal_quality_preset="smoke",
        internal_emit_backbone_atoms=True,
    )

    assert payload["summary"]["backend_mode"] == "internal_physics"
    assert payload["summary"]["ready_to_launch_count"] == 2
    for row in payload["rows"]:
        assert row["recommended_backend"] == "internal_physics"
        assert "run_casp17_internal_physics_baseline_predictor.py" in row["command"]
        assert "--quality-preset smoke" in row["command"]
        assert "--emit-backbone-atoms" in row["command"]
        assert "--backend-kind internal_physics" in row["contract_command"]

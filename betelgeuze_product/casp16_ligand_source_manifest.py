from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

CASP16_FORMAT_URL = "https://predictioncenter.org/casp16/index.cgi?page=format"
CASP16_NUMBERS_URL = "https://predictioncenter.org/casp16/numbers.cgi"

SUITE_ID = "casp16_ligand_pose_affinity"
BENCHMARK_FAMILY = "competition_credibility_ligand_pose_affinity"
PRIMARY_POSE_METRIC = "LDDT-PLI"
PRIMARY_AFFINITY_METRIC = "Kendall_tau"
SOURCE_MANIFEST_REQUIRED_COLUMNS = ("target_id", "source_url", "sha256")
SCORECARD_REQUIRED_COLUMNS = (
    "target_id",
    "task_type",
    "metric_name",
    "metric_value",
    "result_source",
)
SCORECARD_ALLOWED_TASK_TYPES = ("pose", "affinity")
SCORECARD_ALLOWED_METRICS = (PRIMARY_POSE_METRIC, PRIMARY_AFFINITY_METRIC)
CHECKSUM_MANIFEST_FORMAT = "<sha256>  <operator-retained-source-path-or-uri>"
DEFAULT_OPERATOR_SOURCE_MANIFEST_TEMPLATE = (
    "runs/casp16_ligand_operator_source_manifest_template_current.csv"
)
DEFAULT_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE = (
    "runs/casp16_ligand_operator_checksum_manifest_template_current.sha256"
)
DEFAULT_OPERATOR_SCORECARD_ROWS_TEMPLATE = (
    "runs/casp16_ligand_operator_scorecard_rows_template_current.csv"
)
DEFAULT_OPERATOR_RECEIPT_FILL_IN_MD = (
    "runs/casp16_ligand_operator_receipt_fill_in_current.md"
)

CLAIM_BOUNDARY = (
    "CASP16 ligand source manifest only; it records official source references, expected ligand target "
    "counts, local checksum/materialization receipt paths, and scorecard handoff commands. It does not "
    "download CASP data, store raw targets, import official archive models as internal predictions, run "
    "docking, compute pose or affinity metrics, submit predictions, or mutate external state."
)
RAW_DATA_SUFFIXES = {
    ".pdb",
    ".cif",
    ".mmcif",
    ".sdf",
    ".mol",
    ".mol2",
    ".pdbqt",
    ".mae",
    ".maegz",
    ".xtc",
    ".trr",
    ".dcd",
    ".nc",
    ".tar",
    ".gz",
    ".tgz",
    ".zip",
    ".xz",
}
ALLOWED_COMMITTED_FILENAMES = {
    "source_manifest.csv",
    "checksums.sha256",
    "materialization_manifest.json",
}

SOURCE_ROWS: tuple[dict[str, Any], ...] = (
    {
        "source_id": "casp16_lg_format_contract",
        "source_kind": "official_format_contract",
        "source_url": CASP16_FORMAT_URL,
        "tracked_fact": "CASP16 LG predictions use receptor coordinates, ligand MDL coordinates, and/or affinity records.",
        "expected_count": "",
        "claim_use": "format_validation_only",
    },
    {
        "source_id": "casp16_ligand_pose_target_count",
        "source_kind": "official_count",
        "source_url": CASP16_NUMBERS_URL,
        "tracked_fact": "Number of pharma pose ligand targets released.",
        "expected_count": 233,
        "claim_use": "scope_accounting_only",
    },
    {
        "source_id": "casp16_ligand_affinity_target_count",
        "source_kind": "official_count",
        "source_url": CASP16_NUMBERS_URL,
        "tracked_fact": "Number of pharma affinity ligand targets released.",
        "expected_count": 140,
        "claim_use": "scope_accounting_only",
    },
    {
        "source_id": "casp16_ligand_affinity_stage2_target_count",
        "source_kind": "official_count",
        "source_url": CASP16_NUMBERS_URL,
        "tracked_fact": "Number of pharma affinity ligand targets released for stage 2.",
        "expected_count": 110,
        "claim_use": "scope_accounting_only",
    },
    {
        "source_id": "casp16_incidental_ligand_target_count",
        "source_kind": "official_count",
        "source_url": CASP16_NUMBERS_URL,
        "tracked_fact": "Number of incidental ligand targets released.",
        "expected_count": 8,
        "claim_use": "scope_accounting_only",
    },
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _json_status(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "json_unreadable"
    if isinstance(payload, dict):
        summary = payload.get("summary")
        if isinstance(summary, dict):
            return _text(summary.get("status"))
        return _text(payload.get("status"))
    return ""


def _nearest_existing_path(path: Path) -> Path:
    current = path if path.exists() else path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return current if current.exists() else Path.cwd()


def _git_root(path: Path) -> Path | None:
    probe = _nearest_existing_path(path)
    try:
        result = subprocess.run(
            ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return Path(text) if text else None


def _git_tracked_raw_files(path: Path) -> list[str]:
    root = _git_root(path)
    if root is None:
        return []
    try:
        target = path.resolve()
        root_resolved = root.resolve()
        relative = target.relative_to(root_resolved)
    except (OSError, ValueError):
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", str(relative)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    tracked: list[str] = []
    for line in result.stdout.splitlines():
        tracked_path = Path(line.strip())
        if not str(tracked_path):
            continue
        if tracked_path.name in ALLOWED_COMMITTED_FILENAMES:
            continue
        if tracked_path.suffix.lower() in RAW_DATA_SUFFIXES:
            tracked.append(str(tracked_path))
    return sorted(tracked)


def build_casp16_ligand_source_manifest(
    *,
    local_source_manifest_csv: str | Path,
    local_checksum_manifest: str | Path,
    local_materialization_manifest: str | Path,
    scorecard_json: str | Path,
) -> dict[str, Any]:
    source_manifest = Path(local_source_manifest_csv)
    checksum_manifest = Path(local_checksum_manifest)
    materialization_manifest = Path(local_materialization_manifest)
    scorecard = Path(scorecard_json)
    checksum_line_count = _line_count(checksum_manifest)
    materialization_status = _json_status(materialization_manifest)
    scorecard_status = _json_status(scorecard)

    source_rows_ready = all(_text(row.get("source_url")) for row in SOURCE_ROWS)
    local_source_manifest_present = source_manifest.is_file()
    checksum_manifest_present = checksum_manifest.is_file()
    materialization_manifest_present = materialization_manifest.is_file()
    scorecard_present = scorecard.is_file()
    tracked_raw_files = _git_tracked_raw_files(source_manifest.parent)
    raw_data_committed = bool(tracked_raw_files)
    materialization_ready = bool(
        materialization_manifest_present
        and materialization_status
        and "blocked" not in materialization_status
        and checksum_manifest_present
        and checksum_line_count > 0
    )
    scorecard_ready = bool(scorecard_present and scorecard_status and "blocked" not in scorecard_status)

    blockers: list[str] = []
    if not source_rows_ready:
        blockers.append("official_source_rows_incomplete")
    if not local_source_manifest_present:
        blockers.append("local_source_manifest_csv_missing")
    if not checksum_manifest_present:
        blockers.append("checksum_manifest_missing")
    if checksum_manifest_present and checksum_line_count == 0:
        blockers.append("checksum_manifest_empty")
    if not materialization_manifest_present:
        blockers.append("materialization_manifest_missing")
    if materialization_manifest_present and not materialization_ready:
        blockers.append("materialization_manifest_blocked")
    if not scorecard_present:
        blockers.append("scorecard_json_missing")
    if scorecard_present and not scorecard_ready:
        blockers.append("scorecard_json_blocked")
    if raw_data_committed:
        blockers.append("raw_data_committed_in_repo")
    blockers = sorted(set(blockers))

    competition_credibility_ready = bool(
        source_rows_ready
        and materialization_ready
        and scorecard_ready
        and not raw_data_committed
        and not blockers
    )
    status = (
        "casp16_ligand_competition_credibility_ready"
        if competition_credibility_ready
        else "blocked_casp16_ligand_competition_credibility"
    )
    operator_input_artifacts = [
        str(source_manifest),
        str(checksum_manifest),
        str(materialization_manifest),
        str(scorecard),
    ]
    missing_input_artifacts = [
        path
        for path, present in (
            (str(source_manifest), local_source_manifest_present),
            (str(checksum_manifest), checksum_manifest_present),
            (str(materialization_manifest), materialization_manifest_present),
            (str(scorecard), scorecard_present),
        )
        if not present
    ]
    rows = [
        {
            **row,
            "check": "official_source_reference_present",
            "status": "pass" if _text(row.get("source_url")) else "fail",
            "observed": _text(row.get("source_url")),
            "required": "official CASP16 source URL",
        }
        for row in SOURCE_ROWS
    ]
    rows.extend(
        [
            {
                "source_id": "local_source_manifest_csv",
                "source_kind": "operator_local_manifest",
                "source_url": "",
                "tracked_fact": "Operator-reviewed source manifest for locally materialized CASP16 ligand rows.",
                "expected_count": "",
                "claim_use": "local_materialization_input",
                "check": "local_source_manifest_csv_present",
                "status": "pass" if local_source_manifest_present else "fail",
                "observed": str(source_manifest),
                "required": "CSV manifest; raw CASP data must remain outside committed repo files",
            },
            {
                "source_id": "local_checksum_manifest",
                "source_kind": "operator_checksum_manifest",
                "source_url": "",
                "tracked_fact": "SHA256 manifest for locally materialized source/result files.",
                "expected_count": "",
                "claim_use": "integrity_check",
                "check": "checksum_manifest_present",
                "status": "pass" if checksum_manifest_present and checksum_line_count > 0 else "fail",
                "observed": f"{checksum_manifest};lines={checksum_line_count}",
                "required": "non-empty SHA256 manifest",
            },
            {
                "source_id": "local_materialization_manifest",
                "source_kind": "operator_materialization_receipt",
                "source_url": "",
                "tracked_fact": "Local materialization receipt that records source paths and no-download policy.",
                "expected_count": "",
                "claim_use": "materialization_gate",
                "check": "materialization_manifest_ready",
                "status": "pass" if materialization_ready else "fail",
                "observed": materialization_status or str(materialization_manifest),
                "required": "non-blocked local materialization JSON",
            },
            {
                "source_id": "local_scorecard_json",
                "source_kind": "operator_scorecard_receipt",
                "source_url": "",
                "tracked_fact": "Local scorecard receipt for CASP16 ligand pose/affinity rows.",
                "expected_count": "",
                "claim_use": "scorecard_gate",
                "check": "scorecard_ready",
                "status": "pass" if scorecard_ready else "fail",
                "observed": scorecard_status or str(scorecard),
                "required": "non-blocked local scorecard JSON",
            },
        ]
    )

    summary = {
        "packet_type": "casp16_ligand_source_manifest",
        "schema_version": "casp16_ligand_source_manifest_v1",
        "suite_id": SUITE_ID,
        "status": status,
        "competition_credibility_ready": competition_credibility_ready,
        "source_manifest_ready": source_rows_ready,
        "materialization_ready": materialization_ready,
        "scorecard_ready": scorecard_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "benchmark_family": BENCHMARK_FAMILY,
        "primary_pose_metric": PRIMARY_POSE_METRIC,
        "primary_affinity_metric": PRIMARY_AFFINITY_METRIC,
        "official_format_url": CASP16_FORMAT_URL,
        "official_numbers_url": CASP16_NUMBERS_URL,
        "official_source_row_count": len(SOURCE_ROWS),
        "pharma_pose_ligand_target_count": 233,
        "pharma_affinity_ligand_target_count": 140,
        "pharma_affinity_stage2_ligand_target_count": 110,
        "incidental_ligand_target_count": 8,
        "local_source_manifest_csv": str(source_manifest),
        "local_source_manifest_csv_present": local_source_manifest_present,
        "local_checksum_manifest": str(checksum_manifest),
        "local_checksum_manifest_present": checksum_manifest_present,
        "local_checksum_manifest_line_count": checksum_line_count,
        "local_materialization_manifest": str(materialization_manifest),
        "local_materialization_manifest_present": materialization_manifest_present,
        "local_materialization_status": materialization_status,
        "scorecard_json": str(scorecard),
        "scorecard_json_present": scorecard_present,
        "scorecard_status": scorecard_status,
        "operator_input_schema_ready": True,
        "source_manifest_required_columns": list(SOURCE_MANIFEST_REQUIRED_COLUMNS),
        "checksum_manifest_format": CHECKSUM_MANIFEST_FORMAT,
        "scorecard_required_columns": list(SCORECARD_REQUIRED_COLUMNS),
        "scorecard_allowed_task_types": list(SCORECARD_ALLOWED_TASK_TYPES),
        "scorecard_allowed_metrics": list(SCORECARD_ALLOWED_METRICS),
        "operator_source_manifest_template_csv": DEFAULT_OPERATOR_SOURCE_MANIFEST_TEMPLATE,
        "operator_checksum_manifest_template": DEFAULT_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE,
        "operator_scorecard_rows_template_csv": DEFAULT_OPERATOR_SCORECARD_ROWS_TEMPLATE,
        "operator_receipt_fill_in_md": DEFAULT_OPERATOR_RECEIPT_FILL_IN_MD,
        "operator_template_artifacts": ";".join(
            [
                DEFAULT_OPERATOR_SOURCE_MANIFEST_TEMPLATE,
                DEFAULT_OPERATOR_CHECKSUM_MANIFEST_TEMPLATE,
                DEFAULT_OPERATOR_SCORECARD_ROWS_TEMPLATE,
                DEFAULT_OPERATOR_RECEIPT_FILL_IN_MD,
            ]
        ),
        "operator_templates_written": False,
        "raw_data_custody_ready": not raw_data_committed,
        "raw_data_git_tracked_file_count": len(tracked_raw_files),
        "raw_data_git_tracked_sample_paths": tracked_raw_files[:10],
        "operator_input_artifacts": ";".join(operator_input_artifacts),
        "missing_input_artifacts": ";".join(missing_input_artifacts),
        "run_command": "python3 tools/build_casp16_ligand_source_manifest.py",
        "materialization_command_template": (
            "python3 tools/build_casp16_ligand_materialization_manifest.py "
            "--source-manifest-csv OPERATOR_LOCAL_SOURCE_MANIFEST "
            "--checksum-manifest OPERATOR_LOCAL_CHECKSUMS "
            "--out-json runs/casp16_ligand_materialization_manifest_current.json "
            "--out-csv runs/casp16_ligand_materialization_manifest_current.csv "
            "--out-md runs/casp16_ligand_materialization_manifest_current.md"
        ),
        "scorecard_run_command_template": (
            "python3 tools/build_casp16_ligand_scorecard.py "
            "--materialization-json runs/casp16_ligand_materialization_manifest_current.json "
            "--scorecard-rows-csv OPERATOR_REVIEWED_SCORECARD_ROWS_CSV "
            "--out-json runs/casp16_ligand_scorecard_current.json"
        ),
        "raw_data_committed": raw_data_committed,
        "download_executed": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review the CASP16 ligand scorecard and attach it to Package B/C evidence."
            if competition_credibility_ready
            else "Place operator-reviewed source/checksum/materialization/scorecard receipts outside committed raw-data paths, then rebuild this manifest."
        ),
    }
    return {"summary": summary, "rows": rows}

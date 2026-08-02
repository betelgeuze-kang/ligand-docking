from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

BM5_ZLAB_URL = "https://zlab.wenglab.org/benchmark/"
BM5_PUBLICATION_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC4677049/"
CAPRI_EBI_URL = "https://www.ebi.ac.uk/pdbe/complex-pred/capri/"
SBGRID_BM5_CAPRI_URL = "https://data.sbgrid.org/dataset/684/"
SBGRID_BM5_CAPRI_DOI = "10.15785/SBGRID/684"

SUITE_ID = "bm5_capri_complex_benchmark"
BENCHMARK_FAMILY = "competition_credibility_protein_complex_docking"
BM5_SUITE_ID = "protein_protein_docking_benchmark_v5"
PRIMARY_METRIC = "dockq_acceptable_rate_proxy"

CLAIM_BOUNDARY = (
    "BM5/CAPRI complex source manifest only; it records official source references, local BM5 materialization, "
    "checksum/provenance receipts, and scorecard handoff state for protein-complex credibility. It does not "
    "download BM5 or CAPRI data, run docking, submit CAPRI/CASP predictions, compute official CAPRI metrics, "
    "store raw target data, mutate external state, or support small-molecule ligand docking claims."
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
        "source_id": "bm5_zlab_benchmark_page",
        "source_kind": "official_benchmark_table",
        "source_url": BM5_ZLAB_URL,
        "tracked_fact": "ZLab Protein-Protein Docking Benchmark page lists Benchmark 5.5 and links Benchmark 5.0.",
        "expected_count": "",
        "claim_use": "protein_complex_source_reference",
    },
    {
        "source_id": "bm5_publication_docking_entry_count",
        "source_kind": "peer_reviewed_publication",
        "source_url": BM5_PUBLICATION_URL,
        "tracked_fact": "Docking benchmark version 5 publication reports 230 docking benchmark entries.",
        "expected_count": 230,
        "claim_use": "scope_accounting_only",
    },
    {
        "source_id": "capri_ebi_experiment_description",
        "source_kind": "official_capri_program_description",
        "source_url": CAPRI_EBI_URL,
        "tracked_fact": "CAPRI is a blind protein-complex docking assessment with submitted model sets assessed after the round.",
        "expected_count": "",
        "claim_use": "competition_credibility_context",
    },
    {
        "source_id": "sbgrid_bm5_capri_score_set",
        "source_kind": "public_structural_model_dataset",
        "source_url": SBGRID_BM5_CAPRI_URL,
        "tracked_fact": "SBGrid dataset 684 describes docking models for Docking Benchmark 4, 5 and CAPRI score_set.",
        "expected_count": "",
        "claim_use": "optional_capri_score_set_materialization_source",
    },
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "json_unreadable"}
    if not isinstance(payload, dict):
        return {}
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _status(path: Path) -> str:
    return _text(_summary(path).get("status"))


def _sha256_from_summary(summary: dict[str, Any]) -> str:
    for key in (
        "evidence_artifact_sha256",
        "result_artifact_sha256",
        "product_provenance_result_artifact_sha256",
    ):
        value = _text(summary.get(key))
        if value:
            return value
    return ""


def _nonblocked_status(status: str) -> bool:
    return bool(status and "blocked" not in status and "unreadable" not in status)


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


def _display(path_like: str | Path, *, root: Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _benchmark_display_root(*paths: Path) -> Path:
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        parts = resolved.parts
        for index, part in enumerate(parts):
            if part != "data":
                continue
            if index + 1 >= len(parts):
                continue
            if parts[index + 1] not in {"public_benchmarks", "competition_benchmarks"}:
                continue
            prefix = parts[:index]
            if not prefix:
                return Path(resolved.anchor)
            return Path(*prefix)
    return _git_root(Path.cwd()) or Path.cwd()


def _git_tracked_raw_files(path: Path, *, display_root: Path) -> list[str]:
    git_root = _git_root(path)
    if git_root is None:
        return []
    try:
        target = path.resolve()
        git_root_resolved = git_root.resolve()
        relative = target.relative_to(git_root_resolved)
    except (OSError, ValueError):
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(git_root), "ls-files", "--", str(relative)],
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
            tracked.append(_display(git_root / tracked_path, root=display_root))
    return sorted(tracked)


def build_bm5_capri_complex_source_manifest(
    *,
    bm5_dataset_dir: str | Path,
    bm5_materialization_manifest: str | Path,
    bm5_result_provenance_json: str | Path,
    bm5_scorecard_json: str | Path,
    capri_score_set_source_manifest: str | Path,
    capri_score_set_checksum_manifest: str | Path,
    capri_score_set_materialization_manifest: str | Path,
    capri_score_set_scorecard_json: str | Path,
) -> dict[str, Any]:
    bm5_dataset = Path(bm5_dataset_dir)
    bm5_materialization = Path(bm5_materialization_manifest)
    bm5_provenance = Path(bm5_result_provenance_json)
    bm5_scorecard = Path(bm5_scorecard_json)
    capri_source_manifest = Path(capri_score_set_source_manifest)
    capri_checksum_manifest = Path(capri_score_set_checksum_manifest)
    capri_materialization = Path(capri_score_set_materialization_manifest)
    capri_scorecard = Path(capri_score_set_scorecard_json)

    bm5_materialization_summary = _summary(bm5_materialization)
    bm5_provenance_summary = _summary(bm5_provenance)
    bm5_scorecard_summary = _summary(bm5_scorecard)
    bm5_materialization_status = _text(bm5_materialization_summary.get("status"))
    bm5_provenance_status = _text(bm5_provenance_summary.get("status"))
    bm5_scorecard_status = _text(bm5_scorecard_summary.get("status"))
    bm5_result_sha256 = _sha256_from_summary(bm5_provenance_summary) or _sha256_from_summary(bm5_scorecard_summary)

    capri_materialization_status = _status(capri_materialization)
    capri_scorecard_status = _status(capri_scorecard)
    display_root = _benchmark_display_root(bm5_dataset, capri_source_manifest)
    bm5_git_tracked_raw_files = _git_tracked_raw_files(
        bm5_dataset,
        display_root=display_root,
    )
    capri_git_tracked_raw_files = _git_tracked_raw_files(
        capri_source_manifest.parent,
        display_root=display_root,
    )
    tracked_raw_files = sorted(bm5_git_tracked_raw_files + capri_git_tracked_raw_files)
    raw_data_committed = bool(tracked_raw_files)

    bm5_materialization_ready = bool(
        bm5_dataset.is_dir()
        and bm5_materialization.is_file()
        and bm5_materialization_summary.get("suite_id") == BM5_SUITE_ID
        and bm5_materialization_summary.get("materialized") is True
        and _nonblocked_status(bm5_materialization_status)
    )
    bm5_checksum_ready = bool(
        bm5_provenance.is_file()
        and _nonblocked_status(bm5_provenance_status)
        and len(bm5_result_sha256) == 64
    )
    bm5_scorecard_ready = bool(
        bm5_scorecard.is_file()
        and _nonblocked_status(bm5_scorecard_status)
        and len(_sha256_from_summary(bm5_scorecard_summary)) == 64
    )
    bm5_complex_benchmark_ready = bool(
        bm5_materialization_ready and bm5_checksum_ready and bm5_scorecard_ready
    )

    capri_source_ready = bool(capri_source_manifest.is_file() and capri_checksum_manifest.is_file())
    capri_materialization_ready = bool(
        capri_materialization.is_file()
        and _nonblocked_status(capri_materialization_status)
    )
    capri_scorecard_ready = bool(
        capri_scorecard.is_file()
        and _nonblocked_status(capri_scorecard_status)
    )
    capri_score_set_ready = bool(capri_source_ready and capri_materialization_ready and capri_scorecard_ready)

    blockers: list[str] = []
    if not bm5_dataset.is_dir():
        blockers.append("bm5_dataset_dir_missing")
    if not bm5_materialization_ready:
        blockers.append("bm5_materialization_not_ready")
    if not bm5_checksum_ready:
        blockers.append("bm5_checksum_provenance_not_ready")
    if not bm5_scorecard_ready:
        blockers.append("bm5_scorecard_not_ready")
    if not capri_source_manifest.is_file():
        blockers.append("capri_score_set_source_manifest_missing")
    if not capri_checksum_manifest.is_file():
        blockers.append("capri_score_set_checksum_manifest_missing")
    if not capri_materialization_ready:
        blockers.append("capri_score_set_materialization_not_ready")
    if not capri_scorecard_ready:
        blockers.append("capri_score_set_scorecard_not_ready")
    if raw_data_committed:
        blockers.append("raw_data_committed_in_repo")
    blockers = sorted(set(blockers))

    competition_credibility_ready = bool(
        bm5_complex_benchmark_ready
        and capri_score_set_ready
        and not raw_data_committed
        and not blockers
    )
    status = (
        "bm5_capri_complex_competition_credibility_ready"
        if competition_credibility_ready
        else "blocked_bm5_capri_complex_competition_credibility"
    )

    rows = [
        {
            **row,
            "check": "official_source_reference_present",
            "status": "pass" if _text(row.get("source_url")) else "fail",
            "observed": _text(row.get("source_url")),
            "required": "official BM5/CAPRI source URL",
        }
        for row in SOURCE_ROWS
    ]
    rows.extend(
        [
            {
                "source_id": "bm5_materialization_manifest",
                "source_kind": "local_materialization_receipt",
                "source_url": "",
                "tracked_fact": "Local BM5 dataset/result materialization receipt.",
                "expected_count": "",
                "claim_use": "bm5_materialization_gate",
                "check": "bm5_materialization_ready",
                "status": "pass" if bm5_materialization_ready else "fail",
                "observed": bm5_materialization_status or str(bm5_materialization),
                "required": "public_benchmark_materialization_ready for protein_protein_docking_benchmark_v5",
            },
            {
                "source_id": "bm5_checksum_provenance",
                "source_kind": "local_checksum_receipt",
                "source_url": "",
                "tracked_fact": "SHA256 fingerprint for the local BM5 proxy result artifact.",
                "expected_count": "",
                "claim_use": "checksum_gate",
                "check": "bm5_checksum_ready",
                "status": "pass" if bm5_checksum_ready else "fail",
                "observed": bm5_result_sha256 or str(bm5_provenance),
                "required": "64-character result artifact SHA256 in provenance JSON",
            },
            {
                "source_id": "bm5_scorecard",
                "source_kind": "local_scorecard_receipt",
                "source_url": "",
                "tracked_fact": "Local BM5 proxy scorecard with claim boundary and evidence hash.",
                "expected_count": "",
                "claim_use": "scorecard_gate",
                "check": "bm5_scorecard_ready",
                "status": "pass" if bm5_scorecard_ready else "fail",
                "observed": bm5_scorecard_status or str(bm5_scorecard),
                "required": "non-blocked BM5 scorecard JSON with evidence artifact SHA256",
            },
            {
                "source_id": "capri_score_set_materialization",
                "source_kind": "operator_materialization_receipt",
                "source_url": "",
                "tracked_fact": "Optional local CAPRI score_set materialization and scorecard receipts.",
                "expected_count": "",
                "claim_use": "capri_score_set_gate",
                "check": "capri_score_set_ready",
                "status": "pass" if capri_score_set_ready else "fail",
                "observed": capri_materialization_status or str(capri_materialization),
                "required": "operator source/checksum/materialization/scorecard receipts for CAPRI score_set",
            },
        ]
    )

    summary = {
        "packet_type": "bm5_capri_complex_source_manifest",
        "schema_version": "bm5_capri_complex_source_manifest_v1",
        "suite_id": SUITE_ID,
        "status": status,
        "competition_credibility_ready": competition_credibility_ready,
        "source_manifest_ready": all(_text(row.get("source_url")) for row in SOURCE_ROWS),
        "bm5_complex_benchmark_ready": bm5_complex_benchmark_ready,
        "bm5_materialization_ready": bm5_materialization_ready,
        "bm5_checksum_ready": bm5_checksum_ready,
        "bm5_scorecard_ready": bm5_scorecard_ready,
        "capri_score_set_ready": capri_score_set_ready,
        "capri_source_ready": capri_source_ready,
        "capri_materialization_ready": capri_materialization_ready,
        "capri_scorecard_ready": capri_scorecard_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "benchmark_family": BENCHMARK_FAMILY,
        "primary_metric": PRIMARY_METRIC,
        "bm5_zlab_url": BM5_ZLAB_URL,
        "bm5_publication_url": BM5_PUBLICATION_URL,
        "capri_ebi_url": CAPRI_EBI_URL,
        "sbgrid_bm5_capri_url": SBGRID_BM5_CAPRI_URL,
        "sbgrid_bm5_capri_doi": SBGRID_BM5_CAPRI_DOI,
        "bm5_publication_docking_entry_count": 230,
        "bm5_dataset_dir": str(bm5_dataset),
        "bm5_dataset_dir_present": bm5_dataset.is_dir(),
        "bm5_materialization_manifest": str(bm5_materialization),
        "bm5_materialization_status": bm5_materialization_status,
        "bm5_result_provenance_json": str(bm5_provenance),
        "bm5_result_provenance_status": bm5_provenance_status,
        "bm5_result_artifact_sha256": bm5_result_sha256,
        "bm5_scorecard_json": str(bm5_scorecard),
        "bm5_scorecard_status": bm5_scorecard_status,
        "capri_score_set_source_manifest": str(capri_source_manifest),
        "capri_score_set_checksum_manifest": str(capri_checksum_manifest),
        "capri_score_set_materialization_manifest": str(capri_materialization),
        "capri_score_set_materialization_status": capri_materialization_status,
        "capri_score_set_scorecard_json": str(capri_scorecard),
        "capri_score_set_scorecard_status": capri_scorecard_status,
        "raw_data_custody_ready": not raw_data_committed,
        "raw_data_git_tracked_file_count": len(tracked_raw_files),
        "raw_data_git_tracked_sample_paths": tracked_raw_files[:10],
        "bm5_raw_data_git_tracked_file_count": len(bm5_git_tracked_raw_files),
        "capri_raw_data_git_tracked_file_count": len(capri_git_tracked_raw_files),
        "run_command": "python3 tools/build_bm5_capri_complex_source_manifest.py",
        "bm5_materialization_command": (
            "python3 tools/build_public_benchmark_materialization_manifest.py "
            "--suite-id protein_protein_docking_benchmark_v5"
        ),
        "bm5_proxy_results_command": "python3 tools/build_bm5_complex_proxy_results.py",
        "bm5_scorecard_command_template": (
            "python3 tools/build_public_benchmark_suite_scorecard.py "
            "--suite-id protein_protein_docking_benchmark_v5 --primary-metric-value OPERATOR_FILL_METRIC"
        ),
        "capri_score_set_materialization_command_template": (
            "python3 tools/build_public_benchmark_materialization_manifest.py "
            "--suite-id capri_score_set --dataset-artifact OPERATOR_CAPRI_SCORE_SET_DIR "
            "--result-artifact OPERATOR_CAPRI_SCORE_SET_RESULTS"
        ),
        "raw_data_custody_plan_json": "runs/bm5_capri_raw_data_custody_plan_current.json",
        "raw_data_custody_plan_csv": "runs/bm5_capri_raw_data_custody_plan_current.csv",
        "raw_data_custody_plan_command": (
            "python3 tools/build_bm5_capri_raw_data_custody_plan.py --compute-sha256"
        ),
        "raw_data_committed": raw_data_committed,
        "download_executed": False,
        "external_state_mutated": False,
        "small_molecule_ligand_claim_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review BM5/CAPRI complex scorecards as competition-credibility evidence only."
            if competition_credibility_ready
            else (
                "Move BM5/CAPRI raw data out of git-tracked storage or replace it with "
                "source/checksum/materialization receipts before treating the complex benchmark "
                "as competition-credibility evidence."
            )
            if raw_data_committed
            else (
                "BM5 local evidence is ready; add CAPRI score_set source/checksum/materialization/scorecard receipts without committing raw data."
                if bm5_complex_benchmark_ready and not capri_score_set_ready
                else "Repair BM5 materialization/checksum/scorecard receipts, then add CAPRI score_set receipts."
            )
        ),
    }
    return {"summary": summary, "rows": rows}

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

DATASET_RECORD_URL = "https://zenodo.org/records/4588239"
DATASET_DOI = "10.5281/zenodo.4588239"
ARCHIVE_FILENAME = "LIT_PCBA_AVE_docked_released.tar.xz"
ARCHIVE_MD5 = "931de7c5b7904ab6e3a97ddef244b2d4"
ARCHIVE_SIZE_GB = 1.6
SUITE_ID = "lit_pcba_virtual_screening"
BENCHMARK_FAMILY = "protein_ligand_virtual_screening"
PRIMARY_METRIC = "EF1"
PRIMARY_METRIC_THRESHOLD = 1.2

CLAIM_BOUNDARY = (
    "LIT-PCBA materialization manifest only; it validates local benchmark source files and can standardize "
    "operator-provided score/label CSVs into the local LIT-PCBA scorecard schema. It does not download datasets, "
    "extract archives, run docking, compute scorecard metrics, submit predictions, send email, or mutate external state "
    "outside the requested output CSV/manifest paths."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): _text(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _write_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _standardize_scores(
    source_score_csv: Path,
    *,
    target_col: str,
    ligand_col: str,
    score_col: str,
    out_scores_csv: Path,
) -> tuple[bool, int, list[str]]:
    rows = _read_rows(source_score_csv)
    blockers: list[str] = []
    if not rows:
        return False, 0, ["source_score_rows_missing"]
    missing = [col for col in (target_col, ligand_col, score_col) if col not in rows[0]]
    if missing:
        return False, 0, ["source_score_columns_missing=" + ";".join(missing)]
    out_rows = [
        {
            "target": _text(row.get(target_col)),
            "ligand_id": _text(row.get(ligand_col)),
            "binding_score": _text(row.get(score_col)),
        }
        for row in rows
        if _text(row.get(target_col)) and _text(row.get(ligand_col)) and _text(row.get(score_col))
    ]
    if not out_rows:
        blockers.append("standardized_score_rows_empty")
    else:
        _write_rows(out_scores_csv, out_rows, ["target", "ligand_id", "binding_score"])
    return not blockers, len(out_rows), blockers


def _standardize_labels(
    source_label_csv: Path,
    *,
    target_col: str,
    ligand_col: str,
    binder_col: str,
    out_labels_csv: Path,
) -> tuple[bool, int, list[str]]:
    rows = _read_rows(source_label_csv)
    blockers: list[str] = []
    if not rows:
        return False, 0, ["source_label_rows_missing"]
    missing = [col for col in (target_col, ligand_col, binder_col) if col not in rows[0]]
    if missing:
        return False, 0, ["source_label_columns_missing=" + ";".join(missing)]
    out_rows = []
    for row in rows:
        target = _text(row.get(target_col))
        ligand = _text(row.get(ligand_col))
        raw_binder = _text(row.get(binder_col)).lower()
        if not target or not ligand:
            continue
        is_binder = "1" if raw_binder in {"1", "true", "yes", "active", "binder"} else "0"
        out_rows.append({"target": target, "ligand_id": ligand, "is_binder": is_binder})
    if not out_rows:
        blockers.append("standardized_label_rows_empty")
    else:
        _write_rows(out_labels_csv, out_rows, ["target", "ligand_id", "is_binder"])
    return not blockers, len(out_rows), blockers


def build_lit_pcba_materialization_manifest(
    *,
    archive_path: str | Path,
    extracted_dir: str | Path,
    source_score_csv: str | Path,
    source_label_csv: str | Path,
    out_scores_csv: str | Path,
    out_labels_csv: str | Path,
    target_col: str = "target",
    ligand_col: str = "ligand_id",
    score_col: str = "binding_score",
    binder_col: str = "is_binder",
    verify_md5: bool = False,
) -> dict[str, Any]:
    archive = Path(archive_path)
    extracted = Path(extracted_dir)
    source_scores = Path(source_score_csv)
    source_labels = Path(source_label_csv)
    out_scores = Path(out_scores_csv)
    out_labels = Path(out_labels_csv)
    materialization_command = (
        "python3 tools/build_lit_pcba_materialization_manifest.py "
        f"--archive-path {archive} --extracted-dir {extracted} "
        f"--source-score-csv {source_scores} --source-label-csv {source_labels} "
        f"--out-scores-csv {out_scores} --out-labels-csv {out_labels} "
        f"--target-col {target_col} --ligand-col {ligand_col} --score-col {score_col} --binder-col {binder_col}"
    )

    archive_present = archive.exists()
    extracted_present = extracted.exists() and extracted.is_dir()
    source_scores_present = source_scores.exists()
    source_labels_present = source_labels.exists()
    archive_md5_observed = ""
    archive_md5_ok = None
    if archive_present and verify_md5:
        archive_md5_observed = _md5(archive)
        archive_md5_ok = archive_md5_observed == ARCHIVE_MD5

    score_standardized = out_scores.exists()
    label_standardized = out_labels.exists()
    score_row_count = 0
    label_row_count = 0
    blockers: list[str] = []
    if not archive_present:
        blockers.append("zenodo_archive_missing")
    if verify_md5 and archive_present and not archive_md5_ok:
        blockers.append("zenodo_archive_md5_mismatch")
    if not extracted_present:
        blockers.append("extracted_dir_missing")
    if source_scores_present:
        score_standardized, score_row_count, score_blockers = _standardize_scores(
            source_scores,
            target_col=target_col,
            ligand_col=ligand_col,
            score_col=score_col,
            out_scores_csv=out_scores,
        )
        blockers.extend(score_blockers)
    elif not score_standardized:
        blockers.append("source_score_csv_missing")
    if source_labels_present:
        label_standardized, label_row_count, label_blockers = _standardize_labels(
            source_labels,
            target_col=target_col,
            ligand_col=ligand_col,
            binder_col=binder_col,
            out_labels_csv=out_labels,
        )
        blockers.extend(label_blockers)
    elif not label_standardized:
        blockers.append("source_label_csv_missing")

    out_scores_present = out_scores.exists()
    out_labels_present = out_labels.exists()
    operator_input_artifacts = [str(archive), str(extracted), str(source_scores), str(source_labels)]
    operator_output_artifacts = [str(out_scores), str(out_labels)]
    missing_input_artifacts = [
        path
        for path, present in (
            (str(archive), archive_present),
            (str(extracted), extracted_present),
            (str(source_scores), source_scores_present),
            (str(source_labels), source_labels_present),
        )
        if not present
    ]
    missing_output_artifacts = [
        path for path, present in ((str(out_scores), out_scores_present), (str(out_labels), out_labels_present)) if not present
    ]
    if out_scores_present and score_row_count == 0:
        score_row_count = len(_read_rows(out_scores))
    if out_labels_present and label_row_count == 0:
        label_row_count = len(_read_rows(out_labels))
    if not out_scores_present:
        blockers.append("standardized_scores_csv_missing")
    if not out_labels_present:
        blockers.append("standardized_labels_csv_missing")

    blockers = sorted(set(blockers))
    materialized = out_scores_present and out_labels_present and score_row_count > 0 and label_row_count > 0
    status = "lit_pcba_materialization_ready" if materialized and not blockers else "blocked_lit_pcba_materialization"
    summary = {
        "packet_type": "lit_pcba_materialization_manifest",
        "suite_id": SUITE_ID,
        "status": status,
        "materialized": materialized,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "benchmark_family": BENCHMARK_FAMILY,
        "dataset_source_url": DATASET_RECORD_URL,
        "dataset_record_url": DATASET_RECORD_URL,
        "dataset_doi": DATASET_DOI,
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_threshold": PRIMARY_METRIC_THRESHOLD,
        "archive_filename": ARCHIVE_FILENAME,
        "archive_md5_expected": ARCHIVE_MD5,
        "archive_md5_observed": archive_md5_observed,
        "archive_md5_ok": archive_md5_ok,
        "archive_size_gb": ARCHIVE_SIZE_GB,
        "archive_path": str(archive),
        "archive_present": archive_present,
        "extracted_dir": str(extracted),
        "extracted_dir_present": extracted_present,
        "source_score_csv": str(source_scores),
        "source_score_csv_present": source_scores_present,
        "source_label_csv": str(source_labels),
        "source_label_csv_present": source_labels_present,
        "out_scores_csv": str(out_scores),
        "out_scores_csv_present": out_scores_present,
        "out_labels_csv": str(out_labels),
        "out_labels_csv_present": out_labels_present,
        "operator_input_artifacts": ";".join(operator_input_artifacts),
        "operator_output_artifacts": ";".join(operator_output_artifacts),
        "missing_input_artifacts": ";".join(missing_input_artifacts),
        "missing_output_artifacts": ";".join(missing_output_artifacts),
        "score_row_count": score_row_count,
        "label_row_count": label_row_count,
        "target_col": target_col,
        "ligand_col": ligand_col,
        "score_col": score_col,
        "binder_col": binder_col,
        "run_command": materialization_command,
        "scorecard_run_command_template": (
            "python3 tools/build_lit_pcba_scorecard.py "
            f"--scores-csv {out_scores} --labels-csv {out_labels} --score-col {score_col} "
            "--product-provenance-json OPERATOR_FILL_PRODUCT_PROVENANCE_JSON"
        ),
        "external_state_mutated": False,
        "download_executed": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the LIT-PCBA scorecard against the standardized scores and labels."
            if status == "lit_pcba_materialization_ready"
            else "Place or extract the LIT-PCBA archive locally and provide source score/label CSVs for standardization."
        ),
    }
    rows = [
        {
            "check": "zenodo_archive_present",
            "status": "pass" if archive_present else "fail",
            "observed": str(archive),
            "required": ARCHIVE_FILENAME,
        },
        {
            "check": "standardized_scores_present",
            "status": "pass" if out_scores_present and score_row_count > 0 else "fail",
            "observed": f"{out_scores};rows={score_row_count}",
            "required": "non-empty target,ligand_id,binding_score CSV",
        },
        {
            "check": "standardized_labels_present",
            "status": "pass" if out_labels_present and label_row_count > 0 else "fail",
            "observed": f"{out_labels};rows={label_row_count}",
            "required": "non-empty target,ligand_id,is_binder CSV",
        },
    ]
    return {"summary": summary, "rows": rows}

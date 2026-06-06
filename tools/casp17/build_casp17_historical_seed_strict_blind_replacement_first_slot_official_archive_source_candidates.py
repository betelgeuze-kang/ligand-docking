#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html as html_lib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_ROUTE_BOARD_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json"
)
DEFAULT_SOURCE_DIR = "casp17/historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates"
DEFAULT_OUT_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates_current.csv"
)
DEFAULT_OUT_MD = (
    "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_FIRST_SLOT_OFFICIAL_ARCHIVE_SOURCE_CANDIDATES.md"
)

DEFAULT_ARCHIVE_SOURCES = [
    {
        "source_id": "casp16_regular_predictions",
        "competition": "CASP16",
        "prediction_index_url": "https://predictioncenter.org/download_area/CASP16/predictions/regular/",
        "targetlist_url": "https://predictioncenter.org/casp16/targetlist.cgi?view_targets=all",
        "native_public_anchor_url": "https://predictioncenter.org/download_area/CASP16/targets/",
        "native_public_anchor_date": "2025-02-01",
        "native_public_anchor_note": "CASP16 download_area targets directory public anchor",
    },
    {
        "source_id": "casp15_regular_predictions",
        "competition": "CASP15",
        "prediction_index_url": "https://predictioncenter.org/download_area/CASP15/predictions/regular/",
        "targetlist_url": "https://predictioncenter.org/casp15/targetlist.cgi?view_targets=all",
        "native_public_anchor_url": "https://predictioncenter.org/download_area/CASP15/targets/",
        "native_public_anchor_date": "2022-12-20",
        "native_public_anchor_note": "CASP15 public target archive date",
    },
]

ROW_COLUMNS = [
    "candidate_id",
    "competition",
    "source_id",
    "target_id",
    "source_scope",
    "source_category",
    "prediction_index_url",
    "prediction_tarball_url",
    "prediction_archive_modified_at",
    "prediction_archive_size",
    "targetlist_url",
    "targetlist_target_url",
    "targetlist_metadata_status",
    "targetlist_type",
    "targetlist_entry_date",
    "targetlist_server_expiration_date",
    "targetlist_human_expiration_date",
    "targetlist_capri_marker",
    "targetlist_special_mode",
    "target_description",
    "native_pdb_code",
    "native_pdb_url",
    "native_pdb_download_url",
    "native_mmcif_download_url",
    "native_structure_file_url",
    "native_structure_file_format",
    "native_pdb_download_status",
    "native_authority_status",
    "native_public_anchor_url",
    "native_public_anchor_date",
    "pre_native_by_archive_timing",
    "candidate_status",
    "source_folder",
    "operator_value_preview",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 official-archive source candidate board only. It locates official CASP15/16 monomer/domain "
    "prediction tarballs whose archive timestamps precede a public native/target archive anchor. It does not "
    "download tarballs, extract models, prove no-leak provenance, compute metrics, mutate intake CSVs, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _date(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_source_config(path_like: str | Path | None) -> list[dict[str, Any]]:
    if not path_like:
        return [dict(source) for source in DEFAULT_ARCHIVE_SOURCES]
    payload = _read_json(path_like)
    sources = payload.get("sources")
    return [source for source in sources if isinstance(source, dict)] if isinstance(sources, list) else []


def _read_text_source(source: dict[str, Any], path_key: str, url_key: str) -> tuple[str, str]:
    path_text = _text(source.get(path_key))
    if path_text:
        path = _resolve(path_text)
        return path.read_text(encoding="utf-8"), _artifact(path)
    url = _text(source.get(url_key))
    if not url:
        return "", ""
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace"), url


def _read_index_text_from_source(source: dict[str, Any]) -> tuple[str, str]:
    return _read_text_source(source, "prediction_index_path", "prediction_index_url")


def _read_targetlist_text_from_source(source: dict[str, Any]) -> tuple[str, str]:
    return _read_text_source(source, "targetlist_path", "targetlist_url")


def _tarball_rows(source: dict[str, Any], html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    index_url = _text(source.get("prediction_index_url"))
    pattern = re.compile(
        r'href="(?P<name>T[^"]+?\.tar\.gz)".*?(?P<date>\d{4}-\d{2}-\d{2})\s+'
        r'(?P<time>\d{2}:\d{2})\s*</td><td[^>]*>\s*(?P<size>[^<]+)',
        re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        tarball_name = match.group("name")
        target_id = tarball_name.removesuffix(".tar.gz")
        if target_id.endswith("o"):
            continue
        rows.append(
            {
                "target_id": target_id,
                "tarball_name": tarball_name,
                "prediction_archive_modified_at": f"{match.group('date')} {match.group('time')}",
                "prediction_archive_size": match.group("size").strip(),
                "prediction_tarball_url": urljoin(index_url, tarball_name) if index_url else tarball_name,
            }
        )
    return rows


def _plain_html(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", fragment, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return html_lib.unescape(re.sub(r"\s+", " ", text)).strip()


def _unique_csv(values: list[str]) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.lower().strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return ",".join(unique)


def _targetlist_dates(row_text: str) -> list[str]:
    return re.findall(r"\d{4}-\d{2}-\d{2}", row_text)


def _targetlist_type(row_text: str, target_id: str) -> str:
    escaped_target = re.escape(target_id)
    match = re.search(
        rf"\b{escaped_target}\b\s+\*?\s*(?P<target_type>.+?)\s+\d+\s+.+?\s+\d{{4}}-\d{{2}}-\d{{2}}",
        row_text,
    )
    return _text(match.group("target_type")) if match else ""


def _target_description(row_html: str) -> str:
    if '<td class="table_row_right"' not in row_html:
        return ""
    description_fragment = row_html.rsplit('<td class="table_row_right"', 1)[-1]
    if ">" in description_fragment:
        description_fragment = description_fragment.split(">", 1)[1]
    description = _plain_html(description_fragment)
    description = re.sub(
        r"\bPDB codes?:?\s*(?:[A-Za-z0-9]{4})(?:\s*,\s*[A-Za-z0-9]{4})*",
        "",
        description,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", description).strip(" -")


def _fallback_pdb_codes(row_text: str) -> list[str]:
    codes: list[str] = []
    for match in re.finditer(
        r"\bPDB codes?:?\s*((?:[A-Za-z0-9]{4})(?:\s*,\s*[A-Za-z0-9]{4})*)",
        row_text,
        flags=re.IGNORECASE,
    ):
        codes.extend(re.findall(r"\b[A-Za-z0-9]{4}\b", match.group(1)))
    return codes


def _targetlist_metadata(source: dict[str, Any], html: str, targetlist_ref: str) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    targetlist_url = _text(source.get("targetlist_url"))
    base_url = targetlist_url or targetlist_ref
    for fragment in html.split("<tr class=datarow>")[1:]:
        row_html = fragment.split("<tr class=datarow>", 1)[0]
        target_match = re.search(
            r'target\.cgi\?id=(?P<target_number>\d+)&view=all">(?P<target_id>[A-Z]\d+(?:s\d+|v\d+)?)</a>(?P<after>[^<]*)',
            row_html,
            flags=re.IGNORECASE,
        )
        if not target_match:
            continue
        target_id = target_match.group("target_id")
        row_text = _plain_html(row_html)
        dates = _targetlist_dates(row_text)
        pdb_codes = re.findall(r"rcsb\.org/structure/([A-Za-z0-9]{4})", row_html, flags=re.IGNORECASE)
        if not pdb_codes:
            pdb_codes = _fallback_pdb_codes(row_text)
        target_type = _targetlist_type(row_text, target_id)
        target_url = (
            urljoin(base_url, f"target.cgi?id={target_match.group('target_number')}&view=all") if base_url else ""
        )
        metadata[target_id] = {
            "targetlist_url": targetlist_ref or targetlist_url,
            "targetlist_target_url": target_url,
            "targetlist_metadata_status": "targetlist_metadata_present",
            "targetlist_type": target_type,
            "targetlist_entry_date": dates[0] if len(dates) > 0 else "",
            "targetlist_server_expiration_date": dates[1] if len(dates) > 1 else "",
            "targetlist_human_expiration_date": dates[3] if len(dates) > 3 else (dates[2] if len(dates) > 2 else ""),
            "targetlist_capri_marker": str("*" in target_match.group("after")),
            "targetlist_special_mode": (
                "ligand_or_ensemble_flagged" if any(flag in target_type for flag in ["/Ligand", "/Ensmbl"]) else "regular_like"
            ),
            "target_description": _target_description(row_html),
            "native_pdb_code": _unique_csv(pdb_codes),
            "native_pdb_url": (
                ",".join(f"https://www.rcsb.org/structure/{code}" for code in _unique_csv(pdb_codes).split(",") if code)
            ),
        }
    return metadata


def _empty_metadata(source: dict[str, Any]) -> dict[str, str]:
    return {
        "targetlist_url": _text(source.get("targetlist_url")),
        "targetlist_target_url": "",
        "targetlist_metadata_status": "targetlist_metadata_missing",
        "targetlist_type": "",
        "targetlist_entry_date": "",
        "targetlist_server_expiration_date": "",
        "targetlist_human_expiration_date": "",
        "targetlist_capri_marker": "False",
        "targetlist_special_mode": "",
        "target_description": "",
        "native_pdb_code": "",
        "native_pdb_url": "",
    }


def _head_ok(url: str) -> bool:
    try:
        with urlopen(Request(url, method="HEAD"), timeout=15):
            return True
    except Exception:
        return False


def _native_download_fields(native_pdb_code: str, check_downloads: bool, cache: dict[str, dict[str, str]]) -> dict[str, str]:
    first_code = _text(native_pdb_code).split(",")[0].strip().upper()
    if not first_code:
        return {
            "native_pdb_download_url": "",
            "native_mmcif_download_url": "",
            "native_structure_file_url": "",
            "native_structure_file_format": "",
            "native_pdb_download_status": "native_pdb_code_missing",
        }
    if first_code in cache:
        return dict(cache[first_code])
    pdb_url = f"https://files.rcsb.org/download/{first_code}.pdb"
    cif_url = f"https://files.rcsb.org/download/{first_code}.cif"
    status = "not_checked"
    structure_url = pdb_url
    structure_format = "pdb"
    if check_downloads:
        if _head_ok(pdb_url):
            status = "pdb_available"
        elif _head_ok(cif_url):
            status = "pdb_unavailable_cif_available"
            structure_url = cif_url
            structure_format = "mmcif"
        else:
            status = "native_structure_download_unavailable"
            structure_url = ""
            structure_format = ""
    fields = {
        "native_pdb_download_url": pdb_url,
        "native_mmcif_download_url": cif_url,
        "native_structure_file_url": structure_url,
        "native_structure_file_format": structure_format,
        "native_pdb_download_status": status,
    }
    cache[first_code] = fields
    return dict(fields)


def _source_category(target_id: str) -> str:
    if re.match(r"^T\d+s\d+$", target_id):
        return "domain_subunit"
    if re.match(r"^T\d+v\d+$", target_id):
        return "variant"
    return "regular_monomer"


def _source_folder(source_dir: str | Path, index: int, competition: str, target_id: str) -> Path:
    safe_target = target_id.lower().replace("/", "_").replace(" ", "_")
    return _resolve(source_dir) / f"{index:03d}_{competition.lower()}_{safe_target}"


def _operator_value_preview(row: dict[str, Any]) -> str:
    return (
        f"replacement_target_id={row['competition']}_{row['target_id']};"
        f"prediction_pdb=extract_from:{row['prediction_tarball_url']};"
        f"native_pdb=fetch_from:{row['native_structure_file_url'] or row['native_pdb_url'] or row['native_public_anchor_url']};"
        f"prediction_created_at={row['prediction_archive_modified_at'][:10]};"
        f"native_release_date={row['native_public_anchor_date']}"
    )


def _candidate_status(pre_native: bool, native_pdb_code: str) -> str:
    if not pre_native:
        return "blocked_archive_timing_not_pre_native"
    if native_pdb_code:
        return "pre_native_archive_candidate_native_authority_ready_for_download"
    return "pre_native_archive_candidate_native_authority_lookup_required"


def _native_authority_status(native_pdb_code: str) -> str:
    return "native_pdb_code_present" if native_pdb_code else "native_pdb_code_lookup_required"


def _selection_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, int, int, str, str]:
    pre_native = row.get("pre_native_by_archive_timing") == "True"
    native_ready = bool(_text(row.get("native_pdb_code")))
    native_download_status = _text(row.get("native_pdb_download_status"))
    native_download_priority = {
        "pdb_available": 0,
        "not_checked": 1,
        "": 1,
        "pdb_unavailable_cif_available": 2,
        "native_structure_download_unavailable": 3,
        "native_pdb_code_missing": 4,
    }.get(native_download_status, 3)
    capri_marker = row.get("targetlist_capri_marker") == "True"
    special_mode = _text(row.get("targetlist_special_mode"))
    return (
        0 if pre_native else 1,
        0 if native_ready else 1,
        native_download_priority,
        0 if not capri_marker else 1,
        0 if special_mode != "ligand_or_ensemble_flagged" else 1,
        0 if row.get("source_category") == "regular_monomer" else 1,
        _text(row.get("prediction_archive_modified_at")),
        _text(row.get("target_id")),
    )


def _build_rows(
    sources: list[dict[str, Any]],
    max_candidates_per_source: int,
    source_dir: str | Path,
    check_native_pdb_downloads: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    input_blockers: list[str] = []
    index = 1
    native_download_cache: dict[str, dict[str, str]] = {}
    for source in sources:
        try:
            html, index_ref = _read_index_text_from_source(source)
        except Exception as exc:  # pragma: no cover - exercised through status, not stack detail
            input_blockers.append(f"{_text(source.get('source_id')) or 'source'}_index_fetch_failed:{exc.__class__.__name__}")
            continue
        target_metadata: dict[str, dict[str, str]] = {}
        try:
            targetlist_html, targetlist_ref = _read_targetlist_text_from_source(source)
        except Exception as exc:  # pragma: no cover - exercised through status, not stack detail
            targetlist_ref = _text(source.get("targetlist_url"))
            input_blockers.append(
                f"{_text(source.get('source_id')) or 'source'}_targetlist_fetch_failed:{exc.__class__.__name__}"
            )
        else:
            target_metadata = _targetlist_metadata(source, targetlist_html, targetlist_ref)
        source_rows = _tarball_rows(source, html)
        source_rows.sort(key=lambda row: (row["prediction_archive_modified_at"], row["target_id"]))
        enriched_rows: list[dict[str, Any]] = []
        for source_row in source_rows:
            prediction_date = _date(source_row["prediction_archive_modified_at"])
            native_anchor_date = _date(source.get("native_public_anchor_date"))
            pre_native = bool(prediction_date and native_anchor_date and prediction_date < native_anchor_date)
            competition = _text(source.get("competition"))
            target_id = source_row["target_id"]
            metadata = target_metadata.get(target_id, _empty_metadata(source))
            row = {
                "candidate_id": "",
                "competition": competition,
                "source_id": _text(source.get("source_id")),
                "target_id": target_id,
                "source_scope": "monomer",
                "source_category": _source_category(target_id),
                "prediction_index_url": index_ref,
                "prediction_tarball_url": source_row["prediction_tarball_url"],
                "prediction_archive_modified_at": source_row["prediction_archive_modified_at"],
                "prediction_archive_size": source_row["prediction_archive_size"],
                "targetlist_url": metadata["targetlist_url"],
                "targetlist_target_url": metadata["targetlist_target_url"],
                "targetlist_metadata_status": metadata["targetlist_metadata_status"],
                "targetlist_type": metadata["targetlist_type"],
                "targetlist_entry_date": metadata["targetlist_entry_date"],
                "targetlist_server_expiration_date": metadata["targetlist_server_expiration_date"],
                "targetlist_human_expiration_date": metadata["targetlist_human_expiration_date"],
                "targetlist_capri_marker": metadata["targetlist_capri_marker"],
                "targetlist_special_mode": metadata["targetlist_special_mode"],
                "target_description": metadata["target_description"],
                "native_pdb_code": metadata["native_pdb_code"],
                "native_pdb_url": metadata["native_pdb_url"],
                "native_pdb_download_url": "",
                "native_mmcif_download_url": "",
                "native_structure_file_url": "",
                "native_structure_file_format": "",
                "native_pdb_download_status": "",
                "native_authority_status": _native_authority_status(metadata["native_pdb_code"]),
                "native_public_anchor_url": _text(source.get("native_public_anchor_url")),
                "native_public_anchor_date": _text(source.get("native_public_anchor_date")),
                "pre_native_by_archive_timing": str(pre_native),
                "candidate_status": _candidate_status(pre_native, metadata["native_pdb_code"]),
                "source_folder": "",
                "operator_value_preview": "",
                "next_action": (
                    "download official prediction tarball and RCSB native PDB, extract model1/top5/native evidence, "
                    "then rerun strict-blind evidence dropzones"
                    if pre_native and metadata["native_pdb_code"]
                    else (
                        "resolve the targetlist native PDB code before download/import"
                        if pre_native
                        else "choose a tarball whose prediction archive timestamp predates the native public anchor"
                    )
                ),
            }
            enriched_rows.append(row)
        enriched_rows.sort(key=_selection_sort_key)
        candidate_pool_size = max(max_candidates_per_source, max_candidates_per_source * 4)
        candidate_pool = enriched_rows[:candidate_pool_size]
        for row in candidate_pool:
            row.update(
                _native_download_fields(
                    row["native_pdb_code"],
                    check_downloads=check_native_pdb_downloads,
                    cache=native_download_cache,
                )
            )
        candidate_pool.sort(key=_selection_sort_key)
        for row in candidate_pool[:max_candidates_per_source]:
            folder = _source_folder(source_dir, index, row["competition"], row["target_id"])
            row["candidate_id"] = f"official_archive_source_{index:03d}"
            row["source_folder"] = _artifact(folder)
            row["operator_value_preview"] = _operator_value_preview(row)
            rows.append(row)
            index += 1
    return rows, input_blockers


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if not rows and input_blockers:
        return "blocked_official_archive_index_unavailable"
    if any(row["candidate_status"] == "pre_native_archive_candidate_native_authority_ready_for_download" for row in rows):
        return "first_slot_official_archive_native_authority_candidates_available"
    if any(row["candidate_status"] == "pre_native_archive_candidate_native_authority_lookup_required" for row in rows):
        return "first_slot_official_archive_pre_native_candidates_need_native_authority_lookup"
    if input_blockers:
        return "blocked_official_archive_candidates_partial_index_unavailable"
    return "blocked_no_pre_native_archive_candidates"


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    source_route_payload: dict[str, Any],
    sources: list[dict[str, Any]],
    input_blockers: list[str],
) -> dict[str, Any]:
    ready_rows = [
        row
        for row in rows
        if row["candidate_status"] == "pre_native_archive_candidate_native_authority_ready_for_download"
    ]
    pre_native_rows = [row for row in rows if row["pre_native_by_archive_timing"] == "True"]
    lookup_rows = [
        row
        for row in rows
        if row["candidate_status"] == "pre_native_archive_candidate_native_authority_lookup_required"
    ]
    first_ready = ready_rows[0] if ready_rows else {}
    competitions = sorted({_text(row.get("competition")) for row in rows if _text(row.get("competition"))})
    return {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_first_slot_official_archive_source_candidates_status": _overall_status(
            rows, input_blockers
        ),
        "source_route_board_json": _artifact(args.source_route_board_json),
        "source_route_board_status": _text(
            _summary(source_route_payload).get("strict_blind_replacement_first_slot_source_route_board_status")
        ),
        "required_benchmark_id": _text(_summary(source_route_payload).get("required_benchmark_id")),
        "required_target_id": _text(_summary(source_route_payload).get("required_target_id")),
        "required_scope": _text(_summary(source_route_payload).get("required_scope")) or "monomer",
        "source_count": len(sources),
        "source_competitions": ",".join(competitions),
        "candidate_count": len(rows),
        "pre_native_candidate_count": len(pre_native_rows),
        "ready_candidate_count": len(ready_rows),
        "blocked_candidate_count": len(rows) - len(ready_rows),
        "native_authority_ready_count": len(ready_rows),
        "native_authority_lookup_required_count": len(lookup_rows),
        "native_pdb_download_ready_count": sum(1 for row in rows if row["native_pdb_download_status"] == "pdb_available"),
        "native_mmcif_only_count": sum(1 for row in rows if row["native_pdb_download_status"] == "pdb_unavailable_cif_available"),
        "targetlist_metadata_present_count": sum(
            1 for row in rows if row["targetlist_metadata_status"] == "targetlist_metadata_present"
        ),
        "targetlist_capri_marker_count": sum(1 for row in rows if row["targetlist_capri_marker"] == "True"),
        "targetlist_special_mode_count": sum(
            1 for row in rows if row["targetlist_special_mode"] == "ligand_or_ensemble_flagged"
        ),
        "regular_monomer_count": sum(1 for row in rows if row["source_category"] == "regular_monomer"),
        "domain_subunit_count": sum(1 for row in rows if row["source_category"] == "domain_subunit"),
        "variant_count": sum(1 for row in rows if row["source_category"] == "variant"),
        "first_ready_candidate_id": _text(first_ready.get("candidate_id")),
        "first_ready_competition": _text(first_ready.get("competition")),
        "first_ready_target_id": _text(first_ready.get("target_id")),
        "first_ready_prediction_archive_modified_at": _text(first_ready.get("prediction_archive_modified_at")),
        "first_ready_native_public_anchor_date": _text(first_ready.get("native_public_anchor_date")),
        "first_ready_prediction_tarball_url": _text(first_ready.get("prediction_tarball_url")),
        "first_ready_targetlist_target_url": _text(first_ready.get("targetlist_target_url")),
        "first_ready_native_pdb_code": _text(first_ready.get("native_pdb_code")),
        "first_ready_native_pdb_url": _text(first_ready.get("native_pdb_url")),
        "first_ready_native_structure_file_url": _text(first_ready.get("native_structure_file_url")),
        "first_ready_native_structure_file_format": _text(first_ready.get("native_structure_file_format")),
        "first_ready_native_pdb_download_status": _text(first_ready.get("native_pdb_download_status")),
        "first_ready_target_description": _text(first_ready.get("target_description")),
        "first_ready_targetlist_capri_marker": _text(first_ready.get("targetlist_capri_marker")),
        "first_ready_operator_value_preview": _text(first_ready.get("operator_value_preview")),
        "source_dir": _artifact(args.source_dir),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_route_payload = _read_json(args.source_route_board_json)
    sources = _read_source_config(args.archive_source_json)
    input_blockers = []
    if not _resolve(args.source_route_board_json).exists():
        input_blockers.append("first_slot_source_route_board_json_missing")
    if not sources:
        input_blockers.append("archive_source_config_missing")
    rows, source_blockers = _build_rows(
        sources,
        args.max_candidates_per_source,
        args.source_dir,
        check_native_pdb_downloads=bool(args.check_native_pdb_downloads),
    )
    input_blockers.extend(source_blockers)
    summary = _build_summary(args, rows, source_route_payload, sources, input_blockers)
    return {"summary": summary, "rows": rows}


def _write_source_md(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['competition']} {row['target_id']} Official Archive Source Candidate",
        "",
        f"- candidate: `{row['candidate_id']}`",
        f"- status: `{row['candidate_status']}`",
        f"- category: `{row['source_category']}`",
        f"- prediction archive: `{row['prediction_tarball_url']}`",
        f"- prediction modified/native anchor: `{row['prediction_archive_modified_at']}` `{row['native_public_anchor_date']}`",
        f"- targetlist metadata/native: `{row['targetlist_metadata_status']}` `{row['native_pdb_code'] or '-'}` `{row['native_pdb_url'] or '-'}`",
        f"- native structure download: `{row['native_pdb_download_status']}` `{row['native_structure_file_format'] or '-'}` `{row['native_structure_file_url'] or '-'}`",
        f"- targetlist CAPRI marker: `{row['targetlist_capri_marker']}`",
        f"- target description: {row['target_description'] or '-'}",
        f"- operator preview: `{row['operator_value_preview']}`",
        f"- next action: {row['next_action']}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["source_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SOURCE_CANDIDATE.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "source_candidate.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement First Slot Official Archive Source Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_first_slot_official_archive_source_candidates_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id'] or '-'}` `{summary['required_target_id'] or '-'}` `{summary['required_scope'] or '-'}`",
        f"- sources/competitions: `{summary['source_count']}` `{summary['source_competitions'] or '-'}`",
        f"- candidates ready/blocked/total: `{summary['ready_candidate_count']}/{summary['blocked_candidate_count']}/{summary['candidate_count']}`",
        f"- pre-native/native-ready/native-lookup: `{summary['pre_native_candidate_count']}/{summary['native_authority_ready_count']}/{summary['native_authority_lookup_required_count']}`",
        f"- native PDB-ready/mmCIF-only: `{summary['native_pdb_download_ready_count']}/{summary['native_mmcif_only_count']}`",
        f"- targetlist metadata/CAPRI-marker/special-mode: `{summary['targetlist_metadata_present_count']}/{summary['targetlist_capri_marker_count']}/{summary['targetlist_special_mode_count']}`",
        f"- regular/domain/variant: `{summary['regular_monomer_count']}/{summary['domain_subunit_count']}/{summary['variant_count']}`",
        f"- first ready: `{summary['first_ready_candidate_id'] or '-'}` `{summary['first_ready_competition'] or '-'}` `{summary['first_ready_target_id'] or '-'}`",
        f"- first ready native PDB: `{summary['first_ready_native_pdb_code'] or '-'}` `{summary['first_ready_native_pdb_url'] or '-'}`",
        f"- first ready native structure file: `{summary['first_ready_native_structure_file_format'] or '-'}` `{summary['first_ready_native_structure_file_url'] or '-'}`",
        f"- first ready prediction/native anchor: `{summary['first_ready_prediction_archive_modified_at'] or '-'}` `{summary['first_ready_native_public_anchor_date'] or '-'}`",
        f"- next action: download first ready official prediction tarball and native/target archive into the strict-blind first-slot dropzone",
        "",
        "## Source Candidates",
        "",
        "| candidate | source | target | category | status | native PDB | native file | CAPRI marker | prediction modified | native anchor | tarball |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:120]:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['competition']}` | `{row['target_id']}` | `{row['source_category']}` | "
            f"`{row['candidate_status']}` | `{row['native_pdb_code'] or '-'}` | "
            f"`{row['native_pdb_download_status']}/{row['native_structure_file_format'] or '-'}` | `{row['targetlist_capri_marker']}` | "
            f"`{row['prediction_archive_modified_at']}` | "
            f"`{row['native_public_anchor_date']}` | `{row['prediction_tarball_url']}` |"
        )
    if len(payload["rows"]) > 120:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | `{len(payload['rows']) - 120} more rows in CSV` |")
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked` | - | - | - | - | - | rerun after source indexes are reachable |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_source_md(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build first-slot official archive source candidates.")
    parser.add_argument("--source-route-board-json", default=DEFAULT_SOURCE_ROUTE_BOARD_JSON)
    parser.add_argument("--archive-source-json", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--max-candidates-per-source", type=int, default=12)
    parser.add_argument("--check-native-pdb-downloads", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()

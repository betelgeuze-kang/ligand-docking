#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shlex
from pathlib import Path
from typing import Any

import numpy as np

from core.definitions import ResearchConstants

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPAIR_PACKET_JSON = "runs/wetlab_selected_allatom_repair_packet_current.json"
DEFAULT_ACCURACY_GATE_JSON = "runs/accuracy_gate_local_delivery_preflight_current.json"
DEFAULT_ACCURACY_GATE_CSV = "runs/accuracy_gate_local_delivery_preflight_current.csv"
DEFAULT_TARGET_REGISTRATION_JSON = "runs/strict_release_target_registration_packet_current.json"
DEFAULT_OUT_JSON = "runs/allatom_claim_evidence_handoff_current.json"
DEFAULT_OUT_MD = "runs/allatom_claim_evidence_handoff_current.md"
DEFAULT_TARGETS = "T. cruzi PDE"

STRICT_ACCURACY_GATE_FIELDS = (
    "avg_neighbor_jaccard",
    "avg_e2e_rmse_raw",
    "avg_e2e_rel_rmse_mean_clipped",
)
ACCURACY_EXTERNAL_REQUIRED_COLUMNS = (
    "target",
    "avg_rmsd_aligned",
    "avg_rmsd_vs_native_aligned",
)
STRICT_RELEASE_EXTERNAL_MANIFEST_REQUIRED_COLUMNS = ("target", "path")
STRICT_RELEASE_MD_ENGINE_RE = re.compile(r"(openmm|amber|gromacs)", flags=re.IGNORECASE)
FOLD_BALANCED_TARGET_ALIASES = ("noncyclic", "non_cyclic", "fold_balanced_noncyclic")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _quote(value: str) -> str:
    text = _text(value)
    return shlex.quote(text) if text else text


def _safe_float(value: Any) -> float | None:
    try:
        if value in {"", None, "missing"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value in {"", None, "missing"}:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _path_exists(path_text: str) -> bool:
    text = _text(path_text)
    return bool(text and "<" not in text and _resolve(text).exists())


def _load_json_if_exists(path_text: str) -> dict[str, Any]:
    if not _path_exists(path_text):
        return {}
    try:
        with _resolve(path_text).open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _csv_header_if_exists(path_text: str) -> list[str]:
    if not _path_exists(path_text):
        return []
    try:
        with _resolve(path_text).open("r", encoding="utf-8", newline="") as fh:
            return [str(col).strip() for col in next(csv.reader(fh), [])]
    except (OSError, StopIteration, csv.Error):
        return []


def _csv_rows_if_exists(path_text: str) -> list[dict[str, str]]:
    if not _path_exists(path_text):
        return []
    try:
        with _resolve(path_text).open("r", encoding="utf-8", newline="") as fh:
            return [
                {str(k).strip(): str(v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(fh)
            ]
    except (OSError, csv.Error):
        return []


def _iter_values(value: Any, *, key_hint: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            out.extend(_iter_values(child, key_hint=str(key)))
    elif isinstance(value, list):
        for child in value:
            out.extend(_iter_values(child, key_hint=key_hint))
    else:
        text = _text(value)
        if text:
            out.append((key_hint, text))
    return out


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _supported_target_map() -> dict[str, str]:
    return {_normalize_target_key(k): k for k in ResearchConstants.CHALLENGES.keys()}


def _parse_target_spec(targets: str) -> list[str]:
    spec = _text(targets, DEFAULT_TARGETS)
    spec_lower = spec.lower()
    if spec_lower == "all" or spec_lower in FOLD_BALANCED_TARGET_ALIASES:
        return list(ResearchConstants.CHALLENGES.keys())
    return _dedupe([part.strip() for part in spec.split(",")])


def _strict_release_target_support_status(targets: str) -> dict[str, Any]:
    requested_targets = _parse_target_spec(targets)
    target_map = _supported_target_map()
    supported_targets: list[str] = []
    unsupported_targets: list[str] = []
    mapped_targets: dict[str, str] = {}
    for target in requested_targets:
        mapped = target_map.get(_normalize_target_key(target))
        if mapped:
            supported_targets.append(target)
            mapped_targets[target] = mapped
        else:
            unsupported_targets.append(target)
    ready = bool(requested_targets and not unsupported_targets)
    reason = ""
    if not requested_targets:
        reason = "missing_strict_release_targets"
    elif unsupported_targets:
        reason = "unsupported_strict_release_targets:" + ",".join(unsupported_targets)
    return {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "targets": requested_targets,
        "supported_targets": supported_targets,
        "unsupported_targets": unsupported_targets,
        "mapped_targets": mapped_targets,
        "available_targets": list(ResearchConstants.CHALLENGES.keys()),
        "normalization": "lowercase_alphanumeric",
        "reason": reason,
    }


def _target_registration_packet_status(path_text: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ready": False,
        "status": "missing",
        "path": "",
        "reason": "candidate_not_provided",
        "blockers": [],
        "canonical_chain_ready": False,
        "canonical_chain": "",
        "recommended_canonical_chain": "",
        "selected_chain_ca_count": None,
        "selected_chain_seqres_count": None,
        "selected_chain_missing_residue_count": None,
        "next_required_step": "",
    }
    if not _text(path_text):
        return base
    if not _path_exists(path_text):
        return {**base, "path": path_text, "reason": "candidate_not_found"}

    payload = _load_json_if_exists(path_text)
    if not payload:
        return {
            **base,
            "status": "blocked",
            "path": path_text,
            "reason": "invalid_or_unreadable_json",
        }

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    registry = (
        payload.get("strict_release_registry")
        if isinstance(payload.get("strict_release_registry"), dict)
        else {}
    )
    blockers = [
        _text(value)
        for value in summary.get("blockers", [])
        if _text(value)
    ] if isinstance(summary.get("blockers", []), list) else []
    ready = bool(summary.get("registration_ready"))
    reason = "" if ready else ",".join(blockers) or _text(summary.get("status"), "blocked")
    return {
        **base,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "path": path_text,
        "reason": reason,
        "blockers": blockers,
        "canonical_chain_ready": bool(summary.get("canonical_chain_ready")),
        "canonical_chain": _text(registry.get("canonical_chain")),
        "recommended_canonical_chain": _text(registry.get("recommended_canonical_chain")),
        "selected_chain_ca_count": _safe_int(registry.get("selected_chain_ca_count")),
        "selected_chain_seqres_count": _safe_int(registry.get("selected_chain_seqres_count")),
        "selected_chain_missing_residue_count": _safe_int(
            registry.get("selected_chain_missing_residue_count")
        ),
        "next_required_step": _text(summary.get("next_required_step")),
    }


def _normalize_representation(raw: Any) -> str:
    text = _text(raw).lower()
    if not text or text in {"ca", "ca_only", "ca_bead"}:
        return "ca"
    if text in {"ca_sc_2bead", "ca_sc", "2bead", "two_bead", "ca_sc_explicit"}:
        return "ca_sc_2bead"
    return text


def _coerce_coords_array(arr: Any, *, frame: int | None) -> np.ndarray:
    coords = np.asarray(arr)
    if coords.ndim == 3:
        idx = coords.shape[0] - 1 if frame is None else int(frame)
        if idx < 0:
            idx = coords.shape[0] + idx
        if idx < 0 or idx >= coords.shape[0]:
            raise ValueError(f"frame_out_of_range:{idx}")
        coords = coords[idx]
    if coords.ndim != 2:
        raise ValueError(f"invalid_coordinate_shape:{coords.shape}")
    if coords.shape[1] != 3 and coords.shape[0] == 3:
        coords = coords.T
    if coords.shape[1] != 3:
        raise ValueError(f"invalid_coordinate_shape:{coords.shape}")
    return coords


def _load_coords_csv(path: Path, *, frame: int | None) -> np.ndarray:
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("empty_coordinate_csv")
    columns = set(rows[0].keys())
    xyz_columns = None
    for candidate in (("x", "y", "z"), ("coord_x", "coord_y", "coord_z"), ("X", "Y", "Z")):
        if set(candidate).issubset(columns):
            xyz_columns = candidate
            break
    if xyz_columns is None:
        raise ValueError("missing_xyz_columns")
    selected_rows = rows
    if "frame" in columns:
        frame_values = [int(row["frame"]) for row in rows if _text(row.get("frame"))]
        selected = max(frame_values) if frame is None else int(frame)
        selected_rows = [row for row in rows if _safe_int(row.get("frame")) == selected]
        if not selected_rows:
            raise ValueError(f"frame_not_found:{selected}")
    arr = np.asarray(
        [[float(row[col]) for col in xyz_columns] for row in selected_rows],
        dtype=np.float32,
    )
    return _coerce_coords_array(arr, frame=None)


def _load_strict_release_coords(path_text: str, *, key: str, frame: str) -> np.ndarray:
    path = _resolve(path_text)
    frame_i = _safe_int(frame) if _text(frame) else None
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return _coerce_coords_array(np.load(path, mmap_mode="r"), frame=frame_i)
    if suffix == ".npz":
        with np.load(path) as archive:
            if key:
                if key not in archive:
                    raise KeyError(key)
                arr = archive[key]
            else:
                if not archive.files:
                    raise ValueError("empty_npz")
                arr = archive[archive.files[0]]
            return _coerce_coords_array(arr, frame=frame_i)
    if suffix == ".csv":
        return _load_coords_csv(path, frame=frame_i)
    raise ValueError(f"unsupported_coordinate_extension:{suffix}")


def _strict_release_external_manifest_row_reasons(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    target_raw = _text(row.get("target"))
    path_raw = _text(row.get("path"))
    engine_raw = _text(row.get("engine"))
    representation = _normalize_representation(row.get("representation"))

    if not target_raw:
        reasons.append("missing_target")
    if not path_raw:
        reasons.append("missing_path")
    if not engine_raw or STRICT_RELEASE_MD_ENGINE_RE.search(engine_raw) is None:
        reasons.append("engine_not_md")

    expected_n_atoms: int | None = None
    if target_raw:
        mapped = _supported_target_map().get(_normalize_target_key(target_raw))
        if mapped is None:
            reasons.extend(["unknown_target", "unsupported_target"])
        else:
            n_res = int(ResearchConstants.CHALLENGES[mapped]["n_res"])
            if representation == "ca":
                expected_n_atoms = n_res
            elif representation == "ca_sc_2bead":
                expected_n_atoms = 2 * n_res
            else:
                reasons.append(f"unsupported_representation:{representation}")

    if path_raw and not _path_exists(path_raw):
        reasons.append("missing_file")

    coords: np.ndarray | None = None
    if path_raw and _path_exists(path_raw):
        try:
            coords = _load_strict_release_coords(
                path_raw,
                key=_text(row.get("key")),
                frame=_text(row.get("frame")),
            )
        except Exception as exc:
            reasons.append(f"load_error:{type(exc).__name__}")

    if coords is not None and expected_n_atoms is not None and coords.shape[0] != expected_n_atoms:
        reasons.append(
            f"n_atoms_mismatch:expected={expected_n_atoms},actual={int(coords.shape[0])}"
        )

    return reasons


def _candidate_paths_from_payload(payload: dict[str, Any], *, kind: str) -> list[str]:
    candidates: list[str] = []
    for key, value in _iter_values(payload):
        key_lower = key.lower()
        value_lower = value.lower()
        if kind == "strict":
            if "strict_summary_json" in key_lower or (
                "strict" in value_lower and value_lower.endswith(".json")
            ):
                candidates.append(value)
        elif kind == "accuracy_external":
            if "accuracy_external_csv" in key_lower or (
                "accuracy_external" in value_lower and value_lower.endswith(".csv")
            ):
                candidates.append(value)
    return _dedupe(candidates)


def _first_manifest_candidate(payload: dict[str, Any]) -> str:
    for key, value in _iter_values(payload):
        key_lower = key.lower()
        if "manifest" in key_lower and value.lower().endswith(".csv") and _path_exists(value):
            return value
    return ""


def _strict_summary_rejection_reason(path_text: str) -> str:
    if not _text(path_text):
        return "candidate_not_provided"
    if not _path_exists(path_text):
        return "candidate_not_found"
    payload = _load_json_if_exists(path_text)
    if not payload:
        return "invalid_or_unreadable_json"

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return "missing_summary"
    targets = _safe_int(summary.get("targets"))
    if targets is None or targets <= 0:
        return "missing_strict_release_target_count"

    gates = payload.get("gates")
    if not isinstance(gates, dict):
        return "missing_gates"
    accuracy_gate = gates.get("accuracy_gate")
    if not isinstance(accuracy_gate, dict):
        return "missing_accuracy_gate"
    missing_accuracy = [
        field for field in STRICT_ACCURACY_GATE_FIELDS if _safe_float(accuracy_gate.get(field)) is None
    ]
    if missing_accuracy:
        return "missing_strict_release_accuracy_gate:" + ",".join(missing_accuracy)

    speed = gates.get("speed")
    if not isinstance(speed, dict) or _safe_float(speed.get("avg_speedup_on_vs_off")) is None:
        return "missing_strict_release_speed_gate:avg_speedup_on_vs_off"

    long_stability = gates.get("long_stability")
    if not isinstance(long_stability, dict) or _safe_float(long_stability.get("passed_targets")) is None:
        return "missing_strict_release_long_stability_gate:passed_targets"

    return ""


def _accuracy_external_rejection_reason(path_text: str) -> str:
    if not _text(path_text):
        return "candidate_not_provided"
    if not _path_exists(path_text):
        return "candidate_not_found"
    header = _csv_header_if_exists(path_text)
    if not header:
        return "missing_or_unreadable_csv_header"
    header_set = set(header)
    missing = [col for col in ACCURACY_EXTERNAL_REQUIRED_COLUMNS if col not in header_set]
    if missing:
        return "missing_accuracy_external_columns:" + ",".join(missing)
    return ""


def _strict_release_external_manifest_rejection_reason(path_text: str) -> str:
    return str(
        _strict_release_external_manifest_validation(path_text, expected_targets=[])
        .get("reason", "")
    )


def _strict_release_external_manifest_validation(
    path_text: str,
    *,
    expected_targets: list[str],
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ready": False,
        "status": "blocked",
        "path": "",
        "reason": "",
        "row_count": 0,
        "valid_rows": 0,
        "failed_rows": [],
        "valid_targets": [],
        "missing_targets": [],
        "unexpected_targets": [],
        "md_engine_regex": STRICT_RELEASE_MD_ENGINE_RE.pattern,
        "expected_target_count": len(expected_targets),
    }
    if not _text(path_text):
        return {**base, "reason": "candidate_not_provided"}
    if not _path_exists(path_text):
        return {**base, "reason": "candidate_not_found"}
    resolved = str(_resolve(path_text))
    base["path"] = path_text
    header = _csv_header_if_exists(path_text)
    if not header:
        return {**base, "reason": "missing_or_unreadable_csv_header"}
    header_set = set(header)
    missing = [
        col for col in STRICT_RELEASE_EXTERNAL_MANIFEST_REQUIRED_COLUMNS if col not in header_set
    ]
    if missing:
        return {
            **base,
            "path": path_text,
            "reason": "missing_strict_release_external_manifest_columns:" + ",".join(missing),
        }
    rows = _csv_rows_if_exists(path_text)
    if not rows:
        return {**base, "path": path_text, "reason": "empty_strict_release_external_manifest"}

    failed_rows: list[dict[str, Any]] = []
    valid_targets: list[str] = []
    for idx, row in enumerate(rows, start=2):
        reasons = _strict_release_external_manifest_row_reasons(row)
        if reasons:
            failed_rows.append(
                {
                    "line": idx,
                    "target": _text(row.get("target")),
                    "path": _text(row.get("path")),
                    "reasons": reasons,
                }
            )
        else:
            valid_targets.append(_text(row.get("target")))

    expected_keys = {_normalize_target_key(target): target for target in expected_targets}
    valid_keys = {_normalize_target_key(target): target for target in valid_targets}
    missing_targets = [
        target for key, target in expected_keys.items() if key not in valid_keys
    ]
    unexpected_targets = [
        target for key, target in valid_keys.items() if expected_keys and key not in expected_keys
    ]

    reasons: list[str] = []
    if failed_rows:
        row_reasons = [
            f"row{row['line']}:{','.join(row['reasons'])}" for row in failed_rows
        ]
        reasons.append(
            "strict_release_external_manifest_semantic_rejected:" + ";".join(row_reasons)
        )
    if missing_targets:
        reasons.append("missing_strict_release_manifest_targets:" + ",".join(missing_targets))
    if unexpected_targets:
        reasons.append("unexpected_strict_release_manifest_targets:" + ",".join(unexpected_targets))

    ready = not reasons
    return {
        **base,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "path": path_text,
        "reason": "|".join(reasons),
        "row_count": len(rows),
        "valid_rows": len(valid_targets),
        "failed_rows": failed_rows,
        "valid_targets": _dedupe(valid_targets),
        "missing_targets": missing_targets,
        "unexpected_targets": unexpected_targets,
        "expected_target_count": len(expected_targets),
        "resolved_path": resolved,
    }


def _select_strict_release_external_manifest_candidate(
    paths: list[str],
    *,
    expected_targets: list[str],
) -> dict[str, Any]:
    rejected: list[dict[str, Any]] = []
    candidates = _dedupe(paths)
    for path in candidates:
        validation = _strict_release_external_manifest_validation(
            path,
            expected_targets=expected_targets,
        )
        if validation["ready"]:
            return {
                **validation,
                "candidate_paths": candidates,
                "rejected_candidates": rejected,
            }
        rejected.append(
            {
                "path": path,
                "reason": str(validation.get("reason", "")),
                "validation": validation,
            }
        )
    reason = rejected[0]["reason"] if rejected else "candidate_not_provided"
    first_validation = rejected[0]["validation"] if rejected else {}
    return {
        **first_validation,
        "ready": False,
        "status": "blocked",
        "path": "",
        "reason": reason,
        "candidate_paths": candidates,
        "rejected_candidates": rejected,
        "row_count": first_validation.get("row_count", 0),
        "valid_rows": first_validation.get("valid_rows", 0),
        "failed_rows": first_validation.get("failed_rows", []),
        "valid_targets": first_validation.get("valid_targets", []),
        "missing_targets": first_validation.get(
            "missing_targets",
            expected_targets if candidates else [],
        ),
        "unexpected_targets": first_validation.get("unexpected_targets", []),
        "md_engine_regex": first_validation.get(
            "md_engine_regex",
            STRICT_RELEASE_MD_ENGINE_RE.pattern,
        ),
        "expected_target_count": len(expected_targets),
    }


def _select_candidate(paths: list[str], rejection_fn) -> dict[str, Any]:
    rejected: list[dict[str, str]] = []
    for path in _dedupe(paths):
        reason = rejection_fn(path)
        if not reason:
            return {
                "ready": True,
                "status": "ready",
                "path": path,
                "reason": "",
                "candidate_paths": _dedupe(paths),
                "rejected_candidates": rejected,
            }
        rejected.append({"path": path, "reason": reason})
    return {
        "ready": False,
        "status": "blocked",
        "path": "",
        "reason": rejected[0]["reason"] if rejected else "candidate_not_provided",
        "candidate_paths": _dedupe(paths),
        "rejected_candidates": rejected,
    }


def _build_recommended_commands(
    *,
    manifest_csv: str,
    strict_release_external_manifest_csv: str,
    strict_summary_json: str,
    accuracy_external_csv: str,
    targets: str,
    unsupported_targets: list[str],
) -> list[str]:
    stamp = dt.date.today().isoformat()
    claim_prefix = f"runs/allatom_claim_readiness_{stamp}"
    kinetics_csv = f"runs/kinetics_equivalence_input_real_openmm_{stamp}.csv"
    thermo_csv = f"runs/thermo_equivalence_input_real_openmm_{stamp}.csv"
    experiment_csv = f"runs/experiment_consistency_input_real_openmm_{stamp}.csv"
    manifest_arg = _quote(manifest_csv) if manifest_csv else "<openmm_manifest.csv>"
    targets_arg = _quote(_text(targets, DEFAULT_TARGETS))
    strict_manifest_arg = (
        _quote(strict_release_external_manifest_csv)
        if strict_release_external_manifest_csv
        else "<external_openmm_manifest.csv>"
    )
    strict_arg = _quote(strict_summary_json) if strict_summary_json else "<strict_summary.json>"
    accuracy_arg = _quote(accuracy_external_csv) if accuracy_external_csv else "<accuracy_external.csv>"
    strict_release_blocked_comment = (
        " # blocked: unsupported strict-release targets: " + ", ".join(unsupported_targets)
        if unsupported_targets
        else ""
    )

    return [
        (
            "python3 tools/build_claim_inputs_from_openmm_manifest.py "
            f"--manifest-csv {manifest_arg} --targets {targets_arg} "
            f"--out-kinetics-csv {kinetics_csv} "
            f"--out-thermo-csv {thermo_csv} "
            f"--out-experiment-csv {experiment_csv} "
            f"--out-json runs/claim_input_real_openmm_summary_{stamp}.json"
        ),
        (
            "python3 tools/run_openmm_2bead_strict_release.py "
            f"--external-manifest {strict_manifest_arg} "
            f"--targets {targets_arg} "
            f"--out-prefix runs/openmm_2bead_strict_{stamp}_candidate"
            f"{strict_release_blocked_comment}"
        ),
        (
            "python3 tools/run_allatom_claim_readiness.py "
            f"--strict-summary-json {strict_arg} "
            f"--accuracy-external-csv {accuracy_arg} "
            f"--kinetics-input-csv {kinetics_csv} "
            f"--thermo-input-csv {thermo_csv} "
            f"--experiment-input-csv {experiment_csv} "
            "--enforce-complete-claim "
            f"--gate-out-json {claim_prefix}_gate.json "
            f"--gate-out-csv {claim_prefix}_gate.csv "
            f"--out-json {claim_prefix}_summary.json "
            f"--out-csv {claim_prefix}_summary.csv "
            f"--out-md {claim_prefix}_summary.md"
        ),
        (
            "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py "
            f"--claim-readiness-json {claim_prefix}_summary.json "
            f"--equivalence-gate-json {claim_prefix}_gate.json"
        ),
    ]


def _blocked_commands(claim_ready: bool) -> list[str]:
    if claim_ready:
        return []
    return [
        "python3 tools/run_allatom_claim_readiness.py",
        "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py",
    ]


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    strict_input = payload["inputs"]["strict_summary_json"]
    accuracy_input = payload["inputs"]["accuracy_external_csv"]
    strict_manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    target_input = payload["inputs"]["strict_release_target_support"]
    registration_input = payload["inputs"]["target_registration_packet"]
    lines = [
        "# All-Atom Claim Evidence Handoff",
        "",
        f"- strict_summary_status: `{summary['strict_summary_status']}`",
        f"- accuracy_external_status: `{summary['accuracy_external_status']}`",
        (
            "- strict_release_external_manifest_status: "
            f"`{summary['strict_release_external_manifest_status']}`"
        ),
        f"- strict_release_target_status: `{summary['strict_release_target_status']}`",
        f"- target_registration_status: `{summary['target_registration_status']}`",
        f"- strict_summary_generation_ready: `{summary['strict_summary_generation_ready']}`",
        f"- claim_readiness_ready: `{summary['claim_readiness_ready']}`",
        f"- missing_inputs: `{', '.join(summary['missing_inputs']) or 'none'}`",
        f"- upstream_missing_inputs: `{', '.join(summary['upstream_missing_inputs']) or 'none'}`",
        "",
        "## Inputs",
        "",
        f"- strict_summary_json: `{strict_input.get('path') or '<missing>'}`",
        f"- strict_summary_reason: `{strict_input.get('reason') or 'ready'}`",
        f"- accuracy_external_csv: `{accuracy_input.get('path') or '<missing>'}`",
        f"- accuracy_external_reason: `{accuracy_input.get('reason') or 'ready'}`",
        (
            "- strict_release_external_manifest_csv: "
            f"`{strict_manifest_input.get('path') or '<missing>'}`"
        ),
        (
            "- strict_release_external_manifest_reason: "
            f"`{strict_manifest_input.get('reason') or 'ready'}`"
        ),
        f"- strict_release_targets: `{', '.join(target_input.get('targets') or []) or '<missing>'}`",
        (
            "- strict_release_unsupported_targets: "
            f"`{', '.join(target_input.get('unsupported_targets') or []) or 'none'}`"
        ),
        f"- strict_release_target_reason: `{target_input.get('reason') or 'ready'}`",
        f"- target_registration_packet: `{registration_input.get('path') or '<missing>'}`",
        f"- target_registration_reason: `{registration_input.get('reason') or 'ready'}`",
        f"- target_registration_canonical_chain: `{registration_input.get('canonical_chain') or '<missing>'}`",
        "",
        "## Blocked Commands",
        "",
    ]
    if summary["blocked_commands"]:
        lines.extend(f"- `{cmd}`" for cmd in summary["blocked_commands"])
    else:
        lines.append("- none")
    lines.extend(["", "## Recommended Commands", ""])
    lines.extend(f"- `{cmd}`" for cmd in summary["recommended_commands"])
    lines.append("")
    return "\n".join(lines)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    repair_payload = _load_json_if_exists(str(args.repair_packet_json))
    explicit_strict = _text(args.strict_summary_json)
    explicit_accuracy_external = _text(args.accuracy_external_csv)
    explicit_strict_release_external_manifest = _text(args.strict_release_external_manifest)
    target_registration_status = _target_registration_packet_status(args.target_registration_json)

    strict_candidates = _dedupe(
        [explicit_strict] + _candidate_paths_from_payload(repair_payload, kind="strict")
    )
    accuracy_candidates = _dedupe(
        [explicit_accuracy_external]
        + _candidate_paths_from_payload(repair_payload, kind="accuracy_external")
        + [_text(args.accuracy_gate_csv)]
    )

    target_support_status = _strict_release_target_support_status(_text(args.targets, DEFAULT_TARGETS))
    strict_status = _select_candidate(strict_candidates, _strict_summary_rejection_reason)
    accuracy_status = _select_candidate(accuracy_candidates, _accuracy_external_rejection_reason)
    strict_release_external_manifest_status = _select_strict_release_external_manifest_candidate(
        _dedupe([explicit_strict_release_external_manifest, _first_manifest_candidate(repair_payload)]),
        expected_targets=target_support_status["targets"],
    )
    claim_ready = bool(strict_status["ready"] and accuracy_status["ready"])
    missing_inputs = []
    if not strict_status["ready"]:
        missing_inputs.append("strict_summary_json")
    if not accuracy_status["ready"]:
        missing_inputs.append("accuracy_external_csv")
    upstream_missing_inputs = []
    if not strict_release_external_manifest_status["ready"]:
        upstream_missing_inputs.append("strict_release_external_manifest_csv")
    if not target_support_status["ready"]:
        upstream_missing_inputs.append("strict_release_targets")

    manifest_csv = _first_manifest_candidate(repair_payload)
    recommended_commands = _build_recommended_commands(
        manifest_csv=manifest_csv,
        strict_release_external_manifest_csv=_text(strict_release_external_manifest_status["path"]),
        strict_summary_json=_text(strict_status["path"]),
        accuracy_external_csv=_text(accuracy_status["path"]),
        targets=_text(args.targets, DEFAULT_TARGETS),
        unsupported_targets=target_support_status["unsupported_targets"],
    )
    strict_summary_generation_ready = bool(
        strict_release_external_manifest_status["ready"] and target_support_status["ready"]
    )

    summary = {
        "strict_summary_status": strict_status["status"],
        "accuracy_external_status": accuracy_status["status"],
        "strict_release_external_manifest_status": strict_release_external_manifest_status["status"],
        "strict_release_target_status": target_support_status["status"],
        "strict_release_targets_supported": bool(target_support_status["ready"]),
        "strict_release_unsupported_targets": target_support_status["unsupported_targets"],
        "target_registration_status": target_registration_status["status"],
        "target_registration_ready": target_registration_status["ready"],
        "target_registration_blockers": target_registration_status["blockers"],
        "target_registration_canonical_chain_ready": target_registration_status[
            "canonical_chain_ready"
        ],
        "strict_summary_generation_ready": strict_summary_generation_ready,
        "claim_readiness_ready": claim_ready,
        "missing_inputs": missing_inputs,
        "upstream_missing_inputs": upstream_missing_inputs,
        "blocked_commands": _blocked_commands(claim_ready),
        "recommended_commands": recommended_commands,
    }
    return {
        "schema": "allatom_claim_evidence_handoff.v1",
        "summary": summary,
        "sources": {
            "repair_packet_json": _text(args.repair_packet_json),
            "accuracy_gate_json": _text(args.accuracy_gate_json),
            "accuracy_gate_csv": _text(args.accuracy_gate_csv),
        },
        "inputs": {
            "strict_summary_json": strict_status,
            "accuracy_external_csv": accuracy_status,
            "openmm_manifest_csv": {
                "ready": bool(manifest_csv),
                "status": "ready" if manifest_csv else "missing",
                "path": manifest_csv,
                "reason": "" if manifest_csv else "not_required_for_handoff_but_needed_for_claim_input_generation",
            },
            "strict_release_external_manifest_csv": strict_release_external_manifest_status,
            "strict_release_target_support": target_support_status,
            "target_registration_packet": target_registration_status,
        },
        "artifacts": {
            "json": _text(args.out_json),
            "md": _text(args.out_md),
        },
        "safety": {
            "manual_pass_promotion_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args)
    out_json = _resolve(str(args.out_json))
    out_md = _resolve(str(args.out_md))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed all-atom claim/equivalence evidence handoff."
    )
    parser.add_argument("--repair-packet-json", default=DEFAULT_REPAIR_PACKET_JSON)
    parser.add_argument("--accuracy-gate-json", default=DEFAULT_ACCURACY_GATE_JSON)
    parser.add_argument("--accuracy-gate-csv", default=DEFAULT_ACCURACY_GATE_CSV)
    parser.add_argument("--target-registration-json", default=DEFAULT_TARGET_REGISTRATION_JSON)
    parser.add_argument("--strict-summary-json", default="")
    parser.add_argument("--accuracy-external-csv", default="")
    parser.add_argument("--strict-release-external-manifest", default="")
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    print(f"Wrote: {payload['artifacts']['json']}")
    print(f"Wrote: {payload['artifacts']['md']}")
    print(f"claim_readiness_ready={payload['summary']['claim_readiness_ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

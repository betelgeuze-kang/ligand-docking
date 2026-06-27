#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import shutil
import subprocess
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"

ALLOWED_SCOPE_FAMILIES = {
    "kinase": "kinase",
    "gpcr": "gpcr",
    "ion_channel": "ion_channel",
    "ion-channel": "ion_channel",
    "ion channel": "ion_channel",
}
RESTRICTED_SCOPE_HINTS = ("transporter", "transporters")
DISALLOWED_VERDICT_HINTS = (
    "all supported molecular families",
    "broadly commercial-ready",
    "broadly commercial ready",
    "production-ready as a hosted",
    "production ready as a hosted",
    "multi-tenant service",
    "unattended automatic external decision-making",
    "unattended automatic external decision making",
    "prospective wet-lab hit-discovery",
    "prospective wet lab hit discovery",
)
DELIVERY_READY_CLAIM_HINTS = (
    "delivery-ready",
    "delivery ready",
    "ready for delivery",
    "ready for guarded",
    "suitable for guarded validation delivery",
)
NEGATIVE_OR_REVIEW_VERDICT_HINTS = (
    "not delivery-ready",
    "not delivery ready",
    "not yet delivery-ready",
    "not yet delivery ready",
    "not ready for delivery",
    "not suitable for delivery",
    "blocked",
    "internal-review",
    "internal review",
    "review-only",
    "review only",
)
VERDICT_GATE_FINGERPRINT_FIELDS = ("label", "path", "present", "sha256", "size_bytes")


def _default_out_dir() -> Path:
    return RUNS / "local_delivery"


def _default_status_report_md() -> Path:
    return ROOT / "commercialization_status_report.md"


def _default_preflight_json() -> Path:
    return RUNS / "local_delivery_preflight_current.json"


def _default_preflight_md() -> Path:
    return RUNS / "local_delivery_preflight_current.md"


def _default_local_ci_summary_json() -> Path:
    return RUNS / "local_ci_tests_summary.json"


def _default_accuracy_gate_json() -> Path:
    return RUNS / "accuracy_gate_local_delivery_preflight_current.json"


def _default_queue_json() -> Path:
    return RUNS / "local_engine_commercialization_queue_current.json"


def _default_queue_csv() -> Path:
    return RUNS / "local_engine_commercialization_queue_current.csv"


def _default_queue_md() -> Path:
    return RUNS / "local_engine_commercialization_queue_current.md"


def _default_environment_json() -> Path:
    return RUNS / "local_delivery_environment_manifest_current.json"


def _default_environment_md() -> Path:
    return RUNS / "local_delivery_environment_manifest_current.md"


def _default_requirements_lock_json() -> Path:
    return RUNS / "local_delivery_requirements_lock_current.json"


def _default_requirements_lock_md() -> Path:
    return RUNS / "local_delivery_requirements_lock_current.md"


def _default_requirements_lock_txt() -> Path:
    return RUNS / "local_delivery_requirements_lock_current.txt"


def _default_engine_provenance_json() -> Path:
    return RUNS / "local_delivery_engine_provenance_current.json"


def _default_engine_provenance_md() -> Path:
    return RUNS / "local_delivery_engine_provenance_current.md"


def _default_verdict_gate_json() -> Path:
    return RUNS / "local_delivery_verdict_gate_current.json"


def _default_verdict_gate_md() -> Path:
    return RUNS / "local_delivery_verdict_gate_current.md"


def _default_nightly_gate_json() -> Path:
    return RUNS / "nightly_gate_burndown_packet_current.json"


def _default_wetlab_selected_allatom_json() -> Path:
    return RUNS / "wetlab_selected_allatom_gate_burndown_packet_current.json"


def _default_current_results_index_json() -> Path:
    return RUNS / "wetlab_current_results_index_current.json"


def _default_partnering_stack_json() -> Path:
    return RUNS / "wetlab_partnering_stack_current.json"


def _default_hbond_backmap_report_json() -> Path:
    return RUNS / "hbond_backmap_report_current.json"


def _default_hbond_backmap_report_md() -> Path:
    return RUNS / "hbond_backmap_report_current.md"


def _default_hbond_backmap_report_csv() -> Path:
    return RUNS / "hbond_backmap_report_current.csv"


# H-Bond BackMap is additive local interpretability evidence in the bundle, never
# a delivery-ready gate and never a docking-accuracy/affinity claim.
HBOND_BACKMAP_CLAIM_BOUNDARY = (
    "H-Bond BackMap is local interpretability evidence, not a docking-accuracy or binding-affinity claim."
)


def _default_gpcr_hard_decoy_suite_json() -> Path:
    return RUNS / "gpcr_hard_decoy_suite_current.json"


def _default_gpcr_hard_decoy_suite_md() -> Path:
    return RUNS / "gpcr_hard_decoy_suite_current.md"


def _default_gpcr_hard_decoy_suite_csv() -> Path:
    return RUNS / "gpcr_hard_decoy_suite_current.csv"


# The GPCR hard-decoy suite is an additive fail-closed gate surface in the
# bundle: it shows whether broad GPCR/router is still locked, never promotes it.
GPCR_HARD_DECOY_CLAIM_BOUNDARY = (
    "GPCR hard-decoy suite is a fail-closed broad-GPCR gate surface; it does not run scoring, generate decoys, "
    "relax thresholds, or promote broad-GPCR claims. A broad_family_locked result remains non-claimable."
)


def _now_local() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _default_bundle_tag() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _sanitize_tag(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in str(value).strip())
    return cleaned.strip("_")


def _require_text(value: Any, flag: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{flag} is required")
    return text


def _resolve_input_path(path_like: str | Path) -> Path:
    text = str(path_like).strip()
    if not text:
        return Path()
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _resolve_output_dir(path_like: str | Path) -> Path:
    text = str(path_like).strip()
    if not text:
        return _default_out_dir()
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    _mkdir(path.parent)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _manifest_signature(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json_object(path_like: str | Path) -> dict[str, Any]:
    path = _resolve_input_path(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary_from_payload(path_like: str | Path) -> dict[str, Any]:
    payload = _read_json_object(path_like)
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _family_scorecard_summary(path_like: str | Path) -> dict[str, Any]:
    return _summary_from_payload(path_like)


def _hbond_backmap_report_reference(
    json_path: str | Path,
    md_path: str | Path,
    csv_path: str | Path,
) -> dict[str, Any]:
    """Build an additive H-Bond BackMap evidence reference for the bundle manifest.

    Reads ``runs/hbond_backmap_report_current.json`` (built by
    ``tools/product/build_hbond_backmap_report.py``) and surfaces only the
    batch-level KPI plus artifact paths. H-Bond BackMap is additive local
    interpretability evidence: it is never a delivery-ready hard gate, and a
    missing/invalid report is surfaced as a warning, never a positive claim.
    """

    resolved_json = _resolve_input_path(json_path) if str(json_path).strip() else Path()
    present_file = bool(str(resolved_json) and resolved_json.exists() and resolved_json.is_file())
    valid = False
    reason = "missing"
    summary: dict[str, Any] = {}
    if present_file:
        try:
            payload = json.loads(resolved_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reason = "invalid_json"
        else:
            candidate = payload.get("summary") if isinstance(payload, dict) else None
            if isinstance(candidate, dict):
                summary = candidate
                valid = True
                reason = "present"
            else:
                reason = "invalid_payload_missing_summary"

    def _int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    kpi = {
        "hbond_backmap_report_present": valid,
        "hbond_backmap_candidate_count": _int(summary.get("candidate_count")),
        "hbond_backmap_claim_safe_count": _int(summary.get("claim_safe_count")),
        "hbond_backmap_evidence_only_count": _int(summary.get("evidence_only_count")),
        "hbond_backmap_claim_safe_rate": _float(summary.get("claim_safe_rate")),
        "hbond_backmap_total_donor_sites": _int(summary.get("total_donor_sites")),
        "hbond_backmap_total_acceptor_sites": _int(summary.get("total_acceptor_sites")),
    }
    return {
        "artifact_id": "hbond_backmap_report",
        "artifact_type": "interpretability_evidence",
        "present": valid,
        "reason": reason,
        "warning": "" if valid else f"hbond_backmap_report_{reason}",
        "json_path": str(json_path).strip(),
        "md_path": str(md_path).strip(),
        "csv_path": str(csv_path).strip(),
        "required_for_delivery_ready": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": HBOND_BACKMAP_CLAIM_BOUNDARY,
        "kpi": kpi,
    }


def _gpcr_hard_decoy_suite_reference(
    json_path: str | Path,
    md_path: str | Path,
    csv_path: str | Path,
) -> dict[str, Any]:
    """Build an additive GPCR hard-decoy gate reference for the bundle manifest.

    Reads ``runs/gpcr_hard_decoy_suite_current.json`` (built by
    ``tools/product/build_gpcr_hard_decoy_suite_report.py``) and surfaces only
    the family gate KPI plus artifact paths. It is a fail-closed broad-GPCR gate
    surface: never a delivery-ready hard gate, never a broad-GPCR claim. A
    missing/invalid report is surfaced as a warning, and family_claim_safe stays
    false.
    """

    resolved_json = _resolve_input_path(json_path) if str(json_path).strip() else Path()
    present_file = bool(str(resolved_json) and resolved_json.exists() and resolved_json.is_file())
    valid = False
    reason = "missing"
    summary: dict[str, Any] = {}
    if present_file:
        try:
            payload = json.loads(resolved_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reason = "invalid_json"
        else:
            candidate = payload.get("summary") if isinstance(payload, dict) else None
            if isinstance(candidate, dict):
                summary = candidate
                valid = True
                reason = "present"
            else:
                reason = "invalid_payload_missing_summary"

    def _int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _list_len(value: Any) -> int:
        return len(value) if isinstance(value, list) else 0

    kpi = {
        "gpcr_hard_decoy_report_present": valid,
        # Fail-closed: only an explicit True is treated as claim-safe.
        "gpcr_hard_decoy_family_claim_safe": bool(summary.get("family_claim_safe") is True),
        "gpcr_hard_decoy_status": str(summary.get("status") or ("missing" if not valid else "")),
        "gpcr_hard_decoy_target_count": _int(summary.get("target_count")),
        "gpcr_hard_decoy_green_target_count": _list_len(summary.get("green_target_ids")),
        "gpcr_hard_decoy_blocked_target_count": _list_len(summary.get("blocked_target_ids")),
        "gpcr_hard_decoy_missing_required_target_count": _list_len(
            summary.get("missing_required_target_ids")
        ),
        "gpcr_hard_decoy_first_blocked_required_target": str(
            summary.get("first_blocked_required_target") or ""
        ),
    }
    return {
        "artifact_id": "gpcr_hard_decoy_suite_report",
        "artifact_type": "broad_gpcr_gate_evidence",
        "present": valid,
        "reason": reason,
        "warning": "" if valid else f"gpcr_hard_decoy_suite_report_{reason}",
        "json_path": str(json_path).strip(),
        "md_path": str(md_path).strip(),
        "csv_path": str(csv_path).strip(),
        "required_for_delivery_ready": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": GPCR_HARD_DECOY_CLAIM_BOUNDARY,
        "kpi": kpi,
    }


def _family_scorecard_summary_passes(summary: dict[str, Any]) -> bool:
    return (
        summary.get("scorecard_level_status") == "pass"
        and summary.get("acceptance_overall_pass") is not False
    )


def _enforce_delivery_ready_family_scorecards(
    scorecard_paths: Sequence[str],
    *,
    verdict_text: str,
) -> None:
    if not _verdict_claims_delivery_ready(verdict_text):
        return
    for raw_path in scorecard_paths:
        path = _resolve_input_path(raw_path)
        summary = _family_scorecard_summary(path)
        if not _family_scorecard_summary_passes(summary):
            raise ValueError(
                "family_scorecard blocks delivery-ready bundle verdict: "
                f"summary.scorecard_level_status={summary.get('scorecard_level_status')!r}, "
                f"summary.acceptance_overall_pass={summary.get('acceptance_overall_pass')!r}; "
                f"path={path}. Use a blocked/internal-review verdict, or provide a passing family scorecard."
            )


def _verdict_claims_delivery_ready(verdict_text: str) -> bool:
    lowered = " ".join(str(verdict_text).lower().split())
    negative_delivery_ready_forms = (
        "not delivery-ready",
        "not delivery ready",
        "not yet delivery-ready",
        "not yet delivery ready",
        "not ready for delivery",
        "not suitable for delivery",
    )
    if any(hint in lowered for hint in negative_delivery_ready_forms):
        return False
    explicit_delivery_ready_forms = (
        "delivery-ready for",
        "delivery ready for",
        "delivery-ready only for",
        "delivery ready only for",
        "suitable for guarded validation delivery",
    )
    if any(hint in lowered for hint in explicit_delivery_ready_forms):
        return True
    positive_forms = (
        "delivery-ready for guarded",
        "delivery ready for guarded",
        "delivery-ready only for",
        "delivery ready only for",
        "ready for delivery",
        "ready for guarded",
        "suitable for guarded validation delivery",
    )
    if any(hint in lowered for hint in positive_forms):
        return True
    if any(hint in lowered for hint in NEGATIVE_OR_REVIEW_VERDICT_HINTS):
        return False
    return any(hint in lowered for hint in DELIVERY_READY_CLAIM_HINTS)


def _claim_scope_for_verdict_gate(raw_scope: str, gate_builder: Any) -> str:
    claim_scope_ok, _ = gate_builder._claim_scope_ok(raw_scope)
    if claim_scope_ok:
        return raw_scope
    policy = _scope_policy(raw_scope)
    recognized = policy.get("recognized_allowed_families", [])
    if (not recognized) or policy.get("restricted_terms"):
        return raw_scope
    normalized = str(raw_scope).lower().replace("-", "_")
    tokens = set(normalized.replace("/", " ").replace(",", " ").split())
    disallowed = set(getattr(gate_builder, "DISALLOWED_SCOPE_WORDS", set()))
    if any(word in tokens or word in normalized for word in disallowed):
        return raw_scope
    return ",".join(str(item) for item in recognized)


def _load_verdict_gate_builder() -> Any:
    module_path = Path(__file__).resolve().with_name("build_local_delivery_verdict_gate.py")
    spec = importlib.util.spec_from_file_location("_local_delivery_verdict_gate_for_bundle", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load local_delivery_verdict_gate builder from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verdict_gate_fingerprint_index(source_artifacts: Any) -> tuple[bool, str, dict[str, dict[str, Any]]]:
    if not isinstance(source_artifacts, list) or not source_artifacts:
        return False, "source_artifacts_missing", {}
    index: dict[str, dict[str, Any]] = {}
    for row in source_artifacts:
        if not isinstance(row, dict):
            return False, "source_artifacts_invalid", {}
        missing = [field for field in VERDICT_GATE_FINGERPRINT_FIELDS if field not in row]
        if missing:
            return False, f"source_artifacts_fingerprint_missing_fields:{','.join(missing)}", {}
        label = str(row.get("label", "")).strip()
        if not label:
            return False, "source_artifacts_fingerprint_missing_label", {}
        if label in index:
            return False, f"source_artifacts_duplicate_label:{label}", {}
        normalized = {
            "label": label,
            "path": str(row.get("path", "")).strip(),
            "present": bool(row.get("present", False)),
            "sha256": str(row.get("sha256", "")).strip(),
            "size_bytes": int(row.get("size_bytes", 0) or 0),
        }
        if normalized["present"] and (not normalized["sha256"] or normalized["size_bytes"] <= 0):
            return False, f"source_artifacts_fingerprint_incomplete:{label}", {}
        index[label] = normalized
    return True, "source_artifacts_fingerprinted", index


def _verdict_gate_status(path_like: str | Path) -> dict[str, Any]:
    path = _resolve_input_path(path_like)
    if not path.exists():
        return {"ok": False, "reason": "missing", "summary": {}, "path": str(path), "fingerprints": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "reason": f"invalid_json: {exc}", "summary": {}, "path": str(path), "fingerprints": {}}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "invalid_payload_not_object", "summary": {}, "path": str(path), "fingerprints": {}}
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return {"ok": False, "reason": "summary_missing_or_invalid", "summary": {}, "path": str(path), "fingerprints": {}}
    delivery_ready = summary.get("delivery_ready")
    if delivery_ready is not True:
        return {
            "ok": False,
            "reason": f"delivery_ready=false ({delivery_ready!r})",
            "summary": summary,
            "path": str(path),
            "fingerprints": {},
        }
    fingerprints_ok, fingerprint_reason, fingerprints = _verdict_gate_fingerprint_index(payload.get("source_artifacts"))
    if not fingerprints_ok:
        return {
            "ok": False,
            "reason": fingerprint_reason,
            "summary": summary,
            "path": str(path),
            "fingerprints": {},
        }
    return {
        "ok": True,
        "reason": "delivery_ready=true",
        "summary": summary,
        "path": str(path),
        "fingerprints": fingerprints,
    }


def _persisted_verdict_gate_fingerprint_status(path_like: str | Path) -> dict[str, Any]:
    path = _resolve_input_path(path_like)
    if not path.exists():
        return {"ok": False, "reason": "persisted_gate_missing", "path": str(path), "fingerprints": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "reason": f"persisted_gate_invalid_json: {exc}", "path": str(path), "fingerprints": {}}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "persisted_gate_invalid_payload_not_object", "path": str(path), "fingerprints": {}}
    fingerprints_ok, fingerprint_reason, fingerprints = _verdict_gate_fingerprint_index(payload.get("source_artifacts"))
    if not fingerprints_ok:
        return {
            "ok": False,
            "reason": f"persisted_{fingerprint_reason}",
            "path": str(path),
            "fingerprints": {},
        }
    return {
        "ok": True,
        "reason": "persisted_source_artifacts_fingerprinted",
        "path": str(path),
        "fingerprints": fingerprints,
    }


def _verdict_gate_md_status(path_like: str | Path) -> dict[str, Any]:
    path = _resolve_input_path(path_like)
    if not path.exists():
        return {"ok": False, "reason": "md_missing", "path": str(path)}
    if not path.is_file():
        return {"ok": False, "reason": "md_not_file", "path": str(path)}
    if path.stat().st_size <= 0:
        return {"ok": False, "reason": "md_empty", "path": str(path)}
    return {"ok": True, "reason": "md_present", "path": str(path)}


def _fresh_verdict_gate_payload(args: argparse.Namespace) -> dict[str, Any]:
    try:
        gate_builder = _load_verdict_gate_builder()
        claim_scope = _claim_scope_for_verdict_gate(args.claim_scope, gate_builder)
        payload = gate_builder.build_payload(
            claim_scope=claim_scope,
            preflight_json=args.preflight_json,
            accuracy_gate_json=args.accuracy_gate_json,
            requirements_lock_json=args.requirements_lock_json,
            environment_manifest_json=args.environment_json,
            engine_provenance_json=args.engine_provenance_json,
            commercialization_queue_json=args.queue_json,
            status_report_md=args.status_report_md,
            nightly_gate_json=args.nightly_gate_json,
            wetlab_selected_allatom_json=args.wetlab_selected_allatom_json,
            current_results_index_json=args.current_results_index_json,
            partnering_stack_json=args.partnering_stack_json,
        )
    except Exception as exc:  # pragma: no cover - defensive guard for operator-facing CLI failures.
        return {"ok": False, "reason": f"fresh_recheck_failed: {exc}", "payload": {}}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "fresh_recheck_invalid_payload_not_object", "payload": {}}
    return {"ok": True, "reason": "fresh_recheck_payload_built", "payload": payload}


def _fresh_verdict_gate_status(args: argparse.Namespace, persisted_gate: dict[str, Any]) -> dict[str, Any]:
    fresh_payload = _fresh_verdict_gate_payload(args)
    if not fresh_payload["ok"]:
        return {"ok": False, "reason": fresh_payload["reason"]}
    payload = fresh_payload["payload"]
    summary = payload.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    if summary.get("delivery_ready") is not True:
        status_line = str(summary.get("status_line", "")).strip()
        return {
            "ok": False,
            "reason": f"delivery_ready=false fresh_recheck; {status_line or 'current P0 artifacts are not green'}",
        }
    fresh_ok, fresh_reason, fresh_fingerprints = _verdict_gate_fingerprint_index(payload.get("source_artifacts"))
    if not fresh_ok:
        return {"ok": False, "reason": f"fresh_recheck_{fresh_reason}"}
    persisted_fingerprints = persisted_gate.get("fingerprints") if isinstance(persisted_gate, dict) else {}
    if not isinstance(persisted_fingerprints, dict) or not persisted_fingerprints:
        return {"ok": False, "reason": "persisted_source_artifacts_missing"}
    if set(persisted_fingerprints) != set(fresh_fingerprints):
        return {
            "ok": False,
            "reason": (
                "fingerprint_mismatch:labels "
                f"persisted={sorted(persisted_fingerprints)} fresh={sorted(fresh_fingerprints)}"
            ),
        }
    for label, persisted in persisted_fingerprints.items():
        fresh = fresh_fingerprints[label]
        for field in VERDICT_GATE_FINGERPRINT_FIELDS:
            if persisted.get(field) != fresh.get(field):
                return {
                    "ok": False,
                    "reason": (
                        f"fingerprint_mismatch:{label}:{field} "
                        f"persisted={persisted.get(field)!r} fresh={fresh.get(field)!r}"
                    ),
                }
    return {"ok": True, "reason": "fresh_recheck_delivery_ready=true"}


def _verdict_gate_fingerprint_check(args: argparse.Namespace) -> dict[str, Any]:
    required_for_delivery_ready_verdict = _verdict_claims_delivery_ready(str(getattr(args, "verdict", "")))
    persisted = _persisted_verdict_gate_fingerprint_status(args.verdict_gate_json)
    fresh_payload = _fresh_verdict_gate_payload(args)
    fresh_fingerprints: dict[str, dict[str, Any]] = {}
    if fresh_payload["ok"]:
        fresh_ok, fresh_reason, fresh_fingerprints = _verdict_gate_fingerprint_index(
            fresh_payload["payload"].get("source_artifacts")
        )
        if not fresh_ok:
            fresh_payload = {"ok": False, "reason": f"fresh_recheck_{fresh_reason}", "payload": {}}

    persisted_fingerprints = persisted.get("fingerprints") if isinstance(persisted, dict) else {}
    if not isinstance(persisted_fingerprints, dict):
        persisted_fingerprints = {}
    if not isinstance(fresh_fingerprints, dict):
        fresh_fingerprints = {}

    base = {
        "checked": False,
        "ok": False,
        "status": "not_run",
        "reason": "",
        "comparison_performed": False,
        "required_for_delivery_ready_verdict": required_for_delivery_ready_verdict,
        "matched_count": 0,
        "compared_label_count": 0,
        "mismatch_count": 0,
        "mismatches": [],
        "persisted_label_count": len(persisted_fingerprints),
        "fresh_label_count": len(fresh_fingerprints),
    }
    if not persisted["ok"]:
        return {**base, "status": "persisted_unavailable", "reason": persisted["reason"]}
    if not fresh_payload["ok"]:
        return {
            **base,
            "status": "fresh_unavailable",
            "reason": fresh_payload["reason"],
            "fresh_label_count": len(fresh_fingerprints),
        }

    mismatches: list[dict[str, Any]] = []
    persisted_labels = set(persisted_fingerprints)
    fresh_labels = set(fresh_fingerprints)
    compared_label_count = len(persisted_labels & fresh_labels)
    for label in sorted(persisted_labels - fresh_labels):
        mismatches.append({"label": label, "field": "label", "persisted": "present", "fresh": "missing"})
    for label in sorted(fresh_labels - persisted_labels):
        mismatches.append({"label": label, "field": "label", "persisted": "missing", "fresh": "present"})

    matched_count = 0
    for label in sorted(persisted_labels & fresh_labels):
        label_mismatched = False
        persisted_row = persisted_fingerprints[label]
        fresh_row = fresh_fingerprints[label]
        for field in VERDICT_GATE_FINGERPRINT_FIELDS:
            if persisted_row.get(field) != fresh_row.get(field):
                label_mismatched = True
                mismatches.append(
                    {
                        "label": label,
                        "field": field,
                        "persisted": persisted_row.get(field),
                        "fresh": fresh_row.get(field),
                    }
                )
        if not label_mismatched:
            matched_count += 1

    if mismatches:
        first = mismatches[0]
        if first["field"] == "label":
            reason = (
                "fingerprint_mismatch:labels "
                f"persisted={sorted(persisted_fingerprints)} fresh={sorted(fresh_fingerprints)}"
            )
        else:
            reason = (
                f"fingerprint_mismatch:{first['label']}:{first['field']} "
                f"persisted={first['persisted']!r} fresh={first['fresh']!r}"
            )
    else:
        reason = "fingerprints_match"

    return {
        "checked": True,
        "ok": not mismatches,
        "status": "mismatch" if mismatches else "pass",
        "reason": reason,
        "comparison_performed": True,
        "required_for_delivery_ready_verdict": required_for_delivery_ready_verdict,
        "matched_count": matched_count,
        "compared_label_count": compared_label_count,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "persisted_label_count": len(persisted_fingerprints),
        "fresh_label_count": len(fresh_fingerprints),
    }


def _enforce_delivery_ready_verdict_gate(args: argparse.Namespace, verdict_text: str) -> None:
    if not _verdict_claims_delivery_ready(verdict_text):
        return
    gate = _verdict_gate_status(args.verdict_gate_json)
    if gate["ok"]:
        gate_md = _verdict_gate_md_status(args.verdict_gate_md)
        if gate_md["ok"]:
            fresh_gate = _fresh_verdict_gate_status(args, gate)
            if fresh_gate["ok"]:
                return
            reason = fresh_gate["reason"]
            path = gate["path"]
        else:
            reason = gate_md["reason"]
            path = gate_md["path"]
        raise SystemExit(
            "local_delivery_verdict_gate blocks delivery-ready bundle verdict: "
            f"{reason}; path={path}. "
            "Use a blocked/internal-review verdict, or refresh the gate until summary.delivery_ready=true."
        )
    raise SystemExit(
        "local_delivery_verdict_gate blocks delivery-ready bundle verdict: "
        f"{gate['reason']}; path={gate['path']}. "
        "Use a blocked/internal-review verdict, or refresh the gate until summary.delivery_ready=true."
    )


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return ""
    if proc.returncode != 0:
        return ""
    return str(proc.stdout).strip()


def _scope_policy(scope_text: str) -> dict[str, Any]:
    lowered = str(scope_text).lower()
    recognized: list[str] = []
    for needle, canonical in ALLOWED_SCOPE_FAMILIES.items():
        if needle in lowered and canonical not in recognized:
            recognized.append(canonical)
    restricted = [term for term in RESTRICTED_SCOPE_HINTS if term in lowered]
    if restricted:
        status = "contains_restricted_or_blocked_terms"
    elif recognized:
        status = "within_initial_local_delivery_scope"
    else:
        status = "freeform_scope_text_requires_manual_review"
    return {
        "recognized_allowed_families": recognized,
        "restricted_terms": restricted,
        "status": status,
    }


def _verdict_scope_check(verdict_text: str) -> dict[str, Any]:
    lowered = str(verdict_text).lower()
    issues = [hint for hint in DISALLOWED_VERDICT_HINTS if hint in lowered]
    if "general commercialization verdict" in lowered and "not a general commercialization verdict" not in lowered:
        issues.append("general commercialization verdict wording without a restriction qualifier")
    return {
        "ok": not issues,
        "status": "scoped_local_delivery_wording" if not issues else "contains_broad_claim_hints",
        "issues": issues,
    }


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if (not text) or (text in seen):
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _build_known_exclusions(
    explicit: Sequence[str],
    *,
    delivery_policy: dict[str, Any],
    claim_policy: dict[str, Any],
) -> list[str]:
    auto: list[str] = []
    if delivery_policy.get("restricted_terms") or claim_policy.get("restricted_terms"):
        auto.append(
            "Restricted families such as transporter must remain review-only, staged, or not yet claim-safe in this local-delivery bundle."
        )
    return _dedupe_preserve_order([*explicit, *auto])


def _spec(
    *,
    key: str,
    label: str,
    category: str,
    source_path: str | Path,
    bundle_path: str | Path,
    required: bool,
) -> dict[str, Any]:
    source = _resolve_input_path(source_path) if str(source_path).strip() else Path()
    return {
        "key": key,
        "label": label,
        "category": category,
        "requested_path": str(source_path).strip(),
        "source_path": str(source),
        "bundle_path": Path(bundle_path).as_posix(),
        "required": bool(required),
    }


def _build_collection_specs(
    values: Sequence[str],
    *,
    category: str,
    bundle_root: str,
    placeholder_key: str,
    placeholder_label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return [], [
            {
                "spec_key": placeholder_key,
                "name": placeholder_label,
                "logical_name": placeholder_label,
                "category": category,
                "required": True,
                "requested_path": "",
                "source_path": "",
                "bundle_path": f"{bundle_root}/",
                "reason": "not_provided",
            }
        ]

    specs: list[dict[str, Any]] = []
    for index, value in enumerate(cleaned, start=1):
        source = _resolve_input_path(value)
        display_name = source.name if str(source) else Path(value).name
        if source.exists() and source.is_dir():
            bundle_path = Path(bundle_root) / source.name
        else:
            bundle_path = Path(bundle_root) / (display_name or f"{category}_{index}")
        specs.append(
            {
                "key": f"{category}_{index}",
                "label": display_name or f"{category}_{index}",
                "category": category,
                "requested_path": value,
                "source_path": str(source),
                "bundle_path": bundle_path.as_posix(),
                "required": True,
            }
        )
    return specs, []


def _build_family_scorecard_specs(values: Sequence[str]) -> list[dict[str, Any]]:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    specs: list[dict[str, Any]] = []
    for index, value in enumerate(cleaned, start=1):
        source = _resolve_input_path(value)
        filename = source.name if str(source) else Path(value).name
        specs.append(
            {
                "key": f"family_scorecard_{index}",
                "label": filename or f"family_scorecard_{index}.json",
                "category": "family_scorecard",
                "requested_path": value,
                "source_path": str(source),
                "bundle_path": (Path("artifacts") / "family_scorecards" / (filename or f"family_scorecard_{index}.json")).as_posix(),
                "required": True,
                "summary": _family_scorecard_summary(source),
            }
        )
    return specs


def _safe_source_artifact_key(label: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in str(label).strip())
    return cleaned.strip("_") or "source_artifact"


def _safe_source_artifact_bundle_path(row: dict[str, Any]) -> str:
    raw_path = str(row.get("path", "")).strip()
    if raw_path and "\\" not in raw_path:
        rel = PurePosixPath(raw_path)
        if not rel.is_absolute() and all(part not in {"", ".", ".."} for part in rel.parts):
            return rel.as_posix()
    label = _safe_source_artifact_key(str(row.get("label", "")))
    filename = Path(raw_path).name or f"{label}.artifact"
    return (Path("artifacts") / "verdict_gate_source_artifacts" / label / filename).as_posix()


def _build_verdict_gate_source_artifact_specs(
    source_artifacts: Any,
    *,
    existing_specs: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(source_artifacts, list):
        return []

    existing_sources = {
        str(Path(str(spec.get("source_path", ""))).resolve())
        for spec in existing_specs
        if str(spec.get("source_path", "")).strip()
    }
    existing_bundle_paths = {
        str(spec.get("bundle_path", "")).strip()
        for spec in existing_specs
        if str(spec.get("bundle_path", "")).strip()
    }
    specs: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row in source_artifacts:
        if not isinstance(row, dict):
            continue
        label = _safe_source_artifact_key(str(row.get("label", "")))
        raw_path = str(row.get("path", "")).strip()
        if not raw_path:
            continue
        source = _resolve_input_path(raw_path)
        source_key = str(source.resolve())
        if source_key in existing_sources:
            continue
        bundle_path = _safe_source_artifact_bundle_path(row)
        if bundle_path in existing_bundle_paths:
            continue
        key_base = f"verdict_gate_source_artifact_{label}"
        key = key_base
        suffix = 2
        while key in seen_keys:
            key = f"{key_base}_{suffix}"
            suffix += 1
        seen_keys.add(key)
        existing_sources.add(source_key)
        existing_bundle_paths.add(bundle_path)
        specs.append(
            {
                "key": key,
                "label": label,
                "category": "verdict_gate_source_artifact",
                "requested_path": raw_path,
                "source_path": str(source),
                "bundle_path": bundle_path,
                "required": bool(row.get("required") is not False),
            }
        )
    return specs


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    request_summary = _require_text(args.request_summary, "--request-summary")
    delivery_scope = _require_text(args.delivery_scope, "--delivery-scope")
    claim_scope = _require_text(args.claim_scope, "--claim-scope")
    verdict = _require_text(args.verdict, "--verdict")
    rerun_command = _require_text(args.rerun_command, "--rerun-command")
    _enforce_delivery_ready_verdict_gate(args, verdict)
    family_scorecard_paths = list(getattr(args, "family_scorecard_json", []) or [])
    _enforce_delivery_ready_family_scorecards(family_scorecard_paths, verdict_text=verdict)

    bundle_tag = _sanitize_tag(str(getattr(args, "bundle_tag", "")).strip()) or _default_bundle_tag()
    out_dir = _resolve_output_dir(args.out_dir)
    bundle_dir = out_dir / f"bundle_{bundle_tag}"

    delivery_policy = _scope_policy(delivery_scope)
    claim_policy = _scope_policy(claim_scope)
    verdict_scope_check = _verdict_scope_check(verdict)
    known_exclusions = _build_known_exclusions(
        list(getattr(args, "known_exclusion", []) or []),
        delivery_policy=delivery_policy,
        claim_policy=claim_policy,
    )

    core_specs = [
        _spec(
            key="status_report_md",
            label="commercialization_status_report_md",
            category="status_report",
            source_path=args.status_report_md,
            bundle_path="commercialization_status_report.md",
            required=True,
        ),
        _spec(
            key="preflight_json",
            label="local_delivery_preflight_json",
            category="preflight",
            source_path=args.preflight_json,
            bundle_path="runs/local_delivery_preflight_current.json",
            required=True,
        ),
        _spec(
            key="preflight_md",
            label="local_delivery_preflight_md",
            category="preflight",
            source_path=args.preflight_md,
            bundle_path="runs/local_delivery_preflight_current.md",
            required=True,
        ),
        _spec(
            key="local_ci_summary_json",
            label="local_ci_tests_summary_json",
            category="preflight",
            source_path=args.local_ci_summary_json,
            bundle_path="runs/local_ci_tests_summary.json",
            required=True,
        ),
        _spec(
            key="queue_json",
            label="local_engine_commercialization_queue_json",
            category="queue",
            source_path=args.queue_json,
            bundle_path="runs/local_engine_commercialization_queue_current.json",
            required=True,
        ),
        _spec(
            key="queue_csv",
            label="local_engine_commercialization_queue_csv",
            category="queue",
            source_path=args.queue_csv,
            bundle_path="runs/local_engine_commercialization_queue_current.csv",
            required=False,
        ),
        _spec(
            key="queue_md",
            label="local_engine_commercialization_queue_md",
            category="queue",
            source_path=args.queue_md,
            bundle_path="runs/local_engine_commercialization_queue_current.md",
            required=True,
        ),
        _spec(
            key="environment_json",
            label="environment_manifest_json",
            category="environment",
            source_path=args.environment_json,
            bundle_path="environment/environment_manifest.json",
            required=True,
        ),
        _spec(
            key="environment_md",
            label="environment_manifest_md",
            category="environment",
            source_path=args.environment_md,
            bundle_path="environment/environment_manifest.md",
            required=True,
        ),
        _spec(
            key="requirements_lock_json",
            label="requirements_lock_json",
            category="environment",
            source_path=args.requirements_lock_json,
            bundle_path="environment/requirements_lock.json",
            required=True,
        ),
        _spec(
            key="requirements_lock_md",
            label="requirements_lock_md",
            category="environment",
            source_path=args.requirements_lock_md,
            bundle_path="environment/requirements_lock.md",
            required=True,
        ),
        _spec(
            key="requirements_lock_txt",
            label="requirements_lock_txt",
            category="environment",
            source_path=args.requirements_lock_txt,
            bundle_path="environment/requirements_lock.txt",
            required=True,
        ),
        _spec(
            key="engine_provenance_json",
            label="engine_provenance_json",
            category="environment",
            source_path=args.engine_provenance_json,
            bundle_path="environment/engine_provenance.json",
            required=True,
        ),
        _spec(
            key="engine_provenance_md",
            label="engine_provenance_md",
            category="environment",
            source_path=args.engine_provenance_md,
            bundle_path="environment/engine_provenance.md",
            required=True,
        ),
        _spec(
            key="verdict_gate_json",
            label="local_delivery_verdict_gate_json",
            category="verdict_gate",
            source_path=args.verdict_gate_json,
            bundle_path="runs/local_delivery_verdict_gate_current.json",
            required=True,
        ),
        _spec(
            key="verdict_gate_md",
            label="local_delivery_verdict_gate_md",
            category="verdict_gate",
            source_path=args.verdict_gate_md,
            bundle_path="runs/local_delivery_verdict_gate_current.md",
            required=True,
        ),
    ]

    verdict_gate_payload = _read_json_object(args.verdict_gate_json)
    verdict_gate_source_artifacts = verdict_gate_payload.get("source_artifacts")
    if not isinstance(verdict_gate_source_artifacts, list):
        verdict_gate_source_artifacts = []
    verdict_gate_source_artifact_specs = _build_verdict_gate_source_artifact_specs(
        verdict_gate_source_artifacts,
        existing_specs=core_specs,
    )

    config_specs, config_placeholders = _build_collection_specs(
        list(getattr(args, "config_paths", []) or []),
        category="config",
        bundle_root="config",
        placeholder_key="config_paths",
        placeholder_label="config_path",
    )
    artifact_specs, artifact_placeholders = _build_collection_specs(
        list(getattr(args, "artifact_paths", []) or []),
        category="artifact",
        bundle_root="artifacts",
        placeholder_key="artifact_paths",
        placeholder_label="artifact_path",
    )
    family_scorecard_specs = _build_family_scorecard_specs(family_scorecard_paths)

    environment_summary = _summary_from_payload(args.environment_json)
    engine_provenance_summary = _summary_from_payload(args.engine_provenance_json)
    verdict_gate_summary = _summary_from_payload(args.verdict_gate_json)
    verdict_gate_fingerprint_check = _verdict_gate_fingerprint_check(args)
    source_repo_commit = str(environment_summary.get("git_commit", "")).strip() or _git_commit()

    return {
        "bundle_tag": bundle_tag,
        "out_dir": str(out_dir.resolve()),
        "bundle_dir": str(bundle_dir.resolve()),
        "created_at_local": _now_local(),
        "source_repo_commit": source_repo_commit,
        "request_summary": request_summary,
        "delivery_scope": delivery_scope,
        "claim_scope": claim_scope,
        "delivery_scope_policy": delivery_policy,
        "claim_scope_policy": claim_policy,
        "verdict": verdict,
        "verdict_scope_check": verdict_scope_check,
        "rerun_command": rerun_command,
        "known_exclusions": known_exclusions,
        "build_archive": bool(getattr(args, "build_archive", True)),
        "core_specs": core_specs,
        "verdict_gate_source_artifact_specs": verdict_gate_source_artifact_specs,
        "verdict_gate_source_artifacts": verdict_gate_source_artifacts,
        "config_specs": config_specs,
        "artifact_specs": artifact_specs,
        "family_scorecard_specs": family_scorecard_specs,
        "placeholder_missing": [*config_placeholders, *artifact_placeholders],
        "preflight_summary": _summary_from_payload(args.preflight_json),
        "queue_summary": _summary_from_payload(args.queue_json),
        "environment_summary": environment_summary,
        "engine_provenance_summary": engine_provenance_summary,
        "verdict_gate_summary": verdict_gate_summary,
        "verdict_gate_fingerprint_check": verdict_gate_fingerprint_check,
        "hbond_backmap_report_reference": _hbond_backmap_report_reference(
            getattr(args, "hbond_backmap_report_json", str(_default_hbond_backmap_report_json())),
            getattr(args, "hbond_backmap_report_md", str(_default_hbond_backmap_report_md())),
            getattr(args, "hbond_backmap_report_csv", str(_default_hbond_backmap_report_csv())),
        ),
        "gpcr_hard_decoy_suite_reference": _gpcr_hard_decoy_suite_reference(
            getattr(args, "gpcr_hard_decoy_suite_json", str(_default_gpcr_hard_decoy_suite_json())),
            getattr(args, "gpcr_hard_decoy_suite_md", str(_default_gpcr_hard_decoy_suite_md())),
            getattr(args, "gpcr_hard_decoy_suite_csv", str(_default_gpcr_hard_decoy_suite_csv())),
        ),
    }


def _claim_bundle_path(bundle_rel: Path, claimed_paths: set[str]) -> None:
    key = bundle_rel.as_posix()
    if key in claimed_paths:
        raise ValueError(f"duplicate bundle destination: {key}")
    claimed_paths.add(key)


def _missing_record(spec: dict[str, Any], *, reason: str, bundle_path: str | None = None) -> dict[str, Any]:
    return {
        "spec_key": spec["key"],
        "name": spec["label"],
        "logical_name": spec["label"],
        "category": spec["category"],
        "required": bool(spec.get("required", False)),
        "requested_path": str(spec.get("requested_path", "")),
        "source_path": str(spec.get("source_path", "")),
        "bundle_path": bundle_path or str(spec.get("bundle_path", "")),
        "reason": reason,
    }


def _included_record(
    spec: dict[str, Any],
    *,
    source_file: Path,
    bundle_rel: Path,
    bundle_abs: Path,
    suffix: str = "",
) -> dict[str, Any]:
    label = spec["label"]
    name = f"{label}::{suffix}" if suffix else label
    return {
        "spec_key": spec["key"],
        "name": name,
        "logical_name": label,
        "category": spec["category"],
        "required": bool(spec.get("required", False)),
        "requested_path": str(spec.get("requested_path", "")),
        "source_path": str(source_file.resolve()),
        "bundle_path": bundle_rel.as_posix(),
        "bundle_abspath": str(bundle_abs.resolve()),
        "size_bytes": int(bundle_abs.stat().st_size),
        "sha256": _sha256_file(bundle_abs),
    }


def _materialize_spec(
    spec: dict[str, Any],
    *,
    bundle_dir: Path,
    claimed_paths: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_path = Path(str(spec.get("source_path", "")))
    if (not str(source_path)) or (not source_path.exists()):
        return [], [_missing_record(spec, reason="source_missing")]

    if source_path.is_file():
        bundle_rel = Path(str(spec["bundle_path"]))
        _claim_bundle_path(bundle_rel, claimed_paths)
        bundle_abs = bundle_dir / bundle_rel
        _mkdir(bundle_abs.parent)
        shutil.copy2(source_path, bundle_abs)
        return [_included_record(spec, source_file=source_path, bundle_rel=bundle_rel, bundle_abs=bundle_abs)], []

    if source_path.is_dir():
        files = sorted(path for path in source_path.rglob("*") if path.is_file())
        if not files:
            return [], [_missing_record(spec, reason="empty_directory")]
        included: list[dict[str, Any]] = []
        for file_path in files:
            relative_src = file_path.relative_to(source_path)
            bundle_rel = Path(str(spec["bundle_path"])) / relative_src
            _claim_bundle_path(bundle_rel, claimed_paths)
            bundle_abs = bundle_dir / bundle_rel
            _mkdir(bundle_abs.parent)
            shutil.copy2(file_path, bundle_abs)
            included.append(
                _included_record(
                    spec,
                    source_file=file_path,
                    bundle_rel=bundle_rel,
                    bundle_abs=bundle_abs,
                    suffix=relative_src.as_posix(),
                )
            )
        return included, []

    return [], [_missing_record(spec, reason="unsupported_path_type")]


def _group_by_key(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("spec_key", ""))].append(row)
    return dict(grouped)


def _artifact_status(
    spec_key: str,
    included_by_key: dict[str, list[dict[str, Any]]],
    missing_by_key: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if spec_key in included_by_key:
        rows = included_by_key[spec_key]
        return {
            "present": True,
            "required": bool(rows[0].get("required", False)),
            "files": rows,
        }
    rows = missing_by_key.get(spec_key, [])
    if rows:
        return {
            "present": False,
            "required": bool(rows[0].get("required", False)),
            "files": rows,
        }
    return {
        "present": False,
        "required": False,
        "files": [],
    }


def _family_scorecard_manifest_rows(
    specs: Sequence[dict[str, Any]],
    included_by_key: dict[str, list[dict[str, Any]]],
    missing_by_key: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        key = str(spec.get("key", ""))
        included = included_by_key.get(key, [])
        if included:
            for row in included:
                rows.append(
                    {
                        "source_path": str(row.get("source_path", "")),
                        "bundle_path": str(row.get("bundle_path", "")),
                        "present": True,
                        "sha256": str(row.get("sha256", "")),
                        "summary": spec.get("summary") if isinstance(spec.get("summary"), dict) else {},
                    }
                )
            continue
        missing = missing_by_key.get(key, [])
        if missing:
            missing_row = missing[0]
            rows.append(
                {
                    "source_path": str(missing_row.get("source_path", "")),
                    "bundle_path": str(missing_row.get("bundle_path", spec.get("bundle_path", ""))),
                    "present": False,
                    "sha256": "",
                    "summary": spec.get("summary") if isinstance(spec.get("summary"), dict) else {},
                }
            )
    return rows


def _index_section(
    category: str,
    included_rows: Sequence[dict[str, Any]],
    missing_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    included = [row for row in included_rows if str(row.get("category", "")) == category]
    missing = [row for row in missing_rows if str(row.get("category", "")) == category]
    return {
        "included_count": len(included),
        "missing_count": len(missing),
        "included": included,
        "missing": missing,
    }


def _build_manifest_markdown(manifest: dict[str, Any]) -> str:
    checksums = manifest["checksums"]
    archive = manifest["archive"]
    lines = [
        "# Local Delivery Bundle",
        "",
        f"- bundle_tag: `{manifest['bundle_tag']}`",
        f"- created_at_local: `{manifest['created_at_local']}`",
        f"- source_repo_commit: `{manifest['source_repo_commit'] or '-'}`",
        f"- request_summary: {manifest['request_summary']}",
        f"- delivery_scope: `{manifest['delivery_scope']}`",
        f"- claim_scope: `{manifest['claim_scope']}`",
        f"- verdict: {manifest['verdict']}",
        f"- included_count: `{manifest['included_count']}`",
        f"- missing_count: `{manifest['missing_count']}`",
        f"- manifest_signature_sha256: `{manifest['manifest_signature_sha256']}`",
        "",
        "## Local Delivery Guardrails",
        "",
        f"- delivery_scope_status: `{manifest['delivery_scope_policy']['status']}`",
        f"- claim_scope_status: `{manifest['claim_scope_policy']['status']}`",
        f"- verdict_scope_status: `{manifest['verdict_scope_check']['status']}`",
        f"- rerun_command: `{manifest['rerun_command']}`",
        "",
        "## Preflight",
        "",
        f"- overall_ok: `{manifest['preflight'].get('overall_ok', False)}`",
        f"- local_delivery_preflight_json: `{manifest['preflight']['artifacts']['json'].get('files', [{}])[0].get('bundle_path', 'missing') if manifest['preflight']['artifacts']['json'].get('files') else 'missing'}`",
        f"- local_delivery_preflight_md: `{manifest['preflight']['artifacts']['md'].get('files', [{}])[0].get('bundle_path', 'missing') if manifest['preflight']['artifacts']['md'].get('files') else 'missing'}`",
        f"- local_ci_tests_summary_json: `{manifest['preflight']['artifacts']['local_ci_summary_json'].get('files', [{}])[0].get('bundle_path', 'missing') if manifest['preflight']['artifacts']['local_ci_summary_json'].get('files') else 'missing'}`",
        "",
        "## Queue",
        "",
        f"- local_engine_commercialization_queue_json_present: `{manifest['queue']['artifacts']['json']['present']}`",
        f"- local_engine_commercialization_queue_csv_present: `{manifest['queue']['artifacts']['csv']['present']}`",
        f"- local_engine_commercialization_queue_md_present: `{manifest['queue']['artifacts']['md']['present']}`",
        "",
        "## Environment",
        "",
        f"- environment_manifest_json_present: `{manifest['environment']['artifacts']['json']['present']}`",
        f"- environment_manifest_md_present: `{manifest['environment']['artifacts']['md']['present']}`",
        f"- requirements_lock_json_present: `{manifest['environment']['artifacts']['requirements_lock_json']['present']}`",
        f"- requirements_lock_md_present: `{manifest['environment']['artifacts']['requirements_lock_md']['present']}`",
        f"- requirements_lock_txt_present: `{manifest['environment']['artifacts']['requirements_lock_txt']['present']}`",
        f"- engine_provenance_json_present: `{manifest['engine_provenance']['artifacts']['json']['present']}`",
        f"- engine_provenance_md_present: `{manifest['engine_provenance']['artifacts']['md']['present']}`",
        f"- existing_engine_reused: `{manifest['engine_provenance']['summary'].get('existing_engine_reused', False)}`",
        f"- environment_status_line: `{manifest['environment']['summary'].get('status_line', '-')}`",
        "",
        "## Verdict Gate",
        "",
        f"- delivery_ready: `{manifest['local_delivery_verdict_gate']['summary'].get('delivery_ready', False)}`",
        f"- p0_blocker_count: `{manifest['local_delivery_verdict_gate']['summary'].get('p0_blocker_count', '-')}`",
        f"- verdict_gate_json_present: `{manifest['local_delivery_verdict_gate']['artifacts']['json']['present']}`",
        f"- verdict_gate_md_present: `{manifest['local_delivery_verdict_gate']['artifacts']['md']['present']}`",
        f"- fingerprint_check_checked: `{manifest['verdict_gate_fingerprint_check'].get('checked', False)}`",
        f"- fingerprint_check_ok: `{manifest['verdict_gate_fingerprint_check'].get('ok', False)}`",
        f"- fingerprint_check_status: `{manifest['verdict_gate_fingerprint_check'].get('status', '-')}`",
        f"- fingerprint_check_comparison_performed: `{manifest['verdict_gate_fingerprint_check'].get('comparison_performed', False)}`",
        f"- fingerprint_check_required_for_delivery_ready_verdict: `{manifest['verdict_gate_fingerprint_check'].get('required_for_delivery_ready_verdict', False)}`",
        f"- fingerprint_check_reason: `{manifest['verdict_gate_fingerprint_check'].get('reason', '-')}`",
        f"- fingerprint_check_matched_count: `{manifest['verdict_gate_fingerprint_check'].get('matched_count', 0)}`",
        f"- fingerprint_check_compared_label_count: `{manifest['verdict_gate_fingerprint_check'].get('compared_label_count', 0)}`",
        f"- fingerprint_check_mismatch_count: `{manifest['verdict_gate_fingerprint_check'].get('mismatch_count', 0)}`",
        f"- fingerprint_check_persisted_label_count: `{manifest['verdict_gate_fingerprint_check'].get('persisted_label_count', 0)}`",
        f"- fingerprint_check_fresh_label_count: `{manifest['verdict_gate_fingerprint_check'].get('fresh_label_count', 0)}`",
        "",
        "## Family Scorecards",
        "",
        f"- family_scorecard_count: `{len(manifest.get('family_scorecards', []))}`",
        f"- family_scorecard_blocked_count: `{sum(1 for row in manifest.get('family_scorecards', []) if not _family_scorecard_summary_passes(row.get('summary', {}) if isinstance(row, dict) else {}))}`",
        "",
        "## Artifact Index",
        "",
        f"- config_included_count: `{manifest['artifact_index']['config']['included_count']}`",
        f"- config_missing_count: `{manifest['artifact_index']['config']['missing_count']}`",
        f"- delivered_artifact_included_count: `{manifest['artifact_index']['artifacts']['included_count']}`",
        f"- delivered_artifact_missing_count: `{manifest['artifact_index']['artifacts']['missing_count']}`",
        "",
        "## Included Files",
    ]
    if manifest["included_files"]:
        for row in manifest["included_files"]:
            lines.append(f"- {row['name']}: `{row['bundle_path']}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Missing Files"])
    if manifest["missing_files"]:
        for row in manifest["missing_files"]:
            lines.append(
                f"- {row['name']}: requested=`{row.get('requested_path', '') or '-'}` bundle=`{row['bundle_path']}` reason=`{row['reason']}`"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Known Exclusions"])
    if manifest["known_exclusions"]:
        for text in manifest["known_exclusions"]:
            lines.append(f"- {text}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Checksums",
            "",
            f"- bundle_path: `{checksums['bundle_path']}`",
            f"- algorithm: `{checksums['algorithm']}`",
            f"- covered_file_count: `{checksums['covered_file_count']}`",
            "",
            "## Archive",
            "",
            f"- present: `{archive['present']}`",
            f"- bundle_path: `{archive['bundle_path']}`",
            f"- size_bytes: `{archive['size_bytes']}`",
            f"- sha256: `{archive['sha256'] or '-'}`",
            f"- note: {archive['note']}",
        ]
    )
    if archive.get("error"):
        lines.append(f"- error: `{archive['error']}`")

    return "\n".join(lines)


def _write_checksums(bundle_dir: Path, *, checksum_path: Path) -> int:
    rows: list[str] = []
    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == checksum_path.resolve():
            continue
        rows.append(f"{_sha256_file(path)}  {path.relative_to(bundle_dir).as_posix()}")
    _write_markdown(checksum_path, "\n".join(rows))
    return len(rows)


def build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args)

    bundle_dir = Path(payload["bundle_dir"])
    out_dir = Path(payload["out_dir"])
    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        raise FileExistsError(f"bundle directory already exists and is not empty: {bundle_dir}")

    _mkdir(out_dir)
    _mkdir(bundle_dir)
    for folder in ("runs", "environment", "config", "artifacts", "artifacts/family_scorecards"):
        _mkdir(bundle_dir / folder)

    included: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = list(payload["placeholder_missing"])
    claimed_paths: set[str] = set()
    for spec in [
        *payload["core_specs"],
        *payload["verdict_gate_source_artifact_specs"],
        *payload["config_specs"],
        *payload["artifact_specs"],
        *payload["family_scorecard_specs"],
    ]:
        spec_included, spec_missing = _materialize_spec(spec, bundle_dir=bundle_dir, claimed_paths=claimed_paths)
        included.extend(spec_included)
        missing.extend(spec_missing)

    included_by_key = _group_by_key(included)
    missing_by_key = _group_by_key(missing)

    archive_info: dict[str, Any] = {
        "requested": bool(payload["build_archive"]),
        "present": False,
        "bundle_path": "bundle.zip",
        "size_bytes": 0,
        "sha256": "",
        "note": (
            "Convenience zip built from the assembled local-delivery bundle before final checksum materialization; "
            "the bundle directory remains the authoritative record."
        ),
        "error": "",
    }

    draft_manifest_core = {
        "bundle_tag": payload["bundle_tag"],
        "created_at_local": payload["created_at_local"],
        "bundle_dir": str(bundle_dir.resolve()),
        "source_repo_commit": payload["source_repo_commit"],
        "delivery_scope": payload["delivery_scope"],
        "claim_scope": payload["claim_scope"],
        "delivery_scope_policy": payload["delivery_scope_policy"],
        "claim_scope_policy": payload["claim_scope_policy"],
        "request_summary": payload["request_summary"],
        "preflight": {
            "overall_ok": bool(payload["preflight_summary"].get("overall_ok", False)),
            "summary": payload["preflight_summary"],
            "artifacts": {
                "json": _artifact_status("preflight_json", included_by_key, missing_by_key),
                "md": _artifact_status("preflight_md", included_by_key, missing_by_key),
                "local_ci_summary_json": _artifact_status("local_ci_summary_json", included_by_key, missing_by_key),
            },
        },
        "queue": {
            "summary": payload["queue_summary"],
            "artifacts": {
                "json": _artifact_status("queue_json", included_by_key, missing_by_key),
                "csv": _artifact_status("queue_csv", included_by_key, missing_by_key),
                "md": _artifact_status("queue_md", included_by_key, missing_by_key),
            },
        },
        "status_report": {
            "scope_note": "Copied for local-delivery review only; not a general commercialization verdict.",
            "artifact": _artifact_status("status_report_md", included_by_key, missing_by_key),
        },
        "environment": {
            "summary": payload["environment_summary"],
            "artifacts": {
                "json": _artifact_status("environment_json", included_by_key, missing_by_key),
                "md": _artifact_status("environment_md", included_by_key, missing_by_key),
                "requirements_lock_json": _artifact_status("requirements_lock_json", included_by_key, missing_by_key),
                "requirements_lock_md": _artifact_status("requirements_lock_md", included_by_key, missing_by_key),
                "requirements_lock_txt": _artifact_status("requirements_lock_txt", included_by_key, missing_by_key),
            },
        },
        "engine_provenance": {
            "summary": payload["engine_provenance_summary"],
            "scope_note": "Records reuse of existing repository engine surfaces; not a new engine implementation.",
            "artifacts": {
                "json": _artifact_status("engine_provenance_json", included_by_key, missing_by_key),
                "md": _artifact_status("engine_provenance_md", included_by_key, missing_by_key),
            },
        },
        "local_delivery_verdict_gate": {
            "summary": payload["verdict_gate_summary"],
            "source_artifacts": payload["verdict_gate_source_artifacts"],
            "scope_note": "Conservative P0 delivery-readiness gate over refreshed local-delivery artifacts.",
            "artifacts": {
                "json": _artifact_status("verdict_gate_json", included_by_key, missing_by_key),
                "md": _artifact_status("verdict_gate_md", included_by_key, missing_by_key),
            },
        },
        "verdict_gate_fingerprint_check": payload["verdict_gate_fingerprint_check"],
        "hbond_backmap_report": payload["hbond_backmap_report_reference"],
        "gpcr_hard_decoy_suite": payload["gpcr_hard_decoy_suite_reference"],
        "family_scorecards": _family_scorecard_manifest_rows(
            payload["family_scorecard_specs"],
            included_by_key,
            missing_by_key,
        ),
        "artifact_index": {
            "status_report": _index_section("status_report", included, missing),
            "preflight": _index_section("preflight", included, missing),
            "queue": _index_section("queue", included, missing),
            "environment": _index_section("environment", included, missing),
            "verdict_gate": _index_section("verdict_gate", included, missing),
            "verdict_gate_source_artifacts": _index_section("verdict_gate_source_artifact", included, missing),
            "family_scorecards": _index_section("family_scorecard", included, missing),
            "config": _index_section("config", included, missing),
            "artifacts": _index_section("artifact", included, missing),
        },
        "known_exclusions": payload["known_exclusions"],
        "rerun_command": payload["rerun_command"],
        "verdict": payload["verdict"],
        "verdict_scope_check": payload["verdict_scope_check"],
        "included_files": included,
        "missing_files": missing,
        "included_count": len(included),
        "missing_count": len(missing),
        "checksums": {
            "bundle_path": "checksums.sha256",
            "algorithm": "sha256",
            "covered_file_count": 0,
        },
        "archive": archive_info,
    }

    draft_manifest = dict(draft_manifest_core)
    draft_manifest["manifest_signature_sha256"] = _manifest_signature(draft_manifest_core)
    draft_manifest_json = bundle_dir / "manifest.json"
    draft_manifest_md = bundle_dir / "manifest.md"
    _write_json(draft_manifest_json, draft_manifest)
    _write_markdown(draft_manifest_md, _build_manifest_markdown(draft_manifest))

    if bool(payload["build_archive"]):
        archive_tmp_base = out_dir / f"local_delivery_bundle_{payload['bundle_tag']}"
        archive_tmp_zip = archive_tmp_base.with_suffix(".zip")
        if archive_tmp_zip.exists():
            archive_tmp_zip.unlink()
        try:
            built_zip = Path(shutil.make_archive(str(archive_tmp_base), "zip", root_dir=bundle_dir))
            archive_bundle_path = bundle_dir / "bundle.zip"
            shutil.copy2(built_zip, archive_bundle_path)
            archive_info = {
                **archive_info,
                "present": True,
                "size_bytes": int(archive_bundle_path.stat().st_size),
                "sha256": _sha256_file(archive_bundle_path),
            }
            built_zip.unlink(missing_ok=True)
        except Exception as exc:
            archive_info = {
                **archive_info,
                "present": False,
                "error": str(exc),
            }

    checksum_count = sum(
        1
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    manifest_core = {
        **draft_manifest_core,
        "checksums": {
            "bundle_path": "checksums.sha256",
            "algorithm": "sha256",
            "covered_file_count": checksum_count,
        },
        "archive": archive_info,
    }
    manifest = dict(manifest_core)
    manifest["manifest_signature_sha256"] = _manifest_signature(manifest_core)

    manifest_json = bundle_dir / "manifest.json"
    manifest_md = bundle_dir / "manifest.md"
    checksums_sha256 = bundle_dir / "checksums.sha256"
    _write_json(manifest_json, manifest)
    _write_markdown(manifest_md, _build_manifest_markdown(manifest))
    checksum_count = _write_checksums(bundle_dir, checksum_path=checksums_sha256)
    if checksum_count != manifest["checksums"]["covered_file_count"]:
        manifest["checksums"]["covered_file_count"] = checksum_count
        manifest["manifest_signature_sha256"] = _manifest_signature(
            {k: v for k, v in manifest.items() if k != "manifest_signature_sha256"}
        )
        _write_json(manifest_json, manifest)
        _write_markdown(manifest_md, _build_manifest_markdown(manifest))
        checksum_count = _write_checksums(bundle_dir, checksum_path=checksums_sha256)

    return {
        "bundle_tag": payload["bundle_tag"],
        "bundle_dir": str(bundle_dir.resolve()),
        "manifest_json": str(manifest_json.resolve()),
        "manifest_md": str(manifest_md.resolve()),
        "checksums_sha256": str(checksums_sha256.resolve()),
        "archive_zip": str((bundle_dir / "bundle.zip").resolve()) if archive_info.get("present") else "",
        "archive_sha256": str(archive_info.get("sha256", "")),
        "included_count": int(len(included)),
        "missing_count": int(len(missing)),
        "manifest_signature_sha256": str(manifest.get("manifest_signature_sha256", "")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble a scoped local-delivery bundle from refreshed preflight, queue, environment, config, and "
            "result artifacts without implying general commercialization readiness."
        )
    )
    parser.add_argument("--bundle-tag", default="")
    parser.add_argument("--out-dir", default=str(_default_out_dir()))
    parser.add_argument("--request-summary", required=True)
    parser.add_argument("--delivery-scope", required=True)
    parser.add_argument("--claim-scope", required=True)
    parser.add_argument("--verdict", required=True)
    parser.add_argument("--rerun-command", required=True)
    parser.add_argument("--known-exclusion", action="append", default=[])
    parser.add_argument("--config-path", dest="config_paths", action="append", default=[])
    parser.add_argument("--artifact-path", dest="artifact_paths", action="append", default=[])
    parser.add_argument("--extra-artifact-path", dest="artifact_paths", action="append")
    parser.add_argument("--family-scorecard-json", dest="family_scorecard_json", action="append", default=[])
    parser.add_argument("--status-report-md", default=str(_default_status_report_md()))
    parser.add_argument("--preflight-json", default=str(_default_preflight_json()))
    parser.add_argument("--preflight-md", default=str(_default_preflight_md()))
    parser.add_argument("--local-ci-summary-json", default=str(_default_local_ci_summary_json()))
    parser.add_argument("--accuracy-gate-json", default=str(_default_accuracy_gate_json()))
    parser.add_argument("--queue-json", default=str(_default_queue_json()))
    parser.add_argument("--queue-csv", default=str(_default_queue_csv()))
    parser.add_argument("--queue-md", default=str(_default_queue_md()))
    parser.add_argument("--environment-json", default=str(_default_environment_json()))
    parser.add_argument("--environment-md", default=str(_default_environment_md()))
    parser.add_argument("--requirements-lock-json", default=str(_default_requirements_lock_json()))
    parser.add_argument("--requirements-lock-md", default=str(_default_requirements_lock_md()))
    parser.add_argument("--requirements-lock-txt", default=str(_default_requirements_lock_txt()))
    parser.add_argument("--engine-provenance-json", default=str(_default_engine_provenance_json()))
    parser.add_argument("--engine-provenance-md", default=str(_default_engine_provenance_md()))
    parser.add_argument("--verdict-gate-json", default=str(_default_verdict_gate_json()))
    parser.add_argument("--verdict-gate-md", default=str(_default_verdict_gate_md()))
    parser.add_argument("--nightly-gate-json", default=str(_default_nightly_gate_json()))
    parser.add_argument("--wetlab-selected-allatom-json", default=str(_default_wetlab_selected_allatom_json()))
    parser.add_argument("--current-results-index-json", default=str(_default_current_results_index_json()))
    parser.add_argument("--partnering-stack-json", default=str(_default_partnering_stack_json()))
    parser.add_argument("--hbond-backmap-report-json", default=str(_default_hbond_backmap_report_json()))
    parser.add_argument("--hbond-backmap-report-md", default=str(_default_hbond_backmap_report_md()))
    parser.add_argument("--hbond-backmap-report-csv", default=str(_default_hbond_backmap_report_csv()))
    parser.add_argument("--gpcr-hard-decoy-suite-json", default=str(_default_gpcr_hard_decoy_suite_json()))
    parser.add_argument("--gpcr-hard-decoy-suite-md", default=str(_default_gpcr_hard_decoy_suite_md()))
    parser.add_argument("--gpcr-hard-decoy-suite-csv", default=str(_default_gpcr_hard_decoy_suite_csv()))
    parser.add_argument("--build-archive", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_bundle(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

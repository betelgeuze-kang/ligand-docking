#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = ROOT / "runs" / "self_hosted_license_distribution_audit_current.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display_path(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _row(check: str, passed: bool, observed: str, required: str, review_required: bool = False) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "hard_blocker": not passed,
        "operator_review_required": review_required,
        "legal_advice_provided": False,
        "external_state_mutated": False,
    }


def build_audit(
    *,
    license_path: str = "LICENSE",
    license_decision_json: str = "runs/product_license_decision_gate_current.json",
    license_work_order_json: str = "runs/product_license_file_creation_work_order_current.json",
    commercial_independence_json: str = "runs/product_commercial_independence_gate_current.json",
    viewer_vendor_manifest: str = "viewer/vendor/manifest.json",
    third_party_license_review_gate_json: str = "runs/third_party_license_review_gate_current.json",
) -> dict[str, Any]:
    license_file = _resolve(license_path)
    license_text = license_file.read_text(encoding="utf-8") if license_file.is_file() else ""
    license_sha = _sha256(license_file)
    decision = _summary(_read_json(license_decision_json))
    work_order = _summary(_read_json(license_work_order_json))
    commercial = _summary(_read_json(commercial_independence_json))
    vendor_manifest = _read_json(viewer_vendor_manifest)
    review_gate = _summary(_read_json(third_party_license_review_gate_json))

    source_path = _resolve(_text(work_order.get("license_text_source") or decision.get("license_text_source")))
    source_sha = _sha256(source_path)
    spdx_license_id = _text(work_order.get("spdx_license_id") or decision.get("spdx_license_id"))
    holder = _text(work_order.get("copyright_holder") or decision.get("copyright_holder"))
    year = _text(work_order.get("effective_year") or decision.get("effective_year"))
    notice_path = _resolve(_text(vendor_manifest.get("third_party_notice_path")))
    notice_text = notice_path.read_text(encoding="utf-8") if notice_path.is_file() else ""
    assets = vendor_manifest.get("assets") if isinstance(vendor_manifest.get("assets"), list) else []
    dual_license_assets = [
        str(row.get("package") or row.get("name"))
        for row in assets
        if isinstance(row, dict) and (" OR " in _text(row.get("license_id")) or "GPL" in _text(row.get("license_id")))
    ]

    license_present = bool(license_text.strip())
    source_matches_license = bool(license_sha and source_sha and license_sha == source_sha)
    metadata_visible = all(value in license_text for value in (holder, year) if value)
    vendor_notice_complete = bool(assets and notice_text)
    for row in assets:
        if not isinstance(row, dict):
            vendor_notice_complete = False
            continue
        vendor_notice_complete = (
            vendor_notice_complete
            and _text(row.get("package")) in notice_text
            and _text(row.get("license_id")) in notice_text
            and _text(row.get("license_source_url")) in notice_text
        )

    rows = [
        _row(
            "product_license_file_present",
            license_present,
            f"path={_display_path(license_file)};sha256={license_sha};size_bytes={license_file.stat().st_size if license_file.is_file() else 0}",
            "non-empty LICENSE file",
        ),
        _row(
            "license_decision_gate_ready",
            decision.get("status") == "product_license_decision_gate_ready"
            and _bool(decision.get("authorized_for_license_file_creation_review")),
            f"status={decision.get('status')};authorized={decision.get('authorized_for_license_file_creation_review')}",
            "product_license_decision_gate_ready and authorized=true",
        ),
        _row(
            "license_work_order_ready",
            work_order.get("status") == "product_license_file_creation_work_order_ready"
            and _bool(work_order.get("license_review_manifest_ready")),
            f"status={work_order.get('status')};manifest_ready={work_order.get('license_review_manifest_ready')}",
            "product_license_file_creation_work_order_ready and manifest_ready=true",
        ),
        _row(
            "license_matches_approved_source",
            source_matches_license,
            f"license_sha256={license_sha};source={_display_path(source_path)};source_sha256={source_sha}",
            "LICENSE sha256 equals approved license_text_source sha256",
        ),
        _row(
            "license_metadata_visible_in_text",
            metadata_visible,
            f"spdx_license_id={spdx_license_id};holder={holder};effective_year={year}",
            "approved holder/year metadata visible in LICENSE text",
        ),
        _row(
            "commercial_independence_license_check_passed",
            _text(commercial.get("status"))
            in {"product_commercial_independence_gate_ready", "blocked_product_commercial_independence_gate"}
            and commercial.get("license_present") is True,
            (
                f"status={commercial.get('status')};license_present={commercial.get('license_present')};"
                f"commercial_claim_allowed={commercial.get('commercial_independent_product_claim_allowed')};"
                f"local_delivery_bundle_ready={commercial.get('local_delivery_bundle_ready')}"
            ),
            "commercial-independence artifact records license_present=true; non-license product-readiness blockers are tracked by the commercial gate",
        ),
        _row(
            "viewer_third_party_notice_complete",
            vendor_notice_complete,
            f"manifest={vendor_manifest.get('manifest_version')};asset_count={len(assets)};notice={_display_path(notice_path)}",
            "viewer vendor manifest assets are represented in third-party notices",
        ),
        _row(
            "third_party_dual_license_review_recorded",
            True,
            "dual_license_assets=" + (",".join(dual_license_assets) if dual_license_assets else "none"),
            "dual-license or GPL-adjacent third-party assets are surfaced for operator/legal review",
            review_required=bool(dual_license_assets),
        ),
    ]
    blockers = [row for row in rows if row["hard_blocker"]]
    review_items = [row for row in rows if row["operator_review_required"]]
    review_gate_status = _text(review_gate.get("status"))
    review_gate_ready = review_gate_status == "third_party_license_review_gate_ready"
    return {
        "summary": {
            "packet_type": "self_hosted_license_distribution_audit",
            "status": "self_hosted_license_distribution_audit_recorded" if not blockers else "blocked_self_hosted_license_distribution_audit",
            "created_at_utc": _utc_now(),
            "hard_blocker_count": len(blockers),
            "operator_review_item_count": len(review_items),
            "product_license_path": _display_path(license_file),
            "product_license_sha256": license_sha,
            "spdx_license_id": spdx_license_id,
            "copyright_holder": holder,
            "effective_year": year,
            "approved_license_text_source": _display_path(source_path),
            "approved_license_text_source_sha256": source_sha,
            "viewer_third_party_notice_path": _display_path(notice_path),
            "third_party_dual_license_assets": dual_license_assets,
            "third_party_license_review_gate_status": review_gate_status,
            "third_party_license_review_gate_ready": review_gate_ready,
            "third_party_license_review_gate_blocker_count": int(review_gate.get("blocker_count") or 0),
            "third_party_license_review_gate_json": _display_path(third_party_license_review_gate_json),
            "legal_advice_provided": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Read-only self-hosted license distribution audit; checks local product LICENSE, approved license "
                "source hash, commercial-independence license status, and viewer third-party notice linkage. It does "
                "not choose a license or provide legal approval for redistribution."
            ),
            "next_required_step": (
                "Resolve hard license distribution blockers before self-hosted redistribution."
                if blockers
                else "Operator/legal review should confirm recorded dual-license third-party redistribution choices."
                if review_items and not review_gate_ready
                else "No hard license distribution blockers remain; recorded review items are surfaced for operator/legal confirmation."
                if review_items
                else "No hard blockers or recorded license-review items remain in this audit packet."
            ),
        },
        "rows": rows,
        "blockers": blockers,
        "operator_review_items": review_items,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only self-hosted license distribution audit packet.")
    parser.add_argument("--license-path", default="LICENSE")
    parser.add_argument("--license-decision-json", default="runs/product_license_decision_gate_current.json")
    parser.add_argument("--license-work-order-json", default="runs/product_license_file_creation_work_order_current.json")
    parser.add_argument("--commercial-independence-json", default="runs/product_commercial_independence_gate_current.json")
    parser.add_argument("--viewer-vendor-manifest", default="viewer/vendor/manifest.json")
    parser.add_argument("--third-party-license-review-gate-json", default="runs/third_party_license_review_gate_current.json")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    args = parser.parse_args(argv)

    payload = build_audit(
        license_path=args.license_path,
        license_decision_json=args.license_decision_json,
        license_work_order_json=args.license_work_order_json,
        commercial_independence_json=args.commercial_independence_json,
        viewer_vendor_manifest=args.viewer_vendor_manifest,
        third_party_license_review_gate_json=args.third_party_license_review_gate_json,
    )
    _write_json(Path(args.out_json), payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tools.wetlab.wetlab_surface_helpers import (
    DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_CSV,
    DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON,
    DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD,
)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"json is not object: {path}")
    return payload


def _mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _copy_if_exists(src: str, dst_dir: str) -> Optional[str]:
    s = str(src).strip()
    if (not s) or (not os.path.exists(s)):
        return None
    _mkdir(dst_dir)
    dst = os.path.join(dst_dir, os.path.basename(s))
    shutil.copy2(s, dst)
    return dst


def _sha256_file(path: str) -> Optional[str]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return None
    h = hashlib.sha256()
    try:
        with open(src, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _manifest_signature(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_tag() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _resolve_optional_bundle_input(
    *,
    explicit: Any,
    nightly_paths: Dict[str, Any],
    nightly_keys: Sequence[str],
    known_defaults: Sequence[str] = (),
) -> str:
    candidate = str(explicit or "").strip()
    if candidate:
        return candidate
    for key in nightly_keys:
        candidate = str(nightly_paths.get(key, "") or "").strip()
        if candidate:
            return candidate
    for default_path in known_defaults:
        candidate = str(default_path or "").strip()
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def build_bundle(args: argparse.Namespace) -> Dict[str, Any]:
    nightly_json = str(args.nightly_summary_json).strip()
    if not nightly_json:
        raise ValueError("--nightly-summary-json is required")
    if not os.path.exists(nightly_json):
        raise FileNotFoundError(f"nightly summary not found: {nightly_json}")

    nightly = _read_json(nightly_json)
    paths = nightly.get("paths", {}) if isinstance(nightly.get("paths"), dict) else {}
    date_tag = str(nightly.get("date_tag", "")).strip() or str(getattr(args, "date_tag", "")).strip()
    bundle_tag = str(getattr(args, "bundle_tag", "")).strip() or (date_tag if date_tag else _default_tag())

    out_root = str(args.out_dir).strip() or "runs/commercial_delivery"
    bundle_dir = os.path.join(out_root, f"bundle_{bundle_tag}")
    _mkdir(bundle_dir)

    # Priority: explicit arg > nightly paths > known defaults
    external_packet_json = str(getattr(args, "external_packet_json", "")).strip() or str(
        paths.get("external_packet_json", "")
    )
    dashboard_html = str(getattr(args, "dashboard_html", "")).strip() or str(paths.get("dashboard_html", ""))
    commercial_json = str(getattr(args, "commercial_readiness_json", "")).strip() or str(
        paths.get("commercial_readiness_json", "")
    )
    commercial_csv = str(getattr(args, "commercial_readiness_csv", "")).strip() or str(
        paths.get("commercial_readiness_csv", "")
    )
    commercial_md = str(getattr(args, "commercial_readiness_md", "")).strip() or str(
        paths.get("commercial_readiness_md", "")
    )
    nightly_md = str(getattr(args, "nightly_summary_md", "")).strip() or str(paths.get("batch_summary_md", ""))
    commercial_summary: Dict[str, Any] = {}
    if commercial_json and os.path.exists(commercial_json):
        try:
            commercial_payload = _read_json(commercial_json)
        except Exception:
            commercial_payload = {}
        commercial_summary = (
            commercial_payload.get("summary", {})
            if isinstance(commercial_payload.get("summary"), dict)
            else {}
        )
    wetlab_queue_json = _resolve_optional_bundle_input(
        explicit=getattr(args, "wetlab_execution_readiness_queue_json", ""),
        nightly_paths=paths,
        nightly_keys=("wetlab_execution_readiness_queue_json",),
        known_defaults=(DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON,),
    )
    wetlab_queue_csv = _resolve_optional_bundle_input(
        explicit=getattr(args, "wetlab_execution_readiness_queue_csv", ""),
        nightly_paths=paths,
        nightly_keys=("wetlab_execution_readiness_queue_csv",),
        known_defaults=(DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_CSV,),
    )
    wetlab_queue_md = _resolve_optional_bundle_input(
        explicit=getattr(args, "wetlab_execution_readiness_queue_md", ""),
        nightly_paths=paths,
        nightly_keys=("wetlab_execution_readiness_queue_md", "wetlab_execution_readiness_queue_artifact"),
        known_defaults=(DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD,),
    )

    wanted = [
        {"name": "nightly_summary_json", "src": nightly_json},
        {"name": "nightly_summary_md", "src": nightly_md},
        {"name": "external_packet_json", "src": external_packet_json},
        {"name": "dashboard_html", "src": dashboard_html},
        {"name": "commercial_readiness_json", "src": commercial_json},
        {"name": "commercial_readiness_csv", "src": commercial_csv},
        {"name": "commercial_readiness_md", "src": commercial_md},
    ]
    for name, src in (
        ("wetlab_execution_readiness_queue_json", wetlab_queue_json),
        ("wetlab_execution_readiness_queue_csv", wetlab_queue_csv),
        ("wetlab_execution_readiness_queue_md", wetlab_queue_md),
    ):
        if str(src).strip():
            wanted.append({"name": name, "src": src})

    included: List[Dict[str, Any]] = []
    missing: List[Dict[str, str]] = []
    files_dir = os.path.join(bundle_dir, "files")
    for item in wanted:
        name = str(item.get("name", ""))
        src = str(item.get("src", "")).strip()
        copied = _copy_if_exists(src=src, dst_dir=files_dir)
        if copied:
            rec: Dict[str, Any] = {
                "name": name,
                "src": src,
                "dst": copied,
            }
            try:
                rec["size_bytes"] = int(os.path.getsize(copied))
            except Exception:
                rec["size_bytes"] = None
            rec["sha256"] = _sha256_file(copied)
            included.append(rec)
        else:
            missing.append({"name": name, "src": src})

    manifest_core = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "bundle_tag": bundle_tag,
        "source_nightly_summary_json": nightly_json,
        "included_files": included,
        "missing_files": missing,
        "included_count": int(len(included)),
        "missing_count": int(len(missing)),
        "nightly_pass": bool(nightly.get("pass", False)),
        "commercial_readiness_status": nightly.get("commercial_readiness_status", {}),
        "wetlab_execution_readiness_status": {
            "queue_ready": bool(
                commercial_summary.get("wetlab_execution_readiness_queue_ready", False)
                or wetlab_queue_json
                or wetlab_queue_csv
                or wetlab_queue_md
            ),
            "json": wetlab_queue_json,
            "csv": wetlab_queue_csv,
            "artifact": wetlab_queue_md,
            "top_priority_lane_id": str(
                commercial_summary.get("wetlab_execution_readiness_queue_top_priority_lane_id", "")
            ).strip(),
            "top_priority_status": str(
                commercial_summary.get("wetlab_execution_readiness_queue_top_priority_status", "")
            ).strip(),
            "status_line": str(
                commercial_summary.get("wetlab_execution_readiness_queue_status_line", "")
            ).strip(),
            "blocker_signal": str(
                commercial_summary.get("wetlab_execution_readiness_queue_blocker_signal", "")
            ).strip(),
            "next_required_step": str(
                commercial_summary.get("wetlab_execution_readiness_queue_next_required_step", "")
            ).strip(),
        },
    }
    manifest = dict(manifest_core)
    manifest["manifest_signature_sha256"] = _manifest_signature(manifest_core)
    manifest_json = os.path.join(bundle_dir, "manifest.json")
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Commercial Delivery Bundle",
        "",
        f"- bundle_tag: {bundle_tag}",
        f"- generated_at_local: {manifest['generated_at_local']}",
        f"- source_nightly_summary_json: {nightly_json}",
        f"- nightly_pass: {manifest['nightly_pass']}",
        f"- included_count: {manifest['included_count']}",
        f"- missing_count: {manifest['missing_count']}",
        f"- manifest_signature_sha256: {manifest.get('manifest_signature_sha256')}",
        "",
        "## Included Files",
    ]
    if included:
        for row in included:
            md_lines.append(f"- {row['name']}: `{row['dst']}`")
    else:
        md_lines.append("- none")
    md_lines.append("")
    md_lines.append("## Wetlab Execution Readiness")
    md_lines.append(
        f"- queue_ready: `{manifest['wetlab_execution_readiness_status'].get('queue_ready', False)}`"
    )
    md_lines.append(
        f"- artifact: `{manifest['wetlab_execution_readiness_status'].get('artifact', '')}`"
    )
    md_lines.append(
        f"- top_priority_lane_id: `{manifest['wetlab_execution_readiness_status'].get('top_priority_lane_id', '')}`"
    )
    md_lines.append(
        f"- top_priority_status: `{manifest['wetlab_execution_readiness_status'].get('top_priority_status', '')}`"
    )
    md_lines.append(
        f"- status_line: `{manifest['wetlab_execution_readiness_status'].get('status_line', '')}`"
    )
    md_lines.append(
        f"- blocker_signal: `{manifest['wetlab_execution_readiness_status'].get('blocker_signal', '')}`"
    )
    md_lines.append(
        f"- next_required_step: `{manifest['wetlab_execution_readiness_status'].get('next_required_step', '')}`"
    )
    md_lines.append("")
    md_lines.append("## Missing Files")
    if missing:
        for row in missing:
            md_lines.append(f"- {row['name']}: `{row['src']}`")
    else:
        md_lines.append("- none")
    manifest_md = os.path.join(bundle_dir, "manifest.md")
    with open(manifest_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    archive_base = os.path.join(out_root, f"commercial_delivery_{bundle_tag}")
    archive_zip = shutil.make_archive(archive_base, "zip", root_dir=bundle_dir)
    archive_size = int(os.path.getsize(archive_zip)) if os.path.exists(archive_zip) else 0
    archive_sha = _sha256_file(archive_zip)
    manifest["archive"] = {
        "zip_path": archive_zip,
        "size_bytes": archive_size,
        "sha256": archive_sha,
    }
    manifest["manifest_signature_sha256"] = _manifest_signature(
        {k: v for k, v in manifest.items() if k != "manifest_signature_sha256"}
    )
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    md_lines.extend(
        [
            "",
            "## Archive",
            f"- zip_path: `{archive_zip}`",
            f"- size_bytes: {archive_size}",
            f"- sha256: `{archive_sha}`",
            f"- manifest_signature_sha256: `{manifest.get('manifest_signature_sha256')}`",
        ]
    )
    with open(manifest_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    payload = {
        "bundle_tag": bundle_tag,
        "bundle_dir": bundle_dir,
        "archive_zip": archive_zip,
        "archive_sha256": archive_sha,
        "manifest_json": manifest_json,
        "manifest_md": manifest_md,
        "included_count": int(len(included)),
        "missing_count": int(len(missing)),
        "manifest_signature_sha256": manifest.get("manifest_signature_sha256"),
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build single-zip commercial delivery bundle from nightly artifacts.")
    p.add_argument("--nightly-summary-json", type=str, required=True)
    p.add_argument("--bundle-tag", type=str, default="")
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-dir", type=str, default="runs/commercial_delivery")
    p.add_argument("--external-packet-json", type=str, default="")
    p.add_argument("--dashboard-html", type=str, default="")
    p.add_argument("--commercial-readiness-json", type=str, default="")
    p.add_argument("--commercial-readiness-csv", type=str, default="")
    p.add_argument("--commercial-readiness-md", type=str, default="")
    p.add_argument("--wetlab-execution-readiness-queue-json", type=str, default="")
    p.add_argument("--wetlab-execution-readiness-queue-csv", type=str, default="")
    p.add_argument(
        "--wetlab-execution-readiness-queue-md",
        "--wetlab-execution-readiness-queue-artifact",
        dest="wetlab_execution_readiness_queue_md",
        type=str,
        default="",
    )
    p.add_argument("--nightly-summary-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_bundle(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

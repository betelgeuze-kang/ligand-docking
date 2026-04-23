#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _safe_unlink(path: Path) -> None:
    if path.is_symlink() or path.exists():
        path.unlink()


def _copy_if_exists(src: str, dst_dir: Path) -> Optional[str]:
    src_path = Path(src)
    if (not src) or (not src_path.exists()) or (not src_path.is_file()):
        return None
    _ensure_dir(dst_dir)
    dst_path = dst_dir / src_path.name
    shutil.copy2(src_path, dst_path)
    return str(dst_path)


def _collect_core_artifacts(summary_payload: Dict[str, Any]) -> List[str]:
    artifacts = summary_payload.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return []

    out: List[str] = []
    keys = [
        "summary_json",
        "summary_csv",
        "summary_md",
        "packet_json",
        "accuracy_external_csv",
        "accuracy_external_json",
        "accuracy_gate_json",
        "accuracy_gate_csv",
        "speed_stage2_csv",
        "speed_stage2_json",
        "md_validation_csv",
        "md_validation_json",
        "long_stability_csv",
        "long_stability_json",
        "external_manifest_csv",
    ]
    for k in keys:
        v = artifacts.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v)

    parity_prefix = artifacts.get("accuracy_gate_parity_prefix")
    if isinstance(parity_prefix, str) and parity_prefix.strip():
        out.append(f"{parity_prefix}_target.csv")
    return out


def _archive_direct_files_in_date_dir(
    date_dir: Path,
    keep_names: Sequence[str],
    archive_root: Path,
    dry_run: bool,
) -> List[str]:
    keep = set(str(x) for x in keep_names)
    moved: List[str] = []
    if not date_dir.exists():
        return moved

    stamp = dt.date.today().isoformat()
    archive_dir = archive_root / stamp / date_dir.name
    for p in sorted(date_dir.iterdir()):
        if not p.is_file():
            continue
        if p.name in keep:
            continue
        _ensure_dir(archive_dir)
        dst = archive_dir / p.name
        if dst.exists():
            stem = dst.stem
            suf = dst.suffix
            idx = 2
            while dst.exists():
                dst = archive_dir / f"{stem}__{idx}{suf}"
                idx += 1
        moved.append(str(dst))
        if not dry_run:
            shutil.move(str(p), str(dst))
    return moved


def publish_release(
    summary_json: str,
    submission_root: str = "runs/external_eval_submission",
    release_tag: str = "",
    clean_target_dir: bool = True,
    archive_date_dir_files: bool = True,
    archive_root: str = "runs/external_eval_submission/_archive",
    dry_run: bool = False,
) -> Dict[str, Any]:
    payload = _load_json(summary_json)
    date_tag = str(payload.get("date_tag", "")).strip()
    if not date_tag:
        raise ValueError(f"missing date_tag in summary: {summary_json}")

    default_tag = Path(summary_json).name.replace("_summary.json", "")
    tag = str(release_tag).strip() or default_tag

    sub_root = Path(submission_root)
    date_dir = sub_root / f"openmm_2bead_strict_{date_tag}"
    target_dir = date_dir / tag
    send_file = date_dir / "SEND_THIS_FILE.json"
    latest_release = date_dir / "LATEST_RELEASE"

    copied: List[str] = []
    artifacts = _collect_core_artifacts(payload)
    if not dry_run:
        _ensure_dir(target_dir)
        if bool(clean_target_dir):
            for p in target_dir.iterdir():
                if p.is_file() or p.is_symlink():
                    p.unlink()
                elif p.is_dir():
                    shutil.rmtree(p)

    for src in artifacts:
        dst = _copy_if_exists(src, target_dir) if not dry_run else str(target_dir / Path(src).name)
        if dst:
            copied.append(dst)

    packet_path = payload.get("artifacts", {}).get("packet_json", "")
    packet_name = Path(str(packet_path)).name if str(packet_path).strip() else ""
    packet_in_target = target_dir / packet_name if packet_name else None

    if not dry_run:
        _ensure_dir(date_dir)
        _safe_unlink(send_file)
        if packet_in_target and packet_in_target.exists():
            send_file.symlink_to(Path(tag) / packet_in_target.name)

        _safe_unlink(latest_release)
        latest_release.symlink_to(Path(tag))

    archived_files: List[str] = []
    if bool(archive_date_dir_files):
        keep_names = [send_file.name, latest_release.name]
        archived_files = _archive_direct_files_in_date_dir(
            date_dir=date_dir,
            keep_names=keep_names,
            archive_root=Path(archive_root),
            dry_run=bool(dry_run),
        )

    release_manifest = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "release_tag": tag,
        "summary_json": summary_json,
        "target_dir": str(target_dir),
        "copied_files": copied,
        "send_this_file": str(send_file),
        "latest_release_link": str(latest_release),
        "archived_date_dir_files_count": int(len(archived_files)),
        "archived_date_dir_files": archived_files,
        "dry_run": bool(dry_run),
    }
    manifest_path = target_dir / "RELEASE_MANIFEST.json"
    if not dry_run:
        _ensure_dir(target_dir)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(release_manifest, f, indent=2, ensure_ascii=False)
    release_manifest["release_manifest_json"] = str(manifest_path)
    return release_manifest


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Publish a clean OpenMM 2-bead strict release folder from a strict-release summary json."
    )
    p.add_argument("--summary-json", type=str, required=True)
    p.add_argument("--submission-root", type=str, default="runs/external_eval_submission")
    p.add_argument("--release-tag", type=str, default="")
    p.add_argument("--clean-target-dir", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--archive-date-dir-files", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--archive-root", type=str, default="runs/external_eval_submission/_archive")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = publish_release(
        summary_json=str(args.summary_json),
        submission_root=str(args.submission_root),
        release_tag=str(args.release_tag),
        clean_target_dir=bool(args.clean_target_dir),
        archive_date_dir_files=bool(args.archive_date_dir_files),
        archive_root=str(args.archive_root),
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

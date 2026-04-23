#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Sequence


def _collect_inputs(paths: Sequence[str], globs: Sequence[str]) -> List[str]:
    out: List[str] = []
    for p in paths:
        t = str(p).strip()
        if t:
            out.append(t)
    for g in globs:
        tok = str(g).strip()
        if not tok:
            continue
        out.extend(sorted(glob.glob(tok)))
    uniq: List[str] = []
    seen = set()
    for p in out:
        ap = os.path.abspath(str(p))
        if ap in seen:
            continue
        seen.add(ap)
        if os.path.isfile(ap):
            uniq.append(ap)
    return uniq


def _base_name(path: str) -> str:
    return os.path.splitext(os.path.basename(str(path)))[0]


def _is_exec_file(path: str) -> bool:
    p = str(path).strip()
    return bool(p) and os.path.isfile(p) and os.access(p, os.X_OK)


def _resolve_chimerax_path(bin_name: str) -> str:
    tok = str(bin_name).strip() or "chimerax"
    if _is_exec_file(tok):
        return os.path.abspath(tok)
    found = shutil.which(tok)
    if found:
        return str(found)

    # Local fallback search for environments where ~/.local/bin is not in PATH.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates: List[str] = []
    if tok == "chimerax":
        candidates.extend(
            [
                os.path.expanduser("~/.local/bin/chimerax"),
                os.path.join(repo_root, "tools", "bin", "chimerax", "local_unpack", "usr", "bin", "chimerax"),
                "/usr/bin/chimerax",
                "/usr/lib/ucsf-chimerax/bin/ChimeraX",
            ]
        )
    for cand in candidates:
        if _is_exec_file(cand):
            return os.path.abspath(cand)
    return ""


def _build_cxc_script(pdb_path: str, out_mp4: str, fps: int, turn_steps: int) -> str:
    pp = os.path.abspath(str(pdb_path))
    mp4 = os.path.abspath(str(out_mp4))
    return "\n".join(
        [
            f"open {pp}",
            "hide atoms",
            "show cartoons",
            "color byattribute bfactor palette alphafold",
            "lighting soft",
            "graphics silhouettes true",
            "movie record",
            f"turn y 1 {int(turn_steps)}",
            f"wait {int(turn_steps)}",
            f"movie encode {mp4} framerate {int(fps)}",
            "close all",
            "",
        ]
    )


def run(args: argparse.Namespace) -> Dict[str, Any]:
    pdbs = _collect_inputs(args.pdb, args.pdb_glob)
    os.makedirs(args.out_dir, exist_ok=True)

    bin_name = str(args.chimerax_bin).strip() or "chimerax"
    chimerax_path = _resolve_chimerax_path(bin_name)
    can_execute = bool(args.execute) and bool(chimerax_path)

    rows: List[Dict[str, Any]] = []
    for p in pdbs:
        stem = _base_name(p)
        cxc_path = os.path.join(args.out_dir, f"{stem}.cxc")
        mp4_path = os.path.join(args.out_dir, f"{stem}.mp4")
        script = _build_cxc_script(
            pdb_path=p,
            out_mp4=mp4_path,
            fps=int(args.fps),
            turn_steps=int(args.turn_steps),
        )
        with open(cxc_path, "w", encoding="utf-8") as f:
            f.write(script)

        rc = None
        ok = True
        stderr_tail = ""
        stdout_tail = ""
        executed = False
        if bool(args.execute):
            if can_execute:
                executed = True
                proc = subprocess.run(
                    [str(chimerax_path), "--nogui", str(cxc_path)],
                    text=True,
                    capture_output=True,
                )
                rc = int(proc.returncode)
                ok = bool(proc.returncode == 0)
                stderr_tail = "\n".join((proc.stderr or "").splitlines()[-30:])
                stdout_tail = "\n".join((proc.stdout or "").splitlines()[-30:])
            else:
                ok = False if bool(args.fail_on_missing) else True
                rc = 127 if bool(args.fail_on_missing) else 0
                stderr_tail = "chimerax executable not found"

        script_ready = bool(os.path.exists(cxc_path))
        mp4_ready = bool(os.path.exists(mp4_path))
        if mp4_ready:
            asset_status = "turntable_mp4_ready"
            recommended_action = "open_turntable_mp4"
        elif script_ready:
            asset_status = "turntable_script_ready"
            recommended_action = "render_turntable_mp4"
        else:
            asset_status = "turntable_plan_missing"
            recommended_action = "regenerate_turntable_plan"

        rows.append(
            {
                "asset_kind": "chimerax_turntable",
                "asset_label": f"{stem}_turntable",
                "pdb_path": str(p),
                "source_pdb_path": str(p),
                "script_path": str(cxc_path),
                "mp4_path": str(mp4_path),
                "script_ready": script_ready,
                "mp4_ready": mp4_ready,
                "asset_status": asset_status,
                "recommended_action": recommended_action,
                "render_command_hint": f"{str(chimerax_path or bin_name)} --nogui {str(cxc_path)}",
                "executed": bool(executed),
                "ok": bool(ok),
                "returncode": rc,
                "stderr_tail": stderr_tail,
                "stdout_tail": stdout_tail,
            }
        )

    if args.out_csv:
        os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
        keys = [
            "asset_kind",
            "asset_label",
            "pdb_path",
            "source_pdb_path",
            "script_path",
            "mp4_path",
            "script_ready",
            "mp4_ready",
            "asset_status",
            "recommended_action",
            "render_command_hint",
            "executed",
            "ok",
            "returncode",
            "stderr_tail",
            "stdout_tail",
        ]
        with open(args.out_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in rows:
                w.writerow(row)

    summary = {
        "ok": bool(all(bool(r.get("ok", False)) for r in rows)) if rows else (not bool(args.fail_on_empty)),
        "inputs": int(len(pdbs)),
        "render_rows": int(len(rows)),
        "execute": bool(args.execute),
        "chimerax_bin": str(bin_name),
        "chimerax_path": str(chimerax_path) if chimerax_path else "",
        "out_dir": str(args.out_dir),
        "out_csv": str(args.out_csv),
        "rows": rows[:2000],
    }
    if (not rows) and bool(args.fail_on_empty):
        summary["ok"] = False
        summary["error"] = "no_input_pdb"
    if args.out_json:
        os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate ChimeraX headless movie scripts (and optional mp4 rendering).")
    p.add_argument("--pdb", action="append", default=[], help="Input PDB file path (repeatable).")
    p.add_argument("--pdb-glob", action="append", default=[], help="Input PDB glob pattern(s).")
    p.add_argument("--out-dir", type=str, required=True, help="Output dir for .cxc and .mp4.")
    p.add_argument("--out-csv", type=str, default="", help="Optional per-file render report CSV.")
    p.add_argument("--out-json", type=str, default="", help="Optional summary JSON.")
    p.add_argument("--chimerax-bin", type=str, default="chimerax")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--turn-steps", type=int, default=360)
    p.add_argument("--execute", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--fail-on-missing", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--fail-on-empty", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not bool(summary.get("ok", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

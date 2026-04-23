#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from typing import Any, Dict, List, Optional, Sequence


TARGETS = [
    {"name": "alpha_synuclein_full", "uniprot_id": "P37840", "residue_start": 1, "residue_end": 140},
    {"name": "fus_lcd", "uniprot_id": "P35637", "residue_start": 1, "residue_end": 214},
    {"name": "hnrnpa1_lcd", "uniprot_id": "P09651", "residue_start": 186, "residue_end": 320},
    {"name": "tardbp_ctd", "uniprot_id": "Q13148", "residue_start": 267, "residue_end": 414},
    {"name": "tp53_tad", "uniprot_id": "P04637", "residue_start": 1, "residue_end": 93},
]


def fetch(args: argparse.Namespace) -> Dict[str, Any]:
    out_dir = os.path.abspath(str(args.out_dir).strip() or "/home/betelgeuze/분자동역학/data/native/idp_llps")
    os.makedirs(out_dir, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for target in TARGETS:
        out_path = os.path.join(out_dir, f"{target['name']}.pdb")
        latest_version = 6
        try:
            with urllib.request.urlopen(f"https://alphafold.ebi.ac.uk/api/prediction/{target['uniprot_id']}", timeout=20) as r:
                api_payload = json.loads(r.read().decode("utf-8"))
            if isinstance(api_payload, list) and api_payload:
                latest_version = int(api_payload[0].get("latestVersion", latest_version))
        except Exception:
            pass
        url = ""
        rec: Dict[str, Any] = dict(target)
        rec["pdb_path"] = out_path
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            rec["url"] = f"https://alphafold.ebi.ac.uk/files/AF-{target['uniprot_id']}-F1-model_v{latest_version}.pdb"
            rec["downloaded"] = False
            rec["ok"] = True
            rows.append(rec)
            continue
        proc = None
        stderr_tail = ""
        for version in range(int(latest_version), 0, -1):
            trial_url = f"https://alphafold.ebi.ac.uk/files/AF-{target['uniprot_id']}-F1-model_v{version}.pdb"
            proc = subprocess.run(["curl", "-fsSL", "-o", out_path, trial_url], capture_output=True, text=True)
            if int(proc.returncode) == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                url = trial_url
                break
            stderr_tail = "\n".join((proc.stderr or "").splitlines()[-10:])
        rec["url"] = url or f"https://alphafold.ebi.ac.uk/files/AF-{target['uniprot_id']}-F1-model_v{latest_version}.pdb"
        rec["downloaded"] = True
        rec["ok"] = bool(url) and os.path.exists(out_path) and os.path.getsize(out_path) > 0
        rec["stderr_tail"] = stderr_tail
        rows.append(rec)
    out_json = os.path.abspath(str(args.out_json).strip() or "/home/betelgeuze/분자동역학/runs/idp_llps_afdb_fetch_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"out_dir": out_dir, "targets": rows, "all_ok": all(bool(r["ok"]) for r in rows)}, f, indent=2, ensure_ascii=False)
    return {"out_dir": out_dir, "targets": rows, "all_ok": all(bool(r["ok"]) for r in rows), "out_json": out_json}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch small real IDP/LLPS AFDB set.")
    p.add_argument("--out-dir", type=str, default="/home/betelgeuze/분자동역학/data/native/idp_llps")
    p.add_argument("--out-json", type=str, default="/home/betelgeuze/분자동역학/runs/idp_llps_afdb_fetch_summary.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = fetch(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload["all_ok"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

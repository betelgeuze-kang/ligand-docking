#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()


def _resolve_from_base(base_spec_path: Path, path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p.resolve()
    candidates = [
        (base_spec_path.parent / p).resolve(),
        (base_spec_path.parent.parent / p).resolve() if base_spec_path.parent.parent != base_spec_path.parent else (base_spec_path.parent / p).resolve(),
        (ROOT / p).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return (ROOT / p).resolve()


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "embed_seed_shift1",
        "suffix": "rb_embed29",
        "title": "Embedding Seed Shift",
        "description": "Change only csv_relax_embed_seed from 13 to 29 to test 3D embedding stability without changing decoy synthesis or ranking bootstrap.",
        "perturbations": {"csv_relax_embed_seed": 29},
    },
    {
        "scenario_id": "decoy_seed_shift1",
        "suffix": "rb_decoy29",
        "title": "Hard-Decoy Seed Shift",
        "description": "Change only hard_decoy_synth_random_seed from 13 to 29 to test hard-decoy resampling stability.",
        "perturbations": {"hard_decoy_synth_random_seed": 29},
    },
    {
        "scenario_id": "bootstrap_seed_shift1",
        "suffix": "rb_boot31",
        "title": "Bootstrap Seed Shift",
        "description": "Change only ranking_bootstrap_seed from 17 to 31 to test uncertainty-estimation stability without changing generated ligand or decoy structures.",
        "perturbations": {"ranking_bootstrap_seed": 31},
    },
    {
        "scenario_id": "decoy_pressure_12k",
        "suffix": "rb_decoy12k",
        "title": "Decoy Pressure Increase",
        "description": "Increase hard_decoy_synth_total_decoys from 10000 to 12000 while preserving targets, labels, thresholds, and accepted score selections.",
        "perturbations": {"hard_decoy_synth_total_decoys": 12000},
    },
]


def _clone_profile(src: Path, dst: Path, perturbations: dict[str, Any], scenario_title: str, scenario_desc: str) -> list[str]:
    payload = _read_json(src)
    changed: list[str] = []
    for key, value in perturbations.items():
        if key in payload:
            payload[key] = value
            changed.append(key)
    desc = str(payload.get("description") or "").strip()
    extra = f"{scenario_title}: {scenario_desc}"
    payload["description"] = f"{desc} {extra}".strip() if desc else extra
    _write_json(dst, payload)
    return changed


def _spec_with_profiles(base_spec: dict[str, Any], scenario: dict[str, Any], profile_map: dict[str, str]) -> dict[str, Any]:
    spec = deepcopy(base_spec)
    spec["protocol_id"] = f"external_validation_biorxiv_robustness_{scenario['scenario_id']}"
    spec["protocol_title"] = f"{scenario['title']} for Cross-Domain Blind Architecture Validation"
    spec["protocol_version"] = f"robustness_{scenario['scenario_id']}"
    spec["description"] = (
        f"Supplemental robustness scenario '{scenario['scenario_id']}' built on the promoted v7r1 stack. "
        f"{scenario['description']}"
    )
    spec["revision_note"] = (
        f"{scenario['scenario_id']} preserves targets, labels, gates, and accepted score selections while applying "
        f"the following perturbations where supported: {', '.join(sorted(scenario['perturbations'].keys()))}."
    )
    if isinstance(spec.get("global_governance"), dict):
        claim_scope = spec["global_governance"].setdefault("claim_scope", [])
        note = f"This protocol is supplemental robustness evidence for scenario {scenario['scenario_id']} and does not replace the accepted promoted package."
        if note not in claim_scope:
            claim_scope.append(note)
    for set_row in spec.get("sets", []):
        for task in set_row.get("tasks", []):
            profile_json = str(task.get("profile_json") or "")
            if profile_json and profile_json in profile_map:
                task["profile_json"] = profile_map[profile_json]
        set_row["preregistered_claim"] = f"Supplemental robustness evidence for scenario {scenario['scenario_id']} under frozen targets, labels, gates, and acceptance rules."
    return spec


def main() -> int:
    ap = argparse.ArgumentParser(description="Build follow-up robustness battery specs from the promoted v7r1 validation stack.")
    ap.add_argument("--base-spec-json", default="config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json")
    ap.add_argument("--out-config-dir", default="config")
    ap.add_argument("--out-json", default="runs/biorxiv_robustness_battery_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_robustness_battery_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_robustness_battery_current.md")
    args = ap.parse_args()

    base_spec_path = _resolve(args.base_spec_json)
    base_spec = _read_json(base_spec_path)
    out_config_dir = _resolve(args.out_config_dir)
    out_config_dir.mkdir(parents=True, exist_ok=True)

    unique_profiles: dict[str, Path] = {}
    for set_row in base_spec.get("sets", []):
        for task in set_row.get("tasks", []):
            profile_json = str(task.get("profile_json") or "").strip()
            if not profile_json:
                continue
            src = _resolve_from_base(base_spec_path, profile_json)
            if src.exists():
                unique_profiles[profile_json] = src

    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        profile_map: dict[str, str] = {}
        changed_profile_count = 0
        changed_keys: set[str] = set()
        for rel_src, src in unique_profiles.items():
            dst = out_config_dir / f"{src.stem}_{scenario['suffix']}.json"
            changed = _clone_profile(src, dst, scenario["perturbations"], scenario["title"], scenario["description"])
            if changed:
                changed_profile_count += 1
                changed_keys.update(changed)
            profile_map[rel_src] = _rel_or_abs(dst)
        spec = _spec_with_profiles(base_spec, scenario, profile_map)
        spec_path = out_config_dir / f"external_validation_biorxiv_{scenario['scenario_id']}.json"
        _write_json(spec_path, spec)
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "title": scenario["title"],
                "changed_profile_count": changed_profile_count,
                "changed_keys": ",".join(sorted(changed_keys)),
                "spec_json": _rel_or_abs(spec_path),
                "runner_command": (
                    f"python3 tools/run_biorxiv_robustness_scenario.py "
                    f"--scenario {scenario['scenario_id']} "
                    f"--set-spec-json {_rel_or_abs(spec_path)} "
                    f"--tag {dt.date.today().isoformat()}_{scenario['scenario_id']}"
                ),
            }
        )

    payload = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_spec_json": str(base_spec_path),
        "scenario_count": len(rows),
        "rows": rows,
    }
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    _write_json(out_json, payload)

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["scenario_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    lines = [
        "# bioRxiv Robustness Battery",
        "",
        f"- base_spec_json: `{base_spec_path}`",
        f"- scenario_count: `{len(rows)}`",
        "",
        "| scenario_id | changed_profile_count | changed_keys | spec_json |",
        "| --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['scenario_id']} | {row['changed_profile_count']} | {row['changed_keys']} | `{row['spec_json']}` |"
        )
    lines.extend(["", "## Runner Commands", ""])
    for row in rows:
        lines.append(f"- `{row['runner_command']}`")
    _write_text(out_md, "\n".join(lines) + "\n")

    print(json.dumps({"ok": True, "out_json": str(out_json), "scenario_count": len(rows)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

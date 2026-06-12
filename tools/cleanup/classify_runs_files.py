#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Tuple


CategoryRule = Tuple[str, str, Callable[[str], bool]]


RULES: List[CategoryRule] = [
    (
        "01_accuracy_gate_core",
        "Final/variant accuracy gate summaries.",
        lambda n: n.startswith("accuracy_gate")
        and ("_parity" not in n)
        and ("_stage2" not in n),
    ),
    (
        "02_accuracy_gate_parity",
        "Parity artifacts generated from accuracy gate runs.",
        lambda n: n.startswith("accuracy_gate") and ("_parity" in n),
    ),
    (
        "03_accuracy_gate_stage2",
        "Stage2 performance artifacts generated from accuracy gate runs.",
        lambda n: n.startswith("accuracy_gate") and ("_stage2" in n),
    ),
    (
        "04_stage2_reports",
        "Standalone stage2 performance reports.",
        lambda n: n.startswith("stage2_"),
    ),
    (
        "05_parity_reports",
        "Standalone parity reports and temporary parity outputs.",
        lambda n: n.startswith("parity_") or n.startswith("neighbor_force_parity") or n.startswith("tmp_parity"),
    ),
    (
        "06_physics_fidelity",
        "Physics fidelity reports (restrained vs unrestrained).",
        lambda n: n.startswith("physics_fidelity_report"),
    ),
    (
        "07_uq_reports",
        "Uncertainty/overflow neighbor-list sweep outputs.",
        lambda n: n.startswith("uq_"),
    ),
    (
        "08_neighbor_sweep",
        "Neighbor sweep aggregate reports.",
        lambda n: n.startswith("neighbor_sweep_report"),
    ),
    (
        "09_external_eval_packet",
        "Single-file external evaluation packets.",
        lambda n: n.startswith("external_eval_packet"),
    ),
    (
        "10_feature_matrix",
        "Per-target/per-step/per-residue feature matrix artifacts.",
        lambda n: n.startswith("feature_matrix"),
    ),
    (
        "10_experiment_dashboard",
        "Interactive HTML/JSON dashboards for experiment CSV + PDB review.",
        lambda n: n.startswith("experiment_dashboard_"),
    ),
    (
        "11_accuracy_external",
        "Direct external reference accuracy comparison reports.",
        lambda n: n.startswith("accuracy_external"),
    ),
    (
        "12_structure_quality",
        "AFDB/PDB quality curation reports and weights.",
        lambda n: n.startswith("structure_quality_curated"),
    ),
    (
        "12_public_structure_sources",
        "Public PDB/AFDB source download manifests and summaries.",
        lambda n: n.startswith("structure_sources_public"),
    ),
    (
        "13_external_manifest",
        "External reference manifests (real/proxy/md-only).",
        lambda n: n.startswith("external_ref_manifest"),
    ),
    (
        "14_md_gap_report",
        "MD readiness gap reports.",
        lambda n: n.startswith("md_gap_report"),
    ),
    (
        "15_md_reference_validation",
        "MD reference-set validation artifacts (path/shape/residue checks).",
        lambda n: n.startswith("md_reference_validation"),
    ),
    (
        "16_distilled_residual",
        "Storage-efficient distilled residual dataset manifests/summaries.",
        lambda n: n.startswith("distilled_residual") or n.startswith("report_distilled_residual"),
    ),
    (
        "17_sparse_checkpoint",
        "Sparse-checkpoint structural/physics validation reports.",
        lambda n: n.startswith("sparse_checkpoint"),
    ),
    (
        "18_long_stability",
        "Long-horizon stability validation outputs.",
        lambda n: n.startswith("long_stability_"),
    ),
    (
        "19_noncyclic_rebench",
        "Non-cyclic validation-set speed-accuracy re-benchmark outputs.",
        lambda n: n.startswith("noncyclic_") or ("speed_accuracy_rebench" in n),
    ),
    (
        "20_openmm_2bead_strict",
        "Strict unified OpenMM CA-SC 2-bead release artifacts.",
        lambda n: n.startswith("openmm_2bead_strict_"),
    ),
    (
        "21_post_gate_pipeline",
        "Auto-orchestrated Stage-1 gate retry and Stage-4/5/6 pipeline artifacts.",
        lambda n: n.startswith("post_gate_pipeline_"),
    ),
    (
        "22_active_learning_cycle",
        "Active-learning cycle outputs (hard mining/claim correction/curriculum).",
        lambda n: n.startswith("active_learning_cycle_"),
    ),
    (
        "22_special_case_pipeline",
        "Special-case domain coverage pipeline artifacts (metal/dna/membrane).",
        lambda n: n.startswith("special_case_"),
    ),
    (
        "23_ood_validation",
        "OOD-first validation batch outputs and related pair metrics.",
        lambda n: n.startswith("ood_first_validation_batch_")
        or n.startswith("ood_arch_focus_")
        or n.startswith("ood_measured20_validation_batch_")
        or n.startswith("ood_measured40_validation_batch_"),
    ),
    (
        "24_cath_pipeline",
        "CATH diversity split/manifests/noise-augmentation artifacts.",
        lambda n: n.startswith("cath_"),
    ),
    (
        "25_target_ai_interval_policy",
        "Auto-generated target-wise AI interval policy artifacts.",
        lambda n: n.startswith("target_ai_interval_policy"),
    ),
    (
        "26_claim_correction",
        "Claim-metric correction loop outputs (thermo/kinetics corrected artifacts and summaries).",
        lambda n: n.startswith("claim_metric_correction_loop_"),
    ),
    (
        "27_active_learning_priority",
        "Active-learning priority target synthesis artifacts (OOD high-error + oversize backlog).",
        lambda n: n.startswith("active_learning_priority_targets_"),
    ),
    (
        "28_nightly_ops",
        "Nightly operational single-report/failure/maintenance artifacts.",
        lambda n: n.startswith("nightly_failure_latest") or n.startswith("nightly_runs_maintenance_"),
    ),
    (
        "29_commercial_readiness",
        "Commercialization readiness score/report artifacts (go/no-go package).",
        lambda n: n.startswith("commercial_readiness_"),
    ),
    (
        "30_commercial_delivery_bundle",
        "Single-zip external delivery bundle artifacts for review/sales handoff.",
        lambda n: n.startswith("commercial_delivery_"),
    ),
    (
        "31_ligand_htvs_pipeline",
        "Ligand HTVS orchestrator summaries/stage artifacts and nightly status outputs.",
        lambda n: n.startswith("ligand_htvs_pipeline_")
        or n.startswith("ligand_htvs_nightly_"),
    ),
    (
        "32_ligand_mapping_queue",
        "Ligand mapping queue/library artifacts (SDF/CSV -> 2-bead queue).",
        lambda n: n.startswith("ligand_mapping_") or n.startswith("ligand_stage1_"),
    ),
    (
        "33_ligand_residual_meta",
        "Ligand-aware residual/meta learning cycle outputs.",
        lambda n: n.startswith("ligand_residual_meta_cycle_") or n.startswith("ligand_stage2_"),
    ),
    (
        "34_ligand_backmapping_scoring",
        "Ligand backmapping + scoring artifacts and delivery bundles.",
        lambda n: n.startswith("ligand_screening_delivery_") or n.startswith("ligand_stage3_"),
    ),
]


def _classify(name: str) -> str:
    for cat, _, pred in RULES:
        if pred(name):
            return cat
    return "99_other"


def _clean_view(view_root: Path) -> None:
    if not view_root.exists():
        return
    for child in view_root.iterdir():
        if child.is_dir():
            for item in child.iterdir():
                if item.is_symlink() or item.is_file():
                    item.unlink()
            child.rmdir()
        elif child.is_symlink() or child.is_file():
            child.unlink()


def _build_view(runs_dir: Path, files: List[Path]) -> Dict[str, List[Path]]:
    view_root = runs_dir / "_by_name"
    view_root.mkdir(parents=True, exist_ok=True)
    _clean_view(view_root)

    grouped: Dict[str, List[Path]] = {}
    for fp in files:
        cat = _classify(fp.name)
        grouped.setdefault(cat, []).append(fp)

    for cat, file_paths in grouped.items():
        cdir = view_root / cat
        cdir.mkdir(parents=True, exist_ok=True)
        for fp in sorted(file_paths, key=lambda x: x.name):
            name = fp.name
            src_rel = Path("..") / ".." / name
            link_path = cdir / name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(src_rel)

    return grouped


def _role_for_latest(name: str) -> str:
    stem = Path(name).stem
    suffix_roles = [
        ("_gate_attempts.csv", "gate_attempts_csv"),
        ("_atom.csv", "atom_csv"),
        ("_pair.csv", "pair_csv"),
        ("_sample.csv", "sample_csv"),
        ("_target.csv", "target_csv"),
        ("_summary.csv", "summary_csv"),
        ("_manifest.csv", "manifest_csv"),
    ]
    for suffix, role in suffix_roles:
        if name.endswith(suffix):
            return role
    if name.endswith(".csv") and "_summary" in stem:
        return "summary_csv"
    if name.endswith(".csv") and "_manifest" in stem:
        return "manifest_csv"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".csv"):
        return "csv"
    return "file"


def _pick_latest_by_role(files: List[Path]) -> Dict[str, Path]:
    def _safe_mtime(p: Path) -> float:
        try:
            return float(p.stat().st_mtime)
        except FileNotFoundError:
            return -1.0

    picked: Dict[str, Path] = {}
    for fp in files:
        if _safe_mtime(fp) < 0.0:
            continue
        role = _role_for_latest(fp.name)
        current = picked.get(role)
        if current is None or _safe_mtime(fp) > _safe_mtime(current):
            picked[role] = fp
    return picked


def _build_latest_view(runs_dir: Path, grouped: Dict[str, List[Path]]) -> Dict[str, Dict[str, Path]]:
    latest_root = runs_dir / "_latest"
    latest_root.mkdir(parents=True, exist_ok=True)
    _clean_view(latest_root)

    latest_map: Dict[str, Dict[str, Path]] = {}
    for cat, files in grouped.items():
        cdir = latest_root / cat
        cdir.mkdir(parents=True, exist_ok=True)

        role_map = _pick_latest_by_role(files)
        latest_map[cat] = role_map
        for role, fp in sorted(role_map.items()):
            link_name = f"latest_{role}{fp.suffix}"
            link_path = cdir / link_name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            src_rel = Path("..") / ".." / fp.name
            link_path.symlink_to(src_rel)

    return latest_map


def _write_index(runs_dir: Path, grouped: Dict[str, List[Path]]) -> Path:
    index_path = runs_dir / "INDEX.md"
    lines: List[str] = []
    lines.append("# Runs Folder Index")
    lines.append("")
    lines.append("This index is auto-generated by `tools/classify_runs_files.py`.")
    lines.append("Original files are preserved. Categorized symlink views are under `runs/_by_name/`.")
    lines.append("Latest snapshots per category are under `runs/_latest/`.")
    lines.append("")
    lines.append("## Categories")
    lines.append("")

    rule_map = {name: desc for name, desc, _ in RULES}
    for cat in sorted(grouped.keys()):
        desc = rule_map.get(cat, "Unclassified/misc files.")
        names = sorted((fp.name for fp in grouped[cat]))
        lines.append(f"### {cat} ({len(names)})")
        lines.append(desc)
        lines.append("")
        lines.append(f"Path: `runs/_by_name/{cat}`")
        lines.append(f"Latest: `runs/_latest/{cat}`")
        lines.append("")
        for n in names:
            lines.append(f"- `{n}`")
        lines.append("")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return index_path


def _write_latest_index(runs_dir: Path, latest_map: Dict[str, Dict[str, Path]]) -> Path:
    latest_index_path = runs_dir / "LATEST.md"
    lines: List[str] = []
    lines.append("# Runs Latest Snapshot")
    lines.append("")
    lines.append("This file is auto-generated by `tools/classify_runs_files.py`.")
    lines.append("Each category lists only the newest file by artifact role.")
    lines.append("")
    lines.append("## Latest By Category")
    lines.append("")

    for cat in sorted(latest_map.keys()):
        role_map = latest_map[cat]
        lines.append(f"### {cat} ({len(role_map)})")
        lines.append(f"Path: `runs/_latest/{cat}`")
        lines.append("")
        for role in sorted(role_map.keys()):
            fp = role_map[role]
            lines.append(f"- `{role}`: `{fp.name}`")
        lines.append("")

    with open(latest_index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return latest_index_path


def main() -> None:
    runs_dir = Path("runs")
    if not runs_dir.exists():
        raise FileNotFoundError("runs directory not found.")

    files = sorted(
        [
            p
            for p in runs_dir.iterdir()
            if p.is_file() and (not p.name.startswith("INDEX")) and (not p.name.startswith("."))
        ],
        key=lambda x: x.name,
    )
    grouped = _build_view(runs_dir, files)
    latest_map = _build_latest_view(runs_dir, grouped)
    index_path = _write_index(runs_dir, grouped)
    latest_index_path = _write_latest_index(runs_dir, latest_map)

    print(f"Indexed {len(files)} files into {len(grouped)} categories.")
    print(f"Index: {index_path}")
    print(f"View root: {runs_dir / '_by_name'}")
    print(f"Latest index: {latest_index_path}")
    print(f"Latest root: {runs_dir / '_latest'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Offline native DES370K -> unchanged V2 -> frozen energy residual shadow.

This bounded development consumer is not a protein-ligand benchmark, protected
holdout, parameter qualification, or customer runtime. All source row outcomes
remain in a denominator ledger, including unsupported chemistry and split/caps.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import platform
import resource
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from rdkit import Chem, rdBase
import sklearn

from betelgeuze_engine.product.des370k_interaction import (
    ENERGY_COLUMN, GEOMETRY_FIELDS, MODEL_CONFIG, PARAMETER_PROFILE, _number,
    score_native_dimer, sha,
)
from betelgeuze_engine.product.des370k_residual import (
    FEATURE_NAMES, SPLIT_SALT, fit_energy_residual, geometry_features,
    monomer_identity, monomer_role, predict_energy_residual,
)

ARCHIVE_SHA256 = "34e36d0a6a19e67b51d17e466dc2cd98200101e4f42768c23f8c774edb94f5a0"
ROLES = ("fit", "calibration", "development")


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def native_rows(archive):
    with archive.open("DES370K.csv") as stream:
        yield from csv.DictReader(io.TextIOWrapper(stream))


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def support(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "invalid_smiles"
    if not 5 <= mol.GetNumHeavyAtoms() <= 12:
        return "outside_predeclared_5_to_12_heavy_atoms_per_monomer"
    if any(a.GetSymbol() not in {"C", "H", "N", "O"} or a.GetFormalCharge()
           or a.GetNumRadicalElectrons() or a.GetIsotope() for a in mol.GetAtoms()):
        return "outside_neutral_CHNO_profile"
    return None


def source_identity():
    root = Path(__file__).resolve().parents[2]
    files = sorted({*root.glob("betelgeuze_engine_v2/**/*.py"),
                    *root.glob("betelgeuze_engine/product/*.py"), Path(__file__).resolve()})
    return {"source_sha256": {str(p.relative_to(root)): file_hash(p) for p in files},
            "python": sys.version, "numpy": np.__version__, "sklearn": sklearn.__version__,
            "rdkit": rdBase.rdkitVersion, "platform": platform.platform()}


def select_metadata(archive, out, plan):
    """No computed-energy columns are accessed in any selection decision."""
    systems, geometry_counts, monomers = {}, collections.Counter(), {}
    total = 0
    for row in native_rows(archive):
        total += 1
        geometry_counts[row["geom_id"]] += 1
        pair = (row["smiles0"], row["smiles1"])
        for smi in pair:
            if smi not in monomers:
                reason = support(smi)
                identity = None if reason else monomer_identity(smi)
                monomers[smi] = {"identity": identity, "reason": reason,
                                 "role": monomer_role(identity) if identity else None}
        s = systems.setdefault(row["system_id"], {"pair": pair, "rows": 0, "conflicting": False})
        s["rows"] += 1
        s["conflicting"] |= s["pair"] != pair
    for s in systems.values():
        a, b = [monomers[x] for x in s["pair"]]
        s["reason"] = ("ambiguous_system_identity" if s["conflicting"] else a["reason"] or b["reason"]
                       or ("cross_partition_monomer_pair" if a["role"] != b["role"] else None))
        s["role"] = None if s["reason"] else a["role"]
    selected_systems = set()
    for role in ROLES:
        eligible = [key for key, s in systems.items() if s["role"] == role]
        selected_systems.update(sorted(eligible, key=lambda key: sha([SPLIT_SALT, "system", key]))[:plan["systems_per_role_cap"]])
    candidates = collections.defaultdict(list)
    for row in native_rows(archive):
        if row["system_id"] in selected_systems and geometry_counts[row["geom_id"]] == 1:
            candidates[row["system_id"]].append({key: row[key] for key in GEOMETRY_FIELDS})
    selected = {}
    for sid, rows in candidates.items():
        for row in sorted(rows, key=lambda r: sha([SPLIT_SALT, "geometry", r["geom_id"]]))[:plan["geometries_per_system_cap"]]:
            selected[row["geom_id"]] = {"geometry": row, "role": systems[sid]["role"],
                                        "evaluation_only": systems[sid]["role"] != "fit"}
    counts = collections.Counter()
    with (out / "all-source-row-outcomes.jsonl").open("w") as stream:
        for row in native_rows(archive):
            s = systems[row["system_id"]]
            reason = ("duplicate_geometry_id_rejected_all" if geometry_counts[row["geom_id"]] != 1
                      else s["reason"] or ("system_budget_cap" if row["system_id"] not in selected_systems
                      else "geometry_budget_cap" if row["geom_id"] not in selected else "selected_for_scoring"))
            counts[reason] += 1
            stream.write(json.dumps({"geom_id": row["geom_id"], "system_id": row["system_id"],
                                     "role": s["role"], "outcome": reason}) + "\n")
    ledger = {"total_source_rows": total, "source_systems": len(systems), "source_monomers": len(monomers),
              "outcomes": dict(counts), "selected_rows": len(selected),
              "selected_by_role": dict(collections.Counter(r["role"] for r in selected.values())),
              "monomers": monomers, "systems": systems, "reference_columns_used": []}
    dump(out / "metadata-selection.json", ledger)
    dump(out / "selected-geometries-label-free.json", selected)
    return selected


def metrics(records, role):
    requested = [r for r in records if r["role"] == role]
    valid = [r for r in requested if r["status"] == "evaluated"]
    supported = [r for r in valid if r["shadow"]["status"] == "shadow_prediction"]
    def errors(rows, key):
        if not rows:
            return None
        values = np.asarray([r["shadow"][key] - r["reference"]["value"] for r in rows])
        return {"n": len(rows), "mae_kcal_per_mol": float(np.abs(values).mean()),
                "rmse_kcal_per_mol": float(np.sqrt(np.mean(values ** 2)))}
    return {"requested": len(requested), "evaluated": len(valid), "failed": len(requested) - len(valid),
            "shadow_abstained": len(valid) - len(supported),
            "coverage_of_all_requested": len(supported) / len(requested) if requested else None,
            "baseline_all_evaluable": errors(valid, "baseline_kcal_per_mol"),
            "raw_shadow_all_evaluable_diagnostic_including_ood": errors(valid, "raw_shadow_energy_kcal_per_mol"),
            "baseline_on_same_supported_rows": errors(supported, "baseline_kcal_per_mol"),
            "shadow_supported": errors(supported, "supported_shadow_energy_kcal_per_mol")}


def run(archive_path, out):
    out.mkdir(parents=True, exist_ok=False)
    wall, cpu = time.perf_counter(), time.process_time()
    if file_hash(archive_path) != ARCHIVE_SHA256:
        raise ValueError("native_archive_hash_mismatch")
    runtime = source_identity()
    runtime_hash = sha(runtime)
    dump(out / "runtime.json", runtime)
    plan = {"schema_id": "des370k_bounded_energy_residual_development_v1", "archive_sha256": ARCHIVE_SHA256,
            "systems_per_role_cap": 8, "geometries_per_system_cap": 12,
            "split_salt": SPLIT_SALT, "partition": "monomer connectivity (stereoisomers grouped), 60/20/20 hash buckets",
            "split_limits": "not a scaffold or tautomer-generalization guarantee; development only",
            "selection": "metadata hashes only; no label, energy, distance or success filtering",
            "support": "neutral CHNO, 5-12 heavy atoms and <=64 total atoms per monomer; explicit native H and bonds",
            "reference": ENERGY_COLUMN, "parameter_profile": PARAMETER_PROFILE, "model_config": MODEL_CONFIG,
            "features": list(FEATURE_NAMES), "ridge_alpha": 10., "ood_max_absolute_feature_z": 10.,
            "uncertainty_calibration": "not performed; calibration partition evaluated separately",
            "fitting": "fit labels only; no tuning; freeze checkpoint and all predictions before calibration/development label extraction",
            "force_training": False, "customer_execution": False, "protected_holdout_used": False}
    dump(out / "plan-before-selection.json", plan)
    plan_hash = sha(plan)
    with zipfile.ZipFile(archive_path) as archive:
        units = {r["column"]: r["units"] for r in csv.DictReader(io.StringIO(archive.read("DES370K_meta.csv").decode()))}
        selected = select_metadata(archive, out, plan)
        scores, failures = {}, {}
        (out / "scores").mkdir()
        (out / "native-mols").mkdir()
        for gid, item in sorted(selected.items()):
            row = item["geometry"]
            try:
                block = archive.read(f"geometries/{row['system_id']}/DES370K_{gid}.mol").decode()
                (out / "native-mols" / f"{gid}.mol").write_text(block)
                scores[gid] = score_native_dimer(row, block, units=units, parameter_profile=PARAMETER_PROFILE)
                dump(out / "scores" / f"{gid}.json", scores[gid])
            except (ValueError, KeyError, RuntimeError) as exc:
                failures[gid] = {"error_type": type(exc).__name__, "reason": str(exc)}
        dump(out / "scoring-failures.json", failures)
        fit_records, native_fit = [], []
        for row in native_rows(archive):
            gid = row["geom_id"]
            if gid not in scores or selected[gid]["role"] != "fit":
                continue
            native_fit.append(row)  # original record preserved only after its fit admission
            fit_records.append({"geom_id": gid, "role": "fit", "evaluation_only": False,
                                "evidence_kind": "external_computed_reference",
                                "geometry_sha256": scores[gid]["provenance"]["native_row_geometry_sha256"],
                                "features": geometry_features(scores[gid]).tolist(),
                                "baseline_kcal_per_mol": scores[gid]["baseline"]["quantities"]["cross_total_kcal_per_mol"],
                                "reference_kcal_per_mol": _number(row[ENERGY_COLUMN], ENERGY_COLUMN)})
        dump(out / "native-fit-records.json", native_fit)
        dump(out / "fit-records.json", fit_records)
        fit_wall, fit_cpu = time.perf_counter(), time.process_time()
        checkpoint = fit_energy_residual(fit_records, runtime_sha256=runtime_hash, plan_sha256=plan_hash)
        fit_cost = {"wall_seconds": time.perf_counter() - fit_wall, "cpu_seconds": time.process_time() - fit_cpu}
        dump(out / "checkpoint.json", checkpoint)
        predictions = {}
        predict_wall, predict_cpu = time.perf_counter(), time.process_time()
        for gid, score in scores.items():
            predictions[gid] = predict_energy_residual(score, checkpoint, runtime_sha256=runtime_hash, plan_sha256=plan_hash)
        predict_cost = {"wall_seconds": time.perf_counter() - predict_wall, "cpu_seconds": time.process_time() - predict_cpu}
        dump(out / "predictions-before-evaluation.json", predictions)
        freeze = {"checkpoint_file_sha256": file_hash(out / "checkpoint.json"),
                  "predictions_file_sha256": file_hash(out / "predictions-before-evaluation.json"),
                  "fit_records_file_sha256": file_hash(out / "fit-records.json"),
                  "selection_file_sha256": file_hash(out / "selected-geometries-label-free.json"),
                  "plan_sha256": plan_hash, "runtime_sha256": runtime_hash,
                  "phase": "before_calibration_and_development_reference_extraction",
                  "is_external_approval": False}
        dump(out / "prediction-freeze.json", freeze)
        records = []
        for row in native_rows(archive):
            gid = row["geom_id"]
            if gid not in selected:
                continue
            item = selected[gid]
            record = {"geom_id": gid, "role": item["role"], "evaluation_only": item["evaluation_only"],
                      "native_record": row, "status": "scoring_failed" if gid in failures else "evaluated"}
            if gid in failures:
                record["failure"] = failures[gid]
            else:
                record["reference"] = {"value": _number(row[ENERGY_COLUMN], ENERGY_COLUMN),
                                       "evidence_kind": "external_computed_reference", "column": ENERGY_COLUMN,
                                       "units": "kcal/mol", "force_labels": None}
                record["shadow"] = predictions[gid]
            records.append(record)
        dump(out / "evaluation-records.json", records)
        if (file_hash(out / "checkpoint.json") != freeze["checkpoint_file_sha256"]
                or file_hash(out / "predictions-before-evaluation.json") != freeze["predictions_file_sha256"]):
            raise ValueError("frozen_artifact_changed_during_evaluation")
    report = {"scope": "fixed native fragment coordinates, gas-phase interaction energy; not docking or affinity",
              "roles": {role: metrics(records, role) for role in ROLES},
              "fit_cost": fit_cost, "shadow_feature_and_prediction_cost": predict_cost,
              "consumer_cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                "scope": "archive verification, metadata scans, scoring, learning, predictions and evaluation; imports excluded"},
              "selected": len(selected), "scored": len(scores), "failed": len(failures),
              "checkpoint_sha256": checkpoint["checkpoint_sha256"],
              "experimental_training": False, "external_solver_called": False,
              "scientifically_validated": False, "customer_execution": False, "uncertainty_calibrated": False}
    dump(out / "report.json", report)
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    return 2 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    return run(args.archive, args.out)


if __name__ == "__main__":
    raise SystemExit(main())

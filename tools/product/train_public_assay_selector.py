"""Small, target-specific pre-docking assay regression experiment on CPU.

This is a development cheap-selector candidate, not an energy residual model.
Document/scaffold/ligand connected components are kept in one split. IDs, assay
results and structures are never input features. No production route is enabled.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import resource
import time
from urllib.parse import unquote

import numpy as np
from rdkit import Chem, rdBase
from rdkit.Chem import rdFingerprintGenerator
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score

from tools.product.public_assay_dataset import (
    SCHEMA,
    digest,
    file_sha,
    json_text,
    require_sha,
)
from tools.product.residual_evidence import declared_evaluation_only

MODEL_SCHEMA = "public_assay_cheap_selector_ridge_v1"
FEATURES = {
    "kind": "Morgan_bit_vector",
    "radius": 2,
    "bits": 1024,
    "include_chirality": True,
    "available_at_stage": "pre_docking",
    "requires_target_structure": False,
    "target_encoding": "one_exact_target_state_per_model",
}


def features(smiles: list[str]) -> np.ndarray:
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=1024, includeChirality=True
    )
    matrix = []
    for text in smiles:
        mol = Chem.MolFromSmiles(text)
        if mol is None:
            raise ValueError("invalid_inference_smiles")
        matrix.append(generator.GetFingerprintAsNumPy(mol))
    return np.asarray(matrix, dtype=np.float64).reshape(len(smiles), 1024)


def document_keys(row: dict) -> list[str]:
    raw = row["source_provenance"]["row"]
    doi = unquote(raw.get("Article DOI", "").strip()).lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :].strip()
            break
    pmid = raw.get("PMID", "").strip()
    keys = (["doi:" + doi] if doi else []) + (["pmid:" + pmid] if pmid else [])
    if not keys:
        raise ValueError("missing_document_identity")
    return keys


def split_components(
    rows: list[dict], seed: int
) -> tuple[dict[str, list[int]], list[str]]:
    """No label access. Connected components prevent transitive split leakage."""
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, row in enumerate(rows):
        identity = row["chemical_identity"]
        keys = [("document", key) for key in document_keys(row)] + [
            ("scaffold", identity["scaffold_group"]),
            ("ligand", identity["connectivity_smiles_sha256"]),
        ]
        if row.get("ligand_id"):
            keys.append(("source_ligand_id", row["ligand_id"]))
        for inchikey in (
            identity.get("rdkit_inchikey", ""),
            row["source_provenance"]["row"].get("Ligand InChI Key", ""),
        ):
            if inchikey:
                keys.append(("inchikey_connectivity", inchikey[:14]))
        for key in keys:
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = defaultdict(list)
    for i in range(len(rows)):
        groups[find(i)].append(i)
    if len(groups) < 3:
        raise ValueError("insufficient_independent_document_scaffold_components")
    items = []
    group_ids = [""] * len(rows)
    for indices in groups.values():
        key = digest(json_text(sorted(rows[i]["record_id"] for i in indices)))
        for i in indices:
            group_ids[i] = key
        items.append((key, indices))
    items.sort(key=lambda item: (-len(item[1]), digest(str(seed) + item[0])))
    result = {"fit": [], "calibration": [], "development_test": []}
    fractions = {"fit": 0.7, "calibration": 0.15, "development_test": 0.15}
    for _, indices in items:
        destination = max(
            result, key=lambda name: fractions[name] * len(rows) - len(result[name])
        )
        result[destination].extend(indices)
    if any(len(indices) < 5 for indices in result.values()):
        raise ValueError("insufficient_rows_in_predeclared_split")
    return {name: sorted(indices) for name, indices in result.items()}, group_ids


def cohort(
    rows: list[dict], target_state: str, endpoint: str
) -> tuple[list[dict], list[dict]]:
    if endpoint not in {"Ki", "Kd", "IC50"}:
        raise ValueError("unsupported_training_endpoint")
    accepted, ledger = [], []
    for row in rows:
        if row["target_state_sha256"] != target_state:
            continue
        observations = [
            value for value in row["observations"] if value["endpoint"] == endpoint
        ]
        reason = ""
        if (
            row.get("schema_version") != SCHEMA
            or row.get("evidence_kind") != "experimental_label"
        ):
            reason = "incompatible_source_schema_or_evidence"
        elif declared_evaluation_only(row) or declared_evaluation_only(
            row["source_provenance"]["row"]
        ):
            reason = "evaluation_only_source"
        elif not row["eligible_for_split_assignment"] or row["admission_issues"]:
            reason = "intake_admission_failed"
        elif len(observations) != 1 or observations[0]["status"] != "exact":
            reason = "endpoint_not_exact_observation"
        elif not math.isfinite(observations[0]["negative_log10_molar"]):
            reason = "nonfinite_training_label"
        ledger.append(
            {
                "record_id": row["record_id"],
                "status": "excluded" if reason else "selected",
                "reason": reason,
            }
        )
        if not reason:
            accepted.append(row)
    if len({row["record_id"] for row in accepted}) != len(accepted):
        raise ValueError("duplicate_training_record_id")
    return sorted(accepted, key=lambda row: row["record_id"]), ledger


def metrics(actual: np.ndarray, predicted: np.ndarray, threshold: float) -> dict:
    finite = np.isfinite(predicted)
    selected = np.flatnonzero(finite)
    positive = actual >= threshold
    count = max(1, math.ceil(0.2 * len(actual)))
    # Equal scores at the budget boundary receive their fractional expected
    # contribution; arbitrary row order cannot make the constant baseline win.
    hits = 0.0
    remaining = count
    for score in sorted(set(predicted[finite]), reverse=True):
        tied = np.flatnonzero(finite & (predicted == score))
        take = min(remaining, len(tied))
        hits += take * float(positive[tied].mean())
        remaining -= take
        if remaining == 0:
            break
    return {
        "requested": len(actual),
        "predicted": int(finite.sum()),
        "failed": int((~finite).sum()),
        "mae": float(np.abs(actual[selected] - predicted[selected]).mean())
        if len(selected)
        else None,
        "rmse": float(np.sqrt(np.mean((actual[selected] - predicted[selected]) ** 2)))
        if len(selected)
        else None,
        "positive_count": int(positive.sum()),
        "positive_threshold_negative_log10_molar": threshold,
        "top_budget": count,
        "tie_expected_positive_hits_at_budget": hits,
        "recall_at_budget": hits / int(positive.sum()) if positive.any() else None,
        "average_precision": float(average_precision_score(positive, predicted))
        if finite.all() and positive.any()
        else None,
    }


def unique_state_metrics(
    rows: list[dict], actual: np.ndarray, predicted: np.ndarray, threshold: float
) -> dict:
    """One budget item per exact chemical state, with an explicit assay median."""
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row["chemical_identity"]["canonical_isomeric_smiles_sha256"]].append(i)
    observed = np.array([np.median(actual[indices]) for indices in groups.values()])
    estimates = np.array([np.median(predicted[indices]) for indices in groups.values()])
    return {
        **metrics(observed, estimates, threshold),
        "unit_of_budget": "unique_canonical_isomeric_chemical_state",
        "replicate_aggregation": "median_over_retained_assay_measurements",
        "raw_measurement_count": len(rows),
    }


def predict_checkpoint(
    checkpoint: Path,
    expected_sha256: str,
    smiles: list[str],
    target_state: str,
    expected_endpoint: str,
) -> np.ndarray:
    raw = checkpoint.read_bytes()
    require_sha(digest(raw), expected_sha256)
    payload = json.loads(raw)
    if (
        payload.get("schema_version") != MODEL_SCHEMA
        or payload.get("features") != FEATURES
    ):
        raise ValueError("incompatible_selector_checkpoint")
    if (
        payload.get("rdkit_version") != rdBase.rdkitVersion
        or payload.get("target_state_sha256") != target_state
    ):
        raise ValueError("selector_target_or_featurizer_mismatch")
    if (
        expected_endpoint not in {"Ki", "Kd", "IC50"}
        or payload.get("endpoint") != expected_endpoint
        or payload.get("prediction_quantity")
        != "negative_log10_molar_" + expected_endpoint
    ):
        raise ValueError("selector_endpoint_or_quantity_mismatch")
    if payload.get("source_sha256") != file_sha(Path(__file__)):
        raise ValueError("selector_implementation_changed_regenerate")
    coefficients = np.asarray(payload["coefficients"], dtype=np.float64)
    intercept = float(payload["intercept"])
    if (
        coefficients.shape != (1024,)
        or not np.isfinite(coefficients).all()
        or not math.isfinite(intercept)
    ):
        raise ValueError("invalid_selector_weights")
    return features(smiles) @ coefficients + intercept


def run(
    *,
    input_dir: Path,
    summary_sha256: str,
    target_state: str,
    endpoint: str,
    output_dir: Path,
    seed: int = 20260908,
) -> dict:
    if output_dir.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    summary_raw = (input_dir / "summary.json").read_bytes()
    require_sha(digest(summary_raw), summary_sha256)
    intake = json.loads(summary_raw)
    raw = (input_dir / "records.jsonl").read_bytes()
    require_sha(digest(raw), intake["records_sha256"])
    if intake["implementation_sha256"] != file_sha(
        Path(__file__).with_name("public_assay_dataset.py")
    ):
        raise ValueError("intake_implementation_changed_regenerate")
    allrows = [json.loads(line) for line in raw.decode().splitlines()]
    rows, ledger = cohort(allrows, target_state, endpoint)
    raw_ledger = (input_dir / "ledger.jsonl").read_bytes()
    require_sha(digest(raw_ledger), intake["ledger_sha256"])
    intake_state_ledger = [
        entry
        for line in raw_ledger.decode().splitlines()
        if (entry := json.loads(line))["target_state_sha256"] == target_state
    ]
    normalized_state_rows = len(ledger)
    if (
        sum(entry["status"] == "normalized" for entry in intake_state_ledger)
        != normalized_state_rows
    ):
        raise ValueError("normalized_cohort_ledger_mismatch")
    ledger.extend(
        entry for entry in intake_state_ledger if entry["status"] == "excluded"
    )
    split, group_ids = split_components(rows, seed)
    protocol = {
        "schema_version": MODEL_SCHEMA,
        "target_state_sha256": target_state,
        "endpoint": endpoint,
        "prediction_quantity": "negative_log10_molar_" + endpoint,
        "is_potential_energy": False,
        "intake_summary_sha256": summary_sha256,
        "records_sha256": intake["records_sha256"],
        "seed": seed,
        "ridge_alpha": 10.0,
        "feature_specification": FEATURES,
        "positive_threshold_negative_log10_molar": 6.0,
        "top_fraction": 0.2,
        "measurement_metrics_unit": "individual_measurement_rows",
        "candidate_metrics_unit": "unique_canonical_isomeric_chemical_state_with_median_observation_across_retained_assays",
        "split_policy": "connected_document_or_Murcko_scaffold_or_stereo_independent_ligand; label_blind_70_15_15_deficit_assignment",
        "split_record_ids": {
            name: [rows[i]["record_id"] for i in indices]
            for name, indices in split.items()
        },
        "claim_scope": "retrospective public development; mixed assay conditions retained; one target state and endpoint",
        "uncertainty_calibration_planned": False,
        "hyperparameter_search": False,
        "source_sha256": file_sha(Path(__file__)),
    }
    output_dir.mkdir(parents=True)
    (output_dir / "protocol-before-fit.json").write_text(
        json.dumps(protocol, indent=2, sort_keys=True)
    )
    (output_dir / "cohort-ledger.jsonl").write_text(
        "".join(json_text(row) + "\n" for row in ledger)
    )
    (output_dir / "split.jsonl").write_text(
        "".join(
            json_text(
                {
                    "record_id": rows[i]["record_id"],
                    "split": name,
                    "group": group_ids[i],
                }
            )
            + "\n"
            for name, indices in split.items()
            for i in indices
        )
    )
    feature_wall = time.perf_counter()
    x = features(
        [row["chemical_identity"]["canonical_isomeric_smiles"] for row in rows]
    )
    feature_seconds = time.perf_counter() - feature_wall
    y = np.array(
        [
            next(
                value["negative_log10_molar"]
                for value in row["observations"]
                if value["endpoint"] == endpoint
            )
            for row in rows
        ]
    )
    fit = split["fit"]
    # Repeated measurements of the same compound within one paper/assay share
    # one total unit of weight. Raw measurements and their variation stay intact.
    replicate_keys = [
        (
            rows[i]["assays"][0]["entry_assay_id"],
            rows[i]["chemical_identity"]["canonical_isomeric_smiles_sha256"],
            json_text(rows[i].get("assay_conditions", {})),
        )
        for i in fit
    ]
    repetitions = Counter(replicate_keys)
    weights = np.array([1.0 / repetitions[key] for key in replicate_keys])
    start = time.perf_counter()
    model = Ridge(alpha=10.0, solver="cholesky").fit(
        x[fit], y[fit], sample_weight=weights
    )
    fit_seconds = time.perf_counter() - start
    mean = float(np.average(y[fit], weights=weights))
    checkpoint = {
        "schema_version": MODEL_SCHEMA,
        "features": FEATURES,
        "rdkit_version": rdBase.rdkitVersion,
        "target_state_sha256": target_state,
        "endpoint": endpoint,
        "prediction_quantity": "negative_log10_molar_" + endpoint,
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "training_protocol_sha256": file_sha(output_dir / "protocol-before-fit.json"),
        "source_sha256": file_sha(Path(__file__)),
        "uncertainty_calibrated": False,
        "product_ranking_enabled": False,
        "customer_execution": False,
    }
    checkpoint_path = output_dir / "selector.json"
    checkpoint_path.write_text(json_text(checkpoint) + "\n")
    checkpoint_sha = file_sha(checkpoint_path)
    evaluations, predictions = {}, []
    for name in ("calibration", "development_test"):
        indices = split[name]
        begin = time.perf_counter()
        pred = predict_checkpoint(
            checkpoint_path,
            checkpoint_sha,
            [
                rows[i]["chemical_identity"]["canonical_isomeric_smiles"]
                for i in indices
            ],
            target_state,
            endpoint,
        )
        elapsed = time.perf_counter() - begin
        expected = model.predict(x[indices])
        if not np.allclose(pred, expected, atol=1e-12, rtol=1e-12):
            raise ValueError("saved_checkpoint_inference_mismatch")
        evaluations[name] = {
            "mean_baseline": metrics(y[indices], np.full(len(indices), mean), 6.0),
            "morgan_ridge": metrics(y[indices], pred, 6.0),
            "unique_state_mean_baseline": unique_state_metrics(
                [rows[i] for i in indices], y[indices], np.full(len(indices), mean), 6.0
            ),
            "unique_state_morgan_ridge": unique_state_metrics(
                [rows[i] for i in indices], y[indices], pred, 6.0
            ),
            "checkpoint_load_and_feature_and_batch_predict_seconds": elapsed,
        }
        predictions.extend(
            {
                "record_id": rows[i]["record_id"],
                "split": name,
                "observed": float(y[i]),
                "mean_baseline": mean,
                "predicted": float(value),
                "prediction_quantity": checkpoint["prediction_quantity"],
            }
            for i, value in zip(indices, pred)
        )
    (output_dir / "predictions.jsonl").write_text(
        "".join(json_text(value) + "\n" for value in predictions)
    )
    report = {
        **protocol,
        "training_executed": True,
        "checkpoint_sha256": checkpoint_sha,
        "requested_intake_target_rows": intake["requested_target_rows"],
        "requested_model_state_rows": len(ledger),
        "normalized_model_state_rows": normalized_state_rows,
        "model_endpoint_rows": len(rows),
        "excluded_model_state_rows": len(ledger) - len(rows),
        "model_state_exact_endpoint_coverage": len(rows) / len(ledger)
        if ledger
        else 0.0,
        "full_requested_state_recall": None,
        "full_requested_state_recall_unavailable_reason": "excluded_or_missing_or_censored_labels_are_not_assumed_negative; reported_quality_is_within_exact_endpoint_scope",
        "cohort_exclusion_counts": dict(
            Counter(row["reason"] for row in ledger if row["reason"])
        ),
        "split_counts": {name: len(indices) for name, indices in split.items()},
        "component_count": len(set(group_ids)),
        "replicate_weighting": "inverse_count_within_fit_document_assay_isomeric_ligand",
        "fit_effective_group_weight": float(weights.sum()),
        "evaluations": evaluations,
        "cost": {
            "feature_seconds": feature_seconds,
            "fit_seconds": fit_seconds,
            "wall_seconds": time.perf_counter() - wall,
            "cpu_seconds": time.process_time() - cpu,
            "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "scope": "CPU development experiment including input, features, fit, serialized inference; excludes download/intake",
        },
        "engine_speedup_measured": False,
        "docking_recall_measured": False,
        "uncertainty_calibrated": False,
        "scientific_validation": False,
        "customer_execution": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--target-state", required=True)
    parser.add_argument("--endpoint", choices=("Ki", "Kd", "IC50"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260908)
    args = parser.parse_args(argv)
    report = run(
        input_dir=args.input_dir,
        summary_sha256=args.summary_sha256,
        target_state=args.target_state,
        endpoint=args.endpoint,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("training_executed", "split_counts", "evaluations", "cost")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the internal docking surfaces over a frozen public benchmark (P1-8).

The collector freezes case identity, stratification, deposited structures, and
ligand chemistry. This runner turns that immutable input into measured subject
metrics:

- verifies the frozen case-set and deposited PDB hashes before execution;
- removes the native ligand from the receptor input;
- builds one canonical preparation packet per case;
- runs Legacy and V2 at the same candidate budget;
- evaluates every reported pose against the deposited ligand with
  graph/symmetry-aware heavy-atom RMSD;
- counts every frozen case in the denominator, including preparation,
  execution, and evaluation failures;
- emits Top-1/3/5, validity, failure, runtime, subgroup, and bootstrap metrics.

The external Vina/GNINA/Smina paired delta is intentionally not fabricated.
When no operator-supplied offline oracle result exists, the metrics payload
remains fail-closed on that one independent requirement.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_engine.scoring.local_refinement import RefinementParameters  # noqa: E402
from betelgeuze_product.engine_adapters import (  # noqa: E402
    AdapterBudget,
    available_external_oracle_binaries,
    run_engine_v2_adapter,
    run_legacy_adapter,
)
from betelgeuze_product.frozen_benchmark_suite import (  # noqa: E402
    BenchmarkCase,
    FrozenBenchmarkSuite,
    REQUIRED_STRATIFICATION_AXES,
)
from betelgeuze_product.preparation_service import build_preparation_packet  # noqa: E402
from tools.product.collect_public_docking_benchmark_cases import (  # noqa: E402
    COFACTOR_COMP_IDS,
    METAL_COMP_IDS,
)

DEFAULT_CASES_CSV = "config/frozen_public_docking_benchmark_cases_current.csv"
DEFAULT_COLLECTION_RECEIPT = "runs/public_docking_benchmark_case_collection_current.json"
DEFAULT_CACHE_DIR = ".betelgeuze/cache/rcsb_public_docking_benchmark"
DEFAULT_OUT_JSON = "runs/frozen_public_docking_benchmark_execution_current.json"
DEFAULT_OUT_CSV = "runs/frozen_public_docking_benchmark_execution_current.csv"
DEFAULT_OUT_MD = "runs/frozen_public_docking_benchmark_execution_current.md"
DEFAULT_OUT_METRICS = "config/frozen_public_docking_benchmark_metrics_current.json"
DEFAULT_CHECKPOINT = ".betelgeuze/frozen_public_docking_benchmark_execution_checkpoint.jsonl"

SCHEMA_VERSION = "frozen_public_docking_benchmark_execution_v1"
METRICS_SCHEMA_VERSION = "frozen_public_docking_benchmark_subject_metrics_v1"
PRIMARY_ENGINE_SURFACE = "engine_v2"
RMSD_SUCCESS_THRESHOLD_A = 2.0
DEFAULT_BOOTSTRAP_ITERATIONS = 2000
DEFAULT_BOOTSTRAP_SEED = 1729

STATUS_READY = "frozen_public_docking_benchmark_subject_execution_ready"
STATUS_PARTIAL = "partial_frozen_public_docking_benchmark_subject_execution"
STATUS_BLOCKED = "blocked_frozen_public_docking_benchmark_subject_execution"

CLAIM_BOUNDARY = (
    "Frozen public docking benchmark subject execution only. It verifies immutable public inputs, runs the "
    "internal Legacy and V2 surfaces on one canonical preparation packet per case, evaluates deposited-pose "
    "recovery, and counts all selected cases. It does not install or run Vina/GNINA/Smina, invent paired "
    "baseline results, promote a product claim, or mutate external state."
)

AA3_TO_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "MSE": "M",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return [
        {
            "case_id": str(row.get("case_id") or "").strip(),
            "target_id": str(row.get("target_id") or "").strip(),
            "ligand_id": str(row.get("ligand_id") or "").strip(),
            "provenance_id": str(row.get("provenance_id") or "").strip(),
            "strata": {
                axis: str(row.get(axis) or "").strip()
                for axis in REQUIRED_STRATIFICATION_AXES
            },
        }
        for row in rows
    ]


def _case_set_hash(cases: Sequence[dict[str, Any]]) -> str:
    suite = FrozenBenchmarkSuite(
        suite_id="public_docking_benchmark",
        frozen_at_utc="",
        cases=tuple(
            BenchmarkCase(
                case_id=row["case_id"],
                target_id=row["target_id"],
                ligand_id=row["ligand_id"],
                provenance_id=row["provenance_id"],
                strata=dict(row["strata"]),
            )
            for row in cases
        ),
    )
    return suite.case_set_hash


def load_frozen_inputs(
    *,
    cases_csv: str | Path,
    collection_receipt_json: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any], list[str]]:
    """Load and cross-check the immutable case CSV and evidence receipt."""

    blockers: list[str] = []
    cases_path = _resolve(cases_csv)
    receipt_path = _resolve(collection_receipt_json)
    if not cases_path.is_file():
        return [], {}, {}, [f"cases_csv_missing:{cases_path.name}"]
    if not receipt_path.is_file():
        return [], {}, {}, [f"collection_receipt_missing:{receipt_path.name}"]
    try:
        cases = _read_cases(cases_path)
    except (OSError, csv.Error) as exc:
        return [], {}, {}, [f"cases_csv_unreadable:{type(exc).__name__}"]
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return cases, {}, {}, [f"collection_receipt_unreadable:{type(exc).__name__}"]
    if not isinstance(receipt, dict):
        return cases, {}, {}, ["collection_receipt_not_an_object"]

    actual_hash = _case_set_hash(cases)
    summary = receipt.get("summary") or {}
    expected_hash = str(summary.get("case_set_hash") or "")
    if not expected_hash:
        blockers.append("collection_receipt_case_set_hash_missing")
    elif actual_hash != expected_hash:
        blockers.append("collection_receipt_case_set_hash_mismatch")
    if int(summary.get("case_count") or 0) != len(cases):
        blockers.append("collection_receipt_case_count_mismatch")
    if summary.get("frozen_case_set") is not True:
        blockers.append("collection_receipt_not_frozen")
    if not str(summary.get("frozen_at_utc") or ""):
        blockers.append("collection_receipt_frozen_at_utc_missing")

    evidence_by_case: dict[str, dict[str, Any]] = {}
    for item in receipt.get("cases") or []:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "")
        if case_id:
            evidence_by_case[case_id] = dict(item.get("evidence") or {})
    missing_evidence = [row["case_id"] for row in cases if row["case_id"] not in evidence_by_case]
    if missing_evidence:
        blockers.append(f"collection_receipt_case_evidence_missing:{len(missing_evidence)}")
    return cases, evidence_by_case, receipt, list(dict.fromkeys(blockers))


def _is_hydrogen_pdb_line(line: str) -> bool:
    element = line[76:78].strip().upper() if len(line) >= 78 else ""
    atom_name = line[12:16].strip().upper() if len(line) >= 16 else ""
    return element in {"H", "D"} or atom_name.startswith(("H", "D"))


def _pdb_xyz(line: str) -> tuple[float, float, float] | None:
    try:
        return float(line[30:38]), float(line[38:46]), float(line[46:54])
    except (TypeError, ValueError):
        return None


def extract_reference_ligand(pdb_text: str, comp_id: str) -> tuple[dict[str, Any], list[str]]:
    """Select one deterministic deposited ligand instance and its bond block."""

    component = str(comp_id).upper()
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for line in pdb_text.splitlines():
        if not line.startswith("HETATM") or line[17:20].strip().upper() != component:
            continue
        if _is_hydrogen_pdb_line(line):
            continue
        altloc = line[16:17].strip()
        if altloc not in {"", "A"}:
            continue
        xyz = _pdb_xyz(line)
        if xyz is None:
            continue
        key = (line[21:22].strip(), line[22:26].strip(), line[26:27].strip())
        groups[key].append(line)
    if not groups:
        return {}, ["reference_ligand_instance_missing"]

    instance_key, atom_lines = sorted(
        groups.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[0]
    serials = {int(line[6:11]) for line in atom_lines}
    conect_lines: list[str] = []
    for line in pdb_text.splitlines():
        if not line.startswith("CONECT"):
            continue
        fields = [
            int(line[start : start + 5])
            for start in range(6, len(line), 5)
            if line[start : start + 5].strip().isdigit()
        ]
        if not fields or fields[0] not in serials:
            continue
        kept = [serial for serial in fields if serial in serials]
        if len(kept) > 1:
            conect_lines.append("CONECT" + "".join(f"{serial:5d}" for serial in kept))
    if not conect_lines:
        return {}, ["reference_ligand_connectivity_missing"]
    coordinates = [_pdb_xyz(line) for line in atom_lines]
    if any(row is None for row in coordinates):
        return {}, ["reference_ligand_coordinates_invalid"]
    return (
        {
            "comp_id": component,
            "chain_id": instance_key[0],
            "residue_number": instance_key[1],
            "insertion_code": instance_key[2],
            "atom_count": len(atom_lines),
            "atom_names": [line[12:16].strip() for line in atom_lines],
            "elements": [
                (line[76:78].strip() or line[12:16].strip()[:1]).upper()
                for line in atom_lines
            ],
            "coordinates": [list(row) for row in coordinates if row is not None],
            "pdb_block": "\n".join([*atom_lines, *conect_lines, "END", ""]),
        },
        [],
    )


def build_reference_graph(
    reference: dict[str, Any],
    ligand_smiles: str,
) -> tuple[Any | None, list[tuple[int, ...]], list[str]]:
    """Map prepared-SMILES atom order to every deposited symmetry match."""

    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem

    RDLogger.DisableLog("rdApp.*")
    template = Chem.MolFromSmiles(str(ligand_smiles or ""))
    if template is None:
        return None, [], ["reference_template_smiles_invalid"]
    deposited = Chem.MolFromPDBBlock(
        str(reference.get("pdb_block") or ""),
        sanitize=False,
        removeHs=True,
        proximityBonding=False,
    )
    if deposited is None:
        return template, [], ["reference_ligand_pdb_graph_invalid"]
    try:
        assigned = AllChem.AssignBondOrdersFromTemplate(template, deposited)
    except (ValueError, RuntimeError):
        return template, [], ["reference_ligand_bond_order_assignment_failed"]
    matches = list(
        assigned.GetSubstructMatches(
            template,
            uniquify=False,
            useChirality=False,
            maxMatches=100000,
        )
    )
    if not matches:
        return template, [], ["reference_ligand_graph_mapping_missing"]
    if any(len(match) != template.GetNumAtoms() for match in matches):
        return template, [], ["reference_ligand_graph_mapping_incomplete"]
    return template, matches, []


def normalize_heavy_atom_smiles(
    ligand_smiles: str,
) -> tuple[str, dict[str, Any], list[str]]:
    """Remove explicit hydrogen atoms while preserving the deposited heavy graph."""

    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    source = str(ligand_smiles or "").strip()
    molecule = Chem.MolFromSmiles(source)
    if molecule is None:
        return "", {}, ["ligand_smiles_invalid"]
    explicit_hydrogen_count = sum(
        1 for atom in molecule.GetAtoms() if atom.GetAtomicNum() == 1
    )
    if explicit_hydrogen_count == 0:
        return (
            source,
            {
                "method": "identity_no_explicit_hydrogen_atoms",
                "explicit_hydrogen_count_removed": 0,
            },
            [],
        )
    heavy = Chem.RemoveAllHs(molecule)
    normalized = Chem.MolToSmiles(heavy, isomericSmiles=True)
    if not normalized:
        return "", {}, ["ligand_heavy_atom_smiles_normalization_failed"]
    return (
        normalized,
        {
            "method": "rdkit_remove_all_explicit_hydrogens",
            "explicit_hydrogen_count_removed": explicit_hydrogen_count,
            "source_smiles_sha256": _sha256_text(source),
            "normalized_smiles_sha256": _sha256_text(normalized),
        },
        [],
    )


def symmetry_aware_pose_rmsd(
    pose_coordinates: Sequence[Sequence[float]],
    reference_coordinates: Sequence[Sequence[float]],
    matches: Sequence[Sequence[int]],
) -> float | None:
    """RMSD in the receptor frame, minimizing only valid graph symmetries."""

    pose = np.asarray(pose_coordinates, dtype=np.float64).reshape(-1, 3)
    reference = np.asarray(reference_coordinates, dtype=np.float64).reshape(-1, 3)
    if pose.shape[0] == 0 or reference.shape[0] == 0:
        return None
    best: float | None = None
    for match in matches:
        indices = np.asarray(match, dtype=np.int64)
        if len(indices) != pose.shape[0] or np.any(indices < 0) or np.any(indices >= len(reference)):
            continue
        delta = pose - reference[indices]
        value = float(np.sqrt(np.mean(np.sum(delta * delta, axis=1))))
        if best is None or value < best:
            best = value
    return best


def strip_receptor_for_docking(pdb_text: str, ligand_comp_id: str) -> str:
    """Remove the native ligand and solvent while preserving metals/cofactors."""

    ligand = ligand_comp_id.upper()
    removed_serials: set[int] = set()
    kept: list[str] = []
    for line in pdb_text.splitlines():
        if line.startswith("HETATM"):
            comp_id = line[17:20].strip().upper()
            if comp_id == ligand or comp_id not in (METAL_COMP_IDS | COFACTOR_COMP_IDS):
                if line[6:11].strip().isdigit():
                    removed_serials.add(int(line[6:11]))
                continue
        if line.startswith("CONECT"):
            continue
        if line.startswith(("ATOM  ", "HETATM", "TER   ", "MODEL ", "ENDMDL")):
            kept.append(line)
    kept.append("END")
    return "\n".join(kept) + "\n"


def _protein_chains(pdb_text: str) -> dict[str, tuple[str, np.ndarray]]:
    chains: dict[str, list[tuple[tuple[int, str], str, tuple[float, float, float]]]] = defaultdict(
        list
    )
    seen: set[tuple[str, int, str]] = set()
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM  ") or line[12:16].strip() != "CA":
            continue
        altloc = line[16:17].strip()
        if altloc not in {"", "A"}:
            continue
        residue = line[17:20].strip().upper()
        if residue not in AA3_TO_1:
            continue
        try:
            residue_number = int(line[22:26])
        except ValueError:
            continue
        chain = line[21:22].strip()
        insertion = line[26:27].strip()
        identity = (chain, residue_number, insertion)
        xyz = _pdb_xyz(line)
        if identity in seen or xyz is None:
            continue
        seen.add(identity)
        chains[chain].append(((residue_number, insertion), AA3_TO_1[residue], xyz))
    result: dict[str, tuple[str, np.ndarray]] = {}
    for chain, rows in chains.items():
        ordered = sorted(rows, key=lambda row: row[0])
        result[chain] = (
            "".join(row[1] for row in ordered),
            np.asarray([row[2] for row in ordered], dtype=np.float64),
        )
    return result


def align_reference_coordinates(
    source_pdb_text: str,
    receptor_pdb_text: str,
    reference_coordinates: Sequence[Sequence[float]],
) -> tuple[np.ndarray | None, dict[str, Any], list[str]]:
    """Transform a holo-source ligand into an apo receptor coordinate frame."""

    from Bio.Align import PairwiseAligner

    source_chains = _protein_chains(source_pdb_text)
    receptor_chains = _protein_chains(receptor_pdb_text)
    if not source_chains or not receptor_chains:
        return None, {}, ["apo_alignment_protein_chain_missing"]

    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.match_score = 2.0
    aligner.mismatch_score = -1.0
    aligner.open_gap_score = -10.0
    aligner.extend_gap_score = -0.5

    best: tuple[int, int, float, str, str, np.ndarray, np.ndarray] | None = None
    for source_chain, (source_sequence, source_coordinates) in source_chains.items():
        for receptor_chain, (receptor_sequence, receptor_coordinates) in receptor_chains.items():
            alignment = aligner.align(source_sequence, receptor_sequence)[0]
            source_rows: list[np.ndarray] = []
            receptor_rows: list[np.ndarray] = []
            identical = 0
            for (source_start, source_end), (receptor_start, receptor_end) in zip(
                alignment.aligned[0], alignment.aligned[1]
            ):
                length = min(source_end - source_start, receptor_end - receptor_start)
                for offset in range(length):
                    source_index = int(source_start + offset)
                    receptor_index = int(receptor_start + offset)
                    source_rows.append(source_coordinates[source_index])
                    receptor_rows.append(receptor_coordinates[receptor_index])
                    if source_sequence[source_index] == receptor_sequence[receptor_index]:
                        identical += 1
            pair_count = len(source_rows)
            identity = identical / pair_count if pair_count else 0.0
            candidate = (
                identical,
                pair_count,
                identity,
                source_chain,
                receptor_chain,
                np.asarray(source_rows),
                np.asarray(receptor_rows),
            )
            if best is None or candidate[:3] > best[:3]:
                best = candidate
    if best is None or best[1] < 30 or best[2] < 0.70:
        return None, {}, ["apo_alignment_insufficient_sequence_support"]

    _identical, pair_count, identity, source_chain, receptor_chain, source_ca, receptor_ca = best
    inliers = np.ones(pair_count, dtype=bool)
    rotation = np.eye(3, dtype=np.float64)
    translation = np.zeros(3, dtype=np.float64)
    for _iteration in range(6):
        fitted_source = source_ca[inliers]
        fitted_receptor = receptor_ca[inliers]
        source_center = fitted_source.mean(axis=0)
        receptor_center = fitted_receptor.mean(axis=0)
        covariance = (fitted_source - source_center).T @ (
            fitted_receptor - receptor_center
        )
        left, _singular, right_t = np.linalg.svd(covariance)
        rotation = left @ right_t
        if np.linalg.det(rotation) < 0:
            right_t[-1, :] *= -1
            rotation = left @ right_t
        translation = receptor_center - source_center @ rotation
        distances = np.sqrt(
            np.sum((source_ca @ rotation + translation - receptor_ca) ** 2, axis=1)
        )
        threshold = max(2.5, float(np.quantile(distances[inliers], 0.80)))
        updated = distances <= threshold
        if int(updated.sum()) < 30 or np.array_equal(updated, inliers):
            break
        inliers = updated
    aligned_ca = source_ca @ rotation + translation
    ca_rmsd = float(
        np.sqrt(np.mean(np.sum((aligned_ca[inliers] - receptor_ca[inliers]) ** 2, axis=1)))
    )
    if int(inliers.sum()) < 30 or not np.isfinite(ca_rmsd) or ca_rmsd > 2.5:
        return None, {}, ["apo_alignment_ca_rmsd_too_high"]
    transformed = np.asarray(reference_coordinates, dtype=np.float64) @ rotation + translation
    return (
        transformed,
        {
            "method": "local_sequence_alignment_robust_kabsch_ca",
            "source_chain_id": source_chain,
            "receptor_chain_id": receptor_chain,
            "aligned_ca_count": pair_count,
            "inlier_ca_count": int(inliers.sum()),
            "sequence_identity": round(identity, 6),
            "inlier_ca_rmsd_a": round(ca_rmsd, 6),
        },
        [],
    )


def _pdb_path(cache_dir: Path, entry_id: str) -> Path:
    return cache_dir / f"{entry_id.upper()}.pdb"


def _read_verified_pdb(
    *,
    cache_dir: Path,
    entry_id: str,
    expected_sha256: str,
    role: str,
) -> tuple[str, list[str]]:
    path = _pdb_path(cache_dir, entry_id)
    if not path.is_file():
        return "", [f"{role}_pdb_missing:{entry_id.upper()}"]
    text = path.read_text(encoding="utf-8", errors="ignore")
    actual = _sha256_text(text)
    if not expected_sha256:
        return "", [f"{role}_pdb_sha256_missing:{entry_id.upper()}"]
    if actual != expected_sha256:
        return "", [f"{role}_pdb_sha256_mismatch:{entry_id.upper()}"]
    return text, []


def _surface_result(
    bundle: Any,
    *,
    surface_runtime_seconds: float,
    preparation_seconds: float,
    reference_coordinates: Sequence[Sequence[float]],
    symmetry_matches: Sequence[Sequence[int]],
) -> dict[str, Any]:
    payload = bundle.to_dict()
    poses = payload.get("pose_ensemble", {}).get("poses") or []
    rmsds: list[float | None] = []
    for pose in poses:
        coordinates = pose.get("coordinates") or []
        rmsd = symmetry_aware_pose_rmsd(
            coordinates,
            reference_coordinates,
            symmetry_matches,
        )
        rmsds.append(None if rmsd is None else round(rmsd, 6))
        pose["reference_rmsd_a"] = None if rmsd is None else round(rmsd, 6)
    valid_rmsds = [float(value) for value in rmsds if value is not None]
    evaluation_failed = bool(bundle.blockers) or not poses or not valid_rmsds
    payload["evaluation"] = {
        "rmsd_method": "deposited_heavy_atom_graph_symmetry_no_superposition",
        "success_threshold_a": RMSD_SUCCESS_THRESHOLD_A,
        "pose_rmsd_a": rmsds,
        "top1_success": bool(valid_rmsds[:1] and valid_rmsds[0] <= RMSD_SUCCESS_THRESHOLD_A),
        "top3_success": any(
            value <= RMSD_SUCCESS_THRESHOLD_A for value in valid_rmsds[:3]
        ),
        "top5_success": any(
            value <= RMSD_SUCCESS_THRESHOLD_A for value in valid_rmsds[:5]
        ),
        "evaluation_failed": evaluation_failed,
    }
    payload["measured_runtime_seconds"] = {
        "preparation": round(preparation_seconds, 6),
        "surface": round(surface_runtime_seconds, 6),
        "end_to_end": round(preparation_seconds + surface_runtime_seconds, 6),
    }
    return payload


def run_case(
    case: dict[str, Any],
    evidence: dict[str, Any],
    *,
    cache_dir: Path,
    max_conformers: int,
    seed: int,
    candidate_budget: int,
    refinement_max_steps: int,
) -> dict[str, Any]:
    """Run one frozen case, retaining a counted failure on every blocked path."""

    blockers: list[str] = []
    receptor_entry = str(evidence.get("receptor_entry_id") or "").upper()
    ligand_comp_id = str(evidence.get("ligand_comp_id") or "").upper()
    ligand_smiles = str(evidence.get("ligand_smiles") or "")
    if not receptor_entry:
        blockers.append("receptor_entry_id_missing")
    if not ligand_comp_id:
        blockers.append("ligand_comp_id_missing")
    if not ligand_smiles:
        blockers.append("ligand_smiles_missing")
    normalized_smiles, smiles_normalization, normalization_blockers = (
        normalize_heavy_atom_smiles(ligand_smiles)
        if ligand_smiles
        else ("", {}, [])
    )
    blockers.extend(normalization_blockers)
    receptor_text, receptor_blockers = _read_verified_pdb(
        cache_dir=cache_dir,
        entry_id=receptor_entry,
        expected_sha256=str(evidence.get("receptor_pdb_sha256") or ""),
        role="receptor",
    )
    blockers.extend(receptor_blockers)

    source_entry = str(evidence.get("ligand_source_entry_id") or receptor_entry).upper()
    if source_entry == receptor_entry:
        source_text = receptor_text
    else:
        source_text, source_blockers = _read_verified_pdb(
            cache_dir=cache_dir,
            entry_id=source_entry,
            expected_sha256=str(
                evidence.get("ligand_source_receptor_pdb_sha256") or ""
            ),
            role="ligand_source",
        )
        blockers.extend(source_blockers)

    reference: dict[str, Any] = {}
    reference_coordinates: np.ndarray | None = None
    symmetry_matches: list[tuple[int, ...]] = []
    alignment: dict[str, Any] = {
        "method": "identity_holo_receptor_frame",
        "source_entry_id": source_entry,
        "receptor_entry_id": receptor_entry,
    }
    if source_text and ligand_comp_id:
        reference, reference_blockers = extract_reference_ligand(
            source_text, ligand_comp_id
        )
        blockers.extend(reference_blockers)
        if reference:
            reference_coordinates = np.asarray(reference["coordinates"], dtype=np.float64)
            if source_entry != receptor_entry and receptor_text:
                reference_coordinates, alignment_payload, alignment_blockers = (
                    align_reference_coordinates(
                        source_text,
                        receptor_text,
                        reference_coordinates,
                    )
                )
                alignment = {
                    **alignment,
                    **alignment_payload,
                }
                blockers.extend(alignment_blockers)
            _template, symmetry_matches, graph_blockers = build_reference_graph(
                reference, normalized_smiles
            )
            blockers.extend(graph_blockers)

    result: dict[str, Any] = {
        "case_id": case["case_id"],
        "target_id": case["target_id"],
        "ligand_id": case["ligand_id"],
        "strata": dict(case["strata"]),
        "reference": {
            "receptor_entry_id": receptor_entry,
            "ligand_source_entry_id": source_entry,
            "ligand_comp_id": ligand_comp_id,
            "ligand_instance": {
                key: reference.get(key, "")
                for key in ("chain_id", "residue_number", "insertion_code", "atom_count")
            },
            "symmetry_mapping_count": len(symmetry_matches),
            "ligand_smiles_normalization": smiles_normalization,
            "alignment": alignment,
        },
        "preparation": {},
        "surfaces": {},
        "blockers": [],
    }
    if blockers or reference_coordinates is None or not symmetry_matches:
        result["blockers"] = list(dict.fromkeys(blockers or ["reference_evaluation_not_ready"]))
        result["failed"] = True
        return result

    receptor_payload = {
        "pdb_content": strip_receptor_for_docking(receptor_text, ligand_comp_id),
        "target_id": case["target_id"],
    }
    preparation_started = time.perf_counter()
    packet = build_preparation_packet(
        receptor_payload=receptor_payload,
        ligand_smiles=normalized_smiles,
        target_id=case["target_id"],
        ligand_id=case["ligand_id"],
        root=ROOT,
        max_conformers=max_conformers,
        seed=seed,
        ligand_reference_coords=reference_coordinates,
    )
    preparation_seconds = time.perf_counter() - preparation_started
    result["preparation"] = packet.to_dict()

    legacy_budget = AdapterBudget(
        candidate_budget=candidate_budget,
        max_reported_poses=5,
    )
    v2_budget = AdapterBudget(
        candidate_budget=candidate_budget,
        max_reported_poses=5,
        refinement=RefinementParameters(max_steps=refinement_max_steps),
    )
    for surface, runner, budget in (
        ("legacy_product", run_legacy_adapter, legacy_budget),
        ("engine_v2", run_engine_v2_adapter, v2_budget),
    ):
        started = time.perf_counter()
        bundle = runner(
            packet,
            budget=budget,
            benchmark_profile="frozen_public_docking_benchmark_v1",
            claim_scope="restricted_internal",
        )
        elapsed = time.perf_counter() - started
        result["surfaces"][surface] = _surface_result(
            bundle,
            surface_runtime_seconds=elapsed,
            preparation_seconds=preparation_seconds,
            reference_coordinates=reference_coordinates,
            symmetry_matches=symmetry_matches,
        )
    primary = result["surfaces"].get(PRIMARY_ENGINE_SURFACE) or {}
    evaluation = primary.get("evaluation") or {}
    result["failed"] = bool(evaluation.get("evaluation_failed", True))
    result["blockers"] = list(primary.get("blockers") or [])
    return result


def run_case_fail_closed(
    case: dict[str, Any],
    evidence: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Convert an unexpected per-case exception into a counted failure row."""

    try:
        return run_case(case, evidence, **kwargs)
    except Exception as exc:  # noqa: BLE001 - benchmark denominator must survive one bad case
        return {
            "case_id": case.get("case_id", ""),
            "target_id": case.get("target_id", ""),
            "ligand_id": case.get("ligand_id", ""),
            "strata": dict(case.get("strata") or {}),
            "reference": {},
            "preparation": {},
            "surfaces": {},
            "blockers": [f"unhandled_case_execution_error:{type(exc).__name__}"],
            "failed": True,
        }


def _bootstrap_interval(
    values: Sequence[int],
    *,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=np.float64)
    point = float(array.mean()) if len(array) else 0.0
    if not len(array) or iterations <= 0:
        return {
            "metric_id": "top1_rmsd_success_rate_2a",
            "point_estimate": point,
            "ci_low": point,
            "ci_high": point,
            "iterations": int(iterations),
            "seed": int(seed),
        }
    rng = np.random.default_rng(int(seed))
    estimates = np.empty(int(iterations), dtype=np.float64)
    for index in range(int(iterations)):
        sample = rng.choice(array, size=len(array), replace=True)
        estimates[index] = float(sample.mean())
    return {
        "metric_id": "top1_rmsd_success_rate_2a",
        "point_estimate": point,
        "ci_low": float(np.quantile(estimates, 0.025)),
        "ci_high": float(np.quantile(estimates, 0.975)),
        "iterations": int(iterations),
        "seed": int(seed),
    }


def aggregate_subject_metrics(
    case_results: Sequence[dict[str, Any]],
    *,
    candidate_budget: int,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Aggregate the primary surface over the full attempted denominator."""

    attempted = len(case_results)
    top1_values: list[int] = []
    top3_values: list[int] = []
    top5_values: list[int] = []
    geometric_values: list[int] = []
    chemical_values: list[int] = []
    failure_values: list[int] = []
    runtimes: list[float] = []
    rotor_groups: dict[str, list[int]] = defaultdict(list)
    size_groups: dict[str, list[int]] = defaultdict(list)
    for result in case_results:
        primary = (result.get("surfaces") or {}).get(PRIMARY_ENGINE_SURFACE) or {}
        evaluation = primary.get("evaluation") or {}
        failed = bool(result.get("failed", True))
        top1 = int(not failed and evaluation.get("top1_success") is True)
        top3 = int(not failed and evaluation.get("top3_success") is True)
        top5 = int(not failed and evaluation.get("top5_success") is True)
        poses = (primary.get("pose_ensemble") or {}).get("poses") or []
        top_pose = poses[0] if poses else {}
        top1_values.append(top1)
        top3_values.append(top3)
        top5_values.append(top5)
        geometric_values.append(int(not failed and top_pose.get("geometric_valid") is True))
        chemical_values.append(int(not failed and top_pose.get("chemistry_valid") is True))
        failure_values.append(int(failed))
        runtime = (primary.get("measured_runtime_seconds") or {}).get("end_to_end")
        runtimes.append(float(runtime or 0.0))
        strata = result.get("strata") or {}
        rotor_groups[str(strata.get("rotor_count") or "missing")].append(top1)
        size_groups[str(strata.get("ligand_size") or "missing")].append(top1)

    def rate(values: Sequence[int]) -> float:
        return float(sum(values) / attempted) if attempted else 0.0

    def group_rates(groups: dict[str, list[int]]) -> dict[str, float]:
        return {
            key: float(sum(values) / len(values)) if values else 0.0
            for key, values in sorted(groups.items())
        }

    interval = _bootstrap_interval(
        top1_values,
        iterations=bootstrap_iterations,
        seed=bootstrap_seed,
    )
    metrics = {
        "top1_rmsd_success_rate_2a": rate(top1_values),
        "top3_success_rate": rate(top3_values),
        "top5_success_rate": rate(top5_values),
        "geometric_validity_rate": rate(geometric_values),
        "chemical_validity_rate": rate(chemical_values),
        "full_case_failure_rate": rate(failure_values),
        "runtime_seconds_median": float(statistics.median(runtimes)) if runtimes else 0.0,
        "candidate_budget": int(candidate_budget),
        "rotor_subgroup_success": group_rates(rotor_groups),
        "size_subgroup_success": group_rates(size_groups),
        "bootstrap_ci": dict(interval),
        "attempted_case_count": attempted,
    }
    return metrics, interval


def build_execution_packet(
    *,
    cases: Sequence[dict[str, Any]],
    evidence_by_case: dict[str, dict[str, Any]],
    collection_receipt: dict[str, Any],
    cache_dir: Path,
    max_cases: int,
    max_conformers: int,
    seed: int,
    candidate_budget: int,
    refinement_max_steps: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
    checkpoint_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    frozen_case_count = len(cases)
    selected = list(cases[:max_cases]) if max_cases > 0 else list(cases)
    checkpoint_header = {
        "schema_version": "frozen_public_docking_benchmark_checkpoint_v1",
        "runner_sha256": _sha256_text(Path(__file__).read_text(encoding="utf-8")),
        "case_set_hash": str(
            (collection_receipt.get("summary") or {}).get("case_set_hash") or ""
        ),
        "selected_case_ids": [case["case_id"] for case in selected],
        "configuration": {
            "max_conformers": max_conformers,
            "seed": seed,
            "candidate_budget": candidate_budget,
            "refinement_max_steps": refinement_max_steps,
        },
    }
    reused: dict[str, dict[str, Any]] = {}
    if checkpoint_path is not None and checkpoint_path.is_file():
        lines = checkpoint_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise RuntimeError("benchmark_checkpoint_empty")
        stored_header = json.loads(lines[0]).get("checkpoint_header")
        if stored_header != checkpoint_header:
            raise RuntimeError("benchmark_checkpoint_configuration_mismatch")
        for line in lines[1:]:
            payload = json.loads(line)
            result = payload.get("case_result")
            if isinstance(result, dict) and result.get("case_id"):
                reused[str(result["case_id"])] = result
    elif checkpoint_path is not None:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps({"checkpoint_header": checkpoint_header}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    case_results: list[dict[str, Any]] = []
    reused_case_count = 0
    for case in selected:
        cached = reused.get(case["case_id"])
        if cached is not None:
            case_results.append(cached)
            reused_case_count += 1
            continue
        result = run_case_fail_closed(
            case,
            evidence_by_case.get(case["case_id"], {}),
            cache_dir=cache_dir,
            max_conformers=max_conformers,
            seed=seed,
            candidate_budget=candidate_budget,
            refinement_max_steps=refinement_max_steps,
        )
        case_results.append(result)
        if checkpoint_path is not None:
            with checkpoint_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {"case_result": result},
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )
    metrics, interval = aggregate_subject_metrics(
        case_results,
        candidate_budget=candidate_budget,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )
    suite_complete = len(selected) == frozen_case_count
    execution_blockers: list[str] = []
    if not suite_complete:
        execution_blockers.append(
            f"partial_case_selection:{len(selected)}<{frozen_case_count}"
        )
    available_oracles = list(available_external_oracle_binaries())
    benchmark_blockers = [*execution_blockers, "paired_baseline_delta_missing"]
    failed_count = sum(1 for result in case_results if result.get("failed") is True)
    status = STATUS_READY if suite_complete else STATUS_PARTIAL
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "execution_ready": True,
        "suite_complete": suite_complete,
        "benchmark_reportable": False,
        "frozen_at_utc": str(
            (collection_receipt.get("summary") or {}).get("frozen_at_utc") or ""
        ),
        "case_set_hash": str(
            (collection_receipt.get("summary") or {}).get("case_set_hash") or ""
        ),
        "frozen_case_count": frozen_case_count,
        "selected_case_count": len(selected),
        "failed_case_count": failed_count,
        "primary_engine_surface": PRIMARY_ENGINE_SURFACE,
        "executed_engine_surfaces": ["legacy_product", "engine_v2"],
        "candidate_budget": candidate_budget,
        "refinement_max_steps": refinement_max_steps,
        "max_conformers": max_conformers,
        "seed": seed,
        "bootstrap_iterations": bootstrap_iterations,
        "bootstrap_seed": bootstrap_seed,
        "subject_metrics": metrics,
        "subject_metrics_ready": suite_complete,
        "checkpoint_path": (
            ""
            if checkpoint_path is None
            else str(checkpoint_path.relative_to(ROOT))
            if checkpoint_path.is_relative_to(ROOT)
            else str(checkpoint_path)
        ),
        "checkpoint_reused_case_count": reused_case_count,
        "available_external_oracle_binaries": available_oracles,
        "external_oracle_installed_by_runner": False,
        "baseline_executed": False,
        "blocker_count": len(benchmark_blockers),
        "blockers": benchmark_blockers,
        "synthetic_cases_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    packet = {"summary": summary, "cases": case_results}
    metrics_payload: dict[str, Any] | None = None
    if suite_complete:
        metrics_payload = {
            "schema_version": METRICS_SCHEMA_VERSION,
            "frozen_at_utc": summary["frozen_at_utc"],
            "case_set_hash": summary["case_set_hash"],
            "subject_engine_surface": PRIMARY_ENGINE_SURFACE,
            "metrics": metrics,
            "bootstrap_intervals": [interval],
            "paired_baseline_deltas": [],
            "baseline_executed": False,
            "synthetic_metrics_used": False,
            "execution_receipt": DEFAULT_OUT_JSON,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return packet, metrics_payload


def _csv_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in packet.get("cases") or []:
        for surface in ("legacy_product", "engine_v2"):
            result = (case.get("surfaces") or {}).get(surface) or {}
            evaluation = result.get("evaluation") or {}
            runtime = result.get("measured_runtime_seconds") or {}
            rows.append(
                {
                    "case_id": case.get("case_id", ""),
                    "target_id": case.get("target_id", ""),
                    "ligand_id": case.get("ligand_id", ""),
                    "engine_surface": surface,
                    "bundle_status": result.get("status", ""),
                    "failed": case.get("failed", True),
                    "top1_success": evaluation.get("top1_success", False),
                    "top3_success": evaluation.get("top3_success", False),
                    "top5_success": evaluation.get("top5_success", False),
                    "pose_rmsd_a": json.dumps(
                        evaluation.get("pose_rmsd_a") or [], separators=(",", ":")
                    ),
                    "end_to_end_runtime_seconds": runtime.get("end_to_end", ""),
                    "candidate_budget": (result.get("runtime_budget") or {}).get(
                        "candidate_budget", ""
                    ),
                    "blockers": ";".join(
                        [*(case.get("blockers") or []), *(result.get("blockers") or [])]
                    ),
                }
            )
    return rows


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    metrics = summary.get("subject_metrics") or {}
    lines = [
        "# Frozen Public Docking Benchmark Execution (current)",
        "",
        "Generated artifact. Re-run the harness; do not hand-edit.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- case_set_hash: `{summary.get('case_set_hash')}`",
        f"- selected_case_count: `{summary.get('selected_case_count')}` / "
        f"`{summary.get('frozen_case_count')}`",
        f"- failed_case_count: `{summary.get('failed_case_count')}`",
        f"- primary_engine_surface: `{summary.get('primary_engine_surface')}`",
        f"- candidate_budget: `{summary.get('candidate_budget')}`",
        f"- benchmark_reportable: `{summary.get('benchmark_reportable')}`",
        "",
        "## Subject Metrics",
        "",
    ]
    for key in (
        "top1_rmsd_success_rate_2a",
        "top3_success_rate",
        "top5_success_rate",
        "geometric_validity_rate",
        "chemical_validity_rate",
        "full_case_failure_rate",
        "runtime_seconds_median",
        "candidate_budget",
    ):
        lines.append(f"- {key}: `{metrics.get(key)}`")
    lines.extend(["", "## Blockers", ""])
    blockers = summary.get("blockers") or []
    lines.extend(f"- `{blocker}`" for blocker in blockers)
    lines.extend(["", "## Claim Boundary", "", str(summary.get("claim_boundary") or ""), ""])
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    columns = list(materialized[0]) if materialized else ["case_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(materialized)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run internal docking surfaces over a frozen public benchmark."
    )
    parser.add_argument("--cases-csv", default=DEFAULT_CASES_CSV)
    parser.add_argument("--collection-receipt-json", default=DEFAULT_COLLECTION_RECEIPT)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-conformers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--candidate-budget", type=int, default=8)
    parser.add_argument("--refinement-max-steps", type=int, default=24)
    parser.add_argument("--bootstrap-iterations", type=int, default=DEFAULT_BOOTSTRAP_ITERATIONS)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--checkpoint-jsonl", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-metrics-json", default=DEFAULT_OUT_METRICS)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases, evidence_by_case, receipt, blockers = load_frozen_inputs(
        cases_csv=args.cases_csv,
        collection_receipt_json=args.collection_receipt_json,
    )
    if blockers:
        packet = {
            "summary": {
                "schema_version": SCHEMA_VERSION,
                "status": STATUS_BLOCKED,
                "execution_ready": False,
                "suite_complete": False,
                "benchmark_reportable": False,
                "blocker_count": len(blockers),
                "blockers": blockers,
                "claim_boundary": CLAIM_BOUNDARY,
            },
            "cases": [],
        }
        metrics_payload = None
    else:
        packet, metrics_payload = build_execution_packet(
            cases=cases,
            evidence_by_case=evidence_by_case,
            collection_receipt=receipt,
            cache_dir=_resolve(args.cache_dir),
            max_cases=max(int(args.max_cases), 0),
            max_conformers=max(int(args.max_conformers), 1),
            seed=int(args.seed),
            candidate_budget=max(int(args.candidate_budget), 1),
            refinement_max_steps=max(int(args.refinement_max_steps), 1),
            bootstrap_iterations=max(int(args.bootstrap_iterations), 1),
            bootstrap_seed=int(args.bootstrap_seed),
            checkpoint_path=(
                _resolve(args.checkpoint_jsonl)
                if str(args.checkpoint_jsonl or "").strip()
                else None
            ),
        )
    if args.out_json:
        _write_json(_resolve(args.out_json), packet)
    if args.out_csv:
        _write_csv(_resolve(args.out_csv), _csv_rows(packet))
    if args.out_md:
        path = _resolve(args.out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(packet), encoding="utf-8")
    if metrics_payload is not None and args.out_metrics_json:
        _write_json(_resolve(args.out_metrics_json), metrics_payload)
    if not args.quiet:
        print(json.dumps(packet["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if packet["summary"].get("execution_ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

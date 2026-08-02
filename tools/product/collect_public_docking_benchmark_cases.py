#!/usr/bin/env python3
"""Collect real public protein-ligand docking benchmark cases (P1-8 input).

``betelgeuze_product.frozen_benchmark_suite`` requires 100-300 frozen cases,
each labelled on nine stratification axes. ``build_frozen_benchmark_suite_intake``
consumes those rows but deliberately refuses to invent them. This collector is
the missing piece: it pulls the case set from the public RCSB PDB APIs and
derives every stratification label from measured data.

Nothing here is synthesised:

- case identity (entry id, ligand chem-comp id) comes from the RCSB search and
  data APIs;
- ``ligand_size`` / ``rotor_count`` / ``ring_count`` / ``charge_class`` come from
  RDKit on the deposited chemical-component SMILES;
- ``target_family`` comes from the UniProt accession the entry maps to, via an
  explicit curated accession->family table (the accession itself is measured, the
  family name is the curation);
- ``metal_or_cofactor_present`` comes from the entry's other non-polymer
  entities;
- ``apo_or_holo`` is holo for a self-docking case and apo for a cross-docking
  case whose receptor entry has no drug-like ligand;
- ``pocket_polarity`` is computed from the deposited coordinates: the residues
  within a cutoff of the ligand are classified polar/apolar and bucketed;
- ``input_quality`` comes from the deposited resolution.

A case that cannot be labelled from measured data is dropped and reported, not
defaulted, because a defaulted label makes an all-easy suite look stratified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL_URL = "https://data.rcsb.org/graphql"
STRUCTURE_URL = "https://files.rcsb.org/download/{entry_id}.pdb"

DEFAULT_CACHE_DIR = ".betelgeuze/cache/rcsb_public_docking_benchmark"
DEFAULT_OUT_CSV = "config/frozen_public_docking_benchmark_cases_current.csv"
DEFAULT_OUT_RECEIPT = "runs/public_docking_benchmark_case_collection_current.json"
DEFAULT_OUT_MD = "runs/public_docking_benchmark_case_collection_current.md"
FROZEN_CASES_TEMPLATE = "config/frozen_public_docking_benchmark_cases_{case_set_hash}.csv"
FROZEN_RECEIPT_TEMPLATE = "runs/public_docking_benchmark_case_collection_{case_set_hash}.json"
FROZEN_MD_TEMPLATE = "runs/public_docking_benchmark_case_collection_{case_set_hash}.md"
FROZEN_MANIFEST_TEMPLATE = "runs/frozen_public_docking_benchmark_case_set_{case_set_hash}.json"

STATUS_READY = "public_docking_benchmark_case_collection_ready"
STATUS_BLOCKED = "blocked_public_docking_benchmark_case_collection"

CLAIM_BOUNDARY = (
    "Public benchmark case collection only. It reads the public RCSB PDB search/data APIs and deposited "
    "coordinates to produce a frozen case list with measured stratification labels. It does not run docking, "
    "does not compute accuracy metrics, does not run any baseline engine, and does not promote a claim."
)

#: Curated UniProt accession -> target family. The accession attached to an entry
#: is measured from the RCSB API; only the family label is curated here, so the
#: ``target_family`` axis stays interpretable instead of being a raw accession.
TARGET_FAMILY_BY_ACCESSION: dict[str, str] = {
    "P00918": "lyase_carbonic_anhydrase",
    "P00915": "lyase_carbonic_anhydrase",
    "P24941": "kinase_cdk",
    "P11309": "kinase_pim",
    "Q16539": "kinase_mapk",
    "P28482": "kinase_mapk",
    "P00519": "kinase_tyrosine",
    "P00533": "kinase_tyrosine",
    "P35968": "kinase_tyrosine",
    "P00734": "protease_serine",
    "P00760": "protease_serine",
    "P07477": "protease_serine",
    "P56817": "protease_aspartic",
    "P07339": "protease_aspartic",
    "P43235": "protease_cysteine",
    "P07711": "protease_cysteine",
    "P39900": "metalloprotease_mmp",
    "P08254": "metalloprotease_mmp",
    "P14780": "metalloprotease_mmp",
    "P07900": "chaperone_hsp90",
    "P10275": "nuclear_receptor",
    "P37231": "nuclear_receptor",
    "P03372": "nuclear_receptor",
    "P00374": "reductase_dhfr",
    "P0ABQ4": "reductase_dhfr",
    "P09960": "hydrolase_lta4h",
    "P22303": "hydrolase_cholinesterase",
    "P06276": "hydrolase_cholinesterase",
    "P27487": "peptidase_dpp4",
    "P04058": "hydrolase_cholinesterase",
}

#: Non-polymer components that are solvent, cryoprotectant, buffer, or ion, i.e.
#: never the docking subject. Anything on this list cannot become a case ligand.
NON_LIGAND_COMP_IDS = frozenset(
    {
        "HOH", "DOD", "SO4", "PO4", "CL", "BR", "IOD", "NA", "K", "MG", "CA",
        "ZN", "MN", "FE", "FE2", "CU", "CU1", "NI", "CO", "CD", "HG", "AU",
        "PT", "AG", "CS", "RB", "SR", "BA", "LI", "AL", "F", "NO3", "ACT",
        "ACY", "EDO", "GOL", "PEG", "PG4", "PGE", "P6G", "1PE", "2PE", "MPD",
        "DMS", "TRS", "EPE", "MES", "IMD", "FMT", "OXL", "CIT", "FLC", "TAR",
        "MLI", "MLA", "SCN", "AZI", "N3", "NH4", "BME", "DTT", "DTU", "TCE",
        "BCT", "CO3", "NO2", "SIN", "SEP", "TPO", "PTR", "MSE", "UNX", "UNL",
        "ETX", "EOH", "IPA", "ACN", "CCN", "URE", "GLC", "NAG", "BMA", "MAN",
        "FUC", "GAL", "XYP", "SUC", "TLA", "MRD", "BU3", "12P", "15P", "XE",
        "KR", "AR", "HEZ", "OCT", "C8E", "LDA", "LMT", "BOG", "BNG", "D10",
    }
)

#: Cofactor-like components. Their presence is a real structural property that
#: the ``metal_or_cofactor_present`` axis must reflect.
COFACTOR_COMP_IDS = frozenset(
    {
        "HEM", "HEC", "HEA", "SF4", "FES", "FAD", "FMN", "NAD", "NAP", "NAI",
        "NDP", "NADH", "SAM", "SAH", "COA", "ACO", "TPP", "PLP", "B12", "COB",
        "MGD", "PQQ", "BTN", "THF", "MTX", "F43", "GDP", "GTP", "ADP", "ATP",
        "AMP", "ANP", "ACP", "AGS", "GNP", "GSP", "UDP", "UTP", "CTP", "FE2",
    }
)

METAL_COMP_IDS = frozenset(
    {
        "ZN", "MG", "MN", "FE", "FE2", "CA", "CU", "CU1", "NI", "CO", "CD",
        "HG", "AU", "PT", "AG", "NA", "K", "MO", "W", "V", "SR", "BA", "SE4",
    }
)

POLAR_RESIDUES = frozenset(
    {"ARG", "LYS", "ASP", "GLU", "HIS", "ASN", "GLN", "SER", "THR", "TYR", "CYS", "TRP"}
)
APOLAR_RESIDUES = frozenset(
    {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "PRO", "GLY"}
)
STANDARD_RESIDUES = POLAR_RESIDUES | APOLAR_RESIDUES

POCKET_CONTACT_CUTOFF_A = 4.5

#: Stratification bucket edges. Chosen once, before any docking result exists,
#: so the buckets cannot be reshaped to flatter a later number.
LIGAND_SIZE_BUCKETS = (
    ("small_le_18_heavy", 0, 18),
    ("medium_19_28_heavy", 19, 28),
    ("large_29_40_heavy", 29, 40),
    ("very_large_gt_40_heavy", 41, 10**6),
)
ROTOR_BUCKETS = (
    ("rigid_le_2_rotors", 0, 2),
    ("flexible_3_5_rotors", 3, 5),
    ("very_flexible_6_9_rotors", 6, 9),
    ("highly_flexible_ge_10_rotors", 10, 10**6),
)
RING_BUCKETS = (
    ("acyclic_0_rings", 0, 0),
    ("mono_or_bicyclic_1_2_rings", 1, 2),
    ("polycyclic_ge_3_rings", 3, 10**6),
)

MIN_LIGAND_HEAVY_ATOMS = 10
MAX_LIGAND_HEAVY_ATOMS = 60
MIN_LIGAND_MOLECULAR_WEIGHT = 150.0
MAX_LIGAND_MOLECULAR_WEIGHT = 750.0


def _bucket(value: int, buckets: Sequence[tuple[str, int, int]]) -> str:
    for name, low, high in buckets:
        if low <= value <= high:
            return name
    return ""


def _charge_class(formal_charge: int) -> str:
    if formal_charge > 0:
        return "cationic"
    if formal_charge < 0:
        return "anionic"
    return "neutral"


def _input_quality(resolution_a: float | None) -> str:
    if resolution_a is None:
        return ""
    if resolution_a <= 1.8:
        return "high_resolution_le_1p8a"
    if resolution_a <= 2.2:
        return "good_resolution_le_2p2a"
    if resolution_a <= 2.6:
        return "moderate_resolution_le_2p6a"
    return "low_resolution_gt_2p6a"


def _post_json(url: str, payload: dict[str, Any], *, timeout: int, retries: int = 3) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"rcsb_request_failed:{url}:{last_error}")


def _search_entries(
    *,
    accession: str,
    with_ligand: bool,
    max_resolution_a: float,
    rows: int,
    timeout: int,
) -> list[str]:
    """Entries for one UniProt accession, with or without a non-polymer entity."""

    nodes: list[dict[str, Any]] = [
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "exptl.method",
                "operator": "exact_match",
                "value": "X-RAY DIFFRACTION",
            },
        },
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.resolution_combined",
                "operator": "less_or_equal",
                "value": float(max_resolution_a),
            },
        },
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.polymer_entity_count_protein",
                "operator": "equals",
                "value": 1,
            },
        },
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": (
                    "rcsb_polymer_entity_container_identifiers"
                    ".reference_sequence_identifiers.database_accession"
                ),
                "operator": "exact_match",
                "value": accession,
            },
        },
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.nonpolymer_entity_count",
                "operator": "greater_or_equal" if with_ligand else "equals",
                "value": 1 if with_ligand else 0,
            },
        },
    ]
    payload = {
        "query": {"type": "group", "logical_operator": "and", "nodes": nodes},
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": int(rows)},
            "results_verbosity": "compact",
            "sort": [
                {
                    "sort_by": "rcsb_entry_container_identifiers.entry_id",
                    "direction": "asc",
                }
            ],
        },
    }
    try:
        response = _post_json(SEARCH_URL, payload, timeout=timeout)
    except RuntimeError:
        return []
    result_set = response.get("result_set") or []
    return [str(item) for item in result_set if isinstance(item, str)]


_ENTRY_GRAPHQL = """
query EntryBatch($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    rcsb_entry_info { resolution_combined }
    nonpolymer_entities {
      nonpolymer_comp {
        chem_comp { id name formula_weight }
        rcsb_chem_comp_descriptor { SMILES_stereo }
      }
    }
    polymer_entities {
      rcsb_polymer_entity_container_identifiers {
        reference_sequence_identifiers { database_accession database_name }
      }
    }
  }
}
"""


def _fetch_entry_metadata(
    entry_ids: Sequence[str], *, timeout: int, batch_size: int = 40
) -> dict[str, dict[str, Any]]:
    """Measured entry metadata: resolution, non-polymer components, accessions."""

    metadata: dict[str, dict[str, Any]] = {}
    for start in range(0, len(entry_ids), batch_size):
        chunk = [entry_id.upper() for entry_id in entry_ids[start : start + batch_size]]
        response = _post_json(
            GRAPHQL_URL,
            {"query": _ENTRY_GRAPHQL, "variables": {"ids": chunk}},
            timeout=timeout,
        )
        for entry in (response.get("data") or {}).get("entries") or []:
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("rcsb_id") or "").upper()
            if not entry_id:
                continue
            resolutions = (
                (entry.get("rcsb_entry_info") or {}).get("resolution_combined") or []
            )
            components: list[dict[str, Any]] = []
            for nonpolymer in entry.get("nonpolymer_entities") or []:
                comp = ((nonpolymer or {}).get("nonpolymer_comp") or {})
                chem_comp = comp.get("chem_comp") or {}
                descriptor = comp.get("rcsb_chem_comp_descriptor") or {}
                comp_id = str(chem_comp.get("id") or "").upper()
                if not comp_id:
                    continue
                components.append(
                    {
                        "comp_id": comp_id,
                        "name": str(chem_comp.get("name") or ""),
                        "formula_weight": chem_comp.get("formula_weight"),
                        "smiles": str(descriptor.get("SMILES_stereo") or ""),
                    }
                )
            accessions: list[str] = []
            for polymer in entry.get("polymer_entities") or []:
                identifiers = (
                    (polymer or {}).get("rcsb_polymer_entity_container_identifiers") or {}
                )
                for reference in identifiers.get("reference_sequence_identifiers") or []:
                    if str((reference or {}).get("database_name") or "") != "UniProt":
                        continue
                    accession = str((reference or {}).get("database_accession") or "")
                    if accession:
                        accessions.append(accession)
            metadata[entry_id] = {
                "resolution_a": float(resolutions[0]) if resolutions else None,
                "components": components,
                "uniprot_accessions": accessions,
            }
    return metadata


def _download_structure(entry_id: str, *, cache_dir: Path, timeout: int) -> Path | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{entry_id.upper()}.pdb"
    if target.is_file() and target.stat().st_size > 0:
        return target
    url = STRUCTURE_URL.format(entry_id=entry_id.upper())
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"Accept": "chemical/x-pdb"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            if not payload:
                return None
            target.write_bytes(payload)
            return target
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1.0 + attempt)
    return None


@dataclass
class PocketPolarity:
    """Pocket polarity measured from deposited coordinates."""

    bucket: str
    polar_residue_count: int
    apolar_residue_count: int
    contact_residue_count: int
    ligand_atom_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "polar_residue_count": self.polar_residue_count,
            "apolar_residue_count": self.apolar_residue_count,
            "contact_residue_count": self.contact_residue_count,
            "ligand_atom_count": self.ligand_atom_count,
            "contact_cutoff_a": POCKET_CONTACT_CUTOFF_A,
        }


def measure_pocket_polarity(
    pdb_text: str, ligand_comp_id: str, *, cutoff_a: float = POCKET_CONTACT_CUTOFF_A
) -> PocketPolarity | None:
    """Classify the residues contacting the ligand as polar or apolar.

    Returns ``None`` when the ligand or a contact shell cannot be found, so the
    caller drops the case rather than labelling the axis by default.
    """

    ligand_atoms: list[tuple[float, float, float]] = []
    protein_atoms: list[tuple[str, str, tuple[float, float, float]]] = []
    comp_id = ligand_comp_id.upper()
    for line in pdb_text.splitlines():
        record = line[:6]
        if record not in ("ATOM  ", "HETATM"):
            continue
        residue_name = line[17:20].strip().upper()
        element = line[76:78].strip().upper()
        if element == "H" or line[12:16].strip().startswith("H"):
            continue
        try:
            coordinate = (
                float(line[30:38]),
                float(line[38:46]),
                float(line[46:54]),
            )
        except ValueError:
            continue
        if record == "HETATM" and residue_name == comp_id:
            ligand_atoms.append(coordinate)
        elif record == "ATOM  " and residue_name in STANDARD_RESIDUES:
            residue_key = f"{line[20:22].strip()}:{line[22:27].strip()}"
            protein_atoms.append((residue_name, residue_key, coordinate))
    if not ligand_atoms or not protein_atoms:
        return None

    cutoff_squared = float(cutoff_a) ** 2
    contact_residues: dict[str, str] = {}
    for residue_name, residue_key, (px, py, pz) in protein_atoms:
        for lx, ly, lz in ligand_atoms:
            if (px - lx) ** 2 + (py - ly) ** 2 + (pz - lz) ** 2 <= cutoff_squared:
                contact_residues[f"{residue_key}:{residue_name}"] = residue_name
                break
    if not contact_residues:
        return None
    polar = sum(1 for name in contact_residues.values() if name in POLAR_RESIDUES)
    apolar = sum(1 for name in contact_residues.values() if name in APOLAR_RESIDUES)
    total = polar + apolar
    if total == 0:
        return None
    polar_fraction = polar / total
    if polar_fraction >= 0.60:
        bucket = "polar_pocket_ge_0p60"
    elif polar_fraction >= 0.40:
        bucket = "mixed_pocket_0p40_0p60"
    else:
        bucket = "apolar_pocket_lt_0p40"
    return PocketPolarity(
        bucket=bucket,
        polar_residue_count=polar,
        apolar_residue_count=apolar,
        contact_residue_count=len(contact_residues),
        ligand_atom_count=len(ligand_atoms),
    )


@dataclass
class LigandChemistry:
    """RDKit-measured ligand descriptors used for stratification."""

    heavy_atom_count: int
    rotor_count: int
    ring_count: int
    formal_charge: int
    molecular_weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "heavy_atom_count": self.heavy_atom_count,
            "rotor_count": self.rotor_count,
            "ring_count": self.ring_count,
            "formal_charge": self.formal_charge,
            "molecular_weight": round(self.molecular_weight, 3),
        }


def measure_ligand_chemistry(smiles: str) -> LigandChemistry | None:
    """Descriptors from the deposited SMILES; ``None`` when RDKit rejects it."""

    if not smiles.strip():
        return None
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors, rdMolDescriptors

    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    heavy = mol.GetNumHeavyAtoms()
    if heavy <= 0:
        return None
    return LigandChemistry(
        heavy_atom_count=int(heavy),
        rotor_count=int(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        ring_count=int(rdMolDescriptors.CalcNumRings(mol)),
        formal_charge=int(Chem.GetFormalCharge(mol)),
        molecular_weight=float(Descriptors.MolWt(mol)),
    )


def _is_candidate_ligand(component: dict[str, Any]) -> bool:
    comp_id = str(component.get("comp_id") or "").upper()
    if not comp_id or comp_id in NON_LIGAND_COMP_IDS or comp_id in COFACTOR_COMP_IDS:
        return False
    weight = component.get("formula_weight")
    if weight is None:
        return False
    try:
        weight_value = float(weight)
    except (TypeError, ValueError):
        return False
    return MIN_LIGAND_MOLECULAR_WEIGHT <= weight_value <= MAX_LIGAND_MOLECULAR_WEIGHT


def _metal_or_cofactor_label(components: Sequence[dict[str, Any]], ligand_comp_id: str) -> str:
    others = [
        str(component.get("comp_id") or "").upper()
        for component in components
        if str(component.get("comp_id") or "").upper() != ligand_comp_id.upper()
    ]
    has_metal = any(comp_id in METAL_COMP_IDS for comp_id in others)
    has_cofactor = any(comp_id in COFACTOR_COMP_IDS for comp_id in others)
    if has_metal and has_cofactor:
        return "metal_and_cofactor_present"
    if has_metal:
        return "metal_present"
    if has_cofactor:
        return "cofactor_present"
    return "absent"


@dataclass
class CollectedCase:
    case_id: str
    target_id: str
    ligand_id: str
    provenance_id: str
    strata: dict[str, str]
    evidence: dict[str, Any] = field(default_factory=dict)

    def csv_row(self) -> dict[str, str]:
        row = {
            "case_id": self.case_id,
            "target_id": self.target_id,
            "ligand_id": self.ligand_id,
            "provenance_id": self.provenance_id,
        }
        row.update(self.strata)
        return row


def _structure_evidence(entry_id: str, pdb_text: str) -> dict[str, str]:
    normalized_entry_id = entry_id.upper()
    return {
        "receptor_structure_url": STRUCTURE_URL.format(entry_id=normalized_entry_id),
        "receptor_pdb_sha256": hashlib.sha256(pdb_text.encode("utf-8")).hexdigest(),
    }


def _case_set_hash(cases: Sequence[CollectedCase]) -> str:
    """Use the frozen-suite contract's canonical case-set hash."""

    from betelgeuze_product.frozen_benchmark_suite import BenchmarkCase, FrozenBenchmarkSuite

    suite = FrozenBenchmarkSuite(
        suite_id="public_docking_benchmark_case_collection",
        frozen_at_utc="",
        cases=tuple(
            BenchmarkCase(
                case_id=case.case_id,
                target_id=case.target_id,
                ligand_id=case.ligand_id,
                provenance_id=case.provenance_id,
                strata=dict(case.strata),
            )
            for case in cases
        ),
    )
    return suite.case_set_hash


def _select_ligand(
    components: Sequence[dict[str, Any]]
) -> tuple[dict[str, Any] | None, LigandChemistry | None]:
    """Pick the largest drug-like component: the docking subject of the entry."""

    best: tuple[dict[str, Any], LigandChemistry] | None = None
    for component in components:
        if not _is_candidate_ligand(component):
            continue
        chemistry = measure_ligand_chemistry(str(component.get("smiles") or ""))
        if chemistry is None:
            continue
        if not (
            MIN_LIGAND_HEAVY_ATOMS
            <= chemistry.heavy_atom_count
            <= MAX_LIGAND_HEAVY_ATOMS
        ):
            continue
        if best is None or chemistry.heavy_atom_count > best[1].heavy_atom_count:
            best = (component, chemistry)
    if best is None:
        return None, None
    return best[0], best[1]


def build_cases_from_metadata(
    *,
    accession_holo_entries: dict[str, Sequence[str]],
    accession_apo_entries: dict[str, Sequence[str]],
    metadata: dict[str, dict[str, Any]],
    structure_loader,
    max_cases: int,
    per_accession_holo_limit: int,
    per_accession_apo_limit: int,
) -> tuple[list[CollectedCase], list[dict[str, Any]]]:
    """Assemble cases from already-fetched metadata. No network access here.

    ``structure_loader(entry_id)`` returns deposited PDB text or ``None``. Every
    stratification label is derived from that measured data; a case that cannot
    be fully labelled is dropped with a reason instead of being defaulted.
    """

    cases: list[CollectedCase] = []
    dropped: list[dict[str, Any]] = []
    used_ligand_comp_ids: set[str] = set()
    holo_by_accession: dict[str, list[CollectedCase]] = defaultdict(list)

    def _drop(entry_id: str, accession: str, reason: str) -> None:
        dropped.append({"entry_id": entry_id, "uniprot_accession": accession, "reason": reason})

    for accession in sorted(accession_holo_entries):
        family = TARGET_FAMILY_BY_ACCESSION.get(accession, "")
        if not family:
            _drop("", accession, "target_family_not_curated_for_accession")
            continue
        accepted_for_accession = 0
        for entry_id in sorted(accession_holo_entries[accession]):
            if len(cases) >= max_cases:
                break
            if accepted_for_accession >= per_accession_holo_limit:
                break
            entry = metadata.get(entry_id.upper())
            if entry is None:
                _drop(entry_id, accession, "entry_metadata_unavailable")
                continue
            resolution_a = entry.get("resolution_a")
            quality = _input_quality(resolution_a)
            if not quality:
                _drop(entry_id, accession, "resolution_missing")
                continue
            components = entry.get("components") or []
            component, chemistry = _select_ligand(components)
            if component is None or chemistry is None:
                _drop(entry_id, accession, "no_drug_like_ligand_component")
                continue
            comp_id = str(component["comp_id"]).upper()
            if comp_id in used_ligand_comp_ids:
                _drop(entry_id, accession, f"duplicate_ligand_component:{comp_id}")
                continue
            pdb_text = structure_loader(entry_id)
            if not pdb_text:
                _drop(entry_id, accession, "structure_download_unavailable")
                continue
            polarity = measure_pocket_polarity(pdb_text, comp_id)
            if polarity is None:
                _drop(entry_id, accession, "pocket_contact_shell_not_measurable")
                continue
            size_bucket = _bucket(chemistry.heavy_atom_count, LIGAND_SIZE_BUCKETS)
            rotor_bucket = _bucket(chemistry.rotor_count, ROTOR_BUCKETS)
            ring_bucket = _bucket(chemistry.ring_count, RING_BUCKETS)
            if not (size_bucket and rotor_bucket and ring_bucket):
                _drop(entry_id, accession, "ligand_descriptor_out_of_bucket_range")
                continue
            case = CollectedCase(
                case_id=f"pdb_{entry_id.upper()}_{comp_id}_holo",
                target_id=f"pdb:{entry_id.upper()}",
                ligand_id=f"ccd:{comp_id}",
                provenance_id=f"rcsb_pdb_entry:{entry_id.upper()}#ligand={comp_id}",
                strata={
                    "ligand_size": size_bucket,
                    "rotor_count": rotor_bucket,
                    "ring_count": ring_bucket,
                    "target_family": family,
                    "pocket_polarity": polarity.bucket,
                    "charge_class": _charge_class(chemistry.formal_charge),
                    "metal_or_cofactor_present": _metal_or_cofactor_label(components, comp_id),
                    "apo_or_holo": "holo_self_docking",
                    "input_quality": quality,
                },
                evidence={
                    "receptor_entry_id": entry_id.upper(),
                    **_structure_evidence(entry_id, pdb_text),
                    "ligand_comp_id": comp_id,
                    "ligand_name": str(component.get("name") or ""),
                    "ligand_smiles": str(component.get("smiles") or ""),
                    "uniprot_accession": accession,
                    "resolution_a": resolution_a,
                    "ligand_chemistry": chemistry.to_dict(),
                    "pocket_polarity": polarity.to_dict(),
                    "pocket_polarity_measured_on": entry_id.upper(),
                    "non_polymer_comp_ids": [
                        str(item.get("comp_id") or "") for item in components
                    ],
                },
            )
            cases.append(case)
            holo_by_accession[accession].append(case)
            used_ligand_comp_ids.add(comp_id)
            accepted_for_accession += 1

    # Cross-docking (apo) cases: an unliganded receptor entry for the same
    # accession, paired with a ligand measured on a holo entry of that target.
    for accession in sorted(accession_apo_entries):
        family = TARGET_FAMILY_BY_ACCESSION.get(accession, "")
        donors = holo_by_accession.get(accession) or []
        if not family or not donors:
            continue
        accepted_for_accession = 0
        for entry_id in sorted(accession_apo_entries[accession]):
            if len(cases) >= max_cases:
                break
            if accepted_for_accession >= per_accession_apo_limit:
                break
            entry = metadata.get(entry_id.upper())
            if entry is None:
                _drop(entry_id, accession, "entry_metadata_unavailable")
                continue
            quality = _input_quality(entry.get("resolution_a"))
            if not quality:
                _drop(entry_id, accession, "resolution_missing")
                continue
            pdb_text = structure_loader(entry_id)
            if not pdb_text:
                _drop(entry_id, accession, "structure_download_unavailable")
                continue
            donor = donors[accepted_for_accession % len(donors)]
            comp_id = str(donor.evidence["ligand_comp_id"]).upper()
            case_id = f"pdb_{entry_id.upper()}_{comp_id}_apo"
            if any(existing.case_id == case_id for existing in cases):
                _drop(entry_id, accession, f"duplicate_case_id:{case_id}")
                continue
            strata = dict(donor.strata)
            strata["apo_or_holo"] = "apo_cross_docking"
            strata["input_quality"] = quality
            strata["metal_or_cofactor_present"] = _metal_or_cofactor_label(
                entry.get("components") or [], comp_id
            )
            cases.append(
                CollectedCase(
                    case_id=case_id,
                    target_id=f"pdb:{entry_id.upper()}",
                    ligand_id=f"ccd:{comp_id}",
                    provenance_id=(
                        f"rcsb_pdb_entry:{entry_id.upper()}#ligand={comp_id}"
                        f"#ligand_source_entry={donor.evidence['receptor_entry_id']}"
                    ),
                    strata=strata,
                    evidence={
                        "receptor_entry_id": entry_id.upper(),
                        **_structure_evidence(entry_id, pdb_text),
                        "ligand_comp_id": comp_id,
                        "ligand_name": donor.evidence.get("ligand_name", ""),
                        "ligand_smiles": donor.evidence.get("ligand_smiles", ""),
                        "uniprot_accession": accession,
                        "resolution_a": entry.get("resolution_a"),
                        "ligand_chemistry": donor.evidence.get("ligand_chemistry", {}),
                        "pocket_polarity": donor.evidence.get("pocket_polarity", {}),
                        "pocket_polarity_measured_on": donor.evidence["receptor_entry_id"],
                        "ligand_source_entry_id": donor.evidence["receptor_entry_id"],
                        "ligand_source_receptor_structure_url": donor.evidence.get(
                            "receptor_structure_url", ""
                        ),
                        "ligand_source_receptor_pdb_sha256": donor.evidence.get(
                            "receptor_pdb_sha256", ""
                        ),
                        "non_polymer_comp_ids": [
                            str(item.get("comp_id") or "")
                            for item in (entry.get("components") or [])
                        ],
                    },
                )
            )
            accepted_for_accession += 1

    cases.sort(key=lambda case: case.case_id)
    return cases, dropped


def stratification_coverage(cases: Sequence[CollectedCase]) -> dict[str, list[str]]:
    from betelgeuze_product.frozen_benchmark_suite import REQUIRED_STRATIFICATION_AXES

    coverage: dict[str, set[str]] = {axis: set() for axis in REQUIRED_STRATIFICATION_AXES}
    for case in cases:
        for axis in REQUIRED_STRATIFICATION_AXES:
            value = str(case.strata.get(axis) or "").strip()
            if value:
                coverage[axis].add(value)
    return {axis: sorted(values) for axis, values in coverage.items()}


def collection_blockers(cases: Sequence[CollectedCase]) -> list[str]:
    """Fail-closed reasons the collected list is not usable as a frozen suite."""

    from betelgeuze_product.frozen_benchmark_suite import (
        MAX_FROZEN_CASE_COUNT,
        MIN_FROZEN_CASE_COUNT,
        REQUIRED_STRATIFICATION_AXES,
    )

    blockers: list[str] = []
    if len(cases) < MIN_FROZEN_CASE_COUNT:
        blockers.append(f"case_count_below_minimum:{len(cases)}<{MIN_FROZEN_CASE_COUNT}")
    if len(cases) > MAX_FROZEN_CASE_COUNT:
        blockers.append(f"case_count_above_maximum:{len(cases)}>{MAX_FROZEN_CASE_COUNT}")
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        blockers.append("duplicate_case_id")
    coverage = stratification_coverage(cases)
    for axis in REQUIRED_STRATIFICATION_AXES:
        buckets = coverage.get(axis) or []
        if not buckets:
            blockers.append(f"stratification_axis_unpopulated:{axis}")
        elif len(buckets) < 2:
            blockers.append(f"stratification_axis_single_bucket:{axis}")
    incomplete = [
        case.case_id
        for case in cases
        if any(not str(case.strata.get(axis) or "").strip() for axis in REQUIRED_STRATIFICATION_AXES)
    ]
    if incomplete:
        blockers.append(f"cases_missing_stratification_labels:{len(incomplete)}")
    return list(dict.fromkeys(blockers))


def build_collection_packet(
    cases: Sequence[CollectedCase], dropped: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    from betelgeuze_product.frozen_benchmark_suite import (
        MAX_FROZEN_CASE_COUNT,
        MIN_FROZEN_CASE_COUNT,
        REQUIRED_STRATIFICATION_AXES,
    )

    blockers = collection_blockers(cases)
    coverage = stratification_coverage(cases)
    bucket_counts: dict[str, dict[str, int]] = {}
    for axis in REQUIRED_STRATIFICATION_AXES:
        counts: dict[str, int] = defaultdict(int)
        for case in cases:
            value = str(case.strata.get(axis) or "").strip()
            if value:
                counts[value] += 1
        bucket_counts[axis] = dict(sorted(counts.items()))
    drop_reason_counts: dict[str, int] = defaultdict(int)
    for record in dropped:
        reason = str(record.get("reason") or "").split(":", 1)[0]
        drop_reason_counts[reason] += 1
    summary = {
        "schema_version": "public_docking_benchmark_case_collection_v2",
        "status": STATUS_BLOCKED if blockers else STATUS_READY,
        "ready": not blockers,
        "case_count": len(cases),
        "case_set_hash": _case_set_hash(cases),
        "case_count_required_min": MIN_FROZEN_CASE_COUNT,
        "case_count_required_max": MAX_FROZEN_CASE_COUNT,
        "target_family_count": len({case.strata.get("target_family", "") for case in cases}),
        "distinct_receptor_entry_count": len(
            {case.evidence.get("receptor_entry_id", "") for case in cases}
        ),
        "distinct_ligand_component_count": len(
            {case.evidence.get("ligand_comp_id", "") for case in cases}
        ),
        "stratification_coverage": coverage,
        "stratification_bucket_counts": bucket_counts,
        "dropped_candidate_count": len(dropped),
        "dropped_reason_counts": dict(sorted(drop_reason_counts.items())),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "pocket_contact_cutoff_a": POCKET_CONTACT_CUTOFF_A,
        "docking_executed": False,
        "metrics_computed": False,
        "baseline_executed": False,
        "external_state_mutated": False,
        "synthetic_cases_used": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "cases": [
            {
                "case_id": case.case_id,
                "target_id": case.target_id,
                "ligand_id": case.ligand_id,
                "provenance_id": case.provenance_id,
                "strata": dict(sorted(case.strata.items())),
                "evidence": case.evidence,
            }
            for case in cases
        ],
        "dropped_candidates": list(dropped),
    }


def render_markdown(packet: dict[str, Any]) -> str:
    from betelgeuze_product.frozen_benchmark_suite import REQUIRED_STRATIFICATION_AXES

    summary = packet.get("summary", {})
    lines = [
        "# Public Docking Benchmark Case Collection (current)",
        "",
        "Generated packet. Regenerate with the collector; do not hand-edit.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- case_count: `{summary.get('case_count')}` "
        f"(required `{summary.get('case_count_required_min')}`-"
        f"`{summary.get('case_count_required_max')}`)",
        f"- case_set_hash: `{summary.get('case_set_hash')}`",
        f"- frozen_case_set: `{bool(summary.get('frozen_case_set', False))}`",
        f"- frozen_at_utc: `{summary.get('frozen_at_utc', '')}`",
        f"- target_family_count: `{summary.get('target_family_count')}`",
        f"- distinct_receptor_entry_count: `{summary.get('distinct_receptor_entry_count')}`",
        f"- distinct_ligand_component_count: `{summary.get('distinct_ligand_component_count')}`",
        f"- dropped_candidate_count: `{summary.get('dropped_candidate_count')}`",
        f"- blocker_count: `{summary.get('blocker_count')}`",
        "",
        "## Stratification Buckets",
        "",
    ]
    bucket_counts = summary.get("stratification_bucket_counts") or {}
    for axis in REQUIRED_STRATIFICATION_AXES:
        counts = bucket_counts.get(axis) or {}
        rendered = ", ".join(f"{name}={count}" for name, count in counts.items()) or "none"
        lines.append(f"- {axis}: `{len(counts)}` bucket(s) ({rendered})")
    lines.extend(["", "## Dropped Candidate Reasons", ""])
    reasons = summary.get("dropped_reason_counts") or {}
    if reasons:
        lines.extend(f"- `{reason}`: `{count}`" for reason, count in reasons.items())
    else:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    blockers = summary.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", str(summary.get("claim_boundary", "")), ""])
    return "\n".join(lines)


def render_cases_csv(cases: Sequence[CollectedCase]) -> str:
    from betelgeuze_product.frozen_benchmark_suite import REQUIRED_STRATIFICATION_AXES

    columns = [
        "case_id",
        "target_id",
        "ligand_id",
        "provenance_id",
        *REQUIRED_STRATIFICATION_AXES,
    ]
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for case in cases:
        writer.writerow({key: case.csv_row().get(key, "") for key in columns})
    return handle.getvalue()


def write_cases_csv(path: Path, cases: Sequence[CollectedCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_cases_csv(cases), encoding="utf-8")


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write_immutable_text(path: Path, content: str) -> None:
    """Create a content-addressed artifact, refusing an in-place mutation."""

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise RuntimeError(f"immutable_snapshot_conflict:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def freeze_case_set(
    cases: Sequence[CollectedCase],
    packet: dict[str, Any],
    *,
    output_root: Path = ROOT,
    frozen_at_utc: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist an immutable, content-addressed case-set snapshot.

    A repeated freeze of the same case-set hash verifies and reuses the original
    timestamp and files. A content mismatch at any content-addressed path fails
    closed instead of silently replacing the frozen benchmark.
    """

    case_set_hash = str(packet.get("summary", {}).get("case_set_hash") or "")
    if len(case_set_hash) != 64:
        raise RuntimeError("case_set_hash_missing_or_invalid")
    if case_set_hash != _case_set_hash(cases):
        raise RuntimeError("case_set_hash_mismatch")

    relative_cases = Path(FROZEN_CASES_TEMPLATE.format(case_set_hash=case_set_hash))
    relative_receipt = Path(FROZEN_RECEIPT_TEMPLATE.format(case_set_hash=case_set_hash))
    relative_md = Path(FROZEN_MD_TEMPLATE.format(case_set_hash=case_set_hash))
    relative_manifest = Path(FROZEN_MANIFEST_TEMPLATE.format(case_set_hash=case_set_hash))
    cases_path = output_root / relative_cases
    receipt_path = output_root / relative_receipt
    markdown_path = output_root / relative_md
    manifest_path = output_root / relative_manifest

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_files = {
            cases_path: str(manifest.get("cases_csv_sha256") or ""),
            receipt_path: str(manifest.get("collection_receipt_json_sha256") or ""),
            markdown_path: str(manifest.get("collection_receipt_md_sha256") or ""),
        }
        for artifact_path, expected_hash in expected_files.items():
            if not artifact_path.is_file():
                raise RuntimeError(f"frozen_snapshot_artifact_missing:{artifact_path}")
            actual_hash = _sha256_text(artifact_path.read_text(encoding="utf-8"))
            if not expected_hash or actual_hash != expected_hash:
                raise RuntimeError(f"frozen_snapshot_artifact_hash_mismatch:{artifact_path}")
        frozen_packet = json.loads(receipt_path.read_text(encoding="utf-8"))
        if frozen_packet.get("summary", {}).get("case_set_hash") != case_set_hash:
            raise RuntimeError("frozen_snapshot_receipt_case_set_hash_mismatch")
        return frozen_packet, manifest

    timestamp = frozen_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    frozen_packet = json.loads(json.dumps(packet))
    frozen_packet["summary"]["frozen_case_set"] = True
    frozen_packet["summary"]["frozen_at_utc"] = timestamp
    frozen_packet["summary"]["frozen_snapshot_id"] = case_set_hash
    frozen_packet["summary"]["frozen_cases_csv"] = relative_cases.as_posix()
    frozen_packet["summary"]["frozen_manifest"] = relative_manifest.as_posix()

    cases_content = render_cases_csv(cases)
    receipt_content = (
        json.dumps(frozen_packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    markdown_content = render_markdown(frozen_packet)
    manifest = {
        "schema_version": "frozen_public_docking_benchmark_case_set_manifest_v1",
        "status": "frozen_public_docking_benchmark_case_set_ready",
        "ready": True,
        "suite_id": "public_docking_benchmark",
        "frozen_at_utc": timestamp,
        "case_set_hash": case_set_hash,
        "case_count": len(cases),
        "cases_csv": relative_cases.as_posix(),
        "cases_csv_sha256": _sha256_text(cases_content),
        "collection_receipt_json": relative_receipt.as_posix(),
        "collection_receipt_json_sha256": _sha256_text(receipt_content),
        "collection_receipt_md": relative_md.as_posix(),
        "collection_receipt_md_sha256": _sha256_text(markdown_content),
        "immutable": True,
        "synthetic_cases_used": False,
        "metrics_computed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    manifest_content = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    _write_immutable_text(cases_path, cases_content)
    _write_immutable_text(receipt_path, receipt_content)
    _write_immutable_text(markdown_path, markdown_content)
    _write_immutable_text(manifest_path, manifest_content)
    return frozen_packet, manifest


def collect_cases(
    *,
    accessions: Sequence[str],
    max_resolution_a: float,
    holo_search_rows: int,
    apo_search_rows: int,
    per_accession_holo_limit: int,
    per_accession_apo_limit: int,
    max_cases: int,
    cache_dir: Path,
    timeout_seconds: int,
) -> tuple[list[CollectedCase], list[dict[str, Any]]]:
    """Network path: search, fetch metadata and coordinates, then assemble."""

    holo: dict[str, Sequence[str]] = {}
    apo: dict[str, Sequence[str]] = {}
    for accession in accessions:
        holo[accession] = _search_entries(
            accession=accession,
            with_ligand=True,
            max_resolution_a=max_resolution_a,
            rows=holo_search_rows,
            timeout=timeout_seconds,
        )
        if apo_search_rows > 0:
            apo[accession] = _search_entries(
                accession=accession,
                with_ligand=False,
                max_resolution_a=max_resolution_a,
                rows=apo_search_rows,
                timeout=timeout_seconds,
            )
    entry_ids = sorted(
        {entry_id for ids in holo.values() for entry_id in ids}
        | {entry_id for ids in apo.values() for entry_id in ids}
    )
    metadata = _fetch_entry_metadata(entry_ids, timeout=timeout_seconds) if entry_ids else {}

    def structure_loader(entry_id: str) -> str | None:
        path = _download_structure(entry_id, cache_dir=cache_dir, timeout=timeout_seconds)
        if path is None:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")

    return build_cases_from_metadata(
        accession_holo_entries=holo,
        accession_apo_entries=apo,
        metadata=metadata,
        structure_loader=structure_loader,
        max_cases=max_cases,
        per_accession_holo_limit=per_accession_holo_limit,
        per_accession_apo_limit=per_accession_apo_limit,
    )


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect real public protein-ligand docking benchmark cases from RCSB PDB."
    )
    parser.add_argument("--accessions", default="", help="Comma-separated UniProt accessions.")
    parser.add_argument("--max-resolution-a", type=float, default=2.5)
    parser.add_argument("--holo-search-rows", type=int, default=40)
    parser.add_argument("--apo-search-rows", type=int, default=6)
    parser.add_argument("--per-accession-holo-limit", type=int, default=8)
    parser.add_argument("--per-accession-apo-limit", type=int, default=2)
    parser.add_argument("--max-cases", type=int, default=300)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--out-cases-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-receipt-json", default=DEFAULT_OUT_RECEIPT)
    parser.add_argument("--out-receipt-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--freeze-case-set",
        action="store_true",
        help="Write and verify immutable content-addressed case-set artifacts.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    accessions = [
        item.strip()
        for item in str(args.accessions or "").split(",")
        if item.strip()
    ] or sorted(TARGET_FAMILY_BY_ACCESSION)
    cases, dropped = collect_cases(
        accessions=accessions,
        max_resolution_a=args.max_resolution_a,
        holo_search_rows=args.holo_search_rows,
        apo_search_rows=args.apo_search_rows,
        per_accession_holo_limit=args.per_accession_holo_limit,
        per_accession_apo_limit=args.per_accession_apo_limit,
        max_cases=args.max_cases,
        cache_dir=_resolve(args.cache_dir),
        timeout_seconds=args.timeout_seconds,
    )
    packet = build_collection_packet(cases, dropped)
    if args.freeze_case_set:
        packet, _ = freeze_case_set(cases, packet)
    if args.out_cases_csv:
        write_cases_csv(_resolve(args.out_cases_csv), cases)
    if args.out_receipt_json:
        out_json = _resolve(args.out_receipt_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.out_receipt_md:
        out_md = _resolve(args.out_receipt_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(packet), encoding="utf-8")
    if not args.quiet:
        print(json.dumps(packet["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if packet["summary"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

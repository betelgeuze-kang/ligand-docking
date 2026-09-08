"""Offline, loss-aware BindingDB development intake; no docking/energy labels.

The source archive is kept intact. This projection retains source row identities,
assay text, chemical state and every rejection. It never opens a protected pose.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Iterator
import zipfile

from rdkit import Chem, rdBase
from rdkit.Chem.Scaffolds import MurckoScaffold

from tools.product.residual_evidence import declared_evaluation_only

SCHEMA = "public_bindingdb_assay_development_v1"
ENDPOINTS = ("Ki", "Kd", "IC50", "EC50")
CHAIN_COUNT = "Number of Protein Chains in Target (>1 implies a multichain complex)"
LICENSES = {
    "Curated from the literature by BindingDB": "CC-BY-4.0",
    "BindingDB": "CC-BY-4.0",
    "ChEMBL": "CC-BY-SA-3.0",
}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def digest(value: bytes | str) -> str:
    return hashlib.sha256(
        value.encode() if isinstance(value, str) else value
    ).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def file_sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def require_sha(value: str, expected: str) -> None:
    if not SHA.fullmatch(expected) or value != expected:
        raise ValueError("source_sha256_mismatch")


@contextmanager
def tsv_stream(path: Path):
    """Read a single TSV member without extracting archive paths."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) != 1 or not members[0].filename.endswith(".tsv"):
                raise ValueError("expected_single_tsv_archive")
            with archive.open(members[0]) as binary:
                with io.TextIOWrapper(binary, encoding="utf-8", newline="") as fh:
                    yield fh, members[0].filename
    else:
        with path.open(encoding="utf-8", newline="") as fh:
            yield fh, path.name


def tsv_records(path: Path) -> Iterator[tuple[int, dict[str, str], str]]:
    """BindingDB documents TSV as literal tabs, not quoted CSV.

    Only absent, unused chain-column tails may be omitted. Missing declared
    chain columns, duplicate headers and surplus cells fail instead of shifting.
    """
    with tsv_stream(path) as (fh, member):
        header = next(fh, "").rstrip("\r\n").split("\t")
        if (
            not header
            or any(not name for name in header)
            or len(set(header)) != len(header)
        ):
            raise ValueError("invalid_or_duplicate_tsv_header")
        for line_number, line in enumerate(fh, 2):
            values = line.rstrip("\r\n").split("\t")
            if len(values) > len(header):
                raise ValueError(f"surplus_tsv_cells:{line_number}")
            row = dict(zip(header, values))
            if len(values) < len(header):
                if CHAIN_COUNT not in row or not row[CHAIN_COUNT].isdigit():
                    raise ValueError(f"truncated_tsv_row:{line_number}")
                n = int(row[CHAIN_COUNT])
                last = f"UniProt (TrEMBL) Alternative ID(s) of Target Chain {n}"
                if n < 1 or last not in row:
                    raise ValueError(f"truncated_declared_chain:{line_number}")
                if any(
                    not re.search(r"Target Chain \d+$", name)
                    for name in header[len(values) :]
                ):
                    raise ValueError(f"truncated_nonchain_columns:{line_number}")
            yield line_number, row, member


def target_accessions(row: dict[str, str]) -> set[str]:
    n = int(row[CHAIN_COUNT]) if row.get(CHAIN_COUNT, "").isdigit() else 0
    return {
        part
        for i in range(1, min(n, 50) + 1)
        for source in ("SwissProt", "TrEMBL")
        for part in re.split(
            r"[;,\s]+",
            row.get(f"UniProt ({source}) Primary ID of Target Chain {i}", "").strip(),
        )
        if part
    }


def target_schema_rejection(row: dict[str, str]) -> str:
    n = int(row[CHAIN_COUNT]) if row.get(CHAIN_COUNT, "").isdigit() else 0
    if not 1 <= n <= 50:
        return "missing_or_invalid_target_chain_count"
    for name, value in row.items():
        match = re.search(r"Target Chain (\d+)$", name)
        if match and int(match.group(1)) > n and value.strip():
            return "nonempty_undeclared_target_chain"
    if any(
        not row.get(f"BindingDB Target Chain Sequence {i}", "").strip()
        for i in range(1, n + 1)
    ):
        return "missing_target_chain_sequence"
    return ""


def chemical_identity(smiles: str) -> dict:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError("invalid_smiles")
    canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    no_stereo = Chem.Mol(mol)
    Chem.RemoveStereochemistry(no_stereo)
    connectivity = Chem.MolToSmiles(no_stereo, canonical=True, isomericSmiles=True)
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    return {
        "canonical_isomeric_smiles": canonical,
        "canonical_isomeric_smiles_sha256": digest(canonical),
        "connectivity_smiles_sha256": digest(connectivity),
        "scaffold_smiles": scaffold,
        "scaffold_group": digest(scaffold or ("acyclic:" + connectivity)),
        "rdkit_inchikey": Chem.MolToInchiKey(mol),
        "heavy_atom_count": mol.GetNumHeavyAtoms(),
        "formal_charge": Chem.GetFormalCharge(mol),
        "fragment_count": len(Chem.GetMolFrags(mol)),
        "elements": sorted({atom.GetSymbol() for atom in mol.GetAtoms()}),
        "radical_electrons": sum(
            atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()
        ),
        "isotope_atoms": sum(atom.GetIsotope() != 0 for atom in mol.GetAtoms()),
        "stereo_unspecified_count": sum(
            str(info.specified) == "Unspecified"
            for info in Chem.FindPotentialStereo(mol)
        ),
        "canonicalization": "rdkit_MolFromSmiles_MolToSmiles_isomeric_true_no_salt_or_state_change",
        "rdkit_version": rdBase.rdkitVersion,
    }


def measurement(raw: str, endpoint: str) -> dict:
    if endpoint not in ENDPOINTS:
        raise ValueError("unsupported_assay_endpoint")
    text = raw.strip()
    result = {
        "endpoint": endpoint,
        "source_value": raw,
        "unit": "nM",
        "relation": None,
        "value_nm": None,
        "negative_log10_molar": None,
        "log_relation": None,
        "status": "missing",
    }
    if not text:
        return result
    match = re.fullmatch(
        r"(<=|>=|<|>|=|~)?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)", text
    )
    if not match:
        result["status"] = "invalid_numeric_or_relation"
        return result
    relation = match.group(1) or "="
    value = float(match.group(2))
    result.update(relation=relation, value_nm=value if math.isfinite(value) else None)
    if not math.isfinite(value) or value <= 0:
        result["status"] = "nonpositive_or_nonfinite_assay_concentration"
        return result
    result.update(
        status="exact"
        if relation == "="
        else "censored"
        if relation != "~"
        else "approximate",
        negative_log10_molar=9.0 - math.log10(value),
        log_relation={"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "~": "~"}[
            relation
        ],
    )
    return result


def validate_exclusions(policy: dict) -> None:
    for key in (
        "excluded_pdb_ids",
        "excluded_ccd_ids",
        "excluded_ligand_inchikeys",
        "excluded_canonical_isomeric_smiles_sha256",
    ):
        if not isinstance(policy.get(key), list) or any(
            not isinstance(v, str) or not v for v in policy[key]
        ):
            raise ValueError(f"invalid_exclusion_list:{key}")
    if type(policy.get("complete")) is not bool:
        raise ValueError("exclusion_completeness_not_declared")
    if "identity_exclusion_complete" in policy:
        if type(policy["identity_exclusion_complete"]) is not bool or not policy.get(
            "identity_exclusion_scope"
        ):
            raise ValueError("identity_exclusion_scope_not_declared")
        if policy.get("normalization", {}).get("version") != rdBase.rdkitVersion:
            raise ValueError("exclusion_canonicalizer_version_mismatch")


def exclusion_reason(row: dict[str, str], identity: dict, policy: dict) -> str:
    if declared_evaluation_only(row):
        return "source_declares_evaluation_only"
    ccds = set(re.split(r"[;,\s]+", row.get("Ligand HET ID in PDB", "").upper()))
    pdbs = set(
        re.split(r"[;,\s]+", row.get("PDB ID(s) for Ligand-Target Complex", "").upper())
    )
    if ccds.intersection(policy["excluded_ccd_ids"]) or pdbs.intersection(
        policy["excluded_pdb_ids"]
    ):
        return "protected_structure_or_ligand_id"
    keys = {row.get("Ligand InChI Key", ""), identity["rdkit_inchikey"]}
    if keys.intersection(policy["excluded_ligand_inchikeys"]):
        return "protected_ligand_inchikey"
    if (
        identity["canonical_isomeric_smiles_sha256"]
        in policy["excluded_canonical_isomeric_smiles_sha256"]
    ):
        return "protected_ligand_smiles"
    # Optional connectivity exclusions are conservative across stereoisomers.
    if identity["connectivity_smiles_sha256"] in policy.get(
        "excluded_stereo_independent_smiles_sha256", []
    ):
        return "protected_ligand_connectivity"
    if any(
        key[:14] in policy.get("excluded_inchikey_connectivity_blocks", [])
        for key in keys
        if key
    ):
        return "protected_ligand_inchikey_connectivity"
    return ""


def assay_index(
    mapping_path: Path, description_path: Path, ids: set[str]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = defaultdict(list)
    mapping_sha, description_sha = file_sha(mapping_path), file_sha(description_path)
    for line, row, member in tsv_records(mapping_path):
        rid = row.get("REACTANT_SET_ID", "")
        if rid in ids:
            links[rid].append(
                {
                    "entry_assay_id": row["ENTRYID_ASSAYID"],
                    "source_line": line,
                    "source_member": member,
                    "source_sha256": mapping_sha,
                    "row": row,
                }
            )
    requested = {link["entry_assay_id"] for values in links.values() for link in values}
    descriptions: dict[str, list[dict]] = defaultdict(list)
    for line, row, member in tsv_records(description_path):
        key = row.get("ENTRYID", "") + "_" + row.get("ASSAYID", "")
        if key in requested:
            descriptions[key].append(
                {
                    "source_line": line,
                    "source_member": member,
                    "source_sha256": description_sha,
                    "row": row,
                }
            )
    return {
        rid: [
            {
                "entry_assay_id": link["entry_assay_id"],
                "mapping_source": link,
                "description_records": descriptions.get(link["entry_assay_id"], []),
            }
            for link in values
        ]
        for rid, values in links.items()
    }


def target_state_identity(row: dict[str, str]) -> dict:
    # PDB cross-reference lists are annotations, not a change of protein state.
    chain_fields = {
        k: v
        for k, v in row.items()
        if k == CHAIN_COUNT
        or (
            (
                k.startswith("BindingDB Target Chain Sequence")
                or "Primary ID of Target Chain" in k
            )
            and v
        )
    }
    return {
        "target_name": row.get("Target Name"),
        "organism": row.get(
            "Target Source Organism According to Curator or DataSource"
        ),
        "chain_fields": chain_fields,
    }


def normalize_record(
    row: dict[str, str], *, identity: dict, assays: list[dict], origin: dict
) -> dict:
    if declared_evaluation_only(row) or any(
        declared_evaluation_only(item.get("row", {}))
        for assay in assays
        for item in [assay.get("mapping_source", {}), *assay["description_records"]]
    ):
        raise ValueError("evaluation_only_join_source")
    observations = [
        measurement(row.get(endpoint + " (nM)", ""), endpoint) for endpoint in ENDPOINTS
    ]
    state = target_state_identity(row)
    source = row.get("Curation/DataSource", "")
    problems = []
    if target_schema_rejection(row):
        problems.append(target_schema_rejection(row))
    if source not in LICENSES:
        problems.append("unresolved_origin_license")
    if len(assays) != 1 or len(assays[0]["description_records"]) != 1:
        problems.append("missing_or_ambiguous_assay_join")
    if not (row.get("Article DOI", "").strip() or row.get("PMID", "").strip()):
        problems.append("missing_primary_document")
    if not row.get("Date of publication", "").strip():
        problems.append("missing_publication_date")
    if not any(observation["status"] == "exact" for observation in observations):
        problems.append("no_exact_supported_endpoint")
    if any(
        observation["status"] not in ("missing", "exact", "censored", "approximate")
        for observation in observations
    ):
        problems.append("invalid_assay_observation")
    if not 5 <= identity["heavy_atom_count"] <= 70 or identity["fragment_count"] != 1:
        problems.append("outside_pilot_molecule_size_or_multifragment")
    if (
        set(identity["elements"]) - {"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}
        or identity["radical_electrons"]
        or identity["isotope_atoms"]
    ):
        problems.append("outside_pilot_element_radical_or_isotope_scope")
    if abs(identity["formal_charge"]) > 2:
        problems.append("outside_pilot_formal_charge_scope")
    return {
        "schema_version": SCHEMA,
        "record_id": "bindingdb:" + row["BindingDB Reactant_set_id"],
        "ligand_id": "bindingdb:" + row.get("BindingDB MonomerID", ""),
        "evidence_kind": "experimental_label",
        "reference_evidence_kind": "experimental_label",
        "dataset_split": "development_pool",
        "evaluation_only": False,
        "source_provenance": {
            **origin,
            "row_sha256": digest(json_text(row)),
            "row": row,
        },
        "curation_source": source,
        "source_license": LICENSES.get(source),
        "chemical_identity": identity,
        "target_accessions": sorted(target_accessions(row)),
        "target_state": state,
        "target_state_sha256": digest(json_text(state)),
        "assays": assays,
        "observations": observations,
        "assay_conditions": {
            "pH_source": row.get("pH"),
            "temperature_c_source": row.get("Temp (C)"),
        },
        "coordinates": None,
        "atom_order": None,
        "pose": None,
        "force_labels": None,
        "potential_energy": None,
        "engine_parameterability": "not_assessed",
        "admission_issues": problems,
        "eligible_for_split_assignment": not problems,
        "training_admitted": False,
        "uncertainty_calibrated": False,
    }


def build_dataset(
    *,
    source_path: Path,
    source_sha256: str,
    source_url: str,
    release: str,
    mapping_path: Path,
    mapping_sha256: str,
    assay_path: Path,
    assay_sha256: str,
    exclusions: dict,
    targets: set[str],
) -> tuple[list[dict], list[dict], dict]:
    if not targets or not source_url.startswith("https://") or not release.strip():
        raise ValueError("missing_target_or_source_identity")
    validate_exclusions(exclusions)
    for path, expected in (
        (source_path, source_sha256),
        (mapping_path, mapping_sha256),
        (assay_path, assay_sha256),
    ):
        require_sha(file_sha(path), expected)
    candidates = []
    source_counts, archive_counts = Counter(), Counter()
    id_counts = Counter()
    for line, row, member in tsv_records(source_path):
        archive_counts["all_source_rows"] += 1
        source_counts[row.get("Curation/DataSource", "")] += 1
        id_counts[row.get("BindingDB Reactant_set_id", "")] += 1
        if target_accessions(row) & targets:
            candidates.append((line, row, member))
    admitted_identity = []
    ledger = []
    for line, row, member in candidates:
        rid = row.get("BindingDB Reactant_set_id", "")
        reason, identity = "", None
        if not rid.strip() or not row.get("BindingDB MonomerID", "").strip():
            reason = "missing_record_or_ligand_id"
        elif id_counts[rid] != 1:
            reason = "duplicate_record_id_all_occurrences_excluded"
        elif target_schema_rejection(row):
            reason = target_schema_rejection(row)
        else:
            try:
                identity = chemical_identity(row.get("Ligand SMILES", ""))
                reason = exclusion_reason(row, identity, exclusions)
            except ValueError as exc:
                reason = str(exc)
        # Protected entries get identifiers/reasons only: no measured values,
        # raw row copies or assay text are emitted into the development data.
        entry = {
            "source_line": line,
            "record_id": "bindingdb:" + rid,
            "target_state_sha256": digest(json_text(target_state_identity(row))),
            "status": "excluded" if reason else "identity_screened",
            "reason": reason,
        }
        ledger.append(entry)
        if not reason:
            admitted_identity.append((line, row, member, identity, entry))
    assays = assay_index(
        mapping_path,
        assay_path,
        {row["BindingDB Reactant_set_id"] for _, row, _, _, _ in admitted_identity},
    )
    records = []
    for line, row, member, identity, entry in admitted_identity:
        try:
            normalized = normalize_record(
                row,
                identity=identity,
                assays=assays.get(row["BindingDB Reactant_set_id"], []),
                origin={
                    "source_url": source_url,
                    "source_sha256": source_sha256,
                    "release": release,
                    "source_member": member,
                    "source_line": line,
                },
            )
        except ValueError as exc:
            entry.update(status="excluded", reason=str(exc))
            continue
        if not exclusions.get("identity_exclusion_complete", exclusions["complete"]):
            normalized["admission_issues"].append("protected_identity_audit_incomplete")
            normalized["eligible_for_split_assignment"] = False
        entry.update(
            status="normalized", reason=";".join(normalized["admission_issues"])
        )
        records.append(normalized)
    # Ordinary concurrent source changes invalidate the complete bundle before
    # publication. Hashes are identities, not source authenticity signatures.
    for path, expected in (
        (source_path, source_sha256),
        (mapping_path, mapping_sha256),
        (assay_path, assay_sha256),
    ):
        require_sha(file_sha(path), expected)
    summary = {
        "schema_version": SCHEMA,
        "release": release,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "mapping_sha256": mapping_sha256,
        "assay_sha256": assay_sha256,
        "exclusions_sha256": digest(json_text(exclusions)),
        "requested_targets": sorted(targets),
        "identity_exclusion_scope": exclusions.get(
            "identity_exclusion_scope", "caller_declared_exact_identity_list"
        ),
        "global_repository_protected_data_inventory_complete": exclusions.get(
            "global_repository_protected_data_inventory_complete", False
        ),
        "similarity_or_scaffold_leakage_exclusion_complete": exclusions.get(
            "similarity_or_scaffold_leakage_exclusion_complete", False
        ),
        "all_source_rows": archive_counts["all_source_rows"],
        "source_origin_counts": dict(source_counts),
        "requested_target_rows": len(candidates),
        "normalized_rows": len(records),
        "excluded_before_observation_projection": len(candidates) - len(records),
        "exclusion_counts": dict(
            Counter(
                entry["reason"] for entry in ledger if entry["status"] == "excluded"
            )
        ),
        "admission_issue_counts": dict(
            Counter(issue for row in records for issue in row["admission_issues"])
        ),
        "eligible_for_split_assignment": sum(
            row["eligible_for_split_assignment"] for row in records
        ),
        "training_admitted_rows": 0,
        "training_executed": False,
        "rdkit_version": rdBase.rdkitVersion,
        "scientific_validation": False,
        "customer_execution": False,
        "scope": "public assay development intake; concentration endpoints remain distinct; no energy or pose labels",
    }
    return records, ledger, summary

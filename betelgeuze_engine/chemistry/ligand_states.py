from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import os
from typing import Any

try:
    from rdkit import Chem, RDConfig
    from rdkit.Chem import ChemicalFeatures
    from rdkit.Chem.MolStandardize import rdMolStandardize
except Exception:  # pragma: no cover - optional dependency path
    Chem = None
    RDConfig = None
    ChemicalFeatures = None
    rdMolStandardize = None


FEATURE_SOURCE = "rdkit_chemical_features_base_fdef"
TAUTOMER_SOURCE = "rdkit_molstandardize_tautomer_enumerator"
PROTONATION_SOURCE = "rdkit_formal_charge_state_from_input_ph_7_4_no_pka_enumeration"
SALT_SOURCE = "rdkit_molstandardize_fragment_parent"
HBOND_ELEMENTS = {"N", "O", "S", "P"}


@dataclass(frozen=True)
class LigandFeatureSite:
    atom_idx: int
    element: str
    role: str
    feature_family: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LigandChemistryState:
    valid: bool
    source: str
    reason: str
    canonical_smiles: str = ""
    salt_parent_smiles: str = ""
    fragment_count: int = 0
    salt_stripped: bool = False
    formal_charge_sum: int = 0
    charged_atom_count: int = 0
    protonation_status: str = "not_assessed"
    protonation_source: str = "not_assessed"
    tautomer_status: str = "not_assessed"
    tautomer_source: str = "not_assessed"
    canonical_tautomer_smiles: str = ""
    tautomer_count: int = 0
    feature_source: str = "not_assessed"
    feature_sites: tuple[LigandFeatureSite, ...] = ()
    donor_site_count: int = 0
    acceptor_site_count: int = 0
    chiral_center_count: int = 0
    specified_chiral_center_count: int = 0
    unassigned_chiral_center_count: int = 0
    chirality_status: str = "not_assessed"
    claim_safe_blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["feature_sites"] = [site.to_dict() for site in self.feature_sites]
        payload["claim_safe_blockers"] = list(self.claim_safe_blockers)
        return payload


@lru_cache(maxsize=1)
def _feature_factory() -> Any:
    if ChemicalFeatures is None or RDConfig is None:
        return None
    fdef = os.path.join(RDConfig.RDDataDir, "BaseFeatures.fdef")
    return ChemicalFeatures.BuildFeatureFactory(fdef)


def _feature_sites(mol: Any) -> tuple[LigandFeatureSite, ...]:
    factory = _feature_factory()
    if factory is None or mol is None:
        return ()
    role_by_atom: dict[int, set[str]] = {}
    family_by_atom: dict[tuple[int, str], str] = {}
    for feature in factory.GetFeaturesForMol(mol):
        family = str(feature.GetFamily())
        if family not in {"Donor", "Acceptor"}:
            continue
        role = "donor" if family == "Donor" else "acceptor"
        for atom_idx in feature.GetAtomIds():
            atom = mol.GetAtomWithIdx(int(atom_idx))
            element = str(atom.GetSymbol())
            if element not in HBOND_ELEMENTS:
                continue
            role_by_atom.setdefault(int(atom_idx), set()).add(role)
            family_by_atom[(int(atom_idx), role)] = family
    sites: list[LigandFeatureSite] = []
    for atom_idx, roles in sorted(role_by_atom.items()):
        atom = mol.GetAtomWithIdx(int(atom_idx))
        element = str(atom.GetSymbol())
        for role in sorted(roles, key=lambda value: 0 if value == "donor" else 1):
            sites.append(
                LigandFeatureSite(
                    atom_idx=int(atom_idx),
                    element=element,
                    role=role,
                    feature_family=family_by_atom.get((int(atom_idx), role), ""),
                )
            )
    return tuple(sites)


def _canonical_tautomer(mol: Any) -> tuple[str, int, str]:
    if rdMolStandardize is None or Chem is None or mol is None:
        return "", 0, "not_assessed"
    enumerator = rdMolStandardize.TautomerEnumerator()
    canonical = enumerator.Canonicalize(mol)
    try:
        tautomer_count = len(list(enumerator.Enumerate(mol)))
    except Exception:
        tautomer_count = 0
    canonical_smiles = Chem.MolToSmiles(canonical, isomericSmiles=True)
    status = "canonical_tautomer_enumerated" if canonical_smiles else "tautomer_canonicalization_failed"
    return canonical_smiles, int(tautomer_count), status


def _salt_parent_smiles(mol: Any) -> tuple[str, int, bool]:
    if Chem is None or mol is None:
        return "", 0, False
    fragment_count = len(Chem.GetMolFrags(mol))
    if rdMolStandardize is None:
        return Chem.MolToSmiles(mol, isomericSmiles=True), int(fragment_count), fragment_count > 1
    parent = rdMolStandardize.FragmentParent(mol)
    return Chem.MolToSmiles(parent, isomericSmiles=True), int(fragment_count), fragment_count > 1


def ligand_chemistry_state_from_smiles(smiles: str) -> LigandChemistryState:
    smi = str(smiles or "").strip()
    if not smi:
        return LigandChemistryState(
            valid=False,
            source="none",
            reason="empty_smiles",
            claim_safe_blockers=("empty_smiles",),
        )
    if Chem is None:
        return LigandChemistryState(
            valid=False,
            source="rdkit_unavailable",
            reason="rdkit_unavailable",
            claim_safe_blockers=("rdkit_unavailable_ligand_chemistry",),
        )
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return LigandChemistryState(
            valid=False,
            source="rdkit",
            reason="invalid_smiles",
            claim_safe_blockers=("invalid_smiles",),
        )
    canonical_smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    salt_parent, fragment_count, salt_stripped = _salt_parent_smiles(mol)
    formal_charge_sum = int(sum(atom.GetFormalCharge() for atom in mol.GetAtoms()))
    charged_atom_count = int(sum(1 for atom in mol.GetAtoms() if atom.GetFormalCharge() != 0))
    features = _feature_sites(mol)
    canonical_tautomer, tautomer_count, tautomer_status = _canonical_tautomer(mol)
    chiral_centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    unassigned = sum(1 for _idx, label in chiral_centers if str(label) == "?")
    specified = len(chiral_centers) - unassigned
    if unassigned:
        chirality_status = "unassigned_chiral_centers"
    elif specified:
        chirality_status = "specified"
    else:
        chirality_status = "not_applicable"
    blockers: list[str] = []
    if unassigned:
        blockers.append("unassigned_ligand_chirality")
    return LigandChemistryState(
        valid=True,
        source="rdkit",
        reason="rdkit_parse_ok",
        canonical_smiles=canonical_smiles,
        salt_parent_smiles=salt_parent,
        fragment_count=int(fragment_count),
        salt_stripped=bool(salt_stripped),
        formal_charge_sum=formal_charge_sum,
        charged_atom_count=charged_atom_count,
        protonation_status="charged_state_parsed" if charged_atom_count else "neutral_state_parsed",
        protonation_source=PROTONATION_SOURCE,
        tautomer_status=tautomer_status,
        tautomer_source=TAUTOMER_SOURCE,
        canonical_tautomer_smiles=canonical_tautomer,
        tautomer_count=int(tautomer_count),
        feature_source=FEATURE_SOURCE,
        feature_sites=features,
        donor_site_count=sum(1 for site in features if site.role == "donor"),
        acceptor_site_count=sum(1 for site in features if site.role == "acceptor"),
        chiral_center_count=len(chiral_centers),
        specified_chiral_center_count=specified,
        unassigned_chiral_center_count=unassigned,
        chirality_status=chirality_status,
        claim_safe_blockers=tuple(blockers),
    )

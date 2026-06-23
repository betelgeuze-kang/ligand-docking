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
PROTONATION_POLICY = "restricted_formal_charge_input_state_ph_7_4_no_pka"
PROTONATION_CLAIM_BOUNDARY = (
    "Formal-charge/protomer state is derived from the input structure and RDKit standardization only; "
    "no pKa model or pH-range protonation ensemble is claimed."
)
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
    protonation_policy: str = "not_assessed"
    protonation_ph_values: tuple[float, ...] = ()
    protonation_claim_boundary: str = ""
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
    potential_stereo_count: int = 0
    specified_stereo_count: int = 0
    unassigned_stereo_count: int = 0
    unassigned_stereo_bond_count: int = 0
    chirality_status: str = "not_assessed"
    claim_safe_blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["feature_sites"] = [site.to_dict() for site in self.feature_sites]
        payload["claim_safe_blockers"] = list(self.claim_safe_blockers)
        return payload


@dataclass(frozen=True)
class LigandEnumeratedState:
    state_id: str
    smiles: str
    state_kind: str
    source: str
    rank: int
    valid: bool
    reason: str
    canonical_smiles: str = ""
    protonation_status: str = "not_assessed"
    protonation_source: str = "not_assessed"
    protonation_policy: str = "not_assessed"
    protonation_ph_values: tuple[float, ...] = ()
    protonation_claim_boundary: str = ""
    tautomer_status: str = "not_assessed"
    tautomer_source: str = "not_assessed"
    salt_stripped: bool = False
    fragment_count: int = 0
    formal_charge_sum: int = 0
    charged_atom_count: int = 0
    atom_count: int = 0
    claim_safe_blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
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


def _tautomer_smiles(mol: Any, *, max_states: int) -> list[str]:
    if rdMolStandardize is None or Chem is None or mol is None:
        return []
    enumerator = rdMolStandardize.TautomerEnumerator()
    try:
        tautomers = list(enumerator.Enumerate(mol))
    except Exception:
        return []
    smiles: list[str] = []
    seen: set[str] = set()
    for tautomer in tautomers:
        candidate = Chem.MolToSmiles(tautomer, isomericSmiles=True)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        smiles.append(candidate)
        if len(smiles) >= int(max(1, max_states)):
            break
    return smiles


def _potential_stereo_summary(mol: Any) -> dict[str, int]:
    if Chem is None or mol is None or not hasattr(Chem, "FindPotentialStereo"):
        return {
            "potential_stereo_count": 0,
            "specified_stereo_count": 0,
            "unassigned_stereo_count": 0,
            "unassigned_stereo_bond_count": 0,
        }
    potential = 0
    specified = 0
    unassigned = 0
    unassigned_bonds = 0
    for info in Chem.FindPotentialStereo(mol):
        potential += 1
        specified_text = str(getattr(info, "specified", ""))
        type_text = str(getattr(info, "type", ""))
        if specified_text.endswith("Unspecified"):
            unassigned += 1
            if type_text.endswith("Bond_Double"):
                unassigned_bonds += 1
        else:
            specified += 1
    return {
        "potential_stereo_count": int(potential),
        "specified_stereo_count": int(specified),
        "unassigned_stereo_count": int(unassigned),
        "unassigned_stereo_bond_count": int(unassigned_bonds),
    }


def _salt_parent_smiles(mol: Any) -> tuple[str, int, bool]:
    if Chem is None or mol is None:
        return "", 0, False
    fragment_count = len(Chem.GetMolFrags(mol))
    if rdMolStandardize is None:
        return Chem.MolToSmiles(mol, isomericSmiles=True), int(fragment_count), fragment_count > 1
    parent = rdMolStandardize.FragmentParent(mol)
    return Chem.MolToSmiles(parent, isomericSmiles=True), int(fragment_count), fragment_count > 1


def _mol_to_isomeric_smiles(mol: Any) -> str:
    if Chem is None or mol is None:
        return ""
    return Chem.MolToSmiles(mol, isomericSmiles=True)


def _charge_normalized_smiles(mol: Any) -> tuple[str, str]:
    if Chem is None or rdMolStandardize is None or mol is None:
        return "", "not_assessed"
    candidates: list[tuple[str, Any]] = []
    try:
        candidates.append(("rdkit_molstandardize_reionizer_no_pka", rdMolStandardize.Reionizer().reionize(mol)))
    except Exception:
        pass
    try:
        candidates.append(("rdkit_molstandardize_uncharger_no_pka", rdMolStandardize.Uncharger().uncharge(mol)))
    except Exception:
        pass
    for source, candidate in candidates:
        smiles = _mol_to_isomeric_smiles(candidate)
        if smiles:
            return smiles, source
    return "", "charge_normalization_failed"


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
    stereo_summary = _potential_stereo_summary(mol)
    unassigned = sum(1 for _idx, label in chiral_centers if str(label) == "?")
    specified = len(chiral_centers) - unassigned
    if int(stereo_summary["unassigned_stereo_count"]) > 0:
        chirality_status = "unassigned_stereochemistry"
    elif specified or int(stereo_summary["specified_stereo_count"]) > 0:
        chirality_status = "specified"
    else:
        chirality_status = "not_applicable"
    blockers: list[str] = []
    if unassigned:
        blockers.append("unassigned_ligand_chirality")
    if int(stereo_summary["unassigned_stereo_count"]) > 0:
        blockers.append("unassigned_ligand_stereochemistry")
    if int(stereo_summary["unassigned_stereo_bond_count"]) > 0:
        blockers.append("unassigned_ligand_double_bond_stereochemistry")
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
        protonation_policy=PROTONATION_POLICY,
        protonation_ph_values=(7.4,),
        protonation_claim_boundary=PROTONATION_CLAIM_BOUNDARY,
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
        potential_stereo_count=int(stereo_summary["potential_stereo_count"]),
        specified_stereo_count=int(stereo_summary["specified_stereo_count"]),
        unassigned_stereo_count=int(stereo_summary["unassigned_stereo_count"]),
        unassigned_stereo_bond_count=int(stereo_summary["unassigned_stereo_bond_count"]),
        chirality_status=chirality_status,
        claim_safe_blockers=tuple(blockers),
    )


def enumerate_ligand_states_from_smiles(smiles: str, *, max_states: int = 4) -> tuple[LigandEnumeratedState, ...]:
    smi = str(smiles or "").strip()
    limit = int(max(1, max_states))
    chemistry = ligand_chemistry_state_from_smiles(smi)
    if not chemistry.valid or Chem is None:
        return (
            LigandEnumeratedState(
                state_id="ligand_state_00_input",
                smiles=smi,
                state_kind="input",
                source=chemistry.source,
                rank=0,
                valid=bool(chemistry.valid),
                reason=chemistry.reason,
                canonical_smiles=chemistry.canonical_smiles,
                protonation_status=chemistry.protonation_status,
                protonation_source=chemistry.protonation_source,
                protonation_policy=chemistry.protonation_policy,
                protonation_ph_values=chemistry.protonation_ph_values,
                protonation_claim_boundary=chemistry.protonation_claim_boundary,
                tautomer_status=chemistry.tautomer_status,
                tautomer_source=chemistry.tautomer_source,
                salt_stripped=bool(chemistry.salt_stripped),
                fragment_count=int(chemistry.fragment_count),
                formal_charge_sum=int(chemistry.formal_charge_sum),
                charged_atom_count=int(chemistry.charged_atom_count),
                atom_count=0,
                claim_safe_blockers=chemistry.claim_safe_blockers,
            ),
        )

    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return ()

    raw_candidates: list[tuple[str, str, str]] = [
        ("input_canonical", "input_smiles_rdkit_canonicalized", chemistry.canonical_smiles or smi),
    ]
    if chemistry.salt_parent_smiles and chemistry.salt_parent_smiles != chemistry.canonical_smiles:
        raw_candidates.append(("salt_parent", SALT_SOURCE, chemistry.salt_parent_smiles))
    if chemistry.canonical_tautomer_smiles and chemistry.canonical_tautomer_smiles != chemistry.canonical_smiles:
        raw_candidates.append(("canonical_tautomer", TAUTOMER_SOURCE, chemistry.canonical_tautomer_smiles))
    for idx, tautomer_smiles in enumerate(_tautomer_smiles(mol, max_states=limit), start=1):
        if tautomer_smiles != chemistry.canonical_smiles:
            raw_candidates.append((f"tautomer_{idx:02d}", TAUTOMER_SOURCE, tautomer_smiles))
    normalized, normalized_source = _charge_normalized_smiles(mol)
    if normalized and normalized != chemistry.canonical_smiles:
        raw_candidates.append(("charge_normalized", normalized_source, normalized))

    states: list[LigandEnumeratedState] = []
    seen: set[str] = set()
    for state_kind, source, candidate_smiles in raw_candidates:
        candidate_chemistry = ligand_chemistry_state_from_smiles(candidate_smiles)
        canonical = candidate_chemistry.canonical_smiles or candidate_smiles
        if canonical in seen:
            continue
        seen.add(canonical)
        candidate_mol = Chem.MolFromSmiles(candidate_smiles)
        projection_blockers = list(candidate_chemistry.claim_safe_blockers)
        if state_kind == "salt_parent":
            projection_blockers.append("salt_parent_projection_not_product_safe")
        elif state_kind.startswith("tautomer") or state_kind == "canonical_tautomer":
            projection_blockers.append("tautomer_projection_not_product_safe")
            projection_blockers.append("tautomer_enumeration_limited")
        elif state_kind == "charge_normalized":
            projection_blockers.append("charge_projection_not_product_safe")
            projection_blockers.append("protonation_enumeration_limited_no_pka")
        states.append(
            LigandEnumeratedState(
                state_id=f"ligand_state_{len(states):02d}_{state_kind}",
                smiles=canonical,
                state_kind=state_kind,
                source=source,
                rank=len(states),
                valid=bool(candidate_chemistry.valid),
                reason=candidate_chemistry.reason,
                canonical_smiles=canonical,
                protonation_status=candidate_chemistry.protonation_status,
                protonation_source=(
                    normalized_source if state_kind == "charge_normalized" else candidate_chemistry.protonation_source
                ),
                protonation_policy=candidate_chemistry.protonation_policy,
                protonation_ph_values=candidate_chemistry.protonation_ph_values,
                protonation_claim_boundary=candidate_chemistry.protonation_claim_boundary,
                tautomer_status=candidate_chemistry.tautomer_status,
                tautomer_source=candidate_chemistry.tautomer_source,
                salt_stripped=bool(candidate_chemistry.salt_stripped),
                fragment_count=int(candidate_chemistry.fragment_count),
                formal_charge_sum=int(candidate_chemistry.formal_charge_sum),
                charged_atom_count=int(candidate_chemistry.charged_atom_count),
                atom_count=int(candidate_mol.GetNumAtoms()) if candidate_mol is not None else 0,
                claim_safe_blockers=tuple(dict.fromkeys(projection_blockers)),
            )
        )
        if len(states) >= limit:
            break
    return tuple(states)

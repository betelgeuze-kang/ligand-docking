"""Frozen real-world identity corpus for bounded pH protonation.

The corpus manually projects factual PubChem structure identities into the
bounded mmCIF contract syntax.  Coordinates are deterministic contract fixture
values and are not PubChem conformers.  Raw PubChem responses and contributor
text are not bundled.  Every source, transformation, license boundary,
supported state, abstention, and expected failure remains in the signed
projection denominator.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
import tempfile

from .mmcif_nonpoly_all_atom_systems import parse_mmcif_nonpoly_all_atom_systems
from .mmcif_nonpoly_ph_protonation import (
    MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION,
    MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
    MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID,
    MmcifNonpolyPhProtonationError,
    apply_mmcif_nonpoly_ph_protonation,
    mmcif_nonpoly_ph_protonation_reference_sha256,
)
from .mmcif_nonpoly_preparation_corpus import (
    MmcifPreparationCorpusAtom,
    MmcifPreparationCorpusBond,
    _corpus_source,
)


MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_ph_protonation_corpus_projection/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_ph_protonation_corpus_source_binding/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_ph_protonation_corpus_document/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID = (
    "frozen_pubchem_identity_ph_protonation_corpus/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION = "1.0.0"
FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SNAPSHOT_SHA256 = (
    "0b7d7286f6f1619b417591e5d3c5414f96c89517862ca50395d18e213ec30f7f"
)

PUBCHEM_CID_176_RECORD_FIELDS_SHA256 = (
    "6f1ade06eec5019ec6f2e24dee973e74bba42e039e20c3892a18e2668a1c6628"
)
PUBCHEM_CID_702_RECORD_FIELDS_SHA256 = (
    "f2676f3c5d888359b6acf624e250752412899e7c70fe7c4edf0ed1998e04a9fd"
)

FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256: Mapping[str, str] = (
    MappingProxyType(
        {
            "pubchem_cid_176_ph2_protonated": (
                "07db48af36e418cca46f66d0d06ecbb3b03623abf92af12e9d30e92361543b7b"
            ),
            "pubchem_cid_176_ph7_deprotonated": (
                "07db48af36e418cca46f66d0d06ecbb3b03623abf92af12e9d30e92361543b7b"
            ),
            "pubchem_cid_176_ph4_76_abstained": (
                "07db48af36e418cca46f66d0d06ecbb3b03623abf92af12e9d30e92361543b7b"
            ),
            "pubchem_cid_702_structure_mismatch": (
                "e6e0394115ee647db156e1bdbb5036174c2ec589c515567247439dc27850b8e5"
            ),
            "pubchem_cid_176_reference_crosswire": (
                "07db48af36e418cca46f66d0d06ecbb3b03623abf92af12e9d30e92361543b7b"
            ),
            "pubchem_cid_176_ph_out_of_bounds": (
                "07db48af36e418cca46f66d0d06ecbb3b03623abf92af12e9d30e92361543b7b"
            ),
            "pubchem_cid_176_source_hydrogen_rejected": (
                "776a987f81cba5cd1d0dff29016a3dfa0b116a5b4218d1a4b501f41bd79006df"
            ),
        }
    )
)


class MmcifNonpolyPhProtonationCorpusError(ValueError):
    """The frozen real-world corpus or expectation ledger drifted."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "real_world_structure_identities_bound": True,
        "pubchem_cid_176_supported_states_executed": True,
        "pubchem_cid_702_failure_executed": True,
        "supported_abstention_and_failure_rows_retained": True,
        "source_and_case_sha256_frozen": True,
        "license_and_provenance_boundary_bound": True,
        "canonical_selected_state_round_trip_bound": True,
        "source_structure_identity_authenticated": False,
        "raw_pubchem_records_bundled": False,
        "pubchem_contributor_text_bundled": False,
        "pubchem_coordinates_used": False,
        "corpus_is_parameter_fitting_data": False,
        "parameter_fitting_allowed": False,
        "general_ph_protonation_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _source_license_boundary() -> dict[str, Any]:
    return {
        "provider": "PubChem",
        "policy_url": "https://pubchem.ncbi.nlm.nih.gov/docs/downloads",
        "policy_identity": "pubchem_source_specific_license_review_required",
        "retrieved_date": "2026-07-17",
        "raw_record_bundled": False,
        "contributor_text_bundled": False,
        "factual_identifiers_and_manually_projected_graph_only": True,
        "commercial_redistribution_approved": False,
        "source_specific_restrictions_review_required": True,
    }


def _pubchem_record(cid: int) -> dict[str, Any]:
    if cid == 176:
        record = {
            "cid": 176,
            "connectivity_smiles": "CC(=O)O",
            "inchi_key": "QTBSBXVTEAMEQO-UHFFFAOYSA-N",
            "molecular_formula": "C2H4O2",
            "title": "Acetic Acid",
        }
        expected = PUBCHEM_CID_176_RECORD_FIELDS_SHA256
        name = "acetic%20acid"
    elif cid == 702:
        record = {
            "cid": 702,
            "connectivity_smiles": "CCO",
            "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
            "molecular_formula": "C2H6O",
            "title": "Ethanol",
        }
        expected = PUBCHEM_CID_702_RECORD_FIELDS_SHA256
        name = "ethanol"
    else:
        raise MmcifNonpolyPhProtonationCorpusError(
            "unreviewed PubChem record requested"
        )
    if _sha256(record) != expected:
        raise MmcifNonpolyPhProtonationCorpusError(
            "PubChem record identity fields drifted"
        )
    return {
        "record_id": f"pubchem:cid:{cid}",
        "record_fields": record,
        "record_fields_sha256": expected,
        "request_url": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            f"{name}/property/Title,MolecularFormula,ConnectivitySMILES,"
            "InChIKey/JSON"
        ),
        "retrieved_date": "2026-07-17",
        "license_boundary": _source_license_boundary(),
    }


def reviewed_mmcif_nonpoly_ph_protonation_corpus_sources() -> tuple[
    Mapping[str, Any], ...
]:
    """Return reviewed factual source identities without raw responses."""

    return (_pubchem_record(176), _pubchem_record(702))


def _acetic_source(*, source_acidic_hydrogen: bool = False) -> str:
    atoms = (
        MmcifPreparationCorpusAtom("C1", "C"),
        MmcifPreparationCorpusAtom("C2", "C"),
        MmcifPreparationCorpusAtom("O1", "O"),
        MmcifPreparationCorpusAtom("O2", "O"),
    )
    bonds = (
        MmcifPreparationCorpusBond("C1", "C2", "SING"),
        MmcifPreparationCorpusBond("C2", "O1", "DOUB"),
        MmcifPreparationCorpusBond("C2", "O2", "SING"),
    )
    if source_acidic_hydrogen:
        atoms = (*atoms, MmcifPreparationCorpusAtom("HO2", "H"))
        bonds = (*bonds, MmcifPreparationCorpusBond("O2", "HO2", "SING"))
    return _corpus_source(atoms, bonds)


def _ethanol_source() -> str:
    return _corpus_source(
        (
            MmcifPreparationCorpusAtom("C1", "C"),
            MmcifPreparationCorpusAtom("C2", "C"),
            MmcifPreparationCorpusAtom("O1", "O"),
        ),
        (
            MmcifPreparationCorpusBond("C1", "C2", "SING"),
            MmcifPreparationCorpusBond("C2", "O1", "SING"),
        ),
    )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifPhProtonationCorpusCase:
    case_id: str
    cohort: str
    source_text: str
    input_sha256: str
    source_record_id: str
    source_record_fields_sha256: str
    reference_compound_id: str
    target_ph: float
    expected_decision_status: str
    expected_selected_state: str
    expected_error_code: str

    def __repr__(self) -> str:
        return (
            "MmcifPhProtonationCorpusCase("
            f"case_id={self.case_id!r}, cohort={self.cohort!r})"
        )

    @property
    def case_contract_sha256(self) -> str:
        return _sha256(self.binding_dict())

    def binding_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cohort": self.cohort,
            "input_sha256": self.input_sha256,
            "input_byte_count": len(self.source_text.encode("ascii")),
            "source_record_id": self.source_record_id,
            "source_record_fields_sha256": self.source_record_fields_sha256,
            "reference_compound_id": self.reference_compound_id,
            "target_ph_binary64_hex": float(self.target_ph).hex(),
            "expected_decision_status": self.expected_decision_status,
            "expected_selected_state": self.expected_selected_state,
            "expected_error_code": self.expected_error_code,
            "fixture_transform": (
                "manual_bounded_mmcif_projection_from_pubchem_connectivity_identity"
            ),
            "fixture_coordinates": "deterministic_contract_values_not_pubchem_conformer",
        }


def _case(
    case_id: str,
    cohort: str,
    source_text: str,
    *,
    source_cid: int,
    target_ph: float,
    reference_compound_id: str = MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID,
    expected_decision_status: str = "",
    expected_selected_state: str = "",
    expected_error_code: str = "",
) -> MmcifPhProtonationCorpusCase:
    source_text.encode("ascii")
    digest = hashlib.sha256(source_text.encode("ascii")).hexdigest()
    frozen = FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256.get(case_id, "")
    if frozen and digest != frozen:
        raise MmcifNonpolyPhProtonationCorpusError(
            f"frozen pH corpus input drifted for {case_id}"
        )
    source = _pubchem_record(source_cid)
    return MmcifPhProtonationCorpusCase(
        case_id=case_id,
        cohort=cohort,
        source_text=source_text,
        input_sha256=digest,
        source_record_id=str(source["record_id"]),
        source_record_fields_sha256=str(source["record_fields_sha256"]),
        reference_compound_id=reference_compound_id,
        target_ph=float(target_ph),
        expected_decision_status=expected_decision_status,
        expected_selected_state=expected_selected_state,
        expected_error_code=expected_error_code,
    )


def mmcif_nonpoly_ph_protonation_corpus_cases() -> tuple[
    MmcifPhProtonationCorpusCase, ...
]:
    """Return the exact ordered supported, abstention, and failure corpus."""

    acetic = _acetic_source()
    cases = (
        _case(
            "pubchem_cid_176_ph2_protonated",
            "real_world_supported",
            acetic,
            source_cid=176,
            target_ph=2.0,
            expected_decision_status="dominant_protonation_state_selected",
            expected_selected_state="protonated",
        ),
        _case(
            "pubchem_cid_176_ph7_deprotonated",
            "real_world_supported",
            acetic,
            source_cid=176,
            target_ph=7.0,
            expected_decision_status="dominant_protonation_state_selected",
            expected_selected_state="deprotonated",
        ),
        _case(
            "pubchem_cid_176_ph4_76_abstained",
            "real_world_abstention",
            acetic,
            source_cid=176,
            target_ph=4.76,
            expected_decision_status="abstained_population_not_dominant",
        ),
        _case(
            "pubchem_cid_702_structure_mismatch",
            "real_world_failure",
            _ethanol_source(),
            source_cid=702,
            target_ph=7.0,
            expected_error_code="reference_structure_mismatch",
        ),
        _case(
            "pubchem_cid_176_reference_crosswire",
            "real_world_failure",
            acetic,
            source_cid=176,
            target_ph=7.0,
            reference_compound_id="pubchem:cid:702",
            expected_error_code="unsupported_reference_compound",
        ),
        _case(
            "pubchem_cid_176_ph_out_of_bounds",
            "real_world_failure",
            acetic,
            source_cid=176,
            target_ph=14.1,
            expected_error_code="target_ph_out_of_bounds",
        ),
        _case(
            "pubchem_cid_176_source_hydrogen_rejected",
            "real_world_failure",
            _acetic_source(source_acidic_hydrogen=True),
            source_cid=176,
            target_ph=7.0,
            expected_error_code="source_observed_acidic_hydrogen_not_removable",
        ),
    )
    if tuple(row.case_id for row in cases) != tuple(
        FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256
    ):
        raise MmcifNonpolyPhProtonationCorpusError(
            "frozen pH corpus case order drifted"
        )
    return cases


@dataclass(frozen=True, slots=True)
class MmcifPhProtonationCorpusCaseResult:
    case_id: str
    cohort: str
    input_sha256: str
    case_contract_sha256: str
    source_record_id: str
    source_record_fields_sha256: str
    observed_outcome: str
    decision_status: str
    selected_state: str
    error_code: str
    protonation_snapshot_sha256: str
    system_sha256: str
    topology_sha256: str
    coordinates_sha256: str
    protonated_fraction_binary64_hex: str
    deprotonated_fraction_binary64_hex: str
    signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cohort": self.cohort,
            "input_sha256": self.input_sha256,
            "case_contract_sha256": self.case_contract_sha256,
            "source_record_id": self.source_record_id,
            "source_record_fields_sha256": self.source_record_fields_sha256,
            "observed_outcome": self.observed_outcome,
            "expectation_matched": True,
            "decision_status": self.decision_status,
            "selected_state": self.selected_state,
            "error_code": self.error_code,
            "protonation_snapshot_sha256": self.protonation_snapshot_sha256,
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "protonated_fraction_binary64_hex": (self.protonated_fraction_binary64_hex),
            "deprotonated_fraction_binary64_hex": (
                self.deprotonated_fraction_binary64_hex
            ),
            "signals": list(self.signals),
        }


def _run_case(case: MmcifPhProtonationCorpusCase) -> MmcifPhProtonationCorpusCaseResult:
    materialization = parse_mmcif_nonpoly_all_atom_systems(case.source_text)
    target = materialization.instance_reports[0].instance_identity_sha256
    signals = [
        f"real_world_source:{case.source_record_id}",
        "license_policy:pubchem_source_specific_license_review_required",
        "fixture_transform:manual_bounded_mmcif_projection",
    ]
    try:
        snapshot = apply_mmcif_nonpoly_ph_protonation(
            case.source_text,
            instance_identity_sha256=target,
            target_ph=case.target_ph,
            reference_compound_id=case.reference_compound_id,
        )
    except MmcifNonpolyPhProtonationError as exc:
        if not case.expected_error_code or exc.code != case.expected_error_code:
            raise MmcifNonpolyPhProtonationCorpusError(
                f"unexpected pH corpus error for {case.case_id}"
            ) from exc
        signals.extend(("observed_outcome:expected_error", f"error:{exc.code}"))
        return MmcifPhProtonationCorpusCaseResult(
            case_id=case.case_id,
            cohort=case.cohort,
            input_sha256=case.input_sha256,
            case_contract_sha256=case.case_contract_sha256,
            source_record_id=case.source_record_id,
            source_record_fields_sha256=case.source_record_fields_sha256,
            observed_outcome="expected_error",
            decision_status="",
            selected_state="",
            error_code=exc.code,
            protonation_snapshot_sha256="",
            system_sha256="",
            topology_sha256="",
            coordinates_sha256="",
            protonated_fraction_binary64_hex="",
            deprotonated_fraction_binary64_hex="",
            signals=tuple(signals),
        )
    if case.expected_error_code:
        raise MmcifNonpolyPhProtonationCorpusError(
            f"expected pH corpus error was not raised for {case.case_id}"
        )
    report = snapshot.report
    if (
        report.decision_status != case.expected_decision_status
        or report.selected_state != case.expected_selected_state
    ):
        raise MmcifNonpolyPhProtonationCorpusError(
            f"pH corpus decision mismatch for {case.case_id}"
        )
    signals.extend(
        (
            "observed_outcome:expected_decision",
            f"ph_protonation_status:{report.decision_status}",
        )
    )
    if report.selected_state:
        signals.extend(
            (
                f"ph_selected_state:{report.selected_state}",
                "canonical_round_trip:verified",
            )
        )
    else:
        signals.append("ph_abstention:minimum_dominant_population_not_met")
    return MmcifPhProtonationCorpusCaseResult(
        case_id=case.case_id,
        cohort=case.cohort,
        input_sha256=case.input_sha256,
        case_contract_sha256=case.case_contract_sha256,
        source_record_id=case.source_record_id,
        source_record_fields_sha256=case.source_record_fields_sha256,
        observed_outcome="expected_decision",
        decision_status=report.decision_status,
        selected_state=report.selected_state,
        error_code="",
        protonation_snapshot_sha256=snapshot.snapshot_sha256,
        system_sha256=report.system_sha256,
        topology_sha256=report.topology_sha256,
        coordinates_sha256=report.coordinates_sha256,
        protonated_fraction_binary64_hex=report.protonated_fraction.hex(),
        deprotonated_fraction_binary64_hex=report.deprotonated_fraction.hex(),
        signals=tuple(signals),
    )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPhProtonationCorpusSnapshot:
    case_results: tuple[MmcifPhProtonationCorpusCaseResult, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPhProtonationCorpusSnapshot("
            f"case_count={len(self.case_results)})"
        )

    @property
    def corpus_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_ph_protonation_corpus_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_ph_protonation_corpus_source_binding())

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID,
                "corpus_projection_sha256": self.corpus_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID,
            "runner_version": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION,
            "case_count": len(self.case_results),
            "cohort_counts": {
                cohort: sum(row.cohort == cohort for row in self.case_results)
                for cohort in sorted({row.cohort for row in self.case_results})
            },
            "selected_state_count": sum(
                bool(row.selected_state) for row in self.case_results
            ),
            "abstention_count": sum(
                row.decision_status == "abstained_population_not_dominant"
                for row in self.case_results
            ),
            "expected_error_count": sum(
                bool(row.error_code) for row in self.case_results
            ),
            "expectation_mismatch_count": 0,
            "corpus_projection_sha256": self.corpus_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def run_mmcif_nonpoly_ph_protonation_corpus() -> (
    MmcifNonpolyPhProtonationCorpusSnapshot
):
    """Execute every frozen real-world supported, abstention, and failure row."""

    cases = mmcif_nonpoly_ph_protonation_corpus_cases()
    results = tuple(_run_case(case) for case in cases)
    if {row.cohort for row in results} != {
        "real_world_supported",
        "real_world_abstention",
        "real_world_failure",
    }:
        raise MmcifNonpolyPhProtonationCorpusError(
            "pH corpus must retain supported abstention and failure cohorts"
        )
    by_id = {row.case_id: row for row in results}
    required_signals = {
        "pubchem_cid_176_ph2_protonated": "ph_selected_state:protonated",
        "pubchem_cid_176_ph7_deprotonated": "ph_selected_state:deprotonated",
        "pubchem_cid_176_ph4_76_abstained": (
            "ph_abstention:minimum_dominant_population_not_met"
        ),
        "pubchem_cid_702_structure_mismatch": "error:reference_structure_mismatch",
        "pubchem_cid_176_reference_crosswire": "error:unsupported_reference_compound",
        "pubchem_cid_176_ph_out_of_bounds": "error:target_ph_out_of_bounds",
        "pubchem_cid_176_source_hydrogen_rejected": (
            "error:source_observed_acidic_hydrogen_not_removable"
        ),
    }
    if set(by_id) != set(required_signals) or any(
        signal not in by_id[case_id].signals
        for case_id, signal in required_signals.items()
    ):
        raise MmcifNonpolyPhProtonationCorpusError("pH corpus evidence signal missing")
    snapshot = MmcifNonpolyPhProtonationCorpusSnapshot(case_results=results)
    if (
        FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SNAPSHOT_SHA256
        and snapshot.snapshot_sha256
        != FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SNAPSHOT_SHA256
    ):
        raise MmcifNonpolyPhProtonationCorpusError(
            "pH corpus snapshot drifted from the frozen review boundary"
        )
    return snapshot


def mmcif_nonpoly_ph_protonation_corpus_projection(
    snapshot: MmcifNonpolyPhProtonationCorpusSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION,
        "case_results": [row.to_dict() for row in snapshot.case_results],
        "case_order": "frozen_manifest_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_ph_protonation_corpus_source_binding() -> dict[str, Any]:
    cases = mmcif_nonpoly_ph_protonation_corpus_cases()
    return {
        "schema_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SOURCE_BINDING_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION,
        "ph_protonation_profile_id": MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
        "ph_protonation_engine_version": MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION,
        "ph_protonation_reference_snapshot_sha256": (
            mmcif_nonpoly_ph_protonation_reference_sha256()
        ),
        "reviewed_sources": [
            dict(row) for row in reviewed_mmcif_nonpoly_ph_protonation_corpus_sources()
        ],
        "cases": [
            {**row.binding_dict(), "case_contract_sha256": row.case_contract_sha256}
            for row in cases
        ],
        "frozen_input_sha256": dict(
            FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256
        ),
        "raw_input_embedded_in_document": False,
        "raw_pubchem_response_embedded_in_document": False,
        "corpus_use": "contract_regression_only_not_parameter_fitting",
    }


def mmcif_nonpoly_ph_protonation_corpus_document(
    snapshot: MmcifNonpolyPhProtonationCorpusSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_ph_protonation_corpus_projection(snapshot)
    binding = mmcif_nonpoly_ph_protonation_corpus_source_binding()
    return {
        "schema_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION,
        "corpus_projection": projection,
        "source_binding": binding,
        "corpus_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_ph_protonation_corpus_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify frozen source, case, result, claim, and snapshot identities."""

    if not isinstance(payload, Mapping):
        raise ValueError("pH protonation corpus document must be a mapping")
    document = dict(payload)
    projection = document.get("corpus_projection")
    binding = document.get("source_binding")
    if (
        document.get("schema_id")
        != MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID
        or document.get("profile_id") != MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID
        or document.get("runner_version")
        != MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION
        or not isinstance(projection, Mapping)
        or not isinstance(binding, Mapping)
    ):
        raise ValueError("pH protonation corpus envelope mismatch")
    projection_dict = dict(projection)
    binding_dict = dict(binding)
    projection_sha = _sha256(projection_dict)
    binding_sha = _sha256(binding_dict)
    if (
        document.get("corpus_projection_sha256") != projection_sha
        or document.get("source_binding_sha256") != binding_sha
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROJECTION_SCHEMA_ID
        or binding_dict != mmcif_nonpoly_ph_protonation_corpus_source_binding()
    ):
        raise ValueError("pH protonation corpus section digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID,
            "corpus_projection_sha256": projection_sha,
            "source_binding_sha256": binding_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("pH protonation corpus snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if (
            document.get(key) is not expected
            or projection_dict.get(key) is not expected
        ):
            raise ValueError("pH protonation corpus claim boundary mismatch")
    rows = projection_dict.get("case_results")
    expected = run_mmcif_nonpoly_ph_protonation_corpus()
    if (
        not isinstance(rows, list)
        or rows != [row.to_dict() for row in expected.case_results]
        or document.get("case_count") != len(rows)
        or document.get("expectation_mismatch_count") != 0
        or document.get("selected_state_count") != 2
        or document.get("abstention_count") != 1
        or document.get("expected_error_count") != 4
    ):
        raise ValueError("pH protonation corpus result mismatch")
    return payload


def mmcif_nonpoly_ph_protonation_corpus_json_bytes(
    snapshot: MmcifNonpolyPhProtonationCorpusSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_ph_protonation_corpus_document(snapshot))


def write_mmcif_nonpoly_ph_protonation_corpus_json(
    path: str | Path,
    snapshot: MmcifNonpolyPhProtonationCorpusSnapshot,
) -> Path:
    """Atomically write the canonical private corpus receipt."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_ph_protonation_corpus_json_bytes(snapshot) + b"\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


__all__ = [
    "FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_INPUT_SHA256",
    "FROZEN_MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SNAPSHOT_SHA256",
    "MMCIF_NONPOLY_PH_PROTONATION_CORPUS_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROFILE_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_CORPUS_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_CORPUS_RUNNER_VERSION",
    "MMCIF_NONPOLY_PH_PROTONATION_CORPUS_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyPhProtonationCorpusError",
    "MmcifNonpolyPhProtonationCorpusSnapshot",
    "MmcifPhProtonationCorpusCase",
    "MmcifPhProtonationCorpusCaseResult",
    "mmcif_nonpoly_ph_protonation_corpus_cases",
    "mmcif_nonpoly_ph_protonation_corpus_document",
    "mmcif_nonpoly_ph_protonation_corpus_json_bytes",
    "mmcif_nonpoly_ph_protonation_corpus_projection",
    "mmcif_nonpoly_ph_protonation_corpus_source_binding",
    "require_mmcif_nonpoly_ph_protonation_corpus_document",
    "reviewed_mmcif_nonpoly_ph_protonation_corpus_sources",
    "run_mmcif_nonpoly_ph_protonation_corpus",
    "write_mmcif_nonpoly_ph_protonation_corpus_json",
]

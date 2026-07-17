"""Frozen real-world identity corpus for bounded tautomer selection.

Factual PubChem identities are manually projected into the bounded mmCIF
contract syntax.  Coordinates are deterministic contract fixtures, not
PubChem conformers.  Raw records and contributor text are not bundled.  The
corpus retains supported selections and expected failures in one signed
denominator and is not parameter-fitting or scientific-validation data.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_nonpoly_all_atom_systems import parse_mmcif_nonpoly_all_atom_systems
from .mmcif_nonpoly_preparation_corpus import (
    MmcifPreparationCorpusAtom,
    MmcifPreparationCorpusBond,
    _corpus_source,
)
from .mmcif_nonpoly_tautomer_selection import (
    MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION,
    MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID,
    MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID,
    MmcifNonpolyTautomerSelectionError,
    apply_mmcif_nonpoly_tautomer_selection,
    mmcif_nonpoly_tautomer_selection_reference_sha256,
)


MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_tautomer_selection_corpus_projection/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_tautomer_selection_corpus_source_binding/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_tautomer_selection_corpus_document/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID = (
    "frozen_pubchem_identity_tautomer_selection_corpus/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION = "1.0.0"
FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SNAPSHOT_SHA256 = (
    "31d3ae0a3f9481400b8116ea17deb0925bb2bd81292a7739105cbe4fd050fc80"
)

PUBCHEM_CID_177_RECORD_FIELDS_SHA256 = (
    "65d6c251528195fe45a34ad3a6ca2d3df84d5d849ee2e79a75b0f60cfbf7de44"
)
PUBCHEM_CID_11199_RECORD_FIELDS_SHA256 = (
    "f3a820615762730371b34021ada9c68284104d23be8bbaee069374dd30fe4e76"
)
PUBCHEM_CID_702_RECORD_FIELDS_SHA256 = (
    "f2676f3c5d888359b6acf624e250752412899e7c70fe7c4edf0ed1998e04a9fd"
)

FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_INPUT_SHA256: Mapping[str, str] = (
    MappingProxyType(
        {
            "pubchem_cid_177_reference_selected": (
                "4b018ee9a313e5fa7a1b7dec0577af65c67cb62adefb128911901593125b87b5"
            ),
            "pubchem_cid_11199_reference_selected": (
                "d4c6956a16ef8cada815b531500b0aa8660c4cea8e3e9996f08b1f3e481b100e"
            ),
            "pubchem_cid_702_structure_mismatch": (
                "e6e0394115ee647db156e1bdbb5036174c2ec589c515567247439dc27850b8e5"
            ),
            "pubchem_cid_11199_source_hydrogen_rejected": (
                "fa52f422e547d979bf3fd04108648a5f41dc0dc437ebbb9141069b171fd4c103"
            ),
            "pubchem_cid_177_reference_crosswire": (
                "4b018ee9a313e5fa7a1b7dec0577af65c67cb62adefb128911901593125b87b5"
            ),
            "pubchem_cid_177_target_instance_missing": (
                "4b018ee9a313e5fa7a1b7dec0577af65c67cb62adefb128911901593125b87b5"
            ),
        }
    )
)


class MmcifNonpolyTautomerSelectionCorpusError(ValueError):
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
        "real_world_tautomer_pair_identities_bound": True,
        "pubchem_cid_177_and_11199_supported_states_executed": True,
        "failure_rows_retained": True,
        "source_and_case_sha256_frozen": True,
        "license_and_provenance_boundary_bound": True,
        "canonical_selected_state_round_trip_bound": True,
        "source_structure_identity_authenticated": False,
        "raw_pubchem_records_bundled": False,
        "pubchem_contributor_text_bundled": False,
        "pubchem_coordinates_used": False,
        "tautomer_population_predicted": False,
        "thermodynamic_preference_inferred": False,
        "corpus_is_parameter_fitting_data": False,
        "parameter_fitting_allowed": False,
        "general_tautomer_selection_validated": False,
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
    records = {
        177: (
            {
                "cid": 177,
                "connectivity_smiles": "CC=O",
                "inchi_key": "IKHGUXGNUITLKF-UHFFFAOYSA-N",
                "molecular_formula": "C2H4O",
                "title": "Acetaldehyde",
            },
            PUBCHEM_CID_177_RECORD_FIELDS_SHA256,
        ),
        11199: (
            {
                "cid": 11199,
                "connectivity_smiles": "C=CO",
                "inchi_key": "IMROMDMJAWUWLK-UHFFFAOYSA-N",
                "molecular_formula": "C2H4O",
                "title": "Vinyl alcohol",
            },
            PUBCHEM_CID_11199_RECORD_FIELDS_SHA256,
        ),
        702: (
            {
                "cid": 702,
                "connectivity_smiles": "CCO",
                "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                "molecular_formula": "C2H6O",
                "title": "Ethanol",
            },
            PUBCHEM_CID_702_RECORD_FIELDS_SHA256,
        ),
    }
    try:
        fields, expected = records[cid]
    except KeyError as exc:
        raise MmcifNonpolyTautomerSelectionCorpusError(
            "unreviewed PubChem record requested"
        ) from exc
    if _sha256(fields) != expected:
        raise MmcifNonpolyTautomerSelectionCorpusError(
            "PubChem record identity fields drifted"
        )
    return {
        "record_id": f"pubchem:cid:{cid}",
        "record_fields": fields,
        "record_fields_sha256": expected,
        "request_url": (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/"
            "property/Title,MolecularFormula,ConnectivitySMILES,InChIKey/JSON"
        ),
        "retrieved_date": "2026-07-17",
        "license_boundary": _source_license_boundary(),
    }


def reviewed_mmcif_nonpoly_tautomer_selection_corpus_sources() -> tuple[
    Mapping[str, Any], ...
]:
    """Return reviewed factual source identities without raw responses."""

    return (_pubchem_record(177), _pubchem_record(11199), _pubchem_record(702))


def _acetaldehyde_source() -> str:
    return _corpus_source(
        (
            MmcifPreparationCorpusAtom("C1", "C"),
            MmcifPreparationCorpusAtom("C2", "C"),
            MmcifPreparationCorpusAtom("O1", "O"),
        ),
        (
            MmcifPreparationCorpusBond("C1", "C2", "SING"),
            MmcifPreparationCorpusBond("C2", "O1", "DOUB"),
        ),
    )


def _vinyl_alcohol_source(*, source_hydroxyl_hydrogen: bool = False) -> str:
    atoms = (
        MmcifPreparationCorpusAtom("C1", "C"),
        MmcifPreparationCorpusAtom("C2", "C"),
        MmcifPreparationCorpusAtom("O1", "O"),
    )
    bonds = (
        MmcifPreparationCorpusBond("C1", "C2", "DOUB"),
        MmcifPreparationCorpusBond("C2", "O1", "SING"),
    )
    if source_hydroxyl_hydrogen:
        atoms = (*atoms, MmcifPreparationCorpusAtom("HO1", "H"))
        bonds = (*bonds, MmcifPreparationCorpusBond("O1", "HO1", "SING"))
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
class MmcifTautomerSelectionCorpusCase:
    case_id: str
    cohort: str
    source_text: str
    input_sha256: str
    source_record_id: str
    source_record_fields_sha256: str
    reference_compound_id: str
    target_instance_override: str
    expected_source_state: str
    expected_error_code: str

    def __repr__(self) -> str:
        return (
            "MmcifTautomerSelectionCorpusCase("
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
            "target_instance_override_sha256": (
                self.target_instance_override if self.target_instance_override else ""
            ),
            "expected_source_state": self.expected_source_state,
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
    reference_compound_id: str = (
        MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
    ),
    target_instance_override: str = "",
    expected_source_state: str = "",
    expected_error_code: str = "",
) -> MmcifTautomerSelectionCorpusCase:
    source_text.encode("ascii")
    digest = hashlib.sha256(source_text.encode("ascii")).hexdigest()
    frozen = FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_INPUT_SHA256.get(
        case_id, ""
    )
    if frozen and digest != frozen:
        raise MmcifNonpolyTautomerSelectionCorpusError(
            f"frozen tautomer corpus input drifted for {case_id}"
        )
    source = _pubchem_record(source_cid)
    return MmcifTautomerSelectionCorpusCase(
        case_id=case_id,
        cohort=cohort,
        source_text=source_text,
        input_sha256=digest,
        source_record_id=str(source["record_id"]),
        source_record_fields_sha256=str(source["record_fields_sha256"]),
        reference_compound_id=reference_compound_id,
        target_instance_override=target_instance_override,
        expected_source_state=expected_source_state,
        expected_error_code=expected_error_code,
    )


def mmcif_nonpoly_tautomer_selection_corpus_cases() -> tuple[
    MmcifTautomerSelectionCorpusCase, ...
]:
    """Return the exact ordered supported and failure corpus."""

    acetaldehyde = _acetaldehyde_source()
    cases = (
        _case(
            "pubchem_cid_177_reference_selected",
            "real_world_supported",
            acetaldehyde,
            source_cid=177,
            expected_source_state="acetaldehyde",
        ),
        _case(
            "pubchem_cid_11199_reference_selected",
            "real_world_supported",
            _vinyl_alcohol_source(),
            source_cid=11199,
            expected_source_state="vinyl_alcohol",
        ),
        _case(
            "pubchem_cid_702_structure_mismatch",
            "real_world_failure",
            _ethanol_source(),
            source_cid=702,
            expected_error_code="reference_structure_mismatch",
        ),
        _case(
            "pubchem_cid_11199_source_hydrogen_rejected",
            "real_world_failure",
            _vinyl_alcohol_source(source_hydroxyl_hydrogen=True),
            source_cid=11199,
            expected_error_code="source_observed_hydrogen_move_forbidden",
        ),
        _case(
            "pubchem_cid_177_reference_crosswire",
            "real_world_failure",
            acetaldehyde,
            source_cid=177,
            reference_compound_id="pubchem:cid:11199",
            expected_error_code="unsupported_reference_compound",
        ),
        _case(
            "pubchem_cid_177_target_instance_missing",
            "real_world_failure",
            acetaldehyde,
            source_cid=177,
            target_instance_override="0" * 64,
            expected_error_code="target_instance_not_found",
        ),
    )
    if tuple(row.case_id for row in cases) != tuple(
        FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_INPUT_SHA256
    ):
        raise MmcifNonpolyTautomerSelectionCorpusError(
            "frozen tautomer corpus case order drifted"
        )
    return cases


@dataclass(frozen=True, slots=True)
class MmcifTautomerSelectionCorpusCaseResult:
    case_id: str
    cohort: str
    input_sha256: str
    case_contract_sha256: str
    source_record_id: str
    source_record_fields_sha256: str
    observed_outcome: str
    matched_source_state: str
    selected_state: str
    error_code: str
    tautomer_selection_snapshot_sha256: str
    system_sha256: str
    topology_sha256: str
    coordinates_sha256: str
    transferred_generated_hydrogen_count: int
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
            "matched_source_state": self.matched_source_state,
            "selected_state": self.selected_state,
            "error_code": self.error_code,
            "tautomer_selection_snapshot_sha256": (
                self.tautomer_selection_snapshot_sha256
            ),
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "transferred_generated_hydrogen_count": (
                self.transferred_generated_hydrogen_count
            ),
            "signals": list(self.signals),
        }


def _run_case(
    case: MmcifTautomerSelectionCorpusCase,
) -> MmcifTautomerSelectionCorpusCaseResult:
    materialization = parse_mmcif_nonpoly_all_atom_systems(case.source_text)
    target = (
        case.target_instance_override
        or materialization.instance_reports[0].instance_identity_sha256
    )
    signals = [
        f"real_world_source:{case.source_record_id}",
        "license_policy:pubchem_source_specific_license_review_required",
        "fixture_transform:manual_bounded_mmcif_projection",
    ]
    try:
        snapshot = apply_mmcif_nonpoly_tautomer_selection(
            case.source_text,
            instance_identity_sha256=target,
            reference_compound_id=case.reference_compound_id,
        )
    except MmcifNonpolyTautomerSelectionError as exc:
        if not case.expected_error_code or exc.code != case.expected_error_code:
            raise MmcifNonpolyTautomerSelectionCorpusError(
                f"unexpected tautomer corpus error for {case.case_id}"
            ) from exc
        signals.extend(("observed_outcome:expected_error", f"error:{exc.code}"))
        return MmcifTautomerSelectionCorpusCaseResult(
            case_id=case.case_id,
            cohort=case.cohort,
            input_sha256=case.input_sha256,
            case_contract_sha256=case.case_contract_sha256,
            source_record_id=case.source_record_id,
            source_record_fields_sha256=case.source_record_fields_sha256,
            observed_outcome="expected_error",
            matched_source_state="",
            selected_state="",
            error_code=exc.code,
            tautomer_selection_snapshot_sha256="",
            system_sha256="",
            topology_sha256="",
            coordinates_sha256="",
            transferred_generated_hydrogen_count=0,
            signals=tuple(signals),
        )
    if case.expected_error_code:
        raise MmcifNonpolyTautomerSelectionCorpusError(
            f"expected tautomer corpus error was not raised for {case.case_id}"
        )
    report = snapshot.report
    if (
        report.matched_source_state != case.expected_source_state
        or report.selected_state != "acetaldehyde"
        or report.decision_status != "reference_canonical_tautomer_selected"
    ):
        raise MmcifNonpolyTautomerSelectionCorpusError(
            f"tautomer corpus decision mismatch for {case.case_id}"
        )
    signals.extend(
        (
            "observed_outcome:expected_decision",
            f"tautomer_source_state:{report.matched_source_state}",
            "tautomer_selected_state:acetaldehyde",
            "canonical_round_trip:verified",
        )
    )
    transferred = 1 if report.matched_source_state == "vinyl_alcohol" else 0
    return MmcifTautomerSelectionCorpusCaseResult(
        case_id=case.case_id,
        cohort=case.cohort,
        input_sha256=case.input_sha256,
        case_contract_sha256=case.case_contract_sha256,
        source_record_id=case.source_record_id,
        source_record_fields_sha256=case.source_record_fields_sha256,
        observed_outcome="expected_decision",
        matched_source_state=report.matched_source_state,
        selected_state=report.selected_state,
        error_code="",
        tautomer_selection_snapshot_sha256=snapshot.snapshot_sha256,
        system_sha256=report.system_sha256,
        topology_sha256=report.topology_sha256,
        coordinates_sha256=report.coordinates_sha256,
        transferred_generated_hydrogen_count=transferred,
        signals=tuple(signals),
    )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyTautomerSelectionCorpusSnapshot:
    case_results: tuple[MmcifTautomerSelectionCorpusCaseResult, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyTautomerSelectionCorpusSnapshot("
            f"case_count={len(self.case_results)})"
        )

    @property
    def corpus_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_tautomer_selection_corpus_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_tautomer_selection_corpus_source_binding())

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": (
                    MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID
                ),
                "corpus_projection_sha256": self.corpus_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID,
            "runner_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION,
            "case_count": len(self.case_results),
            "cohort_counts": {
                cohort: sum(row.cohort == cohort for row in self.case_results)
                for cohort in sorted({row.cohort for row in self.case_results})
            },
            "selected_state_count": sum(
                bool(row.selected_state) for row in self.case_results
            ),
            "transferred_generated_hydrogen_count": sum(
                row.transferred_generated_hydrogen_count for row in self.case_results
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


def run_mmcif_nonpoly_tautomer_selection_corpus() -> (
    MmcifNonpolyTautomerSelectionCorpusSnapshot
):
    """Execute every frozen supported and expected-failure row."""

    cases = mmcif_nonpoly_tautomer_selection_corpus_cases()
    results = tuple(_run_case(case) for case in cases)
    if {row.cohort for row in results} != {
        "real_world_supported",
        "real_world_failure",
    }:
        raise MmcifNonpolyTautomerSelectionCorpusError(
            "tautomer corpus must retain supported and failure cohorts"
        )
    by_id = {row.case_id: row for row in results}
    required_signals = {
        "pubchem_cid_177_reference_selected": ("tautomer_source_state:acetaldehyde"),
        "pubchem_cid_11199_reference_selected": ("tautomer_source_state:vinyl_alcohol"),
        "pubchem_cid_702_structure_mismatch": ("error:reference_structure_mismatch"),
        "pubchem_cid_11199_source_hydrogen_rejected": (
            "error:source_observed_hydrogen_move_forbidden"
        ),
        "pubchem_cid_177_reference_crosswire": ("error:unsupported_reference_compound"),
        "pubchem_cid_177_target_instance_missing": ("error:target_instance_not_found"),
    }
    if set(by_id) != set(required_signals) or any(
        signal not in by_id[case_id].signals
        for case_id, signal in required_signals.items()
    ):
        raise MmcifNonpolyTautomerSelectionCorpusError(
            "tautomer corpus evidence signal missing"
        )
    snapshot = MmcifNonpolyTautomerSelectionCorpusSnapshot(case_results=results)
    if (
        FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SNAPSHOT_SHA256
        and snapshot.snapshot_sha256
        != FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SNAPSHOT_SHA256
    ):
        raise MmcifNonpolyTautomerSelectionCorpusError(
            "tautomer corpus snapshot drifted from the frozen review boundary"
        )
    return snapshot


def mmcif_nonpoly_tautomer_selection_corpus_projection(
    snapshot: MmcifNonpolyTautomerSelectionCorpusSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION,
        "case_results": [row.to_dict() for row in snapshot.case_results],
        "case_order": "frozen_manifest_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_tautomer_selection_corpus_source_binding() -> dict[str, Any]:
    cases = mmcif_nonpoly_tautomer_selection_corpus_cases()
    return {
        "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SOURCE_BINDING_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION,
        "tautomer_selection_profile_id": (MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID),
        "tautomer_selection_engine_version": (
            MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION
        ),
        "tautomer_selection_reference_snapshot_sha256": (
            mmcif_nonpoly_tautomer_selection_reference_sha256()
        ),
        "reviewed_sources": [
            dict(row)
            for row in reviewed_mmcif_nonpoly_tautomer_selection_corpus_sources()
        ],
        "cases": [
            {**row.binding_dict(), "case_contract_sha256": row.case_contract_sha256}
            for row in cases
        ],
        "frozen_input_sha256": dict(
            FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_INPUT_SHA256
        ),
        "raw_input_embedded_in_document": False,
        "raw_pubchem_response_embedded_in_document": False,
        "corpus_use": "contract_regression_only_not_parameter_fitting",
    }


def mmcif_nonpoly_tautomer_selection_corpus_document(
    snapshot: MmcifNonpolyTautomerSelectionCorpusSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_tautomer_selection_corpus_projection(snapshot)
    binding = mmcif_nonpoly_tautomer_selection_corpus_source_binding()
    return {
        "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION,
        "corpus_projection": projection,
        "source_binding": binding,
        "corpus_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_tautomer_selection_corpus_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify frozen sources, cases, results, claims, and snapshot identity."""

    if not isinstance(payload, Mapping):
        raise ValueError("tautomer selection corpus document must be a mapping")
    document = dict(payload)
    projection = document.get("corpus_projection")
    binding = document.get("source_binding")
    if (
        document.get("schema_id")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID
        or document.get("profile_id")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID
        or document.get("runner_version")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION
        or not isinstance(projection, Mapping)
        or not isinstance(binding, Mapping)
    ):
        raise ValueError("tautomer selection corpus envelope mismatch")
    projection_dict = dict(projection)
    binding_dict = dict(binding)
    projection_sha = _sha256(projection_dict)
    binding_sha = _sha256(binding_dict)
    if (
        document.get("corpus_projection_sha256") != projection_sha
        or document.get("source_binding_sha256") != binding_sha
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROJECTION_SCHEMA_ID
        or binding_dict != mmcif_nonpoly_tautomer_selection_corpus_source_binding()
    ):
        raise ValueError("tautomer selection corpus section digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID,
            "corpus_projection_sha256": projection_sha,
            "source_binding_sha256": binding_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("tautomer selection corpus snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if (
            document.get(key) is not expected
            or projection_dict.get(key) is not expected
        ):
            raise ValueError("tautomer selection corpus claim boundary mismatch")
    rows = projection_dict.get("case_results")
    expected = run_mmcif_nonpoly_tautomer_selection_corpus()
    if (
        not isinstance(rows, list)
        or rows != [row.to_dict() for row in expected.case_results]
        or document.get("case_count") != 6
        or document.get("selected_state_count") != 2
        or document.get("transferred_generated_hydrogen_count") != 1
        or document.get("expected_error_count") != 4
        or document.get("expectation_mismatch_count") != 0
    ):
        raise ValueError("tautomer selection corpus result mismatch")
    return payload


def mmcif_nonpoly_tautomer_selection_corpus_json_bytes(
    snapshot: MmcifNonpolyTautomerSelectionCorpusSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_tautomer_selection_corpus_document(snapshot))


def write_mmcif_nonpoly_tautomer_selection_corpus_json(
    path: str | Path,
    snapshot: MmcifNonpolyTautomerSelectionCorpusSnapshot,
) -> Path:
    """Atomically write the canonical private corpus receipt."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_tautomer_selection_corpus_json_bytes(snapshot) + b"\n"
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
        descriptor = -1
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


__all__ = [
    "FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_INPUT_SHA256",
    "FROZEN_MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SNAPSHOT_SHA256",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROFILE_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_RUNNER_VERSION",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_CORPUS_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyTautomerSelectionCorpusError",
    "MmcifNonpolyTautomerSelectionCorpusSnapshot",
    "MmcifTautomerSelectionCorpusCase",
    "MmcifTautomerSelectionCorpusCaseResult",
    "mmcif_nonpoly_tautomer_selection_corpus_cases",
    "mmcif_nonpoly_tautomer_selection_corpus_document",
    "mmcif_nonpoly_tautomer_selection_corpus_json_bytes",
    "mmcif_nonpoly_tautomer_selection_corpus_projection",
    "mmcif_nonpoly_tautomer_selection_corpus_source_binding",
    "require_mmcif_nonpoly_tautomer_selection_corpus_document",
    "reviewed_mmcif_nonpoly_tautomer_selection_corpus_sources",
    "run_mmcif_nonpoly_tautomer_selection_corpus",
    "write_mmcif_nonpoly_tautomer_selection_corpus_json",
]

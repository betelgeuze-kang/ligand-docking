"""Real-molecule chemistry applicability domain over the audited cohort.

The stratification companion already assigns one chemistry stratum per case.
What was missing is a statement of *which real chemistry the cohort actually
covers* and whether out-of-scope chemistry is rejected rather than silently
scored.

This module reads the frozen corpus audit and the internal-oracle
stratification receipt, projects each case onto declared chemistry domain axes
(charge sign, size bucket, element family, aromaticity, ring, stereo, receptor
metal/cofactor context), and reports per-axis coverage with Wilson 95%
intervals over one all-case denominator.

It also computes an out-of-scope recall: every case the corpus audit marked
outside the reference scorer chemistry scope must be a case the pipeline did
not evaluate. A case that is out of scope yet evaluated is recorded as an
admission leak, and any leak forces a failed domain status.

Coverage is an observation about one cohort, not a validated applicability
claim. No molecule is reparameterized, no energy is recomputed, and no
scientific review is performed, so every result stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from . import public_posebusters_corpus_audit as corpus_module
from . import public_posebusters_internal_oracle_stratification as strata_module
from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_generated_pose_evaluation import _case_id
from .public_posebusters_intake import (
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)


POSEBUSTERS_CHEMISTRY_APPLICABILITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_chemistry_applicability_domain/1.0.0"
)
POSEBUSTERS_CHEMISTRY_APPLICABILITY_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_chemistry_applicability_case/1.0.0"
)
POSEBUSTERS_CHEMISTRY_APPLICABILITY_COVERAGE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_chemistry_applicability_coverage/1.0.0"
)
POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_CASES = 308
POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_CHEMISTRY_APPLICABILITY_Z = 1.959963984540054

POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES = (
    "charge_class",
    "element_class",
    "heavy_atom_class",
    "aromaticity_class",
    "ring_class",
    "stereo_class",
    "receptor_context_class",
    "chemistry_ood_status",
)

# Real-chemistry families the objective corpus must exercise, expressed as the
# axis value each family is observed through.
POSEBUSTERS_CHEMISTRY_APPLICABILITY_REQUIRED_FAMILIES = (
    ("neutral_molecule", "charge_class", "neutral"),
    ("anionic_molecule", "charge_class", "negative"),
    ("cationic_molecule", "charge_class", "positive"),
    ("halogen_containing", "element_class", "chno_plus_halogen"),
    ("sulfur_containing", "element_class", "chno_plus_sulfur"),
    ("phosphorus_containing", "element_class", "chno_plus_phosphorus"),
    ("metal_site_control", "receptor_context_class", "metal"),
    ("cofactor_site_control", "receptor_context_class", "cofactor"),
)

POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_posebusters_chemistry_applicability_configuration/1.0.0"
    ),
    "axes": list(POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES),
    "required_family_ids": [
        family for family, _axis, _value in (
            POSEBUSTERS_CHEMISTRY_APPLICABILITY_REQUIRED_FAMILIES
        )
    ],
    "denominator_policy": "every_stratified_case_including_failures",
    "scope_source_policy": "corpus_audit_reference_scorer_scope_status",
    "chemistry_axis_source_policy": "bound_stratification_case_rows_only",
    "out_of_scope_expectation": "out_of_scope_cases_must_not_be_evaluated",
    "confidence_interval_method": "two_sided_wilson_score",
    "confidence_level": POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIDENCE_LEVEL,
    "molecules_reparameterized": False,
    "energies_recomputed": False,
    "coverage_is_cohort_observation_not_validated_applicability": True,
}
POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION
)

POSEBUSTERS_CHEMISTRY_APPLICABILITY_BLOCKERS = (
    "coverage_reflects_one_public_cohort_not_a_validated_chemical_domain",
    "protonation_state_and_tautomer_axes_not_independently_resolved",
    "parameter_provenance_per_atom_not_established",
    "independent_energy_and_force_comparison_missing",
    "conformer_ranking_and_strain_evidence_missing",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_RESULT_FLAGS = {
    "chemistry_axes_projected": True,
    "all_failure_rows_retained": True,
    "molecules_reparameterized": False,
    "energies_recomputed": False,
    "protonation_and_tautomer_axes_resolved": False,
    "parameter_provenance_established": False,
    "independent_external_review_present": False,
    "benchmark_executed": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_LOWERCASE_SHA256 = frozenset("0123456789abcdef")
_EVALUATED_STATUSES = frozenset({"evaluated", "partial_evaluation"})
_IN_SCOPE_STATUS = "admitted_diagnostic"


class PoseBustersChemistryApplicabilityError(ValueError):
    """A bound receipt, chemistry projection, or scope expectation is invalid."""


class _LoadedReceipt:
    __slots__ = ("file_sha256", "payload", "receipt_sha256")

    def __init__(
        self,
        *,
        payload: dict[str, Any],
        receipt_sha256: str,
        file_sha256: str,
    ) -> None:
        self.payload = payload
        self.receipt_sha256 = receipt_sha256
        self.file_sha256 = file_sha256


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersChemistryApplicabilityError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersChemistryApplicabilityError(f"{name} must be a list")
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWERCASE_SHA256 for character in value)
    ):
        raise PoseBustersChemistryApplicabilityError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _text(value: object, *, name: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersChemistryApplicabilityError(
            f"{name} must be bounded single-line text"
        )
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersChemistryApplicabilityError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _json_object_pairs(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersChemistryApplicabilityError(
                "receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersChemistryApplicabilityError(
        f"receipt contains forbidden JSON constant {value}"
    )


def _load_receipt(
    path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str,
) -> _LoadedReceipt:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    try:
        source = _read_exact_regular_file(
            path,
            maximum_bytes=POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_INPUT_BYTES,
        )
        metadata = Path(path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersChemistryApplicabilityError(
            "receipt could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersChemistryApplicabilityError(
            "receipt must be a bounded mode-0600 regular file"
        )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersChemistryApplicabilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersChemistryApplicabilityError(
            "receipt is not canonical ASCII JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersChemistryApplicabilityError(
            "receipt bytes are not canonical"
        )
    payload = dict(raw)
    receipt_sha = _digest(payload.pop("receipt_sha256", None), name="receipt")
    if (
        raw.get("schema_id") != expected_schema_id
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersChemistryApplicabilityError(
            "receipt schema, digest, or pin is invalid"
        )
    for field in ("benchmark_executed", "scientifically_validated", "claim_safe"):
        if raw.get(field) is not False:
            raise PoseBustersChemistryApplicabilityError(
                f"bound receipt must keep {field}=false"
            )
    return _LoadedReceipt(
        payload=raw,
        receipt_sha256=receipt_sha,
        file_sha256=hashlib.sha256(source).hexdigest(),
    )


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise PoseBustersChemistryApplicabilityError(
            "Wilson interval counts are invalid"
        )
    estimate = numerator / denominator
    z = POSEBUSTERS_CHEMISTRY_APPLICABILITY_Z
    adjustment = 1.0 + z * z / denominator
    center = (estimate + z * z / (2.0 * denominator)) / adjustment
    margin = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / denominator
            + z * z / (4.0 * denominator * denominator)
        )
        / adjustment
    )
    low = min(max(0.0, center - margin), estimate)
    high = max(min(1.0, center + margin), estimate)
    return low, high


def _scope_projection(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = _list(payload.get("case_rows"), name="corpus audit case rows")
    if not rows or len(rows) > POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_CASES:
        raise PoseBustersChemistryApplicabilityError(
            "corpus audit case projection is invalid"
        )
    projection: dict[str, dict[str, Any]] = {}
    for item in rows:
        row = _mapping(item, name="corpus audit case row")
        case = _case_id(row.get("case_id"))
        if case in projection:
            raise PoseBustersChemistryApplicabilityError(
                "corpus audit case rows must be unique"
            )
        scope_status = _text(
            row.get("reference_scorer_scope_status"),
            name="reference scorer scope status",
        )
        blockers = tuple(
            _text(value, name="scope blocker")
            for value in _list(
                row.get("reference_scorer_scope_blockers", []),
                name="scope blockers",
            )
        )
        projection[case] = {
            "reference_scorer_scope_status": scope_status,
            "in_reference_scorer_scope": scope_status == _IN_SCOPE_STATUS,
            "scope_blocker_count": len(blockers),
            "scope_blockers": list(blockers),
        }
    return projection


def _chemistry_projection(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = _list(payload.get("case_rows"), name="stratification case rows")
    if (
        not rows
        or len(rows) > POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_CASES
        or payload.get("all_case_denominator") != len(rows)
    ):
        raise PoseBustersChemistryApplicabilityError(
            "stratification case projection is invalid"
        )
    projection: dict[str, dict[str, Any]] = {}
    for item in rows:
        row = _mapping(item, name="stratification case row")
        case = _case_id(row.get("case_id"))
        if case in projection:
            raise PoseBustersChemistryApplicabilityError(
                "stratification case rows must be unique"
            )
        axes = {
            axis: _text(row.get(axis), name=f"stratification {axis}")
            for axis in POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES
        }
        oracle_status = _text(
            row.get("oracle_status"),
            name="stratification oracle status",
        )
        projection[case] = {
            **axes,
            "oracle_status": oracle_status,
            "case_evaluated": oracle_status in _EVALUATED_STATUSES,
            "chemistry_stratum_id": _text(
                row.get("chemistry_stratum_id"),
                name="chemistry stratum ID",
                maximum=1024,
            ),
            "ligand_formal_charge": _integer(
                row.get("ligand_formal_charge"),
                name="ligand formal charge",
                minimum=-64,
            ),
        }
    return projection


def _axis_coverage_rows(
    case_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    denominator = len(case_rows)
    rows: list[dict[str, Any]] = []
    for axis in POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES:
        values = sorted({str(row[axis]) for row in case_rows})
        for value in values:
            numerator = sum(1 for row in case_rows if row[axis] == value)
            evaluated = sum(
                1 for row in case_rows if row[axis] == value and row["case_evaluated"]
            )
            low, high = _wilson_interval(numerator, denominator)
            evaluated_low, evaluated_high = _wilson_interval(evaluated, numerator)
            rows.append(
                {
                    "schema_id": (
                        POSEBUSTERS_CHEMISTRY_APPLICABILITY_COVERAGE_SCHEMA_ID
                    ),
                    "axis": axis,
                    "axis_value": value,
                    "case_count": numerator,
                    "all_case_denominator": denominator,
                    "cohort_share_binary64_hex": (numerator / denominator).hex(),
                    "cohort_share_confidence_interval_low_binary64_hex": low.hex(),
                    "cohort_share_confidence_interval_high_binary64_hex": high.hex(),
                    "evaluated_case_count": evaluated,
                    "evaluated_rate_binary64_hex": (evaluated / numerator).hex(),
                    "evaluated_rate_confidence_interval_low_binary64_hex": (
                        evaluated_low.hex()
                    ),
                    "evaluated_rate_confidence_interval_high_binary64_hex": (
                        evaluated_high.hex()
                    ),
                    "confidence_interval_method": "two_sided_wilson_score",
                }
            )
    return rows


def _family_rows(case_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_id, axis, axis_value in (
        POSEBUSTERS_CHEMISTRY_APPLICABILITY_REQUIRED_FAMILIES
    ):
        matched = [row for row in case_rows if row[axis] == axis_value]
        evaluated = sum(1 for row in matched if row["case_evaluated"])
        rows.append(
            {
                "family_id": family_id,
                "axis": axis,
                "axis_value": axis_value,
                "case_count": len(matched),
                "evaluated_case_count": evaluated,
                "present_in_cohort": bool(matched),
            }
        )
    return rows


def _source_members() -> tuple[tuple[str, str], ...]:
    paths = (
        (
            "posebusters_chemistry_applicability_domain",
            Path(__file__).resolve(),
        ),
        (
            "posebusters_corpus_audit",
            Path(corpus_module.__file__).resolve(),
        ),
        (
            "posebusters_internal_oracle_stratification",
            Path(strata_module.__file__).resolve(),
        ),
    )
    return tuple((role, _source_file_sha256(path)) for role, path in paths)


def _atomic_write_new(path: str | os.PathLike[str], source: bytes) -> Path:
    if len(source) > POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_RECEIPT_BYTES:
        raise PoseBustersChemistryApplicabilityError(
            "applicability receipt exceeds its byte bound"
        )
    output = Path(path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersChemistryApplicabilityError(
                "applicability output already exists"
            ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


class PoseBustersChemistryApplicabilityReceipt:
    """Canonical, claim-closed chemistry applicability-domain observation."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        if "receipt_sha256" in payload:
            raise PoseBustersChemistryApplicabilityError(
                "receipt payload cannot predefine its digest"
            )
        self._payload_bytes = _canonical_bytes(dict(payload))

    @property
    def fingerprint_sha256(self) -> str:
        return hashlib.sha256(self._payload_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self._payload_bytes)
        payload["receipt_sha256"] = self.fingerprint_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(output_path, self.canonical_bytes())


def _build_domain(
    corpus_audit_receipt_path: str | os.PathLike[str],
    stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_corpus_audit_receipt_sha256: str,
    expected_stratification_receipt_sha256: str,
) -> PoseBustersChemistryApplicabilityReceipt:
    corpus = _load_receipt(
        corpus_audit_receipt_path,
        expected_schema_id=corpus_module.POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID,
        expected_receipt_sha256=expected_corpus_audit_receipt_sha256,
    )
    strata = _load_receipt(
        stratification_receipt_path,
        expected_schema_id=(
            strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_stratification_receipt_sha256,
    )
    if strata.payload.get("corpus_audit_receipt_sha256") != corpus.receipt_sha256:
        raise PoseBustersChemistryApplicabilityError(
            "stratification receipt does not name the bound corpus audit"
        )
    scope = _scope_projection(corpus.payload)
    chemistry = _chemistry_projection(strata.payload)
    missing = sorted(set(chemistry) - set(scope))
    if missing:
        raise PoseBustersChemistryApplicabilityError(
            f"corpus audit omits stratified case {missing[0]}"
        )
    case_rows: list[dict[str, Any]] = []
    for case in sorted(chemistry):
        chemistry_row = chemistry[case]
        scope_row = scope[case]
        in_scope = bool(scope_row["in_reference_scorer_scope"])
        evaluated = bool(chemistry_row["case_evaluated"])
        case_rows.append(
            {
                "schema_id": POSEBUSTERS_CHEMISTRY_APPLICABILITY_CASE_SCHEMA_ID,
                "case_id": case,
                **{
                    axis: chemistry_row[axis]
                    for axis in POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES
                },
                "chemistry_stratum_id": chemistry_row["chemistry_stratum_id"],
                "ligand_formal_charge": chemistry_row["ligand_formal_charge"],
                "oracle_status": chemistry_row["oracle_status"],
                "case_evaluated": evaluated,
                "reference_scorer_scope_status": (
                    scope_row["reference_scorer_scope_status"]
                ),
                "in_reference_scorer_scope": in_scope,
                "scope_blocker_count": scope_row["scope_blocker_count"],
                "scope_blockers": scope_row["scope_blockers"],
                "out_of_scope_rejected": (not in_scope) and (not evaluated),
                "out_of_scope_admission_leak": (not in_scope) and evaluated,
            }
        )
    denominator = len(case_rows)
    out_of_scope = [row for row in case_rows if not row["in_reference_scorer_scope"]]
    leaks = [row["case_id"] for row in out_of_scope if row["out_of_scope_admission_leak"]]
    rejected = len(out_of_scope) - len(leaks)
    in_scope_rows = [row for row in case_rows if row["in_reference_scorer_scope"]]
    families = _family_rows(case_rows)
    absent_families = [row["family_id"] for row in families if not row["present_in_cohort"]]
    recall_low, recall_high = (
        _wilson_interval(rejected, len(out_of_scope))
        if out_of_scope
        else (0.0, 0.0)
    )
    source_members = _source_members()
    payload = {
        "schema_id": POSEBUSTERS_CHEMISTRY_APPLICABILITY_SCHEMA_ID,
        "status": (
            "domain_observed" if not leaks else "domain_failed_admission_leak"
        ),
        "corpus_audit_receipt_sha256": corpus.receipt_sha256,
        "corpus_audit_receipt_file_sha256": corpus.file_sha256,
        "stratification_receipt_sha256": strata.receipt_sha256,
        "stratification_receipt_file_sha256": strata.file_sha256,
        "all_case_denominator": denominator,
        "case_rows": case_rows,
        "axis_coverage_rows": _axis_coverage_rows(case_rows),
        "required_family_rows": families,
        "absent_required_family_ids": absent_families,
        "every_required_family_present": not absent_families,
        "in_reference_scorer_scope_case_count": len(in_scope_rows),
        "out_of_reference_scorer_scope_case_count": len(out_of_scope),
        "out_of_scope_rejected_case_count": rejected,
        "out_of_scope_admission_leak_case_ids": leaks,
        "out_of_scope_rejection_recall_binary64_hex": (
            (rejected / len(out_of_scope)).hex() if out_of_scope else None
        ),
        "out_of_scope_rejection_recall_confidence_interval_low_binary64_hex": (
            recall_low.hex() if out_of_scope else None
        ),
        "out_of_scope_rejection_recall_confidence_interval_high_binary64_hex": (
            recall_high.hex() if out_of_scope else None
        ),
        "out_of_scope_admission_leak_free": not leaks,
        "implementation_source_members": dict(source_members),
        "implementation_source_sha256": _canonical_sha256(dict(source_members)),
        "configuration": POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION_SHA256
        ),
        "scientific_blockers": list(
            POSEBUSTERS_CHEMISTRY_APPLICABILITY_BLOCKERS
        ),
        **_RESULT_FLAGS,
    }
    return PoseBustersChemistryApplicabilityReceipt(payload)


def materialize_posebusters_chemistry_applicability_domain(
    corpus_audit_receipt_path: str | os.PathLike[str],
    stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_corpus_audit_receipt_sha256: str,
    expected_stratification_receipt_sha256: str,
) -> PoseBustersChemistryApplicabilityReceipt:
    """Observe the cohort's real-chemistry coverage and out-of-scope rejection."""

    return _build_domain(
        corpus_audit_receipt_path,
        stratification_receipt_path,
        expected_corpus_audit_receipt_sha256=(
            expected_corpus_audit_receipt_sha256
        ),
        expected_stratification_receipt_sha256=(
            expected_stratification_receipt_sha256
        ),
    )


def verify_posebusters_chemistry_applicability_receipt(
    applicability_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_applicability_receipt_sha256: str,
    expected_corpus_audit_receipt_sha256: str,
    expected_stratification_receipt_sha256: str,
) -> PoseBustersChemistryApplicabilityReceipt:
    """Recompute the domain observation and require exact reconstruction."""

    loaded = _load_receipt(
        applicability_receipt_path,
        expected_schema_id=POSEBUSTERS_CHEMISTRY_APPLICABILITY_SCHEMA_ID,
        expected_receipt_sha256=expected_applicability_receipt_sha256,
    )
    expected = _build_domain(
        corpus_audit_receipt_path,
        stratification_receipt_path,
        expected_corpus_audit_receipt_sha256=(
            expected_corpus_audit_receipt_sha256
        ),
        expected_stratification_receipt_sha256=(
            expected_stratification_receipt_sha256
        ),
    )
    if loaded.receipt_sha256 != expected.fingerprint_sha256:
        raise PoseBustersChemistryApplicabilityError(
            "applicability receipt failed exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-chemistry-domain",
        description=(
            "Observe real-molecule chemistry coverage and out-of-scope "
            "rejection for the audited PoseBusters cohort without opening a "
            "validated applicability claim."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    verify = subparsers.add_parser("verify")
    for command in (materialize, verify):
        command.add_argument("--corpus-audit-receipt", required=True)
        command.add_argument("--stratification-receipt", required=True)
        command.add_argument(
            "--expected-corpus-audit-receipt-sha256",
            required=True,
        )
        command.add_argument(
            "--expected-stratification-receipt-sha256",
            required=True,
        )
    materialize.add_argument("--output", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--expected-applicability-receipt-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "stratification_receipt_path": args.stratification_receipt,
        "expected_corpus_audit_receipt_sha256": (
            args.expected_corpus_audit_receipt_sha256
        ),
        "expected_stratification_receipt_sha256": (
            args.expected_stratification_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_chemistry_applicability_domain(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_chemistry_applicability_receipt(
            applicability_receipt_path=args.receipt,
            expected_applicability_receipt_sha256=(
                args.expected_applicability_receipt_sha256
            ),
            **common,
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "status": payload["status"],
                "all_case_denominator": payload["all_case_denominator"],
                "out_of_scope_admission_leak_free": payload[
                    "out_of_scope_admission_leak_free"
                ],
                "every_required_family_present": payload[
                    "every_required_family_present"
                ],
                "scientifically_validated": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_AXES",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_BLOCKERS",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_CASE_SCHEMA_ID",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIDENCE_LEVEL",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_CONFIGURATION_SHA256",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_COVERAGE_SCHEMA_ID",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_CASES",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_INPUT_BYTES",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_REQUIRED_FAMILIES",
    "POSEBUSTERS_CHEMISTRY_APPLICABILITY_SCHEMA_ID",
    "PoseBustersChemistryApplicabilityError",
    "PoseBustersChemistryApplicabilityReceipt",
    "main",
    "materialize_posebusters_chemistry_applicability_domain",
    "verify_posebusters_chemistry_applicability_receipt",
]

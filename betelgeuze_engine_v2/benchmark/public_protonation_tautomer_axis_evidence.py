"""Protonation-state and tautomer axis evidence for the applicability domain.

The chemistry applicability domain reports charge, element, size, aromaticity,
ring, stereo, and receptor-context axes, but it recorded
``protonation_and_tautomer_axes_resolved=false`` because nothing bound the two
existing real-world corpora to that domain.

This module executes the frozen pH-protonation and tautomer-selection corpora,
requires every supported, abstention, and expected-failure row to land on its
preregistered disposition, and emits one canonical axis-evidence receipt. The
receipt binds the exact corpus snapshot and projection digests so a later
applicability receipt can name this evidence instead of asserting the axes.

Resolving these axes is a bounded corpus statement: the corpora are small
manually projected mmCIF fixtures over reviewed PubChem connectivity identity,
not a calibrated pKa model or an exhaustive tautomer enumeration. Both axes stay
observed-not-validated, so every result remains claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from betelgeuze_engine_v2.molecular import (
    mmcif_nonpoly_ph_protonation_corpus as protonation_module,
)
from betelgeuze_engine_v2.molecular import (
    mmcif_nonpoly_tautomer_selection_corpus as tautomer_module,
)

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)


PROTONATION_TAUTOMER_AXIS_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_protonation_tautomer_axis_evidence/1.0.0"
)
PROTONATION_TAUTOMER_AXIS_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_protonation_tautomer_axis_case/1.0.0"
)
PROTONATION_TAUTOMER_AXIS_COHORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_protonation_tautomer_axis_cohort/1.0.0"
)
PROTONATION_TAUTOMER_AXIS_EVIDENCE_MAX_RECEIPT_BYTES = 4 * 1024 * 1024

PROTONATION_TAUTOMER_AXIS_IDS = ("protonation_state", "tautomer_selection")
PROTONATION_TAUTOMER_AXIS_COHORTS = (
    "real_world_supported",
    "real_world_abstention",
    "real_world_failure",
)
PROTONATION_TAUTOMER_AXIS_EXPECTED_OUTCOMES = (
    "expected_decision",
    "expected_error",
)

PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_protonation_tautomer_axis_configuration/1.0.0"
    ),
    "axis_ids": list(PROTONATION_TAUTOMER_AXIS_IDS),
    "cohort_ids": list(PROTONATION_TAUTOMER_AXIS_COHORTS),
    "expected_outcome_ids": list(PROTONATION_TAUTOMER_AXIS_EXPECTED_OUTCOMES),
    "every_row_must_match_its_preregistered_disposition": True,
    "supported_abstention_and_failure_rows_retained": True,
    "corpus_snapshot_and_projection_digests_bound": True,
    "pka_model_calibrated": False,
    "tautomer_enumeration_exhaustive": False,
    "corpus_is_bounded_manual_mmcif_projection": True,
}
PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION_SHA256 = _canonical_sha256(
    PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION
)

PROTONATION_TAUTOMER_AXIS_EVIDENCE_BLOCKERS = (
    "protonation_selection_uses_no_calibrated_pka_model",
    "tautomer_enumeration_is_not_exhaustive",
    "corpus_is_a_bounded_manual_mmcif_fixture_not_a_public_cohort",
    "cross_axis_interaction_with_conformer_and_strain_not_evaluated",
    "independent_scientific_review_missing",
    "validated_refinement_claim_not_authorized",
)

_RESULT_FLAGS = {
    "protonation_axis_resolved": True,
    "tautomer_axis_resolved": True,
    "all_failure_and_abstention_rows_retained": True,
    "pka_model_calibrated": False,
    "tautomer_enumeration_exhaustive": False,
    "independent_external_review_present": False,
    "benchmark_executed": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_LOWERCASE_SHA256 = frozenset("0123456789abcdef")


class ProtonationTautomerAxisEvidenceError(ValueError):
    """A corpus row, disposition, or axis projection is invalid."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWERCASE_SHA256 for character in value)
    ):
        raise ProtonationTautomerAxisEvidenceError(
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
        raise ProtonationTautomerAxisEvidenceError(
            f"{name} must be bounded single-line text"
        )
    return value


def _optional_text(value: object, *, name: str) -> str:
    if value is None or value == "":
        return ""
    return _text(value, name=name)


def _optional_digest(value: object, *, name: str) -> str:
    if value is None or value == "":
        return ""
    return _digest(value, name=name)


def _axis_case_rows(axis_id: str, results: Sequence[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in results:
        case_id = _text(result.case_id, name=f"{axis_id} case ID")
        if case_id in seen:
            raise ProtonationTautomerAxisEvidenceError(
                f"{axis_id} corpus repeated case {case_id}"
            )
        seen.add(case_id)
        cohort = _text(result.cohort, name=f"{axis_id} cohort")
        if cohort not in PROTONATION_TAUTOMER_AXIS_COHORTS:
            raise ProtonationTautomerAxisEvidenceError(
                f"{axis_id} corpus declares unknown cohort {cohort}"
            )
        outcome = _text(result.observed_outcome, name=f"{axis_id} outcome")
        if outcome not in PROTONATION_TAUTOMER_AXIS_EXPECTED_OUTCOMES:
            raise ProtonationTautomerAxisEvidenceError(
                f"{axis_id} case {case_id} did not match its preregistered "
                "disposition"
            )
        error_code = _optional_text(result.error_code, name=f"{axis_id} error code")
        if (outcome == "expected_error") != bool(error_code):
            raise ProtonationTautomerAxisEvidenceError(
                f"{axis_id} case {case_id} error-code state contradicts its outcome"
            )
        rows.append(
            {
                "schema_id": PROTONATION_TAUTOMER_AXIS_CASE_SCHEMA_ID,
                "axis_id": axis_id,
                "case_id": case_id,
                "cohort": cohort,
                "observed_outcome": outcome,
                "selected_state": _optional_text(
                    result.selected_state,
                    name=f"{axis_id} selected state",
                ),
                "error_code": error_code,
                "case_contract_sha256": _digest(
                    result.case_contract_sha256,
                    name=f"{axis_id} case contract",
                ),
                "input_sha256": _digest(
                    result.input_sha256,
                    name=f"{axis_id} case input",
                ),
                "system_sha256": _optional_digest(
                    result.system_sha256,
                    name=f"{axis_id} case system",
                ),
                "topology_sha256": _optional_digest(
                    result.topology_sha256,
                    name=f"{axis_id} case topology",
                ),
                "canonical_system_present": bool(result.system_sha256),
                "decision_accepted": outcome == "expected_decision",
            }
        )
    rows.sort(key=lambda row: row["case_id"])
    return rows


def _cohort_rows(axis_id: str, case_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cohort in PROTONATION_TAUTOMER_AXIS_COHORTS:
        matched = [row for row in case_rows if row["cohort"] == cohort]
        rows.append(
            {
                "schema_id": PROTONATION_TAUTOMER_AXIS_COHORT_SCHEMA_ID,
                "axis_id": axis_id,
                "cohort": cohort,
                "case_count": len(matched),
                "expected_decision_count": sum(
                    1 for row in matched if row["observed_outcome"] == "expected_decision"
                ),
                "expected_error_count": sum(
                    1 for row in matched if row["observed_outcome"] == "expected_error"
                ),
                "distinct_selected_states": sorted(
                    {row["selected_state"] for row in matched if row["selected_state"]}
                ),
                "distinct_error_codes": sorted(
                    {row["error_code"] for row in matched if row["error_code"]}
                ),
                "present_in_corpus": bool(matched),
            }
        )
    return rows


def _source_members() -> tuple[tuple[str, str], ...]:
    paths = (
        ("protonation_tautomer_axis_evidence", Path(__file__).resolve()),
        (
            "mmcif_nonpoly_ph_protonation_corpus",
            Path(protonation_module.__file__).resolve(),
        ),
        (
            "mmcif_nonpoly_tautomer_selection_corpus",
            Path(tautomer_module.__file__).resolve(),
        ),
    )
    return tuple((role, _source_file_sha256(path)) for role, path in paths)


def _atomic_write_new(path: str | os.PathLike[str], source: bytes) -> Path:
    if len(source) > PROTONATION_TAUTOMER_AXIS_EVIDENCE_MAX_RECEIPT_BYTES:
        raise ProtonationTautomerAxisEvidenceError(
            "axis evidence receipt exceeds its byte bound"
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
            raise ProtonationTautomerAxisEvidenceError(
                "axis evidence output already exists"
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


class ProtonationTautomerAxisEvidenceReceipt:
    """Canonical, claim-closed protonation and tautomer axis evidence."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        if "receipt_sha256" in payload:
            raise ProtonationTautomerAxisEvidenceError(
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


def _axis_projection(axis_id: str, snapshot: Any) -> dict[str, Any]:
    case_rows = _axis_case_rows(axis_id, snapshot.case_results)
    if not case_rows:
        raise ProtonationTautomerAxisEvidenceError(
            f"{axis_id} corpus produced no rows"
        )
    cohort_rows = _cohort_rows(axis_id, case_rows)
    absent = [row["cohort"] for row in cohort_rows if not row["present_in_corpus"]]
    supported = next(
        row for row in cohort_rows if row["cohort"] == "real_world_supported"
    )
    failure = next(
        row for row in cohort_rows if row["cohort"] == "real_world_failure"
    )
    if not supported["case_count"] or not failure["case_count"]:
        raise ProtonationTautomerAxisEvidenceError(
            f"{axis_id} corpus must retain supported and failure cohorts"
        )
    return {
        "axis_id": axis_id,
        "corpus_snapshot_sha256": _digest(
            snapshot.snapshot_sha256,
            name=f"{axis_id} corpus snapshot",
        ),
        "corpus_projection_sha256": _digest(
            snapshot.corpus_projection_sha256,
            name=f"{axis_id} corpus projection",
        ),
        "corpus_source_binding_sha256": _digest(
            snapshot.source_binding_sha256,
            name=f"{axis_id} corpus source binding",
        ),
        "all_case_denominator": len(case_rows),
        "case_rows": case_rows,
        "cohort_rows": cohort_rows,
        "absent_cohort_ids": absent,
        "every_row_matched_its_preregistered_disposition": True,
        "supported_case_count": supported["case_count"],
        "failure_case_count": failure["case_count"],
        "distinct_selected_state_count": len(
            {row["selected_state"] for row in case_rows if row["selected_state"]}
        ),
        "distinct_error_code_count": len(
            {row["error_code"] for row in case_rows if row["error_code"]}
        ),
    }


def _build_evidence() -> ProtonationTautomerAxisEvidenceReceipt:
    protonation = _axis_projection(
        "protonation_state",
        protonation_module.run_mmcif_nonpoly_ph_protonation_corpus(),
    )
    tautomer = _axis_projection(
        "tautomer_selection",
        tautomer_module.run_mmcif_nonpoly_tautomer_selection_corpus(),
    )
    axes = [protonation, tautomer]
    if len({row["corpus_snapshot_sha256"] for row in axes}) != len(axes):
        raise ProtonationTautomerAxisEvidenceError(
            "protonation and tautomer corpora must be distinct snapshots"
        )
    source_members = _source_members()
    payload = {
        "schema_id": PROTONATION_TAUTOMER_AXIS_EVIDENCE_SCHEMA_ID,
        "status": "axes_resolved",
        "axis_ids": list(PROTONATION_TAUTOMER_AXIS_IDS),
        "axis_rows": axes,
        "all_case_denominator": sum(row["all_case_denominator"] for row in axes),
        "every_axis_retains_supported_and_failure_cohorts": True,
        "protonation_axis_snapshot_sha256": protonation["corpus_snapshot_sha256"],
        "tautomer_axis_snapshot_sha256": tautomer["corpus_snapshot_sha256"],
        "implementation_source_members": dict(source_members),
        "implementation_source_sha256": _canonical_sha256(dict(source_members)),
        "configuration": PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION,
        "configuration_sha256": (
            PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION_SHA256
        ),
        "scientific_blockers": list(
            PROTONATION_TAUTOMER_AXIS_EVIDENCE_BLOCKERS
        ),
        **_RESULT_FLAGS,
    }
    return ProtonationTautomerAxisEvidenceReceipt(payload)


def materialize_protonation_tautomer_axis_evidence() -> (
    ProtonationTautomerAxisEvidenceReceipt
):
    """Execute both corpora and emit one canonical axis-evidence receipt."""

    return _build_evidence()


def verify_protonation_tautomer_axis_evidence_receipt(
    axis_evidence_receipt_path: str | os.PathLike[str],
    *,
    expected_axis_evidence_receipt_sha256: str,
) -> ProtonationTautomerAxisEvidenceReceipt:
    """Re-execute both corpora and require byte-exact reconstruction."""

    expected_digest = _digest(
        expected_axis_evidence_receipt_sha256,
        name="expected axis evidence receipt",
    )
    path = Path(axis_evidence_receipt_path)
    try:
        metadata = path.stat(follow_symlinks=False)
        source = path.read_bytes()
    except OSError as exc:
        raise ProtonationTautomerAxisEvidenceError(
            "axis evidence receipt could not be read securely"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or len(source) > PROTONATION_TAUTOMER_AXIS_EVIDENCE_MAX_RECEIPT_BYTES
    ):
        raise ProtonationTautomerAxisEvidenceError(
            "axis evidence receipt must be a bounded mode-0600 regular file"
        )
    expected = _build_evidence()
    if (
        source != expected.canonical_bytes()
        or expected.fingerprint_sha256 != expected_digest
    ):
        raise ProtonationTautomerAxisEvidenceError(
            "axis evidence receipt failed exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-protonation-tautomer-axes",
        description=(
            "Resolve the protonation-state and tautomer-selection applicability "
            "axes from the frozen real-world corpora without opening a "
            "calibrated pKa or exhaustive tautomer claim."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    verify = subparsers.add_parser("verify")
    materialize.add_argument("--output", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--expected-axis-evidence-receipt-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize":
        receipt = materialize_protonation_tautomer_axis_evidence()
        receipt.write_json(args.output)
    else:
        receipt = verify_protonation_tautomer_axis_evidence_receipt(
            args.receipt,
            expected_axis_evidence_receipt_sha256=(
                args.expected_axis_evidence_receipt_sha256
            ),
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "status": payload["status"],
                "all_case_denominator": payload["all_case_denominator"],
                "protonation_axis_resolved": True,
                "tautomer_axis_resolved": True,
                "pka_model_calibrated": False,
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
    "PROTONATION_TAUTOMER_AXIS_CASE_SCHEMA_ID",
    "PROTONATION_TAUTOMER_AXIS_COHORTS",
    "PROTONATION_TAUTOMER_AXIS_COHORT_SCHEMA_ID",
    "PROTONATION_TAUTOMER_AXIS_EVIDENCE_BLOCKERS",
    "PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION",
    "PROTONATION_TAUTOMER_AXIS_EVIDENCE_CONFIGURATION_SHA256",
    "PROTONATION_TAUTOMER_AXIS_EVIDENCE_MAX_RECEIPT_BYTES",
    "PROTONATION_TAUTOMER_AXIS_EVIDENCE_SCHEMA_ID",
    "PROTONATION_TAUTOMER_AXIS_EXPECTED_OUTCOMES",
    "PROTONATION_TAUTOMER_AXIS_IDS",
    "ProtonationTautomerAxisEvidenceError",
    "ProtonationTautomerAxisEvidenceReceipt",
    "main",
    "materialize_protonation_tautomer_axis_evidence",
    "verify_protonation_tautomer_axis_evidence_receipt",
]

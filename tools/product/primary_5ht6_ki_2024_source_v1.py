"""Bounded, source-only ledger for three published human 5-HT6 Ki rows.

This is a reviewed transcription of the cited paper, not a ChEMBL activity
capture or an independent authentication of the experiment. It deliberately
has no role assignment, prepared state, fit admission, or comparison route.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import stat


SCHEMA = "primary_human_5ht6_ki_2024_source_ledger_v1"
RECEIPT_SCHEMA = "primary_human_5ht6_ki_2024_source_verification_v1"
PDF_SHA256 = "4bd52d8bbb3c216b3d6976d17584a2d00b6608643df50278b80e7b94f4ab02ca"
MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_LEDGER_BYTES = 64 * 1024

EXPECTED_LEDGER = {
    "schema_version": SCHEMA,
    "source": {
        "doi": "10.3390/ijms251910287",
        "pdf_url": (
            "https://ruj.uj.edu.pl/server/api/core/bitstreams/"
            "db463f70-771f-42ec-8060-ab5423b38e45/content"
        ),
        "pdf_sha256": PDF_SHA256,
        "license_notice": "CC BY 4.0",
        "table_page": 10,
        "pharmacophore_threshold_page": 19,
        "assay_method_pages": [39, 40],
        "assay_method_summary": (
            "Human 5-HT6 HEK293 membranes; [3H]-LSD radioligand competition; "
            "Cheng-Prusoff Ki"
        ),
    },
    "threshold_projection": {
        "context": "paper_pharmacophore_model_only",
        "active_pki_at_or_above": "6.7",
        "inactive_pki_at_or_below": "6.3",
        "one_sd_semantics": "reported_SD_interval_not_confidence_interval",
    },
    "rows": [
        {
            "paper_row_id": "PR49",
            "experimental_pages": [30, 31],
            "exact_published_name": (
                "N-(8-chloro-3,4-dihydroquinazolin-2-yl)"
                "naphthalene-1-sulfonamide"
            ),
            "reported_ki_mean": "0.077",
            "reported_ki_sd": "0.018",
            "reported_ki_unit": "µM",
            "reported_uncertainty_kind": "SD",
            "reported_purity_percent": "92",
            "proposed_neutral_graph": {
                "canonical_isomeric_smiles": (
                    "O=S(=O)(NC1=Nc2c(Cl)cccc2CN1)c1cccc2ccccc12"
                ),
                "formula": "C18H14ClN3O2S",
                "inchikey": "QQYXUBNTHMWUNC-UHFFFAOYSA-N",
                "formal_charge": 0,
                "fragment_count": 1,
                "assayed_microstate_verified": False,
            },
            "threshold_derived_class_at_mean": "active",
            "threshold_derived_class_across_one_sd": "active",
            "assigned_role": None,
            "prepared_state_origin": None,
            "fit_admitted": False,
        },
        {
            "paper_row_id": "PR58",
            "experimental_pages": [33],
            "exact_published_name": (
                "N-(5-methoxy-3,4-dihydroquinazolin-2-yl)"
                "naphthalene-1-sulfonamide"
            ),
            "reported_ki_mean": "0.172",
            "reported_ki_sd": "0.041",
            "reported_ki_unit": "µM",
            "reported_uncertainty_kind": "SD",
            "reported_purity_percent": "99",
            "proposed_neutral_graph": {
                "canonical_isomeric_smiles": (
                    "COc1cccc2c1CNC(NS(=O)(=O)c1cccc3ccccc13)=N2"
                ),
                "formula": "C19H17N3O3S",
                "inchikey": "QGXGSTXGPRUKQP-UHFFFAOYSA-N",
                "formal_charge": 0,
                "fragment_count": 1,
                "assayed_microstate_verified": False,
            },
            "threshold_derived_class_at_mean": "active",
            "threshold_derived_class_across_one_sd": "not_stable",
            "assigned_role": None,
            "prepared_state_origin": None,
            "fit_admitted": False,
        },
        {
            "paper_row_id": "PR59",
            "experimental_pages": [33],
            "exact_published_name": (
                "N-(6-methoxy-3,4-dihydroquinazolin-2-yl)"
                "naphthalene-1-sulfonamide"
            ),
            "reported_ki_mean": "1.964",
            "reported_ki_sd": "0.452",
            "reported_ki_unit": "µM",
            "reported_uncertainty_kind": "SD",
            "reported_purity_percent": "96",
            "proposed_neutral_graph": {
                "canonical_isomeric_smiles": (
                    "COc1ccc2c(c1)CNC(NS(=O)(=O)c1cccc3ccccc13)=N2"
                ),
                "formula": "C19H17N3O3S",
                "inchikey": "PKYFJQXPMNODTI-UHFFFAOYSA-N",
                "formal_charge": 0,
                "fragment_count": 1,
                "assayed_microstate_verified": False,
            },
            "threshold_derived_class_at_mean": "inactive",
            "threshold_derived_class_across_one_sd": "inactive",
            "assigned_role": None,
            "prepared_state_origin": None,
            "fit_admitted": False,
        },
    ],
    "authority": {
        "source_authenticated": False,
        "roles_assigned": False,
        "prepared_state_bound": False,
        "training_admitted": False,
        "scientifically_validated": False,
        "product_ranking_enabled": False,
        "held_out_evaluation_established": False,
    },
}


def canonical_ledger_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def _read_regular_bounded(path: str | Path, limit: int) -> bytes:
    """Read one canonical local regular file, rejecting links and excess bytes."""
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("noncanonical_source_path")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise ValueError("source_file_not_regular_or_outside_capacity")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        if (len(raw) != before.st_size or len(raw) > limit
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError("source_file_changed_during_read")
        return raw
    finally:
        os.close(fd)


def _strict_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_ledger_json_key")
            result[key] = value
        return result

    def nonfinite(_value):
        raise ValueError("nonfinite_ledger_json_number")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    if type(value) is not dict:
        raise ValueError("invalid_ledger_document")
    return value


def _classify_pki(pki: Decimal) -> str:
    if pki >= Decimal("6.7"):
        return "active"
    if pki <= Decimal("6.3"):
        return "inactive"
    return "indeterminate"


def _derived_classes(row: dict) -> tuple[str, str]:
    mean = Decimal(row["reported_ki_mean"])
    sd = Decimal(row["reported_ki_sd"])
    if not (mean > sd > 0 and row["reported_ki_unit"] == "µM"):
        raise ValueError("invalid_reported_ki_or_unit")

    def label(value: Decimal) -> str:
        # A µM value is value × 10^-6 M, so pKi is 6 - log10(value).
        return _classify_pki(Decimal(6) - value.log10())

    low_class, high_class = label(mean + sd), label(mean - sd)
    stable = low_class if low_class == high_class else "not_stable"
    return label(mean), stable


def verify_ledger(ledger_path: str | Path) -> tuple[dict, str]:
    """Check the exact reviewed capture; do not access any outcome directory."""
    raw = _read_regular_bounded(ledger_path, MAX_LEDGER_BYTES)
    value = _strict_json(raw)
    if (raw != canonical_ledger_bytes(value)
            or raw != canonical_ledger_bytes(EXPECTED_LEDGER)):
        raise ValueError("source_ledger_does_not_match_pinned_capture")
    for row in value["rows"]:
        mean_class, range_class = _derived_classes(row)
        if (row["threshold_derived_class_at_mean"] != mean_class
                or row["threshold_derived_class_across_one_sd"] != range_class):
            raise ValueError("source_ledger_threshold_projection_mismatch")
    return value, hashlib.sha256(raw).hexdigest()


def verify_source(pdf_path: str | Path, ledger_path: str | Path) -> dict:
    """Verify local source bytes and the source-only ledger, without admission."""
    pdf = _read_regular_bounded(pdf_path, MAX_PDF_BYTES)
    observed_pdf_sha256 = hashlib.sha256(pdf).hexdigest()
    if observed_pdf_sha256 != PDF_SHA256:
        raise ValueError("primary_pdf_sha256_mismatch")
    ledger, ledger_sha256 = verify_ledger(ledger_path)
    if ledger["source"]["pdf_sha256"] != observed_pdf_sha256:
        raise ValueError("ledger_primary_pdf_binding_mismatch")
    return {
        "schema_version": RECEIPT_SCHEMA,
        "source_doi": ledger["source"]["doi"],
        "pdf_sha256": observed_pdf_sha256,
        "ledger_sha256": ledger_sha256,
        "paper_row_ids": [row["paper_row_id"] for row in ledger["rows"]],
        "pdf_hash_matched": True,
        "ledger_exact_match": True,
        "protected_outcomes_read": False,
        **ledger["authority"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_source(args.pdf, args.ledger),
                     sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    reference_minimization_validation_review_contract_document,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    reference_validation_review_contract_document,
)
from betelgeuze_engine_v2.physics.validation_legacy_contracts import (
    LEGACY_VALIDATION_CONTRACT_IDENTITIES_BY_SCHEMA_ID,
    LegacyValidationContractError,
    require_legacy_validation_contract_document,
)


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def _legacy_energy_review_document() -> dict[str, Any]:
    document = deepcopy(reference_validation_review_contract_document())
    document.update(
        {
            "schema_id": (
                "betelgeuze.engine_v2_reference_validation_review_contract/1.0.0"
            ),
            "contract_id": (
                "cpu_reference_validation_independent_review_contract/1.0.0"
            ),
            "contract_version": "1.0.0",
            "frozen_at_utc": "2026-07-17T04:31:00Z",
            "contract_sha256": (
                "37ca9f550486febc73e36dc36a113e00042d87de79b14bf8033fbbfc1dcbf104"
            ),
        }
    )
    document["attestation_schema"]["schema_id"] = (
        "betelgeuze.engine_v2_reference_validation_review_attestation/1.0.0"
    )
    legacy_blocker = "signed_execution_authorization_receipt_schema_not_frozen"
    document["authorization_gate"]["current_blockers"].insert(3, legacy_blocker)
    document["blockers"].insert(3, legacy_blocker)
    projection = dict(document)
    projection.pop("contract_sha256")
    assert _sha256(projection) == document["contract_sha256"]
    return document


def test_registry_pins_all_energy_and_minimization_legacy_documents() -> None:
    expected = {
        "betelgeuze.engine_v2_reference_validation_review_contract/1.0.0": (
            "cpu_reference_validation_independent_review_contract/1.0.0",
            "1.0.0",
            "2026-07-17T04:31:00Z",
            "37ca9f550486febc73e36dc36a113e00042d87de79b14bf8033fbbfc1dcbf104",
        ),
        "betelgeuze.engine_v2_reference_validation_authorization_contract/1.0.0": (
            "cpu_reference_validation_execution_authorization_contract/1.0.0",
            "1.0.0",
            "2026-07-17T05:00:00Z",
            "8c10d264c4228bead4a8d53b337a689d1ae1814c893190bb975f438cb9b3c018",
        ),
        "betelgeuze.engine_v2_reference_validation_execution_environment_contract/1.0.0": (
            "cpu_reference_validation_execution_environment_contract/1.0.0",
            "1.0.0",
            "2026-07-17T05:38:00Z",
            "f4d9bea26c38a009c96c2cfc31d1b00abcac8991468406a433d6ad2c4bbde5ec",
        ),
        "betelgeuze.engine_v2_reference_validation_result_receipt_contract/1.0.0": (
            "cpu_reference_validation_result_receipt_contract/1.0.0",
            "1.0.0",
            "2026-07-17T05:38:00Z",
            "3cd5b4c269895baac36c374c8698a36cdfc4424afcaa2772cb5ef60a9f1860f6",
        ),
        "betelgeuze.engine_v2_reference_validation_nonce_reservation_contract/1.0.0": (
            "cpu_reference_validation_atomic_nonce_reservation/1.0.0",
            "1.0.0",
            "2026-07-17T06:18:00Z",
            "fcaa1c9fe02b8bbab83eb8a128f9188bc299e161af1371a6c3dd2b377f6246c1",
        ),
        "betelgeuze.engine_v2_reference_validation_run_start_contract/1.0.0": (
            "cpu_reference_validation_run_start_environment/1.0.0",
            "1.0.0",
            "2026-07-17T13:45:00Z",
            "9ee69b7a0424a409cf15bd6df7450c2d1307afa37b7ea1c5b1d89b372a44f73a",
        ),
        "betelgeuze.engine_v2_reference_validation_runner_contract/1.0.0": (
            "cpu_reference_validation_bounded_runner/1.0.0",
            "1.0.0",
            "2026-07-17T13:45:00Z",
            "c9c3ca36f9afcda451f41848605bcc141e99520e262894d24013a2fabda9ef33",
        ),
        "betelgeuze.engine_v2_reference_validation_result_writer_contract/1.0.0": (
            "cpu_reference_validation_result_receipt_writer/1.0.0",
            "1.0.0",
            "2026-07-17T10:08:00Z",
            "711641f940674c1fda7c4dd7770468b8b4ebcef103933be46a9c754a9a8ea98c",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_review_contract/2.0.0": (
            "cpu_reference_minimization_validation_independent_review_contract/2.0.0",
            "2.0.0",
            "2026-07-19T06:20:00Z",
            "324b9feebe12ba0f4056686a36fb9c62104604fb0be7c0e508a630105d8f448a",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_authorization_contract/2.0.0": (
            "cpu_reference_minimization_validation_execution_authorization_contract/2.0.0",
            "2.0.0",
            "2026-07-19T06:40:00Z",
            "cd60c50e4403ece77c98975fcbc4c45d71b2f4213944e4b48b8ec48691e940a9",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_execution_environment_contract/2.0.0": (
            "cpu_reference_minimization_validation_execution_environment_contract/2.0.0",
            "2.0.0",
            "2026-07-19T06:30:00Z",
            "a3022f345d99dfc84eb0f539d72a75f1e533c61789d770baa8a0aa9a789f51cb",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_receipt_contract/2.0.0": (
            "cpu_reference_minimization_validation_result_receipt_contract/2.0.0",
            "2.0.0",
            "2026-07-19T06:30:00Z",
            "d4d27679f6d658bbc22b35ae9a4d7c588f41aa3e18633eb0bff5ad4c25b38897",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_nonce_reservation_contract/2.0.0": (
            "cpu_reference_minimization_validation_atomic_nonce_reservation/2.0.0",
            "2.0.0",
            "2026-07-19T06:50:00Z",
            "5fe334ba5f2f87294cf6ed49e5b87e92b29b2853fc75e8124f3445c53664d3f6",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_run_start_contract/2.0.0": (
            "cpu_reference_minimization_validation_run_start_environment/2.0.0",
            "2.0.0",
            "2026-07-19T07:00:00Z",
            "b985228f02c43cf0a7161d824f06bc1cd25ab217b02f537597b5de73a0987073",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/3.0.0": (
            "cpu_reference_minimization_validation_bounded_runner/3.0.0",
            "3.0.0",
            "2026-07-19T08:00:00Z",
            "980f0110ce7849795110f2cf034717ae7b71704d5e4a0a8a1520a99f6aee3c7b",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_writer_contract/2.0.0": (
            "cpu_reference_minimization_validation_result_receipt_writer/2.0.0",
            "2.0.0",
            "2026-07-19T07:20:00Z",
            "69c7dcb183194c8d8197ca99474536d2a6e4dc6efba020535c0765e4e53153c8",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_review_contract/2.0.0": (
            "cpu_reference_minimization_validation_independent_result_review_contract/2.0.0",
            "2.0.0",
            "2026-07-19T07:30:00Z",
            "2ad7c25661e4192eb988237a0c351a0e30fdde9c16854f825134b4148744eb82",
        ),
        "betelgeuze.engine_v2_reference_validation_runner_contract/2.0.0": (
            "cpu_reference_validation_bounded_runner/2.0.0",
            "2.0.0",
            "2026-07-18T22:48:58Z",
            "96b133144344183191db89c86838a6d712a26f0dbfc5eee4981d34e2fe074754",
        ),
        "betelgeuze.engine_v2_reference_validation_result_writer_contract/2.0.0": (
            "cpu_reference_validation_result_receipt_writer/2.0.0",
            "2.0.0",
            "2026-07-18T22:48:58Z",
            "60b04e3aa4cccfcbe141154585624be66e5f759fef8de4c2adec0f8c062130cb",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/4.0.0": (
            "cpu_reference_minimization_validation_bounded_runner/4.0.0",
            "4.0.0",
            "2026-07-18T22:48:58Z",
            "56ab57ecf3f512c460c8684e62ef99a58a5ec03f564c52b95ccbf0fa01e0239f",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_writer_contract/3.0.0": (
            "cpu_reference_minimization_validation_result_receipt_writer/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "a02d29c915fa56a55b22a3109cafd8a95a1397e382c85dbb0c9cacfba8b9694b",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_review_contract/3.0.0": (
            "cpu_reference_minimization_validation_independent_result_review_contract/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "b1b981940ea3d5a68f3aa936e4569e6756a8a9b88b0e86137c10d8ec4deebcfa",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/1.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/1.0.0",
            "1.0.0",
            "2026-07-18T22:48:58Z",
            "6f0670708e25966087dafcd54436798455cde2e9c9681d1195d9a426613ea148",
        ),
        "betelgeuze.engine_v2_reference_validation_runner_contract/3.0.0": (
            "cpu_reference_validation_bounded_runner/3.0.0",
            "3.0.0",
            "2026-07-18T23:33:55Z",
            "c450059857a38f7cf8aa44ba1efbb79ff3d6218ebc7deaf963078c2e3f44a1e9",
        ),
        "betelgeuze.engine_v2_reference_validation_result_writer_contract/3.0.0": (
            "cpu_reference_validation_result_receipt_writer/3.0.0",
            "3.0.0",
            "2026-07-18T23:33:55Z",
            "44f12e6025d1aed0a09194b869f20f8838bc000bdfd6f90fb578e4a053fb1708",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/5.0.0": (
            "cpu_reference_minimization_validation_bounded_runner/5.0.0",
            "5.0.0",
            "2026-07-18T23:33:55Z",
            "c27ff1ae8797db615e1aeb1625e70c476ff011026963b3a678880a4cc9fa7d33",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_writer_contract/4.0.0": (
            "cpu_reference_minimization_validation_result_receipt_writer/4.0.0",
            "4.0.0",
            "2026-07-18T23:33:55Z",
            "76bf29c96ea0d369f10d446fa5e33f6906e1adb3f6b3dba0e3a25cffdd0957c2",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_review_contract/4.0.0": (
            "cpu_reference_minimization_validation_independent_result_review_contract/4.0.0",
            "4.0.0",
            "2026-07-18T23:33:55Z",
            "bb53f31227d7be92743b0fc49164237ec81948836ec82441c2854a65e0cb5e0a",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/2.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/2.0.0",
            "2.0.0",
            "2026-07-18T23:33:55Z",
            "b0c3b1cf2f4182ad6c1f508be7126a3ca01c6c6aa3ff03d8c754d25bafee4e22",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/3.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/3.0.0",
            "3.0.0",
            "2026-07-19T00:00:00Z",
            "5f1943bbddb39db0d120269cf8b80bcd9246da27eaff1ffba43879e6d2965eb6",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/4.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/4.0.0",
            "4.0.0",
            "2026-07-19T02:51:00Z",
            "1db4d12a4bba6437c6b3ab4797689a46fadafe0c38888021e0ae1e3b14720566",
        ),
    }

    assert len(expected) == 31
    assert set(LEGACY_VALIDATION_CONTRACT_IDENTITIES_BY_SCHEMA_ID) == set(expected)
    for schema_id, expected_identity in expected.items():
        identity = LEGACY_VALIDATION_CONTRACT_IDENTITIES_BY_SCHEMA_ID[schema_id]
        assert (
            identity.contract_id,
            identity.contract_version,
            identity.frozen_at_utc,
            identity.contract_sha256,
        ) == expected_identity


def test_exact_legacy_document_is_accepted_read_only() -> None:
    document = _legacy_energy_review_document()

    assert require_legacy_validation_contract_document(document) == document


def test_self_consistent_legacy_tamper_is_rejected_by_frozen_hash() -> None:
    document = _legacy_energy_review_document()
    document["claim_policy"]["claim_safe"] = True
    projection = dict(document)
    projection.pop("contract_sha256")
    document["contract_sha256"] = _sha256(projection)

    with pytest.raises(
        LegacyValidationContractError,
        match="hash does not match the registry",
    ):
        require_legacy_validation_contract_document(document)


@pytest.mark.parametrize(
    "document",
    (
        reference_validation_review_contract_document(),
        reference_minimization_validation_review_contract_document(),
    ),
)
def test_current_contract_documents_are_not_legacy(document: dict[str, Any]) -> None:
    with pytest.raises(
        LegacyValidationContractError,
        match="schema is not registered",
    ):
        require_legacy_validation_contract_document(document)


def test_legacy_document_requires_exact_metadata_and_canonical_json_tree() -> None:
    metadata_tamper = _legacy_energy_review_document()
    metadata_tamper["contract_version"] = "9.0.0"
    with pytest.raises(LegacyValidationContractError, match="metadata"):
        require_legacy_validation_contract_document(metadata_tamper)

    invalid_json = _legacy_energy_review_document()
    invalid_json["not_finite"] = float("nan")
    with pytest.raises(LegacyValidationContractError, match="non-finite"):
        require_legacy_validation_contract_document(invalid_json)

    with pytest.raises(LegacyValidationContractError, match="must be a mapping"):
        require_legacy_validation_contract_document([])  # type: ignore[arg-type]

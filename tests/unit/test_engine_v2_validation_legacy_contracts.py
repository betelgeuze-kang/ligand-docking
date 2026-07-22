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
            "schema_id": ("betelgeuze.engine_v2_reference_validation_review_contract/1.0.0"),
            "contract_id": ("cpu_reference_validation_independent_review_contract/1.0.0"),
            "contract_version": "1.0.0",
            "frozen_at_utc": "2026-07-17T04:31:00Z",
            "contract_sha256": ("37ca9f550486febc73e36dc36a113e00042d87de79b14bf8033fbbfc1dcbf104"),
        }
    )
    document["attestation_schema"]["schema_id"] = "betelgeuze.engine_v2_reference_validation_review_attestation/1.0.0"
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
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/5.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/5.0.0",
            "5.0.0",
            "2026-07-19T05:40:00Z",
            "a93386f2be7a68c65684d25a057c5291f9d0374e2fc3c984e53a98fc5e29e8c1",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/6.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/6.0.0",
            "6.0.0",
            "2026-07-19T12:15:00Z",
            "f76048f6b9459cc64b685639a7dda92e5ef6752784b4af38d8d83d6b7f13b44b",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/7.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/7.0.0",
            "7.0.0",
            "2026-07-19T16:10:00Z",
            "562bf2e497692caa3a183d41e76564e92d92d672d2ad35b2eb3f4bb67e54a0ca",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/8.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/8.0.0",
            "8.0.0",
            "2026-07-19T20:10:00Z",
            "7b9402cceaff2aac669fe9b7f2defe09f95c53d36f924403a1a1c734751c9598",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/9.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/9.0.0",
            "9.0.0",
            "2026-07-20T01:25:00Z",
            "dcc7f0901a235b13afe8d71df3b806e2c2a623b8e1d362c04a8e4008665686e6",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_authorization_contract/3.0.0": (
            "cpu_reference_minimization_validation_execution_authorization_contract/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "ccecce01b07020b97856c2dca15d5e93d2857bb2b87490874d02d69922055018",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_receipt_contract/3.0.0": (
            "cpu_reference_minimization_validation_result_receipt_contract/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "814ea0ec6464acb77cdf41ccba8070c03ed79cc6e605805a55719c54c55b6745",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_nonce_reservation_contract/3.0.0": (
            "cpu_reference_minimization_validation_atomic_nonce_reservation/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "c5397b6ea8ea1d8291630dc5b5a0f0761133509cc3d1b5ce3403464a498635a3",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_run_start_contract/3.0.0": (
            "cpu_reference_minimization_validation_run_start_environment/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "ca0b546fe9c5a43b5ff625ed17413af25b768c5be981805085eb507ad9795cec",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/6.0.0": (
            "cpu_reference_minimization_validation_bounded_runner/6.0.0",
            "6.0.0",
            "2026-07-19T00:00:00Z",
            "678d34e58ed5a1ad6763cd072afda07889940f5d63b056687eb47f3616a217f9",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_writer_contract/5.0.0": (
            "cpu_reference_minimization_validation_result_receipt_writer/5.0.0",
            "5.0.0",
            "2026-07-19T00:00:00Z",
            "9a3c4a22cc60dc06a468e8fa62f55b23766a106d2781c3ea485360ce3131a040",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_review_contract/5.0.0": (
            "cpu_reference_minimization_validation_independent_result_review_contract/5.0.0",
            "5.0.0",
            "2026-07-19T00:00:00Z",
            "fef2198e4cc18b07f3607cc4036555f737eb423f51264179738b261dee3ea420",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/10.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/10.0.0",
            "10.0.0",
            "2026-07-20T02:20:00Z",
            "6a260a1b4572c6331e19f8ed8bad8c942d04abe6b485b69738ebb69154ab2ef6",
        ),
        "betelgeuze.engine_v2_validation_production_review_authorization_custody_extension_contract/1.0.0": (
            "engine_v2_synthetic_validation_production_review_authorization_custody_extension/1.0.0",
            "1.0.0",
            "2026-07-19T04:30:00Z",
            "3cb1d5c4289ac5026e5cbc8dc623239469f0fafe8bdce2ffc32bac11cfa549db",
        ),
        "betelgeuze.engine_v2_validation_production_reservation_custody_extension_contract/1.0.0": (
            "engine_v2_synthetic_validation_production_reservation_custody_extension/1.0.0",
            "1.0.0",
            "2026-07-19T12:25:00Z",
            "b9f63eefaf4277a1e93463a6192fc03e2d2cc99aaddd7748ad4da5e3e58b7ce9",
        ),
        "betelgeuze.engine_v2_validation_production_reservation_registry_proof_contract/1.0.0": (
            "engine_v2_validation_production_reservation_registry_proof/1.0.0",
            "1.0.0",
            "2026-07-19T15:30:00Z",
            "a204a1d3859d382fdc248b8c11589d2a7c08560124e2dde8e82b537ce833e756",
        ),
        "betelgeuze.engine_v2_validation_production_reservation_authenticated_head_receipt_contract/1.0.0": (
            "engine_v2_validation_production_reservation_authenticated_head_receipt/1.0.0",
            "1.0.0",
            "2026-07-19T18:20:00Z",
            "0e9ddbab2978ad679eb040faebaa49524d08a59a939d22e7f38029d2fc4b1639",
        ),
        "betelgeuze.engine_v2_validation_production_reservation_later_head_consistency_contract/1.0.0": (
            "engine_v2_validation_production_reservation_later_head_consistency/1.0.0",
            "1.0.0",
            "2026-07-20T00:40:00Z",
            "ee4e5d624e5f565e2fd591ddae899cea5f12b5a07c2a694b23cdb777bfb1d834",
        ),
        "betelgeuze.engine_v2_validation_production_reservation_witness_quorum_contract/1.0.0": (
            "engine_v2_validation_production_reservation_witness_quorum/1.0.0",
            "1.0.0",
            "2026-07-20T02:10:00Z",
            "d7962b6a48fc25c0ff5ce83ad784800a50defa0f3d2022b2deed9ac3ce53f3f4",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_trajectory_comparison_contract/1.0.0": (
            "cpu_reference_minimization_validation_trajectory_comparison/1.0.0",
            "1.0.0",
            "2026-07-22T00:00:00Z",
            "588f07cfe239ffd418a4743522fb9a71910da62d9ac5452109234349f29e8a6f",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_review_contract/3.0.0": (
            "cpu_reference_minimization_validation_independent_review_contract/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "9aee9223b5842f1ddbc2509079fd417958edb24b11262398b74853c9fe44d8a7",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_execution_environment_contract/3.0.0": (
            "cpu_reference_minimization_validation_execution_environment_contract/3.0.0",
            "3.0.0",
            "2026-07-18T22:48:58Z",
            "b639cc7ead5ea15678183c855b14bcaa289b7f62d36d1fc98706e2a32c44ed9f",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_receipt_contract/4.0.0": (
            "cpu_reference_minimization_validation_result_receipt_contract/4.0.0",
            "4.0.0",
            "2026-07-22T00:00:00Z",
            "eb47782990fc643938ad166d52d55ebd0680625c551b763643b0fb8482e53732",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_authorization_contract/4.0.0": (
            "cpu_reference_minimization_validation_execution_authorization_contract/4.0.0",
            "4.0.0",
            "2026-07-22T00:00:00Z",
            "a321deb2ffbfcf32e3da651d970689a602c6b0e9ca16b751e62e081a70a8de36",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_nonce_reservation_contract/4.0.0": (
            "cpu_reference_minimization_validation_atomic_nonce_reservation/4.0.0",
            "4.0.0",
            "2026-07-22T00:00:00Z",
            "09a5d401577fe7ae53ed4d22d088e1e9ef1377bdff02c2a4d82d87f7c37a24ab",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_run_start_contract/4.0.0": (
            "cpu_reference_minimization_validation_run_start_environment/4.0.0",
            "4.0.0",
            "2026-07-22T00:00:00Z",
            "7b5682a49063808e7e73554a81bd80248b14065cde5d0f2defe3eccfeea73bf9",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/7.0.0": (
            "cpu_reference_minimization_validation_bounded_runner/7.0.0",
            "7.0.0",
            "2026-07-22T00:00:00Z",
            "5045242591ef028a5461a49936242998c2ced42a31fe3242ec06a0253b12f066",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_writer_contract/6.0.0": (
            "cpu_reference_minimization_validation_result_receipt_writer/6.0.0",
            "6.0.0",
            "2026-07-22T00:00:00Z",
            "533913643878a3f0a7235dc0bd4ca5ca32b197a253d526a2aa7f51a7943c6329",
        ),
        "betelgeuze.engine_v2_reference_minimization_validation_result_review_contract/6.0.0": (
            "cpu_reference_minimization_validation_independent_result_review_contract/6.0.0",
            "6.0.0",
            "2026-07-22T00:00:00Z",
            "b62a476bac963b63ee48c3a763d2423103676db0ec568380dc28104d246c4fe2",
        ),
        "betelgeuze.engine_v2_validation_runtime_integrity_contract/11.0.0": (
            "engine_v2_synthetic_validation_runtime_integrity/11.0.0",
            "11.0.0",
            "2026-07-22T00:00:00Z",
            "24a95d5c42efcd63235614f491d7c2dc818cd3d4f3a6a40317ec8ee6f2d6018d",
        ),
        "betelgeuze.engine_v2_validation_production_review_authorization_custody_extension_contract/2.0.0": (
            "engine_v2_synthetic_validation_production_review_authorization_custody_extension/2.0.0",
            "2.0.0",
            "2026-07-22T00:00:00Z",
            "d7c0a32d52777b3406cd7e820e36addd5d7e98af7662f9400d6f1b450ee8dda3",
        ),
        "betelgeuze.engine_v2_validation_production_reservation_custody_extension_contract/2.0.0": (
            "engine_v2_synthetic_validation_production_reservation_custody_extension/2.0.0",
            "2.0.0",
            "2026-07-22T00:00:00Z",
            "cf1eafa05f58320ae71a2e2a781dc801d0dcedb326d29b310c8a734daae63069",
        ),
    }

    assert len(expected) == 63
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

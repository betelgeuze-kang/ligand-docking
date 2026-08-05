"""Full score, rank, and validity evidence for clearance activation.

This module only seals already-computed development evidence.  It does not
expose an execution entrypoint, run docking, or authorize the historical A/B.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping, Sequence

from betelgeuze_engine_v2.docking.source_paired_clearance_activation import (
    SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
    SourcePairedClearanceActivatedStateV1,
    build_source_paired_clearance_activated_state_v1,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerV1Terms
from betelgeuze_engine_v2.docking.guided_placement import (
    SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
    SourcePairedTorsionRescueProposalReceipt,
    _torsion_metadata_sha256,
)
from betelgeuze_engine_v2.docking.proposals import DockingProposal
from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID,
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_ID,
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_VERSION,
    SOURCE_PAIRED_TORSION_RESCUE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
    SourcePairedTorsionRescueActivationSnapshotV1,
)
from betelgeuze_engine_v2.docking.validity import PoseValidityResult

from .public_redocking_benchmark import (
    PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
    PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
)


SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_candidate_evidence/2.0.0"
)
SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_arm_ranking/2.0.0"
)
SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_selection_activation_receipt/2.0.0"
)
SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_case_source_receipt/1.0.0"
)
SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_current_v7_lineage/1.0.0"
)
SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_internal_validity_evidence/1.0.0"
)
SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_posebusters_evidence/2.0.0"
)
SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_rmsd_evidence/1.0.0"
)
SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID = (
    SOURCE_PAIRED_TORSION_RESCUE_ACTIVATION_SNAPSHOT_SCHEMA_ID
)
SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR = 64
SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
SOURCE_PAIRED_CLEARANCE_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
SOURCE_PAIRED_CLEARANCE_V11_ARCHIVE_SHA256 = (
    "7a2561f646f3cf5434de6c79ed797073ac1b7e034e4fcd2291755a58128f5e98"
)
SOURCE_PAIRED_CLEARANCE_V11_MEMBER_MANIFEST_SHA256 = (
    "7ae57e3bec8ecf96b754e2038dd2eef023058c4ea1adae2fbf4933bf556cf6bd"
)
SOURCE_PAIRED_CLEARANCE_V11_BUNDLE_SHA256 = (
    "37d9478c78076eef908e3a86c712f49820078ab14289fb1ee26a1f8c4fc37ea5"
)
SOURCE_PAIRED_CLEARANCE_V11_REPORT_SHA256 = (
    "8d9e9eef5907e51fbf2f25385c7cb1468dbd099c5636715ddea78274ef22fae3"
)
_FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE: Mapping[str, Mapping[str, str]] = (
    MappingProxyType(
        {
            "5SD5_HWI": MappingProxyType(
                {
                    "allocation_receipt_sha256": "44fdb41049d49b6ea5198f39e94772ad62065b1ba47e3c0191e00e535aa10f64",
                    "authenticated_input_receipt_sha256": "129286d9f9bf96ba482b6744197b330a6dd489033e3533f9f9542b2c3e39f730",
                    "current_v7_candidate_lineage_sha256": "0133959300cee30971f55e3b3a7b043f06008d58e0abd38346c6972a4c038b52",
                    "input_artifact_set_sha256": "4e52f80c435c05f690d23beece4b035eb3688cf1de9c60d57e46268d77cdaf74",
                    "native_pose_artifact_sha256": "5cb7355e18c0af38af55ab49824e34c8f97540ab0a6866d97dbc45c1dfc59fb3",
                    "receptor_artifact_sha256": "30a1ca38d5f047209fc65752e9a7e4a643d929be7f8d5c06eae303371e266ac6",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/5SD5_HWI.json",
                    "source_case_member_receipt_sha256": "367131fa76af6c1a3c579176c621f72631fe859464d8883218da0ebab6f16bfe",
                    "source_case_member_sha256": "231b3267c8a77983383a54dac2ab255d839347025ac705868c275a78c45a2b60",
                    "source_proposal_receipt_sha256": "f2a100e35c8951f5ce954a963091ee04cf6d86eb15d6c47e8cc1e8a2d6ab67ba",
                }
            ),
            "5SIS_JSM": MappingProxyType(
                {
                    "allocation_receipt_sha256": "3d7e00d50fa48006ab8a00fe2e3c00338e6f53ca18716e2252264fffd4c95b73",
                    "authenticated_input_receipt_sha256": "67f259c49dc682c001b7afa6c99e4337d6e5cce1c45dd1d0de0b8d045c4e5481",
                    "current_v7_candidate_lineage_sha256": "1e6a11a46b76d9913d167094b4c9479a14ec23e6052b55d501f0e4ad1c330d3a",
                    "input_artifact_set_sha256": "8e4609933fb92102e551ccc21e3352ca8a159ab1a59f452fdf8777484631c833",
                    "native_pose_artifact_sha256": "507806a7b4cc0d84929fb9570a3228d3abdee59d1443c69cc9893d8c5fe7e0ad",
                    "receptor_artifact_sha256": "cfe0f5722634fa881f9b1d313a3712dea78d20cdbe2367f32d8191f6382ffd9a",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/5SIS_JSM.json",
                    "source_case_member_receipt_sha256": "ffc35d373f0945bd3405688318031c3873430f7932a18c359fb67d028154c0a4",
                    "source_case_member_sha256": "d4ea898c57718435194f9dfbc522f2d203b4d1e57eb6a60274ffd30d63158b99",
                    "source_proposal_receipt_sha256": "7ca5389edbfbf9a06b467da95336e21b8f1bcb0d4cfe91384d9b6ef3829637b5",
                }
            ),
            "6M2B_EZO": MappingProxyType(
                {
                    "allocation_receipt_sha256": "95d90c25450dfc6556fd7dadd2e0f2580d4e29460528f3cf961c85a4635bc69c",
                    "authenticated_input_receipt_sha256": "753148eef70f6fed333d31ce12ac8d8cb7ea181b2e0d0e2b4151ad7d9c6c740b",
                    "current_v7_candidate_lineage_sha256": "9e8fc7c3c9a1aac38c45eb30ed5e9aeb592c7336770ffb526b52cfb30fb87952",
                    "input_artifact_set_sha256": "672d10719ff5544af93d569430d70f0ab4ee1e58c62b3c9359ac85d42d742665",
                    "native_pose_artifact_sha256": "13dab137d84a0d4dca8b6dfbbd2ee18f8f0194d3dfa8580864d20a688abcb989",
                    "receptor_artifact_sha256": "de067961294fa2a93f9969be979b01a07318146f4ddc8fab1491ff5f183fe18a",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/6M2B_EZO.json",
                    "source_case_member_receipt_sha256": "a5a269bda5f7d8aaec5ab2ca4c1f2b43278411bd76d98a242e93f88a035ce273",
                    "source_case_member_sha256": "3010ee474a27175b88a204f0afb076f56ff06fb5a264722e1747b96d5834b286",
                    "source_proposal_receipt_sha256": "ee5e729f4171962a8326012ec6b80c52c0f708398b412ebc4665c3f094590368",
                }
            ),
            "6T88_MWQ": MappingProxyType(
                {
                    "allocation_receipt_sha256": "1064d7956267037db21afa6d20fed086d4b92792a3d9a732755d8fc1dd7bdee3",
                    "authenticated_input_receipt_sha256": "af4da8a5ba619be0a11e31c19ecbc468feeaf201e42cc46a73a0aade9c27c1e4",
                    "current_v7_candidate_lineage_sha256": "09a8bc0009ed0e05b1d09370eb09f82072190bf8bfa6dee8e16654b4691f19dd",
                    "input_artifact_set_sha256": "88d8ca6b648f7f201e43c0452a9e7619a8a6decde090e04e470e2c1b18c53f7a",
                    "native_pose_artifact_sha256": "42791e5be6dd6c60bc8e5a04af5ff1a6c3ef5938140497d72f05996cfdc94f15",
                    "receptor_artifact_sha256": "51f1829b29c1704f0a0b2598130dde403c0ba1efce006521124677c968ad5851",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/6T88_MWQ.json",
                    "source_case_member_receipt_sha256": "1fbcc1186dc0d879bbe5bceb198ef4c21cb6257206e6650e1b81a609dd88a0e9",
                    "source_case_member_sha256": "b73256a4423a1172041b6afe101ce1e335c0aa9413d2fe9e05bf20d7b54087ac",
                    "source_proposal_receipt_sha256": "51339ee6fc9138f84753ad7fa637f0f8957ae18af0e0facc98a1a340ce57293d",
                }
            ),
            "6TW5_9M2": MappingProxyType(
                {
                    "allocation_receipt_sha256": "2dbf76b8e7db925215e16123476b8a1c14420febf2826898588fea6d63e5187f",
                    "authenticated_input_receipt_sha256": "c79216692a549c4b63db8853a948eb62c7750fde60b3d381e96693c832e7a09b",
                    "current_v7_candidate_lineage_sha256": "3a365b3bb51aa2be01bec444ed96a637f4e16ea44dd47e0e25beafb3a7050596",
                    "input_artifact_set_sha256": "3bed03499fd026d80acd4f7ffcc1eed50bb28ca1f652286209b8d6204340333a",
                    "native_pose_artifact_sha256": "95eaaa7830c9eccd0a86d7631914cd332f89700c22079b48318db146c24514df",
                    "receptor_artifact_sha256": "58103cb1cdd29cab8e80892d6800e8395268e33697ce9401342107e2220c1243",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/6TW5_9M2.json",
                    "source_case_member_receipt_sha256": "be096cfd8e3e5d9cf1c14781235c1a1b7cb853daf3f411b9411abed352db90a0",
                    "source_case_member_sha256": "5af7f5e26cf922b8216d2a2a53391b7f332878c4d37a49da47a395293e888440",
                    "source_proposal_receipt_sha256": "906ad8807a1da95345921f4139ca39f73a57427f16c156b843a2b53c3d0352e3",
                }
            ),
            "6TW7_NZB": MappingProxyType(
                {
                    "allocation_receipt_sha256": "11fbd284284313dec2a141f6209e08c2019fac505e67277742b48f973f306851",
                    "authenticated_input_receipt_sha256": "dd5e38afbb3aad8781586e8188de299dc2805c0ee6d1a8af91512f0804ca2198",
                    "current_v7_candidate_lineage_sha256": "92a78638bc4d44373142fb855238414bcb6fc5a7675bcf5c1f2bd09e388ee10c",
                    "input_artifact_set_sha256": "6236de2876801ec0513a75079c08ed5cb2b3949b5796fb432c77354e6c17fb16",
                    "native_pose_artifact_sha256": "839a116b45f65b56a2e98542c6d4327e8837c2d26f6417da59d66c9446e34a53",
                    "receptor_artifact_sha256": "19a178000c5866ebd4b5ecc595e8986fcf40c64f871eded0912c58e96b1ba0fe",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/6TW7_NZB.json",
                    "source_case_member_receipt_sha256": "0dc578be8bf4c757f48f818987fcf9229a85cc6236e3b5c772b1601af182d743",
                    "source_case_member_sha256": "678f46d3e283aa9d12191db243ceda5f2e4b3247e2041a85b836375d172fd09c",
                    "source_proposal_receipt_sha256": "279b65abf065c925b61fe6234cdf57215b7583c615c29f0563ae6f802bebbf80",
                }
            ),
            "6VTA_AKN": MappingProxyType(
                {
                    "allocation_receipt_sha256": "7d21c9f638c77f1a95e6455b8a489ceb23f3935d4dfe42d8de9c5bd5a73d281b",
                    "authenticated_input_receipt_sha256": "feaad4874797f6d75e304824a6de732dcc647a4ad38cde6328c452601025463e",
                    "current_v7_candidate_lineage_sha256": "e8fc07b8a3540d2a3e0aacdc81ca339c71ff57194883bf1b9b4eb57181ed5b76",
                    "input_artifact_set_sha256": "4fe358d2d70687a716b2d6b5194023ff4fa9260dbf7d950382312561bb1836ca",
                    "native_pose_artifact_sha256": "db18d13566c7fcedf8a5bfccf83979f4bf27a1ddd58a8723e8a4c9f1efa050db",
                    "receptor_artifact_sha256": "344087a778131cdff686b5e60ef6d5c39b603fd1a43d0b97f9911c429b06be48",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/6VTA_AKN.json",
                    "source_case_member_receipt_sha256": "9c5c8cc53ff46b7cf452aec200d3d25ee3a930e22a5acb96f385606c625df884",
                    "source_case_member_sha256": "394f0e763938754967e5a9d7c00ee5e073576d7660708813762943cb8ededa97",
                    "source_proposal_receipt_sha256": "3c1f1e5a4fb026321b116cc10cbefe79a1a0447b0f4b1f9b2d0d392200749641",
                }
            ),
            "6WTN_RXT": MappingProxyType(
                {
                    "allocation_receipt_sha256": "1ecb7dcad4a3ff6fa7402f78bf23c1b31d57549e789274fe2be7655fecf9fa38",
                    "authenticated_input_receipt_sha256": "dee013361ac719792b56b7e0857ed851589289e06c7b3b2c614ea8d78adc1c1b",
                    "current_v7_candidate_lineage_sha256": "4bcc74b03b172a107113981d8f64157682c512934183a617ea2e59fb91f30371",
                    "input_artifact_set_sha256": "1d6643460d2b72a7a3f4c4a4ba8a29ed6b011df221c31dff0b31844d5c7bc393",
                    "native_pose_artifact_sha256": "29681b97b5b0f75571d08ac27b622772057be141ddc03625c88400598eb49566",
                    "receptor_artifact_sha256": "afaded7b307b222cf39af23fff2eff83fcbcddc5ae7c46e8e823e0b47969c633",
                    "source_case_member_path": ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine/receipts/engine_v2/6WTN_RXT.json",
                    "source_case_member_receipt_sha256": "c29a4a67f18207ef0f46a7e6d3d93a6940c84c1438759daf7c6b418a4f1e7b10",
                    "source_case_member_sha256": "c33509cd07931d9f593cb8c61889cc5b7c50d3006df97e95f59467fd84df6a7d",
                    "source_proposal_receipt_sha256": "e5b35bbb5852821f35151ddd6b3c496076268f57a1fd72d7b7c0cf65ed2e9d2f",
                }
            ),
        }
    )
)
INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES = (
    "proper_rotation",
    "bond_lengths_preserved",
    "ligand_self_clash_free",
    "receptor_ligand_clash_free",
    "declared_chirality_preserved",
    "inside_declared_pocket",
)
_INTERNAL_VALIDITY_BLOCKER_BY_CHECK = {
    "proper_rotation": "rigid_rotation_not_proper_orthogonal",
    "bond_lengths_preserved": "bond_length_preservation_failed",
    "ligand_self_clash_free": "ligand_self_clash_detected",
    "receptor_ligand_clash_free": "receptor_ligand_clash_detected",
    "declared_chirality_preserved": "declared_chirality_not_preserved",
    "inside_declared_pocket": "pose_outside_declared_pocket",
}
POSEBUSTERS_REQUIRED_CHECK_NAMES = (
    *PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
    *PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
)


class SourcePairedClearanceActivationEvidenceError(ValueError):
    """Raised when activation evidence is incomplete or cross-wired."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SourcePairedClearanceActivationEvidenceError(
            "activation evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256 = _sha256(
    {
        case_id: dict(authority)
        for case_id, authority in _FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE.items()
    }
)
_EXPECTED_CASE_SOURCE_AUTHORITY_SHA256 = (
    "4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc"
)
if (
    SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256
    != _EXPECTED_CASE_SOURCE_AUTHORITY_SHA256
):  # pragma: no cover - import-time source-integrity guard
    raise RuntimeError(
        "frozen case-source authority does not match its policy identity"
    )


def _frozen_case_source_authority(
    case_id: str,
    _authority_map: Mapping[str, Mapping[str, str]] = (
        _FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE
    ),
) -> Mapping[str, str] | None:
    """Return one case row from the import-frozen, canonically verified map."""

    if (
        tuple(_authority_map) != SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS
        or _sha256(
            {
                frozen_case_id: dict(authority)
                for frozen_case_id, authority in _authority_map.items()
            }
        )
        != _EXPECTED_CASE_SOURCE_AUTHORITY_SHA256
    ):
        raise SourcePairedClearanceActivationEvidenceError(
            "runtime case-source authority does not match the frozen policy"
        )
    return _authority_map.get(case_id)


POSEBUSTERS_REQUIRED_CHECK_SET_SHA256 = _sha256(list(POSEBUSTERS_REQUIRED_CHECK_NAMES))


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SourcePairedClearanceActivationEvidenceError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(value: object, *, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise SourcePairedClearanceActivationEvidenceError(f"{name} must be numeric")
    try:
        observed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SourcePairedClearanceActivationEvidenceError(
            f"{name} must be numeric"
        ) from exc
    if not math.isfinite(observed) or (minimum is not None and observed < minimum):
        raise SourcePairedClearanceActivationEvidenceError(f"{name} is out of range")
    return observed


def _canonical_copy(value: object) -> object:
    try:
        return json.loads(_canonical_bytes(value).decode("ascii"))
    except json.JSONDecodeError as exc:  # pragma: no cover - encoder is authoritative
        raise SourcePairedClearanceActivationEvidenceError(
            "activation evidence canonical copy failed"
        ) from exc


def _self_hashed_mapping(
    value: Mapping[str, object],
    *,
    hash_field: str,
    schema_id: str,
    name: str,
) -> dict[str, object]:
    copied = _canonical_copy(dict(value))
    if not isinstance(copied, dict):
        raise SourcePairedClearanceActivationEvidenceError(f"{name} must be an object")
    observed = copied.pop(hash_field, None)
    if (
        copied.get("schema_id") != schema_id
        or not isinstance(observed, str)
        or _digest(observed, name=f"{name} {hash_field}") != _sha256(copied)
    ):
        raise SourcePairedClearanceActivationEvidenceError(
            f"{name} schema or self-hash is invalid"
        )
    copied[hash_field] = observed
    return copied


def _validity_payload(result: PoseValidityResult) -> dict[str, object]:
    if type(result) is not PoseValidityResult:
        raise TypeError("internal_validity must be PoseValidityResult")
    payload = result.to_dict()
    checks = payload.get("checks")
    evaluated = payload.get("evaluated_checks")
    reasons = payload.get("not_evaluated_reasons")
    expected_blockers = (
        tuple(
            _INTERNAL_VALIDITY_BLOCKER_BY_CHECK[name]
            for name in INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
            if checks.get(name) is False
        )
        if isinstance(checks, dict)
        else ()
    )
    expected_valid = bool(isinstance(checks, dict) and all(checks.values()))
    if (
        not isinstance(checks, dict)
        or tuple(checks) != INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
        or not isinstance(evaluated, dict)
        or tuple(evaluated) != INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES
        or any(type(value) is not bool for value in checks.values())
        or any(
            type(value) is not bool or value is not True for value in evaluated.values()
        )
        or type(payload.get("complete")) is not bool
        or payload.get("complete") is not True
        or type(payload.get("valid_within_evaluated_scope")) is not bool
        or payload.get("valid_within_evaluated_scope") is not expected_valid
        or not isinstance(reasons, dict)
        or reasons
        or type(payload.get("valid")) is not bool
        or payload.get("valid") is not expected_valid
        or tuple(payload.get("blockers", ())) != expected_blockers
        or type(payload.get("claim_safe")) is not bool
        or payload.get("claim_safe") is not False
    ):
        raise SourcePairedClearanceActivationEvidenceError(
            "internal pose validity evidence is incomplete"
        )
    measurements = payload.get("measurements")
    if not isinstance(measurements, dict):
        raise SourcePairedClearanceActivationEvidenceError(
            "internal pose validity measurements are invalid"
        )
    for name, value in measurements.items():
        if not isinstance(name, str) or not name or isinstance(value, bool):
            raise SourcePairedClearanceActivationEvidenceError(
                "internal pose validity measurements are invalid"
            )
        _finite(value, name=f"validity measurement {name}")
    copied = _canonical_copy(payload)
    assert isinstance(copied, dict)
    return copied


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceInternalValidityEvidenceV1:
    proposal_fingerprint_sha256: str
    coordinate_sha256: str
    pose_artifact_sha256: str
    authority_input_receipt_sha256: str
    problem_fingerprint_sha256: str
    context_fingerprint_sha256: str
    config_fingerprint_sha256: str
    evaluator_implementation_sha256: str
    result: PoseValidityResult
    schema_id: str = SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "internal validity evidence schema_id is invalid"
            )
        for name in (
            "proposal_fingerprint_sha256",
            "coordinate_sha256",
            "pose_artifact_sha256",
            "authority_input_receipt_sha256",
            "problem_fingerprint_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
            "evaluator_implementation_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        _validity_payload(self.result)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def valid(self) -> bool:
        return self.result.valid

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "pose_artifact_sha256": self.pose_artifact_sha256,
            "authority_input_receipt_sha256": (self.authority_input_receipt_sha256),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "context_fingerprint_sha256": self.context_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "evaluator_implementation_sha256": (self.evaluator_implementation_sha256),
            "required_check_names": list(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES),
            "required_check_set_sha256": _sha256(
                list(INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES)
            ),
            "result": _validity_payload(self.result),
            "complete": True,
            "valid": self.valid,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "internal validity evidence changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedClearancePoseBustersEvidenceV1:
    implementation_sha256: str
    config_sha256: str
    proposal_fingerprint_sha256: str
    coordinate_sha256: str
    pose_artifact_sha256: str
    native_pose_artifact_sha256: str
    receptor_artifact_sha256: str
    report_artifact_sha256: str
    check_results: Mapping[str, bool]
    posebusters_version: str = "0.3.1"
    mode: str = "redock"
    complete: bool = True
    schema_id: str = SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID:
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters evidence schema_id is invalid"
            )
        for name in (
            "implementation_sha256",
            "config_sha256",
            "proposal_fingerprint_sha256",
            "coordinate_sha256",
            "pose_artifact_sha256",
            "native_pose_artifact_sha256",
            "receptor_artifact_sha256",
            "report_artifact_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.posebusters_version != "0.3.1" or self.mode != "redock":
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters execution profile is not frozen"
            )
        if type(self.complete) is not bool or self.complete is not True:
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters evidence must be complete"
            )
        if not isinstance(self.check_results, Mapping):
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters check map must be complete"
            )
        rows: dict[str, bool] = {}
        for name, value in sorted(self.check_results.items()):
            if not isinstance(name, str) or not name or type(value) is not bool:
                raise SourcePairedClearanceActivationEvidenceError(
                    "PoseBusters check map is invalid"
                )
            rows[name] = value
        if tuple(rows) != tuple(sorted(POSEBUSTERS_REQUIRED_CHECK_NAMES)):
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters check map does not match the frozen complete check set"
            )
        object.__setattr__(self, "check_results", MappingProxyType(rows))
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def valid(self) -> bool:
        return all(self.check_results.values())

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "implementation_sha256": self.implementation_sha256,
            "config_sha256": self.config_sha256,
            "posebusters_version": self.posebusters_version,
            "mode": self.mode,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "pose_artifact_sha256": self.pose_artifact_sha256,
            "native_pose_artifact_sha256": self.native_pose_artifact_sha256,
            "receptor_artifact_sha256": self.receptor_artifact_sha256,
            "report_artifact_sha256": self.report_artifact_sha256,
            "required_check_names": list(POSEBUSTERS_REQUIRED_CHECK_NAMES),
            "required_check_set_sha256": POSEBUSTERS_REQUIRED_CHECK_SET_SHA256,
            "check_results": dict(self.check_results),
            "complete": True,
            "valid": self.valid,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters evidence changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceRmsdEvidenceV1:
    implementation_sha256: str
    config_sha256: str
    proposal_fingerprint_sha256: str
    coordinate_sha256: str
    pose_artifact_sha256: str
    native_pose_artifact_sha256: str
    receptor_artifact_sha256: str
    atom_mapping_sha256: str
    symmetry_policy_sha256: str
    report_artifact_sha256: str
    rmsd_angstrom: float
    method_id: str = "posebusters_redock_symmetry_aware_rmsd"
    complete: bool = True
    schema_id: str = SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID:
            raise SourcePairedClearanceActivationEvidenceError(
                "RMSD evidence schema_id is invalid"
            )
        for name in (
            "implementation_sha256",
            "config_sha256",
            "proposal_fingerprint_sha256",
            "coordinate_sha256",
            "pose_artifact_sha256",
            "native_pose_artifact_sha256",
            "receptor_artifact_sha256",
            "atom_mapping_sha256",
            "symmetry_policy_sha256",
            "report_artifact_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if (
            self.method_id != "posebusters_redock_symmetry_aware_rmsd"
            or type(self.complete) is not bool
            or self.complete is not True
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "RMSD evidence method or completeness is invalid"
            )
        object.__setattr__(
            self,
            "rmsd_angstrom",
            _finite(self.rmsd_angstrom, name="rmsd_angstrom", minimum=0.0),
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "method_id": self.method_id,
            "implementation_sha256": self.implementation_sha256,
            "config_sha256": self.config_sha256,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "pose_artifact_sha256": self.pose_artifact_sha256,
            "native_pose_artifact_sha256": self.native_pose_artifact_sha256,
            "receptor_artifact_sha256": self.receptor_artifact_sha256,
            "atom_mapping_sha256": self.atom_mapping_sha256,
            "symmetry_policy_sha256": self.symmetry_policy_sha256,
            "report_artifact_sha256": self.report_artifact_sha256,
            "rmsd_angstrom_binary64_hex": self.rmsd_angstrom.hex(),
            "complete": True,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError("RMSD evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceCurrentV7LineageReceiptV1:
    """Exact 64-slot current-V7 lineage sealed before replacement scoring."""

    source_proposal_receipt: SourcePairedTorsionRescueProposalReceipt
    current_v7_proposals: Sequence[DockingProposal]
    source_v11_receipts: Sequence[Mapping[str, object] | None]
    schema_id: str = SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID
    _lineage_rows: tuple[Mapping[str, object], ...] = field(
        init=False,
        repr=False,
    )
    _source_v11_receipt_payloads: tuple[Mapping[str, object] | None, ...] = field(
        init=False,
        repr=False,
    )
    _problem_fingerprint_sha256: str = field(init=False, repr=False)
    _search_space_fingerprint_sha256: str = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID:
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 lineage schema_id is invalid"
            )
        if (
            type(self.source_proposal_receipt)
            is not SourcePairedTorsionRescueProposalReceipt
        ):
            raise TypeError(
                "source_proposal_receipt must be "
                "SourcePairedTorsionRescueProposalReceipt"
            )
        source_receipt_sha256 = self.source_proposal_receipt.receipt_sha256
        source_receipt = _self_hashed_mapping(
            self.source_proposal_receipt.to_dict(),
            hash_field="receipt_sha256",
            schema_id=SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_RECEIPT_SCHEMA_ID,
            name="current-V7 source proposal receipt",
        )
        slots = source_receipt.get("candidate_slots")
        proposals = tuple(self.current_v7_proposals)
        receipts = tuple(self.source_v11_receipts)
        if (
            not isinstance(slots, list)
            or len(slots) != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
            or len(proposals) != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
            or len(receipts) != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 lineage must retain the exact ordered 64-slot denominator"
            )

        cloned_proposals: list[DockingProposal] = []
        receipt_payloads: list[Mapping[str, object] | None] = []
        rows: list[Mapping[str, object]] = []
        problem_fingerprints: set[str] = set()
        search_space_fingerprints: set[str] = set()
        allocation_sha256 = self.source_proposal_receipt.allocation.allocation_sha256
        for index, (slot_value, proposal_value, receipt_value) in enumerate(
            zip(slots, proposals, receipts, strict=True)
        ):
            if not isinstance(slot_value, dict):
                raise SourcePairedClearanceActivationEvidenceError(
                    "current-V7 source proposal slot is invalid"
                )
            if type(proposal_value) is not DockingProposal:
                raise TypeError("current_v7_proposals must contain DockingProposal")
            proposal_value.assert_integrity()
            proposal = replace(proposal_value)
            source_proposal_sha256 = _digest(
                slot_value.get("proposal_fingerprint_sha256"),
                name="current-V7 source proposal fingerprint",
            )
            source_coordinate_sha256 = _digest(
                slot_value.get("coordinate_fingerprint_sha256"),
                name="current-V7 source coordinate fingerprint",
            )
            source_torsion_sha256 = _digest(
                slot_value.get("torsion_metadata_sha256"),
                name="current-V7 source torsion fingerprint",
            )
            if (
                slot_value.get("proposal_index") != index
                or proposal.proposal_index != index
                or proposal.candidate_id != slot_value.get("candidate_id")
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "current-V7 candidate is cross-wired to another source slot"
                )
            problem_fingerprints.add(proposal.problem_fingerprint_sha256)
            search_space_fingerprints.add(proposal.search_space_fingerprint_sha256)

            if receipt_value is None:
                if (
                    proposal.fingerprint_sha256 != source_proposal_sha256
                    or proposal.coordinate_fingerprint_sha256
                    != source_coordinate_sha256
                    or _torsion_metadata_sha256(proposal.torsion_angles)
                    != source_torsion_sha256
                    or proposal.refined
                    or proposal.refinement_receipt_sha256
                ):
                    raise SourcePairedClearanceActivationEvidenceError(
                        "current-V7 identity passthrough does not equal its source slot"
                    )
                lineage_mode = "identity_passthrough_exact_source"
                refinement_receipt_sha256 = ""
                refinement_receipt_schema_id = "none"
                source_v11_receipt: Mapping[str, object] | None = None
            else:
                source_v11_receipt = _self_hashed_mapping(
                    receipt_value,
                    hash_field="receipt_sha256",
                    schema_id=(
                        INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID
                    ),
                    name="current-V7 source V1.1 receipt",
                )
                refinement_receipt_sha256 = _digest(
                    source_v11_receipt.get("receipt_sha256"),
                    name="current-V7 refinement receipt SHA-256",
                )
                expected_flags = {
                    "source_paired_torsion_rescue_profile": True,
                    "source_lane_retained": True,
                    "result_dependent_eligibility": False,
                    "posebusters_or_rmsd_used_for_selection": False,
                    "development_only": True,
                    "stage0_eligible": False,
                    "fresh_execution_authorized": False,
                    "scientifically_validated": False,
                    "claim_safe": False,
                }
                if (
                    proposal.parent_proposal_fingerprint_sha256
                    != source_proposal_sha256
                    or proposal.refiner_id
                    != INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_ID
                    or proposal.refiner_version
                    != INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_REFINER_VERSION
                    or proposal.refinement_receipt_sha256 != refinement_receipt_sha256
                    or source_v11_receipt.get("source_proposal_sha256")
                    != source_proposal_sha256
                    or source_v11_receipt.get("post_coordinates_sha256")
                    != proposal.coordinate_fingerprint_sha256
                    or source_v11_receipt.get(
                        "source_paired_torsion_rescue_allocation_sha256"
                    )
                    != allocation_sha256
                    or any(
                        source_v11_receipt.get(name) is not expected
                        for name, expected in expected_flags.items()
                    )
                ):
                    raise SourcePairedClearanceActivationEvidenceError(
                        "current-V7 proposal and V1.1 refinement receipt are cross-wired"
                    )
                lineage_mode = "source_paired_v11_refined"
                refinement_receipt_schema_id = str(source_v11_receipt["schema_id"])

            cloned_proposals.append(proposal)
            receipt_payloads.append(
                None
                if source_v11_receipt is None
                else MappingProxyType(dict(source_v11_receipt))
            )
            rows.append(
                MappingProxyType(
                    {
                        "proposal_index": index,
                        "candidate_id": proposal.candidate_id,
                        "source_proposal_fingerprint_sha256": (source_proposal_sha256),
                        "source_coordinate_sha256": source_coordinate_sha256,
                        "source_torsion_metadata_sha256": source_torsion_sha256,
                        "current_v7_candidate_proposal_fingerprint_sha256": (
                            proposal.fingerprint_sha256
                        ),
                        "current_v7_coordinate_sha256": (
                            proposal.coordinate_fingerprint_sha256
                        ),
                        "current_v7_refinement_receipt_sha256": (
                            refinement_receipt_sha256
                        ),
                        "current_v7_refinement_receipt_schema_id": (
                            refinement_receipt_schema_id
                        ),
                        "lineage_mode": lineage_mode,
                    }
                )
            )

        if len(problem_fingerprints) != 1 or len(search_space_fingerprints) != 1:
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 candidates do not share one problem and search space"
            )
        object.__setattr__(self, "current_v7_proposals", tuple(cloned_proposals))
        object.__setattr__(self, "source_v11_receipts", tuple(receipt_payloads))
        object.__setattr__(self, "_lineage_rows", tuple(rows))
        object.__setattr__(
            self,
            "_source_v11_receipt_payloads",
            tuple(receipt_payloads),
        )
        object.__setattr__(
            self,
            "_problem_fingerprint_sha256",
            next(iter(problem_fingerprints)),
        )
        object.__setattr__(
            self,
            "_search_space_fingerprint_sha256",
            next(iter(search_space_fingerprints)),
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))
        if self.source_proposal_receipt.receipt_sha256 != source_receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 source proposal receipt changed"
            )

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self._problem_fingerprint_sha256

    @property
    def search_space_fingerprint_sha256(self) -> str:
        return self._search_space_fingerprint_sha256

    @property
    def lineage_identity_sha256(self) -> str:
        for proposal in self.current_v7_proposals:
            proposal.assert_integrity()
        return _sha256([dict(row) for row in self._lineage_rows])

    def source_proposal_fingerprint_sha256(self, proposal_index: int) -> str:
        return str(
            self._lineage_rows[proposal_index]["source_proposal_fingerprint_sha256"]
        )

    def _projection(self) -> dict[str, object]:
        for proposal in self.current_v7_proposals:
            proposal.assert_integrity()
        return {
            "schema_id": self.schema_id,
            "source_proposal_receipt_sha256": (
                self.source_proposal_receipt.receipt_sha256
            ),
            "authenticated_input_receipt_sha256": (
                self.source_proposal_receipt.authenticated_input_receipt_sha256
            ),
            "allocation_receipt_sha256": (
                self.source_proposal_receipt.allocation.allocation_sha256
            ),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": (self.search_space_fingerprint_sha256),
            "candidate_denominator": SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
            "current_v7_candidate_lineage_rows": [
                dict(row) for row in self._lineage_rows
            ],
            "current_v7_candidate_lineage_sha256": self.lineage_identity_sha256,
            "source_v11_receipts_by_proposal_index": [
                None if payload is None else dict(payload)
                for payload in self._source_v11_receipt_payloads
            ],
            "full_source_lineage_verified": True,
            "development_only": True,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 lineage receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceCaseSourceReceiptV1:
    case_id: str
    source_case_member_path: str
    source_case_member_sha256: str
    source_case_member_receipt_sha256: str
    authenticated_input_receipt_sha256: str
    problem_fingerprint_sha256: str
    source_proposal_receipt_sha256: str
    allocation_receipt_sha256: str
    native_pose_artifact_sha256: str
    receptor_artifact_sha256: str
    input_artifact_set_sha256: str
    current_v7_candidate_lineage_sha256: str
    source_v11_archive_sha256: str = SOURCE_PAIRED_CLEARANCE_V11_ARCHIVE_SHA256
    source_v11_member_manifest_sha256: str = (
        SOURCE_PAIRED_CLEARANCE_V11_MEMBER_MANIFEST_SHA256
    )
    source_v11_bundle_sha256: str = SOURCE_PAIRED_CLEARANCE_V11_BUNDLE_SHA256
    source_v11_report_sha256: str = SOURCE_PAIRED_CLEARANCE_V11_REPORT_SHA256
    cohort_case_ids_sha256: str = SOURCE_PAIRED_CLEARANCE_CASE_IDS_SHA256
    schema_id: str = SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID:
            raise SourcePairedClearanceActivationEvidenceError(
                "case source receipt schema_id is invalid"
            )
        if self.case_id not in SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS:
            raise SourcePairedClearanceActivationEvidenceError(
                "case source receipt is outside the frozen scored cohort"
            )
        member_path = str(self.source_case_member_path or "").strip()
        if (
            not member_path
            or member_path.startswith("/")
            or ".." in member_path.split("/")
            or self.case_id not in member_path
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "case source member path is invalid"
            )
        object.__setattr__(self, "source_case_member_path", member_path)
        for name in (
            "source_case_member_sha256",
            "source_case_member_receipt_sha256",
            "authenticated_input_receipt_sha256",
            "problem_fingerprint_sha256",
            "source_proposal_receipt_sha256",
            "allocation_receipt_sha256",
            "native_pose_artifact_sha256",
            "receptor_artifact_sha256",
            "input_artifact_set_sha256",
            "current_v7_candidate_lineage_sha256",
            "source_v11_archive_sha256",
            "source_v11_member_manifest_sha256",
            "source_v11_bundle_sha256",
            "source_v11_report_sha256",
            "cohort_case_ids_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if (
            self.source_v11_archive_sha256 != SOURCE_PAIRED_CLEARANCE_V11_ARCHIVE_SHA256
            or self.source_v11_member_manifest_sha256
            != SOURCE_PAIRED_CLEARANCE_V11_MEMBER_MANIFEST_SHA256
            or self.source_v11_bundle_sha256
            != SOURCE_PAIRED_CLEARANCE_V11_BUNDLE_SHA256
            or self.source_v11_report_sha256
            != SOURCE_PAIRED_CLEARANCE_V11_REPORT_SHA256
            or self.cohort_case_ids_sha256 != SOURCE_PAIRED_CLEARANCE_CASE_IDS_SHA256
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "case source receipt is not bound to the pinned V1.1 archive"
            )
        authority = _frozen_case_source_authority(self.case_id)
        if authority is None:
            raise SourcePairedClearanceActivationEvidenceError(
                "case source authority is absent from the frozen archive map"
            )
        observed_authority = {
            name: getattr(self, name)
            for name in (
                "allocation_receipt_sha256",
                "authenticated_input_receipt_sha256",
                "current_v7_candidate_lineage_sha256",
                "input_artifact_set_sha256",
                "native_pose_artifact_sha256",
                "receptor_artifact_sha256",
                "source_case_member_path",
                "source_case_member_receipt_sha256",
                "source_case_member_sha256",
                "source_proposal_receipt_sha256",
            )
        }
        if observed_authority != dict(authority):
            raise SourcePairedClearanceActivationEvidenceError(
                "case source does not match its frozen archive member authority"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "source_case_member_path": self.source_case_member_path,
            "source_case_member_sha256": self.source_case_member_sha256,
            "source_case_member_receipt_sha256": (
                self.source_case_member_receipt_sha256
            ),
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "source_proposal_receipt_sha256": (self.source_proposal_receipt_sha256),
            "allocation_receipt_sha256": self.allocation_receipt_sha256,
            "native_pose_artifact_sha256": self.native_pose_artifact_sha256,
            "receptor_artifact_sha256": self.receptor_artifact_sha256,
            "input_artifact_set_sha256": self.input_artifact_set_sha256,
            "current_v7_candidate_lineage_sha256": (
                self.current_v7_candidate_lineage_sha256
            ),
            "source_v11_archive_sha256": self.source_v11_archive_sha256,
            "source_v11_member_manifest_sha256": (
                self.source_v11_member_manifest_sha256
            ),
            "source_v11_bundle_sha256": self.source_v11_bundle_sha256,
            "source_v11_report_sha256": self.source_v11_report_sha256,
            "cohort_case_ids_sha256": self.cohort_case_ids_sha256,
            "case_source_authority_sha256": (
                SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256
            ),
            "member_manifest_membership_verified": True,
            "historical_archive_full_scorer_terms_available": False,
            "historical_archive_score_rank_semantics_authorized": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "case source receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _canonical_scorer_terms(value: ScorerV1Terms) -> ScorerV1Terms:
    if type(value) is not ScorerV1Terms:
        raise TypeError("scorer_terms must be exact ScorerV1Terms")
    canonical = ScorerV1Terms(
        proposal_fingerprint_sha256=value.proposal_fingerprint_sha256,
        authority_input_receipt_sha256=value.authority_input_receipt_sha256,
        context_fingerprint_sha256=value.context_fingerprint_sha256,
        config_fingerprint_sha256=value.config_fingerprint_sha256,
        backend_receipt_sha256=value.backend_receipt_sha256,
        typed_vdw=value.typed_vdw,
        electrostatics=value.electrostatics,
        directional_hbond=value.directional_hbond,
        hydrophobic_contact=value.hydrophobic_contact,
        desolvation_proxy=value.desolvation_proxy,
        torsion_energy=value.torsion_energy,
        ligand_strain=value.ligand_strain,
        weak_pocket_prior=value.weak_pocket_prior,
        total_score=value.total_score,
        receptor_candidate_pair_count=value.receptor_candidate_pair_count,
        ligand_pair_count=value.ligand_pair_count,
        hbond_count=value.hbond_count,
        hydrophobic_contact_count=value.hydrophobic_contact_count,
        buried_polar_count=value.buried_polar_count,
    )
    if canonical.to_dict() != value.to_dict():
        raise SourcePairedClearanceActivationEvidenceError(
            "ScorerV1Terms does not independently rederive"
        )
    return canonical


def _canonical_internal_validity(
    value: SourcePairedClearanceInternalValidityEvidenceV1,
) -> SourcePairedClearanceInternalValidityEvidenceV1:
    if type(value) is not SourcePairedClearanceInternalValidityEvidenceV1:
        raise TypeError("internal_validity must be exact bound validity evidence")
    if type(value.result) is not PoseValidityResult:
        raise TypeError("internal validity result must be exact PoseValidityResult")
    result = PoseValidityResult(
        checks=dict(value.result.checks),
        evaluated_checks=dict(value.result.evaluated_checks),
        complete=value.result.complete,
        valid_within_evaluated_scope=value.result.valid_within_evaluated_scope,
        measurements=dict(value.result.measurements),
        blockers=tuple(value.result.blockers),
        not_evaluated_reasons=dict(value.result.not_evaluated_reasons),
    )
    canonical = SourcePairedClearanceInternalValidityEvidenceV1(
        proposal_fingerprint_sha256=value.proposal_fingerprint_sha256,
        coordinate_sha256=value.coordinate_sha256,
        pose_artifact_sha256=value.pose_artifact_sha256,
        authority_input_receipt_sha256=value.authority_input_receipt_sha256,
        problem_fingerprint_sha256=value.problem_fingerprint_sha256,
        context_fingerprint_sha256=value.context_fingerprint_sha256,
        config_fingerprint_sha256=value.config_fingerprint_sha256,
        evaluator_implementation_sha256=value.evaluator_implementation_sha256,
        result=result,
        schema_id=value.schema_id,
    )
    if canonical.to_dict() != value.to_dict():
        raise SourcePairedClearanceActivationEvidenceError(
            "internal validity evidence does not independently rederive"
        )
    return canonical


def _canonical_posebusters(
    value: SourcePairedClearancePoseBustersEvidenceV1,
) -> SourcePairedClearancePoseBustersEvidenceV1:
    if type(value) is not SourcePairedClearancePoseBustersEvidenceV1:
        raise TypeError("posebusters must be exact complete PoseBusters evidence")
    canonical = SourcePairedClearancePoseBustersEvidenceV1(
        implementation_sha256=value.implementation_sha256,
        config_sha256=value.config_sha256,
        proposal_fingerprint_sha256=value.proposal_fingerprint_sha256,
        coordinate_sha256=value.coordinate_sha256,
        pose_artifact_sha256=value.pose_artifact_sha256,
        native_pose_artifact_sha256=value.native_pose_artifact_sha256,
        receptor_artifact_sha256=value.receptor_artifact_sha256,
        report_artifact_sha256=value.report_artifact_sha256,
        check_results=dict(value.check_results),
        posebusters_version=value.posebusters_version,
        mode=value.mode,
        complete=value.complete,
        schema_id=value.schema_id,
    )
    if canonical.to_dict() != value.to_dict():
        raise SourcePairedClearanceActivationEvidenceError(
            "PoseBusters evidence does not independently rederive"
        )
    return canonical


def _canonical_rmsd(
    value: SourcePairedClearanceRmsdEvidenceV1,
) -> SourcePairedClearanceRmsdEvidenceV1:
    if type(value) is not SourcePairedClearanceRmsdEvidenceV1:
        raise TypeError("rmsd must be exact authenticated RMSD evidence")
    canonical = SourcePairedClearanceRmsdEvidenceV1(
        implementation_sha256=value.implementation_sha256,
        config_sha256=value.config_sha256,
        proposal_fingerprint_sha256=value.proposal_fingerprint_sha256,
        coordinate_sha256=value.coordinate_sha256,
        pose_artifact_sha256=value.pose_artifact_sha256,
        native_pose_artifact_sha256=value.native_pose_artifact_sha256,
        receptor_artifact_sha256=value.receptor_artifact_sha256,
        atom_mapping_sha256=value.atom_mapping_sha256,
        symmetry_policy_sha256=value.symmetry_policy_sha256,
        report_artifact_sha256=value.report_artifact_sha256,
        rmsd_angstrom=value.rmsd_angstrom,
        method_id=value.method_id,
        complete=value.complete,
        schema_id=value.schema_id,
    )
    if canonical.to_dict() != value.to_dict():
        raise SourcePairedClearanceActivationEvidenceError(
            "RMSD evidence does not independently rederive"
        )
    return canonical


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceCandidateEvidenceV1:
    candidate_id: str
    proposal_index: int
    candidate_proposal_fingerprint_sha256: str
    source_proposal_fingerprint_sha256: str
    coordinate_sha256: str
    pose_artifact_sha256: str
    scorer_terms: ScorerV1Terms
    internal_validity: SourcePairedClearanceInternalValidityEvidenceV1
    posebusters: SourcePairedClearancePoseBustersEvidenceV1
    rmsd: SourcePairedClearanceRmsdEvidenceV1
    raw_score_rank: int
    schema_id: str = SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID:
            raise SourcePairedClearanceActivationEvidenceError(
                "candidate evidence schema_id is invalid"
            )
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise SourcePairedClearanceActivationEvidenceError(
                "candidate_id must be non-empty"
            )
        if (
            type(self.proposal_index) is not int
            or not 0
            <= self.proposal_index
            < SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "proposal_index is outside the frozen denominator"
            )
        for name in (
            "candidate_proposal_fingerprint_sha256",
            "source_proposal_fingerprint_sha256",
            "coordinate_sha256",
            "pose_artifact_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        object.__setattr__(
            self,
            "scorer_terms",
            _canonical_scorer_terms(self.scorer_terms),
        )
        if (
            self.scorer_terms.proposal_fingerprint_sha256
            != self.candidate_proposal_fingerprint_sha256
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "ScorerV1Terms is cross-wired to another proposal"
            )
        self.scorer_terms.receipt_sha256
        object.__setattr__(
            self,
            "internal_validity",
            _canonical_internal_validity(self.internal_validity),
        )
        object.__setattr__(
            self,
            "posebusters",
            _canonical_posebusters(self.posebusters),
        )
        object.__setattr__(self, "rmsd", _canonical_rmsd(self.rmsd))
        bound_evidence = (self.internal_validity, self.posebusters, self.rmsd)
        if any(
            evidence.proposal_fingerprint_sha256
            != self.candidate_proposal_fingerprint_sha256
            or evidence.coordinate_sha256 != self.coordinate_sha256
            or evidence.pose_artifact_sha256 != self.pose_artifact_sha256
            for evidence in bound_evidence
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "validity or RMSD evidence is cross-wired to another candidate pose"
            )
        if (
            self.posebusters.native_pose_artifact_sha256
            != self.rmsd.native_pose_artifact_sha256
            or self.posebusters.receptor_artifact_sha256
            != self.rmsd.receptor_artifact_sha256
            or self.posebusters.report_artifact_sha256
            != self.rmsd.report_artifact_sha256
            or self.posebusters.implementation_sha256 != self.rmsd.implementation_sha256
            or self.posebusters.config_sha256 != self.rmsd.config_sha256
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "PoseBusters checks and RMSD are not from one full report"
            )
        if (
            type(self.raw_score_rank) is not int
            or not 1
            <= self.raw_score_rank
            <= SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "raw_score_rank is invalid"
            )
        self.internal_validity.receipt_sha256
        self.posebusters.receipt_sha256
        self.rmsd.receipt_sha256
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def exact_valid(self) -> bool:
        return bool(
            self.rmsd.rmsd_angstrom <= 2.0
            and self.internal_validity.valid
            and self.posebusters.valid
        )

    def _scientific_projection(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "candidate_proposal_fingerprint_sha256": (
                self.candidate_proposal_fingerprint_sha256
            ),
            "source_proposal_fingerprint_sha256": (
                self.source_proposal_fingerprint_sha256
            ),
            "coordinate_sha256": self.coordinate_sha256,
            "pose_artifact_sha256": self.pose_artifact_sha256,
            "raw_score_binary64_hex": self.scorer_terms.total_score.hex(),
            "scorer_v1_terms": self.scorer_terms.to_dict(),
            "internal_pose_validity": self.internal_validity.to_dict(),
            "posebusters": self.posebusters.to_dict(),
            "rmsd": self.rmsd.to_dict(),
            "rmsd_angstrom_binary64_hex": self.rmsd.rmsd_angstrom.hex(),
            "exact_valid": self.exact_valid,
        }

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            **self._scientific_projection(),
            "raw_score_rank": self.raw_score_rank,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "candidate activation evidence changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _canonical_candidate_evidence(
    value: SourcePairedClearanceCandidateEvidenceV1,
) -> SourcePairedClearanceCandidateEvidenceV1:
    if type(value) is not SourcePairedClearanceCandidateEvidenceV1:
        raise TypeError("candidate row must be exact candidate evidence")
    canonical = SourcePairedClearanceCandidateEvidenceV1(
        candidate_id=value.candidate_id,
        proposal_index=value.proposal_index,
        candidate_proposal_fingerprint_sha256=(
            value.candidate_proposal_fingerprint_sha256
        ),
        source_proposal_fingerprint_sha256=(value.source_proposal_fingerprint_sha256),
        coordinate_sha256=value.coordinate_sha256,
        pose_artifact_sha256=value.pose_artifact_sha256,
        scorer_terms=value.scorer_terms,
        internal_validity=value.internal_validity,
        posebusters=value.posebusters,
        rmsd=value.rmsd,
        raw_score_rank=value.raw_score_rank,
        schema_id=value.schema_id,
    )
    if canonical.to_dict() != value.to_dict():
        raise SourcePairedClearanceActivationEvidenceError(
            "candidate evidence does not independently rederive"
        )
    return canonical


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceArmRankingReceiptV1:
    arm: str
    candidate_rows: Sequence[SourcePairedClearanceCandidateEvidenceV1]
    schema_id: str = SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID:
            raise SourcePairedClearanceActivationEvidenceError(
                "arm ranking receipt schema_id is invalid"
            )
        if self.arm not in {"baseline_current_v7", "experimental_clearance_shadow"}:
            raise SourcePairedClearanceActivationEvidenceError("ranking arm is invalid")
        untrusted_rows = tuple(self.candidate_rows)
        if len(untrusted_rows) != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR or any(
            type(row) is not SourcePairedClearanceCandidateEvidenceV1
            for row in untrusted_rows
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "ranking receipt must retain the exact ordered 64-slot denominator"
            )
        rows = tuple(_canonical_candidate_evidence(row) for row in untrusted_rows)
        if tuple(row.proposal_index for row in rows) != tuple(
            range(SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR)
        ) or len({row.candidate_id for row in rows}) != len(rows):
            raise SourcePairedClearanceActivationEvidenceError(
                "ranking receipt must retain the exact ordered 64-slot denominator"
            )
        ranked = tuple(
            sorted(
                rows,
                key=lambda row: (row.scorer_terms.total_score, row.proposal_index),
            )
        )
        if tuple(row.raw_score_rank for row in ranked) != tuple(
            range(1, SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR + 1)
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "raw ranks do not match (total_score, proposal_index)"
            )
        scorer_authority_fields = (
            "authority_input_receipt_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
            "backend_receipt_sha256",
        )
        if any(
            len({getattr(row.scorer_terms, name) for row in rows}) != 1
            for name in scorer_authority_fields
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "ranking rows are cross-wired across scorer authority"
            )
        if any(
            len({getattr(row.posebusters, name) for row in rows}) != 1
            for name in (
                "implementation_sha256",
                "config_sha256",
                "native_pose_artifact_sha256",
                "receptor_artifact_sha256",
            )
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "ranking rows are cross-wired across PoseBusters authority"
            )
        if any(
            len({getattr(row.internal_validity, name) for row in rows}) != 1
            for name in (
                "authority_input_receipt_sha256",
                "problem_fingerprint_sha256",
                "context_fingerprint_sha256",
                "config_fingerprint_sha256",
                "evaluator_implementation_sha256",
            )
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "ranking rows are cross-wired across internal validity authority"
            )
        if any(
            len({getattr(row.rmsd, name) for row in rows}) != 1
            for name in (
                "implementation_sha256",
                "config_sha256",
                "native_pose_artifact_sha256",
                "receptor_artifact_sha256",
                "atom_mapping_sha256",
                "symmetry_policy_sha256",
            )
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "ranking rows are cross-wired across RMSD authority"
            )
        object.__setattr__(self, "candidate_rows", rows)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def ranked_rows(self) -> tuple[SourcePairedClearanceCandidateEvidenceV1, ...]:
        return tuple(sorted(self.candidate_rows, key=lambda row: row.raw_score_rank))

    def _projection(self) -> dict[str, object]:
        ranked = self.ranked_rows
        scorer = self.candidate_rows[0].scorer_terms
        return {
            "schema_id": self.schema_id,
            "arm": self.arm,
            "candidate_denominator": SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR,
            "candidate_rows_by_proposal_index": [
                row.to_dict() for row in self.candidate_rows
            ],
            "raw_rank_order_proposal_indices": [row.proposal_index for row in ranked],
            "raw_rank_order_receipt_sha256": _sha256(
                [row.receipt_sha256 for row in ranked]
            ),
            "top1_candidate_receipt_sha256": ranked[0].receipt_sha256,
            "top5_candidate_receipt_sha256s": [
                row.receipt_sha256 for row in ranked[:5]
            ],
            "scorer_execution_profile": {
                "authority_input_receipt_sha256": (
                    scorer.authority_input_receipt_sha256
                ),
                "context_fingerprint_sha256": scorer.context_fingerprint_sha256,
                "config_fingerprint_sha256": scorer.config_fingerprint_sha256,
                "backend_receipt_sha256": scorer.backend_receipt_sha256,
            },
            "scorer_execution_profile_sha256": _sha256(
                {
                    "authority_input_receipt_sha256": (
                        scorer.authority_input_receipt_sha256
                    ),
                    "context_fingerprint_sha256": scorer.context_fingerprint_sha256,
                    "config_fingerprint_sha256": scorer.config_fingerprint_sha256,
                    "backend_receipt_sha256": scorer.backend_receipt_sha256,
                }
            ),
            "score_term_semantics_fully_rederivable": True,
            "validity_semantics_fully_rederivable": True,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "arm ranking evidence changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedClearanceSelectionActivationReceiptV1:
    case_source: SourcePairedClearanceCaseSourceReceiptV1
    source_proposal_receipt: SourcePairedTorsionRescueProposalReceipt
    current_v7_lineage: SourcePairedClearanceCurrentV7LineageReceiptV1
    source_snapshots: Sequence[SourcePairedTorsionRescueActivationSnapshotV1]
    activated_states: Sequence[SourcePairedClearanceActivatedStateV1]
    baseline_arm: SourcePairedClearanceArmRankingReceiptV1
    experimental_arm: SourcePairedClearanceArmRankingReceiptV1
    schema_id: str = SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID
    _source_proposal_receipt_payload: Mapping[str, object] = field(
        init=False,
        repr=False,
    )
    _source_snapshot_payloads: tuple[Mapping[str, object], ...] = field(
        init=False,
        repr=False,
    )
    _activated_state_payloads: tuple[Mapping[str, object], ...] = field(
        init=False,
        repr=False,
    )
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "activation receipt schema_id is invalid"
            )
        if type(self.case_source) is not SourcePairedClearanceCaseSourceReceiptV1:
            raise TypeError(
                "case_source must be SourcePairedClearanceCaseSourceReceiptV1"
            )
        canonical_case_source = SourcePairedClearanceCaseSourceReceiptV1(
            case_id=self.case_source.case_id,
            source_case_member_path=self.case_source.source_case_member_path,
            source_case_member_sha256=self.case_source.source_case_member_sha256,
            source_case_member_receipt_sha256=(
                self.case_source.source_case_member_receipt_sha256
            ),
            authenticated_input_receipt_sha256=(
                self.case_source.authenticated_input_receipt_sha256
            ),
            problem_fingerprint_sha256=self.case_source.problem_fingerprint_sha256,
            source_proposal_receipt_sha256=(
                self.case_source.source_proposal_receipt_sha256
            ),
            allocation_receipt_sha256=self.case_source.allocation_receipt_sha256,
            native_pose_artifact_sha256=(self.case_source.native_pose_artifact_sha256),
            receptor_artifact_sha256=self.case_source.receptor_artifact_sha256,
            input_artifact_set_sha256=self.case_source.input_artifact_set_sha256,
            current_v7_candidate_lineage_sha256=(
                self.case_source.current_v7_candidate_lineage_sha256
            ),
            source_v11_archive_sha256=self.case_source.source_v11_archive_sha256,
            source_v11_member_manifest_sha256=(
                self.case_source.source_v11_member_manifest_sha256
            ),
            source_v11_bundle_sha256=self.case_source.source_v11_bundle_sha256,
            source_v11_report_sha256=self.case_source.source_v11_report_sha256,
            cohort_case_ids_sha256=self.case_source.cohort_case_ids_sha256,
            schema_id=self.case_source.schema_id,
        )
        if canonical_case_source.to_dict() != self.case_source.to_dict():
            raise SourcePairedClearanceActivationEvidenceError(
                "case source does not independently revalidate against frozen authority"
            )
        object.__setattr__(self, "case_source", canonical_case_source)
        if (
            type(self.source_proposal_receipt)
            is not SourcePairedTorsionRescueProposalReceipt
        ):
            raise TypeError(
                "source_proposal_receipt must be "
                "SourcePairedTorsionRescueProposalReceipt"
            )
        proposal_receipt_sha256 = self.source_proposal_receipt.receipt_sha256
        proposal_receipt = self.source_proposal_receipt.to_dict()
        proposal_projection = dict(proposal_receipt)
        embedded_proposal_sha256 = proposal_projection.pop("receipt_sha256", None)
        allocation = self.source_proposal_receipt.allocation
        if (
            embedded_proposal_sha256 != proposal_receipt_sha256
            or _sha256(proposal_projection) != proposal_receipt_sha256
            or self.case_source.source_proposal_receipt_sha256
            != proposal_receipt_sha256
            or self.case_source.allocation_receipt_sha256
            != allocation.allocation_sha256
            or self.case_source.authenticated_input_receipt_sha256
            != self.source_proposal_receipt.authenticated_input_receipt_sha256
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "case, proposal, and allocation source identities are cross-wired"
            )
        if (
            type(self.current_v7_lineage)
            is not SourcePairedClearanceCurrentV7LineageReceiptV1
        ):
            raise TypeError(
                "current_v7_lineage must be "
                "SourcePairedClearanceCurrentV7LineageReceiptV1"
            )
        canonical_current_v7_lineage = SourcePairedClearanceCurrentV7LineageReceiptV1(
            source_proposal_receipt=self.source_proposal_receipt,
            current_v7_proposals=self.current_v7_lineage.current_v7_proposals,
            source_v11_receipts=self.current_v7_lineage.source_v11_receipts,
            schema_id=self.current_v7_lineage.schema_id,
        )
        if canonical_current_v7_lineage.to_dict() != self.current_v7_lineage.to_dict():
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 lineage does not independently rederive"
            )
        object.__setattr__(
            self,
            "current_v7_lineage",
            canonical_current_v7_lineage,
        )
        lineage_source_receipt = self.current_v7_lineage.source_proposal_receipt
        if (
            lineage_source_receipt.receipt_sha256 != proposal_receipt_sha256
            or self.current_v7_lineage.lineage_identity_sha256
            != self.case_source.current_v7_candidate_lineage_sha256
            or self.current_v7_lineage.problem_fingerprint_sha256
            != self.case_source.problem_fingerprint_sha256
            or lineage_source_receipt.authenticated_input_receipt_sha256
            != self.case_source.authenticated_input_receipt_sha256
            or lineage_source_receipt.allocation.allocation_sha256
            != self.case_source.allocation_receipt_sha256
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "current-V7 lineage is not bound to the frozen case source"
            )
        candidate_slots = proposal_receipt.get("candidate_slots")
        if (
            not isinstance(candidate_slots, list)
            or len(candidate_slots) != SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR
            or any(
                not isinstance(slot, dict) or slot.get("proposal_index") != index
                for index, slot in enumerate(candidate_slots)
            )
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "source proposal receipt does not retain the exact 64 slots"
            )
        expected_target_indices = tuple(
            target for target, _ in allocation.rescue_target_parent_pairs
        )
        snapshots = tuple(self.source_snapshots)
        states = tuple(self.activated_states)
        if (
            len(snapshots) != len(expected_target_indices)
            or len(states) != len(expected_target_indices)
            or len(expected_target_indices) > 4
            or any(
                type(snapshot) is not SourcePairedTorsionRescueActivationSnapshotV1
                for snapshot in snapshots
            )
            or any(
                type(state) is not SourcePairedClearanceActivatedStateV1
                for state in states
            )
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "activation evidence must cover every allocated rescue target"
            )
        snapshot_payloads: list[dict[str, object]] = []
        state_payloads: list[dict[str, object]] = []
        canonical_states: list[SourcePairedClearanceActivatedStateV1] = []
        for snapshot_object, state_object in zip(snapshots, states, strict=True):
            expected_state = build_source_paired_clearance_activated_state_v1(
                snapshot_object,
                state_object.baseline_proposal,
            )
            expected_baseline = expected_state.baseline_proposal
            expected_selected = expected_state.selected_or_retained_proposal
            observed_baseline = state_object.baseline_proposal
            observed_selected = state_object.selected_or_retained_proposal
            for proposal in (
                expected_baseline,
                expected_selected,
                observed_baseline,
                observed_selected,
            ):
                proposal.assert_integrity()
            if (
                expected_state.to_dict() != state_object.to_dict()
                or expected_baseline.fingerprint_sha256
                != observed_baseline.fingerprint_sha256
                or expected_selected.fingerprint_sha256
                != observed_selected.fingerprint_sha256
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "activated state does not rederive from its frozen pre-score decision"
                )
            canonical_states.append(expected_state)
            snapshot = _self_hashed_mapping(
                snapshot_object.to_dict(),
                hash_field="snapshot_sha256",
                schema_id=SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID,
                name="source activation snapshot",
            )
            state = _self_hashed_mapping(
                state_object.to_dict(),
                hash_field="state_sha256",
                schema_id=SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID,
                name="activated clearance state",
            )
            snapshot_payloads.append(snapshot)
            state_payloads.append(state)
        states = tuple(canonical_states)
        observed_target_indices = tuple(
            payload.get("proposal_index") for payload in snapshot_payloads
        )
        if observed_target_indices != expected_target_indices:
            raise SourcePairedClearanceActivationEvidenceError(
                "activation targets do not equal the frozen allocation targets"
            )
        for snapshot, state in zip(
            snapshot_payloads,
            state_payloads,
            strict=True,
        ):
            if (
                state.get("proposal_index") != snapshot.get("proposal_index")
                or state.get("source_snapshot_sha256")
                != snapshot.get("snapshot_sha256")
                or state.get("source_v11_receipt_sha256")
                != snapshot.get("source_v11_receipt_sha256")
                or state.get("allocation_receipt_sha256")
                != allocation.allocation_sha256
                or snapshot.get("allocation_receipt_sha256")
                != allocation.allocation_sha256
                or state.get("source_proposal_receipt_sha256")
                != proposal_receipt_sha256
                or snapshot.get("source_proposal_receipt_sha256")
                != proposal_receipt_sha256
                or snapshot.get("source_proposal_receipt_payload") != proposal_receipt
                or snapshot.get("authenticated_input_receipt_sha256")
                != self.case_source.authenticated_input_receipt_sha256
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "activation snapshot and pre-score decision are cross-wired"
                )

        if (
            type(self.baseline_arm) is not SourcePairedClearanceArmRankingReceiptV1
            or self.baseline_arm.arm != "baseline_current_v7"
            or type(self.experimental_arm)
            is not SourcePairedClearanceArmRankingReceiptV1
            or self.experimental_arm.arm != "experimental_clearance_shadow"
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "activation receipt arms are invalid"
            )
        canonical_baseline_arm = SourcePairedClearanceArmRankingReceiptV1(
            arm=self.baseline_arm.arm,
            candidate_rows=self.baseline_arm.candidate_rows,
            schema_id=self.baseline_arm.schema_id,
        )
        canonical_experimental_arm = SourcePairedClearanceArmRankingReceiptV1(
            arm=self.experimental_arm.arm,
            candidate_rows=self.experimental_arm.candidate_rows,
            schema_id=self.experimental_arm.schema_id,
        )
        if (
            canonical_baseline_arm.to_dict() != self.baseline_arm.to_dict()
            or canonical_experimental_arm.to_dict() != self.experimental_arm.to_dict()
        ):
            raise SourcePairedClearanceActivationEvidenceError(
                "activation receipt arms do not independently rederive"
            )
        object.__setattr__(self, "baseline_arm", canonical_baseline_arm)
        object.__setattr__(self, "experimental_arm", canonical_experimental_arm)
        baseline_rows = self.baseline_arm.candidate_rows
        experimental_rows = self.experimental_arm.candidate_rows

        scorer_fields = (
            "authority_input_receipt_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
            "backend_receipt_sha256",
        )
        validity_fields = (
            "authority_input_receipt_sha256",
            "problem_fingerprint_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
            "evaluator_implementation_sha256",
        )
        posebusters_fields = (
            "implementation_sha256",
            "config_sha256",
            "native_pose_artifact_sha256",
            "receptor_artifact_sha256",
        )
        rmsd_fields = (
            "implementation_sha256",
            "config_sha256",
            "native_pose_artifact_sha256",
            "receptor_artifact_sha256",
            "atom_mapping_sha256",
            "symmetry_policy_sha256",
        )
        for name in scorer_fields:
            if getattr(baseline_rows[0].scorer_terms, name) != getattr(
                experimental_rows[0].scorer_terms,
                name,
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "baseline and experimental scorer authority differ"
                )
        for evidence_name, fields in (
            ("internal validity", validity_fields),
            ("PoseBusters", posebusters_fields),
            ("RMSD", rmsd_fields),
        ):
            baseline_evidence = getattr(
                baseline_rows[0],
                evidence_name.replace(" ", "_").lower()
                if evidence_name != "PoseBusters"
                else "posebusters",
            )
            experimental_evidence = getattr(
                experimental_rows[0],
                evidence_name.replace(" ", "_").lower()
                if evidence_name != "PoseBusters"
                else "posebusters",
            )
            for name in fields:
                if getattr(baseline_evidence, name) != getattr(
                    experimental_evidence,
                    name,
                ):
                    raise SourcePairedClearanceActivationEvidenceError(
                        f"baseline and experimental {evidence_name} authority differ"
                    )
        for rows in (baseline_rows, experimental_rows):
            if (
                rows[0].scorer_terms.authority_input_receipt_sha256
                != self.case_source.authenticated_input_receipt_sha256
                or rows[0].internal_validity.authority_input_receipt_sha256
                != self.case_source.authenticated_input_receipt_sha256
                or rows[0].internal_validity.problem_fingerprint_sha256
                != self.case_source.problem_fingerprint_sha256
                or rows[0].posebusters.native_pose_artifact_sha256
                != self.case_source.native_pose_artifact_sha256
                or rows[0].posebusters.receptor_artifact_sha256
                != self.case_source.receptor_artifact_sha256
                or rows[0].rmsd.native_pose_artifact_sha256
                != self.case_source.native_pose_artifact_sha256
                or rows[0].rmsd.receptor_artifact_sha256
                != self.case_source.receptor_artifact_sha256
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "score or validity authority is not bound to the source case"
                )

        for index, (baseline, experimental, slot, current_v7_proposal) in enumerate(
            zip(
                baseline_rows,
                experimental_rows,
                candidate_slots,
                self.current_v7_lineage.current_v7_proposals,
                strict=True,
            )
        ):
            assert isinstance(slot, dict)
            current_v7_proposal.assert_integrity()
            if (
                baseline.candidate_id != slot.get("candidate_id")
                or experimental.candidate_id != slot.get("candidate_id")
                or baseline.source_proposal_fingerprint_sha256
                != slot.get("proposal_fingerprint_sha256")
                or experimental.source_proposal_fingerprint_sha256
                != slot.get("proposal_fingerprint_sha256")
                or baseline.candidate_proposal_fingerprint_sha256
                != current_v7_proposal.fingerprint_sha256
                or baseline.coordinate_sha256
                != current_v7_proposal.coordinate_fingerprint_sha256
                or baseline.internal_validity.problem_fingerprint_sha256
                != current_v7_proposal.problem_fingerprint_sha256
                or self.current_v7_lineage.source_proposal_fingerprint_sha256(index)
                != slot.get("proposal_fingerprint_sha256")
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    f"candidate slot {index} is not bound to exact current-V7 lineage"
                )

        state_by_index = {
            int(payload["proposal_index"]): payload for payload in state_payloads
        }
        snapshot_by_index = {
            int(payload["proposal_index"]): payload for payload in snapshot_payloads
        }
        selected_replacement_indices: set[int] = set()
        for index, (baseline, experimental) in enumerate(
            zip(baseline_rows, experimental_rows, strict=True)
        ):
            state = state_by_index.get(index)
            if state is None:
                if (
                    baseline._scientific_projection()
                    != experimental._scientific_projection()
                ):
                    raise SourcePairedClearanceActivationEvidenceError(
                        "experimental arm changed a non-target candidate"
                    )
                continue
            snapshot = snapshot_by_index[index]
            if (
                snapshot.get("candidate_proposal_fingerprint_sha256")
                != baseline.candidate_proposal_fingerprint_sha256
                or snapshot.get("candidate_coordinate_sha256")
                != baseline.coordinate_sha256
                or state.get("baseline_candidate_proposal_fingerprint_sha256")
                != baseline.candidate_proposal_fingerprint_sha256
                or state.get("baseline_candidate_coordinate_sha256")
                != baseline.coordinate_sha256
                or state.get(
                    "selected_or_retained_candidate_proposal_fingerprint_sha256"
                )
                != experimental.candidate_proposal_fingerprint_sha256
                or state.get("selected_or_retained_coordinate_sha256")
                != experimental.coordinate_sha256
                or baseline.candidate_id != experimental.candidate_id
                or baseline.source_proposal_fingerprint_sha256
                != snapshot.get("source_proposal_fingerprint_sha256")
                or experimental.source_proposal_fingerprint_sha256
                != snapshot.get("source_proposal_fingerprint_sha256")
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "target candidate does not match its pre-score activated state"
                )
            selection_applied = state.get("selection_applied")
            if type(selection_applied) is not bool:
                raise SourcePairedClearanceActivationEvidenceError(
                    "activated-state selection flag is invalid"
                )
            same_scientific_evidence = (
                baseline._scientific_projection()
                == experimental._scientific_projection()
            )
            if selection_applied:
                if (
                    state.get("shadow_selection_eligible") is not True
                    or same_scientific_evidence
                    or baseline.candidate_proposal_fingerprint_sha256
                    == experimental.candidate_proposal_fingerprint_sha256
                    or baseline.coordinate_sha256 == experimental.coordinate_sha256
                ):
                    raise SourcePairedClearanceActivationEvidenceError(
                        "selected target did not produce one bound replacement state"
                    )
                selected_replacement_indices.add(index)
            elif not same_scientific_evidence:
                raise SourcePairedClearanceActivationEvidenceError(
                    "retained target changed post-decision scientific evidence"
                )

        expected_state_boundary = {
            "decision_sealed_before_scoring": True,
            "score_rank_rmsd_posebusters_native_or_case_identity_used": False,
            "result_dependent_allocation": False,
            "default_v7_output_changed": False,
            "historical_ab_execution_authorized": False,
            "historical_result_materialization_authorized": False,
            "generic_runner_cli_wired": False,
            "product_path_wired": False,
            "fresh_execution_authorized": False,
            "customer_pose_emission_authorized": False,
            "stage0_eligible": False,
            "public_or_scientific_claim_authorized": False,
            "development_only": True,
            "claim_safe": False,
        }
        for state in state_payloads:
            if any(
                state.get(name) is not value
                for name, value in expected_state_boundary.items()
            ):
                raise SourcePairedClearanceActivationEvidenceError(
                    "activated state exceeds its frozen evidence-only authority"
                )

        object.__setattr__(self, "source_snapshots", snapshots)
        object.__setattr__(self, "activated_states", states)
        object.__setattr__(
            self,
            "_source_proposal_receipt_payload",
            MappingProxyType(proposal_receipt),
        )
        object.__setattr__(
            self,
            "_source_snapshot_payloads",
            tuple(MappingProxyType(payload) for payload in snapshot_payloads),
        )
        object.__setattr__(
            self,
            "_activated_state_payloads",
            tuple(MappingProxyType(payload) for payload in state_payloads),
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        targets: list[dict[str, object]] = []
        selected_indices: list[int] = []
        for snapshot, state in zip(
            self._source_snapshot_payloads,
            self._activated_state_payloads,
            strict=True,
        ):
            proposal_index = int(snapshot["proposal_index"])
            baseline_candidate = self.baseline_arm.candidate_rows[proposal_index]
            selected_candidate = self.experimental_arm.candidate_rows[proposal_index]
            if state.get("selection_applied") is True:
                selected_indices.append(proposal_index)
            targets.append(
                {
                    "proposal_index": proposal_index,
                    "source_v11_receipt": snapshot.get("source_v11_receipt_payload"),
                    "source_v11_receipt_sha256": snapshot.get(
                        "source_v11_receipt_sha256"
                    ),
                    "source_snapshot": dict(snapshot),
                    "policy_sha256": state.get("policy_sha256"),
                    "probe_input_sha256": state.get("probe_input_sha256"),
                    "decision_sha256": state.get("decision_sha256"),
                    "activated_state": dict(state),
                    "baseline_candidate": baseline_candidate.to_dict(),
                    "selected_or_retained_candidate": selected_candidate.to_dict(),
                }
            )
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_source.case_id,
            "case_source": self.case_source.to_dict(),
            "source_proposal_receipt": dict(self._source_proposal_receipt_payload),
            "source_proposal_receipt_sha256": (
                self.source_proposal_receipt.receipt_sha256
            ),
            "current_v7_lineage": self.current_v7_lineage.to_dict(),
            "current_v7_candidate_lineage_sha256": (
                self.current_v7_lineage.lineage_identity_sha256
            ),
            "allocation_receipt": self.source_proposal_receipt.allocation.to_dict(),
            "allocation_receipt_sha256": (
                self.source_proposal_receipt.allocation.allocation_sha256
            ),
            "activation_target_count": len(targets),
            "activation_targets": targets,
            "selected_replacement_proposal_indices": selected_indices,
            "baseline_arm_ranking": self.baseline_arm.to_dict(),
            "experimental_arm_ranking": self.experimental_arm.to_dict(),
            "full_scoring_and_validity_evidence": True,
            "full_source_proposal_lineage_verified": True,
            "full_current_v7_candidate_lineage_verified": True,
            "full_posebusters_check_set_verified": True,
            "authenticated_rmsd_receipts_verified": True,
            "score_term_semantics_fully_rederivable": True,
            "top1_top5_semantics_fully_rederivable": True,
            "decision_sealed_before_score_rank_validity": True,
            "historical_ab_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "product_or_claim_authority": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise SourcePairedClearanceActivationEvidenceError(
                "activation receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


__all__ = [
    "INTERNAL_VALIDITY_REQUIRED_CHECK_NAMES",
    "POSEBUSTERS_REQUIRED_CHECK_NAMES",
    "POSEBUSTERS_REQUIRED_CHECK_SET_SHA256",
    "SOURCE_PAIRED_CLEARANCE_ACTIVATED_STATE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_ACTIVATION_SNAPSHOT_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_ARM_RANKING_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_CANDIDATE_DENOMINATOR",
    "SOURCE_PAIRED_CLEARANCE_CANDIDATE_EVIDENCE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_AUTHORITY_SHA256",
    "SOURCE_PAIRED_CLEARANCE_CASE_SOURCE_RECEIPT_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_CURRENT_V7_LINEAGE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_INTERNAL_VALIDITY_EVIDENCE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_POSEBUSTERS_EVIDENCE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_RMSD_EVIDENCE_SCHEMA_ID",
    "SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS",
    "SOURCE_PAIRED_CLEARANCE_SELECTION_ACTIVATION_RECEIPT_SCHEMA_ID",
    "SourcePairedClearanceActivationEvidenceError",
    "SourcePairedClearanceArmRankingReceiptV1",
    "SourcePairedClearanceCaseSourceReceiptV1",
    "SourcePairedClearanceCandidateEvidenceV1",
    "SourcePairedClearanceCurrentV7LineageReceiptV1",
    "SourcePairedClearanceInternalValidityEvidenceV1",
    "SourcePairedClearancePoseBustersEvidenceV1",
    "SourcePairedClearanceRmsdEvidenceV1",
    "SourcePairedClearanceSelectionActivationReceiptV1",
]

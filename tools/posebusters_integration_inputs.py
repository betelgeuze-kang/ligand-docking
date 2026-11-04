"""Pinned input preparation for all successful cases in the fixed development32.

The three originally unprepared cases remain explicit in the denominator.
This module does not generate new poses or run molecular evaluations.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from typing import Any

from tools import posebusters_replay_inputs as frozen

SCHEMA_ID = "betelgeuze.posebusters_integration_inputs/1.0.0"
ARTIFACT_SPECS = (*frozen.ARTIFACT_SPECS[1:],
    frozen.ArtifactSpec("development-26", 13265626749,
        "e07bf3b1e0d0793b6edcb0e91e523e4faf84c0042c2c915b5ae3a79ba62fccb5",
        "28b98747c1c44cebfebae2b4c1662410737544c836ca5cc73b95d853a336d279",
        "2a61a6bbcc9cb72e7963c886f5cdd04b83dbed8e8bb433ee8a05b8a4bb4236e3"),
)
# case_id, source artifact, source root, original index, seed, receipt file hash.
CASE_SPECS = (
    ("5SD5_HWI", "development-2", "development/cases/5SD5_HWI", 2, 2026072702, "98678dfd93b5ff3d0908334b3ec4277452b09b3dae5986c9b8465ac80ee56982"),
    ("5SIS_JSM", "development-2", "development/cases/5SIS_JSM", 3, 2026072703, "e53f1dfd135b89f4c89dfbd9aed9b760c2072392eb4788b8a1eec6e921a42d8c"),
    ("6M2B_EZO", "development-2", "development/cases/6M2B_EZO", 4, 2026072704, "84fb8a9d3cf4cd0b29ddb3cbf876837186507c70841dd1de90d6fc61fa75b537"),
    ("6T88_MWQ", "development-2", "development/cases/6T88_MWQ", 6, 2026072706, "f6ce760d1aee608fe40ca5a8946f12f0ea4c29cb707ac81a42773b6d7d1543f4"),
    ("6TW5_9M2", "development-2", "development/cases/6TW5_9M2", 7, 2026072707, "3174675e9c20c9e16f6c2a0f937503d3c7181a7b7bcfec0730b84310db1179be"),
    ("6TW7_NZB", "development-2", "development/cases/6TW7_NZB", 8, 2026072708, "08a16d6fcdaea1f1ed87701dcfd64432e29c4038c23e8893de2ce6b45b5ade49"),
    ("6VTA_AKN", "development-2", "development/cases/6VTA_AKN", 9, 2026072709, "90eb1135cd7c47264415cbbc38461ee2d86e03c2d1c659e3cfc3d7b1385be0c1"),
    ("6WTN_RXT", "development-10", "development/cases/6WTN_RXT", 10, 2026072710, "475094ce50b2e120ef0c13401cb309a2f7408fd6503ffdd538cf0e290793d676"),
    ("6XBO_5MC", "development-10", "development/cases/6XBO_5MC", 11, 2026072711, "c49da8df092216116aa0c4ac71b467abd3a0961e6f55c37b53af5ea66eac13dd"),
    ("6XCT_478", "development-10", "development/cases/6XCT_478", 12, 2026072712, "4155054b09da2f0b5eb8a0b9fe876d71ef3bf0ababfbd667be36c41690562619"),
    ("6XG5_TOP", "development-10", "development/cases/6XG5_TOP", 13, 2026072713, "4ad5ebf20687a196d4977927dd0b469a1476e1a5963e01b2beec37a0358aed28"),
    ("6XHT_V2V", "development-10", "development/cases/6XHT_V2V", 14, 2026072714, "0e018d349e582cc1b5ed1380a59a9169f00eb705c4bbb8cc61f6d235eefe9011"),
    ("6XM9_V55", "development-10", "development/cases/6XM9_V55", 15, 2026072715, "ce90fb4aeee2720f8e1a5518917ebd881a2070e1e8446cdf798e70e18bf61a68"),
    ("6YMS_OZH", "development-10", "development/cases/6YMS_OZH", 17, 2026072717, "408b8fcc1ddc4efda5c28a00d2a2c148f2beaf55d742fc49c920b664b8d3deae"),
    ("6YQV_8K2", "development-18", "development/cases/6YQV_8K2", 18, 2026072718, "0090af41ab074cc3e43d64c3556626b8952d82c2da9cefbbe58cfd2b4a38788b"),
    ("6YQW_82I", "development-18", "development/cases/6YQW_82I", 19, 2026072719, "a37d72fcaa873b589a7ec42dce3f5bba047143aa541438d840e62142902c0576"),
    ("6YRV_PJ8", "development-18", "development/cases/6YRV_PJ8", 21, 2026072721, "54d323f7a85660fad8e89ffa06181cb9421e429be386fbc11d2c44ede0be052c"),
    ("6YSP_PAL", "development-18", "development/cases/6YSP_PAL", 22, 2026072722, "087de77daeef402ee56b5571042d4952d486c5a02324870fd14c9769c4ae8ff1"),
    ("6YT6_PKE", "development-18", "development/cases/6YT6_PKE", 23, 2026072723, "07c955386c5c948c2aa0ec0281e75aa2890044d05a80da476d07586ba42b4c8e"),
    ("6YYO_Q1K", "development-18", "development/cases/6YYO_Q1K", 24, 2026072724, "e5c28035379d93f8028494ef4427f0a668acd1d43d628d6974ee40da56eb47fd"),
    ("6Z0R_Q4H", "development-18", "development/cases/6Z0R_Q4H", 25, 2026072725, "380dd02f26f5f95e165e77efe6418dc42f6126179d078c01358922b58dd1ffd3"),
    ("6Z14_Q4Z", "development-26", "development/cases/6Z14_Q4Z", 26, 2026072726, "dbcee51802965bbb24ebe1c168df60eac7e2b8b2fe4afd700e47a822508375ee"),
    ("6Z1C_7EY", "development-26", "development/cases/6Z1C_7EY", 27, 2026072727, "ae39250bcafdadd08c66e8584a86369c718da4b7c74bc30b368f76538c38dd71"),
    ("6Z2C_Q5E", "development-26", "development/cases/6Z2C_Q5E", 28, 2026072728, "a9730fc24cc5c430bee8d9897a768b16a410766fc740fe0d412bfc24918129c7"),
    ("6Z4N_Q7B", "development-26", "development/cases/6Z4N_Q7B", 29, 2026072729, "25fc9dc2a3adfd31b8b0be7cdc0cd9dfea80d39bd104e8f267256a3b3a90b248"),
    ("6ZAE_ACV", "development-26", "development/cases/6ZAE_ACV", 30, 2026072730, "9dae693ce785cc6693c83803f418876a375f8e1e4f3a3d60bfa36669cf61e13b"),
    ("6ZC3_JOR", "development-26", "development/cases/6ZC3_JOR", 31, 2026072731, "682802f9a85b42a87f7278755b85bad47801deec04fbd948b52a63239c12780a"),
    ("6ZCY_QF8", "development-26", "development/cases/6ZCY_QF8", 32, 2026072732, "e50ed3ccc3103cbb0e990d139967bc1809f512dbcfcc3cfcd77ca921e043395d"),
    ("6ZK5_IMH", "development-26", "development/cases/6ZK5_IMH", 33, 2026072733, "65bcb7f6e28277753ea3fc847c4280b859eb2ce0b86f811e2aad7c447cc9a206"),
)
NOT_PREPARED_SPECS = (
    ("6M73_FNR", "development-2", "development/cases/6M73_FNR", 5, 2026072705, "19ee9e8c106e82c4f7524e2c74dcf87af3cc2f8cad226f6518ac68128e8809bc"),
    ("6YJA_2BA", "development-10", "development/cases/6YJA_2BA", 16, 2026072716, "69ed543e60b5d5320ef17fa7fa841e9ef52538370fbd4f0d5e86a5a0d6247b3b"),
    ("6YR2_T1C", "development-18", "development/cases/6YR2_T1C", 20, 2026072720, "3cc2cdb4e2f5bcbe252250a99d240d779b30568775b6ad6fb9c7c677a9ad06fe"),
)
CASE_IDS = tuple(row[0] for row in CASE_SPECS)
FIXED_CASE_ORDER = ["5SD5_HWI","5SIS_JSM","6M2B_EZO","6M73_FNR","6T88_MWQ","6TW5_9M2","6TW7_NZB","6VTA_AKN","6WTN_RXT","6XBO_5MC","6XCT_478","6XG5_TOP","6XHT_V2V","6XM9_V55","6YJA_2BA","6YMS_OZH","6YQV_8K2","6YQW_82I","6YR2_T1C","6YRV_PJ8","6YSP_PAL","6YT6_PKE","6YYO_Q1K","6Z0R_Q4H","6Z14_Q4Z","6Z1C_7EY","6Z2C_Q5E","6Z4N_Q7B","6ZAE_ACV","6ZC3_JOR","6ZCY_QF8","6ZK5_IMH"]
PILOT_CASES = ("6T88_MWQ", "6YSP_PAL")


def validate_fixed_cohort() -> None:
    all_rows = (*CASE_SPECS, *NOT_PREPARED_SPECS)
    frozen._require(len(CASE_SPECS) == 29 and len(NOT_PREPARED_SPECS) == 3,
                    "fixed development denominator changed")
    frozen._require(len({row[0] for row in all_rows}) == 32,
                    "duplicate fixed development case")
    frozen._require(sorted(row[3] for row in all_rows) == list(range(2, 34)),
                    "fixed development indices changed")
    frozen._require([row[0] for row in sorted(all_rows, key=lambda r: r[3])] == FIXED_CASE_ORDER,
                    "fixed development case order changed")
    frozen._require(all(row[4] == 2026072700 + row[3] for row in all_rows),
                    "original case seed changed")


def prepare_cases(artifact_root: Path, output_root: Path) -> dict[str, Any]:
    validate_fixed_cohort()
    artifact_root = frozen._no_symlink_path(Path(artifact_root))
    output_root = frozen._no_symlink_path(Path(output_root))
    frozen._require(artifact_root.is_dir(), "artifact root is missing")
    frozen._require(not output_root.exists() and not output_root.is_symlink(),
                    "input output directory must be fresh")
    frozen._require(output_root.parent.is_dir(), "input parent directory is missing")
    staging = Path(tempfile.mkdtemp(prefix=f".{output_root.name}-preparing-", dir=output_root.parent))
    try:
        cases, not_prepared, artifacts = {}, [], []
        for spec in ARTIFACT_SPECS:
            archive, _ = frozen._load_artifact(artifact_root, spec)
            try:
                artifacts.append(archive.summary)
                for case_id, key, case_root, index, seed, receipt_file_sha256 in CASE_SPECS:
                    if key != spec.key:
                        continue
                    receipt_path = f"{case_root}/engines/engine_v2/receipt.json"
                    frozen._require(archive.inventory[receipt_path]["sha256"] == receipt_file_sha256,
                                    "original successful receipt changed")
                    descriptor = frozen._prepare_case(
                        archive, case_id=case_id, artifact_key=key, case_root=case_root,
                        global_index=index, staging=staging, final_root=output_root)
                    materialization = archive.document(f"{case_root}/materialization/materialization.json")
                    frozen._require(type(materialization.get("frozen_case_seed")) is int and
                                    materialization["frozen_case_seed"] == seed, "original seed mismatch")
                    descriptor["frozen_case_seed"] = seed
                    descriptor["purpose"] = "fixed_development32_successful_case"
                    row = archive.document(receipt_path)["result"]
                    descriptor["source_row"] = frozen._write_file(
                        staging, output_root, f"cases/{case_id}/source-row.json",
                        frozen._canonical(row) + b"\n")
                    cases[case_id] = descriptor
                for case_id, key, case_root, index, seed, receipt_file_sha256 in NOT_PREPARED_SPECS:
                    if key != spec.key:
                        continue
                    receipt_path = f"{case_root}/engines/engine_v2/receipt.json"
                    frozen._require(archive.inventory[receipt_path]["sha256"] == receipt_file_sha256,
                                    "original unprepared receipt changed")
                    receipt = archive.document(receipt_path)
                    receipt_sha256 = frozen._self_hash(receipt, "receipt_sha256", receipt_path)
                    row = receipt["result"]
                    frozen._require(row.get("case_id") == case_id and row.get("status") == "failure" and
                                    row.get("engine_id") == "engine_v2", "unprepared case status changed")
                    materialization = archive.document(f"{case_root}/materialization/materialization.json")
                    frozen._require(materialization.get("frozen_case_seed") == seed, "unprepared seed changed")
                    request = archive.document(f"{case_root}/engines/engine_v2/request.json")
                    frozen._require(request.get("global_index") == index and request.get("case_id") == case_id,
                                    "unprepared request index changed")
                    frozen._validate_source(request.get("source"))
                    not_prepared.append(dict(
                        case_id=case_id, source_global_index=index, artifact_key=key,
                        status="not_prepared", candidate_count=0,
                        preparation_failure_code="unsupported_large_ring_system",
                        receipt_sha256=receipt_sha256, receipt_file_sha256=receipt_file_sha256))
            finally:
                archive.close()
        frozen._require(set(cases) == set(CASE_IDS) and
                        {row["case_id"] for row in not_prepared} == {row[0] for row in NOT_PREPARED_SPECS},
                        "incomplete fixed development cohort")
        manifest = dict(
            schema_id=SCHEMA_ID, source_run_id=frozen.SOURCE_RUN_ID,
            source_execution_commit=frozen.SOURCE_COMMIT, source_execution_tree=frozen.SOURCE_TREE,
            source_evaluation_pipeline_sha256=frozen.EVALUATION_PIPELINE_SHA256,
            source_environment_content_identity_sha256=frozen.ENVIRONMENT_CONTENT_IDENTITY_SHA256,
            artifact_root=str(artifact_root), output_root=str(output_root),
            fixed_case_denominator=32, fixed_case_order=FIXED_CASE_ORDER,
            successful_case_count=29, not_prepared_case_count=3,
            molecular_evaluation_performed=False, candidate_generation_performed=False,
            exact_saved_top5_record_count=145, expected_candidate_record_count=1856,
            artifacts=artifacts, cases=[cases[case_id] for case_id in CASE_IDS],
            not_prepared=sorted(not_prepared, key=lambda r: r["source_global_index"]))
        frozen._write_file(staging, output_root, "manifest.json", frozen._canonical(manifest) + b"\n")
        frozen._require(not output_root.exists() and not output_root.is_symlink(),
                        "input output appeared during preparation")
        staging.rename(output_root)
        return manifest
    except BaseException:
        shutil.rmtree(staging)
        raise


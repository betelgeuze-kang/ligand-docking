#!/usr/bin/env python3
"""Pack and verify the exact historical source-paired V1.1 clearance audit."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import subprocess
import sys
import tarfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.analyze_engine_v2_score_terms as score_term_analysis  # noqa: E402
import tools.build_engine_v2_source_paired_failure_atlas as failure_atlas  # noqa: E402


SCHEMA_ID = "betelgeuze.engine_v2_source_paired_clearance_v11_audit/1.2.0"
OPERATOR_OBSERVED_CHECKOUT_OR_BASE_SHA1 = "6a749540339db5e53875841e463cfcbcdf7072b2"
EXPECTED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6M73_FNR",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
EXPECTED_UNCOVERED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_PREPARATION_FAILURE_CASE_ID = "6M73_FNR"
EXPECTED_PREPARATION_FAILURE_CODE = "unsupported_large_ring_system"
EXPECTED_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
)
PUBLIC_REDOCKING_ARCHIVE_SHA256 = (
    "495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c"
)
PUBLIC_REDOCKING_SOURCE_IDS_SHA256 = (
    "a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6"
)
PUBLIC_REDOCKING_RUNNER_ID = "betelgeuze.engine_v2_public_redocking_300_runner/2.13.0"
PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_case_execution/1.1.0"
)
PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_case_materialization/1.0.0"
)
PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE = "uniform_torsion_rescue_variant"
EXPECTED_BASE_PROPOSAL_MODES = frozenset(
    {
        "donor_acceptor_hotspot",
        "charge_anchor",
        "hydrophobic_patch",
        "aromatic_plane",
        "shape_complementarity",
        "multi_anchor_hotspot",
        "pocket_center_baseline",
        "uniform_fallback",
        "uniform_v3_rigid_ensemble",
    }
)
EXPECTED_POSEBUSTERS_CHEMICAL_CHECK_IDS = (
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "double_bond_flatness",
    "internal_energy",
)
EXPECTED_POSEBUSTERS_GEOMETRIC_CHECK_IDS = (
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)
EXPECTED_SCORER_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
    "total_score",
)
EXPECTED_BASELINE_SUMMARY_SCHEMA_ID = (
    "betelgeuze.engine_v2_historical_development_execution_summary/1.0.0"
)
EXPECTED_RESCUE_SUMMARY_SCHEMA_ID = (
    "betelgeuze.engine_v2_historical_development_source_paired_"
    "torsion_rescue_summary/1.0.0"
)
EXPECTED_ANALYSIS_SCHEMA_ID = (
    "betelgeuze.engine_v2_scorer_v1_development_analysis/1.2.0"
)
EXPECTED_BASELINE_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_engine_v2_diagnostics/1.5.0"
)
EXPECTED_RESCUE_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_engine_v2_diagnostics/1.6.0"
)
EXPECTED_BASELINE_CANDIDATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0"
)
EXPECTED_RESCUE_CANDIDATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.7.0"
)
EXPECTED_CANDIDATE_COUNT = 64
EXPECTED_SCORER_BACKEND = "python_reference"
EXPECTED_INTERACTION_REFINER_CONFIG_SHA256 = (
    "5e8b61d242abfe52e04df6de7f56a137b7736150e95d3e6b526e4269eb275337"
)
# The execution-policy hash above identifies the shared generic refiner policy.
# V1.1 receipts bind a case-specific composite refiner configuration that also
# includes authenticated authority, allocation, and proposal context.
EXPECTED_SOURCE_PAIRED_REFINER_COMPOSITE_CONFIG_SHA256_BY_CASE = {
    "5SD5_HWI": ("1d4896a6597ecde6956565730d343bbf0ff25cfc287a6d74537565f1f42abe71"),
    "5SIS_JSM": ("6edbf859fb4933ea5cd30a5901bd195f7583de8ca46ab90868944b6290fa62cc"),
    "6M2B_EZO": ("60a13d239dc58f684cfccc4f0576792026f2807a8fc275e7154aba8602908dc3"),
    "6T88_MWQ": ("81136a4d81b5728f13aafb58ad68bd19c5e6cff2c46caf06ad58a32058ec5c89"),
    "6TW5_9M2": ("694ff7b3cf2a63ebe4b1b1dc35bb6ac676ca3b6a91431b8abd5ee28d4803d59a"),
    "6TW7_NZB": ("565b30512cc9ae53897b43abceefd09edd43aa0c0ae0b339bc9ecb7e6a21176b"),
    "6VTA_AKN": ("db16a22b37d24246d9fd7f13f60bcb8218ba68448433e5a50e840e78bc99649b"),
    "6WTN_RXT": ("aa3fb65a9a171553f1c6ce69d17ea424b2f24497eb3375a71c3b1fb457bb65c7"),
}
EXPECTED_BASELINE_V6_COMPOSITE_CONFIG_SHA256_BY_CASE = {
    "5SD5_HWI": "e9573816ae586c472f2660e11826f4bd523403fa25b78d42322d7befe3d2e204",
    "5SIS_JSM": "628c979f9bd322797744003d64965d8e894effe100ce081a88d7ae317bf2ab22",
    "6M2B_EZO": "81dde35e1db400a6b05ab0aca9cd62ab2793f3edea37a4841e61ae44e4c2da33",
    "6T88_MWQ": "65885329393d474a20d7f1e5741a316a250dfbca306343d7c97c08c824ce8460",
    "6TW5_9M2": "adabd62848da6e8031b108eafa23ec6ed8a3cc8342b94f36c3e1dadbb529044b",
    "6TW7_NZB": "73bbbaee9ec90cad5ba33892998571ed3122b501014b5e1015fd79b55a1b4e0a",
    "6VTA_AKN": "f7e16e2f74ca22018dfe61c100bc7847a1dff58235b23054261a379e6ed9b0dc",
    "6WTN_RXT": "4aa9fdb5aa2286d31704e1112b749e142836aedf89904939d264e1ecd94ce194",
}
EXPECTED_SCORER_BACKEND_RECEIPT = {
    "backend": EXPECTED_SCORER_BACKEND,
    "backend_version": "1.0.0",
    "build_flags": [],
    "cargo_lock_sha256": "",
    "extension_sha256": "",
    "implementation_source_sha256": (
        "80e758ac66e0b9825ce3372eac6a4adc6f2dc6fe4b1f08cf95402dcfbf2cee39"
    ),
    "implicit_fallback_allowed": False,
    "options_fingerprint_sha256": (
        "3e1279f7426288224a1377e9021cc07c3a62115a3ac38534a70871fb8911415f"
    ),
    "receipt_sha256": (
        "4070816b9d99437002a617300c16162b944d0a62c4e5eb48670053cd84203d00"
    ),
    "rustc_version": "",
    "schema_id": "betelgeuze.engine_v2_scorer_v1_backend_receipt/1.0.0",
    "target_triple": "",
}
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROFILE_ID = (
    "betelgeuze.engine_v2_historical_development_source_paired_torsion_rescue/1.0.0"
)
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256 = (
    "1930119181619f603f563e3e2aabc8b7ae1347b58e2fcf0a657a7b234f8bb8a6"
)
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256 = (
    "2974e9ba80479cccc97dce1b51567e8e7309e7f89c983401c9a8966a3d08633f"
)
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP = 4
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_proposal_receipt/1.0.0"
)
EXPECTED_BASELINE_GUIDED_PLACEMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_receipt/1.3.0"
)
EXPECTED_RESCUE_GUIDED_PLACEMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_guided_placement_receipt/1.4.0"
)
EXPECTED_BASELINE_V6_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_hybrid_ensemble_receipt/6.0.0"
)
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_policy/1.0.0"
)
EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_allocation/1.0.0"
)
EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE = {
    "5SD5_HWI": "44fdb41049d49b6ea5198f39e94772ad62065b1ba47e3c0191e00e535aa10f64",
    "5SIS_JSM": "3d7e00d50fa48006ab8a00fe2e3c00338e6f53ca18716e2252264fffd4c95b73",
    "6M2B_EZO": "95d90c25450dfc6556fd7dadd2e0f2580d4e29460528f3cf961c85a4635bc69c",
    "6T88_MWQ": "1064d7956267037db21afa6d20fed086d4b92792a3d9a732755d8fc1dd7bdee3",
    "6TW5_9M2": "2dbf76b8e7db925215e16123476b8a1c14420febf2826898588fea6d63e5187f",
    "6TW7_NZB": "11fbd284284313dec2a141f6209e08c2019fac505e67277742b48f973f306851",
    "6VTA_AKN": "7d21c9f638c77f1a95e6455b8a489ceb23f3935d4dfe42d8de9c5bd5a73d281b",
    "6WTN_RXT": "1ecb7dcad4a3ff6fa7402f78bf23c1b31d57549e789274fe2be7655fecf9fa38",
}
EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE = {
    "5SD5_HWI": "f2a100e35c8951f5ce954a963091ee04cf6d86eb15d6c47e8cc1e8a2d6ab67ba",
    "5SIS_JSM": "7ca5389edbfbf9a06b467da95336e21b8f1bcb0d4cfe91384d9b6ef3829637b5",
    "6M2B_EZO": "ee5e729f4171962a8326012ec6b80c52c0f708398b412ebc4665c3f094590368",
    "6T88_MWQ": "51339ee6fc9138f84753ad7fa637f0f8957ae18af0e0facc98a1a340ce57293d",
    "6TW5_9M2": "906ad8807a1da95345921f4139ca39f73a57427f16c156b843a2b53c3d0352e3",
    "6TW7_NZB": "279b65abf065c925b61fe6234cdf57215b7583c615c29f0563ae6f802bebbf80",
    "6VTA_AKN": "3c1f1e5a4fb026321b116cc10cbefe79a1a0447b0f4b1f9b2d0d392200749641",
    "6WTN_RXT": "e5b35bbb5852821f35151ddd6b3c496076268f57a1fd72d7b7c0cf65ed2e9d2f",
}
EXPECTED_RESCUE_CANDIDATE_RECEIPT_SET_SHA256_BY_CASE = {
    "5SD5_HWI": "1ad73e8bd63ec0dad264267fc3be704501cc96c7deedf27829a243750d9636e1",
    "5SIS_JSM": "26455e788ea11465587667d5085018788e153cb128830769a059f8a3b2db396b",
    "6M2B_EZO": "478e74c434090f1cf049d444c9da10bc8546d8e4c615e622c8a15715147df28b",
    "6T88_MWQ": "cfff587271fa72a730a67ec9a8f377ee548243fd1d93fe8928f957a83b28e9be",
    "6TW5_9M2": "dee3c999d6ca9b90d6f0733b337e0359987ca4b44c19b8316bfb716bbc3bbb38",
    "6TW7_NZB": "1947e10103e3bc25ab4e23f5e16d5d6a0f718906eccf98b4caa3fd3798e59183",
    "6VTA_AKN": "5cf355f7348e218096516276fbd3f6f57715fbaa27e7261321db770196066bb3",
    "6WTN_RXT": "6b15a5f5abdcc66fc8c623e01b7b0f163937994007fe390783d0a5b85e000d29",
}
EXPECTED_RESCUE_CANDIDATE_PROPOSAL_FINGERPRINT_SET_SHA256_BY_CASE = {
    "5SD5_HWI": "1edd348d5d99e04e26874ef8c69f76d3c00e5d48e2cfa9886d6848696cc7604f",
    "5SIS_JSM": "74e1bc4618cf48515166011ced34edb42f3b158d68949fdca5009d4cf6baf6fa",
    "6M2B_EZO": "ca33130b12f29b8b7b75d1e2107f4b0dbdaf07308e4c991110428862c9d5b5ed",
    "6T88_MWQ": "228182491bda6f10d718125ad2356ee5c07c44614c1c3432231883427b7e4976",
    "6TW5_9M2": "73b4a276b4917f3ab2d58168b6be9652d98f239279f92d680d1b8207a94984a6",
    "6TW7_NZB": "f163c9196c00f1ab3236e9c5b5eb8d225baa57d1b1123ca64dfad7522b7a4160",
    "6VTA_AKN": "308b8b9463a666163180f6b67ab07f8b3950f9b7122b4ac4201b5be0d774ac07",
    "6WTN_RXT": "df6bf6c4fbd475dca26e32b66d8c6562bccc1be73c247387f443fc0a4f51e112",
}
EXPECTED_CANDIDATE_SCORE_TERM_PROJECTION_SET_SHA256_BY_LANE_CASE = {
    "baseline": {
        "5SD5_HWI": "d5cb2fa10df230fdddab17fc19ed10eeffb9631bb5e85c1647e0eddfade53899",
        "5SIS_JSM": "bac31d3db6a447dafd657494c757ad89d8c260ed9e0bd7e9d65636b11a4aff3a",
        "6M2B_EZO": "23c8c301d2b79ddabce561db658ab1a5141a52b40cbe701d2f79bd3a89ea7c9a",
        "6T88_MWQ": "1afd29b8da3b541ddfe84b37b52e417ac2792ae2beaf3c7068e5ef127d550d09",
        "6TW5_9M2": "35719baa933233124373b0538ec06c42fe25a2d76a87e78d35464426e830be4f",
        "6TW7_NZB": "be8f197c4879ae48571b6a3c72521538a6c8990fb2f96e5d3cf1d6371d273c5a",
        "6VTA_AKN": "98d113ac769e2353a004d93f6b95bb5b6f1c8029322308b788a18cfcb29b4925",
        "6WTN_RXT": "894b179adfa684c8fe5bf2fc6fb6aebc8003de694220ba24da04297626321079",
    },
    "rescue": {
        "5SD5_HWI": "58e058badb2789667fb3d7e7df3142cc1e9964ca0e32d11f80d5706b82e1e057",
        "5SIS_JSM": "b6169337744135b79df0a449a67d9e16489e41e58704b1b8218d652368eea3a8",
        "6M2B_EZO": "855968b252fca3ab0dd56c50cdfbe6e6f4e7ec8c1f377f824c75e8dcc6584aff",
        "6T88_MWQ": "257cdb6ba1070e79a85c7f62efa0667bf604f0029b2f3e524a4db92ea7e19df8",
        "6TW5_9M2": "258d43d0a603f756feeeef5cd170c27c238c743ef41f08e1cc86589010b29b56",
        "6TW7_NZB": "1b534a8df42ca9ef2d8d149e0304a28e7e9ebfdcbfc2625cd7a104c7225ed42e",
        "6VTA_AKN": "3883e87c533281fc49bc7cd6d0aa6dfccd05803a83d0aade14972ec3fbd7a567",
        "6WTN_RXT": "c3e4f710457fb274c4308d61c38f7b20ee5aa9ebf055f3e3ea32d35fc6fe4edd",
    },
}
EXPECTED_EXECUTION_CONTRACT_SHA256_BY_LANE_CASE = {
    "baseline": {
        "5SD5_HWI": "f6cbd306fd98e23333a6a00558258f433ed8cec96cfd4d1270324161fa6cf7a2",
        "5SIS_JSM": "689c977a03565e4648656f671fda1b28115d3f27193728f0a19e6003697a3a54",
        "6M2B_EZO": "176cf10b769b77df446ccd864f6ee3dfce748d1320fd2b35b699bd381491cace",
        "6M73_FNR": "61ecaab601c224aa747c8addfcec0822ee548d0a38ffa57aa6151dcfee468d89",
        "6T88_MWQ": "537f6460cabbc14e941174abb26a96ed6818568a769152a66cdc2152eb7c0259",
        "6TW5_9M2": "cfffac146b491f22ce67bbe30638aceabc1d5af2db2471292897ce2c72c26c06",
        "6TW7_NZB": "1742661a74ff876473374c6ebdbdac7d6276f9c20cb4a7ff17d4245a4493e62f",
        "6VTA_AKN": "1a9a4c8baf7289bb7170a482fe2ad6e1c6d9c2da1368221a2f737c0691e1ba97",
        "6WTN_RXT": "a703be53e26e9d6f9ac9f519f5850a7896634656f8b14fb1c41a35da7ef6be71",
    },
    "rescue": {
        "5SD5_HWI": "0685b9a77131058c7e7a36d3093158253c59056ede9335e60b63d5325c9f7853",
        "5SIS_JSM": "c08e4813887d028c4b0ccf05295629067ee9a2cd49fd334a65d9b24d65f0f9a9",
        "6M2B_EZO": "5bbe9323e234159688e83d1b3194cba04a0afdb95d598e6f2d1ee6392ffbbd6f",
        "6M73_FNR": "2890438c62d83850124300f038f4ae4c29fadd685e417cf447a929b30c06ca9f",
        "6T88_MWQ": "896016eaa81462cab1d5e18bb5855af7fde1bdf596d86f2be207fb99a6e95dc7",
        "6TW5_9M2": "18e6ec50df0fc8d2523423dee5efcf4d5a87e1ac31c307b0470c86e631bb78be",
        "6TW7_NZB": "51aa91fa096b53f42595659273733dd4e399313dd6d80c3d70b7c24049a26b4c",
        "6VTA_AKN": "de8018021fcd7abebae856e33187cb1fbfe87a532b99840b8ac90e615e52b9b9",
        "6WTN_RXT": "3717f3bb6551798c9a376e4885b09d1d614e67e25870ec13e3bcfebd619fe225",
    },
}
EXPECTED_SCORE_TERM_ANALYZER_SOURCE_SHA256 = (
    "10e586424ee0a456749ea7441ba0b5ef3ba8146491afd2b0c4ac741382045e78"
)

EXPECTED_RESULT_FIELDS = frozenset(
    {
        "case_id",
        "engine_id",
        "status",
        "runtime_seconds",
        "receptor_artifact_sha256",
        "reference_artifact_sha256",
        "native_artifact_sha256",
        "seed_artifact_sha256",
        "execution_command",
        "execution_policy",
        "rmsd_angstroms",
        "geometric_valid",
        "chemical_valid",
        "pose_artifact_sha256s",
        "failure_code",
        "engine_v2_diagnostics",
    }
)
EXPECTED_BASELINE_DIAGNOSTIC_FIELDS = frozenset(
    {
        "schema_id",
        "preparation_status",
        "preparation_failure_code",
        "candidate_budget",
        "candidate_success_count",
        "candidate_failure_count",
        "candidates",
        "proposal_oracle_rmsd_angstrom",
        "diagnostic_evaluation_seconds",
        "diagnostic_evaluation_excluded_from_runtime",
        "receptor_atom_count",
        "ligand_atom_count",
        "receptor_partial_charge_count",
        "ligand_partial_charge_count",
        "charge_coverage_complete",
        "hbond_feature_covered",
        "receptor_ion_proxy_count",
        "receptor_ion_proxy_used",
        "receptor_ion_coordination_modeled",
        "ligand_metal_support",
        "scorer_backend_receipt",
        "receptor_donor_count",
        "receptor_acceptor_count",
        "ligand_donor_count",
        "ligand_acceptor_count",
    }
)
EXPECTED_RESCUE_DIAGNOSTIC_FIELDS = frozenset(
    {
        *EXPECTED_BASELINE_DIAGNOSTIC_FIELDS,
        "source_paired_torsion_rescue_proposal_receipt",
    }
)
EXPECTED_SUMMARY_INPUT_BINDING = {
    "mode": "sealed_linux_memfd_snapshot/1.0.0",
    "immutable_execution_bytes": True,
    "source_identity_verified_before_and_after": True,
    "continuous_source_monitoring": False,
    "external_aliases_created": False,
}
EXPECTED_BASELINE_SUMMARY_FIELDS = frozenset(
    {
        "analysis_scope",
        "benchmark_validated",
        "case_count",
        "case_ids",
        "case_ids_sha256",
        "claim_safe",
        "contains_engineering_smoke",
        "contains_fresh_internal_blind_holdout",
        "development_v8_clearance_variant",
        "engine_identity",
        "engine_ids",
        "evidence_role",
        "execution_receipts",
        "external_engines_executed",
        "fresh_execution_authorized",
        "input_binding",
        "materializations",
        "paired_baseline_metrics_present",
        "primary_claim_eligible",
        "product_promotion_eligible",
        "product_qualified",
        "profiles",
        "public_claim_eligible",
        "rows",
        "runner_id",
        "schema_id",
        "scientifically_validated",
        "summary_sha256",
    }
)
EXPECTED_RESCUE_SUMMARY_FIELDS = frozenset(
    {
        *EXPECTED_BASELINE_SUMMARY_FIELDS,
        "development_source_paired_torsion_rescue",
        "source_paired_torsion_rescue_policy",
    }
)
EXPECTED_BASELINE_ENGINE_IDENTITY = {
    "engine_id": "engine_v2",
    "evaluation_pipeline_sha256": (
        "40530119249b792728a70cb5ba65cc9c60cf834e1a744d6987dae75046459922"
    ),
    "execution_environment_sha256": (
        "e6f96f53ec1d0ce83f665f170b27d0727e98455153720c741122584d0cfadb79"
    ),
    "implementation_sha256": (
        "26e0dcdc80c9b62381b7c4442933b87a69172abbbe4e50ad9dd86784691074aa"
    ),
    "interaction_refiner": "interaction_aware_torsion_contact_v7_ensemble",
    "interaction_refiner_config_sha256": (
        EXPECTED_INTERACTION_REFINER_CONFIG_SHA256
    ),
    "scorer_backend": EXPECTED_SCORER_BACKEND,
    "stage0_eligible": False,
}
EXPECTED_RESCUE_ENGINE_IDENTITY = {
    **EXPECTED_BASELINE_ENGINE_IDENTITY,
    "candidate_schema_id": EXPECTED_RESCUE_CANDIDATE_SCHEMA_ID,
    "diagnostic_schema_id": EXPECTED_RESCUE_DIAGNOSTIC_SCHEMA_ID,
    "interaction_refiner": (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_refiner/1.0.0"
    ),
    "proposal_profile_id": EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROFILE_ID,
    "proposal_profile_sha256": EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256,
}
EXPECTED_SUMMARY_RESCUE_POLICY = {
    "authority_rotor_required": True,
    "base_guided_policy_sha256": (
        EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
    ),
    "candidate_count": EXPECTED_CANDIDATE_COUNT,
    "candidate_denominator_changed": False,
    "claim_safe": False,
    "development_only": True,
    "fingerprint_sha256": EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256,
    "fresh_execution_authorized": False,
    "maximum_variant_count": EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP,
    "ordinary_v3_and_rescue_target_parent_unions_disjoint": True,
    "policy_id": EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROFILE_ID,
    "product_promotion_eligible": False,
    "proposal_objects_and_coordinates_unchanged": True,
    "public_claim_eligible": False,
    "rmsd_posebusters_native_rank_or_score_used_for_allocation": False,
    "schema_id": EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID,
    "scientifically_validated": False,
    "selected_parent_proposal_objects_retained": True,
    "source_pair_authority": "base_uniform_v3_ensemble_receipt",
    "stage0_eligible": False,
    "variant_target_selection": (
        "rounded_even_spacing_across_ordered_v3_target_indices"
    ),
}
EXPECTED_SUMMARY_FALSE_BOUNDARY_FIELDS = (
    "benchmark_validated",
    "claim_safe",
    "contains_engineering_smoke",
    "contains_fresh_internal_blind_holdout",
    "development_v8_clearance_variant",
    "external_engines_executed",
    "fresh_execution_authorized",
    "paired_baseline_metrics_present",
    "primary_claim_eligible",
    "product_promotion_eligible",
    "product_qualified",
    "public_claim_eligible",
    "scientifically_validated",
)
EXPECTED_PROFILE_FIELDS = frozenset(
    {
        "case_id",
        "heavy_atom_count",
        "rotor_count",
        "ring_count",
        "ligand_artifact_sha256",
        "profile_method_id",
        "ring_profile_method_id",
        "size_subgroup",
        "rotor_subgroup",
        "ring_subgroup",
    }
)
EXPECTED_PROFILE_SET_SHA256 = (
    "541059fe40cf54a2b7d75efda1c6f6fa0a790d1c7b38187a72e2bfb55fe7f33a"
)
EXPECTED_PREPARATION_FAILURE_ZERO_INT_DIAGNOSTIC_FIELDS = (
    "candidate_success_count",
    "candidate_failure_count",
    "receptor_atom_count",
    "ligand_atom_count",
    "receptor_partial_charge_count",
    "ligand_partial_charge_count",
    "receptor_ion_proxy_count",
    "receptor_donor_count",
    "receptor_acceptor_count",
    "ligand_donor_count",
    "ligand_acceptor_count",
)
EXPECTED_PREPARATION_FAILURE_FALSE_DIAGNOSTIC_FIELDS = (
    "charge_coverage_complete",
    "hbond_feature_covered",
    "receptor_ion_proxy_used",
    "receptor_ion_coordination_modeled",
    "ligand_metal_support",
)
EXPECTED_PREPARATION_FAILURE_NULL_DIAGNOSTIC_FIELDS = (
    "proposal_oracle_rmsd_angstrom",
    "scorer_backend_receipt",
)
EXPECTED_PREPARATION_COUNT_DIAGNOSTIC_FIELDS = (
    "receptor_atom_count",
    "ligand_atom_count",
    "receptor_partial_charge_count",
    "ligand_partial_charge_count",
    "receptor_donor_count",
    "receptor_acceptor_count",
    "ligand_donor_count",
    "ligand_acceptor_count",
    "receptor_ion_proxy_count",
)
EXPECTED_BASELINE_CANDIDATE_FIELDS = frozenset(
    {
        "schema_id",
        "proposal_index",
        "proposal_mode",
        "status",
        "error_code",
        "score",
        "rmsd_angstrom",
        "geometric_valid",
        "chemical_valid",
        "selection_eligible",
        "posebusters_failed_check_ids",
        "proposal_fingerprint_sha256",
        "coordinate_fingerprint_sha256",
        "pose_artifact_sha256",
        "score_terms_receipt_sha256",
        "score_term_binary64_hex",
        "hbond_count",
        "ensemble_source_proposal_index",
        "refinement_original_pose_valid",
        "refinement_accepted_steps",
        "refinement_accepted_rotation_steps",
        "refinement_initial_penalty_binary64_hex",
        "refinement_final_penalty_binary64_hex",
        "refinement_total_translation_binary64_hex",
        "refinement_total_rotation_vector_binary64_hex",
        "refinement_receipt_sha256",
        "refinement_receipt_payload",
    }
)
EXPECTED_RESCUE_CANDIDATE_FIELDS = frozenset(
    {
        *EXPECTED_BASELINE_CANDIDATE_FIELDS,
        "torsion_rescue_parent_proposal_index",
    }
)
EXPECTED_V11_RECEIPT_KEYSET_SHA256 = (
    "bb7be9e06493448ff1f2b603b7365090fa01a068115d143c005bac38863ae68e"
)
EXPECTED_V11_RECEIPT_FIELDS = frozenset(
    {
        "schema_id",
        "source_proposal_sha256",
        "config_sha256",
        "lane",
        "selection_reason",
        "baseline_v6_receipt_sha256",
        "baseline_v6_receipt_payload",
        "baseline_v6_max_steps",
        "v3_proposal_indices",
        "rotatable_child_atom_indices",
        "torsion_step_budget",
        "selection_window_reachable_from_baseline_v6_receptor_penalty",
        "torsion_evaluation_skip_reason",
        "evaluation_stopped_after_selection_window_became_unreachable",
        "torsion_evaluated",
        "torsion_variant_available",
        "torsion_selected",
        "evaluated_torsion_steps",
        "evaluated_torsion_moves",
        "evaluated_total_torsion_path_radians_binary64_hex",
        "accepted_torsion_steps",
        "accepted_torsion_moves",
        "objective_evaluation_count",
        "fixed_objective_evaluation_count",
        "torsion_trial_objective_evaluation_count",
        "initial_receptor_penalty_binary64_hex",
        "baseline_v6_receptor_penalty_binary64_hex",
        "optimized_receptor_penalty_binary64_hex",
        "final_receptor_penalty_binary64_hex",
        "initial_internal_penalty_binary64_hex",
        "baseline_v6_internal_penalty_binary64_hex",
        "optimized_internal_penalty_binary64_hex",
        "final_internal_penalty_binary64_hex",
        "initial_combined_penalty_binary64_hex",
        "baseline_v6_combined_penalty_binary64_hex",
        "optimized_combined_penalty_binary64_hex",
        "final_combined_penalty_binary64_hex",
        "initial_penalty_binary64_hex",
        "final_penalty_binary64_hex",
        "generic_penalty_scope",
        "baseline_v6_penalty_scope",
        "minimum_selected_final_receptor_penalty_binary64_hex",
        "maximum_selected_final_receptor_penalty_binary64_hex",
        "total_torsion_path_radians_binary64_hex",
        "accepted_steps",
        "accepted_translation_steps",
        "accepted_rigid_rotation_steps",
        "accepted_rotation_steps",
        "accepted_rotation_steps_include_torsion",
        "line_search_evaluation_count",
        "fallback_direction_step_count",
        "original_pose_valid",
        "total_translation_binary64_hex",
        "total_rotation_vector_binary64_hex",
        "pre_coordinates_sha256",
        "baseline_coordinates_sha256",
        "post_coordinates_sha256",
        "ranking_score_reused_as_physical_energy",
        "posebusters_or_rmsd_used_for_selection",
        "source_lane_retained",
        "scientifically_validated",
        "legacy_v7_receipt_schema_id",
        "source_paired_torsion_rescue_profile",
        "source_paired_torsion_rescue_pairs",
        "source_paired_torsion_rescue_allocation_sha256",
        "source_paired_torsion_rescue_policy_sha256",
        "source_paired_torsion_rescue_guidance_context_sha256",
        "source_paired_torsion_rescue_budget_sha256",
        "source_paired_torsion_rescue_variant_cap",
        "proposal_torsion_eligibility_lane",
        "source_paired_parent_proposal_index",
        "nested_v6_treated_proposal_as_v3_variant",
        "rescue_target_excluded_from_nested_v3_indices",
        "result_dependent_eligibility",
        "development_only",
        "stage0_eligible",
        "fresh_execution_authorized",
        "claim_safe",
        "clearance_measurement_evaluated",
        "clearance_measurement_unavailable_reason",
        "clearance_radii_policy_sha256",
        "clearance_ligand_atom_count",
        "clearance_receptor_atom_count",
        "clearance_full_cartesian_pair_count",
        "clearance_pair_count_bound",
        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex",
        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex",
        "optimized_coordinates_sha256",
        "receipt_sha256",
    }
)
EXPECTED_BASELINE_V7_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
)
EXPECTED_BASELINE_V7_RECEIPT_KEYSET_SHA256 = (
    "557bb91b72ce3047c7a366e4731a05c9787ae451c4b6b030747babf766191603"
)

BASELINE_RUN_ROOT = (
    ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-baseline-nine"
)
RESCUE_RUN_ROOT = ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-nine"
BASELINE_SUMMARY_PATH = (
    f"{BASELINE_RUN_ROOT}/engine-v2-only-summary-development-009-cd2c24c9c7d93786.json"
)
RESCUE_SUMMARY_PATH = (
    f"{RESCUE_RUN_ROOT}/"
    "engine-v2-only-summary-development-source-paired-torsion-rescue-"
    "009-cd2c24c9c7d93786.json"
)
BASELINE_ANALYSIS_PATH = (
    ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-baseline-analysis.json"
)
RESCUE_ANALYSIS_PATH = (
    ".betelgeuze/stage0-development/v7-clearance-v11-6a749540-rescue-analysis.json"
)
BASELINE_WALLTIME_PATH = f"{BASELINE_RUN_ROOT}.walltime.txt"
RESCUE_WALLTIME_PATH = f"{RESCUE_RUN_ROOT}.walltime.txt"
REPORT_PATH = (
    ".betelgeuze/stage0-development/source-paired-clearance-v11-6a749540-audit.json"
)
ARCHIVE_PATH = (
    ".betelgeuze/stage0-development/archives/"
    "v7-source-paired-clearance-v11-6a749540-ab.tar.zst"
)
MEMBERS_PATH = (
    ".betelgeuze/stage0-development/archives/"
    "v7-source-paired-clearance-v11-6a749540-ab.members.sha256"
)
BUNDLE_PATH = (
    ".betelgeuze/stage0-development/archives/"
    "v7-source-paired-clearance-v11-6a749540-ab.bundle.sha256"
)

EXPECTED_EVIDENCE_ARCHIVE_SHA256 = (
    "7a2561f646f3cf5434de6c79ed797073ac1b7e034e4fcd2291755a58128f5e98"
)
EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256 = (
    "7ae57e3bec8ecf96b754e2038dd2eef023058c4ea1adae2fbf4933bf556cf6bd"
)
EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256 = (
    "37d9478c78076eef908e3a86c712f49820078ab14289fb1ee26a1f8c4fc37ea5"
)
EXPECTED_REPORT_SHA256 = (
    "8d9e9eef5907e51fbf2f25385c7cb1468dbd099c5636715ddea78274ef22fae3"
)
EXPECTED_EVIDENCE_MEMBER_COUNT = 59

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_TAR_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_MEMBER_MANIFEST_BYTES = 256 * 1024
MAX_BUNDLE_CHECKSUM_BYTES = 4 * 1024
EXPECTED_CLEARANCE_PAIR_COUNT_BOUND = 1_000_000
EXPECTED_CLEARANCE_RADII_POLICY_SHA256 = (
    "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
)

EXPECTED_BASELINE_METRICS = {
    "case_count": 9,
    "scored_case_count": 8,
    "candidate_success_count": 512,
    "exact_valid_candidate_count": 7,
    "native_like_candidate_count": 4,
    "selection_eligible_candidate_count": 31,
    "native_like_selection_eligible_candidate_count": 3,
    "proposal_oracle_recovery_case_count": 1,
    "top1_recovery_case_count": 1,
    "top5_recovery_case_count": 1,
    "valid_top1_case_count": 3,
}
EXPECTED_RESCUE_METRICS = {
    **EXPECTED_BASELINE_METRICS,
    "selection_eligible_candidate_count": 30,
    "native_like_selection_eligible_candidate_count": 2,
}
EXPECTED_TORSION_COUNTS = {
    "allocated_candidate_count": 28,
    "torsion_evaluated_candidate_count": 27,
    "torsion_variant_available_candidate_count": 26,
    "torsion_selected_candidate_count": 0,
    "clearance_evaluated_candidate_count": 28,
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_payload(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _is_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _safe_member_name(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("archive member name is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("archive member name is invalid")
    if any(part.startswith(".env") for part in path.parts):
        raise ValueError("archive member name is prohibited")
    return path.as_posix()


def _distribution(values: Sequence[float]) -> dict[str, object]:
    return failure_atlas._distribution(values)


def _binary64(value: object, *, name: str) -> float:
    encoded = failure_atlas._binary64_hex(value, name=name)
    number = float.fromhex(encoded)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _finite_number(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError(f"{name} is outside the frozen numeric contract")
    return number


def _execution_policy_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, list):
        raise ValueError("execution policy tokens are invalid")
    mapping: dict[str, object] = {}
    for token in value:
        if not isinstance(token, str):
            raise ValueError("execution policy token is invalid")
        key, separator, encoded = token.partition("=")
        if not key or separator != "=" or key in mapping:
            raise ValueError("execution policy token is invalid")
        try:
            decoded = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise ValueError("execution policy value is invalid") from exc
        if encoded != json.dumps(
            decoded,
            allow_nan=False,
            separators=(",", ":"),
        ):
            raise ValueError("execution policy value is not canonical")
        mapping[key] = decoded
    return mapping


def _historical_v11_candidate(
    value: object,
    *,
    lane: str,
    case_id: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{lane} {case_id} candidate must be an object")
    candidate = dict(value)
    expected_fields = (
        EXPECTED_BASELINE_CANDIDATE_FIELDS
        if lane == "baseline"
        else EXPECTED_RESCUE_CANDIDATE_FIELDS
    )
    expected_schema = (
        EXPECTED_BASELINE_CANDIDATE_SCHEMA_ID
        if lane == "baseline"
        else EXPECTED_RESCUE_CANDIDATE_SCHEMA_ID
    )
    proposal_index = candidate.get("proposal_index")
    proposal_mode = candidate.get("proposal_mode")
    ensemble_source = candidate.get("ensemble_source_proposal_index")
    rescue_parent = candidate.get("torsion_rescue_parent_proposal_index")
    failed_checks = candidate.get("posebusters_failed_check_ids")
    allowed_proposal_modes = set(EXPECTED_BASE_PROPOSAL_MODES)
    if lane == "rescue":
        allowed_proposal_modes.add(PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE)
    if (
        set(candidate) != expected_fields
        or candidate.get("schema_id") != expected_schema
        or candidate.get("status") != "success"
        or candidate.get("error_code") != ""
        or type(proposal_index) is not int
        or not 0 <= proposal_index < EXPECTED_CANDIDATE_COUNT
        or proposal_mode not in allowed_proposal_modes
        or any(
            type(candidate.get(field)) is not bool
            for field in (
                "geometric_valid",
                "chemical_valid",
                "selection_eligible",
                "refinement_original_pose_valid",
            )
        )
        or type(candidate.get("hbond_count")) is not int
        or int(candidate["hbond_count"]) < 0
        or not isinstance(failed_checks, list)
        or any(
            not isinstance(check_id, str) or not check_id for check_id in failed_checks
        )
    ):
        raise ValueError(f"{lane} {case_id} candidate shape is invalid")
    if proposal_mode == "uniform_v3_rigid_ensemble":
        if (
            type(ensemble_source) is not int
            or not 0 <= ensemble_source < EXPECTED_CANDIDATE_COUNT
            or ensemble_source == proposal_index
            or rescue_parent is not None
        ):
            raise ValueError(f"{lane} {case_id} ensemble lineage is invalid")
    elif ensemble_source is not None:
        raise ValueError(f"{lane} {case_id} non-ensemble lineage is invalid")
    if proposal_mode == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE:
        if (
            lane != "rescue"
            or type(rescue_parent) is not int
            or not 0 <= rescue_parent < EXPECTED_CANDIDATE_COUNT
            or rescue_parent == proposal_index
            or ensemble_source is not None
        ):
            raise ValueError(f"{lane} {case_id} rescue lineage is invalid")
    elif rescue_parent is not None:
        raise ValueError(f"{lane} {case_id} non-rescue parent is invalid")
    allowed_checks = (
        *EXPECTED_POSEBUSTERS_CHEMICAL_CHECK_IDS,
        *EXPECTED_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
    )
    failed_check_tuple = tuple(failed_checks)
    if (
        failed_check_tuple
        != tuple(check for check in allowed_checks if check in set(failed_check_tuple))
        or len(failed_check_tuple) != len(set(failed_check_tuple))
        or candidate.get("geometric_valid")
        is not (
            not bool(
                set(failed_check_tuple) & set(EXPECTED_POSEBUSTERS_GEOMETRIC_CHECK_IDS)
            )
        )
        or candidate.get("chemical_valid")
        is not (
            not bool(
                set(failed_check_tuple) & set(EXPECTED_POSEBUSTERS_CHEMICAL_CHECK_IDS)
            )
        )
    ):
        raise ValueError(f"{lane} {case_id} PoseBusters projection is invalid")
    candidate_score = _finite_number(candidate.get("score"), name="candidate score")
    _finite_number(
        candidate.get("rmsd_angstrom"),
        name="candidate RMSD",
        minimum=0.0,
    )
    for field in (
        "proposal_fingerprint_sha256",
        "coordinate_fingerprint_sha256",
        "pose_artifact_sha256",
        "score_terms_receipt_sha256",
        "refinement_receipt_sha256",
    ):
        if not _is_sha256(candidate.get(field)):
            raise ValueError(f"{lane} {case_id} candidate {field} is invalid")
    score_terms = candidate.get("score_term_binary64_hex")
    if not isinstance(score_terms, Mapping) or set(score_terms) != set(
        EXPECTED_SCORER_TERM_NAMES
    ):
        raise ValueError(f"{lane} {case_id} candidate score terms are invalid")
    decoded_terms: dict[str, float] = {}
    for term, encoded in score_terms.items():
        if not isinstance(term, str) or not term:
            raise ValueError("candidate score term name is invalid")
        decoded_terms[term] = _binary64(
            encoded,
            name=f"candidate score term {term}",
        )
    if candidate_score.hex() != decoded_terms["total_score"].hex():
        raise ValueError(f"{lane} {case_id} candidate score contradicts retained total")
    if not math.isclose(
        decoded_terms["total_score"],
        sum(decoded_terms[name] for name in EXPECTED_SCORER_TERM_NAMES[:-1]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError(f"{lane} {case_id} candidate score terms are inconsistent")
    initial_penalty = _binary64(
        candidate.get("refinement_initial_penalty_binary64_hex"),
        name="candidate refinement initial penalty",
    )
    final_penalty = _binary64(
        candidate.get("refinement_final_penalty_binary64_hex"),
        name="candidate refinement final penalty",
    )
    accepted_steps = candidate.get("refinement_accepted_steps")
    accepted_rotation_steps = candidate.get("refinement_accepted_rotation_steps")
    if (
        initial_penalty < 0.0
        or final_penalty < 0.0
        or type(accepted_steps) is not int
        or accepted_steps < 0
        or type(accepted_rotation_steps) is not int
        or not 0 <= accepted_rotation_steps <= accepted_steps
    ):
        raise ValueError(f"{lane} {case_id} refinement diagnostics are invalid")
    failure_atlas._vector_summary(
        candidate.get("refinement_total_translation_binary64_hex"),
        name="candidate refinement translation",
    )
    failure_atlas._vector_summary(
        candidate.get("refinement_total_rotation_vector_binary64_hex"),
        name="candidate refinement rotation",
    )
    payload = candidate.get("refinement_receipt_payload")
    if not isinstance(payload, Mapping):
        raise ValueError(f"{lane} {case_id} refinement payload is invalid")
    if (
        proposal_mode
        in {
            "uniform_v3_rigid_ensemble",
            PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE,
        }
        and not payload
    ):
        raise ValueError(f"{lane} {case_id} source-paired payload is missing")
    if lane == "baseline":
        if payload:
            if (
                _sha256_payload(sorted(payload))
                != EXPECTED_BASELINE_V7_RECEIPT_KEYSET_SHA256
                or payload.get("schema_id") != EXPECTED_BASELINE_V7_RECEIPT_SCHEMA_ID
                or payload.get("receipt_sha256")
                != candidate.get("refinement_receipt_sha256")
            ):
                raise ValueError(
                    f"{lane} {case_id} baseline V7 receipt contract is invalid"
                )
            receipt_projection = dict(payload)
            receipt_sha256 = receipt_projection.pop("receipt_sha256", None)
            if not _is_sha256(receipt_sha256) or receipt_sha256 != _sha256_payload(
                receipt_projection
            ):
                raise ValueError(
                    f"{lane} {case_id} baseline V7 receipt self-hash is invalid"
                )
    else:
        if (
            set(payload) != EXPECTED_V11_RECEIPT_FIELDS
            or _sha256_payload(sorted(payload)) != EXPECTED_V11_RECEIPT_KEYSET_SHA256
            or payload.get("schema_id") != EXPECTED_RECEIPT_SCHEMA_ID
            or payload.get("receipt_sha256")
            != candidate.get("refinement_receipt_sha256")
            or any(
                payload.get(field) is not False
                for field in (
                    "claim_safe",
                    "fresh_execution_authorized",
                    "scientifically_validated",
                    "stage0_eligible",
                )
            )
            or payload.get("development_only") is not True
            or payload.get("source_paired_torsion_rescue_profile") is not True
            or payload.get("source_paired_torsion_rescue_policy_sha256")
            != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
            or payload.get("source_paired_torsion_rescue_variant_cap")
            != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
            or payload.get("result_dependent_eligibility") is not False
            or payload.get("legacy_v7_receipt_schema_id")
            != "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
            or payload.get("source_lane_retained") is not True
            or payload.get("ranking_score_reused_as_physical_energy") is not False
            or payload.get("posebusters_or_rmsd_used_for_selection") is not False
            or payload.get("accepted_rotation_steps_include_torsion") is not True
            or payload.get("generic_penalty_scope")
            != "source_proposal_to_final_coordinates_v7_objective"
            or payload.get("baseline_v6_penalty_scope")
            != "post_v6_coordinates_v7_objective"
            or payload.get("config_sha256")
            != EXPECTED_SOURCE_PAIRED_REFINER_COMPOSITE_CONFIG_SHA256_BY_CASE.get(
                case_id
            )
            or payload.get("post_coordinates_sha256")
            != candidate.get("coordinate_fingerprint_sha256")
            or type(payload.get("torsion_selected")) is not bool
            or (
                payload.get("torsion_selected") is False
                and (
                    not _is_sha256(payload.get("baseline_coordinates_sha256"))
                    or payload.get("post_coordinates_sha256")
                    != payload.get("baseline_coordinates_sha256")
                )
            )
            or payload.get("initial_penalty_binary64_hex")
            != candidate.get("refinement_initial_penalty_binary64_hex")
            or payload.get("final_penalty_binary64_hex")
            != candidate.get("refinement_final_penalty_binary64_hex")
            or payload.get("accepted_steps")
            != candidate.get("refinement_accepted_steps")
            or payload.get("accepted_rotation_steps")
            != candidate.get("refinement_accepted_rotation_steps")
            or payload.get("original_pose_valid")
            is not candidate.get("refinement_original_pose_valid")
            or payload.get("total_translation_binary64_hex")
            != candidate.get("refinement_total_translation_binary64_hex")
            or payload.get("total_rotation_vector_binary64_hex")
            != candidate.get("refinement_total_rotation_vector_binary64_hex")
        ):
            raise ValueError(f"{lane} {case_id} V1.1 receipt contract is invalid")
        receipt_projection = dict(payload)
        receipt_sha256 = receipt_projection.pop("receipt_sha256", None)
        if not _is_sha256(receipt_sha256) or receipt_sha256 != _sha256_payload(
            receipt_projection
        ):
            raise ValueError(f"{lane} {case_id} V1.1 receipt self-hash is invalid")
        baseline_v6_payload = payload.get("baseline_v6_receipt_payload")
        if not isinstance(baseline_v6_payload, Mapping):
            raise ValueError(f"{lane} {case_id} baseline V6 receipt payload is invalid")
        baseline_v6_projection = dict(baseline_v6_payload)
        baseline_v6_sha256 = baseline_v6_projection.pop("receipt_sha256", None)
        baseline_v6_core_fields = {
            "accepted_rotation_steps",
            "accepted_steps",
            "accepted_translation_steps",
            "config_sha256",
            "fallback_direction_step_count",
            "final_penalty_binary64_hex",
            "initial_penalty_binary64_hex",
            "lane",
            "line_search_evaluation_count",
            "nested_receipt_sha256",
            "nested_refiner_id",
            "nested_refiner_version",
            "original_pose_valid",
            "post_coordinates_sha256",
            "pre_coordinates_sha256",
            "ranking_score_reused_as_physical_energy",
            "receipt_sha256",
            "schema_id",
            "scientifically_validated",
            "source_lane_retained",
            "source_proposal_sha256",
            "total_rotation_vector_binary64_hex",
            "total_translation_binary64_hex",
            "v3_proposal_indices",
        }
        baseline_v6_extended_fields = baseline_v6_core_fields | {
            "baseline_duplicate_of_v2_refinement",
            "baseline_final_penalty_binary64_hex",
            "baseline_v3_receipt_sha256",
            "clearance_evaluated",
            "clearance_final_penalty_binary64_hex",
            "clearance_initial_penalty_binary64_hex",
            "clearance_receipt_sha256",
            "clearance_selected",
            "comparison_v2_receipt_sha256",
            "near_clear_penalty_binary64_hex",
            "selection_reason",
        }
        baseline_v6_fields = set(baseline_v6_payload)
        nested_accepted_steps = baseline_v6_payload.get("accepted_steps")
        nested_rotation_steps = baseline_v6_payload.get("accepted_rotation_steps")
        nested_line_search_count = baseline_v6_payload.get(
            "line_search_evaluation_count"
        )
        accepted_torsion_steps = payload.get("accepted_torsion_steps")
        torsion_trial_count = payload.get("torsion_trial_objective_evaluation_count")
        if (
            baseline_v6_fields
            not in (baseline_v6_core_fields, baseline_v6_extended_fields)
            or baseline_v6_payload.get("schema_id")
            != EXPECTED_BASELINE_V6_RECEIPT_SCHEMA_ID
            or not _is_sha256(baseline_v6_sha256)
            or baseline_v6_sha256 != _sha256_payload(baseline_v6_projection)
            or payload.get("baseline_v6_receipt_sha256") != baseline_v6_sha256
            or baseline_v6_payload.get("config_sha256")
            != EXPECTED_BASELINE_V6_COMPOSITE_CONFIG_SHA256_BY_CASE.get(case_id)
            or not _is_sha256(baseline_v6_payload.get("nested_receipt_sha256"))
            or baseline_v6_payload.get("source_proposal_sha256")
            != payload.get("source_proposal_sha256")
            or baseline_v6_payload.get("pre_coordinates_sha256")
            != payload.get("pre_coordinates_sha256")
            or baseline_v6_payload.get("post_coordinates_sha256")
            != payload.get("baseline_coordinates_sha256")
            or baseline_v6_payload.get("v3_proposal_indices")
            != payload.get("v3_proposal_indices")
            or baseline_v6_payload.get("original_pose_valid")
            is not payload.get("original_pose_valid")
            or baseline_v6_payload.get("accepted_translation_steps")
            != payload.get("accepted_translation_steps")
            or baseline_v6_payload.get("accepted_rotation_steps")
            != payload.get("accepted_rigid_rotation_steps")
            or baseline_v6_payload.get("total_translation_binary64_hex")
            != payload.get("total_translation_binary64_hex")
            or baseline_v6_payload.get("total_rotation_vector_binary64_hex")
            != payload.get("total_rotation_vector_binary64_hex")
            or baseline_v6_payload.get("fallback_direction_step_count")
            != payload.get("fallback_direction_step_count")
            or any(
                type(value) is not int or value < 0
                for value in (
                    nested_accepted_steps,
                    nested_rotation_steps,
                    nested_line_search_count,
                    accepted_torsion_steps,
                    torsion_trial_count,
                )
            )
            or payload.get("accepted_steps")
            != nested_accepted_steps + accepted_torsion_steps
            or payload.get("accepted_rotation_steps")
            != nested_rotation_steps + accepted_torsion_steps
            or payload.get("line_search_evaluation_count")
            != nested_line_search_count + torsion_trial_count
            or baseline_v6_payload.get("source_lane_retained") is not True
            or baseline_v6_payload.get("scientifically_validated") is not False
            or baseline_v6_payload.get("ranking_score_reused_as_physical_energy")
            is not False
        ):
            raise ValueError(
                f"{lane} {case_id} baseline V6 receipt contract is invalid"
            )
    return candidate


def _historical_v11_result(
    value: object,
    *,
    lane: str,
    case_id: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != EXPECTED_RESULT_FIELDS:
        raise ValueError(f"{lane} {case_id} result shape is invalid")
    result = dict(value)
    if (
        result.get("case_id") != case_id
        or result.get("engine_id") != "engine_v2"
        or result.get("status") not in {"success", "failure"}
        or not isinstance(result.get("failure_code"), str)
    ):
        raise ValueError(f"{lane} {case_id} result identity is invalid")
    _finite_number(
        result.get("runtime_seconds"),
        name=f"{lane} runtime",
        minimum=0.0,
    )
    for field in (
        "receptor_artifact_sha256",
        "reference_artifact_sha256",
        "native_artifact_sha256",
        "seed_artifact_sha256",
    ):
        if not _is_sha256(result.get(field)):
            raise ValueError(f"{lane} {case_id} input artifact identity is invalid")
    command = result.get("execution_command")
    policy = result.get("execution_policy")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(token, str) or not token for token in command)
        or not isinstance(policy, list)
        or not policy
        or policy != sorted(policy)
        or any(not isinstance(token, str) or "=" not in token for token in policy)
    ):
        raise ValueError(f"{lane} {case_id} execution contract is invalid")
    if (
        _execution_policy_mapping(policy).get("scorer_backend")
        != EXPECTED_SCORER_BACKEND
    ):
        raise ValueError(f"{lane} {case_id} execution scorer backend is invalid")
    execution_contract_sha256 = _sha256_payload(
        {
            "execution_command": command,
            "execution_policy": policy,
        }
    )
    if execution_contract_sha256 != EXPECTED_EXECUTION_CONTRACT_SHA256_BY_LANE_CASE.get(
        lane,
        {},
    ).get(case_id):
        raise ValueError(f"{lane} {case_id} execution contract is not pinned")
    diagnostics = result.get("engine_v2_diagnostics")
    expected_diagnostic_fields = (
        EXPECTED_BASELINE_DIAGNOSTIC_FIELDS
        if lane == "baseline"
        else EXPECTED_RESCUE_DIAGNOSTIC_FIELDS
    )
    expected_diagnostic_schema = (
        EXPECTED_BASELINE_DIAGNOSTIC_SCHEMA_ID
        if lane == "baseline"
        else EXPECTED_RESCUE_DIAGNOSTIC_SCHEMA_ID
    )
    if (
        not isinstance(diagnostics, Mapping)
        or set(diagnostics) != expected_diagnostic_fields
        or diagnostics.get("schema_id") != expected_diagnostic_schema
        or type(diagnostics.get("candidate_budget")) is not int
        or diagnostics.get("candidate_budget") != EXPECTED_CANDIDATE_COUNT
    ):
        raise ValueError(f"{lane} {case_id} diagnostic shape is invalid")
    raw_candidates = diagnostics.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError(f"{lane} {case_id} candidate collection is invalid")
    if diagnostics.get("preparation_status") == "failure":
        if (
            case_id != EXPECTED_PREPARATION_FAILURE_CASE_ID
            or result.get("status") != "failure"
            or result.get("failure_code") != "engine_v2_case_failed"
            or diagnostics.get("preparation_failure_code")
            != EXPECTED_PREPARATION_FAILURE_CODE
            or raw_candidates
            or any(
                type(diagnostics.get(field)) is not int
                or diagnostics.get(field) != 0
                for field in EXPECTED_PREPARATION_FAILURE_ZERO_INT_DIAGNOSTIC_FIELDS
            )
            or type(diagnostics.get("diagnostic_evaluation_seconds")) is not float
            or diagnostics.get("diagnostic_evaluation_seconds").hex()
            != (0.0).hex()
            or diagnostics.get("diagnostic_evaluation_excluded_from_runtime")
            is not True
            or any(
                diagnostics.get(field) is not False
                for field in EXPECTED_PREPARATION_FAILURE_FALSE_DIAGNOSTIC_FIELDS
            )
            or any(
                diagnostics.get(field) is not None
                for field in EXPECTED_PREPARATION_FAILURE_NULL_DIAGNOSTIC_FIELDS
            )
            or (
                lane == "rescue"
                and diagnostics.get(
                    "source_paired_torsion_rescue_proposal_receipt"
                )
                is not None
            )
        ):
            raise ValueError(f"{lane} preparation failure is invalid")
        failure_atlas._validate_ranked_result_projection(
            result,
            (),
            lane=lane,
            case_id=case_id,
        )
        return result
    if (
        diagnostics.get("preparation_status") != "success"
        or result.get("status") != "success"
        or result.get("failure_code") != ""
        or type(diagnostics.get("candidate_success_count")) is not int
        or diagnostics.get("candidate_success_count") != EXPECTED_CANDIDATE_COUNT
        or type(diagnostics.get("candidate_failure_count")) is not int
        or diagnostics.get("candidate_failure_count") != 0
        or len(raw_candidates) != EXPECTED_CANDIDATE_COUNT
        or diagnostics.get("scorer_backend_receipt") != EXPECTED_SCORER_BACKEND_RECEIPT
        or any(
            type(diagnostics.get(field)) is not int
            or diagnostics.get(field) < 0
            for field in EXPECTED_PREPARATION_COUNT_DIAGNOSTIC_FIELDS
        )
        or diagnostics.get("receptor_atom_count") < 1
        or diagnostics.get("ligand_atom_count") < 1
        or diagnostics.get("receptor_partial_charge_count")
        != diagnostics.get("receptor_atom_count")
        or diagnostics.get("ligand_partial_charge_count")
        != diagnostics.get("ligand_atom_count")
        or diagnostics.get("receptor_ion_proxy_count")
        > diagnostics.get("receptor_atom_count")
        or type(diagnostics.get("diagnostic_evaluation_seconds")) is not float
        or not math.isfinite(diagnostics.get("diagnostic_evaluation_seconds"))
        or diagnostics.get("diagnostic_evaluation_seconds") < 0.0
        or diagnostics.get("diagnostic_evaluation_excluded_from_runtime") is not True
        or diagnostics.get("charge_coverage_complete") is not True
        or diagnostics.get("hbond_feature_covered")
        is not (
            (
                diagnostics.get("ligand_donor_count") > 0
                and diagnostics.get("receptor_acceptor_count") > 0
            )
            or (
                diagnostics.get("ligand_acceptor_count") > 0
                and diagnostics.get("receptor_donor_count") > 0
            )
        )
        or diagnostics.get("receptor_ion_proxy_used")
        is not (diagnostics.get("receptor_ion_proxy_count") > 0)
        or diagnostics.get("receptor_ion_coordination_modeled") is not False
        or diagnostics.get("ligand_metal_support") is not False
        or (
            lane == "rescue"
            and not isinstance(
                diagnostics.get("source_paired_torsion_rescue_proposal_receipt"),
                Mapping,
            )
        )
    ):
        raise ValueError(f"{lane} {case_id} successful denominator is invalid")
    candidates = tuple(
        _historical_v11_candidate(candidate, lane=lane, case_id=case_id)
        for candidate in raw_candidates
    )
    if {int(candidate["proposal_index"]) for candidate in candidates} != set(
        range(EXPECTED_CANDIDATE_COUNT)
    ):
        raise ValueError(f"{lane} {case_id} candidate indices are invalid")
    proposal_fingerprints = [
        str(candidate["proposal_fingerprint_sha256"]) for candidate in candidates
    ]
    if len(proposal_fingerprints) != len(set(proposal_fingerprints)):
        raise ValueError(f"{lane} {case_id} proposal fingerprints are duplicated")
    proposal_oracle_rmsd = diagnostics.get("proposal_oracle_rmsd_angstrom")
    expected_proposal_oracle_rmsd = min(
        float(candidate["rmsd_angstrom"]) for candidate in candidates
    )
    if (
        type(proposal_oracle_rmsd) is not float
        or not math.isfinite(proposal_oracle_rmsd)
        or proposal_oracle_rmsd.hex() != expected_proposal_oracle_rmsd.hex()
    ):
        raise ValueError(f"{lane} {case_id} proposal oracle RMSD is invalid")
    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: int(candidate["proposal_index"]),
    )
    if lane == "rescue":
        ordered_proposal_fingerprints = [
            str(candidate["proposal_fingerprint_sha256"])
            for candidate in ordered_candidates
        ]
        if _sha256_payload(ordered_proposal_fingerprints) != (
            EXPECTED_RESCUE_CANDIDATE_PROPOSAL_FINGERPRINT_SET_SHA256_BY_CASE.get(
                case_id
            )
        ):
            raise ValueError(
                f"{lane} {case_id} candidate proposal fingerprint set is not "
                "the pinned cohort"
            )
        ordered_receipt_sha256s = [
            str(candidate["refinement_receipt_sha256"])
            for candidate in ordered_candidates
        ]
        if _sha256_payload(ordered_receipt_sha256s) != (
            EXPECTED_RESCUE_CANDIDATE_RECEIPT_SET_SHA256_BY_CASE.get(case_id)
        ):
            raise ValueError(
                f"{lane} {case_id} candidate receipt set is not the pinned cohort"
            )
    # The historical summaries retain the score-term receipt ID and only the
    # candidate-facing term projection, not the opaque complete ScorerV1Terms
    # receipt. Pin their complete retained co-projection without claiming that
    # the omitted receipt internals were reconstructed after the fact.
    retained_score_term_projections = [
        {
            "proposal_index": int(candidate["proposal_index"]),
            "proposal_fingerprint_sha256": str(
                candidate["proposal_fingerprint_sha256"]
            ),
            "score_terms_receipt_sha256": str(
                candidate["score_terms_receipt_sha256"]
            ),
            "score_term_binary64_hex": dict(candidate["score_term_binary64_hex"]),
            "hbond_count": int(candidate["hbond_count"]),
        }
        for candidate in ordered_candidates
    ]
    if _sha256_payload(retained_score_term_projections) != (
        EXPECTED_CANDIDATE_SCORE_TERM_PROJECTION_SET_SHA256_BY_LANE_CASE.get(
            lane,
            {},
        ).get(case_id)
    ):
        raise ValueError(
            f"{lane} {case_id} retained score-term projection is not the "
            "pinned cohort"
        )
    failure_atlas._validate_ranked_result_projection(
        result,
        candidates,
        lane=lane,
        case_id=case_id,
    )
    return result


def _split_historical_sdf_records(source: bytes) -> tuple[bytes, ...]:
    if not source or b"\r" in source:
        raise ValueError("historical SDF is empty or uses CRLF")
    records: list[bytes] = []
    current = bytearray()
    for line in source.splitlines(keepends=True):
        current.extend(line)
        if line == b"$$$$\n":
            records.append(bytes(current))
            current.clear()
    if current or not records or b"".join(records) != source:
        raise ValueError("historical SDF records are incomplete")
    return tuple(records)


def _validate_pose_member(
    members: Mapping[str, bytes],
    path: str,
    expected_hashes: object,
    *,
    lane: str,
    case_id: str,
) -> None:
    raw = members.get(_safe_member_name(path))
    if raw is None or len(raw) > MAX_MEMBER_BYTES:
        raise ValueError(f"{lane} {case_id} pose member is missing or oversized")
    records = _split_historical_sdf_records(raw)
    if (
        not isinstance(expected_hashes, list)
        or len(records) != 5
        or tuple(_sha256_bytes(record) for record in records) != tuple(expected_hashes)
    ):
        raise ValueError(
            f"{lane} {case_id} pose artifact hashes contradict retained SDF"
        )


def _member_object(
    members: Mapping[str, bytes],
    member: str,
    *,
    name: str,
    hash_field: str,
) -> tuple[dict[str, object], bytes]:
    safe = _safe_member_name(member)
    raw = members.get(safe)
    if raw is None or len(raw) > MAX_MEMBER_BYTES:
        raise ValueError(f"{name} member is missing or oversized")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not valid JSON") from exc
    if not isinstance(payload, dict) or raw != _canonical_bytes(payload) + b"\n":
        raise ValueError(f"{name} is not canonical JSON")
    projection = dict(payload)
    observed = projection.pop(hash_field, None)
    if not _is_sha256(observed) or observed != _sha256_payload(projection):
        raise ValueError(f"{name} self-hash is invalid")
    return payload, raw


def _walltime(
    members: Mapping[str, bytes], path: str, *, lane: str
) -> dict[str, object]:
    raw = members.get(_safe_member_name(path))
    if raw is None or len(raw) > 4096:
        raise ValueError(f"{lane} wall-time receipt is missing or oversized")
    try:
        lines = raw.decode("ascii").splitlines()
        pairs = [line.split("=", 1) for line in lines]
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"{lane} wall-time receipt is invalid") from exc
    expected_fields = (
        "elapsed_seconds",
        "user_seconds",
        "system_seconds",
        "max_rss_kb",
        "exit_status",
    )
    if (
        len(lines) != len(expected_fields)
        or any(len(pair) != 2 or not pair[0] or not pair[1] for pair in pairs)
        or tuple(pair[0] for pair in pairs) != expected_fields
        or raw != ("\n".join(lines) + "\n").encode("ascii")
    ):
        raise ValueError(f"{lane} wall-time fields are invalid")
    values = dict(pairs)
    elapsed = float(values["elapsed_seconds"])
    user = float(values["user_seconds"])
    system = float(values["system_seconds"])
    maximum_rss = int(values["max_rss_kb"])
    exit_status = int(values["exit_status"])
    if (
        not all(
            math.isfinite(value) and value >= 0.0 for value in (elapsed, user, system)
        )
        or maximum_rss < 1
        or exit_status != 0
    ):
        raise ValueError(f"{lane} wall-time values are invalid")
    return {
        "elapsed_seconds_binary64_hex": elapsed.hex(),
        "user_seconds_binary64_hex": user.hex(),
        "system_seconds_binary64_hex": system.hex(),
        "maximum_rss_kb": maximum_rss,
        "exit_status": exit_status,
        "file_sha256": _sha256_bytes(raw),
    }


def _analysis(
    members: Mapping[str, bytes],
    path: str,
    *,
    lane: str,
    run_root: str,
    receipt_hashes: Mapping[str, str],
    results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    payload, raw = _member_object(
        members,
        path,
        name=f"{lane} analysis",
        hash_field="report_sha256",
    )
    source = payload.get("source_receipts_sha256")
    if (
        payload.get("schema_id") != EXPECTED_ANALYSIS_SCHEMA_ID
        or payload.get("analysis_scope") != "historical_contaminated_development_only"
        or payload.get("contains_fresh_internal_blind_holdout") is not False
        or payload.get("claimable") is not False
        or tuple(payload.get("case_ids", ())) != EXPECTED_CASE_IDS
        or not isinstance(source, Mapping)
    ):
        raise ValueError(f"{lane} analysis identity or boundary is invalid")
    expected_source = {
        f"{run_root}/receipts/engine_v2/{case_id}.json": receipt_hashes[case_id]
        for case_id in EXPECTED_CASE_IDS
    }
    if dict(source) != expected_source:
        raise ValueError(f"{lane} analysis contradicts restored receipts")
    analyzer_path = Path(score_term_analysis.__file__)
    try:
        analyzer_raw = analyzer_path.read_bytes()
    except OSError as exc:
        raise ValueError("frozen score-term analyzer source is unavailable") from exc
    if _sha256_bytes(analyzer_raw) != EXPECTED_SCORE_TERM_ANALYZER_SOURCE_SHA256:
        raise ValueError("frozen score-term analyzer implementation drifted")
    allowed_proposal_modes = set(EXPECTED_BASE_PROPOSAL_MODES)
    if lane == "rescue":
        allowed_proposal_modes.add(PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE)
    recomputed = score_term_analysis.analyze_validated_results(
        [results[case_id] for case_id in EXPECTED_CASE_IDS],
        source_receipts_sha256=expected_source,
        allowed_proposal_modes=tuple(sorted(allowed_proposal_modes)),
    )
    if payload != recomputed:
        raise ValueError(f"{lane} analysis contradicts restored candidate terms")
    return {
        "path": path,
        "file_sha256": _sha256_bytes(raw),
        "report_sha256": payload["report_sha256"],
        "case_count": payload.get("case_count"),
        "scored_case_count": payload.get("scored_case_count"),
        "candidate_count": payload.get("candidate_count"),
        "oracle_2a_recovery_case_count": payload.get("oracle_2a_recovery_case_count"),
        "full_top1_recovery_case_count": payload.get("full_top1_recovery_case_count"),
        "full_top5_recovery_case_count": payload.get("full_top5_recovery_case_count"),
    }


def _metric_summary(results: Mapping[str, Mapping[str, object]]) -> dict[str, int]:
    if tuple(sorted(results)) != EXPECTED_CASE_IDS:
        raise ValueError("lane result case set is invalid")
    totals: Counter[str] = Counter(
        {
            "case_count": len(EXPECTED_CASE_IDS),
            "scored_case_count": 0,
            "candidate_success_count": 0,
            "exact_valid_candidate_count": 0,
            "native_like_candidate_count": 0,
            "selection_eligible_candidate_count": 0,
            "native_like_selection_eligible_candidate_count": 0,
            "proposal_oracle_recovery_case_count": 0,
            "top1_recovery_case_count": 0,
            "top5_recovery_case_count": 0,
            "valid_top1_case_count": 0,
        }
    )
    for case_id in EXPECTED_CASE_IDS:
        result = results[case_id]
        diagnostics = result.get("engine_v2_diagnostics")
        if not isinstance(diagnostics, Mapping):
            raise ValueError(f"{case_id} diagnostics are missing")
        candidates = diagnostics.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError(f"{case_id} candidates are invalid")
        if result.get("status") == "failure":
            if case_id != EXPECTED_PREPARATION_FAILURE_CASE_ID or candidates:
                raise ValueError("unexpected preparation-failure result")
            continue
        if result.get("status") != "success" or len(candidates) != 64:
            raise ValueError(f"{case_id} successful candidate denominator drifted")
        successful = [
            candidate
            for candidate in candidates
            if isinstance(candidate, Mapping) and candidate.get("status") == "success"
        ]
        if len(successful) != 64:
            raise ValueError(f"{case_id} candidate success denominator drifted")
        totals["scored_case_count"] += 1
        totals["candidate_success_count"] += len(successful)
        exact_valid = [
            candidate
            for candidate in successful
            if candidate.get("geometric_valid") is True
            and candidate.get("chemical_valid") is True
        ]
        native_like = [
            candidate
            for candidate in successful
            if float(candidate["rmsd_angstrom"]) <= 2.0
        ]
        eligible = [
            candidate
            for candidate in successful
            if candidate.get("selection_eligible") is True
        ]
        totals["exact_valid_candidate_count"] += len(exact_valid)
        totals["native_like_candidate_count"] += len(native_like)
        totals["selection_eligible_candidate_count"] += len(eligible)
        totals["native_like_selection_eligible_candidate_count"] += sum(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in eligible
        )
        ranked = sorted(
            successful,
            key=lambda candidate: (
                float(candidate["score"]),
                int(candidate["proposal_index"]),
            ),
        )
        totals["proposal_oracle_recovery_case_count"] += bool(native_like)
        totals["top1_recovery_case_count"] += float(ranked[0]["rmsd_angstrom"]) <= 2.0
        totals["top5_recovery_case_count"] += any(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in ranked[:5]
        )
        totals["valid_top1_case_count"] += (
            ranked[0].get("geometric_valid") is True
            and ranked[0].get("chemical_valid") is True
        )
    return {key: int(totals[key]) for key in EXPECTED_BASELINE_METRICS}


def _frozen_summary_input_binding(value: object, *, lane: str) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != set(EXPECTED_SUMMARY_INPUT_BINDING)
        or value.get("mode") != EXPECTED_SUMMARY_INPUT_BINDING["mode"]
        or any(
            value.get(field) is not expected
            for field, expected in EXPECTED_SUMMARY_INPUT_BINDING.items()
            if field != "mode"
        )
    ):
        raise ValueError(f"{lane} summary input binding is invalid")
    return dict(value)


def _frozen_summary_lane_identity(value: object, *, lane: str) -> None:
    expected_fields = (
        EXPECTED_BASELINE_SUMMARY_FIELDS
        if lane == "baseline"
        else EXPECTED_RESCUE_SUMMARY_FIELDS
    )
    expected_role = (
        "current_source_engine_v2_execution_only"
        if lane == "baseline"
        else "development_source_paired_torsion_rescue_execution_only"
    )
    expected_engine_identity = (
        EXPECTED_BASELINE_ENGINE_IDENTITY
        if lane == "baseline"
        else EXPECTED_RESCUE_ENGINE_IDENTITY
    )
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_fields
        or value.get("engine_ids") != ["engine_v2"]
        or value.get("evidence_role") != expected_role
        or type(value.get("case_count")) is not int
        or value.get("case_count") != len(EXPECTED_CASE_IDS)
        or type(value.get("case_ids")) is not list
        or value.get("case_ids") != list(EXPECTED_CASE_IDS)
        or value.get("case_ids_sha256") != EXPECTED_CASE_IDS_SHA256
        or _canonical_bytes(value.get("engine_identity"))
        != _canonical_bytes(expected_engine_identity)
    ):
        raise ValueError(f"{lane} summary lane identity is invalid")
    if lane == "rescue":
        policy = value.get("source_paired_torsion_rescue_policy")
        if (
            value.get("development_source_paired_torsion_rescue") is not True
            or _canonical_bytes(policy)
            != _canonical_bytes(EXPECTED_SUMMARY_RESCUE_POLICY)
        ):
            raise ValueError(f"{lane} summary rescue policy is invalid")


def _frozen_summary_boundary_flags(value: object, *, lane: str) -> None:
    if not isinstance(value, Mapping) or any(
        value.get(field) is not False
        for field in EXPECTED_SUMMARY_FALSE_BOUNDARY_FIELDS
    ):
        raise ValueError(f"{lane} summary external boundary is invalid")


def _frozen_profiles(value: object, *, lane: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or len(value) != len(EXPECTED_CASE_IDS):
        raise ValueError(f"{lane} summary profiles are invalid")
    profiles: list[dict[str, object]] = []
    for index, profile in enumerate(value):
        if (
            not isinstance(profile, Mapping)
            or set(profile) != EXPECTED_PROFILE_FIELDS
            or profile.get("case_id") != EXPECTED_CASE_IDS[index]
        ):
            raise ValueError(f"{lane} summary profile projection is invalid")
        profiles.append(dict(profile))
    if _sha256_payload(profiles) != EXPECTED_PROFILE_SET_SHA256:
        raise ValueError(f"{lane} summary profiles are not the pinned cohort")
    return tuple(profiles)


def _bind_frozen_profile_to_result(
    profile: Mapping[str, object],
    result: Mapping[str, object],
    *,
    lane: str,
    case_id: str,
) -> None:
    if profile.get("ligand_artifact_sha256") != result.get(
        "native_artifact_sha256"
    ):
        raise ValueError(f"{lane} {case_id} profile native input is cross-wired")


def _load_lane(
    members: Mapping[str, bytes],
    *,
    lane: str,
    run_root: str,
    summary_path: str,
    analysis_path: str,
    walltime_path: str,
) -> dict[str, object]:
    expected_schema = (
        EXPECTED_BASELINE_SUMMARY_SCHEMA_ID
        if lane == "baseline"
        else EXPECTED_RESCUE_SUMMARY_SCHEMA_ID
    )
    summary, summary_raw = _member_object(
        members,
        summary_path,
        name=f"{lane} summary",
        hash_field="summary_sha256",
    )
    engine_identity = summary.get("engine_identity")
    _frozen_summary_lane_identity(summary, lane=lane)
    _frozen_summary_input_binding(summary.get("input_binding"), lane=lane)
    _frozen_summary_boundary_flags(summary, lane=lane)
    if (
        summary.get("schema_id") != expected_schema
        or summary.get("analysis_scope") != "historical_contaminated_development_only"
        or summary.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
        or summary.get("case_count") != len(EXPECTED_CASE_IDS)
        or tuple(summary.get("case_ids", ())) != EXPECTED_CASE_IDS
        or summary.get("case_ids_sha256") != EXPECTED_CASE_IDS_SHA256
        or not isinstance(engine_identity, Mapping)
        or engine_identity.get("scorer_backend") != EXPECTED_SCORER_BACKEND
        or (
            lane == "rescue"
            and summary.get("development_source_paired_torsion_rescue") is not True
        )
        or (
            lane == "rescue"
            and (
                engine_identity.get("proposal_profile_id")
                != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROFILE_ID
                or engine_identity.get("proposal_profile_sha256")
                != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
            )
        )
        or (
            lane == "baseline" and "development_source_paired_torsion_rescue" in summary
        )
    ):
        raise ValueError(f"{lane} summary identity or boundary is invalid")

    results: dict[str, dict[str, object]] = {}
    receipt_payloads: dict[str, dict[str, object]] = {}
    receipt_hashes: dict[str, str] = {}
    materializations: dict[str, dict[str, object]] = {}
    expected_members = {summary_path}
    for case_id in EXPECTED_CASE_IDS:
        receipt_path = f"{run_root}/receipts/engine_v2/{case_id}.json"
        materialization_path = f"{run_root}/receipts/materializations/{case_id}.json"
        expected_members.update((receipt_path, materialization_path))
        receipt, receipt_raw = _member_object(
            members,
            receipt_path,
            name=f"{lane} execution receipt {case_id}",
            hash_field="receipt_sha256",
        )
        result = receipt.get("result")
        if (
            set(receipt) != failure_atlas._EXECUTION_FIELDS
            or receipt.get("schema_id") != PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID
            or receipt.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
            or receipt.get("archive_sha256") != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or receipt.get("source_ids_sha256") != PUBLIC_REDOCKING_SOURCE_IDS_SHA256
            or receipt.get("cache_read_allowed") is not False
            or receipt.get("fresh_execution") is not True
            or not isinstance(result, Mapping)
            or result.get("case_id") != case_id
        ):
            raise ValueError(f"{lane} execution receipt identity is invalid")
        for field in (
            "implementation_sha256",
            "evaluation_pipeline_sha256",
            "execution_environment_sha256",
        ):
            if receipt.get(field) != engine_identity.get(field):
                raise ValueError(f"{lane} execution receipt engine identity drifted")
        typed_payload = _historical_v11_result(
            result,
            lane=lane,
            case_id=case_id,
        )
        if (
            typed_payload != dict(result)
            or receipt.get("command") != typed_payload.get("execution_command")
            or failure_atlas._execution_policy_tokens(receipt.get("execution_policy"))
            != typed_payload.get("execution_policy")
        ):
            raise ValueError(f"{lane} execution receipt result is cross-wired")

        materialization, materialization_raw = _member_object(
            members,
            materialization_path,
            name=f"{lane} materialization {case_id}",
            hash_field="receipt_sha256",
        )
        expected_inputs = failure_atlas._materialization_inputs(
            materialization,
            case_id=case_id,
        )
        if (
            materialization.get("schema_id")
            != PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID
            or materialization.get("source_archive_sha256")
            != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or materialization.get("hash_verified_archive") is not True
            or receipt.get("materialization_receipt_sha256")
            != materialization.get("receipt_sha256")
            or receipt.get("input_sha256s") != expected_inputs
            or {
                "receptor": result.get("receptor_artifact_sha256"),
                "reference": result.get("reference_artifact_sha256"),
                "native": result.get("native_artifact_sha256"),
                "seed": result.get("seed_artifact_sha256"),
            }
            != expected_inputs
            or materialization_raw != _canonical_bytes(materialization) + b"\n"
        ):
            raise ValueError(f"{lane} materialization binding is invalid")

        results[case_id] = typed_payload
        receipt_payloads[case_id] = receipt
        receipt_hashes[case_id] = _sha256_bytes(receipt_raw)
        materializations[case_id] = materialization
        if typed_payload["status"] == "success":
            pose_path = f"{run_root}/poses/engine_v2/{case_id}.sdf"
            _validate_pose_member(
                members,
                pose_path,
                typed_payload["pose_artifact_sha256s"],
                lane=lane,
                case_id=case_id,
            )
            expected_members.add(pose_path)

    rows = summary.get("rows")
    embedded_receipts = summary.get("execution_receipts")
    embedded_materializations = summary.get("materializations")
    profiles = summary.get("profiles")
    if not all(
        isinstance(value, list)
        for value in (rows, embedded_receipts, embedded_materializations, profiles)
    ):
        raise ValueError(f"{lane} summary collections are invalid")
    assert isinstance(rows, list)
    assert isinstance(embedded_receipts, list)
    assert isinstance(embedded_materializations, list)
    assert isinstance(profiles, list)
    frozen_profiles = _frozen_profiles(profiles, lane=lane)
    if any(
        len(value) != len(EXPECTED_CASE_IDS)
        for value in (rows, embedded_receipts, embedded_materializations, profiles)
    ):
        raise ValueError(f"{lane} summary collection denominator drifted")
    for index, case_id in enumerate(EXPECTED_CASE_IDS):
        profile = frozen_profiles[index]
        _bind_frozen_profile_to_result(
            profile,
            results[case_id],
            lane=lane,
            case_id=case_id,
        )
        if (
            rows[index] != results[case_id]
            or embedded_receipts[index] != receipt_payloads[case_id]
            or embedded_materializations[index] != materializations[case_id]
            or profile.get("case_id") != case_id
        ):
            raise ValueError(f"{lane} summary collection is cross-wired")

    root_prefix = f"{run_root}/"
    observed_members = {path for path in members if path.startswith(root_prefix)}
    if observed_members != expected_members:
        raise ValueError(f"{lane} run-root member set is invalid")

    metrics = _metric_summary(results)
    expected_metrics = (
        EXPECTED_BASELINE_METRICS if lane == "baseline" else EXPECTED_RESCUE_METRICS
    )
    if metrics != expected_metrics:
        raise ValueError(f"{lane} historical metrics drifted")
    analysis = _analysis(
        members,
        analysis_path,
        lane=lane,
        run_root=run_root,
        receipt_hashes=receipt_hashes,
        results=results,
    )
    if (
        analysis["case_count"] != metrics["case_count"]
        or analysis["scored_case_count"] != metrics["scored_case_count"]
        or analysis["candidate_count"] != metrics["candidate_success_count"]
        or analysis["oracle_2a_recovery_case_count"]
        != metrics["proposal_oracle_recovery_case_count"]
        or analysis["full_top1_recovery_case_count"]
        != metrics["top1_recovery_case_count"]
        or analysis["full_top5_recovery_case_count"]
        != metrics["top5_recovery_case_count"]
    ):
        raise ValueError(f"{lane} compact analysis metrics drifted")

    return {
        "run_root": run_root,
        "summary_path": summary_path,
        "summary_file_sha256": _sha256_bytes(summary_raw),
        "summary_sha256": summary["summary_sha256"],
        "analysis": analysis,
        "walltime_path": walltime_path,
        "walltime": _walltime(members, walltime_path, lane=lane),
        "engine_identity": dict(engine_identity),
        "metrics": metrics,
        "results": results,
        "receipts": receipt_payloads,
        "receipt_hashes": receipt_hashes,
        "member_count": len(expected_members),
        "logical_size_bytes": sum(len(members[path]) for path in expected_members),
    }


def _gap_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    baseline = [float(row["baseline_gap"]) for row in rows]
    optimized = [float(row["optimized_gap"]) for row in rows]
    deltas = [after - before for before, after in zip(baseline, optimized, strict=True)]
    pair_counts = [float(row["pair_count"]) for row in rows]
    return {
        "count": len(rows),
        "baseline_v6_minimum_vdw_surface_gap_angstrom": _distribution(baseline),
        "optimized_minimum_vdw_surface_gap_angstrom": _distribution(optimized),
        "optimized_minus_baseline_gap_angstrom": _distribution(deltas),
        "gap_change_counts": {
            "improved": sum(delta > 0.0 for delta in deltas),
            "equal": sum(delta == 0.0 for delta in deltas),
            "regressed": sum(delta < 0.0 for delta in deltas),
        },
        "full_cartesian_pair_count": _distribution(pair_counts),
    }


def _clearance_summary(
    results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    target_rows: list[dict[str, object]] = []
    non_target_count = 0
    torsion_counts: Counter[str] = Counter()
    per_case: dict[str, list[dict[str, object]]] = {
        case_id: [] for case_id in EXPECTED_CASE_IDS
    }
    total_candidates = 0
    for case_id in EXPECTED_CASE_IDS:
        result = results[case_id]
        diagnostics = result.get("engine_v2_diagnostics")
        candidates = (
            diagnostics.get("candidates") if isinstance(diagnostics, Mapping) else None
        )
        if not isinstance(candidates, list):
            raise ValueError(f"{case_id} rescue candidates are invalid")
        diagnostic_ligand_count = (
            diagnostics.get("ligand_atom_count")
            if isinstance(diagnostics, Mapping)
            else None
        )
        diagnostic_receptor_count = (
            diagnostics.get("receptor_atom_count")
            if isinstance(diagnostics, Mapping)
            else None
        )
        if candidates and (
            type(diagnostic_ligand_count) is not int
            or diagnostic_ligand_count < 1
            or type(diagnostic_receptor_count) is not int
            or diagnostic_receptor_count < 1
        ):
            raise ValueError(f"{case_id} diagnostic atom counts are invalid")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise ValueError(f"{case_id} rescue candidate is invalid")
            total_candidates += 1
            payload = candidate.get("refinement_receipt_payload")
            if (
                not isinstance(payload, Mapping)
                or payload.get("schema_id") != EXPECTED_RECEIPT_SCHEMA_ID
            ):
                raise ValueError(f"{case_id} is not uniformly V1.1 receipt-bound")
            target = (
                candidate.get("proposal_mode")
                == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            )
            evaluated = payload.get("clearance_measurement_evaluated")
            reason = payload.get("clearance_measurement_unavailable_reason")
            if not target:
                if (
                    evaluated is not False
                    or reason != "not_source_paired_rescue_target"
                    or payload.get("clearance_radii_policy_sha256") != ""
                    or payload.get(
                        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    )
                    != ""
                    or payload.get(
                        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    )
                    != ""
                    or payload.get("optimized_coordinates_sha256") != ""
                    or payload.get("clearance_ligand_atom_count") != 0
                    or payload.get("clearance_receptor_atom_count") != 0
                    or payload.get("clearance_full_cartesian_pair_count") != 0
                    or payload.get("clearance_pair_count_bound")
                    != EXPECTED_CLEARANCE_PAIR_COUNT_BOUND
                ):
                    raise ValueError("non-target clearance telemetry is not empty")
                non_target_count += 1
                continue
            torsion_evaluated = payload.get("torsion_evaluated")
            variant_available = payload.get("torsion_variant_available")
            torsion_selected = payload.get("torsion_selected")
            if any(
                type(value) is not bool
                for value in (
                    torsion_evaluated,
                    variant_available,
                    torsion_selected,
                )
            ):
                raise ValueError("target torsion state flags must be boolean")
            torsion_counts["allocated_candidate_count"] += 1
            torsion_counts["torsion_evaluated_candidate_count"] += (
                torsion_evaluated is True
            )
            torsion_counts["torsion_variant_available_candidate_count"] += (
                variant_available is True
            )
            torsion_counts["torsion_selected_candidate_count"] += (
                torsion_selected is True
            )
            torsion_counts["clearance_evaluated_candidate_count"] += evaluated is True
            ligand_count = payload.get("clearance_ligand_atom_count")
            receptor_count = payload.get("clearance_receptor_atom_count")
            pair_count = payload.get("clearance_full_cartesian_pair_count")
            pair_bound = payload.get("clearance_pair_count_bound")
            if (
                evaluated is not True
                or reason != "none"
                or payload.get("clearance_radii_policy_sha256")
                != EXPECTED_CLEARANCE_RADII_POLICY_SHA256
                or type(ligand_count) is not int
                or ligand_count != diagnostic_ligand_count
                or type(receptor_count) is not int
                or not 0 < receptor_count <= diagnostic_receptor_count
                or type(pair_count) is not int
                or pair_count != ligand_count * receptor_count
                or pair_bound != EXPECTED_CLEARANCE_PAIR_COUNT_BOUND
                or pair_count > pair_bound
                or not _is_sha256(payload.get("optimized_coordinates_sha256"))
            ):
                raise ValueError("target clearance telemetry identity is invalid")
            if torsion_selected is False and (
                not _is_sha256(payload.get("baseline_coordinates_sha256"))
                or payload.get("post_coordinates_sha256")
                != payload.get("baseline_coordinates_sha256")
            ):
                raise ValueError(
                    "unselected torsion coordinates must retain the baseline"
                )
            if variant_available is False:
                baseline_coordinates_sha256 = payload.get("baseline_coordinates_sha256")
                if (
                    not _is_sha256(baseline_coordinates_sha256)
                    or payload.get("optimized_coordinates_sha256")
                    != baseline_coordinates_sha256
                    or payload.get("post_coordinates_sha256")
                    != baseline_coordinates_sha256
                    or payload.get(
                        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    )
                    != payload.get(
                        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    )
                ):
                    raise ValueError(
                        "unavailable torsion clearance must equal its baseline"
                    )
            row = {
                "case_id": case_id,
                "proposal_index": int(candidate["proposal_index"]),
                "baseline_gap": _binary64(
                    payload.get(
                        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    ),
                    name="baseline clearance gap",
                ),
                "optimized_gap": _binary64(
                    payload.get(
                        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"
                    ),
                    name="optimized clearance gap",
                ),
                "pair_count": pair_count,
                "ligand_atom_count": ligand_count,
                "receptor_atom_count": receptor_count,
            }
            target_rows.append(row)
            per_case[case_id].append(row)

    observed_torsion = {
        key: int(torsion_counts[key]) for key in EXPECTED_TORSION_COUNTS
    }
    if (
        total_candidates != 512
        or non_target_count != 484
        or observed_torsion != EXPECTED_TORSION_COUNTS
        or [case_id for case_id in EXPECTED_CASE_IDS if per_case[case_id]]
        != [
            "5SD5_HWI",
            "5SIS_JSM",
            "6T88_MWQ",
            "6TW5_9M2",
            "6TW7_NZB",
            "6VTA_AKN",
            "6WTN_RXT",
        ]
        or any(
            len(rows) != 4
            for case_id, rows in per_case.items()
            if case_id not in {"6M2B_EZO", EXPECTED_PREPARATION_FAILURE_CASE_ID}
        )
    ):
        raise ValueError("V1.1 clearance telemetry denominator drifted")

    uncovered_rows = [
        row for row in target_rows if row["case_id"] in EXPECTED_UNCOVERED_CASE_IDS
    ]
    return {
        "receipt_schema_id": EXPECTED_RECEIPT_SCHEMA_ID,
        "uniform_v11_candidate_receipt_count": total_candidates,
        "non_target_empty_telemetry_count": non_target_count,
        "radii_policy_sha256": EXPECTED_CLEARANCE_RADII_POLICY_SHA256,
        "pair_count_bound": EXPECTED_CLEARANCE_PAIR_COUNT_BOUND,
        "pair_bound_unavailable_count": 0,
        "torsion": observed_torsion,
        "all_fixed_rescue_targets": _gap_summary(target_rows),
        "proposal_oracle_uncovered_targets": {
            "case_count": len(EXPECTED_UNCOVERED_CASE_IDS),
            "case_ids": list(EXPECTED_UNCOVERED_CASE_IDS),
            **_gap_summary(uncovered_rows),
        },
        "cases": [
            {
                "case_id": case_id,
                **_gap_summary(per_case[case_id]),
            }
            for case_id in EXPECTED_CASE_IDS
            if per_case[case_id]
        ],
    }


def _v11_rescue_allocation(
    diagnostics: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    *,
    case_id: str,
) -> tuple[int, list[dict[str, int]]]:
    proposal = diagnostics.get("source_paired_torsion_rescue_proposal_receipt")
    if not isinstance(proposal, Mapping):
        raise ValueError("source-paired proposal receipt is missing")
    proposal_projection = dict(proposal)
    proposal_sha256 = proposal_projection.pop("receipt_sha256", None)
    if not _is_sha256(proposal_sha256) or proposal_sha256 != _sha256_payload(
        proposal_projection
    ):
        raise ValueError("source-paired proposal receipt self-hash is invalid")
    policy = proposal.get("rescue_policy")
    if not isinstance(policy, Mapping):
        raise ValueError("source-paired rescue policy is missing")
    policy_projection = dict(policy)
    policy_sha256 = policy_projection.pop("fingerprint_sha256", None)
    if (
        policy_sha256 != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        or _sha256_payload(policy_projection) != policy_sha256
        or policy.get("schema_id")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID
        or policy.get("policy_id") != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROFILE_ID
        or policy.get("base_guided_policy_sha256")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
        or policy.get("candidate_count") != EXPECTED_CANDIDATE_COUNT
        or policy.get("maximum_variant_count")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
        or policy.get("source_pair_authority") != "base_uniform_v3_ensemble_receipt"
        or policy.get("variant_target_selection")
        != "rounded_even_spacing_across_ordered_v3_target_indices"
        or policy.get("authority_rotor_required") is not True
        or policy.get("ordinary_v3_and_rescue_target_parent_unions_disjoint")
        is not True
        or policy.get("rmsd_posebusters_native_rank_or_score_used_for_allocation")
        is not False
    ):
        raise ValueError("source-paired rescue policy is not frozen")
    allocation = proposal.get("allocation")
    if not isinstance(allocation, Mapping):
        raise ValueError("source-paired allocation is missing")
    allocation_projection = dict(allocation)
    allocation_sha256 = allocation_projection.pop("allocation_sha256", None)
    if not _is_sha256(allocation_sha256) or allocation_sha256 != _sha256_payload(
        allocation_projection
    ):
        raise ValueError("source-paired allocation self-hash is invalid")
    if allocation_sha256 != EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE.get(case_id):
        raise ValueError("source-paired allocation is not the pinned case allocation")
    expected_top_fields = {
        "schema_id",
        "authenticated_input_receipt_sha256",
        "budget_sha256",
        "source_ligand_system_sha256",
        "source_ligand_topology_sha256",
        "rescue_policy_sha256",
        "rescue_policy",
        "allocation",
        "baseline_guided_placement",
        "guided_placement",
        "candidate_count",
        "candidate_slots",
        "proposal_objects_and_coordinates_unchanged",
        "selected_parent_proposal_objects_retained",
        "result_dependent_allocation",
        "development_only",
        "stage0_eligible",
        "fresh_execution_authorized",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
    expected_policy_fields = {
        "schema_id",
        "policy_id",
        "base_guided_policy_sha256",
        "candidate_count",
        "maximum_variant_count",
        "source_pair_authority",
        "variant_target_selection",
        "authority_rotor_required",
        "proposal_objects_and_coordinates_unchanged",
        "selected_parent_proposal_objects_retained",
        "ordinary_v3_and_rescue_target_parent_unions_disjoint",
        "candidate_denominator_changed",
        "rmsd_posebusters_native_rank_or_score_used_for_allocation",
        "development_only",
        "stage0_eligible",
        "fresh_execution_authorized",
        "product_promotion_eligible",
        "public_claim_eligible",
        "scientifically_validated",
        "claim_safe",
        "fingerprint_sha256",
    }
    expected_allocation_fields = {
        "schema_id",
        "authenticated_input_receipt_sha256",
        "guidance_context_sha256",
        "budget_sha256",
        "rescue_policy_sha256",
        "base_guided_policy_sha256",
        "candidate_count",
        "authority_rotor_count",
        "v3_target_parent_pairs",
        "rescue_target_parent_pairs",
        "rescue_variant_count",
        "rescue_variant_cap",
        "selected_parent_proposal_objects_retained",
        "candidate_denominator_changed",
        "result_dependent_allocation",
        "development_only",
        "stage0_eligible",
        "fresh_execution_authorized",
        "claim_safe",
        "allocation_sha256",
    }
    authority_sha256 = proposal.get("authenticated_input_receipt_sha256")
    budget_sha256 = proposal.get("budget_sha256")
    guidance_context_sha256 = allocation.get("guidance_context_sha256")
    if (
        set(proposal) != expected_top_fields
        or set(policy) != expected_policy_fields
        or set(allocation) != expected_allocation_fields
        or any(
            not _is_sha256(value)
            for value in (
                authority_sha256,
                budget_sha256,
                guidance_context_sha256,
                proposal.get("source_ligand_system_sha256"),
                proposal.get("source_ligand_topology_sha256"),
            )
        )
        or allocation.get("authenticated_input_receipt_sha256") != authority_sha256
        or allocation.get("budget_sha256") != budget_sha256
        or proposal.get("rescue_policy_sha256") != policy_sha256
        or any(
            proposal.get(field) is not expected
            for field, expected in (
                ("proposal_objects_and_coordinates_unchanged", True),
                ("selected_parent_proposal_objects_retained", True),
                ("result_dependent_allocation", False),
                ("development_only", True),
                ("stage0_eligible", False),
                ("fresh_execution_authorized", False),
                ("scientifically_validated", False),
                ("claim_safe", False),
            )
        )
        or any(
            allocation.get(field) is not expected
            for field, expected in (
                ("selected_parent_proposal_objects_retained", True),
                ("candidate_denominator_changed", False),
                ("result_dependent_allocation", False),
                ("development_only", True),
                ("stage0_eligible", False),
                ("fresh_execution_authorized", False),
                ("claim_safe", False),
            )
        )
    ):
        raise ValueError("source-paired proposal authority contract is invalid")
    if (
        proposal.get("schema_id")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_SCHEMA_ID
        or proposal.get("rescue_policy_sha256") != policy_sha256
        or proposal.get("candidate_count") != EXPECTED_CANDIDATE_COUNT
        or proposal.get("result_dependent_allocation") is not False
        or allocation.get("schema_id")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID
        or allocation.get("rescue_policy_sha256") != policy_sha256
        or allocation.get("base_guided_policy_sha256")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
        or allocation.get("candidate_count") != EXPECTED_CANDIDATE_COUNT
        or allocation.get("rescue_variant_cap")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
        or allocation.get("result_dependent_allocation") is not False
        or allocation.get("candidate_denominator_changed") is not False
    ):
        raise ValueError("source-paired allocation policy identity is invalid")
    rotor_count = allocation.get("authority_rotor_count")
    raw_v3_pairs = allocation.get("v3_target_parent_pairs")
    raw_pairs = allocation.get("rescue_target_parent_pairs")
    if (
        type(rotor_count) is not int
        or rotor_count < 0
        or not isinstance(raw_v3_pairs, list)
        or not isinstance(raw_pairs, list)
    ):
        raise ValueError("source-paired allocation values are invalid")

    def normalized_pairs(rows: Sequence[object]) -> list[dict[str, int]]:
        normalized: list[dict[str, int]] = []
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != {
                "target_proposal_index",
                "parent_proposal_index",
            }:
                raise ValueError("source-paired pair row is invalid")
            target = row["target_proposal_index"]
            parent = row["parent_proposal_index"]
            if (
                type(target) is not int
                or type(parent) is not int
                or not 0 <= target < EXPECTED_CANDIDATE_COUNT
                or not 0 <= parent < EXPECTED_CANDIDATE_COUNT
                or target == parent
            ):
                raise ValueError("source-paired pair indices are invalid")
            normalized.append(
                {
                    "target_proposal_index": target,
                    "parent_proposal_index": parent,
                }
            )
        if normalized != sorted(
            normalized,
            key=lambda row: (
                row["target_proposal_index"],
                row["parent_proposal_index"],
            ),
        ):
            raise ValueError("source-paired allocation pairs are not ordered")
        return normalized

    v3_pairs = normalized_pairs(raw_v3_pairs)
    pairs = normalized_pairs(raw_pairs)
    ordered_pairs = sorted(
        (*v3_pairs, *pairs),
        key=lambda row: (
            row["target_proposal_index"],
            row["parent_proposal_index"],
        ),
    )
    rescue_count = (
        min(EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP, len(ordered_pairs))
        if rotor_count
        else 0
    )
    if rescue_count == 0:
        expected_targets: set[int] = set()
    elif rescue_count == 1:
        expected_targets = {ordered_pairs[0]["target_proposal_index"]}
    else:
        target_indices = [row["target_proposal_index"] for row in ordered_pairs]
        expected_targets = {
            target_indices[
                round(index * (len(target_indices) - 1) / (rescue_count - 1))
            ]
            for index in range(rescue_count)
        }
    expected_pairs = [
        row for row in ordered_pairs if row["target_proposal_index"] in expected_targets
    ]
    expected_v3_pairs = [
        row
        for row in ordered_pairs
        if row["target_proposal_index"] not in expected_targets
    ]
    all_targets = [row["target_proposal_index"] for row in ordered_pairs]
    all_parents = [row["parent_proposal_index"] for row in ordered_pairs]
    if (
        pairs != expected_pairs
        or v3_pairs != expected_v3_pairs
        or len(all_targets) != len(set(all_targets))
        or len(all_parents) != len(set(all_parents))
        or set(all_targets) & set(all_parents)
        or allocation.get("rescue_variant_count") != len(pairs)
        or len(pairs) > EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
        or (pairs and rotor_count == 0)
    ):
        raise ValueError("source-paired allocation is not result-independent")
    raw_slots = proposal.get("candidate_slots")
    expected_slot_fields = {
        "proposal_index",
        "candidate_id",
        "proposal_fingerprint_sha256",
        "coordinate_fingerprint_sha256",
        "torsion_metadata_sha256",
    }
    if not isinstance(raw_slots, list) or len(raw_slots) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError("source-paired candidate slots are incomplete")
    slots: list[Mapping[str, object]] = []
    candidate_ids: set[str] = set()
    slot_fingerprints: set[str] = set()
    for index, slot in enumerate(raw_slots):
        if (
            not isinstance(slot, Mapping)
            or set(slot) != expected_slot_fields
            or slot.get("proposal_index") != index
            or not isinstance(slot.get("candidate_id"), str)
            or not str(slot["candidate_id"]).strip()
            or not _is_sha256(slot.get("proposal_fingerprint_sha256"))
            or not _is_sha256(slot.get("coordinate_fingerprint_sha256"))
            or not _is_sha256(slot.get("torsion_metadata_sha256"))
            or str(slot["candidate_id"]) in candidate_ids
            or str(slot["proposal_fingerprint_sha256"]) in slot_fingerprints
        ):
            raise ValueError("source-paired candidate slot is invalid")
        candidate_ids.add(str(slot["candidate_id"]))
        slot_fingerprints.add(str(slot["proposal_fingerprint_sha256"]))
        slots.append(slot)
    candidate_by_index = {
        int(candidate["proposal_index"]): candidate for candidate in candidates
    }
    if set(candidate_by_index) != set(range(EXPECTED_CANDIDATE_COUNT)):
        raise ValueError("source-paired candidates contradict the slot denominator")
    canonical_rotatable_child_atom_indices: tuple[int, ...] | None = None
    for index, candidate in candidate_by_index.items():
        slot = slots[index]
        payload = candidate.get("refinement_receipt_payload")
        rotatable_child_atom_indices = (
            payload.get("rotatable_child_atom_indices")
            if isinstance(payload, Mapping)
            else None
        )
        if (
            not isinstance(payload, Mapping)
            or payload.get("source_proposal_sha256")
            != slot.get("proposal_fingerprint_sha256")
            or payload.get("pre_coordinates_sha256")
            != slot.get("coordinate_fingerprint_sha256")
        ):
            raise ValueError("source-paired receipt contradicts its proposal slot")
        if (
            not isinstance(rotatable_child_atom_indices, list)
            or any(
                type(atom_index) is not int or atom_index < 0
                for atom_index in rotatable_child_atom_indices
            )
            or rotatable_child_atom_indices
            != sorted(set(rotatable_child_atom_indices))
        ):
            raise ValueError("source-paired rotor authority list is invalid")
        observed_rotatable_child_atom_indices = tuple(rotatable_child_atom_indices)
        if canonical_rotatable_child_atom_indices is None:
            canonical_rotatable_child_atom_indices = (
                observed_rotatable_child_atom_indices
            )
        elif (
            observed_rotatable_child_atom_indices
            != canonical_rotatable_child_atom_indices
        ):
            raise ValueError("source-paired rotor authority lists disagree")
    if (
        canonical_rotatable_child_atom_indices is None
        or len(canonical_rotatable_child_atom_indices) != rotor_count
        or bool(canonical_rotatable_child_atom_indices) is not bool(rotor_count)
    ):
        raise ValueError("source-paired rotor authority count is inconsistent")
    rescue_targets = {
        int(candidate["proposal_index"])
        for candidate in candidates
        if candidate.get("proposal_mode")
        == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
    }
    v3_targets = {row["target_proposal_index"] for row in v3_pairs}
    candidate_v3_targets = {
        index
        for index, candidate in candidate_by_index.items()
        if candidate.get("proposal_mode") == "uniform_v3_rigid_ensemble"
    }
    v3_parent_by_target = {
        row["target_proposal_index"]: row["parent_proposal_index"] for row in v3_pairs
    }
    if candidate_v3_targets != v3_targets or any(
        candidate_by_index[target].get("ensemble_source_proposal_index") != parent
        for target, parent in v3_parent_by_target.items()
    ):
        raise ValueError("V3 candidate lineage contradicts the allocation")
    baseline_guided = proposal.get("baseline_guided_placement")
    guided = proposal.get("guided_placement")

    def authenticated_guided_receipt(
        value: object,
        *,
        expected_schema_id: str,
        name: str,
    ) -> tuple[Mapping[str, object], str]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} receipt is missing")
        projection = dict(value)
        receipt_sha256 = projection.pop("receipt_sha256", None)
        if (
            value.get("schema_id") != expected_schema_id
            or not _is_sha256(receipt_sha256)
            or receipt_sha256 != _sha256_payload(projection)
        ):
            raise ValueError(f"{name} receipt self-hash is invalid")
        return value, str(receipt_sha256)

    baseline_guided, baseline_guided_sha256 = authenticated_guided_receipt(
        baseline_guided,
        expected_schema_id=EXPECTED_BASELINE_GUIDED_PLACEMENT_SCHEMA_ID,
        name="baseline guided placement",
    )
    guided, _ = authenticated_guided_receipt(
        guided,
        expected_schema_id=EXPECTED_RESCUE_GUIDED_PLACEMENT_SCHEMA_ID,
        name="rescue guided placement",
    )
    common_guided_fields = {
        "schema_id",
        "authenticated_input_receipt_sha256",
        "guidance_context_sha256",
        "guided_policy_sha256",
        "budget_sha256",
        "proposal_count",
        "proposal_fingerprint_sha256s",
        "proposal_modes",
        "proposal_guidance_rows",
        "guided_proposal_count",
        "pocket_center_baseline_count",
        "uniform_fallback_count",
        "uniform_v3_ensemble_count",
        "uniform_random_placement_retained_as_fallback",
        "feature_counts",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
    rescue_guided_fields = common_guided_fields | {
        "source_paired_torsion_rescue_profile",
        "baseline_guided_receipt_sha256",
        "torsion_rescue_allocation_sha256",
        "uniform_torsion_rescue_variant_count",
        "uniform_torsion_rescue_variant_cap",
        "proposal_objects_and_coordinates_unchanged",
        "selected_parent_proposal_objects_retained",
        "development_only",
        "stage0_eligible",
        "fresh_execution_authorized",
    }
    feature_fields = {
        "ligand_acceptor",
        "ligand_aromatic",
        "ligand_aromatic_system",
        "ligand_donor",
        "ligand_hydrophobic",
        "ligand_hydrophobic_patch",
        "ligand_negative",
        "ligand_positive",
        "ligand_shape_atom",
        "receptor_acceptor",
        "receptor_aromatic",
        "receptor_aromatic_plane",
        "receptor_donor",
        "receptor_hydrophobic",
        "receptor_hydrophobic_patch",
        "receptor_negative",
        "receptor_positive",
        "receptor_shape_atom",
    }
    baseline_features = baseline_guided.get("feature_counts")
    guided_features = guided.get("feature_counts")
    if (
        set(baseline_guided) != common_guided_fields
        or set(guided) != rescue_guided_fields
        or guided.get("baseline_guided_receipt_sha256") != baseline_guided_sha256
        or guided.get("torsion_rescue_allocation_sha256") != allocation_sha256
        or baseline_guided.get("authenticated_input_receipt_sha256") != authority_sha256
        or guided.get("authenticated_input_receipt_sha256") != authority_sha256
        or baseline_guided.get("guidance_context_sha256") != guidance_context_sha256
        or guided.get("guidance_context_sha256") != guidance_context_sha256
        or baseline_guided.get("budget_sha256") != budget_sha256
        or guided.get("budget_sha256") != budget_sha256
        or baseline_guided.get("guided_policy_sha256")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
        or guided.get("guided_policy_sha256")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        or baseline_guided.get("proposal_count") != EXPECTED_CANDIDATE_COUNT
        or guided.get("proposal_count") != EXPECTED_CANDIDATE_COUNT
        or baseline_guided.get("uniform_random_placement_retained_as_fallback")
        is not True
        or guided.get("uniform_random_placement_retained_as_fallback") is not True
        or baseline_guided.get("scientifically_validated") is not False
        or baseline_guided.get("claim_safe") is not False
        or guided.get("source_paired_torsion_rescue_profile") is not True
        or guided.get("uniform_torsion_rescue_variant_cap")
        != EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
        or any(
            guided.get(field) is not expected
            for field, expected in (
                ("proposal_objects_and_coordinates_unchanged", True),
                ("selected_parent_proposal_objects_retained", True),
                ("development_only", True),
                ("stage0_eligible", False),
                ("fresh_execution_authorized", False),
                ("scientifically_validated", False),
                ("claim_safe", False),
            )
        )
        or not isinstance(baseline_features, Mapping)
        or set(baseline_features) != feature_fields
        or any(
            type(value) is not int or value < 0 for value in baseline_features.values()
        )
        or guided_features != baseline_features
    ):
        raise ValueError("guided proposal authority contract is invalid")
    baseline_rows = baseline_guided.get("proposal_guidance_rows")
    baseline_modes = baseline_guided.get("proposal_modes")
    baseline_fingerprints = baseline_guided.get("proposal_fingerprint_sha256s")
    guided_rows = guided.get("proposal_guidance_rows")
    guided_modes = guided.get("proposal_modes")
    guided_fingerprints = guided.get("proposal_fingerprint_sha256s")
    if any(
        not isinstance(value, list) or len(value) != EXPECTED_CANDIDATE_COUNT
        for value in (
            baseline_rows,
            baseline_modes,
            baseline_fingerprints,
            guided_rows,
            guided_modes,
            guided_fingerprints,
        )
    ):
        raise ValueError("guided proposal lineage is incomplete")
    assert isinstance(baseline_rows, list)
    assert isinstance(baseline_modes, list)
    assert isinstance(baseline_fingerprints, list)
    assert isinstance(guided_rows, list)
    assert isinstance(guided_modes, list)
    assert isinstance(guided_fingerprints, list)
    if (
        baseline_guided.get("guided_proposal_count") != len(ordered_pairs)
        or baseline_guided.get("pocket_center_baseline_count") != 8
        or baseline_guided.get("uniform_fallback_count") != 40
        or baseline_guided.get("uniform_v3_ensemble_count") != len(ordered_pairs)
        or baseline_modes.count("pocket_center_baseline") != 8
        or baseline_modes.count("uniform_fallback") != 40
        or baseline_modes.count("uniform_v3_rigid_ensemble") != len(ordered_pairs)
        or guided.get("guided_proposal_count") != len(ordered_pairs)
        or guided.get("pocket_center_baseline_count") != 8
        or guided.get("uniform_fallback_count") != 40
        or guided.get("uniform_v3_ensemble_count") != len(v3_pairs)
        or guided.get("uniform_torsion_rescue_variant_count") != len(pairs)
        or guided_modes.count("pocket_center_baseline") != 8
        or guided_modes.count("uniform_fallback") != 40
        or guided_modes.count("uniform_v3_rigid_ensemble") != len(v3_pairs)
        or guided_modes.count(PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE)
        != len(pairs)
    ):
        raise ValueError("guided proposal counts contradict the frozen cohort")
    baseline_parent_by_target = {
        row["target_proposal_index"]: row["parent_proposal_index"]
        for row in ordered_pairs
    }
    baseline_v3_targets = {
        index
        for index, mode in enumerate(baseline_modes)
        if mode == "uniform_v3_rigid_ensemble"
    }
    if baseline_v3_targets != set(baseline_parent_by_target):
        raise ValueError("baseline guided V3 targets contradict the allocation")
    baseline_guidance_fields = {
        "proposal_index",
        "mode",
        "ligand_anchor_atom_indices",
        "receptor_anchor_atom_indices",
        "anchor_pairs",
        "anchor_pairing",
        "anchor_distance_aggregation",
        "requested_anchor_distance_angstrom_binary64_hex",
        "observed_anchor_distance_angstrom_binary64_hex",
        "ensemble_source_proposal_index",
    }
    for index, candidate in candidate_by_index.items():
        baseline_row = baseline_rows[index]
        row = guided_rows[index]
        slot = slots[index]
        expected_baseline_mode = (
            "uniform_v3_rigid_ensemble"
            if index in baseline_parent_by_target
            else candidate.get("proposal_mode")
        )
        if (
            not isinstance(baseline_row, Mapping)
            or set(baseline_row) != baseline_guidance_fields
            or baseline_row.get("proposal_index") != index
            or baseline_row.get("mode") != expected_baseline_mode
            or baseline_modes[index] != expected_baseline_mode
            or baseline_fingerprints[index] != slot.get("proposal_fingerprint_sha256")
            or baseline_row.get("ensemble_source_proposal_index")
            != baseline_parent_by_target.get(index)
            or any(
                baseline_row.get(field) != []
                for field in (
                    "ligand_anchor_atom_indices",
                    "receptor_anchor_atom_indices",
                    "anchor_pairs",
                )
            )
            or any(
                baseline_row.get(field) is not None
                for field in (
                    "anchor_pairing",
                    "anchor_distance_aggregation",
                    "requested_anchor_distance_angstrom_binary64_hex",
                    "observed_anchor_distance_angstrom_binary64_hex",
                )
            )
        ):
            raise ValueError("baseline guided lineage contradicts the allocation")
        if (
            not isinstance(row, Mapping)
            or set(row)
            != baseline_guidance_fields | {"torsion_rescue_parent_proposal_index"}
            or row.get("proposal_index") != index
            or row.get("mode") != candidate.get("proposal_mode")
            or guided_modes[index] != candidate.get("proposal_mode")
            or guided_fingerprints[index] != slot.get("proposal_fingerprint_sha256")
            or row.get("ensemble_source_proposal_index")
            != candidate.get("ensemble_source_proposal_index")
            or row.get("torsion_rescue_parent_proposal_index")
            != candidate.get("torsion_rescue_parent_proposal_index")
        ):
            raise ValueError("guided proposal lineage contradicts candidate rows")
        baseline_common = dict(baseline_row)
        guided_common = dict(row)
        for document in (baseline_common, guided_common):
            document.pop("mode", None)
            document.pop("ensemble_source_proposal_index", None)
        guided_common.pop("torsion_rescue_parent_proposal_index", None)
        if baseline_common != guided_common:
            raise ValueError("guided proposal changed frozen placement guidance")
    expected_v3_indices = [row["target_proposal_index"] for row in v3_pairs]
    for candidate in candidates:
        payload = candidate.get("refinement_receipt_payload")
        mode = candidate.get("proposal_mode")
        expected_lane = (
            "source_paired_torsion_rescue_variant"
            if mode == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            else (
                "uniform_v3_rigid_ensemble"
                if mode == "uniform_v3_rigid_ensemble"
                else "ineligible_source_or_other_lane"
            )
        )
        if (
            not isinstance(payload, Mapping)
            or payload.get("source_paired_torsion_rescue_allocation_sha256")
            != allocation_sha256
            or payload.get("source_paired_torsion_rescue_pairs") != pairs
            or payload.get("source_paired_torsion_rescue_guidance_context_sha256")
            != guidance_context_sha256
            or payload.get("source_paired_torsion_rescue_budget_sha256")
            != budget_sha256
            or payload.get("v3_proposal_indices") != expected_v3_indices
            or payload.get("proposal_torsion_eligibility_lane") != expected_lane
            or payload.get("source_paired_parent_proposal_index")
            != candidate.get("torsion_rescue_parent_proposal_index")
            or payload.get("nested_v6_treated_proposal_as_v3_variant")
            is not (mode == "uniform_v3_rigid_ensemble")
            or payload.get("rescue_target_excluded_from_nested_v3_indices")
            is not (mode == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE)
        ):
            raise ValueError("candidate receipt contradicts case allocation lineage")
    pair_targets = [row["target_proposal_index"] for row in pairs]
    if rescue_targets != set(pair_targets) or len(pair_targets) != len(
        set(pair_targets)
    ):
        raise ValueError("rescue candidate modes contradict the allocation")
    for row in pairs:
        target = row["target_proposal_index"]
        parent = row["parent_proposal_index"]
        candidate = candidate_by_index[target]
        parent_candidate = candidate_by_index[parent]
        payload = candidate.get("refinement_receipt_payload")
        if (
            target == parent
            or parent in rescue_targets
            or candidate.get("torsion_rescue_parent_proposal_index") != parent
            or parent_candidate.get("proposal_mode")
            == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            or not isinstance(payload, Mapping)
            or payload.get("source_paired_parent_proposal_index") != parent
            or payload.get("source_paired_torsion_rescue_pairs") != pairs
            or payload.get("source_paired_torsion_rescue_allocation_sha256")
            != allocation_sha256
        ):
            raise ValueError("rescue allocation parent binding is invalid")
    if proposal_sha256 != EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE.get(case_id):
        raise ValueError("source-paired proposal is not the pinned case proposal")
    return rotor_count, pairs


def _lane_comparison(
    baseline: Mapping[str, object],
    rescue: Mapping[str, object],
) -> dict[str, object]:
    baseline_results = baseline.get("results")
    rescue_results = rescue.get("results")
    if not isinstance(baseline_results, Mapping) or not isinstance(
        rescue_results, Mapping
    ):
        raise ValueError("lane result maps are invalid")
    coordinate_changes: dict[str, list[int]] = {}
    parent_duplicate_count = 0
    for case_id in EXPECTED_CASE_IDS:
        baseline_result = baseline_results[case_id]
        rescue_result = rescue_results[case_id]
        if not isinstance(baseline_result, Mapping) or not isinstance(
            rescue_result, Mapping
        ):
            raise ValueError("lane result row is invalid")
        for field in (
            "receptor_artifact_sha256",
            "reference_artifact_sha256",
            "native_artifact_sha256",
            "seed_artifact_sha256",
        ):
            if baseline_result.get(field) != rescue_result.get(field):
                raise ValueError("lane input artifact identity drifted")
        baseline_diagnostics = baseline_result.get("engine_v2_diagnostics")
        rescue_diagnostics = rescue_result.get("engine_v2_diagnostics")
        baseline_candidates = (
            baseline_diagnostics.get("candidates")
            if isinstance(baseline_diagnostics, Mapping)
            else None
        )
        rescue_candidates = (
            rescue_diagnostics.get("candidates")
            if isinstance(rescue_diagnostics, Mapping)
            else None
        )
        if not isinstance(baseline_candidates, list) or not isinstance(
            rescue_candidates, list
        ):
            raise ValueError("lane candidate collections are invalid")
        if any(not isinstance(candidate, Mapping) for candidate in baseline_candidates):
            raise ValueError("baseline candidate collection contains an invalid row")
        if any(not isinstance(candidate, Mapping) for candidate in rescue_candidates):
            raise ValueError("rescue candidate collection contains an invalid row")
        baseline_by_index = {
            int(candidate["proposal_index"]): candidate
            for candidate in baseline_candidates
        }
        rescue_by_index = {
            int(candidate["proposal_index"]): candidate
            for candidate in rescue_candidates
        }
        if (
            len(baseline_by_index) != len(baseline_candidates)
            or len(rescue_by_index) != len(rescue_candidates)
            or set(baseline_by_index) != set(rescue_by_index)
        ):
            raise ValueError("lane candidate indices drifted")
        changed = [
            index
            for index in sorted(baseline_by_index)
            if baseline_by_index[index].get("coordinate_fingerprint_sha256")
            != rescue_by_index[index].get("coordinate_fingerprint_sha256")
        ]
        allocation_pairs: list[dict[str, int]] = []
        if rescue_candidates:
            assert isinstance(rescue_diagnostics, Mapping)
            _, allocation_pairs = _v11_rescue_allocation(
                rescue_diagnostics,
                rescue_candidates,
                case_id=case_id,
            )
        expected_changed = sorted(
            row["target_proposal_index"] for row in allocation_pairs
        )
        if changed != expected_changed:
            raise ValueError("rescue coordinate changes contradict the allocation")
        if changed:
            coordinate_changes[case_id] = changed
        for pair in allocation_pairs:
            target = pair["target_proposal_index"]
            parent = pair["parent_proposal_index"]
            target_candidate = rescue_by_index[target]
            parent_candidate = rescue_by_index[parent]
            payload = target_candidate.get("refinement_receipt_payload")
            if target_candidate.get(
                "coordinate_fingerprint_sha256"
            ) == parent_candidate.get("coordinate_fingerprint_sha256"):
                parent_duplicate_count += 1
            if (
                isinstance(payload, Mapping)
                and payload.get("torsion_variant_available") is False
            ):
                baseline_parent_coordinate = baseline_by_index[parent].get(
                    "coordinate_fingerprint_sha256"
                )
                if any(
                    coordinate != baseline_parent_coordinate
                    for coordinate in (
                        parent_candidate.get("coordinate_fingerprint_sha256"),
                        target_candidate.get("coordinate_fingerprint_sha256"),
                        payload.get("baseline_coordinates_sha256"),
                        payload.get("post_coordinates_sha256"),
                        payload.get("optimized_coordinates_sha256"),
                    )
                ):
                    raise ValueError(
                        "unavailable torsion coordinates contradict baseline parent"
                    )
    changed_count = sum(len(indices) for indices in coordinate_changes.values())
    if changed_count != 28 or parent_duplicate_count != 28:
        raise ValueError("source-paired coordinate lineage drifted")
    return {
        "same_case_denominator": True,
        "same_candidate_denominator": True,
        "same_input_artifacts": True,
        "baseline_to_rescue_coordinate_change_candidate_count": changed_count,
        "baseline_to_rescue_coordinate_change_proposal_indices_by_case": (
            coordinate_changes
        ),
        "rescue_to_parent_coordinate_duplicate_candidate_count": (
            parent_duplicate_count
        ),
        "torsion_selected_candidate_count": 0,
        "semantic_regression_against_pinned_v1_metrics": False,
        "interpretation": (
            "v11_adds_clearance_telemetry_without_changing_the_pinned_v1_"
            "historical_outcome_counts"
        ),
    }


def _shared_engine_identity(
    baseline_identity: Mapping[str, object],
    rescue_identity: Mapping[str, object],
) -> dict[str, object]:
    shared_hash_fields = (
        "implementation_sha256",
        "evaluation_pipeline_sha256",
        "execution_environment_sha256",
        "interaction_refiner_config_sha256",
    )
    shared_identity: dict[str, object] = {
        field: baseline_identity.get(field) for field in shared_hash_fields
    }
    shared_identity["scorer_backend"] = baseline_identity.get("scorer_backend")
    if any(
        not _is_sha256(value) or rescue_identity.get(field) != value
        for field, value in shared_identity.items()
        if field != "scorer_backend"
    ) or (
        shared_identity["scorer_backend"] != EXPECTED_SCORER_BACKEND
        or rescue_identity.get("scorer_backend") != EXPECTED_SCORER_BACKEND
        or shared_identity["interaction_refiner_config_sha256"]
        != EXPECTED_INTERACTION_REFINER_CONFIG_SHA256
    ):
        raise ValueError("lane engine identity is not comparable")
    return shared_identity


def _build_report(members: Mapping[str, bytes]) -> dict[str, object]:
    baseline = _load_lane(
        members,
        lane="baseline",
        run_root=BASELINE_RUN_ROOT,
        summary_path=BASELINE_SUMMARY_PATH,
        analysis_path=BASELINE_ANALYSIS_PATH,
        walltime_path=BASELINE_WALLTIME_PATH,
    )
    rescue = _load_lane(
        members,
        lane="rescue",
        run_root=RESCUE_RUN_ROOT,
        summary_path=RESCUE_SUMMARY_PATH,
        analysis_path=RESCUE_ANALYSIS_PATH,
        walltime_path=RESCUE_WALLTIME_PATH,
    )
    baseline_identity = baseline["engine_identity"]
    rescue_identity = rescue["engine_identity"]
    assert isinstance(baseline_identity, Mapping)
    assert isinstance(rescue_identity, Mapping)
    shared_identity = _shared_engine_identity(baseline_identity, rescue_identity)
    baseline_walltime = baseline["walltime"]
    rescue_walltime = rescue["walltime"]
    assert isinstance(baseline_walltime, Mapping)
    assert isinstance(rescue_walltime, Mapping)
    elapsed_delta = float.fromhex(
        str(rescue_walltime["elapsed_seconds_binary64_hex"])
    ) - float.fromhex(str(baseline_walltime["elapsed_seconds_binary64_hex"]))
    rescue_results = rescue["results"]
    assert isinstance(rescue_results, Mapping)

    report: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "evidence_role": "source_paired_clearance_v11_receipt_audit",
        "operator_observed_checkout_or_base_sha1": (
            OPERATOR_OBSERVED_CHECKOUT_OR_BASE_SHA1
        ),
        "operator_observed_checkout_or_base_receipt_authenticated": False,
        "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
        "input_archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_identifiers_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
        "case_count": len(EXPECTED_CASE_IDS),
        "case_ids": list(EXPECTED_CASE_IDS),
        "case_ids_sha256": EXPECTED_CASE_IDS_SHA256,
        "engine_identity": shared_identity,
        "baseline": {
            key: baseline[key]
            for key in (
                "run_root",
                "summary_path",
                "summary_file_sha256",
                "summary_sha256",
                "analysis",
                "walltime_path",
                "walltime",
                "metrics",
                "member_count",
                "logical_size_bytes",
            )
        },
        "rescue": {
            key: rescue[key]
            for key in (
                "run_root",
                "summary_path",
                "summary_file_sha256",
                "summary_sha256",
                "analysis",
                "walltime_path",
                "walltime",
                "metrics",
                "member_count",
                "logical_size_bytes",
            )
        },
        "clearance_telemetry": _clearance_summary(rescue_results),
        "comparison": _lane_comparison(baseline, rescue),
        "runtime": {
            "wall_elapsed_delta_seconds_binary64_hex": elapsed_delta.hex(),
            "interpretation": ("single_run_historical_development_only_no_speed_claim"),
        },
        "preservation": {
            "report_member": REPORT_PATH,
            "archive_path": ARCHIVE_PATH,
            "members_sha256_path": MEMBERS_PATH,
            "bundle_sha256_path": BUNDLE_PATH,
            "archive_binding_direction": (
                "external_reviewed_hashes_bind_this_report_member"
            ),
        },
        "development_only": True,
        "contains_engineering_smoke": False,
        "contains_fresh_internal_blind_holdout": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "stage0_eligible": False,
        "primary_claim_eligible": False,
        "public_claim_eligible": False,
        "product_promotion_eligible": False,
        "selection_rule_changed": False,
        "threshold_changed": False,
        "v7_replacement_authorized": False,
        "decision": ("telemetry_available_for_descriptive_review_no_policy_change"),
    }
    report["report_sha256"] = _sha256_payload(report)
    return report


def _read_regular_mode_0600(path: Path, *, repo_root: Path) -> tuple[str, bytes]:
    raw, relative = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        path,
        maximum=MAX_MEMBER_BYTES,
        name="V1.1 evidence member",
    )
    return _safe_member_name(relative), raw


def _collect_run_root(
    repo_root: Path,
    relative_root: str,
    *,
    maximum_total_bytes: int,
) -> dict[str, bytes]:
    root = repo_root / relative_root
    failure_atlas._reject_symlink_ancestry(root, name="V1.1 run root")
    root_metadata = root.lstat()
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or stat.S_ISLNK(root_metadata.st_mode)
        or stat.S_IMODE(root_metadata.st_mode) != 0o700
    ):
        raise ValueError(f"run root must be a mode-0700 directory: {relative_root}")
    members: dict[str, bytes] = {}
    logical_size = 0
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if (
            not stat.S_ISDIR(current_metadata.st_mode)
            or stat.S_ISLNK(current_metadata.st_mode)
            or stat.S_IMODE(current_metadata.st_mode) != 0o700
        ):
            raise ValueError("run-root directory contract is invalid")
        for directory in directories:
            metadata = (current_path / directory).lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("run root cannot contain symlink directories")
        for filename in filenames:
            safe, raw = _read_regular_mode_0600(
                current_path / filename,
                repo_root=repo_root,
            )
            if safe in members:
                raise ValueError("run root contains duplicate member names")
            logical_size += len(raw)
            if logical_size > maximum_total_bytes:
                raise ValueError("run-root members exceed the aggregate size bound")
            members[safe] = raw
    return members


def _collect_source_members(repo_root: Path) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    logical_size = 0
    for run_root in (BASELINE_RUN_ROOT, RESCUE_RUN_ROOT):
        run_members = _collect_run_root(
            repo_root,
            run_root,
            maximum_total_bytes=MAX_TAR_BYTES - logical_size,
        )
        if set(members).intersection(run_members):
            raise ValueError("evidence member path is duplicated")
        members.update(run_members)
        logical_size += sum(len(raw) for raw in run_members.values())
    for relative in (
        BASELINE_ANALYSIS_PATH,
        RESCUE_ANALYSIS_PATH,
        BASELINE_WALLTIME_PATH,
        RESCUE_WALLTIME_PATH,
    ):
        safe, raw = _read_regular_mode_0600(
            repo_root / relative,
            repo_root=repo_root,
        )
        if safe in members:
            raise ValueError("evidence member path is duplicated")
        logical_size += len(raw)
        if logical_size > MAX_TAR_BYTES:
            raise ValueError("evidence members exceed the aggregate size bound")
        members[safe] = raw
    if len(members) != EXPECTED_EVIDENCE_MEMBER_COUNT - 1:
        raise ValueError("pre-report evidence member denominator drifted")
    return members


def _deterministic_tar_bytes(members: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name in sorted(members):
            safe = _safe_member_name(name)
            payload = members[safe]
            if len(payload) > MAX_MEMBER_BYTES:
                raise ValueError("archive member exceeds the fixed size bound")
            info = tarfile.TarInfo(safe)
            info.size = len(payload)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    raw = buffer.getvalue()
    if len(raw) > MAX_TAR_BYTES:
        raise ValueError("deterministic tar exceeds the fixed size bound")
    return raw


def _compress_zstd(tar_raw: bytes) -> bytes:
    try:
        completed = subprocess.run(
            ("zstd", "-q", "-T1", "-19", "-c"),
            input=tar_raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("deterministic Zstandard compression failed") from exc
    archive_raw = completed.stdout
    if not archive_raw or len(archive_raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed archive exceeds the fixed size bound")
    return archive_raw


def _manifest_bytes(members: Mapping[str, bytes]) -> bytes:
    raw = "".join(
        f"{_sha256_bytes(members[name])}  {name}\n" for name in sorted(members)
    ).encode("ascii")
    if len(raw) > MAX_MEMBER_MANIFEST_BYTES:
        raise ValueError("member manifest exceeds the fixed size bound")
    return raw


def _parse_manifest(raw: bytes) -> dict[str, str]:
    if len(raw) > MAX_MEMBER_MANIFEST_BYTES:
        raise ValueError("member manifest exceeds the fixed size bound")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("member manifest is not ASCII") from exc
    observed: dict[str, str] = {}
    for line in lines:
        if "  " not in line:
            raise ValueError("member manifest row is invalid")
        digest, name = line.split("  ", 1)
        safe = _safe_member_name(name)
        if safe in observed or not _is_sha256(digest):
            raise ValueError("member manifest identity is invalid")
        observed[safe] = digest
    if len(observed) != EXPECTED_EVIDENCE_MEMBER_COUNT:
        raise ValueError("member manifest count drifted")
    if raw != "".join(
        f"{observed[name]}  {name}\n" for name in sorted(observed)
    ).encode("ascii"):
        raise ValueError("member manifest is not canonically sorted")
    return observed


def _tar_members(tar_raw: bytes, manifest: Mapping[str, str]) -> dict[str, bytes]:
    if len(tar_raw) > MAX_TAR_BYTES:
        raise ValueError("tar stream exceeds the fixed size bound")
    restored: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_raw), mode="r:") as archive:
            for member in archive:
                safe = _safe_member_name(member.name)
                if (
                    safe in restored
                    or not member.isreg()
                    or stat.S_IMODE(member.mode) != 0o600
                    or member.uid != 0
                    or member.gid != 0
                    or member.mtime != 0
                    or member.size < 0
                    or member.size > MAX_MEMBER_BYTES
                ):
                    raise ValueError("tar member contract is invalid")
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("tar member payload is unavailable")
                payload = handle.read(MAX_MEMBER_BYTES + 1)
                if (
                    len(payload) != member.size
                    or len(payload) > MAX_MEMBER_BYTES
                    or manifest.get(safe) != _sha256_bytes(payload)
                ):
                    raise ValueError("tar member payload hash is invalid")
                restored[safe] = payload
    except tarfile.TarError as exc:
        raise ValueError("tar stream is invalid") from exc
    if set(restored) != set(manifest):
        raise ValueError("tar member set contradicts the manifest")
    if tar_raw != _deterministic_tar_bytes(restored):
        raise ValueError("tar stream is not in the canonical deterministic layout")
    return restored


def _bundle_bytes(archive_sha256: str, members_sha256: str) -> bytes:
    return (
        f"{archive_sha256}  {Path(ARCHIVE_PATH).name}\n"
        f"{members_sha256}  {Path(MEMBERS_PATH).name}\n"
    ).encode("ascii")


def _verify_bundle_bytes(
    *,
    archive_raw: bytes,
    members_raw: bytes,
    bundle_raw: bytes,
    expected_archive_sha256: str,
    expected_members_sha256: str,
    expected_bundle_sha256: str,
    expected_report_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    for value, name in (
        (expected_archive_sha256, "archive SHA-256"),
        (expected_members_sha256, "member-manifest SHA-256"),
        (expected_bundle_sha256, "bundle SHA-256"),
        (expected_report_sha256, "report SHA-256"),
    ):
        if not _is_sha256(value):
            raise ValueError(f"expected {name} is invalid")
    if (
        _sha256_bytes(archive_raw) != expected_archive_sha256
        or _sha256_bytes(members_raw) != expected_members_sha256
        or _sha256_bytes(bundle_raw) != expected_bundle_sha256
        or bundle_raw != _bundle_bytes(expected_archive_sha256, expected_members_sha256)
    ):
        raise ValueError("archive bundle identity is invalid")
    manifest = _parse_manifest(members_raw)
    tar_raw = failure_atlas._bounded_zstd_decompress(archive_raw)
    restored = _tar_members(tar_raw, manifest)
    report_raw = restored.get(REPORT_PATH)
    if report_raw is None:
        raise ValueError("audit report member is missing")
    report, _ = _member_object(
        restored,
        REPORT_PATH,
        name="V1.1 clearance audit",
        hash_field="report_sha256",
    )
    if (
        report.get("schema_id") != SCHEMA_ID
        or report.get("operator_observed_checkout_or_base_sha1")
        != OPERATOR_OBSERVED_CHECKOUT_OR_BASE_SHA1
        or report.get("operator_observed_checkout_or_base_receipt_authenticated")
        is not False
        or report.get("report_sha256") != expected_report_sha256
    ):
        raise ValueError("V1.1 clearance audit identity is invalid")
    source_members = dict(restored)
    source_members.pop(REPORT_PATH)
    recomputed = _build_report(source_members)
    if report != recomputed or report_raw != _canonical_bytes(recomputed) + b"\n":
        raise ValueError("archived V1.1 audit contradicts raw receipt members")
    identity = {
        "archive_sha256": expected_archive_sha256,
        "member_manifest_sha256": expected_members_sha256,
        "bundle_sha256": expected_bundle_sha256,
        "report_sha256": expected_report_sha256,
        "member_count": len(restored),
        "archive_size_bytes": len(archive_raw),
        "tar_size_bytes": len(tar_raw),
        "expanded_member_size_bytes": sum(len(value) for value in restored.values()),
    }
    return report, identity


def _unlink_owned_name(
    parent_descriptor: int,
    name: str,
    device: int,
    inode: int,
) -> bool:
    try:
        metadata = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_dev != device
        or metadata.st_ino != inode
    ):
        return False
    try:
        os.unlink(name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
    except OSError:
        return False
    return True


def _unlink_owned_output(
    repo_root: Path,
    relative_path: Path,
    device: int,
    inode: int,
) -> bool:
    try:
        parent_descriptor = failure_atlas._owned_output_directory_descriptor(
            repo_root,
            relative_path.parent,
        )
    except (OSError, ValueError):
        return False
    try:
        return _unlink_owned_name(
            parent_descriptor,
            relative_path.name,
            device,
            inode,
        )
    finally:
        os.close(parent_descriptor)


def _write_exclusive_owned(
    repo_root: Path,
    relative_path: Path,
    payload: bytes,
) -> tuple[int, int]:
    parent_descriptor = failure_atlas._owned_output_directory_descriptor(
        repo_root,
        relative_path.parent,
    )
    descriptor = -1
    temporary_name = f".{relative_path.name}.{secrets.token_hex(16)}.tmp"
    temporary_created = False
    final_link_created = False
    inode_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        temporary_created = True
        temporary_metadata = os.fstat(descriptor)
        inode_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(
            temporary_name,
            relative_path.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        final_link_created = True
        os.fsync(parent_descriptor)
        final_metadata = os.stat(
            relative_path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            (final_metadata.st_dev, final_metadata.st_ino) != inode_identity
            or not stat.S_ISREG(final_metadata.st_mode)
            or stat.S_IMODE(final_metadata.st_mode) != 0o600
        ):
            raise ValueError("published evidence output contract is invalid")
        os.unlink(temporary_name, dir_fd=parent_descriptor)
        temporary_created = False
        os.fsync(parent_descriptor)
        return inode_identity
    except BaseException as exc:
        if descriptor >= 0:
            os.close(descriptor)
            descriptor = -1
        rollback_failed = False
        if final_link_created and inode_identity is not None:
            rollback_failed = not _unlink_owned_name(
                parent_descriptor,
                relative_path.name,
                *inode_identity,
            )
        if temporary_created and inode_identity is not None:
            if _unlink_owned_name(
                parent_descriptor,
                temporary_name,
                *inode_identity,
            ):
                temporary_created = False
            else:
                rollback_failed = True
        if rollback_failed:
            raise RuntimeError(
                "evidence output failed after publication and rollback was incomplete"
            ) from exc
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_descriptor)


def pack_evidence(repo_root: Path) -> dict[str, object]:
    failure_atlas._reject_symlink_ancestry(repo_root, name="repository root")
    repo_root = repo_root.resolve()
    failure_atlas._prohibited_path(repo_root, name="repository root")
    output_paths = tuple(
        repo_root / path
        for path in (REPORT_PATH, ARCHIVE_PATH, MEMBERS_PATH, BUNDLE_PATH)
    )
    if any(path.exists() or path.is_symlink() for path in output_paths):
        raise FileExistsError("V1.1 evidence outputs already exist")

    source_members = _collect_source_members(repo_root)
    report = _build_report(source_members)
    report_raw = _canonical_bytes(report) + b"\n"
    members = {**source_members, REPORT_PATH: report_raw}
    if len(members) != EXPECTED_EVIDENCE_MEMBER_COUNT:
        raise ValueError("final evidence member denominator drifted")
    tar_raw = _deterministic_tar_bytes(members)
    archive_raw = _compress_zstd(tar_raw)
    members_raw = _manifest_bytes(members)
    archive_sha256 = _sha256_bytes(archive_raw)
    members_sha256 = _sha256_bytes(members_raw)
    bundle_raw = _bundle_bytes(archive_sha256, members_sha256)
    bundle_sha256 = _sha256_bytes(bundle_raw)
    report_sha256 = str(report["report_sha256"])
    _, identity = _verify_bundle_bytes(
        archive_raw=archive_raw,
        members_raw=members_raw,
        bundle_raw=bundle_raw,
        expected_archive_sha256=archive_sha256,
        expected_members_sha256=members_sha256,
        expected_bundle_sha256=bundle_sha256,
        expected_report_sha256=report_sha256,
    )
    expected_identity = {
        "archive_sha256": EXPECTED_EVIDENCE_ARCHIVE_SHA256,
        "member_manifest_sha256": EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256,
        "bundle_sha256": EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256,
        "report_sha256": EXPECTED_REPORT_SHA256,
    }
    if any(identity[key] != value for key, value in expected_identity.items()):
        raise ValueError("generated evidence does not match the reviewed pins")
    created: list[tuple[Path, int, int]] = []
    try:
        for relative, raw in (
            (REPORT_PATH, report_raw),
            (ARCHIVE_PATH, archive_raw),
            (MEMBERS_PATH, members_raw),
            (BUNDLE_PATH, bundle_raw),
        ):
            relative_path = Path(relative)
            device, inode = _write_exclusive_owned(repo_root, relative_path, raw)
            created.append((relative_path, device, inode))
    except BaseException as exc:
        rollback_failed = False
        for relative_path, device, inode in reversed(created):
            try:
                removed = _unlink_owned_output(
                    repo_root,
                    relative_path,
                    device,
                    inode,
                )
            except Exception:
                removed = False
            if not removed:
                rollback_failed = True
        if rollback_failed:
            raise RuntimeError(
                "evidence publication failed and rollback was incomplete"
            ) from exc
        raise
    return identity


def verify_pinned_evidence(
    repo_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    failure_atlas._reject_symlink_ancestry(repo_root, name="repository root")
    repo_root = repo_root.resolve()
    failure_atlas._prohibited_path(repo_root, name="repository root")
    for value, name in (
        (EXPECTED_EVIDENCE_ARCHIVE_SHA256, "pinned archive SHA-256"),
        (EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256, "pinned manifest SHA-256"),
        (EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256, "pinned bundle SHA-256"),
        (EXPECTED_REPORT_SHA256, "pinned report SHA-256"),
    ):
        if not _is_sha256(value):
            raise ValueError(f"{name} has not been reviewed and pinned")
    archive_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(ARCHIVE_PATH),
        maximum=MAX_ARCHIVE_BYTES,
        name="V1.1 evidence archive",
    )[0]
    members_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(MEMBERS_PATH),
        maximum=MAX_MEMBER_MANIFEST_BYTES,
        name="V1.1 member manifest",
    )[0]
    bundle_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(BUNDLE_PATH),
        maximum=MAX_BUNDLE_CHECKSUM_BYTES,
        name="V1.1 bundle sidecar",
    )[0]
    external_report_raw = failure_atlas._bounded_repository_artifact_bytes(
        repo_root,
        Path(REPORT_PATH),
        maximum=MAX_MEMBER_BYTES,
        name="V1.1 external audit report",
    )[0]
    report, identity = _verify_bundle_bytes(
        archive_raw=archive_raw,
        members_raw=members_raw,
        bundle_raw=bundle_raw,
        expected_archive_sha256=EXPECTED_EVIDENCE_ARCHIVE_SHA256,
        expected_members_sha256=EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256,
        expected_bundle_sha256=EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256,
        expected_report_sha256=EXPECTED_REPORT_SHA256,
    )
    if external_report_raw != _canonical_bytes(report) + b"\n":
        raise ValueError("external V1.1 audit contradicts the pinned archive")
    return report, identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("action", choices=("pack", "verify"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.action == "pack":
        identity = pack_evidence(arguments.repo_root)
        print(json.dumps(identity, sort_keys=True))
        return 0
    report, identity = verify_pinned_evidence(arguments.repo_root)
    print(
        json.dumps(
            {
                **identity,
                "decision": report["decision"],
                "clearance_evaluated_candidate_count": report["clearance_telemetry"][
                    "torsion"
                ]["clearance_evaluated_candidate_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify the fixed contaminated-development global-orientation protocol."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_contaminated_development_protocol/1.7.0"
)
FROZEN_GLOBAL_ORIENTATION_GENERATOR_ID = "deterministic_surface_aware_rigid_v2"
BASELINE_LINEAGE_BY_CASE = {
    "5SD5_HWI": "0133959300cee30971f55e3b3a7b043f06008d58e0abd38346c6972a4c038b52",
    "5SIS_JSM": "1e6a11a46b76d9913d167094b4c9479a14ec23e6052b55d501f0e4ad1c330d3a",
    "6M2B_EZO": "9e8fc7c3c9a1aac38c45eb30ed5e9aeb592c7336770ffb526b52cfb30fb87952",
    "6T88_MWQ": "09a8bc0009ed0e05b1d09370eb09f82072190bf8bfa6dee8e16654b4691f19dd",
    "6TW5_9M2": "3a365b3bb51aa2be01bec444ed96a637f4e16ea44dd47e0e25beafb3a7050596",
    "6TW7_NZB": "92a78638bc4d44373142fb855238414bcb6fc5a7675bcf5c1f2bd09e388ee10c",
    "6VTA_AKN": "e8fc07b8a3540d2a3e0aacdc81ca339c71ff57194883bf1b9b4eb57181ed5b76",
    "6WTN_RXT": "4bcc74b03b172a107113981d8f64157682c512934183a617ea2e59fb91f30371",
}
CASE_IDS = (
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
UNCOVERED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
SOURCE_RECEIPT_FIELDS = (
    "case_id",
    "historical_case_source",
    "historical_case_source_receipt_sha256",
    "historical_archive_sha256",
    "historical_member_manifest_sha256",
    "historical_bundle_checksum_sha256",
    "authenticated_problem",
    "receptor_system",
    "receptor_system_sha256",
    "ligand_system",
    "ligand_system_sha256",
    "scorer_context",
    "source_case_member_receipt_sha256",
    "authenticated_input_receipt_sha256",
    "receptor_coordinate_sha256",
    "ligand_coordinate_sha256",
    "ligand_topology_sha256",
    "pocket_declaration_sha256",
    "pocket_center_binary64_hex",
    "pocket_normal_binary64_hex",
    "pocket_radius_angstrom_binary64_hex",
    "pose_validity_config_fingerprint_sha256",
    "preparation_policy_sha256",
    "evaluation_pipeline_sha256",
    "scorer_backend_receipt",
    "scorer_implementation_manifest_sha256",
    "scorer_native_extension_sha256",
    "scorer_backend_receipt_sha256",
    "sanitized_authenticated_input_sha256",
    "generator_source_receipt_sha256",
    "generator_runtime_artifacts_bound",
)
ALLOWED_INPUTS = (
    "prepared_ligand_coordinates",
    "declared_pocket_center",
    "declared_pocket_normal",
    "bounded_receptor_surface_points",
    "frozen_global_orientation_config",
    "source_receipt_sha256",
    "profile_id",
)
FORBIDDEN_INPUTS = (
    "native_pose",
    "reference_pose",
    "rmsd",
    "candidate_score",
    "prior_benchmark_outcome",
    "fresh_holdout_identity",
    "product_routing_state",
)
AUTHORITY_KEYS = (
    "historical_development_execution_authorized",
    "fresh_holdout_execution_authorized",
    "stage0_admission_authority",
    "profile_promotion_authority",
    "product_execution_authorized",
    "customer_pose_emission_authorized",
    "public_or_scientific_claim_authorized",
)
INTERNAL_VALIDITY_SOURCE_SCOPE = {
    "files": [
        "betelgeuze_engine_v2/__init__.py",
        "betelgeuze_engine_v2/docking/validity.py",
        "betelgeuze_engine_v2/stack_round1_hardening.py",
    ],
    "manifest_algorithm": "canonical_sorted_path_sha256_rows/1.0.0",
}
POSEBUSTERS_EVALUATION_SOURCE_SCOPE = {
    "files": [
        "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
        "tools/run_engine_v2_public_redocking_300.py",
    ],
    "manifest_algorithm": "canonical_sorted_path_sha256_rows/1.0.0",
}
SCORER_PYTHON_SOURCE_SCOPE = {
    "files": [],
    "manifest_algorithm": "canonical_sorted_path_sha256_rows/1.0.0",
    "roots": ["betelgeuze_engine_v2"],
}
GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_config/1.0.0"
)


class GlobalOrientationDevelopmentProtocolError(ValueError):
    """Raised when the fixed development protocol fails closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(relative_path: str) -> str:
    path = _REPO_ROOT / relative_path
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"bound authority source is not readable: {relative_path}: {exc}"
        ) from exc


def _source_manifest(
    *,
    roots: tuple[str, ...] = (),
    files: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    paths = set(files)
    for relative_root in roots:
        root = _REPO_ROOT / relative_root
        if not root.is_dir():
            raise GlobalOrientationDevelopmentProtocolError(
                f"bound authority source root is not readable: {relative_root}"
            )
        paths.update(
            path.relative_to(_REPO_ROOT).as_posix()
            for path in root.rglob("*.py")
            if path.is_file()
        )
    return [
        {"path": relative_path, "sha256": _file_sha256(relative_path)}
        for relative_path in sorted(paths)
    ]


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise GlobalOrientationDevelopmentProtocolError(f"{name} must be an object")
    return value


def _reject_duplicate_object_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    for key, value in pairs:
        if key in observed:
            raise GlobalOrientationDevelopmentProtocolError(
                f"duplicate JSON key: {key}"
            )
        observed[key] = value
    return observed


def _load_json_object(path: Path, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except GlobalOrientationDevelopmentProtocolError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"{name} is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GlobalOrientationDevelopmentProtocolError(f"{name} must be a JSON object")
    return payload


def _typed_equal(value: object, expected: object) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            _typed_equal(value[key], expected[key]) for key in expected
        )
    if isinstance(expected, (list, tuple)):
        return len(value) == len(expected) and all(
            _typed_equal(observed, frozen)
            for observed, frozen in zip(value, expected, strict=True)
        )
    return bool(value == expected)


def _exact(value: object, expected: object, *, name: str) -> None:
    if not _typed_equal(value, expected):
        raise GlobalOrientationDevelopmentProtocolError(f"{name} drifted")


def load_protocol(path: Path) -> dict[str, Any]:
    return _load_json_object(path, name="protocol")


def _generator_parameters() -> tuple[str, ...]:
    path = _REPO_ROOT / "betelgeuze_engine_v2/docking/global_orientation.py"
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise GlobalOrientationDevelopmentProtocolError(
            f"generator source is not parseable: {exc}"
        ) from exc
    functions = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "generate_global_orientation_batch"
    ]
    if len(functions) != 1:
        raise GlobalOrientationDevelopmentProtocolError(
            "generator entry point is not unique"
        )
    arguments = functions[0].args
    if arguments.posonlyargs or arguments.vararg or arguments.kwarg:
        raise GlobalOrientationDevelopmentProtocolError(
            "generator signature exposes unsupported parameter forms"
        )
    return tuple(argument.arg for argument in (*arguments.args, *arguments.kwonlyargs))


def _verify_generator_boundary() -> None:
    parameters = _generator_parameters()
    _exact(
        parameters,
        (
            "ligand_coordinates",
            "pocket_center",
            "pocket_normal",
            "receptor_surface_points",
            "config",
            "source_receipt_sha256",
            "profile_id",
        ),
        name="generator signature",
    )
    forbidden_tokens = (
        "native",
        "reference",
        "rmsd",
        "score",
        "benchmark",
        "fresh",
        "product",
    )
    if any(
        token in parameter.lower()
        for parameter in parameters
        for token in forbidden_tokens
    ):
        raise GlobalOrientationDevelopmentProtocolError(
            "generator signature exposes forbidden information"
        )


def _verify_synthetic_contract_binding(
    source_bindings: Mapping[str, Any],
) -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "config/engine_v2_global_orientation_synthetic_contract.json"
    )
    contract = _load_json_object(contract_path, name="synthetic contract")
    projection = dict(contract)
    observed_hash = projection.pop("contract_sha256", None)
    _exact(
        contract.get("schema_id"),
        source_bindings.get("global_orientation_synthetic_contract_schema_id"),
        name="live synthetic contract schema binding",
    )
    _exact(
        observed_hash,
        _sha256(projection),
        name="live synthetic contract self-hash",
    )
    _exact(
        observed_hash,
        source_bindings.get("global_orientation_synthetic_contract_sha256"),
        name="live synthetic contract hash binding",
    )
    algorithm = _mapping(contract.get("algorithm"), name="synthetic algorithm")
    _exact(
        algorithm.get("generator_id"),
        FROZEN_GLOBAL_ORIENTATION_GENERATOR_ID,
        name="synthetic generator identity",
    )


def _verify_phase25_policy_binding(
    source_bindings: Mapping[str, Any],
) -> None:
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "config/engine_v2_phase25_cohort_admission.json"
    )
    policy = _load_json_object(policy_path, name="phase 2.5 policy")
    projection = dict(policy)
    observed_hash = projection.pop("policy_sha256", None)
    _exact(
        policy.get("schema_id"),
        source_bindings.get("phase25_policy_schema_id"),
        name="live phase 2.5 policy schema binding",
    )
    _exact(
        observed_hash,
        _sha256(projection),
        name="live phase 2.5 policy self-hash",
    )
    _exact(
        observed_hash,
        source_bindings.get("phase25_policy_sha256"),
        name="live phase 2.5 policy hash binding",
    )


def _verify_preimport_source_bindings(protocol: Mapping[str, Any]) -> None:
    bindings = _mapping(protocol.get("authority_bindings"), name="authority bindings")
    scorer = _mapping(bindings.get("scorer_v1"), name="ScorerV1 authority binding")
    scorer_manifest = _mapping(
        scorer.get("implementation_manifest"),
        name="ScorerV1 implementation manifest",
    )
    _exact(
        scorer_manifest.get("python_transitive_source_scope"),
        SCORER_PYTHON_SOURCE_SCOPE,
        name="pre-import ScorerV1 source scope",
    )
    _exact(
        scorer_manifest.get("python_transitive_source_manifest_sha256"),
        "440e754f75ce48ac5e4631b051eca066ababec55e618579079db3d155521169a",
        name="pre-import ScorerV1 source identity",
    )
    _exact(
        scorer_manifest.get("python_transitive_source_manifest_sha256"),
        _sha256(
            _source_manifest(
                roots=tuple(SCORER_PYTHON_SOURCE_SCOPE["roots"]),
                files=tuple(SCORER_PYTHON_SOURCE_SCOPE["files"]),
            )
        ),
        name="pre-import ScorerV1 source manifest",
    )


def _verify_authority_bindings(
    protocol: Mapping[str, Any],
) -> None:
    bindings = _mapping(protocol.get("authority_bindings"), name="authority bindings")
    _exact(
        set(bindings),
        {
            "baseline_current_v7",
            "experimental_global_orientation",
            "internal_validity",
            "posebusters",
            "rmsd",
            "scorer_v1",
        },
        name="authority binding key set",
    )

    baseline = _mapping(
        bindings.get("baseline_current_v7"),
        name="baseline authority binding",
    )
    _exact(
        dict(baseline),
        {
            "candidate_lineage_manifest_sha256": (
                "220db66f0b6dde2b4c2cabfa48dbccc2e6bd7d4192e9f93f092364a249327c99"
            ),
            "candidate_lineage_receipt_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_current_v7_lineage/1.0.0"
            ),
            "candidate_lineage_sha256_by_case": BASELINE_LINEAGE_BY_CASE,
            "source_authority_module_path": (
                "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py"
            ),
            "source_authority_module_sha256": (
                "e93774d3e2a93154268ba593bf51032e017dbccf80f5a67dcc432b384fbd8a7f"
            ),
        },
        name="baseline authority binding",
    )
    _exact(
        baseline.get("candidate_lineage_manifest_sha256"),
        _sha256(BASELINE_LINEAGE_BY_CASE),
        name="baseline lineage manifest",
    )

    experimental = _mapping(
        bindings.get("experimental_global_orientation"),
        name="experimental authority binding",
    )
    generator_runtime_artifact_contract = {
        "generator_libm_sha256": None,
        "generator_python_executable_sha256": None,
        "generator_python_shared_library_sha256": None,
        "generator_runtime_fingerprint_sha256": None,
        "runtime_identities_committed": False,
        "unbound_generator_runtime_blocks_execution": True,
    }
    _exact(
        dict(experimental),
        {
            "generator_id": FROZEN_GLOBAL_ORIENTATION_GENERATOR_ID,
            "generator_module_path": (
                "betelgeuze_engine_v2/docking/global_orientation.py"
            ),
            "generator_module_sha256": (
                "9983774745872a6d3e2abf3c8a14dc80c915ad4703dfe3675b58f39aedcd6b61"
            ),
            "runtime_artifact_contract": generator_runtime_artifact_contract,
        },
        name="experimental authority binding",
    )

    internal = _mapping(
        bindings.get("internal_validity"),
        name="internal validity authority binding",
    )
    internal_source_manifest = _source_manifest(
        files=tuple(INTERNAL_VALIDITY_SOURCE_SCOPE["files"]),
    )
    validity_fixed_fields = {
        "schema_id": "betelgeuze.engine_v2_pose_validity_fixed_fields/1.0.0",
        "policy_id": (
            "betelgeuze.engine_v2_pose_validity_policy/public-redocking/1.0.0"
        ),
        "bond_length_tolerance_angstrom": 0.15,
        "ligand_self_clash_angstrom": 0.75,
        "receptor_ligand_clash_angstrom": 0.8,
        "rotation_tolerance": 1.0e-6,
        "chirality_volume_tolerance": 1.0e-8,
        "max_pair_checks": 250_000,
        "max_cross_checks": 1_000_000,
    }
    validity_config_contract = {
        "config_schema_id": "betelgeuze.engine_v2_pose_validity_config/3.0.0",
        "execution_requires_exact_per_case_config_fingerprint": True,
        "fixed_fields": validity_fixed_fields,
        "fixed_fields_sha256": (
            "598a7dbe66b534d94591858b5897c3b30361b80258395458fbf5af933b7aeb43"
        ),
        "per_case_config_fingerprint_sha256_by_case": {},
        "per_case_config_fingerprints_committed": False,
        "per_case_config_fingerprints_source_field": (
            "pose_validity_config_fingerprint_sha256"
        ),
        "pocket_radius_source_field": "pocket_radius_angstrom_binary64_hex",
        "uncommitted_per_case_config_blocks_execution": True,
    }
    _exact(
        dict(internal),
        {
            "config_contract": validity_config_contract,
            "evaluator_implementation_path": (
                "betelgeuze_engine_v2/docking/validity.py"
            ),
            "evaluator_implementation_sha256": (
                "5b1263ddf83deee0c46142be9e8d973bc9af6710d197f20451ab4d5ee996a619"
            ),
            "evaluator_source_manifest_sha256": (
                "5f966c2fca0b1ba43664ac8c1fdef4fd345a5d47829590972ed902df411675fc"
            ),
            "evaluator_source_scope": INTERNAL_VALIDITY_SOURCE_SCOPE,
            "required_check_set_sha256": (
                "dcab24089ac9c88daa53f3faeabd04d71fb819cbbe9f86982d964b657cbc5583"
            ),
        },
        name="internal validity authority binding",
    )
    _exact(
        internal.get("evaluator_source_manifest_sha256"),
        _sha256(internal_source_manifest),
        name="internal validity transitive source manifest",
    )
    _exact(
        validity_config_contract["fixed_fields_sha256"],
        _sha256(validity_fixed_fields),
        name="internal validity fixed configuration",
    )

    posebusters = _mapping(
        bindings.get("posebusters"),
        name="PoseBusters authority binding",
    )
    posebusters_config = {
        "mode": "redock",
        "package_filename": "posebusters-0.3.1-py3-none-any.whl",
        "package_sha256": (
            "a6d1437d0eb3e0fe13ad73b5c4efdc8c0914ceadd904cde55b2a9835bf591a9d"
        ),
        "posebusters_version": "0.3.1",
        "required_check_set_sha256": (
            "3b4797c8eb95f6471f3dce0977b95b83fd0ed2630d6079607609fbcb2c1d8b93"
        ),
    }
    expected_posebusters = {
        **posebusters_config,
        "config_sha256": (
            "1e2013837fc3fbb3334ff5b2e94f029c65f1203f2a2a2abbd7f7d01c008c5533"
        ),
        "evaluation_source_manifest_sha256": (
            "2f843fee77e2d40d70882d2bb959fc828f3806921b915a0e702b1a138cc777bb"
        ),
        "evaluation_source_scope": POSEBUSTERS_EVALUATION_SOURCE_SCOPE,
        "expected_evaluation_pipeline_sha256": (
            "40530119249b792728a70cb5ba65cc9c60cf834e1a744d6987dae75046459922"
        ),
        "implementation_sha256": posebusters_config["package_sha256"],
        "runner_source_path": "tools/run_engine_v2_public_redocking_300.py",
        "runner_source_sha256": (
            "045267dcdbf27cf18a29dee55a95d3cf123b14e857b10c7cb9971b47a8955169"
        ),
    }
    _exact(
        dict(posebusters), expected_posebusters, name="PoseBusters authority binding"
    )
    _exact(
        posebusters.get("config_sha256"),
        _sha256(posebusters_config),
        name="PoseBusters config identity",
    )
    _exact(
        posebusters.get("evaluation_source_manifest_sha256"),
        _sha256(
            _source_manifest(files=tuple(POSEBUSTERS_EVALUATION_SOURCE_SCOPE["files"]))
        ),
        name="PoseBusters evaluation source manifest",
    )

    rmsd = _mapping(bindings.get("rmsd"), name="RMSD authority binding")
    atom_mapping_policy = {
        "complete_bijection_required": True,
        "mapping_direction": "reference_position_to_candidate_position",
        "mapping_scope": "all_ligand_heavy_atoms",
        "mapping_source": "posebusters_redock_report",
    }
    symmetry_policy = {
        "alignment_allowed": False,
        "metric": "direct_heavy_atom_rmsd_angstrom",
        "minimum_over_symmetry_permutations": True,
        "symmetry_mapping_source": "posebusters_redock_report",
    }
    _exact(
        dict(rmsd),
        {
            "atom_mapping_policy": atom_mapping_policy,
            "atom_mapping_sha256": (
                "0ab5a381924ae5a4ab08ca0dd6a0af58b8637d83927c88f04c8c82b2d7ce328c"
            ),
            "config_sha256": expected_posebusters["config_sha256"],
            "implementation_sha256": expected_posebusters["implementation_sha256"],
            "local_metric_module_path": ("betelgeuze_engine_v2/docking/metrics.py"),
            "local_metric_module_sha256": (
                "e47915e80fdec830243f28105bee4f43b7f7b9d92a4ece73826dc29282305df9"
            ),
            "method_id": "posebusters_redock_symmetry_aware_rmsd",
            "symmetry_policy": symmetry_policy,
            "symmetry_policy_sha256": (
                "e29f135b0809fd4fc417899ceaff71b766beb939291a52af06435957e4da833b"
            ),
        },
        name="RMSD authority binding",
    )
    _exact(
        rmsd.get("atom_mapping_sha256"),
        _sha256(atom_mapping_policy),
        name="RMSD atom-mapping identity",
    )
    _exact(
        rmsd.get("symmetry_policy_sha256"),
        _sha256(symmetry_policy),
        name="RMSD symmetry-policy identity",
    )

    scorer = _mapping(bindings.get("scorer_v1"), name="ScorerV1 authority binding")
    native_runtime_artifact_contract = {
        "artifact_identities_committed": False,
        "consumed_qualification_receipt_path": (
            "config/engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.json"
        ),
        "consumed_qualification_receipt_sha256": (
            "80df998dbe52ec51ac29a27511d936d9cb08b0df29e333b35f8a7de513d4da1a"
        ),
        "native_backend_receipt_sha256": None,
        "native_extension_sha256": None,
        "post_qualification_build_boundary_path": (
            "config/engine_v2_native_fixed64_cpu_post_qualification_build_boundary_v1.json"
        ),
        "post_qualification_build_boundary_sha256": (
            "c151fbff4ca2853fa5ed958541a0f215dc5eda41810d17916533c9907f11546c"
        ),
        "qualification_rerun_authorized": False,
        "unbound_native_runtime_blocks_execution": True,
    }
    implementation_manifest = {
        "native_build_configuration_sha256": (
            "6e39e4e07bcb2f9324f242adcf3f48428191b2a91418d34520c6acc1cf046068"
        ),
        "native_profile_id": "engine_v2_native_fixed64_cpu_synthetic_v7",
        "native_profile_sha256": (
            "50c3e609a23e3bf0641a900f71dc360dcadc1a52c3bde66cdfa74b8c1affcd5d"
        ),
        "native_source_manifest_sha256": (
            "ecb009ac228652c6c6cbdefcdd70828ce3d9aeea5a5e31d0fff0246d4d5f932e"
        ),
        "python_module_path": "betelgeuze_engine_v2/docking/scorer_v1.py",
        "python_module_sha256": (
            "138484e4e3f5473c582485316ed8482fc770d0df2aa9f8397e4c91be22d81b75"
        ),
        "python_transitive_source_manifest_sha256": (
            "440e754f75ce48ac5e4631b051eca066ababec55e618579079db3d155521169a"
        ),
        "python_transitive_source_scope": SCORER_PYTHON_SOURCE_SCOPE,
    }
    _exact(
        dict(scorer),
        {
            "backend": "rust_cpu_required",
            "backend_options_fingerprint_sha256": (
                "3e1279f7426288224a1377e9021cc07c3a62115a3ac38534a70871fb8911415f"
            ),
            "config_fingerprint_sha256": (
                "f6592bb681ae1dfad2700291013e04a239c5961687386582ac7c009c5a7de783"
            ),
            "implementation_manifest": implementation_manifest,
            "implementation_source_sha256": (
                "fdcba186efd0cef0d73d7490fa652181379d950eb30b4674e31f4d4b5627328f"
            ),
            "native_runtime_artifact_contract": native_runtime_artifact_contract,
            "terms_schema_id": "betelgeuze.engine_v2_scorer_v1_terms/1.1.0",
        },
        name="ScorerV1 authority binding",
    )
    _exact(
        scorer.get("implementation_source_sha256"),
        _sha256(implementation_manifest),
        name="ScorerV1 implementation manifest",
    )
    _exact(
        implementation_manifest["python_transitive_source_manifest_sha256"],
        _sha256(
            _source_manifest(
                roots=tuple(SCORER_PYTHON_SOURCE_SCOPE["roots"]),
                files=tuple(SCORER_PYTHON_SOURCE_SCOPE["files"]),
            )
        ),
        name="ScorerV1 transitive Python source manifest",
    )
    for path_key, hash_key in (
        (
            "consumed_qualification_receipt_path",
            "consumed_qualification_receipt_sha256",
        ),
        (
            "post_qualification_build_boundary_path",
            "post_qualification_build_boundary_sha256",
        ),
    ):
        relative_path = native_runtime_artifact_contract[path_key]
        _exact(
            native_runtime_artifact_contract[hash_key],
            _file_sha256(relative_path),
            name=f"ScorerV1 native runtime boundary {relative_path}",
        )
    scorer_config_projection = {
        "schema_id": "betelgeuze.engine_v2_scorer_v1_config/1.0.0",
        "algorithm_id": (
            "sparse_typed_lj_charge_hbond_hydrophobic_geometry_torsion_strain/1.0.0"
        ),
        "typed_vdw_weight_binary64_hex": float(1.0).hex(),
        "electrostatics_weight_binary64_hex": float(0.35).hex(),
        "directional_hbond_weight_binary64_hex": float(1.5).hex(),
        "hydrophobic_contact_weight_binary64_hex": float(0.6).hex(),
        "desolvation_weight_binary64_hex": float(0.4).hex(),
        "torsion_energy_weight_binary64_hex": float(0.15).hex(),
        "ligand_strain_weight_binary64_hex": float(0.5).hex(),
        "weak_pocket_prior_weight_binary64_hex": float(0.05).hex(),
        "electrostatic_dielectric_binary64_hex": float(4.0).hex(),
        "pair_cutoff_angstrom_binary64_hex": float(8.0).hex(),
        "hbond_distance_max_angstrom_binary64_hex": float(3.0).hex(),
        "polar_burial_distance_angstrom_binary64_hex": float(4.5).hex(),
        "max_receptor_candidate_pairs": 1_000_000,
        "max_ligand_pair_checks": 250_000,
        "calibrated": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    _exact(
        scorer.get("config_fingerprint_sha256"),
        _sha256(scorer_config_projection),
        name="ScorerV1 config identity",
    )
    _exact(
        scorer.get("backend_options_fingerprint_sha256"),
        _sha256({"thread_count": 1, "max_batch_size": 64}),
        name="ScorerV1 backend options identity",
    )

    source_bindings = (
        (baseline, "source_authority_module_path", "source_authority_module_sha256"),
        (experimental, "generator_module_path", "generator_module_sha256"),
        (internal, "evaluator_implementation_path", "evaluator_implementation_sha256"),
        (posebusters, "runner_source_path", "runner_source_sha256"),
        (rmsd, "local_metric_module_path", "local_metric_module_sha256"),
        (
            _mapping(scorer.get("implementation_manifest"), name="scorer manifest"),
            "python_module_path",
            "python_module_sha256",
        ),
    )
    for binding, path_key, hash_key in source_bindings:
        relative_path = binding.get(path_key)
        if type(relative_path) is not str:
            raise GlobalOrientationDevelopmentProtocolError(
                f"authority source path is invalid: {path_key}"
            )
        _exact(
            binding.get(hash_key),
            _file_sha256(relative_path),
            name=f"live authority source {relative_path}",
        )


def verify_protocol(protocol: Mapping[str, Any]) -> str:
    expected_top_keys = {
        "arm_contract",
        "authority",
        "authority_bindings",
        "cohort",
        "decision",
        "execution_gate",
        "information_boundary",
        "metrics",
        "protocol_role",
        "protocol_sha256",
        "schema_id",
        "shared_execution_contract",
        "source_bindings",
        "status",
    }
    _exact(set(protocol), expected_top_keys, name="protocol key set")
    _exact(protocol.get("schema_id"), SCHEMA_ID, name="protocol schema")
    _exact(
        protocol.get("status"),
        "frozen_protocol_only_execution_blocked",
        name="protocol status",
    )
    _exact(
        protocol.get("protocol_role"),
        "fixed_historical_contaminated_development_global_orientation_ab",
        name="protocol role",
    )
    projection = dict(protocol)
    observed_hash = projection.pop("protocol_sha256", None)
    expected_hash = _sha256(projection)
    _exact(observed_hash, expected_hash, name="protocol self-hash")

    cohort = _mapping(protocol.get("cohort"), name="cohort")
    _exact(
        set(cohort),
        {
            "baseline_recovered_case_ids",
            "historical_case_count",
            "historical_case_ids",
            "historical_case_ids_sha256",
            "preparation_failure_case_ids",
            "previously_uncovered_case_count",
            "previously_uncovered_case_ids",
            "scored_case_count",
        },
        name="cohort key set",
    )
    _exact(
        tuple(cohort.get("historical_case_ids", ())), CASE_IDS, name="historical cohort"
    )
    _exact(cohort.get("historical_case_count"), 9, name="historical count")
    _exact(
        cohort.get("historical_case_ids_sha256"),
        _sha256(list(CASE_IDS)),
        name="historical cohort hash",
    )
    _exact(cohort.get("scored_case_count"), 8, name="scored count")
    _exact(
        tuple(cohort.get("preparation_failure_case_ids", ())),
        ("6M73_FNR",),
        name="preparation-failure roster",
    )
    _exact(
        tuple(cohort.get("baseline_recovered_case_ids", ())),
        ("6T88_MWQ",),
        name="baseline-recovered roster",
    )
    _exact(
        tuple(cohort.get("previously_uncovered_case_ids", ())),
        UNCOVERED_CASE_IDS,
        name="previously-uncovered roster",
    )
    _exact(
        cohort.get("previously_uncovered_case_count"),
        7,
        name="previously-uncovered count",
    )

    sources = _mapping(protocol.get("source_bindings"), name="source_bindings")
    expected_sources = {
        "source_commit_git_sha1": "754bebb9ddc2fbffdaca5d4143ff515c3b38c032",
        "historical_archive_sha256": "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc",
        "historical_member_manifest_sha256": "7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21",
        "historical_bundle_checksum_sha256": "6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9",
        "phase25_policy_schema_id": "betelgeuze.engine_v2_phase25_cohort_admission/1.3.0",
        "phase25_policy_sha256": "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211",
        "global_orientation_synthetic_contract_schema_id": "betelgeuze.engine_v2_global_orientation_synthetic_contract/2.0.0",
        "global_orientation_synthetic_contract_sha256": "02fa37a94f3c1719f5e7b5b808c71d053e313b018ef9bfa7d904869c2ab1dad0",
        "case_source_receipt_schema_id": "betelgeuze.engine_v2_global_orientation_"
        "development_case_source/1.0.0",
        "preparation_failure_receipt_schema_id": (
            "betelgeuze.engine_v2_global_orientation_development_"
            "preparation_failure/1.0.0"
        ),
        "historical_failure_authority_schema_id": (
            "betelgeuze.engine_v2_global_orientation_historical_failure_authority/1.0.0"
        ),
        "lineage_slot_receipt_schema_id": (
            "betelgeuze.engine_v2_global_orientation_development_lineage_slot/1.0.0"
        ),
        "arm_lineage_receipt_schema_id": (
            "betelgeuze.engine_v2_global_orientation_development_arm_lineage/1.0.0"
        ),
        "observation_slot_receipt_schema_id": (
            "betelgeuze.engine_v2_global_orientation_development_observation_slot/1.0.0"
        ),
        "partial_evidence_schema_id": (
            "betelgeuze.engine_v2_global_orientation_development_partial_evidence/1.0.0"
        ),
        "arm_observations_receipt_schema_id": (
            "betelgeuze.engine_v2_global_orientation_development_arm_observations/1.0.0"
        ),
        "development_evidence_contract_module_path": (
            "betelgeuze_engine_v2/benchmark/global_orientation_development_contracts.py"
        ),
        "development_evidence_contract_module_sha256": (
            "832a5b40257919a1dbe3114cf06a0c5d696bd1e9faf6ee2294a7474d99c8c4aa"
        ),
        "contract_types_implemented": True,
        "exact_case_source_receipt_required": True,
        "source_receipt_required_fields": list(SOURCE_RECEIPT_FIELDS),
        "source_receipts_committed": False,
        "source_receipt_absence_blocks_execution": True,
    }
    _exact(dict(sources), expected_sources, name="source bindings")
    _exact(
        sources.get("development_evidence_contract_module_sha256"),
        _file_sha256(str(sources.get("development_evidence_contract_module_path"))),
        name="live development evidence contract source",
    )
    _verify_phase25_policy_binding(sources)
    _verify_synthetic_contract_binding(sources)
    _verify_preimport_source_bindings(protocol)
    _verify_authority_bindings(protocol)

    information = _mapping(
        protocol.get("information_boundary"), name="information_boundary"
    )
    _exact(
        set(information),
        {
            "generator_allowed_inputs",
            "generator_forbidden_inputs",
            "post_result_candidate_allocation_forbidden",
            "reference_pose_consumed_only_after_candidate_generation",
        },
        name="information boundary key set",
    )
    _exact(
        tuple(information.get("generator_allowed_inputs", ())),
        ALLOWED_INPUTS,
        name="generator allowed inputs",
    )
    _exact(
        tuple(information.get("generator_forbidden_inputs", ())),
        FORBIDDEN_INPUTS,
        name="generator forbidden inputs",
    )
    _exact(
        information.get("reference_pose_consumed_only_after_candidate_generation"),
        True,
        name="reference-pose boundary",
    )
    _exact(
        information.get("post_result_candidate_allocation_forbidden"),
        True,
        name="post-result allocation boundary",
    )
    _verify_generator_boundary()

    shared = _mapping(
        protocol.get("shared_execution_contract"),
        name="shared_execution_contract",
    )
    _exact(
        dict(shared),
        {
            "preparation_policy": "exact_source_paired_current_v7_preparation",
            "conformer_authority": "same_prepared_ligand_for_both_arms",
            "scorer_backend": "rust_cpu_required",
            "scorer_terms_schema_id": "betelgeuze.engine_v2_scorer_v1_terms/1.1.0",
            "posebusters_version": "0.3.1",
            "posebusters_check_count": 22,
            "posebusters_evidence_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_"
                "posebusters_evidence/2.0.0"
            ),
            "posebusters_full_check_map_required": True,
            "posebusters_required_check_set_sha256": (
                "3b4797c8eb95f6471f3dce0977b95b83fd0ed2630d6079607609fbcb2c1d8b93"
            ),
            "internal_validity_required_check_set_sha256": (
                "dcab24089ac9c88daa53f3faeabd04d71fb819cbbe9f86982d964b657cbc5583"
            ),
            "rmsd_contract": "symmetry_aware_heavy_atom_rmsd_angstrom",
            "rmsd_threshold_angstrom": 2.0,
            "seed": 2026080601,
            "cpu_count": 1,
            "native_scorer_threads": 1,
            "torch_intraop_threads": 1,
            "torch_interop_threads": 1,
        },
        name="shared execution contract",
    )

    arms = _mapping(protocol.get("arm_contract"), name="arm_contract")
    _exact(
        set(arms),
        {
            "arm_ids",
            "baseline",
            "candidate_slots_per_scored_case_per_arm",
            "denominators_identical_required",
            "expected_scored_candidate_rows_combined",
            "expected_scored_candidate_rows_per_arm",
            "experimental",
            "failed_candidate_slots_retained",
            "failed_preparation_rows_retained",
            "same_candidate_budget_required",
            "same_pocket_required",
            "same_prepared_ligand_required",
            "same_scorer_required",
        },
        name="arm contract key set",
    )
    _exact(
        tuple(arms.get("arm_ids", ())),
        ("baseline_current_v7", "experimental_global_orientation_v1"),
        name="arm identities",
    )
    _exact(
        arms.get("baseline"),
        {"proposal_authority": "current_v7", "candidate_slot_count": 64},
        name="baseline arm",
    )
    experimental = _mapping(arms.get("experimental"), name="experimental arm")
    _exact(
        set(experimental),
        {
            "candidate_slot_count",
            "candidate_slot_formula",
            "generator_config",
            "profile_id",
            "proposal_authority",
        },
        name="experimental arm key set",
    )
    _exact(
        experimental.get("proposal_authority"),
        FROZEN_GLOBAL_ORIENTATION_GENERATOR_ID,
        name="experimental proposal authority",
    )
    _exact(
        experimental.get("profile_id"),
        FROZEN_GLOBAL_ORIENTATION_GENERATOR_ID,
        name="experimental profile identity",
    )
    config = _mapping(
        experimental.get("generator_config"),
        name="experimental generator config",
    )
    _exact(
        dict(config),
        {
            "schema_id": GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID,
            "orientation_count": 8,
            "translation_shell_radii": [1.5],
            "translation_points_per_shell": 7,
            "minimum_receptor_distance": 1.1,
        },
        name="experimental generator config",
    )
    candidate_slot_count = config["orientation_count"] * (
        1
        + len(config["translation_shell_radii"])
        * config["translation_points_per_shell"]
    )
    _exact(candidate_slot_count, 64, name="experimental denominator")
    _exact(
        experimental.get("candidate_slot_count"),
        64,
        name="experimental candidate count",
    )
    _exact(
        experimental.get("candidate_slot_formula"),
        "orientation_count*(1+translation_shell_count*translation_points_per_shell)",
        name="candidate formula",
    )
    for key, expected in {
        "candidate_slots_per_scored_case_per_arm": 64,
        "expected_scored_candidate_rows_per_arm": 512,
        "expected_scored_candidate_rows_combined": 1024,
        "denominators_identical_required": True,
        "failed_candidate_slots_retained": True,
        "failed_preparation_rows_retained": True,
        "same_prepared_ligand_required": True,
        "same_pocket_required": True,
        "same_scorer_required": True,
        "same_candidate_budget_required": True,
    }.items():
        _exact(arms.get(key), expected, name=f"arm_contract.{key}")

    metrics = _mapping(protocol.get("metrics"), name="metrics")
    _exact(
        set(metrics),
        {
            "arm_metrics_evaluator_implemented",
            "arm_metrics_module_path",
            "arm_metrics_module_sha256",
            "arm_metrics_require_exact_arm_observations",
            "arm_metrics_schema_id",
            "failure_classes",
            "full_observation_rederivation_required",
            "required_per_case",
            "source_geometry_rederivation_required",
            "summary_rederived_from_complete_case_receipts",
            "top_k",
        },
        name="metrics key set",
    )
    _exact(
        metrics.get("arm_metrics_evaluator_implemented"),
        True,
        name="arm metrics evaluator implementation state",
    )
    _exact(
        metrics.get("arm_metrics_schema_id"),
        "betelgeuze.engine_v2_global_orientation_development_arm_metrics/1.0.0",
        name="arm metrics schema",
    )
    _exact(
        metrics.get("arm_metrics_module_path"),
        "betelgeuze_engine_v2/benchmark/global_orientation_development_metrics.py",
        name="arm metrics module path",
    )
    _exact(
        metrics.get("arm_metrics_module_sha256"),
        "2648a5788d7cbc7079db736ae6317a8d71f39b11dd820e8f8335b6e331167d75",
        name="arm metrics module identity",
    )
    _exact(
        metrics.get("arm_metrics_module_sha256"),
        _file_sha256(str(metrics.get("arm_metrics_module_path"))),
        name="live arm metrics source",
    )
    _exact(
        metrics.get("arm_metrics_require_exact_arm_observations"),
        True,
        name="arm metrics exact-observation requirement",
    )
    _exact(
        tuple(metrics.get("failure_classes", ())),
        ("success", "proposal_failure", "validity_failure", "ranking_failure"),
        name="failure classes",
    )
    _exact(tuple(metrics.get("top_k", ())), (1, 5), name="Top-K")
    _exact(
        tuple(metrics.get("required_per_case", ())),
        (
            "proposal_oracle_rmsd",
            "valid_proposal_oracle_rmsd",
            "ranked_top1_oracle_rmsd",
            "ranked_top5_oracle_rmsd",
            "selected_top1_rmsd",
            "selection_regret",
            "generated_candidate_count",
            "accepted_candidate_count",
            "rejected_candidate_count",
            "unscored_candidate_count",
            "failure_class",
        ),
        name="required per-case metrics",
    )
    for key in (
        "full_observation_rederivation_required",
        "source_geometry_rederivation_required",
        "summary_rederived_from_complete_case_receipts",
    ):
        _exact(metrics.get(key), True, name=f"metrics.{key}")

    decision = _mapping(protocol.get("decision"), name="decision")
    _exact(
        set(decision),
        {
            "decision_evaluator_implemented",
            "go_criteria_all",
            "go_effect",
            "go_receipt_emission_authorized",
            "go_requires_all_invariants",
            "hard_no_go_any",
            "invariants_all",
            "no_go_effect",
            "required_private_evidence_instances",
            "result_cannot_change_protocol",
        },
        name="decision key set",
    )
    _exact(
        decision.get("decision_evaluator_implemented"),
        False,
        name="decision evaluator implementation state",
    )
    _exact(
        decision.get("go_receipt_emission_authorized"),
        False,
        name="Go receipt authority",
    )
    _exact(
        tuple(decision.get("required_private_evidence_instances", ())),
        (
            "case_source_receipt_with_ligand_topology_pocket_preparation_and_"
            "rederived_receptor_surface_identities",
            "baseline_candidate_lineage_bound_to_all_64_observation_slots",
            "experimental_candidate_lineage_bound_to_all_64_observation_slots",
            "failure_complete_observation_slots_with_explicit_unscored_state",
        ),
        name="required private evidence instances",
    )
    _exact(
        decision.get("go_requires_all_invariants"),
        True,
        name="Go invariant requirement",
    )
    _exact(
        decision.get("result_cannot_change_protocol"), True, name="result independence"
    )
    _exact(
        tuple(decision.get("invariants_all", ())),
        (
            "complete_source_receipts_for_all_nine_cases",
            "identical_failure_complete_64_slot_denominators",
            "no_reference_or_result_dependent_generator_input",
            "no_preparation_failure_regression",
            "baseline_recovered_case_reproduced",
            "no_baseline_recovered_case_regression",
            "complete_source_and_observation_rederivation",
        ),
        name="decision invariants",
    )
    _exact(
        tuple(decision.get("go_criteria_all", ())),
        (
            "valid_proposal_oracle_recovery_in_at_least_2_of_7_"
            "previously_uncovered_cases",
            "no_increase_in_invalid_selected_top1_count",
        ),
        name="Go criteria",
    )
    _exact(
        tuple(decision.get("hard_no_go_any", ())),
        (
            "evaluator_or_required_private_evidence_absent",
            "required_invariant_failed",
            "zero_new_previously_uncovered_valid_proposal_recoveries",
            "baseline_recovered_case_regression",
            "candidate_denominator_or_source_binding_drift",
        ),
        name="hard No-Go criteria",
    )
    _exact(
        decision.get("go_effect"),
        "permit_separate_review_of_global_orientation_development_followup_only",
        name="Go effect",
    )
    _exact(
        decision.get("no_go_effect"),
        "retain_synthetic_only_global_orientation_and_"
        "close_molecular_execution_request",
        name="No-Go effect",
    )

    gate = _mapping(protocol.get("execution_gate"), name="execution_gate")
    _exact(
        dict(gate),
        {
            "pr245_reviewed_terminal_state_required": True,
            "separate_execution_authority_required": True,
            "operator_reservation_required": True,
            "actual_execution_authorized": False,
            "output_root": ".betelgeuze/engine_v2_global_orientation_"
            "contaminated_development",
            "owner_only_directory_mode_octal": "0700",
            "owner_only_receipt_mode_octal": "0600",
        },
        name="execution gate",
    )
    authority = _mapping(protocol.get("authority"), name="authority")
    _exact(set(authority), set(AUTHORITY_KEYS), name="authority key set")
    if any(authority.get(key) is not False for key in AUTHORITY_KEYS):
        raise GlobalOrientationDevelopmentProtocolError(
            "all execution, product, promotion, and claim authority must remain false"
        )
    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=(
            _REPO_ROOT
            / "config/engine_v2_global_orientation_contaminated_development.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    print(verify_protocol(load_protocol(arguments.protocol)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Second-round public-evaluator hardening for the Engine v2 stacked head.

The public redocking evaluator now:

* chooses one exact graph mapping and uses that same mapping for direct RMSD,
  reference geometry, chirality, and all bounded validity checks;
* distinguishes expected per-case failures from evaluator implementation defects;
* emits report schema v2 with explicit input-binding mode, authenticated input
  identities, derivation policy, evaluation scope, and execution-evidence state.

These receipts remain operational evidence.  Scientific validation, benchmark
validation, product qualification, customer execution, and claim safety remain
false.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sys
from types import MappingProxyType
from typing import Mapping, Sequence

import torch

from betelgeuze_engine_v2.stack_round1_hardening import (
    PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
)


STACK_ROUND2_EVALUATOR_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round2_evaluator/1.0.0"
)
PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_evaluation_report/2.0.0"
)
PUBLIC_BENCHMARK_EVALUATION_SCOPE = "known_reference_pocket_redocking"
PREPARED_INPUT_BINDING_MODE = "prepared_non_authoritative"
AUTHENTICATED_INPUT_BINDING_MODE = "authenticated_raw_artifacts"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class PublicBenchmarkEvaluationInternalError(RuntimeError):
    """The evaluator implementation or an internal invariant failed."""


def _install_public_evaluator_v2() -> None:
    from betelgeuze_engine_v2 import benchmark as benchmark_package
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.benchmark import public_evaluator as module
    from betelgeuze_engine_v2.benchmark import public_evaluator_authenticated as authenticated

    if getattr(module, "_BETELGEUZE_ROUND2_EVALUATOR", False):
        return

    row_class = module.PublicBenchmarkEvaluationRow

    @dataclass(frozen=True, slots=True)
    class PublicBenchmarkEvaluationReport:
        protocol_sha256: str
        materialization_manifest_sha256: str
        engine_commit: str
        environment_fingerprint_sha256: str
        command: tuple[str, ...]
        seed: int
        rows: tuple[object, ...]
        legacy_materialization_direction_present: bool
        report_sha256: str
        input_binding_mode: str = PREPARED_INPUT_BINDING_MODE
        authenticated_case_input_sha256s: tuple[tuple[str, str], ...] = ()
        derivation_policy_sha256: str = ""
        execution_receipt_sha256: str = ""
        authoritative_input_binding: bool = False
        execution_identity_authoritative: bool = False
        evaluation_scope: str = PUBLIC_BENCHMARK_EVALUATION_SCOPE
        evaluator_integrity_complete: bool = True
        internal_error_count: int = 0

        def __post_init__(self) -> None:
            if self.input_binding_mode not in {
                PREPARED_INPUT_BINDING_MODE,
                AUTHENTICATED_INPUT_BINDING_MODE,
            }:
                raise module.PublicBenchmarkEvaluationError(
                    "unsupported public evaluation input-binding mode"
                )
            rows = tuple(self.rows)
            if not rows or not all(isinstance(row, row_class) for row in rows):
                raise module.PublicBenchmarkEvaluationError(
                    "public evaluation report rows are invalid"
                )
            object.__setattr__(self, "rows", rows)
            identities = tuple(
                sorted(
                    (str(case_id), module._require_sha256(digest, name="authenticated input"))
                    for case_id, digest in self.authenticated_case_input_sha256s
                )
            )
            if len({case_id for case_id, _ in identities}) != len(identities):
                raise module.PublicBenchmarkEvaluationError(
                    "authenticated case-input identities are duplicated"
                )
            object.__setattr__(self, "authenticated_case_input_sha256s", identities)
            derivation = str(self.derivation_policy_sha256 or "")
            execution = str(self.execution_receipt_sha256 or "")
            if derivation:
                derivation = module._require_sha256(
                    derivation, name="derivation_policy_sha256"
                )
            if execution:
                execution = module._require_sha256(
                    execution, name="execution_receipt_sha256"
                )
            object.__setattr__(self, "derivation_policy_sha256", derivation)
            object.__setattr__(self, "execution_receipt_sha256", execution)
            if self.input_binding_mode == AUTHENTICATED_INPUT_BINDING_MODE:
                if not self.authoritative_input_binding or not identities or not derivation:
                    raise module.PublicBenchmarkEvaluationError(
                        "authenticated reports require authoritative input identities"
                    )
            elif self.authoritative_input_binding or identities or derivation:
                raise module.PublicBenchmarkEvaluationError(
                    "prepared reports cannot assert authoritative input binding"
                )
            if self.execution_identity_authoritative and not execution:
                raise module.PublicBenchmarkEvaluationError(
                    "execution authority requires an execution receipt"
                )
            if self.evaluation_scope != PUBLIC_BENCHMARK_EVALUATION_SCOPE:
                raise module.PublicBenchmarkEvaluationError(
                    "public evaluator scope is not the frozen redocking scope"
                )
            if self.evaluator_integrity_complete is not True or self.internal_error_count != 0:
                raise module.PublicBenchmarkEvaluationError(
                    "successful public reports require complete evaluator integrity"
                )

        @property
        def success_count(self) -> int:
            return sum(row.succeeded for row in self.rows)

        @property
        def failure_count(self) -> int:
            return len(self.rows) - self.success_count

        @property
        def primary_success_count(self) -> int:
            return sum(row.primary_pose_success is True for row in self.rows)

        @property
        def primary_success_rate_all_cases(self) -> float:
            return self.primary_success_count / len(self.rows)

        def _projection(self) -> dict[str, object]:
            return {
                "schema_id": PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID,
                "evaluator_id": module.PUBLIC_BENCHMARK_EVALUATOR_ID,
                "protocol_sha256": self.protocol_sha256,
                "materialization_manifest_sha256": (
                    self.materialization_manifest_sha256
                ),
                "engine_commit": self.engine_commit,
                "environment_fingerprint_sha256": (
                    self.environment_fingerprint_sha256
                ),
                "command": list(self.command),
                "seed": self.seed,
                "input_binding_mode": self.input_binding_mode,
                "authoritative_input_binding": self.authoritative_input_binding,
                "authenticated_case_input_sha256s": {
                    case_id: digest
                    for case_id, digest in self.authenticated_case_input_sha256s
                },
                "derivation_policy_sha256": self.derivation_policy_sha256,
                "execution_receipt_sha256": self.execution_receipt_sha256,
                "execution_identity_authoritative": (
                    self.execution_identity_authoritative
                ),
                "evaluation_scope": self.evaluation_scope,
                "evaluator_integrity_complete": self.evaluator_integrity_complete,
                "internal_error_count": self.internal_error_count,
                "case_count": len(self.rows),
                "evaluation_success_count": self.success_count,
                "evaluation_failure_count": self.failure_count,
                "primary_success_count": self.primary_success_count,
                "primary_success_rate_all_cases": (
                    self.primary_success_rate_all_cases
                ),
                "failure_rows_retained": True,
                "denominator": "all_materialization_manifest_cases",
                "rmsd_method": (
                    "minimum_direct_receptor_frame_heavy_atom_rmsd_with_"
                    "validity_evaluated_under_the_same_exact_mapping"
                ),
                "rmsd_threshold_angstrom": (
                    module.PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM
                ),
                "symmetry_permutation_direction": (
                    module.PUBLIC_BENCHMARK_METRIC_PERMUTATION_DIRECTION
                ),
                "legacy_materialization_direction_present": (
                    self.legacy_materialization_direction_present
                ),
                "network_fetch_performed": False,
                "ligand_only_alignment_performed": False,
                "scientifically_validated": False,
                "benchmark_validated": False,
                "product_qualified": False,
                "customer_execution_enabled": False,
                "claim_safe": False,
                "rows": [row.to_dict() for row in self.rows],
            }

        def to_dict(self) -> dict[str, object]:
            return {**self._projection(), "report_sha256": self.report_sha256}

    def mapping_pairs(case: object) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
        full_mappings = module.exact_graph_isomorphisms(
            case.reference_system,
            case.ligand_identity_seed_system,
        )
        if not full_mappings:
            raise module.PublicBenchmarkEvaluationError(
                "reference and ligand seed are not exact labeled-graph isomorphs"
            )
        reference_heavy = module._heavy_indices(case.reference_system)
        seed_heavy = module._heavy_indices(case.ligand_identity_seed_system)
        seed_heavy_position = {
            atom_index: position for position, atom_index in enumerate(seed_heavy)
        }
        pairs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
        for raw_mapping in full_mappings:
            full_mapping = tuple(int(value) for value in raw_mapping)
            heavy_mapping = tuple(
                seed_heavy_position[int(full_mapping[reference_atom])]
                for reference_atom in reference_heavy
            )
            if sorted(heavy_mapping) != list(range(len(seed_heavy))):
                raise module.PublicBenchmarkEvaluationError(
                    "reference-to-seed heavy-atom mapping is not a bijection"
                )
            pairs.append((full_mapping, heavy_mapping))
        result = tuple(sorted(set(pairs)))
        materialized = module._materialized_metric_mappings(case.materialization)
        if tuple(sorted(heavy for _, heavy in result)) != materialized:
            raise module.PublicBenchmarkEvaluationError(
                "materialized symmetry mappings disagree with exact graph matching"
            )
        return result

    def evaluate_under_mapping(
        case: object,
        *,
        full_mapping: tuple[int, ...],
        heavy_mapping: tuple[int, ...],
        mapping_index: int,
    ) -> tuple[float, object, dict[str, object]]:
        reference_coordinates = module._frame(
            case.reference_system, name="reference_system"
        )
        candidate_coordinates = module._frame(
            case.candidate_system, name="candidate_system"
        )
        reference_heavy = reference_coordinates[
            torch.tensor(
                module._heavy_indices(case.reference_system),
                dtype=torch.long,
            )
        ]
        candidate_heavy = candidate_coordinates[
            torch.tensor(
                module._heavy_indices(case.ligand_identity_seed_system),
                dtype=torch.long,
            )
        ]
        rmsd = module.symmetry_aware_rmsd(
            reference_heavy,
            candidate_heavy,
            permutations=(heavy_mapping,),
            align=False,
        ).rmsd_angstrom
        ordered_reference = module._reference_in_seed_order(
            reference_coordinates,
            case.ligand_identity_seed_system.atom_count,
            full_mapping,
        )
        problem = module.DockingProblemIdentity(
            receptor_system_sha256=case.receptor_system_sha256,
            ligand_system_sha256=module.canonical_system_sha256(
                case.ligand_identity_seed_system
            ),
            pocket_definition_sha256=module._pocket_definition_sha256(
                case.pocket_center,
                case.pocket_radius_angstrom,
            ),
            coordinate_frame_id="public-receptor-frame-v1",
        )
        atom_count = case.ligand_identity_seed_system.atom_count
        search_space = module.TorsionSearchSpace(
            local_offsets=torch.zeros((atom_count, 3), dtype=torch.float64),
            parent=torch.full((atom_count,), -1, dtype=torch.long),
            local_axes=torch.tensor(
                [[0.0, 0.0, 1.0]] * atom_count,
                dtype=torch.float64,
            ),
            rotatable_mask=torch.zeros(atom_count, dtype=torch.bool),
            root_positions=ordered_reference,
        )
        baseline = module.generate_bounded_docking_proposals(
            search_space,
            module.DockingBudget(
                candidate_count=1,
                top_k=1,
                max_torsions=0,
                translation_radius_angstrom=0.0,
                seed=0,
            ),
            problem=problem,
        )[0]
        proposal = baseline.with_refined_coordinates(
            candidate_coordinates,
            refiner_id="offline-public-benchmark-evaluator",
            refiner_version="2.0.0",
        )
        validity_context = module.PoseValidityContext(
            problem_fingerprint_sha256=problem.fingerprint_sha256,
            reference_coordinates=ordered_reference,
            bond_pairs=module._bond_pairs(case.ligand_identity_seed_system),
            excluded_nonbonded_pairs=case.excluded_nonbonded_pairs,
            receptor_coordinates=case.receptor_coordinates,
            pocket_center=case.pocket_center,
            chirality_centers=case.chirality_centers,
            config=module.PoseValidityConfig(
                pocket_radius_angstrom=case.pocket_radius_angstrom,
                policy_id=PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
            ),
        )
        validity = validity_context.evaluate(proposal)
        validity_document = validity.to_dict()
        validity_document.update(
            {
                "selected_symmetry_mapping_index": mapping_index,
                "selected_full_reference_to_seed_mapping": list(full_mapping),
                "selected_heavy_reference_to_candidate_mapping": list(
                    heavy_mapping
                ),
                "validity_policy_sha256": (
                    validity_context.config.fingerprint_sha256
                ),
            }
        )
        return float(rmsd), validity, validity_document

    def evaluate_case(ordinal: int, case: object) -> object:
        evaluated: list[tuple[float, int, object, dict[str, object]]] = []
        for mapping_index, (full_mapping, heavy_mapping) in enumerate(
            mapping_pairs(case)
        ):
            rmsd, validity, validity_document = evaluate_under_mapping(
                case,
                full_mapping=full_mapping,
                heavy_mapping=heavy_mapping,
                mapping_index=mapping_index,
            )
            evaluated.append((rmsd, mapping_index, validity, validity_document))
        rmsd, _, validity, validity_document = min(
            evaluated,
            key=lambda row: (row[0], row[1]),
        )
        primary = bool(
            rmsd <= module.PUBLIC_BENCHMARK_PRIMARY_RMSD_THRESHOLD_ANGSTROM
            and validity.valid
        )
        return row_class(
            ordinal=ordinal,
            case_id=case.case_id,
            status="success",
            materialization_sha256=case.materialization.materialization_sha256,
            candidate_artifact_sha256=case.candidate_artifact_sha256,
            rmsd_angstrom=rmsd,
            bounded_pose_valid=bool(validity.valid),
            primary_pose_success=primary,
            pose_validity=MappingProxyType(validity_document),
        )

    expected_case_exceptions = (
        module.PublicBenchmarkEvaluationError,
        docking.DockingProposalError,
        docking.PoseMetricError,
        docking.PoseValidityError,
    )

    def run_offline_public_benchmark_evaluation(
        materialization_manifest: object,
        case_inputs: Mapping[str, object],
        *,
        engine_commit: str,
        environment_fingerprint_sha256: str,
        command: Sequence[str],
        seed: int,
        input_binding_mode: str = PREPARED_INPUT_BINDING_MODE,
        authenticated_case_input_sha256s: Mapping[str, str] | None = None,
        derivation_policy_sha256: str = "",
        execution_receipt_sha256: str = "",
    ) -> object:
        if not isinstance(
            materialization_manifest,
            module.PublicBenchmarkMaterializationManifest,
        ):
            raise TypeError(
                "materialization_manifest must be PublicBenchmarkMaterializationManifest"
            )
        if not isinstance(case_inputs, Mapping):
            raise TypeError("case_inputs must be a mapping")
        if len(materialization_manifest.rows) > module.MAX_PUBLIC_EVALUATION_CASES:
            raise module.PublicBenchmarkEvaluationError(
                "materialization manifest exceeds the evaluator case bound"
            )
        expected_case_ids = {
            row.case_id for row in materialization_manifest.rows
        }
        unexpected = set(case_inputs) - expected_case_ids
        if unexpected:
            raise module.PublicBenchmarkEvaluationError(
                "case_inputs contains cases outside the materialization manifest"
            )
        commit = module._require_commit(engine_commit, name="engine_commit")
        environment = module._require_sha256(
            environment_fingerprint_sha256,
            name="environment_fingerprint_sha256",
        )
        argv = tuple(str(value) for value in command)
        if not argv or any(not value for value in argv):
            raise module.PublicBenchmarkEvaluationError(
                "command must be non-empty"
            )
        if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
            raise module.PublicBenchmarkEvaluationError(
                "seed must be in [0,2**63-1]"
            )

        rows: list[object] = []
        legacy_direction = False
        for materialization_row in materialization_manifest.rows:
            materialization = materialization_row.materialization
            if materialization is not None:
                legacy_direction = legacy_direction or (
                    "symmetry_permutation_direction"
                    not in materialization.to_dict()
                )
            try:
                if not materialization_row.succeeded or materialization is None:
                    raise module.PublicBenchmarkEvaluationError(
                        "materialization row failed and cannot be evaluated"
                    )
                case = case_inputs.get(materialization_row.case_id)
                if case is None:
                    raise module.PublicBenchmarkEvaluationError(
                        "predicted pose input is missing for the materialized case"
                    )
                if (
                    case.materialization.materialization_sha256
                    != materialization.materialization_sha256
                ):
                    raise module.PublicBenchmarkEvaluationError(
                        "evaluation input is cross-wired to another materialization"
                    )
                rows.append(evaluate_case(materialization_row.ordinal, case))
            except expected_case_exceptions as exc:
                receipt = module.failure_receipt(
                    exc,
                    public_message="public benchmark case evaluation failed",
                )
                case = case_inputs.get(materialization_row.case_id)
                rows.append(
                    row_class(
                        ordinal=materialization_row.ordinal,
                        case_id=materialization_row.case_id,
                        status="failure",
                        materialization_sha256=(
                            ""
                            if materialization is None
                            else materialization.materialization_sha256
                        ),
                        candidate_artifact_sha256=(
                            "" if case is None else case.candidate_artifact_sha256
                        ),
                        error_code=receipt.public_error_code,
                        error_message=receipt.public_message,
                        private_error_sha256=receipt.private_error_sha256,
                        private_error_byte_length=(
                            receipt.private_error_byte_length
                        ),
                    )
                )
            except Exception as exc:
                raise PublicBenchmarkEvaluationInternalError(
                    "public benchmark evaluator internal invariant failed"
                ) from exc

        identity_rows = tuple(
            sorted((authenticated_case_input_sha256s or {}).items())
        )
        authoritative = input_binding_mode == AUTHENTICATED_INPUT_BINDING_MODE
        # A bare digest is only a cross-link.  Authority requires verification
        # of the receipt payload, signer, execution context, and this exact run.
        execution_authoritative = False
        provisional = PublicBenchmarkEvaluationReport(
            protocol_sha256=materialization_manifest.protocol_sha256,
            materialization_manifest_sha256=(
                materialization_manifest.manifest_sha256
            ),
            engine_commit=commit,
            environment_fingerprint_sha256=environment,
            command=argv,
            seed=seed,
            rows=tuple(rows),
            legacy_materialization_direction_present=legacy_direction,
            report_sha256="0" * 64,
            input_binding_mode=input_binding_mode,
            authenticated_case_input_sha256s=identity_rows,
            derivation_policy_sha256=derivation_policy_sha256,
            execution_receipt_sha256=execution_receipt_sha256,
            authoritative_input_binding=authoritative,
            execution_identity_authoritative=execution_authoritative,
        )
        report_sha256 = module._sha256(provisional._projection())
        return PublicBenchmarkEvaluationReport(
            protocol_sha256=provisional.protocol_sha256,
            materialization_manifest_sha256=(
                provisional.materialization_manifest_sha256
            ),
            engine_commit=provisional.engine_commit,
            environment_fingerprint_sha256=(
                provisional.environment_fingerprint_sha256
            ),
            command=provisional.command,
            seed=provisional.seed,
            rows=provisional.rows,
            legacy_materialization_direction_present=(
                provisional.legacy_materialization_direction_present
            ),
            report_sha256=report_sha256,
            input_binding_mode=provisional.input_binding_mode,
            authenticated_case_input_sha256s=(
                provisional.authenticated_case_input_sha256s
            ),
            derivation_policy_sha256=provisional.derivation_policy_sha256,
            execution_receipt_sha256=provisional.execution_receipt_sha256,
            authoritative_input_binding=provisional.authoritative_input_binding,
            execution_identity_authoritative=(
                provisional.execution_identity_authoritative
            ),
        )

    def run_authenticated_offline_public_benchmark_evaluation(
        materialization_manifest: object,
        case_inputs: Mapping[str, object],
        *,
        engine_commit: str,
        environment_fingerprint_sha256: str,
        command: Sequence[str],
        seed: int,
        execution_receipt_sha256: str = "",
    ) -> object:
        if not isinstance(case_inputs, Mapping):
            raise TypeError("case_inputs must be a mapping")
        prepared: dict[str, object] = {}
        identities: dict[str, str] = {}
        for case_id, row in case_inputs.items():
            if not isinstance(
                case_id, str
            ) or not isinstance(
                row, authenticated.AuthenticatedPublicBenchmarkCaseInput
            ):
                raise authenticated.AuthenticatedPublicBenchmarkInputError(
                    "authenticated evaluator inputs are invalid"
                )
            if case_id != row.case_id:
                raise authenticated.AuthenticatedPublicBenchmarkInputError(
                    "authenticated evaluator input key is cross-wired"
                )
            prepared[case_id] = row.prepared_input
            identities[case_id] = row.input_sha256
        policy = authenticated.authenticated_public_benchmark_derivation_policy_document()
        return run_offline_public_benchmark_evaluation(
            materialization_manifest,
            MappingProxyType(prepared),
            engine_commit=engine_commit,
            environment_fingerprint_sha256=environment_fingerprint_sha256,
            command=command,
            seed=seed,
            input_binding_mode=AUTHENTICATED_INPUT_BINDING_MODE,
            authenticated_case_input_sha256s=identities,
            derivation_policy_sha256=str(policy["policy_sha256"]),
            execution_receipt_sha256=execution_receipt_sha256,
        )

    module.PUBLIC_BENCHMARK_EVALUATION_REPORT_SCHEMA_ID = (
        PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID
    )
    module.PublicBenchmarkEvaluationReport = PublicBenchmarkEvaluationReport
    module.PublicBenchmarkEvaluationInternalError = (
        PublicBenchmarkEvaluationInternalError
    )
    module._evaluate_case = evaluate_case
    module.run_offline_public_benchmark_evaluation = (
        run_offline_public_benchmark_evaluation
    )
    authenticated._run_prepared_evaluation = (
        run_offline_public_benchmark_evaluation
    )
    authenticated.run_authenticated_offline_public_benchmark_evaluation = (
        run_authenticated_offline_public_benchmark_evaluation
    )
    benchmark_package.PUBLIC_BENCHMARK_EVALUATION_REPORT_SCHEMA_ID = (
        PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID
    )
    benchmark_package.PublicBenchmarkEvaluationReport = (
        PublicBenchmarkEvaluationReport
    )
    benchmark_package.PublicBenchmarkEvaluationInternalError = (
        PublicBenchmarkEvaluationInternalError
    )
    benchmark_package.run_prepared_offline_public_benchmark_evaluation = (
        run_offline_public_benchmark_evaluation
    )
    benchmark_package.run_authenticated_offline_public_benchmark_evaluation = (
        run_authenticated_offline_public_benchmark_evaluation
    )
    benchmark_package.run_offline_public_benchmark_evaluation = (
        run_authenticated_offline_public_benchmark_evaluation
    )
    module._BETELGEUZE_ROUND2_EVALUATOR = True


def install_stack_round2_evaluator() -> str:
    marker = "_betelgeuze_stack_round2_evaluator_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing
    _install_public_evaluator_v2()
    receipt = _sha256(
        {
            "schema_id": STACK_ROUND2_EVALUATOR_SCHEMA_ID,
            "same_mapping_rmsd_and_validity": True,
            "expected_case_failures_separated_from_internal_defects": True,
            "report_schema_id": (
                PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID
            ),
            "evaluation_scope": PUBLIC_BENCHMARK_EVALUATION_SCOPE,
            "authenticated_input_identities_retained": True,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "AUTHENTICATED_INPUT_BINDING_MODE",
    "PREPARED_INPUT_BINDING_MODE",
    "PUBLIC_BENCHMARK_EVALUATION_REPORT_V2_SCHEMA_ID",
    "PUBLIC_BENCHMARK_EVALUATION_SCOPE",
    "PublicBenchmarkEvaluationInternalError",
    "STACK_ROUND2_EVALUATOR_SCHEMA_ID",
    "install_stack_round2_evaluator",
]

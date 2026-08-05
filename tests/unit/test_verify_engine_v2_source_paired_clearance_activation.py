from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    SourcePairedClearanceActivationEvidenceError,
    SourcePairedClearanceArmRankingReceiptV1,
)
from tools.verify_engine_v2_source_paired_clearance_activation import (
    EXPECTED_POLICY_SHA256,
    verify_policy,
)


_ROOT = Path(__file__).resolve().parents[2]


def _policy() -> dict[str, object]:
    return json.loads(
        (_ROOT / "config/engine_v2_source_paired_clearance_activation.json").read_text(
            encoding="utf-8"
        )
    )


def _rehash(policy: dict[str, object]) -> None:
    projection = dict(policy)
    projection.pop("policy_sha256", None)
    raw = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    policy["policy_sha256"] = hashlib.sha256(raw).hexdigest()


def test_tracked_activation_policy_is_valid() -> None:
    policy = _policy()
    assert policy["policy_sha256"] == EXPECTED_POLICY_SHA256
    verify_policy(policy)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("historical_ab_execution_authorized", True),
        ("generic_runner_cli_wired", True),
        ("fresh_holdout_execution_authorized", True),
        ("product_path_wired", True),
    ),
)
def test_execution_boundary_cannot_be_opened(field: str, value: bool) -> None:
    policy = copy.deepcopy(_policy())
    execution = policy["execution_boundary"]
    assert isinstance(execution, dict)
    execution[field] = value
    _rehash(policy)

    with pytest.raises(ValueError, match=field):
        verify_policy(policy)


def test_bool_as_int_cannot_bypass_execution_boundary() -> None:
    policy = copy.deepcopy(_policy())
    execution = policy["execution_boundary"]
    assert isinstance(execution, dict)
    execution["historical_ab_execution_authorized"] = 0
    _rehash(policy)

    with pytest.raises(ValueError, match="historical_ab_execution_authorized"):
        verify_policy(policy)


def test_incomplete_historical_terms_cannot_be_admitted() -> None:
    policy = copy.deepcopy(_policy())
    evidence = policy["evidence_requirements"]
    assert isinstance(evidence, dict)
    evidence["historical_archive_without_full_terms_accepted"] = True
    _rehash(policy)

    with pytest.raises(ValueError, match="evidence requirements"):
        verify_policy(policy)


def test_rank_semantics_cannot_change() -> None:
    policy = copy.deepcopy(_policy())
    evidence = policy["evidence_requirements"]
    assert isinstance(evidence, dict)
    evidence["rank_order"] = ["result_dependent_rank"]
    _rehash(policy)

    with pytest.raises(ValueError, match="evidence requirements"):
        verify_policy(policy)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("activated_state_independent_rederivation_required", False),
        ("all_allocated_targets_required", False),
        (
            "authenticated_geometry_independent_clearance_rederivation_required",
            False,
        ),
        ("authenticated_torsion_move_replay_required", False),
        ("case_source_frozen_archive_member_authority_required", False),
        ("changed_slot_set_equals_selected_target_set", False),
        ("current_v7_candidate_full_64_slot_lineage_required", False),
        ("exact_snapshot_runtime_type_required", False),
        ("full_internal_validity_context_and_pose_binding_required", False),
        ("full_posebusters_check_map_required", False),
        ("proposal_receipt_full_64_slot_lineage_required", False),
        ("retained_target_scientific_projection_equality_required", False),
        ("rmsd_reference_atom_mapping_symmetry_binding_required", False),
        ("scorer_authority_bound_to_authenticated_input_required", False),
        ("candidate_denominator_per_scored_case", 512),
    ),
)
def test_activation_evidence_guards_cannot_be_weakened(
    field: str,
    value: object,
) -> None:
    policy = copy.deepcopy(_policy())
    evidence = policy["evidence_requirements"]
    assert isinstance(evidence, dict)
    evidence[field] = value
    _rehash(policy)

    with pytest.raises(ValueError, match=field):
        verify_policy(policy)


def test_posebusters_check_set_cannot_be_truncated() -> None:
    policy = copy.deepcopy(_policy())
    evidence = policy["evidence_requirements"]
    assert isinstance(evidence, dict)
    names = evidence["posebusters_required_check_names"]
    assert isinstance(names, list)
    names.pop()
    _rehash(policy)

    with pytest.raises(ValueError, match="posebusters_required_check_names"):
        verify_policy(policy)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "proposal_receipt_schema_id",
            "betelgeuze.engine_v2_source_paired_torsion_rescue_proposal_receipt/9.0.0",
        ),
        ("historical_v11_archive_sha256", "0" * 64),
        ("historical_v11_member_manifest_sha256", "1" * 64),
        ("historical_case_ids_sha256", "2" * 64),
        ("historical_case_source_authority_sha256", "3" * 64),
        ("internal_validity_required_check_set_sha256", "4" * 64),
        ("posebusters_required_check_set_sha256", "5" * 64),
    ),
)
def test_source_and_validity_dependencies_cannot_be_replaced(
    field: str,
    value: str,
) -> None:
    policy = copy.deepcopy(_policy())
    dependencies = policy["frozen_dependencies"]
    assert isinstance(dependencies, dict)
    dependencies[field] = value
    _rehash(policy)

    with pytest.raises(ValueError, match=field):
        verify_policy(policy)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "snapshot_schema_id",
            "betelgeuze.engine_v2_source_paired_torsion_rescue_activation_snapshot/1.0.0",
        ),
        (
            "activation_receipt_schema_id",
            "betelgeuze.engine_v2_source_paired_clearance_selection_activation_receipt/1.0.0",
        ),
        (
            "posebusters_evidence_schema_id",
            "betelgeuze.engine_v2_source_paired_clearance_posebusters_evidence/1.0.0",
        ),
        (
            "current_v7_lineage_receipt_schema_id",
            "betelgeuze.engine_v2_source_paired_clearance_current_v7_lineage/0.9.0",
        ),
    ),
)
def test_receipt_contract_versions_cannot_be_downgraded(
    field: str,
    value: str,
) -> None:
    policy = copy.deepcopy(_policy())
    contract = policy["activation_contract"]
    assert isinstance(contract, dict)
    contract[field] = value
    _rehash(policy)

    with pytest.raises(ValueError, match=field):
        verify_policy(policy)


@pytest.mark.parametrize(
    "required_input",
    (
        "source_case_member_receipt_sha256",
        "authenticated_input_receipt_payload",
        "validity_context_payload",
        "receptor_coordinates",
        "authenticated_receptor_atom_indices",
        "vdw_contact_policy_payload",
        "current_v7_candidate_lineage_receipt",
        "current_v7_candidate_lineage_sha256",
        "current_v7_proposal_state",
        "source_v11_receipt_per_candidate",
        "source_proposal_receipt_payload",
        "v6_baseline_torsion_angles",
        "optimized_torsion_angles",
        "v6_baseline_torsion_metadata_sha256",
        "optimized_torsion_metadata_sha256",
    ),
)
def test_required_input_lineage_cannot_be_removed(required_input: str) -> None:
    policy = copy.deepcopy(_policy())
    evidence = policy["evidence_requirements"]
    assert isinstance(evidence, dict)
    inputs = evidence["required_activation_inputs"]
    assert isinstance(inputs, list)
    inputs.remove(required_input)
    _rehash(policy)

    with pytest.raises(ValueError, match="required_activation_inputs"):
        verify_policy(policy)


def test_unknown_policy_field_is_rejected_even_when_resealed() -> None:
    policy = copy.deepcopy(_policy())
    policy["result_materialization_command"] = "disabled"
    _rehash(policy)

    with pytest.raises(ValueError, match="top-level keys"):
        verify_policy(policy)


def test_policy_identity_cannot_be_replaced_by_a_valid_self_hash() -> None:
    policy = copy.deepcopy(_policy())
    policy["status"] = "implemented_but_locally_resealed"
    _rehash(policy)

    with pytest.raises(ValueError, match="status"):
        verify_policy(policy)


def _complete_activation_evidence(monkeypatch: pytest.MonkeyPatch):
    fixtures = runpy.run_path(
        str(Path(__file__).with_name("test_source_paired_clearance_activation_evidence.py"))
    )
    evidence_module = fixtures["activation_evidence_module"]
    synthetic_authority: dict[str, dict[str, str]] = {}
    monkeypatch.setattr(
        evidence_module,
        "_FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE",
        synthetic_authority,
    )
    monkeypatch.setattr(
        evidence_module,
        "_frozen_case_source_authority",
        synthetic_authority.get,
    )
    return fixtures, fixtures["_complete_activation_evidence"]()


def _reuse_pose_artifact(row, pose_artifact_sha256: str):
    return replace(
        row,
        pose_artifact_sha256=pose_artifact_sha256,
        internal_validity=replace(
            row.internal_validity,
            pose_artifact_sha256=pose_artifact_sha256,
        ),
        posebusters=replace(
            row.posebusters,
            pose_artifact_sha256=pose_artifact_sha256,
        ),
        rmsd=replace(
            row.rmsd,
            pose_artifact_sha256=pose_artifact_sha256,
        ),
    )


def test_arm_rejects_one_pose_artifact_bound_to_distinct_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, evidence = _complete_activation_evidence(monkeypatch)
    rows = list(evidence["baseline"].candidate_rows)
    assert rows[0].coordinate_sha256 != rows[1].coordinate_sha256
    rows[1] = _reuse_pose_artifact(rows[1], rows[0].pose_artifact_sha256)

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="pose artifact",
    ):
        SourcePairedClearanceArmRankingReceiptV1(
            arm="baseline_current_v7",
            candidate_rows=rows,
        )


def test_outer_rejects_cross_arm_pose_artifact_reuse_after_coordinate_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures, evidence = _complete_activation_evidence(monkeypatch)
    target = evidence["target"]
    baseline = evidence["baseline"].candidate_rows[target]
    experimental_rows = list(evidence["experimental"].candidate_rows)
    experimental = experimental_rows[target]
    assert baseline.coordinate_sha256 != experimental.coordinate_sha256
    experimental_rows[target] = _reuse_pose_artifact(
        experimental,
        baseline.pose_artifact_sha256,
    )
    experimental_arm = SourcePairedClearanceArmRankingReceiptV1(
        arm="experimental_clearance_shadow",
        candidate_rows=experimental_rows,
    )

    with pytest.raises(
        SourcePairedClearanceActivationEvidenceError,
        match="pose artifact",
    ):
        fixtures["_outer"](
            evidence,
            experimental=experimental_arm,
        )

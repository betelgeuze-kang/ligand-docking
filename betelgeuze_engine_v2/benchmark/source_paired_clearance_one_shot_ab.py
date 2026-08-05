"""Atomic authority for the single historical source-paired clearance A/B.

This module authorizes only the exact contaminated-development comparison frozen
by ``config/engine_v2_source_paired_clearance_one_shot_ab.json``. It does not
materialize molecular inputs, execute docking, access the fresh holdout, promote
an algorithm profile, or authorize product/customer use.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence


POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_policy/1.0.0"
)
RESERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_reservation/1.0.0"
)
RUN_START_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_run_start/1.0.0"
)
VERDICT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_verdict/1.0.0"
)
EXPECTED_POLICY_SHA256 = (
    "f9e5ff44a95361df3394b316ad071966d2a23e45d8de395428ac29ef4fd5a0a5"
)
EXPECTED_PHASE25_POLICY_SHA256 = (
    "67910559ec02790cb59fbf41648ca9aff2134cff960292d7ad1acc4caf546cfa"
)
EXPECTED_ACTIVATION_POLICY_SHA256 = (
    "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
)
EXPECTED_CLEARANCE_POLICY_SHA256 = (
    "e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad"
)
EXPECTED_OUTPUT_ROOT = Path(
    ".betelgeuze/engine_v2_source_paired_clearance_one_shot_ab"
)
EXPECTED_RESERVATION_FILENAME = "execution-reservation.json"
EXPECTED_RUN_START_FILENAME = "run-start.json"
EXPECTED_RESULT_FILENAME = "result.json"
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
EXPECTED_UNCOVERED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_GO_CRITERIA = (
    "new_exact_valid_candidate_in_previously_uncovered_case",
    "proposal_oracle_recovery_at_least_2_of_8",
    "invalid_top1_at_most_4_of_8",
)
EXPECTED_INVARIANTS = (
    "no_preparation_failure_regression",
    "no_top1_or_top5_recovery_regression",
    "candidate_denominator_512_per_arm",
    "source_control_preserved",
    "score_term_semantics_fully_verified",
    "no_result_dependent_allocation",
)
EXPECTED_NO_GO_CRITERIA = (
    "shadow_eligible_candidate_without_new_case_recovery",
    "no_exact_valid_case_increase",
    "no_invalid_top1_reduction",
    "existing_recovery_regression",
    "selected_state_remains_penetrating_without_posebusters_validity_change",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


class OneShotABAuthorityError(ValueError):
    """Raised when one-shot authority or evidence fails closed."""


@dataclass(frozen=True, slots=True)
class OneShotABDecision:
    authorized: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OneShotABVerdictInputs:
    preparation_failure_case_ids: tuple[str, ...]
    baseline_top1_recovery_case_ids: tuple[str, ...]
    experimental_top1_recovery_case_ids: tuple[str, ...]
    baseline_top5_recovery_case_ids: tuple[str, ...]
    experimental_top5_recovery_case_ids: tuple[str, ...]
    baseline_exact_valid_case_ids: tuple[str, ...]
    experimental_exact_valid_case_ids: tuple[str, ...]
    baseline_proposal_oracle_case_ids: tuple[str, ...]
    experimental_proposal_oracle_case_ids: tuple[str, ...]
    baseline_invalid_top1_case_ids: tuple[str, ...]
    experimental_invalid_top1_case_ids: tuple[str, ...]
    baseline_candidate_count: int
    experimental_candidate_count: int
    source_control_preserved: bool
    score_term_semantics_fully_verified: bool
    result_dependent_allocation_observed: bool
    shadow_eligible_candidate_count: int
    selected_penetrating_without_validity_change_count: int


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def sha256_payload(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise OneShotABAuthorityError(f"{name} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], keys: set[str], *, name: str) -> None:
    if set(value) != keys:
        raise OneShotABAuthorityError(f"{name} key set is invalid")


def _exact_string_sequence(
    value: object,
    expected: Sequence[str],
    *,
    name: str,
) -> None:
    if not isinstance(value, list) or tuple(value) != tuple(expected):
        raise OneShotABAuthorityError(f"{name} must equal the frozen ordered values")


def verify_self_hash(
    document: Mapping[str, Any],
    *,
    hash_field: str,
    name: str,
) -> None:
    projection = dict(document)
    observed = projection.pop(hash_field, None)
    if not _is_sha256(observed) or observed != sha256_payload(projection):
        raise OneShotABAuthorityError(f"{name} self-hash is invalid")


def load_json_document(path: Path, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OneShotABAuthorityError(f"{name} is not readable canonical JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise OneShotABAuthorityError(f"{name} must be a JSON object")
    return payload


def verify_one_shot_policy(
    policy: Mapping[str, Any],
    *,
    phase25_policy: Mapping[str, Any],
    activation_policy: Mapping[str, Any],
) -> None:
    _exact_keys(
        policy,
        {
            "arm_contract",
            "authority",
            "cohort",
            "decision",
            "execution",
            "policy_role",
            "policy_sha256",
            "schema_id",
            "source_bindings",
            "status",
        },
        name="one-shot policy",
    )
    if policy.get("schema_id") != POLICY_SCHEMA_ID:
        raise OneShotABAuthorityError("one-shot policy schema_id is invalid")
    verify_self_hash(policy, hash_field="policy_sha256", name="one-shot policy")
    if policy.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("one-shot policy identity is not frozen")
    if policy.get("status") != "authorized_pending_external_operator_reservation":
        raise OneShotABAuthorityError("one-shot policy status is invalid")
    if (
        policy.get("policy_role")
        != "historical_contaminated_development_single_execution_authority"
    ):
        raise OneShotABAuthorityError("one-shot policy role is invalid")

    authority = _mapping(policy.get("authority"), name="authority")
    if authority.get("historical_ab_execution_authorized") is not True:
        raise OneShotABAuthorityError("historical A/B execution is not authorized")
    if authority.get("historical_result_materialization_authorized") is not True:
        raise OneShotABAuthorityError("historical result materialization is not authorized")
    if authority.get("maximum_lifetime_run_count") != 1:
        raise OneShotABAuthorityError("maximum lifetime run count must equal one")
    for forbidden in (
        "fresh_holdout_execution_authorized",
        "stage0_admission_authority",
        "profile_promotion_authority",
        "selection_policy_authority",
        "product_execution_authorized",
        "customer_pose_emission_authorized",
        "public_or_scientific_claim_authorized",
    ):
        if authority.get(forbidden) is not False:
            raise OneShotABAuthorityError(f"{forbidden} must remain false")

    source = _mapping(policy.get("source_bindings"), name="source_bindings")
    if source.get("phase25_cohort_policy_sha256") != EXPECTED_PHASE25_POLICY_SHA256:
        raise OneShotABAuthorityError("Phase 2.5 cohort policy identity drifted")
    if source.get("activation_policy_sha256") != EXPECTED_ACTIVATION_POLICY_SHA256:
        raise OneShotABAuthorityError("activation policy identity drifted")
    if source.get("clearance_selection_policy_sha256") != EXPECTED_CLEARANCE_POLICY_SHA256:
        raise OneShotABAuthorityError("clearance selection policy identity drifted")
    if source.get("baseline_profile_id") != "current_v7":
        raise OneShotABAuthorityError("baseline profile identity drifted")
    if (
        source.get("experimental_profile_id")
        != "current_v7_with_only_predeclared_clearance_shadow_selected_states_replaced"
    ):
        raise OneShotABAuthorityError("experimental profile identity drifted")
    if source.get("required_scorer_backend") != "rust_cpu_required":
        raise OneShotABAuthorityError("Rust CPU scorer is required")
    if source.get("source_control_required") is not True:
        raise OneShotABAuthorityError("paired source controls are required")

    if phase25_policy.get("schema_id") != source.get("phase25_cohort_policy_schema_id"):
        raise OneShotABAuthorityError("Phase 2.5 schema cross-wire")
    if phase25_policy.get("policy_sha256") != EXPECTED_PHASE25_POLICY_SHA256:
        raise OneShotABAuthorityError("Phase 2.5 policy cross-wire")
    if activation_policy.get("schema_id") != source.get("activation_policy_schema_id"):
        raise OneShotABAuthorityError("activation schema cross-wire")
    if activation_policy.get("policy_sha256") != EXPECTED_ACTIVATION_POLICY_SHA256:
        raise OneShotABAuthorityError("activation policy cross-wire")

    cohort = _mapping(policy.get("cohort"), name="cohort")
    _exact_string_sequence(
        cohort.get("historical_case_ids"), EXPECTED_CASE_IDS, name="historical case IDs"
    )
    _exact_string_sequence(
        cohort.get("previously_uncovered_case_ids"),
        EXPECTED_UNCOVERED_CASE_IDS,
        name="uncovered case IDs",
    )
    _exact_string_sequence(
        cohort.get("preparation_failure_case_ids"),
        ("6M73_FNR",),
        name="preparation-failure case IDs",
    )
    _exact_string_sequence(
        cohort.get("baseline_recovery_case_ids"),
        ("6T88_MWQ",),
        name="baseline recovery case IDs",
    )
    if cohort.get("historical_case_count") != 9 or cohort.get("scored_case_count") != 8:
        raise OneShotABAuthorityError("historical cohort denominator drifted")
    if cohort.get("candidate_slots_per_scored_case_per_arm") != 64:
        raise OneShotABAuthorityError("candidate-slot denominator drifted")
    if cohort.get("arm_count") != 2 or cohort.get("expected_scored_candidate_rows") != 1024:
        raise OneShotABAuthorityError("two-arm candidate denominator drifted")
    if cohort.get("historical_case_ids_sha256") != sha256_payload(list(EXPECTED_CASE_IDS)):
        raise OneShotABAuthorityError("historical case roster hash is invalid")

    arm_contract = _mapping(policy.get("arm_contract"), name="arm_contract")
    if arm_contract.get("baseline_candidate_authority") != "current_v7":
        raise OneShotABAuthorityError("baseline candidate authority drifted")
    if (
        arm_contract.get("experimental_candidate_authority")
        != "activation_snapshot_selected_or_current_v7"
    ):
        raise OneShotABAuthorityError("experimental candidate authority drifted")
    for required_true in (
        "allocated_target_exactly_once_required",
        "candidate_denominator_failure_complete",
        "changed_slots_equal_selected_targets_required",
        "complete_scorer_v1_terms_required",
        "internal_validity_required",
        "non_target_rows_identical_required",
        "selection_sealed_before_scoring",
        "stable_rank_required",
        "symmetry_aware_rmsd_required",
        "top1_top5_required",
    ):
        if arm_contract.get(required_true) is not True:
            raise OneShotABAuthorityError(f"{required_true} must remain true")
    if arm_contract.get("posebusters_check_count") != 22:
        raise OneShotABAuthorityError("PoseBusters check count must equal 22")

    execution = _mapping(policy.get("execution"), name="execution")
    for field in (
        "cpu_count",
        "torch_intraop_threads",
        "torch_interop_threads",
        "native_scorer_threads",
    ):
        if execution.get(field) != 1:
            raise OneShotABAuthorityError(f"{field} must equal one")
    if execution.get("seed") != 2026073000:
        raise OneShotABAuthorityError("execution seed drifted")
    if execution.get("external_engine_invocation") is not False:
        raise OneShotABAuthorityError("external engine invocation must remain false")
    if execution.get("atomic_no_overwrite") is not True:
        raise OneShotABAuthorityError("atomic no-overwrite is required")
    if execution.get("preexisting_reservation_rejected") is not True:
        raise OneShotABAuthorityError("preexisting reservations must be rejected")
    if execution.get("preexisting_result_rejected") is not True:
        raise OneShotABAuthorityError("preexisting results must be rejected")
    if execution.get("owner_only_mode_octal") != "0600":
        raise OneShotABAuthorityError("owner-only receipt mode must remain 0600")
    if execution.get("output_root") != EXPECTED_OUTPUT_ROOT.as_posix():
        raise OneShotABAuthorityError("durable output root drifted")
    if execution.get("reservation_filename") != EXPECTED_RESERVATION_FILENAME:
        raise OneShotABAuthorityError("reservation filename drifted")
    if execution.get("run_start_filename") != EXPECTED_RUN_START_FILENAME:
        raise OneShotABAuthorityError("run-start filename drifted")
    if execution.get("result_filename") != EXPECTED_RESULT_FILENAME:
        raise OneShotABAuthorityError("result filename drifted")

    decision = _mapping(policy.get("decision"), name="decision")
    _exact_string_sequence(decision.get("go_criteria_any"), EXPECTED_GO_CRITERIA, name="Go criteria")
    _exact_string_sequence(decision.get("invariants_all"), EXPECTED_INVARIANTS, name="invariants")
    _exact_string_sequence(
        decision.get("no_go_criteria_any"), EXPECTED_NO_GO_CRITERIA, name="No-Go criteria"
    )
    if decision.get("go_requires_all_invariants") is not True:
        raise OneShotABAuthorityError("Go must require all invariants")
    if decision.get("go_requires_any_primary_criterion") is not True:
        raise OneShotABAuthorityError("Go must require a primary criterion")
    if decision.get("no_go_trigger_precedence") is not True:
        raise OneShotABAuthorityError("No-Go trigger precedence must remain enabled")


def resolve_output_root(policy: Mapping[str, Any], *, repository_root: Path) -> Path:
    execution = _mapping(policy.get("execution"), name="execution")
    configured = Path(str(execution.get("output_root", "")))
    if configured != EXPECTED_OUTPUT_ROOT or configured.is_absolute():
        raise OneShotABAuthorityError("one-shot output root is not the frozen path")
    if any(part in {"", ".", ".."} for part in configured.parts):
        raise OneShotABAuthorityError("one-shot output root contains an unsafe component")
    root = repository_root.resolve(strict=True)
    output = (root / configured).resolve(strict=False)
    if root not in output.parents:
        raise OneShotABAuthorityError("one-shot output root escapes the repository root")
    return output


def _prepare_owner_only_directory(path: Path, *, repository_root: Path) -> None:
    root = repository_root.resolve(strict=True)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise OneShotABAuthorityError("output path is outside the repository root") from exc
    current = root
    for component in relative.parts:
        current = current / component
        if current.exists() or current.is_symlink():
            if current.is_symlink() or not current.is_dir():
                raise OneShotABAuthorityError("output path contains a symlink or non-directory")
            mode = stat.S_IMODE(current.stat().st_mode)
            if mode != 0o700:
                raise OneShotABAuthorityError(
                    f"existing evidence directory {current.name} must have mode 0700"
                )
        else:
            current.mkdir(mode=0o700)
            if stat.S_IMODE(current.stat().st_mode) != 0o700:
                raise OneShotABAuthorityError(
                    f"created evidence directory {current.name} is not mode 0700"
                )


def authorization_decision(
    policy: Mapping[str, Any],
    *,
    phase25_policy: Mapping[str, Any],
    activation_policy: Mapping[str, Any],
    repository_root: Path,
) -> OneShotABDecision:
    blockers: list[str] = []
    try:
        verify_one_shot_policy(
            policy,
            phase25_policy=phase25_policy,
            activation_policy=activation_policy,
        )
        output_root = resolve_output_root(policy, repository_root=repository_root)
    except (OneShotABAuthorityError, OSError) as exc:
        blockers.append(str(exc))
        return OneShotABDecision(authorized=False, blockers=tuple(blockers))

    execution = _mapping(policy.get("execution"), name="execution")
    reservation = output_root / str(execution.get("reservation_filename", ""))
    run_start = output_root / str(execution.get("run_start_filename", ""))
    result = output_root / str(execution.get("result_filename", ""))
    if reservation.exists() or reservation.is_symlink():
        blockers.append("one_shot_reservation_already_exists")
    if run_start.exists() or run_start.is_symlink():
        blockers.append("one_shot_run_start_already_exists")
    if result.exists() or result.is_symlink():
        blockers.append("one_shot_result_already_exists")
    return OneShotABDecision(authorized=not blockers, blockers=tuple(blockers))


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OneShotABAuthorityError("short write while creating evidence receipt")
        view = view[written:]


def _write_exclusive_json(
    path: Path,
    payload: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    _prepare_owner_only_directory(path.parent, repository_root=repository_root)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise OneShotABAuthorityError(f"refusing to overwrite {path.name}") from exc
    try:
        encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        _write_all(descriptor, encoded.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise OneShotABAuthorityError(f"{path.name} is not owner-only")


def reserve_one_shot_execution(
    *,
    policy: Mapping[str, Any],
    phase25_policy: Mapping[str, Any],
    activation_policy: Mapping[str, Any],
    repository_root: Path,
    source_commit_git_sha1: str,
    operator_id: str,
    execution_environment_sha256: str,
) -> dict[str, Any]:
    decision = authorization_decision(
        policy,
        phase25_policy=phase25_policy,
        activation_policy=activation_policy,
        repository_root=repository_root,
    )
    if not decision.authorized:
        raise OneShotABAuthorityError(";".join(decision.blockers))
    if _GIT_SHA1_RE.fullmatch(source_commit_git_sha1) is None:
        raise OneShotABAuthorityError("source commit must be a lowercase Git SHA-1")
    if not operator_id or operator_id.strip() != operator_id:
        raise OneShotABAuthorityError("operator_id is invalid")
    if not _is_sha256(execution_environment_sha256):
        raise OneShotABAuthorityError("execution environment SHA-256 is invalid")

    output_root = resolve_output_root(policy, repository_root=repository_root)
    execution = _mapping(policy["execution"], name="execution")
    receipt: dict[str, Any] = {
        "schema_id": RESERVATION_SCHEMA_ID,
        "policy_sha256": policy["policy_sha256"],
        "source_commit_git_sha1": source_commit_git_sha1,
        "operator_id": operator_id,
        "execution_environment_sha256": execution_environment_sha256,
        "durable_output_root": EXPECTED_OUTPUT_ROOT.as_posix(),
        "maximum_lifetime_run_count": 1,
        "reserved_run_ordinal": 1,
        "fresh_holdout_execution_authorized": False,
        "product_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }
    receipt["receipt_sha256"] = sha256_payload(receipt)
    _write_exclusive_json(
        output_root / str(execution["reservation_filename"]),
        receipt,
        repository_root=repository_root,
    )
    return receipt


def create_run_start_receipt(
    *,
    policy: Mapping[str, Any],
    reservation: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    verify_self_hash(reservation, hash_field="receipt_sha256", name="reservation receipt")
    if reservation.get("schema_id") != RESERVATION_SCHEMA_ID:
        raise OneShotABAuthorityError("reservation schema is invalid")
    if reservation.get("policy_sha256") != policy.get("policy_sha256"):
        raise OneShotABAuthorityError("reservation/policy cross-wire")
    if reservation.get("durable_output_root") != EXPECTED_OUTPUT_ROOT.as_posix():
        raise OneShotABAuthorityError("reservation output-root identity drifted")
    if reservation.get("reserved_run_ordinal") != 1:
        raise OneShotABAuthorityError("only run ordinal one is authorized")
    output_root = resolve_output_root(policy, repository_root=repository_root)
    execution = _mapping(policy["execution"], name="execution")
    if (output_root / str(execution["result_filename"])).exists():
        raise OneShotABAuthorityError("result already exists")

    receipt: dict[str, Any] = {
        "schema_id": RUN_START_SCHEMA_ID,
        "policy_sha256": policy["policy_sha256"],
        "reservation_receipt_sha256": reservation["receipt_sha256"],
        "source_commit_git_sha1": reservation["source_commit_git_sha1"],
        "execution_environment_sha256": reservation["execution_environment_sha256"],
        "durable_output_root": EXPECTED_OUTPUT_ROOT.as_posix(),
        "required_scorer_backend": "rust_cpu_required",
        "historical_case_ids": list(EXPECTED_CASE_IDS),
        "candidate_slots_per_scored_case_per_arm": 64,
        "expected_scored_candidate_rows": 1024,
        "fresh_holdout_execution_authorized": False,
        "product_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }
    receipt["receipt_sha256"] = sha256_payload(receipt)
    _write_exclusive_json(
        output_root / str(execution["run_start_filename"]),
        receipt,
        repository_root=repository_root,
    )
    return receipt


def build_verdict(inputs: OneShotABVerdictInputs, *, policy_sha256: str) -> dict[str, Any]:
    if policy_sha256 != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("verdict policy identity is invalid")
    candidate_denominator_ok = (
        inputs.baseline_candidate_count == 512
        and inputs.experimental_candidate_count == 512
    )
    preparation_ok = tuple(inputs.preparation_failure_case_ids) == ("6M73_FNR",)
    top1_regression = not set(inputs.baseline_top1_recovery_case_ids).issubset(
        inputs.experimental_top1_recovery_case_ids
    )
    top5_regression = not set(inputs.baseline_top5_recovery_case_ids).issubset(
        inputs.experimental_top5_recovery_case_ids
    )
    new_valid = bool(
        (set(inputs.experimental_exact_valid_case_ids) & set(EXPECTED_UNCOVERED_CASE_IDS))
        - set(inputs.baseline_exact_valid_case_ids)
    )
    oracle_at_least_two = len(set(inputs.experimental_proposal_oracle_case_ids)) >= 2
    invalid_top1_at_most_four = len(set(inputs.experimental_invalid_top1_case_ids)) <= 4

    invariants = {
        "no_preparation_failure_regression": preparation_ok,
        "no_top1_or_top5_recovery_regression": not top1_regression and not top5_regression,
        "candidate_denominator_512_per_arm": candidate_denominator_ok,
        "source_control_preserved": inputs.source_control_preserved,
        "score_term_semantics_fully_verified": inputs.score_term_semantics_fully_verified,
        "no_result_dependent_allocation": not inputs.result_dependent_allocation_observed,
    }
    go_criteria = {
        "new_exact_valid_candidate_in_previously_uncovered_case": new_valid,
        "proposal_oracle_recovery_at_least_2_of_8": oracle_at_least_two,
        "invalid_top1_at_most_4_of_8": invalid_top1_at_most_four,
    }
    no_go_criteria = {
        "shadow_eligible_candidate_without_new_case_recovery": (
            inputs.shadow_eligible_candidate_count > 0
            and not new_valid
            and not oracle_at_least_two
            and not invalid_top1_at_most_four
        ),
        "no_exact_valid_case_increase": not new_valid,
        "no_invalid_top1_reduction": (
            len(set(inputs.experimental_invalid_top1_case_ids))
            >= len(set(inputs.baseline_invalid_top1_case_ids))
        ),
        "existing_recovery_regression": top1_regression or top5_regression,
        "selected_state_remains_penetrating_without_posebusters_validity_change": (
            inputs.selected_penetrating_without_validity_change_count > 0
        ),
    }
    no_go = any(no_go_criteria.values())
    go = all(invariants.values()) and any(go_criteria.values()) and not no_go
    verdict = "GO_CONTINUE_FIXED_32_CASE" if go else "NO_GO_CLOSE_LOCAL_REFINEMENT"
    receipt: dict[str, Any] = {
        "schema_id": VERDICT_SCHEMA_ID,
        "policy_sha256": policy_sha256,
        "verdict": verdict,
        "invariants": invariants,
        "go_criteria": go_criteria,
        "no_go_criteria": no_go_criteria,
        "fresh_holdout_execution_authorized": False,
        "stage0_admission_authority": False,
        "profile_promotion_authority": False,
        "product_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }
    receipt["receipt_sha256"] = sha256_payload(receipt)
    return receipt


__all__ = [
    "EXPECTED_OUTPUT_ROOT",
    "EXPECTED_POLICY_SHA256",
    "OneShotABAuthorityError",
    "OneShotABDecision",
    "OneShotABVerdictInputs",
    "authorization_decision",
    "build_verdict",
    "canonical_json_bytes",
    "create_run_start_receipt",
    "load_json_document",
    "reserve_one_shot_execution",
    "resolve_output_root",
    "sha256_payload",
    "verify_one_shot_policy",
    "verify_self_hash",
]

"""Bind one-shot A/B authority to coherent policy and durable source state.

This stacked-PR boundary updates the frozen policy identities consumed by the
one-shot authority, corrects the primary Go / hard No-Go decision semantics,
verifies both source-policy self-hashes, requires the exact clean Git ``HEAD``,
and prevents callers from bypassing durable reservation or run-start files with
reconstructed in-memory mappings.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any


SOURCE_PAIRED_CLEARANCE_ONE_SHOT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_binding/1.3.0"
)
EXPECTED_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_policy/1.1.0"
)
EXPECTED_VERDICT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_verdict/1.1.0"
)
EXPECTED_ONE_SHOT_POLICY_SHA256 = (
    "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
)
EXPECTED_PHASE25_POLICY_SHA256 = (
    "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211"
)
EXPECTED_ACTIVATION_POLICY_SHA256 = (
    "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
)
EXPECTED_NO_GO_CRITERIA = (
    "required_invariant_failed",
    "all_primary_go_criteria_failed",
    "existing_recovery_regression",
    "selected_state_remains_penetrating_without_posebusters_validity_change",
)
MAX_DURABLE_RECEIPT_BYTES = 4 * 1024 * 1024


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _git_executable() -> Path:
    for candidate in (Path("/usr/bin/git"), Path("/bin/git")):
        if candidate.is_file():
            return candidate
    raise RuntimeError("a fixed system Git executable is required")


def _run_git(repository_root: Path, *arguments: str) -> str:
    root = repository_root.resolve(strict=True)
    command = [str(_git_executable()), "-C", str(root), *arguments]
    completed = subprocess.run(
        command,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "HOME": "/nonexistent",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().replace("\n", " ")[:240]
        raise RuntimeError(f"Git source verification failed: {detail}")
    return completed.stdout.strip()


def require_clean_checkout(repository_root: Path) -> str:
    """Return exact HEAD only for a clean tracked and untracked checkout."""

    head = _run_git(repository_root, "rev-parse", "--verify", "HEAD^{commit}")
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise RuntimeError("observed Git HEAD is not a lowercase SHA-1")
    status = _run_git(
        repository_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise RuntimeError("one-shot authority requires a clean Git checkout")
    return head


def _durable_path_components(path: Path, *, repository_root: Path) -> tuple[Path, ...]:
    root = repository_root.resolve(strict=True)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("durable receipt path escapes the repository root") from exc
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise RuntimeError("durable receipt path contains an unsafe component")
    current = root
    components: list[Path] = []
    for component in relative.parts:
        current = current / component
        components.append(current)
    return tuple(components)


def read_durable_receipt(
    path: Path,
    *,
    repository_root: Path,
    name: str,
) -> dict[str, Any]:
    """Read one exact owner-only receipt without following path components."""

    components = _durable_path_components(path, repository_root=repository_root)
    if not components:
        raise RuntimeError(f"{name} path is empty")
    for directory in components[:-1]:
        try:
            observed = os.lstat(directory)
        except OSError as exc:
            raise RuntimeError(f"{name} cannot be opened safely: {exc}") from exc
        if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode):
            raise RuntimeError(f"{name} path contains a symlink or non-directory")
        if stat.S_IMODE(observed.st_mode) != 0o700:
            raise RuntimeError(f"{name} directory must have mode 0700")

    target = components[-1]
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as exc:
        raise RuntimeError(f"{name} cannot be opened safely: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"{name} must be a regular file")
        if stat.S_IMODE(before.st_mode) != 0o600:
            raise RuntimeError(f"{name} must have mode 0600")
        if before.st_size <= 0 or before.st_size > MAX_DURABLE_RECEIPT_BYTES:
            raise RuntimeError(f"{name} size is outside the bounded receipt envelope")
        chunks: list[bytes] = []
        observed_size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_DURABLE_RECEIPT_BYTES + 1))
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > MAX_DURABLE_RECEIPT_BYTES:
                raise RuntimeError(f"{name} exceeds the bounded receipt envelope")
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after or observed_size != before.st_size:
        raise RuntimeError(f"{name} changed while it was being read")
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{name} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name} must be a JSON object")
    return payload


def _corrected_verdict_builder(one_shot):
    def build_verdict(inputs, *, policy_sha256: str) -> dict[str, Any]:
        if policy_sha256 != EXPECTED_ONE_SHOT_POLICY_SHA256:
            raise one_shot.OneShotABAuthorityError(
                "verdict policy identity is invalid"
            )
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
        existing_recovery_regression = top1_regression or top5_regression
        new_valid = bool(
            (
                set(inputs.experimental_exact_valid_case_ids)
                & set(one_shot.EXPECTED_UNCOVERED_CASE_IDS)
            )
            - set(inputs.baseline_exact_valid_case_ids)
        )
        oracle_at_least_two = (
            len(set(inputs.experimental_proposal_oracle_case_ids)) >= 2
        )
        invalid_top1_at_most_four = (
            len(set(inputs.experimental_invalid_top1_case_ids)) <= 4
        )

        invariants = {
            "no_preparation_failure_regression": preparation_ok,
            "no_top1_or_top5_recovery_regression": not existing_recovery_regression,
            "candidate_denominator_512_per_arm": candidate_denominator_ok,
            "source_control_preserved": inputs.source_control_preserved,
            "score_term_semantics_fully_verified": (
                inputs.score_term_semantics_fully_verified
            ),
            "no_result_dependent_allocation": (
                not inputs.result_dependent_allocation_observed
            ),
        }
        go_criteria = {
            "new_exact_valid_candidate_in_previously_uncovered_case": new_valid,
            "proposal_oracle_recovery_at_least_2_of_8": oracle_at_least_two,
            "invalid_top1_at_most_4_of_8": invalid_top1_at_most_four,
        }
        required_invariant_failed = not all(invariants.values())
        all_primary_go_criteria_failed = not any(go_criteria.values())
        no_go_criteria = {
            "required_invariant_failed": required_invariant_failed,
            "all_primary_go_criteria_failed": all_primary_go_criteria_failed,
            "existing_recovery_regression": existing_recovery_regression,
            "selected_state_remains_penetrating_without_posebusters_validity_change": (
                inputs.selected_penetrating_without_validity_change_count > 0
            ),
        }
        no_go = any(no_go_criteria.values())
        go = all(invariants.values()) and any(go_criteria.values()) and not no_go
        verdict = (
            "GO_CONTINUE_FIXED_32_CASE"
            if go
            else "NO_GO_CLOSE_LOCAL_REFINEMENT"
        )
        receipt: dict[str, Any] = {
            "schema_id": EXPECTED_VERDICT_SCHEMA_ID,
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
        receipt["receipt_sha256"] = one_shot.sha256_payload(receipt)
        return receipt

    build_verdict._betelgeuze_coherent_primary_go_semantics = True
    return build_verdict


def install_source_paired_clearance_one_shot_binding() -> str:
    """Install policy, verdict, clean-checkout, and durable-state guards."""

    marker = "_betelgeuze_source_paired_clearance_one_shot_binding_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import source_paired_clearance_one_shot_ab as one_shot

    one_shot.POLICY_SCHEMA_ID = EXPECTED_POLICY_SCHEMA_ID
    one_shot.VERDICT_SCHEMA_ID = EXPECTED_VERDICT_SCHEMA_ID
    one_shot.EXPECTED_POLICY_SHA256 = EXPECTED_ONE_SHOT_POLICY_SHA256
    one_shot.EXPECTED_PHASE25_POLICY_SHA256 = EXPECTED_PHASE25_POLICY_SHA256
    one_shot.EXPECTED_ACTIVATION_POLICY_SHA256 = EXPECTED_ACTIVATION_POLICY_SHA256
    one_shot.EXPECTED_NO_GO_CRITERIA = EXPECTED_NO_GO_CRITERIA
    one_shot.build_verdict = _corrected_verdict_builder(one_shot)

    original_verify = one_shot.verify_one_shot_policy
    original_decision = one_shot.authorization_decision
    original_reserve = one_shot.reserve_one_shot_execution
    original_start = one_shot.create_run_start_receipt

    if not getattr(
        original_verify,
        "_betelgeuze_source_policy_self_hash_binding",
        False,
    ):

        def verify_one_shot_policy(
            policy,
            *,
            phase25_policy,
            activation_policy,
        ) -> None:
            one_shot.verify_self_hash(
                phase25_policy,
                hash_field="policy_sha256",
                name="Phase 2.5 cohort policy",
            )
            try:
                one_shot.verify_self_hash(
                    activation_policy,
                    hash_field="policy_sha256",
                    name="activation policy",
                )
            except one_shot.OneShotABAuthorityError as exc:
                raise one_shot.OneShotABAuthorityError(
                    "activation policy self-hash is invalid; activation policy cross-wire"
                ) from exc
            original_verify(
                policy,
                phase25_policy=phase25_policy,
                activation_policy=activation_policy,
            )

        verify_one_shot_policy._betelgeuze_source_policy_self_hash_binding = True
        one_shot.verify_one_shot_policy = verify_one_shot_policy

    if not getattr(original_decision, "_betelgeuze_clean_checkout_binding", False):

        def authorization_decision(
            policy,
            *,
            phase25_policy,
            activation_policy,
            repository_root,
        ):
            decision = original_decision(
                policy,
                phase25_policy=phase25_policy,
                activation_policy=activation_policy,
                repository_root=repository_root,
            )
            if not decision.authorized:
                return decision
            try:
                require_clean_checkout(repository_root)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                return one_shot.OneShotABDecision(
                    authorized=False,
                    blockers=(*decision.blockers, str(exc)),
                )
            return decision

        authorization_decision._betelgeuze_clean_checkout_binding = True
        one_shot.authorization_decision = authorization_decision

    if not getattr(original_reserve, "_betelgeuze_exact_head_binding", False):

        def reserve_one_shot_execution(
            *,
            policy,
            phase25_policy,
            activation_policy,
            repository_root,
            source_commit_git_sha1,
            operator_id,
            execution_environment_sha256,
        ):
            try:
                observed_head = require_clean_checkout(repository_root)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                raise one_shot.OneShotABAuthorityError(str(exc)) from exc
            if source_commit_git_sha1 != observed_head:
                raise one_shot.OneShotABAuthorityError(
                    "declared source commit does not equal the clean checkout HEAD"
                )
            return original_reserve(
                policy=policy,
                phase25_policy=phase25_policy,
                activation_policy=activation_policy,
                repository_root=repository_root,
                source_commit_git_sha1=source_commit_git_sha1,
                operator_id=operator_id,
                execution_environment_sha256=execution_environment_sha256,
            )

        reserve_one_shot_execution._betelgeuze_exact_head_binding = True
        one_shot.reserve_one_shot_execution = reserve_one_shot_execution

    if not getattr(original_start, "_betelgeuze_durable_exact_head_binding", False):

        def create_run_start_receipt(
            *,
            policy,
            reservation,
            repository_root,
        ):
            one_shot.verify_self_hash(
                policy,
                hash_field="policy_sha256",
                name="one-shot policy",
            )
            if policy.get("policy_sha256") != EXPECTED_ONE_SHOT_POLICY_SHA256:
                raise one_shot.OneShotABAuthorityError(
                    "run-start policy identity is invalid"
                )
            output_root = one_shot.resolve_output_root(
                policy,
                repository_root=repository_root,
            )
            execution = one_shot._mapping(policy.get("execution"), name="execution")
            reservation_path = output_root / str(execution.get("reservation_filename"))
            try:
                durable_reservation = read_durable_receipt(
                    reservation_path,
                    repository_root=repository_root,
                    name="one-shot reservation",
                )
                observed_head = require_clean_checkout(repository_root)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                raise one_shot.OneShotABAuthorityError(str(exc)) from exc
            if dict(reservation) != durable_reservation:
                raise one_shot.OneShotABAuthorityError(
                    "reservation argument does not equal the durable reservation"
                )
            if durable_reservation.get("source_commit_git_sha1") != observed_head:
                raise one_shot.OneShotABAuthorityError(
                    "reservation source commit does not equal the clean checkout HEAD"
                )
            return original_start(
                policy=policy,
                reservation=durable_reservation,
                repository_root=repository_root,
            )

        create_run_start_receipt._betelgeuze_durable_exact_head_binding = True
        one_shot.create_run_start_receipt = create_run_start_receipt

    receipt = _sha256(
        {
            "schema_id": SOURCE_PAIRED_CLEARANCE_ONE_SHOT_BINDING_SCHEMA_ID,
            "one_shot_policy_schema_id": EXPECTED_POLICY_SCHEMA_ID,
            "one_shot_policy_sha256": EXPECTED_ONE_SHOT_POLICY_SHA256,
            "verdict_schema_id": EXPECTED_VERDICT_SCHEMA_ID,
            "primary_go_semantics": "all_invariants_and_any_primary_criterion",
            "hard_no_go_trigger_precedence": True,
            "phase25_policy_schema_id": (
                "betelgeuze.engine_v2_phase25_cohort_admission/1.3.0"
            ),
            "phase25_policy_sha256": EXPECTED_PHASE25_POLICY_SHA256,
            "activation_policy_schema_id": (
                "betelgeuze.engine_v2_source_paired_clearance_activation_policy/1.2.0"
            ),
            "activation_policy_sha256": EXPECTED_ACTIVATION_POLICY_SHA256,
            "phase25_source_self_hash_required": True,
            "activation_source_self_hash_required": True,
            "clean_git_checkout_required_for_authorization": True,
            "declared_source_commit_must_equal_head": True,
            "run_start_rechecks_head_and_cleanliness": True,
            "run_start_requires_exact_durable_reservation": True,
            "historical_ab_execution_scope_only": True,
            "fresh_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "EXPECTED_ACTIVATION_POLICY_SHA256",
    "EXPECTED_NO_GO_CRITERIA",
    "EXPECTED_ONE_SHOT_POLICY_SHA256",
    "EXPECTED_PHASE25_POLICY_SHA256",
    "EXPECTED_POLICY_SCHEMA_ID",
    "EXPECTED_VERDICT_SCHEMA_ID",
    "MAX_DURABLE_RECEIPT_BYTES",
    "SOURCE_PAIRED_CLEARANCE_ONE_SHOT_BINDING_SCHEMA_ID",
    "install_source_paired_clearance_one_shot_binding",
    "read_durable_receipt",
    "require_clean_checkout",
]

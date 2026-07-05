from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_pr38_ci_runner_hygiene_child_pr_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _patch_text(*, include_uid_guard: bool = True) -> str:
    tokens = [
        "Recover stale product image smoke workspace artifacts",
        "clean: false",
        "${{ runner.temp }}/product_image_smoke_runner_artifacts",
        "runs/product_image_build_smoke.log\n+            ${{ runner.temp }}/product_image_smoke_runner_artifacts/**",
        "runs/product_image_rocm_runtime_smoke.log\n+            ${{ runner.temp }}/product_image_smoke_runner_artifacts/**",
        'workflow.count("${{ runner.temp }}/product_image_smoke_runner_artifacts/**") >= 2',
        'PRODUCT_IMAGE_CONTAINER_UID_GID="$(id -u):$(id -g)"',
        "chmod -R a+rwX logs runs",
        "mktemp .betelgeuze/ai_verify_kiro_design_prompt",
        "normalize_product_image_smoke_artifact_ownership.sh",
        "build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
        "observe_product_ci_runtime_gate_from_github.py",
        "runner_workspace_cleanup_command",
        'DEFAULT_RUNNER_SMOKE_DIR="${RUNNER_TEMP:-/tmp}/product_image_smoke_runner_artifacts"',
        "PRODUCT_IMAGE_WORKSPACE_RUNNER_SMOKE_DIR",
        "container_uid_gid_invalid",
        "container_uid_gid_root",
        "product_image_runner_hygiene_v1",
    ]
    if include_uid_guard:
        tokens.append("container_uid_gid_not_host")
    return "\n".join(tokens) + "\n"


def _write_inputs(root: Path, *, include_uid_guard: bool = True) -> dict[str, Path]:
    source_path = root / "tools/product/build_pr38_child_pr_verification_matrix.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "\n".join(
            [
                "PRODUCT_MODE_PASS_RESULT = 'pass_product_smoke_claim_boundaries_locked'",
                "PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS = []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    patch_path = root / ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(_patch_text(include_uid_guard=include_uid_guard), encoding="utf-8")
    focused = (
        "python3 -m pytest -q tests/unit/test_ai_design_kiro_wrapper_contract.py "
        "tests/unit/test_api_worker_deploy_artifacts.py "
        "tests/unit/test_build_product_image_smoke_preflight.py "
        "tests/unit/test_build_github_self_hosted_runner_host_preflight.py "
        "tests/unit/test_build_product_ci_runtime_gate.py "
        "tests/unit/test_build_release_ci_remote_green_receipt.py "
        "tests/unit/test_release_ci_remote_green_evidence_contract.py "
        "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py "
        "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py "
        "tests/unit/test_build_pr38_child_pr_verification_matrix.py "
        "tests/unit/test_observe_product_ci_runtime_gate_from_github.py "
        "tests/unit/test_product_runtime_reality.py"
    )
    plan = {
        "summary": {"status": "pr38_child_pr_extraction_plan_ready"},
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "draft_branch_name": "codex/pr38-ci-runner-hygiene",
                "focused_test_command": focused,
            }
        ],
    }
    bundle = {
        "summary": {"status": "pr38_slice_patch_bundle_ready"},
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "draft_branch_name": "codex/pr38-ci-runner-hygiene",
                "patch_path": ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch",
                "patch_sha256": "a" * 64,
                "patch_nonempty": True,
                "changed_file_count": len(mod.REQUIRED_PATCH_FILES),
                "file_paths": list(mod.REQUIRED_PATCH_FILES),
            }
        ],
    }
    apply = {
        "summary": {"status": "pr38_slice_patch_apply_preflight_ready"},
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "patch_path": ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch",
                "apply_check_ready": True,
                "apply_check_status": "apply_check_passed",
            }
        ],
    }
    launch = {
        "summary": {
            "status": "pr38_child_pr_launch_command_pack_ready",
            "launch_command_pack_ready": True,
            "shell_pack_prints_commands_only": True,
            "operator_branch_pr_launch_allowed_by_this_packet": False,
            "post_push_remote_ci_branch_filter_uses_json_head_branch": True,
            "post_push_remote_ci_dispatch_guard_present": True,
            "post_push_remote_ci_remote_ref_guard_present": True,
            "post_push_remote_ci_uses_isolated_worktree": True,
            "post_push_remote_ci_bootstraps_local_evidence": True,
            "post_push_remote_ci_syncs_local_evidence_back": True,
            "post_push_remote_ci_rebuilds_root_release_gate": True,
            "post_push_remote_ci_waits_for_expected_head_sha": True,
            "post_push_remote_ci_requires_all_dispatched_runs_observed": True,
            "post_push_remote_ci_unsupported_branch_flag_present": False,
            "bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path": True,
            "bootstrap_ci_runner_hygiene_launch_preconditions_ready": True,
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present": True,
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present": True,
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree": True,
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence": True,
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back": True,
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate": True,
            "bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet": False,
            "bootstrap_ci_runner_hygiene_isolated_worktree_launch_present": True,
            "bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree": True,
            "isolated_worktree_launch_script_count": 1,
            "post_push_remote_ci_script_count": 1,
            "launch_scripts_non_executable": True,
            "isolated_worktree_launch_preserves_current_worktree": True,
            "isolated_worktree_launch_uses_absolute_patch_and_body_paths": True,
            "isolated_worktree_root": ".betelgeuze/pr38_child_pr_worktrees",
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "draft_branch_name": "codex/pr38-ci-runner-hygiene",
                "patch_path": ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch",
                "focused_test_command": focused,
            }
        ],
    }
    preflight = {
        "summary": {
            "status": "product_image_smoke_preflight_ready",
            "receipt_runner_hygiene_ready": True,
            "receipt_runner_smoke_dir_outside_workspace": True,
            "receipt_container_output_uid_gid_pinned": True,
            "receipt_container_output_uid_gid_matches_host": True,
            "receipt_container_output_uid_gid_non_root": True,
            "receipt_workspace_runner_smoke_dir_cleanup_ready": True,
        }
    }
    runtime = {
        "summary": {
            "status": "blocked_product_ci_runtime_gate",
            "runtime_gate_ready": False,
            "primary_blocker": "github_actions_workspace_cleanup_permission_denied",
            "local_product_image_runner_hygiene_remediation_ready": True,
            "remote_ci_rerun_handoff_ready": True,
            "remote_ci_failure_class": "workspace_cleanup_permission",
            "remote_workspace_cleanup_permission_blocked": True,
        }
    }
    paths = {
        "plan": root / "plan.json",
        "bundle": root / "bundle.json",
        "apply": root / "apply.json",
        "launch": root / "launch.json",
        "preflight": root / "preflight.json",
        "runtime": root / "runtime.json",
    }
    for key, payload in (
        ("plan", plan),
        ("bundle", bundle),
        ("apply", apply),
        ("launch", launch),
        ("preflight", preflight),
        ("runtime", runtime),
    ):
        _write_json(paths[key], payload)
    return paths


def test_ci_runner_hygiene_child_pr_gate_ready_for_first_slice_review(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "pr38_ci_runner_hygiene_child_pr_gate_ready"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is True
    assert summary["ci_runner_hygiene_child_pr_review_ready"] is True
    assert summary["ci_runner_hygiene_remote_ci_verified"] is False
    assert summary["ci_runner_hygiene_remote_ci_verification_required"] is True
    assert summary["remote_ci_rerun_current_patch_verification_required"] is True
    assert summary["remote_ci_rerun_current_patch_published"] is False
    assert summary["remote_ci_rerun_after_push_required"] is True
    assert summary["local_git_state_available"] is False
    assert summary["local_runner_hygiene_required_patch_file_dirty_count"] == 0
    assert summary["local_runner_hygiene_required_patch_files_pending_commit"] is False
    assert summary["operator_branch_pr_launch_allowed_by_this_gate"] is False
    assert summary["missing_required_patch_file_count"] == 0
    assert summary["missing_required_patch_token_count"] == 0
    assert summary["verification_matrix_self_contained_imports_ready"] is True
    assert summary["verification_matrix_source_prohibited_import_count"] == 0
    assert summary["verification_matrix_patch_prohibited_import_count"] == 0
    assert summary["patch_runner_temp_artifact_upload_glob_count"] >= 2
    assert summary["patch_runner_temp_artifact_upload_count_guard_present"] is True
    assert summary["patch_build_runner_temp_artifact_upload_hunk_present"] is True
    assert summary["patch_workspace_artifact_upload_glob_added"] is False
    assert summary["missing_focused_test_token_count"] == 0
    assert summary["local_product_image_runner_hygiene_ready"] is True
    assert summary["local_product_image_runner_hygiene_remediation_ready"] is True
    assert summary["product_ci_runtime_remote_ci_handoff_recorded"] is True
    assert summary["product_ci_runtime_remote_ci_rerun_handoff_ready"] is True
    assert summary["product_ci_runtime_remote_ci_failure_class"] == "workspace_cleanup_permission"
    assert summary["remote_workspace_cleanup_permission_blocked"] is True
    assert (
        summary["launch_pack_post_push_remote_ci_branch_filter_uses_json_head_branch"]
        is True
    )
    assert summary["launch_pack_post_push_remote_ci_dispatch_guard_present"] is True
    assert summary["launch_pack_post_push_remote_ci_remote_ref_guard_present"] is True
    assert summary["launch_pack_post_push_remote_ci_uses_isolated_worktree"] is True
    assert summary["launch_pack_post_push_remote_ci_bootstraps_local_evidence"] is True
    assert summary["launch_pack_post_push_remote_ci_syncs_local_evidence_back"] is True
    assert summary["launch_pack_post_push_remote_ci_rebuilds_root_release_gate"] is True
    assert summary["launch_pack_post_push_remote_ci_waits_for_expected_head_sha"] is True
    assert (
        summary["launch_pack_post_push_remote_ci_requires_all_dispatched_runs_observed"]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present"
        ]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present"
        ]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree"
        ]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence"
        ]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back"
        ]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate"
        ]
        is True
    )
    assert (
        summary["launch_pack_post_push_remote_ci_unsupported_branch_flag_present"]
        is False
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path"
        ]
        is True
    )
    assert (
        summary["launch_pack_bootstrap_ci_runner_hygiene_launch_preconditions_ready"]
        is True
    )
    assert summary["launch_pack_bootstrap_ci_runner_hygiene_operator_launch_allowed"] is False
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_launch_present"
        ]
        is True
    )
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree"
        ]
        is True
    )
    assert summary["launch_pack_isolated_worktree_launch_script_count"] == 1
    assert summary["launch_pack_post_push_remote_ci_script_count"] == 1
    assert summary["launch_pack_launch_scripts_non_executable"] is True
    assert (
        summary["launch_pack_isolated_worktree_launch_preserves_current_worktree"]
        is True
    )
    assert (
        summary[
            "launch_pack_isolated_worktree_launch_uses_absolute_patch_and_body_paths"
        ]
        is True
    )
    assert (
        summary["launch_pack_isolated_worktree_root"]
        == ".betelgeuze/pr38_child_pr_worktrees"
    )
    assert summary["blocker_count"] == 0
    assert summary["next_required_step"].startswith("Commit and push the local CI runner hygiene patch")
    assert all(row["passed"] is True for row in payload["rows"])


def test_ci_runner_hygiene_child_pr_gate_blocks_cross_slice_verification_matrix_import(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    source_path = tmp_path / "tools/product/build_pr38_child_pr_verification_matrix.py"
    source_path.write_text(
        "from tools.product.build_pr38_split_acceptance_packet import PRODUCT_MODE_PASS_RESULT\n",
        encoding="utf-8",
    )
    patch_path = (
        tmp_path
        / ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch"
    )
    patch_path.write_text(
        patch_path.read_text(encoding="utf-8")
        + "+from tools.product.build_pr38_split_acceptance_packet import PRODUCT_MODE_PASS_RESULT\n",
        encoding="utf-8",
    )

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["check_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["verification_matrix_self_contained_imports_ready"] is False
    assert summary["verification_matrix_source_prohibited_import_count"] == 1
    assert summary["verification_matrix_patch_prohibited_import_count"] == 1
    assert rows["verification_matrix_self_contained_imports"]["passed"] is False
    assert summary["primary_blocker"] == (
        "ci_runner_hygiene_verification_matrix_cross_slice_imports_present"
    )


def test_ci_runner_hygiene_child_pr_gate_accepts_remote_not_green_handoff(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    _write_json(
        paths["runtime"],
        {
            "summary": {
                "status": "blocked_product_ci_runtime_gate",
                "runtime_gate_ready": False,
                "primary_blocker": "product-api-worker_not_green",
                "blockers": [
                    "product-api-worker_not_green",
                    "product-image-smoke_not_green",
                ],
                "local_product_image_runner_hygiene_remediation_ready": True,
                "remote_ci_rerun_handoff_ready": True,
                "remote_ci_failure_class": "remote_workflows_not_green",
                "remote_workspace_cleanup_permission_blocked": False,
            }
        },
    )

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "pr38_ci_runner_hygiene_child_pr_gate_ready"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is True
    assert summary["remote_workspace_cleanup_permission_blocked"] is False
    assert summary["product_ci_runtime_remote_ci_handoff_recorded"] is True
    assert summary["product_ci_runtime_remote_ci_rerun_handoff_ready"] is True
    assert summary["product_ci_runtime_remote_ci_failure_class"] == "remote_workflows_not_green"
    assert summary["product_ci_runtime_remote_ci_not_green_blockers"] == [
        "product-api-worker_not_green",
        "product-image-smoke_not_green",
    ]
    assert summary["blocker_count"] == 0
    assert all(row["passed"] is True for row in payload["rows"])


def test_ci_runner_hygiene_child_pr_gate_blocks_unsupported_run_list_branch_flag(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    launch = json.loads(paths["launch"].read_text(encoding="utf-8"))
    launch["summary"]["post_push_remote_ci_branch_filter_uses_json_head_branch"] = False
    launch["summary"]["post_push_remote_ci_unsupported_branch_flag_present"] = True
    _write_json(paths["launch"], launch)

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["primary_blocker"] == "launch_pack_review_only_contract_not_ready"
    assert (
        summary["launch_pack_post_push_remote_ci_branch_filter_uses_json_head_branch"]
        is False
    )
    assert (
        summary["launch_pack_post_push_remote_ci_unsupported_branch_flag_present"]
        is True
    )


def test_ci_runner_hygiene_child_pr_gate_blocks_missing_dispatch_guard(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    launch = json.loads(paths["launch"].read_text(encoding="utf-8"))
    launch["summary"]["post_push_remote_ci_dispatch_guard_present"] = False
    launch["summary"][
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present"
    ] = False
    _write_json(paths["launch"], launch)

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["primary_blocker"] == "launch_pack_review_only_contract_not_ready"
    assert summary["launch_pack_post_push_remote_ci_dispatch_guard_present"] is False
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present"
        ]
        is False
    )


def test_ci_runner_hygiene_child_pr_gate_blocks_missing_remote_ref_guard(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    launch = json.loads(paths["launch"].read_text(encoding="utf-8"))
    launch["summary"]["post_push_remote_ci_remote_ref_guard_present"] = False
    launch["summary"][
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present"
    ] = False
    _write_json(paths["launch"], launch)

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["primary_blocker"] == "launch_pack_review_only_contract_not_ready"
    assert summary["launch_pack_post_push_remote_ci_remote_ref_guard_present"] is False
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present"
        ]
        is False
    )


def test_ci_runner_hygiene_child_pr_gate_blocks_missing_isolated_worktree_launch(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    launch = json.loads(paths["launch"].read_text(encoding="utf-8"))
    launch["summary"]["bootstrap_ci_runner_hygiene_isolated_worktree_launch_present"] = False
    launch["summary"]["bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree"] = False
    launch["summary"]["isolated_worktree_launch_preserves_current_worktree"] = False
    launch["summary"]["isolated_worktree_launch_uses_absolute_patch_and_body_paths"] = False
    _write_json(paths["launch"], launch)

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["primary_blocker"] == "launch_pack_review_only_contract_not_ready"
    assert (
        summary[
            "launch_pack_bootstrap_ci_runner_hygiene_isolated_worktree_launch_present"
        ]
        is False
    )
    assert (
        summary["launch_pack_isolated_worktree_launch_preserves_current_worktree"]
        is False
    )


def test_ci_runner_hygiene_child_pr_gate_blocks_missing_uid_guard(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, include_uid_guard=False)

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["missing_required_patch_token_count"] == 1
    assert summary["missing_required_patch_tokens"] == ["uid_gid_not_host_guard"]
    assert summary["primary_blocker"] == "ci_runner_hygiene_required_patch_tokens_missing"


def test_ci_runner_hygiene_child_pr_gate_blocks_stale_runner_temp_upload_semantics(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    patch_path = (
        tmp_path
        / ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch"
    )
    patch_text = patch_path.read_text(encoding="utf-8")
    patch_text = patch_text.replace(
        'workflow.count("${{ runner.temp }}/product_image_smoke_runner_artifacts/**") >= 2',
        '"${{ runner.temp }}/product_image_smoke_runner_artifacts/**" in workflow',
    )
    patch_text = patch_text.replace(
        "runs/product_image_build_smoke.log\n+            ${{ runner.temp }}/product_image_smoke_runner_artifacts/**",
        "runs/product_image_build_smoke.log",
    )
    patch_path.write_text(patch_text, encoding="utf-8")

    payload = mod.build_pr38_ci_runner_hygiene_child_pr_gate(
        extraction_plan_json=paths["plan"],
        patch_bundle_json=paths["bundle"],
        apply_preflight_json=paths["apply"],
        launch_command_pack_json=paths["launch"],
        product_image_preflight_json=paths["preflight"],
        product_ci_runtime_gate_json=paths["runtime"],
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["check_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_child_pr_gate"
    assert summary["ci_runner_hygiene_child_pr_gate_ready"] is False
    assert summary["patch_runner_temp_artifact_upload_count_guard_present"] is False
    assert summary["patch_build_runner_temp_artifact_upload_hunk_present"] is False
    assert rows["patch_bundle_runner_temp_artifact_upload_semantics"]["passed"] is False
    assert summary["primary_blocker"] == (
        "ci_runner_hygiene_runner_temp_artifact_upload_semantics_missing"
    )


def test_git_dirty_required_patch_files_preserves_dot_prefixed_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "_git_output",
        lambda *_args: (
            "M .github/workflows/product-api-worker.yml\n"
            " M .github/workflows/product-image-smoke.yml\n"
            "?? scripts/normalize_product_image_smoke_artifact_ownership.sh\n"
            " M scripts/ai-verify.sh\n"
            " M tests/unit/test_ai_design_kiro_wrapper_contract.py\n"
            "?? tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py\n"
            "?? tests/unit/test_observe_product_ci_runtime_gate_from_github.py\n"
            "?? tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py\n"
            "?? tools/product/observe_product_ci_runtime_gate_from_github.py\n"
        ),
    )

    rows = mod._git_dirty_required_patch_files(tmp_path)

    assert rows == [
        {"status": "M", "path": ".github/workflows/product-api-worker.yml"},
        {"status": "M", "path": ".github/workflows/product-image-smoke.yml"},
        {
            "status": "??",
            "path": "scripts/normalize_product_image_smoke_artifact_ownership.sh",
        },
        {"status": "M", "path": "scripts/ai-verify.sh"},
        {"status": "M", "path": "tests/unit/test_ai_design_kiro_wrapper_contract.py"},
        {
            "status": "??",
            "path": "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
        },
        {
            "status": "??",
            "path": "tests/unit/test_observe_product_ci_runtime_gate_from_github.py",
        },
        {
            "status": "??",
            "path": "tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
        },
        {
            "status": "??",
            "path": "tools/product/observe_product_ci_runtime_gate_from_github.py",
        },
    ]

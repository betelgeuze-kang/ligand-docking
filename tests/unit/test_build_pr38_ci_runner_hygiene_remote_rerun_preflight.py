from __future__ import annotations

from pathlib import Path

from tools.product import build_pr38_ci_runner_hygiene_remote_rerun_preflight as mod


def _write_runtime_gate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """{
  "summary": {
    "status": "blocked_product_ci_runtime_gate",
    "primary_blocker": "github_actions_workspace_cleanup_permission_denied",
    "blockers": [
      "github_actions_workspace_cleanup_permission_denied",
      "product-api-worker_not_green",
      "product-image-build-smoke_not_green",
      "product-image-smoke_not_green"
    ],
    "remote_ci_failure_class": "workspace_cleanup_permission",
    "remote_workspace_cleanup_permission_blocked": true,
    "product_api_worker_run_id": "28733222237",
    "product_image_build_smoke_run_id": "28733222606",
    "product_image_smoke_run_id": "28733223018",
    "remote_ci_observed_head_sha": "abc123",
    "remote_ci_observed_head_branch": "codex/source-of-truth-benchmark-gpcr-pocketmd",
    "remote_ci_observed_checkout_clean_mode": "true",
    "remote_ci_observed_checkout_clean_true": true,
    "remote_ci_current_workflow_patch_unverified": true,
    "remote_ci_rerun_after_workflow_publication_required": true,
    "remote_ci_science_tests_unverified": true
  }
}
""",
        encoding="utf-8",
    )


def _child_payload(
    *,
    published: bool,
    current_branch_matches_expected: bool | None = None,
) -> dict:
    if current_branch_matches_expected is None:
        current_branch_matches_expected = published
    current_branch = (
        "codex/pr38-ci-runner-hygiene"
        if current_branch_matches_expected
        else "codex/source-of-truth-benchmark-gpcr-pocketmd"
    )
    return {
        "summary": {
            "status": "pr38_ci_runner_hygiene_child_pr_gate_ready",
            "ci_runner_hygiene_child_pr_gate_ready": True,
            "ci_runner_hygiene_remote_ci_verified": False,
            "ci_runner_hygiene_remote_ci_verification_required": True,
            "draft_branch_name": "codex/pr38-ci-runner-hygiene",
            "local_git_current_branch": current_branch,
            "local_git_head_sha": "abc123",
            "local_git_upstream_ref": (
                "origin/codex/pr38-ci-runner-hygiene"
                if current_branch_matches_expected
                else "origin/codex/source-of-truth-benchmark-gpcr-pocketmd"
            ),
            "local_git_upstream_sha": "abc123" if published else "def456",
            "local_git_head_matches_upstream": published,
            "local_runner_hygiene_required_patch_file_dirty_count": 0 if published else 21,
            "local_runner_hygiene_required_patch_file_dirty_paths": (
                [] if published else ["deploy/verify_product_image.sh"]
            ),
            "remote_ci_rerun_current_patch_published": published,
            "remote_ci_rerun_after_push_required": not published,
        }
    }


def test_remote_rerun_preflight_blocks_until_child_patch_is_published(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_gate = tmp_path / "runs/product_ci_runtime_gate_current.json"
    _write_runtime_gate(runtime_gate)
    monkeypatch.setattr(
        mod,
        "build_pr38_ci_runner_hygiene_child_pr_gate",
        lambda **_kwargs: _child_payload(published=False),
    )
    monkeypatch.setattr(
        mod,
        "_git_status_dirty_paths",
        lambda _root: [
            "deploy/verify_product_image.sh",
            "tools/product/ci_contract_fixture_packets.py",
        ],
    )

    payload = mod.build_pr38_ci_runner_hygiene_remote_rerun_preflight(
        product_ci_runtime_gate_json=runtime_gate,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_remote_rerun_preflight"
    assert summary["remote_rerun_preflight_ready"] is False
    assert summary["operator_remote_ci_dispatch_preconditions_ready"] is False
    assert summary["operator_remote_ci_dispatch_allowed_by_this_preflight"] is False
    assert summary["workflow_dispatch_executed"] is False
    assert summary["local_git_current_branch"] == (
        "codex/source-of-truth-benchmark-gpcr-pocketmd"
    )
    assert summary["expected_branch"] == "codex/pr38-ci-runner-hygiene"
    assert summary["expected_remote_ci_rerun_ref"] == (
        "refs/heads/codex/pr38-ci-runner-hygiene"
    )
    assert summary["expected_remote_ci_rerun_upstream_ref"] == (
        "origin/codex/pr38-ci-runner-hygiene"
    )
    assert summary["expected_remote_ci_rerun_ref_published_for_dispatch"] is False
    assert summary["expected_remote_ci_rerun_ref_missing_for_dispatch"] is True
    assert summary["gh_workflow_dispatch_422_expected_until_ref_published"] is True
    assert summary["expected_remote_ci_rerun_ref_missing_required_action"] == (
        "Create, commit, and push codex/pr38-ci-runner-hygiene before any "
        "gh workflow run --ref codex/pr38-ci-runner-hygiene command."
    )
    assert summary["local_runner_hygiene_required_patch_file_dirty_count"] == 21
    assert summary["local_worktree_dirty_count"] == 2
    assert summary["local_worktree_dirty_paths"] == [
        "deploy/verify_product_image.sh",
        "tools/product/ci_contract_fixture_packets.py",
    ]
    assert summary["human_owner_external_mutation_required"] is True
    assert summary["codex_should_not_run_handoff_commands"] is True
    assert summary["human_commit_worktree_dir"] == (
        ".betelgeuze/pr38_child_pr_worktrees/ci_runner_hygiene"
    )
    assert summary["human_commit_required_dirty_path_count"] == 0
    assert summary["human_commit_required_dirty_paths"] == []
    assert summary["human_commit_dirty_paths_suppressed_wrong_branch"] is True
    assert summary["human_git_add_command"] == "git add <reviewed-files>"
    assert summary["human_git_commit_command"] == (
        "git commit -m '[codex] Isolate PR39 self-hosted checkout workspace'"
    )
    assert summary["human_git_push_command"] == "git push"
    assert summary["human_post_push_remote_ci_command"] == (
        "bash .betelgeuze/pr38_child_pr_launch_command_pack_current/"
        "01-ci_runner_hygiene-post-push-remote-ci.sh"
    )
    assert summary["human_commit_push_command_block"] == [
        "cd .betelgeuze/pr38_child_pr_worktrees/ci_runner_hygiene",
        "git add <reviewed-files>",
        "git commit -m '[codex] Isolate PR39 self-hosted checkout workspace'",
        "git push",
        "cd ../../..",
        (
            "bash .betelgeuze/pr38_child_pr_launch_command_pack_current/"
            "01-ci_runner_hygiene-post-push-remote-ci.sh"
        ),
    ]
    assert summary["remote_ci_rerun_current_patch_published"] is False
    assert summary["remote_ci_rerun_after_push_required"] is True
    assert summary["primary_blocker"] == "ci_runner_hygiene_wrong_branch_for_remote_rerun"
    assert "ci_runner_hygiene_wrong_branch_for_remote_rerun" in summary["blockers"]
    assert "ci_runner_hygiene_required_patch_files_uncommitted" in summary["blockers"]
    assert "ci_runner_hygiene_local_worktree_dirty" in summary["blockers"]
    assert "ci_runner_hygiene_patch_not_published_for_remote_rerun" in summary["blockers"]
    assert summary["product_ci_runtime_gate_status"] == "blocked_product_ci_runtime_gate"
    assert summary["product_ci_runtime_primary_blocker"] == (
        "github_actions_workspace_cleanup_permission_denied"
    )
    assert summary["product_ci_runtime_remote_ci_failure_class"] == (
        "workspace_cleanup_permission"
    )
    assert summary[
        "product_ci_runtime_remote_workspace_cleanup_permission_blocked"
    ] is True
    assert summary["latest_product_api_worker_run_id"] == "28733222237"
    assert summary["latest_product_image_build_smoke_run_id"] == "28733222606"
    assert summary["latest_product_image_smoke_run_id"] == "28733223018"
    assert summary["latest_remote_ci_observed_head_sha"] == "abc123"
    assert summary["latest_remote_ci_observed_head_branch"] == (
        "codex/source-of-truth-benchmark-gpcr-pocketmd"
    )
    assert summary["expected_remote_ci_rerun_branch"] == (
        "codex/pr38-ci-runner-hygiene"
    )
    assert summary["latest_remote_ci_observed_head_matches_expected_branch"] is False
    assert summary["latest_remote_ci_observed_wrong_branch_for_child_rerun"] is True
    assert summary["latest_remote_ci_observed_wrong_branch_required_action"] == (
        "Rerun product-api-worker and product-image-smoke with --ref "
        "codex/pr38-ci-runner-hygiene"
    )
    assert summary["latest_remote_ci_observed_checkout_clean_mode"] == "true"
    assert summary["latest_remote_ci_observed_checkout_clean_true"] is True
    assert summary["latest_remote_ci_current_workflow_patch_unverified"] is True
    assert summary[
        "latest_remote_ci_rerun_after_workflow_publication_required"
    ] is True
    assert summary["latest_remote_ci_science_tests_unverified"] is True
    assert summary["latest_remote_rerun_observed"] is True
    assert summary["latest_remote_rerun_observed_head_matches_local_head"] is True
    assert summary["latest_remote_rerun_cannot_validate_local_patch"] is True
    assert summary["latest_remote_rerun_cannot_validate_child_branch_patch"] is True


def test_remote_rerun_preflight_handoff_includes_all_dirty_paths_on_child_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "build_pr38_ci_runner_hygiene_child_pr_gate",
        lambda **_kwargs: _child_payload(
            published=False,
            current_branch_matches_expected=True,
        ),
    )
    monkeypatch.setattr(
        mod,
        "_git_status_dirty_paths",
        lambda _root: [
            "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
            "tools/product/materialize_docking_htvs_request.py",
        ],
    )

    payload = mod.build_pr38_ci_runner_hygiene_remote_rerun_preflight(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_pr38_ci_runner_hygiene_remote_rerun_preflight"
    assert summary["local_git_current_branch"] == "codex/pr38-ci-runner-hygiene"
    assert summary["local_worktree_dirty_count"] == 2
    assert summary["human_commit_required_dirty_path_count"] == 2
    assert summary["human_commit_required_dirty_paths"] == [
        "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py",
        "tools/product/materialize_docking_htvs_request.py",
    ]
    assert summary["human_git_add_command"] == (
        "git add "
        "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py "
        "tools/product/materialize_docking_htvs_request.py"
    )
    assert summary["human_commit_dirty_paths_suppressed_wrong_branch"] is False
    assert "ci_runner_hygiene_local_worktree_dirty" in summary["blockers"]


def test_remote_rerun_preflight_ready_when_child_branch_is_clean_and_pushed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "build_pr38_ci_runner_hygiene_child_pr_gate",
        lambda **_kwargs: _child_payload(published=True),
    )

    payload = mod.build_pr38_ci_runner_hygiene_remote_rerun_preflight(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "pr38_ci_runner_hygiene_remote_rerun_preflight_ready"
    assert summary["remote_rerun_preflight_ready"] is True
    assert summary["operator_remote_ci_dispatch_preconditions_ready"] is True
    assert summary["operator_remote_ci_dispatch_allowed_by_this_preflight"] is False
    assert summary["workflow_dispatch_executed"] is False
    assert summary["local_git_current_branch"] == "codex/pr38-ci-runner-hygiene"
    assert summary["expected_remote_ci_rerun_ref_published_for_dispatch"] is True
    assert summary["expected_remote_ci_rerun_ref_missing_for_dispatch"] is False
    assert summary["gh_workflow_dispatch_422_expected_until_ref_published"] is False
    assert summary["expected_remote_ci_rerun_ref_missing_required_action"] == ""
    assert summary["local_git_head_matches_upstream"] is True
    assert summary["local_runner_hygiene_required_patch_file_dirty_count"] == 0
    assert summary["local_worktree_dirty_count"] == 0
    assert summary["local_worktree_dirty_paths"] == []
    assert summary["human_owner_external_mutation_required"] is False
    assert summary["codex_should_not_run_handoff_commands"] is True
    assert summary["human_commit_required_dirty_path_count"] == 0
    assert summary["human_commit_required_dirty_paths"] == []
    assert summary["remote_ci_rerun_current_patch_published"] is True
    assert summary["remote_ci_rerun_after_push_required"] is False
    assert summary["expected_remote_ci_rerun_branch"] == (
        "codex/pr38-ci-runner-hygiene"
    )
    assert summary["latest_remote_ci_observed_head_matches_expected_branch"] is False
    assert summary["latest_remote_ci_observed_wrong_branch_for_child_rerun"] is False
    assert summary["latest_remote_rerun_cannot_validate_child_branch_patch"] is False
    assert summary["blocker_count"] == 0
    assert all(row["passed"] is True for row in payload["rows"])

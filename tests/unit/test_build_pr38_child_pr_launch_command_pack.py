from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from tools.product import build_pr38_child_pr_launch_command_pack as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _packets(root: Path, *, patch_ready: bool = True) -> tuple[Path, Path, Path]:
    plan = {
        "summary": {
            "status": "pr38_child_pr_extraction_plan_ready",
            "extraction_plan_ready": True,
            "minimum_child_pr_count": 2,
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "draft_branch_name": "codex/pr38-ci-runner-hygiene",
                "draft_pr_title": "[codex] Split PR38 self-hosted runner hygiene",
                "depends_on_slice_ids": [],
                "depends_on_slice_count": 0,
                "integration_touchpoint_count": 0,
                "focused_test_command": "python3 -m pytest tests/unit/test_build_product_ci_runtime_gate.py",
                "claim_boundary": "No product image claim.",
            },
            {
                "sequence": 2,
                "slice_id": "api_operator_cockpit",
                "draft_branch_name": "codex/pr38-api-operator-cockpit",
                "draft_pr_title": "[codex] Split PR38 API operator cockpit surfaces",
                "depends_on_slice_ids": ["ci_runner_hygiene"],
                "depends_on_slice_count": 1,
                "integration_touchpoint_count": 2,
                "focused_test_command": "python3 -m pytest tests/unit/test_build_product_operator_cockpit.py",
                "claim_boundary": "No API readiness claim.",
            },
        ],
    }
    patch_bundle = {
        "summary": {
            "status": "pr38_slice_patch_bundle_ready" if patch_ready else "blocked_pr38_slice_patch_bundle",
            "patch_bundle_ready": patch_ready,
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "patch_path": ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch",
                "patch_sha256": "a" * 64,
                "patch_nonempty": True,
                "changed_file_count": 7,
            },
            {
                "sequence": 2,
                "slice_id": "api_operator_cockpit",
                "patch_path": ".betelgeuze/pr38_slice_patch_bundle_current/08-api_operator_cockpit.patch",
                "patch_sha256": "b" * 64,
                "patch_nonempty": True,
                "changed_file_count": 18,
            },
        ],
    }
    acceptance = {
        "summary": {
            "status": "blocked_pr38_split_acceptance_packet",
            "split_acceptance_ready": False,
            "split_structural_acceptance_ready": True,
            "product_mode_verification_ready": False,
            "minimum_child_pr_count": 2,
            "blocker_count": 3,
            "primary_blocker": "product_mode:release_ci_remote_green_semantic_ready_status=fail",
            "blockers": [
                "product_mode:release_ci_remote_green_semantic_ready_status=fail",
                "product_mode:release_ci_remote_green_semantic_ready_missing_true:pass",
                "product_mode:bm5_capri_raw_data_custody_plan_semantic_ready_status=fail",
            ],
        }
    }
    plan_path = root / "plan.json"
    patch_path = root / "patches.json"
    acceptance_path = root / "acceptance.json"
    _write_json(plan_path, plan)
    _write_json(patch_path, patch_bundle)
    _write_json(acceptance_path, acceptance)
    return plan_path, patch_path, acceptance_path


def test_child_pr_launch_command_pack_writes_read_only_handoff(tmp_path: Path) -> None:
    plan, patches, acceptance = _packets(tmp_path)

    payload = mod.build_pr38_child_pr_launch_command_pack(
        extraction_plan_json=plan,
        patch_bundle_json=patches,
        acceptance_packet_json=acceptance,
        out_dir=tmp_path / "bodies",
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = {row["slice_id"]: row for row in payload["rows"]}

    assert summary["status"] == "pr38_child_pr_launch_command_pack_ready"
    assert summary["launch_command_pack_ready"] is True
    assert summary["child_pr_count"] == 2
    assert summary["minimum_child_pr_count_met"] is True
    assert summary["isolated_worktree_launch_script_count"] == 2
    assert summary["post_push_remote_ci_script_count"] == 1
    assert summary["launch_scripts_non_executable"] is True
    assert summary["acceptance_packet_status"] == "blocked_pr38_split_acceptance_packet"
    assert summary["acceptance_packet_ready"] is False
    assert summary["acceptance_packet_split_structural_acceptance_ready"] is True
    assert summary["acceptance_packet_product_mode_verification_ready"] is False
    assert summary["acceptance_packet_blocker_count"] == 3
    assert summary["acceptance_packet_primary_blocker"] == (
        "product_mode:release_ci_remote_green_semantic_ready_status=fail"
    )
    assert summary["acceptance_packet_blockers"] == [
        "product_mode:release_ci_remote_green_semantic_ready_status=fail",
        "product_mode:release_ci_remote_green_semantic_ready_missing_true:pass",
        "product_mode:bm5_capri_raw_data_custody_plan_semantic_ready_status=fail",
    ]
    assert summary["operator_branch_pr_launch_preconditions_ready"] is False
    assert summary["operator_branch_pr_launch_allowed_by_this_packet"] is False
    assert summary["operator_branch_pr_launch_blocked_by_acceptance_packet"] is True
    assert summary["bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path"] is True
    assert summary["bootstrap_ci_runner_hygiene_launch_preconditions_ready"] is True
    assert (
        summary["bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet"]
        is False
    )
    assert summary["bootstrap_ci_runner_hygiene_sequence"] == 1
    assert summary["bootstrap_ci_runner_hygiene_branch"] == "codex/pr38-ci-runner-hygiene"
    assert summary["bootstrap_ci_runner_hygiene_post_push_remote_ci_command_count"] == 55
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present"
        ]
        is True
    )
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present"
        ]
        is True
    )
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree"
        ]
        is True
    )
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence"
        ]
        is True
    )
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back"
        ]
        is True
    )
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate"
        ]
        is True
    )
    assert summary["bootstrap_ci_runner_hygiene_isolated_worktree_launch_present"] is True
    assert (
        summary[
            "bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree"
        ]
        is True
    )
    assert summary["post_push_remote_ci_verification_slice_count"] == 1
    assert summary["post_push_remote_ci_command_count"] == 55
    assert summary["post_push_remote_ci_dispatch_required"] is True
    assert summary["post_push_remote_ci_dispatch_guard_present"] is True
    assert summary["post_push_remote_ci_remote_ref_guard_present"] is True
    assert summary["post_push_remote_ci_uses_isolated_worktree"] is True
    assert summary["post_push_remote_ci_bootstraps_local_evidence"] is True
    assert summary["post_push_remote_ci_syncs_local_evidence_back"] is True
    assert summary["post_push_remote_ci_rebuilds_root_release_gate"] is True
    assert summary["post_push_remote_ci_waits_for_expected_head_sha"] is True
    assert summary["post_push_remote_ci_requires_all_dispatched_runs_observed"] is True
    assert summary["post_push_remote_ci_dispatch_executed_by_this_packet"] is False
    assert summary["post_push_remote_ci_branch_filter_uses_json_head_branch"] is True
    assert summary["post_push_remote_ci_unsupported_branch_flag_present"] is False
    assert summary["isolated_worktree_launch_preserves_current_worktree"] is True
    assert summary["isolated_worktree_launch_uses_absolute_patch_and_body_paths"] is True
    assert summary["isolated_worktree_root"] == ".betelgeuze/pr38_child_pr_worktrees"
    assert summary["next_required_step"].startswith(
        "Human owner can use only the sequence-1 ci_runner_hygiene bootstrap commands"
    )
    assert summary["operator_launch_requires_human_approval"] is True
    assert summary["branch_commit_push_pr_mutation_required"] is True
    assert summary["shell_pack_prints_commands_only"] is True
    assert summary["execution_enabled"] is False
    assert summary["branches_created"] is False
    assert summary["pull_requests_created"] is False
    assert rows["ci_runner_hygiene"]["pr_body_path"].endswith(
        "01-ci_runner_hygiene-body.md"
    )
    assert rows["ci_runner_hygiene"]["branch"] == "codex/pr38-ci-runner-hygiene"
    assert rows["ci_runner_hygiene"]["pr_body"].endswith(
        "01-ci_runner_hygiene-body.md"
    )
    assert rows["ci_runner_hygiene"]["isolated_worktree_launch_script_path"].endswith(
        "01-ci_runner_hygiene-isolated-launch.sh"
    )
    assert rows["ci_runner_hygiene"]["isolated_worktree_launch_script"].endswith(
        "01-ci_runner_hygiene-isolated-launch.sh"
    )
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_script_path"].endswith(
        "01-ci_runner_hygiene-post-push-remote-ci.sh"
    )
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_script"].endswith(
        "01-ci_runner_hygiene-post-push-remote-ci.sh"
    )
    assert rows["ci_runner_hygiene"]["launch_script_executable"] is False
    assert rows["ci_runner_hygiene"]["launch_script_mode"] == "0644"
    assert "git apply --check" in rows["ci_runner_hygiene"]["launch_commands"]
    assert "git apply --index" in rows["ci_runner_hygiene"]["launch_commands"]
    assert rows["ci_runner_hygiene"]["launch_commands"].startswith(
        "(\nset -euo pipefail\n"
    )
    assert rows["ci_runner_hygiene"]["launch_commands"].endswith("\n)")
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_verification_required"] is True
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_dispatch_required"] is True
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_command_count"] == 55
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_dispatch_guard_present"]
        is True
    )
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_remote_ref_guard_present"]
        is True
    )
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_uses_isolated_worktree"] is True
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_bootstraps_local_evidence"]
        is True
    )
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_syncs_local_evidence_back"]
        is True
    )
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_rebuilds_root_release_gate"]
        is True
    )
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_waits_for_expected_head_sha"]
        is True
    )
    assert (
        rows["ci_runner_hygiene"][
            "post_push_remote_ci_requires_all_dispatched_runs_observed"
        ]
        is True
    )
    assert (
        rows["ci_runner_hygiene"][
            "post_push_remote_ci_branch_filter_uses_json_head_branch"
        ]
        is True
    )
    assert (
        rows["ci_runner_hygiene"]["post_push_remote_ci_unsupported_branch_flag_present"]
        is False
    )
    assert "product-api-worker.yml" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert (
        "git ls-remote --exit-code --heads origin codex/pr38-ci-runner-hygiene >/dev/null"
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        "remote branch codex/pr38-ci-runner-hygiene is not published"
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert "--ref codex/pr38-ci-runner-hygiene" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert 'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert (
        'orchestration_root="$(git -C "${script_dir}/../.." rev-parse --show-toplevel)"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        'worktree_dir="${orchestration_root}/.betelgeuze/pr38_child_pr_worktrees/ci_runner_hygiene"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        'mkdir -p "${worktree_dir}/.betelgeuze/pr38_slice_patch_bundle_current"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        'cp "${orchestration_root}/.betelgeuze/pr38_child_pr_extraction_plan_current.json"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        'cp "${orchestration_root}/.betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        'cp "${orchestration_root}/runs/product_ci_runtime_gate_current.json"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert "for evidence_path in runs/product_ci_runtime_gate_current.json" in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert (
        ".betelgeuze/pr38_child_pr_verification_matrix_current.json"
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        'cp "${worktree_dir}/${evidence_path}" "${orchestration_root}/${evidence_path}"'
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert (
        "python3 tools/product/build_product_release_source_of_truth_gate.py"
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert 'git -C "${worktree_dir}" rev-parse --show-toplevel' in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert 'cd "${worktree_dir}"' in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert "isolated worktree for ci_runner_hygiene is missing" in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_commands"].startswith(
        'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
    )
    assert "else\n  echo 'BLOCKED: ci_runner_hygiene remote-rerun preflight is not ready" in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_commands"].endswith("\nfi")
    assert (
        rows["ci_runner_hygiene"]["isolated_worktree_launch_preserves_current_worktree"]
        is True
    )
    assert (
        rows["ci_runner_hygiene"][
            "isolated_worktree_launch_uses_absolute_patch_and_body_paths"
        ]
        is True
    )
    assert rows["ci_runner_hygiene"]["isolated_worktree_root"] == (
        ".betelgeuze/pr38_child_pr_worktrees"
    )
    assert 'repo_root="$(git rev-parse --show-toplevel)"' in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"].startswith(
        "(\nset -euo pipefail\n"
    )
    assert rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"].endswith(
        "\n)"
    )
    assert 'branch_name="codex/pr38-ci-runner-hygiene"' in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert 'git worktree add -b "${branch_name}"' in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert "BLOCKED: isolated worktree already exists for ci_runner_hygiene" in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert 'git -C \\"${worktree_dir}\\" status --short' in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert 'git worktree remove --force \\"${worktree_dir}\\"' in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert "exit 8" in rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"]
    assert "BLOCKED: local branch already exists for isolated launch" in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert 'git branch -D \\"${branch_name}\\"' in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert "exit 9" in rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"]
    assert "BLOCKED: remote branch already exists for isolated launch" in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert "Use the post-push remote CI script for the published branch" in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert "exit 10" in rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"]
    assert 'test ! -e "${worktree_dir}"' not in rows[
        "ci_runner_hygiene"
    ]["isolated_worktree_launch_commands"]
    assert "git switch main" not in rows["ci_runner_hygiene"][
        "isolated_worktree_launch_commands"
    ]
    assert (
        '"${repo_root}/.betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch"'
        in rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"]
    )
    assert (
        '"${repo_root}/bodies/01-ci_runner_hygiene-body.md"'
        in rows["ci_runner_hygiene"]["isolated_worktree_launch_commands"]
    )
    assert "verify_mode=rocm-runtime" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert (
        "expected_head_sha=\"$(git ls-remote origin "
        "refs/heads/codex/pr38-ci-runner-hygiene"
        in rows["ci_runner_hygiene"]["post_push_remote_ci_commands"]
    )
    assert "awk '{print $1}'" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert 'expected_head_sha="$(git rev-parse HEAD)"' not in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert 'grep -cx "${expected_head_sha}"' in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert 'test "${product_api_worker_run_count:-0}" -ge 1' in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert 'test "${product_image_smoke_run_count:-0}" -ge 2' in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert "gh run list --workflow=product-api-worker.yml --limit 20 --branch" not in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert "gh run list --workflow=product-image-smoke.yml --limit 20 --branch" not in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert "--json" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert "headBranch" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert "--jq" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert "build_pr38_ci_runner_hygiene_remote_rerun_preflight.py" in rows[
        "ci_runner_hygiene"
    ]["post_push_remote_ci_commands"]
    assert "observe_product_ci_runtime_gate_from_github.py" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert "build_pr38_ci_runner_hygiene_child_pr_gate.py" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert "build_pr38_child_pr_verification_matrix.py" in rows["ci_runner_hygiene"][
        "post_push_remote_ci_commands"
    ]
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_commands"].rfind(
        "build_pr38_ci_runner_hygiene_remote_rerun_preflight.py"
    ) > rows["ci_runner_hygiene"]["post_push_remote_ci_commands"].find(
        "observe_product_ci_runtime_gate_from_github.py"
    )
    assert rows["ci_runner_hygiene"]["post_push_remote_ci_commands"].find(
        "build_pr38_child_pr_verification_matrix.py"
    ) > rows["ci_runner_hygiene"]["post_push_remote_ci_commands"].find(
        "build_pr38_ci_runner_hygiene_child_pr_gate.py"
    )
    assert "gh pr create --draft" in rows["api_operator_cockpit"]["launch_commands"]
    assert rows["api_operator_cockpit"]["post_push_remote_ci_verification_required"] is False
    assert rows["api_operator_cockpit"]["post_push_remote_ci_commands"] == ""
    assert rows["api_operator_cockpit"]["post_push_remote_ci_script_path"] == ""
    assert rows["api_operator_cockpit"]["depends_on_slice_ids"] == ["ci_runner_hygiene"]
    ci_body = (tmp_path / rows["ci_runner_hygiene"]["pr_body_path"]).read_text(
        encoding="utf-8"
    )
    assert "## Post-Push Remote Verification" in ci_body
    assert "product-image-smoke.yml" in ci_body
    isolated_launch_script = (
        tmp_path / rows["ci_runner_hygiene"]["isolated_worktree_launch_script_path"]
    )
    post_push_script = tmp_path / rows["ci_runner_hygiene"]["post_push_remote_ci_script_path"]
    for script in (isolated_launch_script, post_push_script):
        script_text = script.read_text(encoding="utf-8")
        assert script_text.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
        assert script.stat().st_mode & 0o111 == 0
        subprocess.run(["bash", "-n", str(script)], check=True)
    assert 'git worktree add -b "${branch_name}"' in isolated_launch_script.read_text(
        encoding="utf-8"
    )
    assert "BLOCKED: isolated worktree already exists for ci_runner_hygiene" in (
        isolated_launch_script.read_text(encoding="utf-8")
    )
    assert "git ls-remote --exit-code --heads origin codex/pr38-ci-runner-hygiene" in post_push_script.read_text(
        encoding="utf-8"
    )
    body = tmp_path / rows["api_operator_cockpit"]["pr_body_path"]
    assert body.read_text(encoding="utf-8").startswith("## Summary")


def test_child_pr_launch_command_pack_blocks_when_patch_bundle_is_not_ready(
    tmp_path: Path,
) -> None:
    plan, patches, acceptance = _packets(tmp_path, patch_ready=False)

    payload = mod.build_pr38_child_pr_launch_command_pack(
        extraction_plan_json=plan,
        patch_bundle_json=patches,
        acceptance_packet_json=acceptance,
        out_dir=tmp_path / "bodies",
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_child_pr_launch_command_pack"
    assert payload["summary"]["launch_command_pack_ready"] is False
    assert payload["summary"]["patch_bundle_status"] == "blocked_pr38_slice_patch_bundle"


def test_child_pr_launch_command_pack_main_writes_print_only_shell_pack(
    tmp_path: Path,
) -> None:
    plan, patches, acceptance = _packets(tmp_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    out_sh = tmp_path / "out.sh"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--extraction-plan-json",
            str(plan),
            "--patch-bundle-json",
            str(patches),
            "--acceptance-packet-json",
            str(acceptance),
            "--out-dir",
            str(tmp_path / "bodies"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-sh",
            str(out_sh),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "pr38_child_pr_launch_command_pack_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["slice_id"] for row in rows] == [
        "ci_runner_hygiene",
        "api_operator_cockpit",
    ]
    assert out_md.read_text(encoding="utf-8").startswith(
        "# PR #38 Child PR Launch Command Pack"
    )
    shell_output = subprocess.run(
        ["bash", str(out_sh)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "This script prints commands only" in shell_output
    assert "acceptance_packet_ready: False" in shell_output
    assert "launch_allowed_by_this_packet: False" in shell_output
    assert "post_push_remote_ci_dispatch_required: True" in shell_output
    assert "post_push_remote_ci_dispatch_guard_present: True" in shell_output
    assert "post_push_remote_ci_remote_ref_guard_present: True" in shell_output
    assert "post_push_remote_ci_uses_isolated_worktree: True" in shell_output
    assert "post_push_remote_ci_bootstraps_local_evidence: True" in shell_output
    assert "post_push_remote_ci_syncs_local_evidence_back: True" in shell_output
    assert "post_push_remote_ci_rebuilds_root_release_gate: True" in shell_output
    assert "post_push_remote_ci_waits_for_expected_head_sha: True" in shell_output
    assert (
        "post_push_remote_ci_requires_all_dispatched_runs_observed: True"
        in shell_output
    )
    assert "post_push_remote_ci_dispatch_executed_by_this_packet: False" in shell_output
    assert "isolated_worktree_launch_script_count: 2" in shell_output
    assert "post_push_remote_ci_script_count: 1" in shell_output
    assert "launch_scripts_non_executable: True" in shell_output
    assert "bootstrap_ci_runner_hygiene_launch_preconditions_ready: True" in shell_output
    assert (
        "bootstrap_ci_runner_hygiene_isolated_worktree_launch_present: True"
        in shell_output
    )
    assert (
        "bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree: True"
        in shell_output
    )
    assert "isolated_worktree_launch_preserves_current_worktree: True" in shell_output
    assert (
        "isolated_worktree_launch_uses_absolute_patch_and_body_paths: True"
        in shell_output
    )
    assert (
        "bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet: False"
        in shell_output
    )
    assert "bootstrap blocker-clearance path" in shell_output
    assert "Prefer isolated worktree launch commands" in shell_output
    assert "Do not run the printed branch/commit/push/PR commands" in shell_output
    assert "Do not run printed gh workflow commands" in shell_output
    assert 'repo_root="$(git rev-parse --show-toplevel)"' in shell_output
    assert "set -euo pipefail" in shell_output
    assert 'branch_name="codex/pr38-ci-runner-hygiene"' in shell_output
    assert 'git worktree add -b "${branch_name}"' in shell_output
    assert 'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in shell_output
    assert (
        'orchestration_root="$(git -C "${script_dir}/../.." rev-parse --show-toplevel)"'
        in shell_output
    )
    assert (
        'worktree_dir="${orchestration_root}/.betelgeuze/pr38_child_pr_worktrees/ci_runner_hygiene"'
        in shell_output
    )
    assert (
        'mkdir -p "${worktree_dir}/.betelgeuze/pr38_slice_patch_bundle_current"'
        in shell_output
    )
    assert (
        'cp "${orchestration_root}/.betelgeuze/pr38_child_pr_launch_command_pack_current.json"'
        in shell_output
    )
    assert (
        'cp "${orchestration_root}/runs/product_image_smoke_preflight_current.json"'
        in shell_output
    )
    assert "for evidence_path in runs/product_ci_runtime_gate_current.json" in shell_output
    assert ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.json" in shell_output
    assert (
        'cp "${worktree_dir}/${evidence_path}" "${orchestration_root}/${evidence_path}"'
        in shell_output
    )
    assert "python3 tools/product/build_product_release_source_of_truth_gate.py" in shell_output
    assert 'git -C "${worktree_dir}" rev-parse --show-toplevel' in shell_output
    assert 'cd "${worktree_dir}"' in shell_output
    assert "isolated worktree for ci_runner_hygiene is missing" in shell_output
    assert (
        '"${repo_root}/.betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch"'
        in shell_output
    )
    assert "git switch -c codex/pr38-ci-runner-hygiene" in shell_output
    assert "gh pr create --draft" in shell_output
    assert "gh workflow run product-api-worker.yml --ref codex/pr38-ci-runner-hygiene" in shell_output
    assert (
        "git ls-remote --exit-code --heads origin codex/pr38-ci-runner-hygiene >/dev/null"
        in shell_output
    )
    assert "remote branch codex/pr38-ci-runner-hygiene is not published" in shell_output
    assert (
        "if python3 tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py; then"
        in shell_output
    )
    assert (
        "BLOCKED: ci_runner_hygiene remote-rerun preflight is not ready"
        in shell_output
    )
    assert "verify_mode=build" in shell_output
    assert "verify_mode=rocm-runtime" in shell_output
    assert (
        "expected_head_sha=\"$(git ls-remote origin "
        "refs/heads/codex/pr38-ci-runner-hygiene"
        in shell_output
    )
    assert "awk '{print $1}'" in shell_output
    assert 'expected_head_sha="$(git rev-parse HEAD)"' not in shell_output
    assert 'grep -cx "${expected_head_sha}"' in shell_output
    assert 'test "${product_api_worker_run_count:-0}" -ge 1' in shell_output
    assert 'test "${product_image_smoke_run_count:-0}" -ge 2' in shell_output
    assert "build_pr38_ci_runner_hygiene_remote_rerun_preflight.py" in shell_output
    assert "observe_product_ci_runtime_gate_from_github.py" in shell_output
    assert "build_pr38_ci_runner_hygiene_child_pr_gate.py" in shell_output
    assert "build_pr38_child_pr_verification_matrix.py" in shell_output
    assert shell_output.rfind("build_pr38_ci_runner_hygiene_remote_rerun_preflight.py") > shell_output.find(
        "observe_product_ci_runtime_gate_from_github.py"
    )
    assert "gh run list --workflow=product-api-worker.yml --limit 20 --branch" not in shell_output
    assert "gh run list --workflow=product-image-smoke.yml --limit 20 --branch" not in shell_output
    assert "--json databaseId,status,conclusion" in shell_output
    assert "headBranch == \"codex/pr38-ci-runner-hygiene\"" in shell_output

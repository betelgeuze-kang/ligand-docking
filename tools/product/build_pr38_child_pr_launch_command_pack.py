#!/usr/bin/env python3
"""Build a read-only launch command pack for PR #38 child PRs.

The pack turns the existing extraction plan and slice patch bundle into
operator-facing branch/commit/PR commands. It writes local command/body
artifacts only; it does not apply patches, create branches, stage, commit,
push, open PRs, post comments, merge, dispatch workflows, or mutate external
state.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXTRACTION_PLAN_JSON = ".betelgeuze/pr38_child_pr_extraction_plan_current.json"
DEFAULT_PATCH_BUNDLE_JSON = ".betelgeuze/pr38_slice_patch_bundle_current.json"
DEFAULT_ACCEPTANCE_PACKET_JSON = ".betelgeuze/pr38_split_acceptance_packet_current.json"
DEFAULT_OUT_DIR = ".betelgeuze/pr38_child_pr_launch_command_pack_current"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_child_pr_launch_command_pack_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_child_pr_launch_command_pack_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_child_pr_launch_command_pack_current.md"
DEFAULT_OUT_SH = ".betelgeuze/pr38_child_pr_launch_command_pack_current.sh"
DEFAULT_ISOLATED_WORKTREE_ROOT = ".betelgeuze/pr38_child_pr_worktrees"

PACKET_TYPE = "pr38_child_pr_launch_command_pack"
SCHEMA_VERSION = "pr38_child_pr_launch_command_pack_v1"
MINIMUM_CHILD_PR_COUNT = 5
CI_RUNNER_HYGIENE_SLICE_ID = "ci_runner_hygiene"
DEFAULT_GITHUB_REPO = "betelgeuze-kang/ligand-docking"
CI_RUNNER_HYGIENE_POST_PUSH_LOCAL_EVIDENCE_FILES = [
    ".betelgeuze/pr38_child_pr_extraction_plan_current.json",
    ".betelgeuze/pr38_slice_patch_bundle_current.json",
    ".betelgeuze/pr38_slice_patch_bundle_current/01-ci_runner_hygiene.patch",
    ".betelgeuze/pr38_slice_patch_apply_preflight_current.json",
    ".betelgeuze/pr38_child_pr_launch_command_pack_current.json",
    ".betelgeuze/pr38_split_acceptance_packet_current.json",
    "runs/product_image_smoke_preflight_current.json",
    "runs/product_ci_runtime_gate_current.json",
]
CI_RUNNER_HYGIENE_POST_PUSH_SYNC_BACK_FILES = [
    "runs/product_ci_runtime_gate_current.json",
    "runs/product_ci_runtime_gate_current.md",
    ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.json",
    ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.csv",
    ".betelgeuze/pr38_ci_runner_hygiene_remote_rerun_preflight_current.md",
    ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.json",
    ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.csv",
    ".betelgeuze/pr38_ci_runner_hygiene_child_pr_gate_current.md",
    ".betelgeuze/pr38_child_pr_verification_matrix_current.json",
    ".betelgeuze/pr38_child_pr_verification_matrix_current.csv",
    ".betelgeuze/pr38_child_pr_verification_matrix_current.md",
]

CLAIM_BOUNDARY = (
    "PR #38 child-PR launch command pack only; it emits local review commands and draft PR body files "
    "from already-prepared split artifacts. It does not apply patches, create branches, stage, commit, "
    "push, create pull requests, post comments, merge PR #38, dispatch workflows, promote claims, or "
    "mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "branches_created": False,
    "commits_created": False,
    "pushes_executed": False,
    "pull_requests_created": False,
    "claim_promotion_allowed": False,
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path: Path, *, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _rows_by_slice(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return {}
    return {
        _text(row.get("slice_id")): row
        for row in rows
        if isinstance(row, dict) and _text(row.get("slice_id"))
    }


def _quote(value: str) -> str:
    return shlex.quote(value)


def _body_text(row: dict[str, Any]) -> str:
    focused = _text(row.get("focused_test_command")) or "See focused_test_command in the launch packet row."
    lines = [
        "## Summary",
        "",
        f"Extracts PR #38 slice `{row['slice_id']}` into a reviewable child PR.",
        "",
        "## Patch Source",
        "",
        f"- patch: `{row['patch_path']}`",
        f"- patch_sha256: `{row['patch_sha256']}`",
        f"- changed_file_count: `{row['changed_file_count']}`",
        f"- integration_touchpoint_count: `{row['integration_touchpoint_count']}`",
        "",
        "## Validation",
        "",
        f"- `{focused}`",
        "- `./scripts/ai-verify.sh`",
        "",
    ]
    if _text(row.get("post_push_remote_ci_commands")):
        lines.extend(
            [
                "## Post-Push Remote Verification",
                "",
                "Run these only after the human owner has approved, pushed this child branch, and wants to validate the current patch on GitHub Actions.",
                "",
                "```bash",
                _text(row.get("post_push_remote_ci_commands")),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim Boundary",
            "",
            row["claim_boundary"] or CLAIM_BOUNDARY,
            "",
            "## Notes",
            "",
            "- Keep this PR as a draft until focused tests and ai-verify are attached.",
            "- Do not promote product, paid-pilot, benchmark, or scientific claims from this split alone.",
            "",
        ]
    )
    return "\n".join(lines)


def _script_text(*, title: str, commands: str) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"# {title}",
            "# Human-owner action only: review before running; this script may create branches, commits, pushes, PRs, or workflow dispatches.",
            commands,
            "",
        ]
    )


def _launch_commands(row: dict[str, Any], *, base_branch: str) -> list[str]:
    commands = [
        "(",
        "set -euo pipefail",
        f"git switch {_quote(base_branch)}",
        f"git pull --ff-only origin {_quote(base_branch)}",
        f"git switch -c {_quote(row['draft_branch_name'])}",
        f"git apply --check {_quote(row['patch_path'])}",
        f"git apply --index {_quote(row['patch_path'])}",
    ]
    focused = _text(row.get("focused_test_command"))
    if focused:
        commands.append(focused)
    commands.extend(
        [
            "./scripts/ai-verify.sh",
            "git status --short",
            f"git commit -m {_quote(row['draft_pr_title'])}",
            f"git push -u origin {_quote(row['draft_branch_name'])}",
            (
                "gh pr create --draft "
                f"--base {_quote(base_branch)} "
                f"--head {_quote(row['draft_branch_name'])} "
                f"--title {_quote(row['draft_pr_title'])} "
                f"--body-file {_quote(row['pr_body_path'])}"
            ),
            ")",
        ]
    )
    return commands


def _isolated_worktree_launch_commands(
    row: dict[str, Any],
    *,
    base_branch: str,
    worktree_root: str = DEFAULT_ISOLATED_WORKTREE_ROOT,
) -> list[str]:
    worktree_dir = f"{worktree_root}/{row['slice_id']}"
    focused = _text(row.get("focused_test_command"))
    commands = [
        "(",
        "set -euo pipefail",
        'repo_root="$(git rev-parse --show-toplevel)"',
        f'branch_name="{row["draft_branch_name"]}"',
        f'worktree_dir="${{repo_root}}/{worktree_dir}"',
        'mkdir -p "$(dirname "${worktree_dir}")"',
        'if [[ -e "${worktree_dir}" ]]; then',
        (
            f'  echo "BLOCKED: isolated worktree already exists for {row["slice_id"]}: '
            '${worktree_dir}" >&2'
        ),
        (
            '  echo "Inspect it before retrying: git -C \\"${worktree_dir}\\" '
            'status --short" >&2'
        ),
        (
            '  echo "If it only contains failed generated launch state, remove it '
            'manually with git worktree remove --force \\"${worktree_dir}\\" and '
            'delete the local branch with git branch -D \\"${branch_name}\\" only '
            'after review." >&2'
        ),
        "  exit 8",
        "fi",
        f"git fetch origin {_quote(base_branch)}",
        'if git show-ref --verify --quiet "refs/heads/${branch_name}"; then',
        (
            '  echo "BLOCKED: local branch already exists for isolated launch: '
            '${branch_name}" >&2'
        ),
        (
            '  echo "Inspect it before retrying: git log -1 --oneline '
            '\\"${branch_name}\\" && git status --short" >&2'
        ),
        (
            '  echo "If it only contains failed generated launch state, delete the '
            'local branch manually with git branch -D \\"${branch_name}\\" only after '
            'review." >&2'
        ),
        "  exit 9",
        "fi",
        'remote_head="$(git ls-remote --heads origin "${branch_name}")"',
        'if [[ -n "${remote_head}" ]]; then',
        (
            '  echo "BLOCKED: remote branch already exists for isolated launch: '
            '${branch_name}" >&2'
        ),
        (
            '  echo "Use the post-push remote CI script for the published branch, '
            'or inspect the existing remote branch before creating a replacement." >&2'
        ),
        "  exit 10",
        "fi",
        (
            'git worktree add -b "${branch_name}" '
            f'"${{worktree_dir}}" origin/{_quote(base_branch)}'
        ),
        'cd "${worktree_dir}"',
        f"git apply --check \"${{repo_root}}/{row['patch_path']}\"",
        f"git apply --index \"${{repo_root}}/{row['patch_path']}\"",
    ]
    if focused:
        commands.append(focused)
    commands.extend(
        [
            "./scripts/ai-verify.sh",
            "git status --short",
            f"git commit -m {_quote(row['draft_pr_title'])}",
            f"git push -u origin {_quote(row['draft_branch_name'])}",
            (
                "gh pr create --draft "
                f"--base {_quote(base_branch)} "
                f"--head {_quote(row['draft_branch_name'])} "
                f"--title {_quote(row['draft_pr_title'])} "
                f"--body-file \"${{repo_root}}/{row['pr_body_path']}\""
            ),
            ")",
        ]
    )
    return commands


def _gh_run_list_branch_filter_command(*, workflow: str, branch_name: str) -> str:
    json_fields = "databaseId,status,conclusion,createdAt,updatedAt,headSha,headBranch,url,event,name"
    jq_filter = f'.[] | select(.headBranch == "{branch_name}")'
    return (
        f"gh run list --workflow={_quote(workflow)} --limit 20 "
        f"--json {_quote(json_fields)} --jq {_quote(jq_filter)}"
    )


def _gh_run_count_for_expected_head_command(
    *,
    workflow: str,
    branch_name: str,
    variable_name: str,
) -> str:
    json_fields = "databaseId,headBranch,headSha"
    jq_filter = f'.[] | select(.headBranch == "{branch_name}") | .headSha'
    return (
        f'{variable_name}="$(gh run list --workflow={_quote(workflow)} --limit 20 '
        f"--json {_quote(json_fields)} --jq {_quote(jq_filter)} "
        '| grep -cx "${expected_head_sha}" || true)"'
    )


def _post_push_remote_ci_commands(row: dict[str, Any]) -> list[str]:
    if row["slice_id"] != CI_RUNNER_HYGIENE_SLICE_ID:
        return []
    branch_name = row["draft_branch_name"]
    branch = _quote(branch_name)
    linux_labels = _quote('["self-hosted","linux"]')
    worktree_dir = f"{DEFAULT_ISOLATED_WORKTREE_ROOT}/{row['slice_id']}"
    evidence_copy_commands = [
        "  mkdir -p "
        '"${worktree_dir}/.betelgeuze/pr38_slice_patch_bundle_current" '
        '"${worktree_dir}/.betelgeuze/pr38_child_pr_launch_command_pack_current" '
        '"${worktree_dir}/runs"',
        *[
            f'  cp "${{orchestration_root}}/{path}" "${{worktree_dir}}/{path}"'
            for path in CI_RUNNER_HYGIENE_POST_PUSH_LOCAL_EVIDENCE_FILES
        ],
    ]
    evidence_sync_back_commands = [
        "    for evidence_path in "
        + " ".join(_quote(path) for path in CI_RUNNER_HYGIENE_POST_PUSH_SYNC_BACK_FILES)
        + "; do",
        '      if [[ -f "${worktree_dir}/${evidence_path}" ]]; then',
        '        mkdir -p "$(dirname "${orchestration_root}/${evidence_path}")"',
        '        cp "${worktree_dir}/${evidence_path}" "${orchestration_root}/${evidence_path}"',
        "      fi",
        "    done",
        '    cd "${orchestration_root}"',
        "    python3 tools/product/build_pr38_child_pr_verification_matrix.py",
        "    python3 tools/product/build_product_release_source_of_truth_gate.py",
    ]
    return [
        'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'orchestration_root="$(git -C "${script_dir}/../.." rev-parse --show-toplevel)"',
        f'worktree_dir="${{orchestration_root}}/{worktree_dir}"',
        'if git -C "${worktree_dir}" rev-parse --show-toplevel >/dev/null 2>&1; then',
        *evidence_copy_commands,
        '  cd "${worktree_dir}"',
        "else",
        (
            "  echo 'BLOCKED: isolated worktree for ci_runner_hygiene is missing; "
            "run 01-ci_runner_hygiene-isolated-launch.sh before post-push remote CI.' >&2"
        ),
        "  exit 1",
        "fi",
        "if python3 tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py; then",
        f"  if git ls-remote --exit-code --heads origin {branch} >/dev/null; then",
        f"    gh workflow run product-api-worker.yml --ref {branch} -f runner_labels_json={linux_labels}",
        (
            f"    gh workflow run product-image-smoke.yml --ref {branch} "
            f"-f verify_mode=build -f build_runner_labels_json={linux_labels}"
        ),
        (
            f"    gh workflow run product-image-smoke.yml --ref {branch} "
            f"-f verify_mode=rocm-runtime -f build_runner_labels_json={linux_labels}"
        ),
        (
            "    expected_head_sha=\"$(git ls-remote origin "
            f"{_quote('refs/heads/' + branch_name)} | awk '{{print $1}}')\""
        ),
        "    for attempt in 1 2 3 4 5 6; do",
        "      "
        + _gh_run_count_for_expected_head_command(
            workflow="product-api-worker.yml",
            branch_name=branch_name,
            variable_name="product_api_worker_run_count",
        ),
        "      "
        + _gh_run_count_for_expected_head_command(
            workflow="product-image-smoke.yml",
            branch_name=branch_name,
            variable_name="product_image_smoke_run_count",
        ),
        (
            '      if [ "${product_api_worker_run_count:-0}" -ge 1 ] '
            '&& [ "${product_image_smoke_run_count:-0}" -ge 2 ]; then'
        ),
        "        break",
        "      fi",
        "      sleep 10",
        "    done",
        '    test "${product_api_worker_run_count:-0}" -ge 1',
        '    test "${product_image_smoke_run_count:-0}" -ge 2',
        "    "
        + _gh_run_list_branch_filter_command(
            workflow="product-api-worker.yml",
            branch_name=branch_name,
        ),
        "    "
        + _gh_run_list_branch_filter_command(
            workflow="product-image-smoke.yml",
            branch_name=branch_name,
        ),
        (
            "    python3 tools/product/observe_product_ci_runtime_gate_from_github.py "
            f"--repo {_quote(DEFAULT_GITHUB_REPO)} --branch {branch}"
        ),
        "    python3 tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py || true",
        "    python3 tools/product/build_pr38_ci_runner_hygiene_child_pr_gate.py",
        "    python3 tools/product/build_pr38_child_pr_verification_matrix.py",
        *evidence_sync_back_commands,
        "  else",
        (
            "    echo 'BLOCKED: remote branch codex/pr38-ci-runner-hygiene is not "
            "published; run the isolated worktree launch commands through git push "
            "-u origin codex/pr38-ci-runner-hygiene before gh workflow run --ref.' >&2"
        ),
        "  fi",
        "else",
        (
            "  echo 'BLOCKED: ci_runner_hygiene remote-rerun preflight is not ready; "
            "commit and push codex/pr38-ci-runner-hygiene before dispatch.' >&2"
        ),
        "fi",
    ]


def build_pr38_child_pr_launch_command_pack(
    *,
    extraction_plan_json: str | Path = DEFAULT_EXTRACTION_PLAN_JSON,
    patch_bundle_json: str | Path = DEFAULT_PATCH_BUNDLE_JSON,
    acceptance_packet_json: str | Path = DEFAULT_ACCEPTANCE_PACKET_JSON,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    base_branch: str = "main",
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    plan_packet = _read_json(extraction_plan_json, root=root_path)
    patch_packet = _read_json(patch_bundle_json, root=root_path)
    acceptance_packet = _read_json(acceptance_packet_json, root=root_path)
    plan_summary = _summary(plan_packet)
    patch_summary = _summary(patch_packet)
    acceptance_summary = _summary(acceptance_packet)
    plan_rows = plan_packet.get("rows") if isinstance(plan_packet.get("rows"), list) else []
    patch_rows = _rows_by_slice(patch_packet)
    body_dir = _resolve(out_dir, root=root_path)
    body_dir.mkdir(parents=True, exist_ok=True)
    for stale_script in list(body_dir.glob("*-isolated-launch.sh")) + list(
        body_dir.glob("*-post-push-remote-ci.sh")
    ):
        stale_script.unlink()

    rows: list[dict[str, Any]] = []
    missing_patch_slice_ids: list[str] = []
    for raw_row in plan_rows:
        if not isinstance(raw_row, dict):
            continue
        slice_id = _text(raw_row.get("slice_id"))
        patch_row = patch_rows.get(slice_id)
        if not patch_row:
            missing_patch_slice_ids.append(slice_id)
            continue
        sequence = int(raw_row.get("sequence") or len(rows) + 1)
        body_path = body_dir / f"{sequence:02d}-{slice_id}-body.md"
        isolated_launch_script_path = (
            body_dir / f"{sequence:02d}-{slice_id}-isolated-launch.sh"
        )
        post_push_remote_ci_script_path = (
            body_dir / f"{sequence:02d}-{slice_id}-post-push-remote-ci.sh"
        )
        row = {
            "sequence": sequence,
            "slice_id": slice_id,
            "draft_branch_name": _text(raw_row.get("draft_branch_name")),
            "branch": _text(raw_row.get("draft_branch_name")),
            "draft_pr_title": _text(raw_row.get("draft_pr_title")),
            "depends_on_slice_ids": list(raw_row.get("depends_on_slice_ids") or []),
            "depends_on_slice_count": int(raw_row.get("depends_on_slice_count") or 0),
            "patch_path": _text(patch_row.get("patch_path")),
            "patch_sha256": _text(patch_row.get("patch_sha256")),
            "patch_nonempty": bool(patch_row.get("patch_nonempty") is True),
            "changed_file_count": int(patch_row.get("changed_file_count") or 0),
            "integration_touchpoint_count": int(raw_row.get("integration_touchpoint_count") or 0),
            "focused_test_command": _text(raw_row.get("focused_test_command")),
            "claim_boundary": _text(raw_row.get("claim_boundary")),
            "pr_body_path": _display(body_path, root=root_path),
            "pr_body": _display(body_path, root=root_path),
            "isolated_worktree_launch_script_path": _display(
                isolated_launch_script_path,
                root=root_path,
            ),
            "isolated_worktree_launch_script": _display(
                isolated_launch_script_path,
                root=root_path,
            ),
            "post_push_remote_ci_script_path": "",
            "post_push_remote_ci_script": "",
            "operator_launch_script_requires_human_approval": True,
            "launch_script_executable": False,
            "launch_script_mode": "0644",
            "base_branch": base_branch,
            "operator_launch_requires_human_approval": True,
            "branch_commit_push_pr_mutation_required": True,
            **_READ_ONLY_FLAGS,
        }
        post_push_remote_ci_commands = _post_push_remote_ci_commands(row)
        row["post_push_remote_ci_verification_required"] = bool(
            post_push_remote_ci_commands
        )
        row["post_push_remote_ci_dispatch_required"] = bool(
            post_push_remote_ci_commands
        )
        row["post_push_remote_ci_command_count"] = len(post_push_remote_ci_commands)
        row["post_push_remote_ci_commands"] = "\n".join(post_push_remote_ci_commands)
        row["post_push_remote_ci_dispatch_guard_present"] = bool(
            post_push_remote_ci_commands
            and any(
                command.strip()
                == "if python3 tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py; then"
                for command in post_push_remote_ci_commands
            )
            and post_push_remote_ci_commands[-3] == "else"
            and post_push_remote_ci_commands[-1] == "fi"
            and any(
                "ci_runner_hygiene remote-rerun preflight is not ready"
                in command
                for command in post_push_remote_ci_commands
            )
        )
        row["post_push_remote_ci_uses_isolated_worktree"] = bool(
            post_push_remote_ci_commands
            and any('worktree_dir="${orchestration_root}/' in command for command in post_push_remote_ci_commands)
            and any(
                'git -C "${worktree_dir}" rev-parse --show-toplevel' in command
                for command in post_push_remote_ci_commands
            )
            and any(command.strip() == 'cd "${worktree_dir}"' for command in post_push_remote_ci_commands)
            and any("isolated worktree for ci_runner_hygiene is missing" in command for command in post_push_remote_ci_commands)
        )
        row["post_push_remote_ci_bootstraps_local_evidence"] = bool(
            post_push_remote_ci_commands
            and any(
                '.betelgeuze/pr38_slice_patch_bundle_current'
                in command
                for command in post_push_remote_ci_commands
            )
            and all(
                f'"${{orchestration_root}}/{path}"' in "\n".join(post_push_remote_ci_commands)
                and f'"${{worktree_dir}}/{path}"' in "\n".join(post_push_remote_ci_commands)
                for path in CI_RUNNER_HYGIENE_POST_PUSH_LOCAL_EVIDENCE_FILES
            )
        )
        row["post_push_remote_ci_syncs_local_evidence_back"] = bool(
            post_push_remote_ci_commands
            and all(
                path in "\n".join(post_push_remote_ci_commands)
                for path in CI_RUNNER_HYGIENE_POST_PUSH_SYNC_BACK_FILES
            )
            and any(
                'cp "${worktree_dir}/${evidence_path}" "${orchestration_root}/${evidence_path}"'
                in command
                for command in post_push_remote_ci_commands
            )
        )
        row["post_push_remote_ci_rebuilds_root_release_gate"] = bool(
            post_push_remote_ci_commands
            and any(
                command.strip()
                == "python3 tools/product/build_product_release_source_of_truth_gate.py"
                for command in post_push_remote_ci_commands
            )
        )
        row["post_push_remote_ci_remote_ref_guard_present"] = bool(
            post_push_remote_ci_commands
            and any(
                "git ls-remote --exit-code --heads origin" in command
                and row["draft_branch_name"] in command
                for command in post_push_remote_ci_commands
            )
            and any(
                "remote branch codex/pr38-ci-runner-hygiene is not published"
                in command
                for command in post_push_remote_ci_commands
            )
        )
        row["post_push_remote_ci_waits_for_expected_head_sha"] = bool(
            any("expected_head_sha=" in command for command in post_push_remote_ci_commands)
            and any(
                'grep -cx "${expected_head_sha}"' in command
                for command in post_push_remote_ci_commands
            )
            and any(
                "product_api_worker_run_count" in command
                for command in post_push_remote_ci_commands
            )
            and any(
                "product_image_smoke_run_count" in command
                for command in post_push_remote_ci_commands
            )
        )
        row["post_push_remote_ci_requires_all_dispatched_runs_observed"] = bool(
            any(
                '"${product_api_worker_run_count:-0}" -ge 1' in command
                for command in post_push_remote_ci_commands
            )
            and any(
                '"${product_image_smoke_run_count:-0}" -ge 2' in command
                for command in post_push_remote_ci_commands
            )
            and any(
                command.strip() == 'test "${product_api_worker_run_count:-0}" -ge 1'
                for command in post_push_remote_ci_commands
            )
            and any(
                command.strip() == 'test "${product_image_smoke_run_count:-0}" -ge 2'
                for command in post_push_remote_ci_commands
            )
        )
        post_push_run_list_commands = [
            command.strip()
            for command in post_push_remote_ci_commands
            if command.lstrip().startswith("gh run list ")
        ]
        row["post_push_remote_ci_branch_filter_uses_json_head_branch"] = bool(
            post_push_run_list_commands
            and all(
                "--json" in command
                and "--jq" in command
                and "headBranch" in command
                and "--branch" not in command
                for command in post_push_run_list_commands
            )
        )
        row["post_push_remote_ci_unsupported_branch_flag_present"] = bool(
            any("--branch" in command for command in post_push_run_list_commands)
        )
        row["launch_commands"] = "\n".join(_launch_commands(row, base_branch=base_branch))
        isolated_worktree_commands = _isolated_worktree_launch_commands(
            row,
            base_branch=base_branch,
        )
        row["isolated_worktree_launch_commands"] = "\n".join(
            isolated_worktree_commands
        )
        row["isolated_worktree_launch_command_count"] = len(
            isolated_worktree_commands
        )
        row["isolated_worktree_root"] = DEFAULT_ISOLATED_WORKTREE_ROOT
        row["isolated_worktree_launch_preserves_current_worktree"] = bool(
            any("git worktree add" in command for command in isolated_worktree_commands)
            and not any(command.startswith("git switch ") for command in isolated_worktree_commands)
            and any('repo_root="$(git rev-parse --show-toplevel)"' == command for command in isolated_worktree_commands)
        )
        row["isolated_worktree_launch_uses_absolute_patch_and_body_paths"] = bool(
            any('"${repo_root}/' in command and row["patch_path"] in command for command in isolated_worktree_commands)
            and any('"${repo_root}/' in command and row["pr_body_path"] in command for command in isolated_worktree_commands)
        )
        body_path.write_text(_body_text(row), encoding="utf-8")
        isolated_launch_script_path.write_text(
            _script_text(
                title=f"PR #38 {slice_id} isolated worktree launch",
                commands=row["isolated_worktree_launch_commands"],
            ),
            encoding="utf-8",
        )
        isolated_launch_script_path.chmod(0o644)
        if _text(row.get("post_push_remote_ci_commands")):
            row["post_push_remote_ci_script_path"] = _display(
                post_push_remote_ci_script_path,
                root=root_path,
            )
            row["post_push_remote_ci_script"] = row[
                "post_push_remote_ci_script_path"
            ]
            post_push_remote_ci_script_path.write_text(
                _script_text(
                    title=f"PR #38 {slice_id} post-push remote CI verification",
                    commands=row["post_push_remote_ci_commands"],
                ),
                encoding="utf-8",
            )
            post_push_remote_ci_script_path.chmod(0o644)
        rows.append(row)

    minimum_child_pr_count = int(
        plan_summary.get("minimum_child_pr_count")
        or acceptance_summary.get("minimum_child_pr_count")
        or MINIMUM_CHILD_PR_COUNT
    )
    empty_patch_slice_ids = [row["slice_id"] for row in rows if not row["patch_nonempty"]]
    command_pack_ready = bool(
        plan_summary.get("extraction_plan_ready") is True
        and patch_summary.get("patch_bundle_ready") is True
        and len(rows) >= minimum_child_pr_count
        and not missing_patch_slice_ids
        and not empty_patch_slice_ids
    )
    acceptance_packet_ready = bool(acceptance_summary.get("split_acceptance_ready") is True)
    acceptance_packet_blockers = _string_list(acceptance_summary.get("blockers"))
    acceptance_packet_primary_blocker = (
        _text(acceptance_summary.get("primary_blocker"))
        or (acceptance_packet_blockers[0] if acceptance_packet_blockers else "")
    )
    post_push_remote_ci_rows = [
        row for row in rows if row["post_push_remote_ci_verification_required"]
    ]
    post_push_remote_ci_command_count = sum(
        row["post_push_remote_ci_command_count"] for row in post_push_remote_ci_rows
    )
    isolated_worktree_launch_script_rows = [
        row for row in rows if _text(row.get("isolated_worktree_launch_script_path"))
    ]
    post_push_remote_ci_script_rows = [
        row for row in rows if _text(row.get("post_push_remote_ci_script_path"))
    ]
    launch_scripts_non_executable = bool(
        rows and all(row.get("launch_script_executable") is False for row in rows)
    )
    ci_runner_hygiene_row = next(
        (row for row in rows if row["slice_id"] == CI_RUNNER_HYGIENE_SLICE_ID),
        {},
    )
    bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path = bool(
        command_pack_ready
        and ci_runner_hygiene_row
        and int(ci_runner_hygiene_row.get("sequence") or 0) == 1
        and ci_runner_hygiene_row.get("patch_nonempty") is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_verification_required")
        is True
        and acceptance_summary.get("split_structural_acceptance_ready") is True
        and acceptance_packet_ready is False
        and (
            "release_ci_remote_green" in acceptance_packet_primary_blocker
            or any("release_ci_remote_green" in blocker for blocker in acceptance_packet_blockers)
            or acceptance_summary.get("product_mode_verification_ready") is False
        )
    )
    bootstrap_ci_runner_hygiene_launch_preconditions_ready = bool(
        bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path
        and ci_runner_hygiene_row.get("post_push_remote_ci_branch_filter_uses_json_head_branch")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_unsupported_branch_flag_present")
        is False
        and ci_runner_hygiene_row.get("post_push_remote_ci_dispatch_guard_present")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_remote_ref_guard_present")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_uses_isolated_worktree")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_bootstraps_local_evidence")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_syncs_local_evidence_back")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_rebuilds_root_release_gate")
        is True
        and ci_runner_hygiene_row.get("post_push_remote_ci_waits_for_expected_head_sha")
        is True
        and ci_runner_hygiene_row.get(
            "post_push_remote_ci_requires_all_dispatched_runs_observed"
        )
        is True
    )
    post_push_remote_ci_branch_filter_uses_json_head_branch = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_branch_filter_uses_json_head_branch"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_unsupported_branch_flag_present = any(
        row["post_push_remote_ci_unsupported_branch_flag_present"]
        for row in post_push_remote_ci_rows
    )
    post_push_remote_ci_dispatch_guard_present = bool(
        post_push_remote_ci_rows
        and all(row["post_push_remote_ci_dispatch_guard_present"] for row in post_push_remote_ci_rows)
    )
    post_push_remote_ci_remote_ref_guard_present = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_remote_ref_guard_present"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_uses_isolated_worktree = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_uses_isolated_worktree"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_bootstraps_local_evidence = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_bootstraps_local_evidence"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_syncs_local_evidence_back = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_syncs_local_evidence_back"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_rebuilds_root_release_gate = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_rebuilds_root_release_gate"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_waits_for_expected_head_sha = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_waits_for_expected_head_sha"]
            for row in post_push_remote_ci_rows
        )
    )
    post_push_remote_ci_requires_all_dispatched_runs_observed = bool(
        post_push_remote_ci_rows
        and all(
            row["post_push_remote_ci_requires_all_dispatched_runs_observed"]
            for row in post_push_remote_ci_rows
        )
    )
    isolated_worktree_launch_preserves_current_worktree = bool(
        rows
        and all(row["isolated_worktree_launch_preserves_current_worktree"] for row in rows)
    )
    isolated_worktree_launch_uses_absolute_patch_and_body_paths = bool(
        rows
        and all(
            row["isolated_worktree_launch_uses_absolute_patch_and_body_paths"]
            for row in rows
        )
    )
    operator_branch_pr_launch_preconditions_ready = bool(
        command_pack_ready and acceptance_packet_ready
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": (
            "pr38_child_pr_launch_command_pack_ready"
            if command_pack_ready
            else "blocked_pr38_child_pr_launch_command_pack"
        ),
        "launch_command_pack_ready": command_pack_ready,
        "extraction_plan_status": _text(plan_summary.get("status")) or "missing",
        "patch_bundle_status": _text(patch_summary.get("status")) or "missing",
        "acceptance_packet_status": _text(acceptance_summary.get("status")) or "missing",
        "acceptance_packet_ready": acceptance_packet_ready,
        "acceptance_packet_split_structural_acceptance_ready": bool(
            acceptance_summary.get("split_structural_acceptance_ready") is True
        ),
        "acceptance_packet_product_mode_verification_ready": bool(
            acceptance_summary.get("product_mode_verification_ready") is True
        ),
        "acceptance_packet_blocker_count": int(acceptance_summary.get("blocker_count") or 0),
        "acceptance_packet_primary_blocker": acceptance_packet_primary_blocker,
        "acceptance_packet_blockers": acceptance_packet_blockers,
        "child_pr_count": len(rows),
        "minimum_child_pr_count": minimum_child_pr_count,
        "minimum_child_pr_count_met": len(rows) >= minimum_child_pr_count,
        "body_file_count": len(rows),
        "isolated_worktree_launch_script_count": len(
            isolated_worktree_launch_script_rows
        ),
        "post_push_remote_ci_script_count": len(post_push_remote_ci_script_rows),
        "launch_scripts_non_executable": launch_scripts_non_executable,
        "missing_patch_slice_count": len(missing_patch_slice_ids),
        "missing_patch_slice_ids": missing_patch_slice_ids,
        "empty_patch_count": len(empty_patch_slice_ids),
        "empty_patch_slice_ids": empty_patch_slice_ids,
        "base_branch": base_branch,
        "out_dir": _display(body_dir, root=root_path),
        "operator_launch_requires_human_approval": True,
        "branch_commit_push_pr_mutation_required": True,
        "operator_branch_pr_launch_preconditions_ready": operator_branch_pr_launch_preconditions_ready,
        "operator_branch_pr_launch_allowed_by_this_packet": False,
        "operator_branch_pr_launch_blocked_by_acceptance_packet": not acceptance_packet_ready,
        "bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path": (
            bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path
        ),
        "bootstrap_ci_runner_hygiene_launch_preconditions_ready": (
            bootstrap_ci_runner_hygiene_launch_preconditions_ready
        ),
        "bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet": False,
        "bootstrap_ci_runner_hygiene_sequence": int(
            ci_runner_hygiene_row.get("sequence") or 0
        ),
        "bootstrap_ci_runner_hygiene_branch": _text(
            ci_runner_hygiene_row.get("draft_branch_name")
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_command_count": int(
            ci_runner_hygiene_row.get("post_push_remote_ci_command_count") or 0
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_dispatch_guard_present": bool(
            ci_runner_hygiene_row.get("post_push_remote_ci_dispatch_guard_present")
            is True
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_remote_ref_guard_present": bool(
            ci_runner_hygiene_row.get("post_push_remote_ci_remote_ref_guard_present")
            is True
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_uses_isolated_worktree": bool(
            ci_runner_hygiene_row.get("post_push_remote_ci_uses_isolated_worktree")
            is True
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_bootstraps_local_evidence": bool(
            ci_runner_hygiene_row.get("post_push_remote_ci_bootstraps_local_evidence")
            is True
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_syncs_local_evidence_back": bool(
            ci_runner_hygiene_row.get("post_push_remote_ci_syncs_local_evidence_back")
            is True
        ),
        "bootstrap_ci_runner_hygiene_post_push_remote_ci_rebuilds_root_release_gate": bool(
            ci_runner_hygiene_row.get("post_push_remote_ci_rebuilds_root_release_gate")
            is True
        ),
        "bootstrap_ci_runner_hygiene_isolated_worktree_launch_present": bool(
            _text(ci_runner_hygiene_row.get("isolated_worktree_launch_commands"))
        ),
        "bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree": bool(
            ci_runner_hygiene_row.get("isolated_worktree_launch_preserves_current_worktree")
            is True
        ),
        "post_push_remote_ci_verification_slice_count": len(post_push_remote_ci_rows),
        "post_push_remote_ci_command_count": post_push_remote_ci_command_count,
        "post_push_remote_ci_dispatch_required": bool(post_push_remote_ci_rows),
        "post_push_remote_ci_dispatch_guard_present": (
            post_push_remote_ci_dispatch_guard_present
        ),
        "post_push_remote_ci_remote_ref_guard_present": (
            post_push_remote_ci_remote_ref_guard_present
        ),
        "post_push_remote_ci_uses_isolated_worktree": (
            post_push_remote_ci_uses_isolated_worktree
        ),
        "post_push_remote_ci_bootstraps_local_evidence": (
            post_push_remote_ci_bootstraps_local_evidence
        ),
        "post_push_remote_ci_syncs_local_evidence_back": (
            post_push_remote_ci_syncs_local_evidence_back
        ),
        "post_push_remote_ci_rebuilds_root_release_gate": (
            post_push_remote_ci_rebuilds_root_release_gate
        ),
        "post_push_remote_ci_waits_for_expected_head_sha": (
            post_push_remote_ci_waits_for_expected_head_sha
        ),
        "post_push_remote_ci_requires_all_dispatched_runs_observed": (
            post_push_remote_ci_requires_all_dispatched_runs_observed
        ),
        "post_push_remote_ci_dispatch_executed_by_this_packet": False,
        "post_push_remote_ci_branch_filter_uses_json_head_branch": (
            post_push_remote_ci_branch_filter_uses_json_head_branch
        ),
        "post_push_remote_ci_unsupported_branch_flag_present": (
            post_push_remote_ci_unsupported_branch_flag_present
        ),
        "isolated_worktree_launch_preserves_current_worktree": (
            isolated_worktree_launch_preserves_current_worktree
        ),
        "isolated_worktree_launch_uses_absolute_patch_and_body_paths": (
            isolated_worktree_launch_uses_absolute_patch_and_body_paths
        ),
        "isolated_worktree_root": DEFAULT_ISOLATED_WORKTREE_ROOT,
        "shell_pack_prints_commands_only": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Human owner can use only the sequence-1 ci_runner_hygiene bootstrap commands after explicit approval to clear the remote CI runner-hygiene blocker; other child PR launches remain blocked until split acceptance is ready."
            if command_pack_ready
            and bootstrap_ci_runner_hygiene_launch_preconditions_ready
            else
            "Clear the split acceptance blockers before any branch/commit/push/PR launch; this pack is for command review only while acceptance is blocked."
            if command_pack_ready and not acceptance_packet_ready
            else "Human owner reviews this command pack; after explicit approval, create child branches/PRs in order and attach each focused test plus ai-verify result."
            if command_pack_ready
            else "Repair extraction-plan or patch-bundle gaps before preparing child PR launch commands."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# PR #38 Child PR Launch Command Pack",
        "",
        f"- status: `{s['status']}`",
        f"- launch_command_pack_ready: `{s['launch_command_pack_ready']}`",
        f"- child_pr_count: `{s['child_pr_count']}`",
        f"- minimum_child_pr_count: `{s['minimum_child_pr_count']}`",
        f"- acceptance_packet_status: `{s['acceptance_packet_status']}`",
        f"- acceptance_packet_ready: `{s['acceptance_packet_ready']}`",
        f"- acceptance_packet_blocker_count: `{s['acceptance_packet_blocker_count']}`",
        f"- acceptance_packet_primary_blocker: `{s['acceptance_packet_primary_blocker'] or '-'}`",
        f"- operator_branch_pr_launch_preconditions_ready: `{s['operator_branch_pr_launch_preconditions_ready']}`",
        f"- operator_branch_pr_launch_allowed_by_this_packet: `{s['operator_branch_pr_launch_allowed_by_this_packet']}`",
        f"- operator_branch_pr_launch_blocked_by_acceptance_packet: `{s['operator_branch_pr_launch_blocked_by_acceptance_packet']}`",
        f"- bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path: `{s['bootstrap_ci_runner_hygiene_acceptance_blocker_clearance_path']}`",
        f"- bootstrap_ci_runner_hygiene_launch_preconditions_ready: `{s['bootstrap_ci_runner_hygiene_launch_preconditions_ready']}`",
        f"- bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet: `{s['bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet']}`",
        f"- bootstrap_ci_runner_hygiene_branch: `{s['bootstrap_ci_runner_hygiene_branch'] or '-'}`",
        f"- bootstrap_ci_runner_hygiene_isolated_worktree_launch_present: `{s['bootstrap_ci_runner_hygiene_isolated_worktree_launch_present']}`",
        f"- bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree: `{s['bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree']}`",
        f"- post_push_remote_ci_verification_slice_count: `{s['post_push_remote_ci_verification_slice_count']}`",
        f"- post_push_remote_ci_command_count: `{s['post_push_remote_ci_command_count']}`",
        f"- post_push_remote_ci_dispatch_required: `{s['post_push_remote_ci_dispatch_required']}`",
        f"- post_push_remote_ci_dispatch_guard_present: `{s['post_push_remote_ci_dispatch_guard_present']}`",
        f"- post_push_remote_ci_remote_ref_guard_present: `{s['post_push_remote_ci_remote_ref_guard_present']}`",
        f"- post_push_remote_ci_uses_isolated_worktree: `{s['post_push_remote_ci_uses_isolated_worktree']}`",
        f"- post_push_remote_ci_bootstraps_local_evidence: `{s['post_push_remote_ci_bootstraps_local_evidence']}`",
        f"- post_push_remote_ci_syncs_local_evidence_back: `{s['post_push_remote_ci_syncs_local_evidence_back']}`",
        f"- post_push_remote_ci_rebuilds_root_release_gate: `{s['post_push_remote_ci_rebuilds_root_release_gate']}`",
        f"- post_push_remote_ci_waits_for_expected_head_sha: `{s['post_push_remote_ci_waits_for_expected_head_sha']}`",
        f"- post_push_remote_ci_requires_all_dispatched_runs_observed: `{s['post_push_remote_ci_requires_all_dispatched_runs_observed']}`",
        f"- post_push_remote_ci_dispatch_executed_by_this_packet: `{s['post_push_remote_ci_dispatch_executed_by_this_packet']}`",
        f"- isolated_worktree_launch_script_count: `{s['isolated_worktree_launch_script_count']}`",
        f"- post_push_remote_ci_script_count: `{s['post_push_remote_ci_script_count']}`",
        f"- launch_scripts_non_executable: `{s['launch_scripts_non_executable']}`",
        f"- isolated_worktree_launch_preserves_current_worktree: `{s['isolated_worktree_launch_preserves_current_worktree']}`",
        f"- isolated_worktree_launch_uses_absolute_patch_and_body_paths: `{s['isolated_worktree_launch_uses_absolute_patch_and_body_paths']}`",
        f"- operator_launch_requires_human_approval: `{s['operator_launch_requires_human_approval']}`",
        f"- shell_pack_prints_commands_only: `{s['shell_pack_prints_commands_only']}`",
        "",
        "| seq | slice | branch | patch | PR body | launch script |",
        "| --: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['sequence']} | `{row['slice_id']}` | `{row['draft_branch_name']}` | "
            f"`{row['patch_path']}` | `{row['pr_body_path']}` | "
            f"`{row['isolated_worktree_launch_script_path']}` |"
        )
    lines.extend(["", "## Commands", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['sequence']:02d} {row['slice_id']} isolated worktree launch",
                "",
                "```bash",
            ]
        )
        lines.extend(row["isolated_worktree_launch_commands"].splitlines())
        lines.extend(["```", ""])
        lines.extend([f"### {row['sequence']:02d} {row['slice_id']}", "", "```bash"])
        lines.extend(row["launch_commands"].splitlines())
        lines.extend(["```", ""])
        if _text(row.get("post_push_remote_ci_commands")):
            lines.extend(
                [
                    "Post-push remote verification commands:",
                    "",
                    "```bash",
                ]
            )
            lines.extend(row["post_push_remote_ci_commands"].splitlines())
            lines.extend(["```", ""])
    lines.extend(["## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_shell(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "cat <<'PR38_CHILD_PR_COMMANDS'",
        "# PR #38 child PR launch commands.",
        "# This script prints commands only; it intentionally does not execute branch, commit, push, or PR creation steps.",
        f"# acceptance_packet_status: {payload['summary']['acceptance_packet_status']}",
        f"# acceptance_packet_ready: {payload['summary']['acceptance_packet_ready']}",
        f"# launch_preconditions_ready: {payload['summary']['operator_branch_pr_launch_preconditions_ready']}",
        f"# launch_allowed_by_this_packet: {payload['summary']['operator_branch_pr_launch_allowed_by_this_packet']}",
        f"# bootstrap_ci_runner_hygiene_launch_preconditions_ready: {payload['summary']['bootstrap_ci_runner_hygiene_launch_preconditions_ready']}",
        f"# bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet: {payload['summary']['bootstrap_ci_runner_hygiene_operator_launch_allowed_by_this_packet']}",
        f"# bootstrap_ci_runner_hygiene_isolated_worktree_launch_present: {payload['summary']['bootstrap_ci_runner_hygiene_isolated_worktree_launch_present']}",
        f"# bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree: {payload['summary']['bootstrap_ci_runner_hygiene_isolated_worktree_preserves_current_worktree']}",
        f"# isolated_worktree_launch_preserves_current_worktree: {payload['summary']['isolated_worktree_launch_preserves_current_worktree']}",
        f"# isolated_worktree_launch_uses_absolute_patch_and_body_paths: {payload['summary']['isolated_worktree_launch_uses_absolute_patch_and_body_paths']}",
        f"# post_push_remote_ci_dispatch_required: {payload['summary']['post_push_remote_ci_dispatch_required']}",
        f"# post_push_remote_ci_dispatch_guard_present: {payload['summary']['post_push_remote_ci_dispatch_guard_present']}",
        f"# post_push_remote_ci_remote_ref_guard_present: {payload['summary']['post_push_remote_ci_remote_ref_guard_present']}",
        f"# post_push_remote_ci_uses_isolated_worktree: {payload['summary']['post_push_remote_ci_uses_isolated_worktree']}",
        f"# post_push_remote_ci_bootstraps_local_evidence: {payload['summary']['post_push_remote_ci_bootstraps_local_evidence']}",
        f"# post_push_remote_ci_syncs_local_evidence_back: {payload['summary']['post_push_remote_ci_syncs_local_evidence_back']}",
        f"# post_push_remote_ci_rebuilds_root_release_gate: {payload['summary']['post_push_remote_ci_rebuilds_root_release_gate']}",
        f"# post_push_remote_ci_waits_for_expected_head_sha: {payload['summary']['post_push_remote_ci_waits_for_expected_head_sha']}",
        f"# post_push_remote_ci_requires_all_dispatched_runs_observed: {payload['summary']['post_push_remote_ci_requires_all_dispatched_runs_observed']}",
        f"# post_push_remote_ci_dispatch_executed_by_this_packet: {payload['summary']['post_push_remote_ci_dispatch_executed_by_this_packet']}",
        f"# isolated_worktree_launch_script_count: {payload['summary']['isolated_worktree_launch_script_count']}",
        f"# post_push_remote_ci_script_count: {payload['summary']['post_push_remote_ci_script_count']}",
        f"# launch_scripts_non_executable: {payload['summary']['launch_scripts_non_executable']}",
        "# Do not run the printed branch/commit/push/PR commands until split acceptance is ready and the human owner explicitly approves launch.",
        "# Exception: the sequence-1 ci_runner_hygiene commands are the bootstrap blocker-clearance path, but still require explicit human approval before any mutation.",
        "# Prefer isolated worktree launch commands when the current PR #38 worktree has uncommitted or unrelated changes.",
        "# Do not run printed gh workflow commands until the matching child branch has been pushed.",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"# {row['sequence']:02d} {row['slice_id']} isolated worktree launch",
                row["isolated_worktree_launch_commands"],
                "",
            ]
        )
        lines.extend([f"# {row['sequence']:02d} {row['slice_id']}", row["launch_commands"], ""])
        if _text(row.get("post_push_remote_ci_commands")):
            lines.extend(
                [
                    f"# {row['sequence']:02d} {row['slice_id']} post-push remote verification",
                    row["post_push_remote_ci_commands"],
                    "",
                ]
            )
    lines.extend(["PR38_CHILD_PR_COMMANDS", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(0o644)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build PR #38 child PR launch command pack.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--extraction-plan-json", default=DEFAULT_EXTRACTION_PLAN_JSON)
    parser.add_argument("--patch-bundle-json", default=DEFAULT_PATCH_BUNDLE_JSON)
    parser.add_argument("--acceptance-packet-json", default=DEFAULT_ACCEPTANCE_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-sh", default=DEFAULT_OUT_SH)
    parser.add_argument("--base-branch", default="main")
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_child_pr_launch_command_pack(
        extraction_plan_json=args.extraction_plan_json,
        patch_bundle_json=args.patch_bundle_json,
        acceptance_packet_json=args.acceptance_packet_json,
        out_dir=args.out_dir,
        base_branch=args.base_branch,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    _write_shell(args.out_sh, payload, root=root)
    return 0 if payload["summary"]["launch_command_pack_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

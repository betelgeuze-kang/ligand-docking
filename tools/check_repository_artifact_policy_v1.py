#!/usr/bin/env python3
"""Reject new repository artifacts that belong in external storage.

The guard is forward-only: it inspects paths added or modified between an
explicit base and head.  It does not rewrite or reinterpret existing history.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

SCHEMA_ID = "betelgeuze.repository_artifact_policy/1.0.0"
POLICY_ID = "repository_forward_growth_guard_v1"


class ArtifactPolicyError(ValueError):
    """The policy, Git comparison, or changed path is invalid."""


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactPolicyError(f"cannot load policy: {exc}") from exc
    if type(value) is not dict:
        raise ArtifactPolicyError("artifact policy must be a JSON object")
    if value.get("schema_id") != SCHEMA_ID or value.get("policy_id") != POLICY_ID:
        raise ArtifactPolicyError("artifact policy identity changed")
    for key in ("max_file_bytes", "max_generated_text_bytes"):
        if type(value.get(key)) is not int or value[key] <= 0:
            raise ArtifactPolicyError(f"{key} must be a positive integer")
    for key in (
        "generated_text_suffixes",
        "forbidden_suffixes",
        "forbidden_path_prefixes",
        "allowlisted_exact_paths",
        "allowlisted_path_prefixes",
    ):
        rows = value.get(key)
        if type(rows) is not list or any(type(row) is not str or not row for row in rows):
            raise ArtifactPolicyError(f"{key} must contain non-empty strings")
        if len(rows) != len(set(rows)):
            raise ArtifactPolicyError(f"{key} contains duplicates")
    if value.get("history_rewrite_authorized") is not False:
        raise ArtifactPolicyError("history rewrite must remain unauthorized")
    if value.get("existing_repository_history_reinterpreted") is not False:
        raise ArtifactPolicyError("existing history cannot be reinterpreted")
    return value


def _run_git(root: Path, arguments: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise ArtifactPolicyError(f"git {' '.join(arguments)} failed: {detail}") from exc
    return completed.stdout


def _changed_paths(root: Path, base: str, head: str) -> tuple[str, ...]:
    output = _run_git(
        root,
        ["diff", "--name-only", "--diff-filter=AMCR", "-z", f"{base}...{head}"],
    )
    result: list[str] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        try:
            value = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ArtifactPolicyError("changed Git path is not valid UTF-8") from exc
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value.startswith("./"):
            raise ArtifactPolicyError(f"unsafe changed path: {value}")
        result.append(value)
    return tuple(sorted(set(result)))


def _blob_size(root: Path, head: str, path: str) -> int | None:
    try:
        output = _run_git(root, ["cat-file", "-s", f"{head}:{path}"])
    except ArtifactPolicyError:
        return None
    try:
        value = int(output.decode("ascii").strip())
    except (UnicodeError, ValueError) as exc:
        raise ArtifactPolicyError(f"invalid blob size for {path}") from exc
    if value < 0:
        raise ArtifactPolicyError(f"negative blob size for {path}")
    return value


def _tree_mode(root: Path, head: str, path: str) -> str | None:
    output = _run_git(root, ["ls-tree", head, "--", path]).decode(
        "utf-8", errors="strict"
    )
    if not output.strip():
        return None
    first = output.splitlines()[0]
    fields = first.split(None, 3)
    if len(fields) < 3:
        raise ArtifactPolicyError(f"invalid ls-tree output for {path}")
    return fields[0]


def _allowlisted(path: str, policy: dict[str, Any]) -> bool:
    if path in policy["allowlisted_exact_paths"]:
        return True
    return any(path.startswith(prefix) for prefix in policy["allowlisted_path_prefixes"])


def evaluate(root: Path, *, base: str, head: str, policy_path: Path) -> dict[str, Any]:
    root = root.resolve()
    policy = _load_policy(policy_path)
    paths = _changed_paths(root, base, head)
    violations: list[dict[str, Any]] = []
    observed: list[dict[str, Any]] = []

    for path in paths:
        mode = _tree_mode(root, head, path)
        size = _blob_size(root, head, path)
        if mode is None or size is None:
            continue
        row = {"path": path, "mode": mode, "size_bytes": size}
        observed.append(row)
        if _allowlisted(path, policy):
            continue
        lower = path.lower()
        if mode == "120000":
            violations.append({**row, "reason": "changed_symlink_forbidden"})
            continue
        forbidden_prefix = next(
            (prefix for prefix in policy["forbidden_path_prefixes"] if path.startswith(prefix)),
            None,
        )
        if forbidden_prefix is not None:
            violations.append(
                {
                    **row,
                    "reason": "forbidden_generated_path_prefix",
                    "matched": forbidden_prefix,
                }
            )
            continue
        forbidden_suffix = next(
            (suffix for suffix in policy["forbidden_suffixes"] if lower.endswith(suffix)),
            None,
        )
        if forbidden_suffix is not None:
            violations.append(
                {
                    **row,
                    "reason": "binary_or_archive_suffix_forbidden",
                    "matched": forbidden_suffix,
                }
            )
            continue
        generated_suffix = next(
            (
                suffix
                for suffix in policy["generated_text_suffixes"]
                if lower.endswith(suffix)
            ),
            None,
        )
        if generated_suffix is not None and size > policy["max_generated_text_bytes"]:
            violations.append(
                {
                    **row,
                    "reason": "generated_text_too_large",
                    "limit_bytes": policy["max_generated_text_bytes"],
                }
            )
            continue
        if size > policy["max_file_bytes"]:
            violations.append(
                {
                    **row,
                    "reason": "changed_file_too_large",
                    "limit_bytes": policy["max_file_bytes"],
                }
            )

    return {
        "schema_id": "betelgeuze.repository_artifact_policy_result/1.0.0",
        "policy_id": POLICY_ID,
        "base": base,
        "head": head,
        "changed_path_count": len(paths),
        "observed_blob_count": len(observed),
        "violation_count": len(violations),
        "violations": violations,
        "history_rewrite_performed": False,
        "passed": not violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument(
        "--policy",
        type=Path,
        default=root / "config/repository_artifact_policy_v1.json",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = evaluate(
            args.root,
            base=args.base,
            head=args.head,
            policy_path=args.policy,
        )
    except ArtifactPolicyError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

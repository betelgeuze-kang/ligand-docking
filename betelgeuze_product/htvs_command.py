from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

ENTRYPOINT = "tools/run_ligand_htvs_pipeline.py"
PYTHON_BIN = "python3"
SKIP_PROFILE_KEYS = {
    "version",
    "description",
    "retry",
    "build_hard_decoy_benchmark",
    "positive_count_sweep",
    "positive_counter_auto_augment",
    "product_eval_panel_repair",
}
SKIP_PROFILE_PREFIXES = ("hard_decoy_",)
TOP_LEVEL_ALIASES = {
    "require_rust_hip": "traj_require_rust_hip",
}
NESTED_SECTION_PREFIXES = {
    "smoke": {
        "max_ligands": "max_ligands_smoke",
        "replicas": "replicas_smoke",
        "jobs_per_target": "jobs_per_target_smoke",
        "traj_frames": "traj_frames_smoke",
        "max_jobs_score": "max_jobs_score_smoke",
    },
    "full": {
        "max_ligands": "max_ligands_full",
        "replicas": "replicas_full",
        "jobs_per_target": "jobs_per_target_full",
        "traj_frames": "traj_frames_full",
        "max_jobs_score": "max_jobs_score_full",
    },
}
GATE_ALIASES = {
    "enforce_operational_gate": "enforce_operational_gate",
    "enforce_strict_gate": "enforce_strict_gate",
    "strict_fail_fast": "strict_fail_fast",
    "gate_enforcement_mode": "gate_enforcement_mode",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _flag_for_dest(action: argparse.Action) -> str:
    for option in action.option_strings:
        if option.startswith("--") and not option.startswith("--no-"):
            return option
    return ""


def _no_flag_for_dest(action: argparse.Action) -> str:
    for option in action.option_strings:
        if option.startswith("--no-"):
            return option
    return ""


def _parser_actions_by_dest() -> dict[str, argparse.Action]:
    from tools.run_ligand_htvs_pipeline import build_parser

    return {
        str(action.dest): action
        for action in build_parser()._actions
        if str(action.dest) != "help" and any(opt.startswith("--") for opt in action.option_strings)
    }


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _add_action_value(parts: list[str], action: argparse.Action, value: Any) -> None:
    flag = _flag_for_dest(action)
    if not flag:
        return
    if isinstance(action, argparse.BooleanOptionalAction):
        if bool(value):
            parts.append(flag)
        else:
            no_flag = _no_flag_for_dest(action)
            parts.append(no_flag or flag)
        return
    if value is None:
        return
    text = _text(value)
    if text == "":
        return
    parts.extend([flag, text])


def _flatten_profile(profile: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    flat: dict[str, Any] = {}
    skipped: list[str] = []
    for key, value in profile.items():
        key_text = _text(key)
        if key_text in SKIP_PROFILE_KEYS or any(key_text.startswith(prefix) for prefix in SKIP_PROFILE_PREFIXES):
            skipped.append(key_text)
            continue
        if key_text in NESTED_SECTION_PREFIXES:
            if not isinstance(value, dict):
                skipped.append(key_text)
                continue
            for nested_key, dest in NESTED_SECTION_PREFIXES[key_text].items():
                if nested_key in value:
                    flat[dest] = value[nested_key]
            for nested_key in value:
                if nested_key not in NESTED_SECTION_PREFIXES[key_text]:
                    skipped.append(f"{key_text}.{nested_key}")
            continue
        if key_text == "gate":
            if not isinstance(value, dict):
                skipped.append(key_text)
                continue
            for nested_key, nested_value in value.items():
                nested_text = _text(nested_key)
                dest = GATE_ALIASES.get(nested_text, f"gate_{nested_text}")
                flat[dest] = nested_value
            continue
        flat[TOP_LEVEL_ALIASES.get(key_text, key_text)] = value
    return flat, skipped


def build_htvs_command_from_profile(
    profile: dict[str, Any],
    *,
    profile_json: str = "",
    out_prefix: str = "",
    python_bin: str = PYTHON_BIN,
) -> dict[str, Any]:
    actions = _parser_actions_by_dest()
    flat, skipped_keys = _flatten_profile(profile)
    if out_prefix:
        flat["out_prefix"] = out_prefix

    parts = [_text(python_bin) or PYTHON_BIN, ENTRYPOINT]
    rendered: list[str] = []
    unsupported: list[str] = []
    for dest in sorted(flat):
        action = actions.get(dest)
        if action is None:
            unsupported.append(dest)
            continue
        before = len(parts)
        _add_action_value(parts, action, flat[dest])
        if len(parts) > before:
            rendered.append(dest)

    argv = parts[2:]
    parser_error = ""
    try:
        _, unknown = _parse_known(argv)
    except ValueError as exc:
        unknown = []
        parser_error = _text(exc)
    command = " ".join(shlex.quote(part) for part in parts)
    return {
        "command": command,
        "parts": parts,
        "argv": argv,
        "profile_json": profile_json,
        "rendered_destinations": rendered,
        "rendered_count": len(rendered),
        "unsupported_profile_keys": unsupported,
        "skipped_profile_keys": skipped_keys,
        "unknown_args_after_render": unknown,
        "parser_error": parser_error,
        "parser_valid": len(unknown) == 0 and not parser_error,
    }


def build_htvs_command_from_profile_json(
    profile_json: str | Path,
    *,
    out_prefix: str = "",
    python_bin: str = PYTHON_BIN,
) -> dict[str, Any]:
    return build_htvs_command_from_profile(
        _read_json(profile_json),
        profile_json=str(profile_json),
        out_prefix=out_prefix,
        python_bin=python_bin,
    )


def _parse_known(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    from tools.run_ligand_htvs_pipeline import build_parser

    parser = build_parser()
    parser.exit = lambda status=0, message=None: (_ for _ in ()).throw(
        ValueError(_text(message) or f"argparse exit {status}")
    )
    parser.error = lambda message: (_ for _ in ()).throw(ValueError(_text(message)))
    return parser.parse_known_args(argv)

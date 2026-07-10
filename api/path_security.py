from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def confined_path(
    value: str | Path,
    root: str | Path,
    *,
    label: str,
    must_exist: bool = False,
) -> Path:
    root_path = Path(root).expanduser().resolve()
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root_path / candidate
    # Check the lexical path before resolving it.  Checking ``is_symlink`` on
    # the resolved target is too late because ``Path.resolve`` has already
    # erased the evidence that a symlink was traversed.
    lexical = Path(os.path.abspath(candidate))
    try:
        relative = lexical.relative_to(root_path)
    except ValueError as exc:
        raise PermissionError(f"{label} escapes configured root") from exc
    cursor = root_path
    for component in relative.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise PermissionError(f"{label} cannot traverse a symbolic link")
    resolved = candidate.resolve(strict=False)
    if resolved == root_path or root_path not in resolved.parents:
        raise PermissionError(f"{label} escapes configured root")
    if must_exist and (not resolved.exists() or not resolved.is_file()):
        raise FileNotFoundError(f"{label} is missing")
    return resolved


def looks_like_local_file_reference(value: Any, *, suffixes: tuple[str, ...]) -> bool:
    text = str(value or "").strip()
    if not text or "\n" in text or "\r" in text:
        return False
    path = Path(text)
    return bool(
        path.is_absolute()
        or text.startswith(("./", "../", "~"))
        or path.suffix.lower() in suffixes
    )


def normalize_operator_input_value(
    value: Any,
    *,
    suffixes: tuple[str, ...],
    local_paths_enabled: bool,
    input_root: str | Path,
    label: str,
) -> str:
    text = str(value or "")
    if not looks_like_local_file_reference(text, suffixes=suffixes):
        return text
    if not local_paths_enabled:
        raise PermissionError(f"{label} local path inputs are disabled; submit inline content or an upload reference")
    return str(confined_path(text, input_root, label=label, must_exist=True))


def normalize_tier_beta_request_paths(
    request_data: dict[str, Any],
    *,
    local_paths_enabled: bool,
    input_root: str | Path,
) -> dict[str, Any]:
    normalized = dict(request_data)
    params = dict(normalized.get("runner_profile_params") or {})
    protein_input = (
        params.get("protein_input")
        or params.get("pdb_content")
        or normalized.get("pdb_content")
        or params.get("pdb_path")
        or normalized.get("pdb_path")
        or ""
    )
    ligand_input = (
        params.get("ligand_input")
        or params.get("smiles")
        or params.get("sdf_content")
        or params.get("sdf_path")
        or ""
    )
    params["protein_input"] = normalize_operator_input_value(
        protein_input,
        suffixes=(".pdb", ".cif", ".mmcif"),
        local_paths_enabled=local_paths_enabled,
        input_root=input_root,
        label="protein_input",
    )
    params["ligand_input"] = normalize_operator_input_value(
        ligand_input,
        suffixes=(".sdf", ".mol", ".mol2", ".pdbqt"),
        local_paths_enabled=local_paths_enabled,
        input_root=input_root,
        label="ligand_input",
    )
    normalized["runner_profile_params"] = params
    return normalized

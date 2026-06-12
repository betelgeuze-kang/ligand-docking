from __future__ import annotations

import hashlib
import json
from typing import Any

SENSITIVE_SCALAR_KEYS = {
    "canonical_smiles",
    "inline_pdb",
    "isomeric_smiles",
    "ligand_smiles",
    "mol2_content",
    "pdb_content",
    "pdb_text",
    "pdbqt_content",
    "protein_pdb",
    "sdf_content",
    "smiles",
    "source_value",
    "structure_content",
    "target_pdb",
}
SENSITIVE_COLLECTION_KEYS = {"compound", "compounds", "ligand", "ligands"}
SENSITIVE_KEY_SUFFIXES = ("_pdb_content", "_pdb_text", "_smiles")


def _canonical_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _redaction_record(value: Any) -> dict[str, Any]:
    raw = _canonical_text(value)
    return {
        "redacted": True,
        "redaction": "sha256",
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else "",
        "byte_length": len(raw.encode("utf-8")),
    }


def _is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_SCALAR_KEYS or key.endswith(SENSITIVE_KEY_SUFFIXES)


def sanitize_request_for_ledger(value: Any, *, parent_key: str = "") -> Any:
    key = parent_key.lower()
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            child_key = str(raw_key)
            child_key_l = child_key.lower()
            if child_key_l.endswith("_sha256") or child_key_l == "request_sha256":
                sanitized[child_key] = raw_value
            elif _is_sensitive_key(child_key_l):
                sanitized[child_key] = _redaction_record(raw_value)
            else:
                sanitized[child_key] = sanitize_request_for_ledger(raw_value, parent_key=child_key)
        return sanitized
    if isinstance(value, list):
        return [sanitize_request_for_ledger(item, parent_key=parent_key) for item in value]
    if key in SENSITIVE_COLLECTION_KEYS and isinstance(value, str):
        return _redaction_record(value)
    return value

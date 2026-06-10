"""Optional external structure-metric adapters (MolProbity, OST/lDDT) with proxy fallback."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from core.structure_metrics import (
    STRUCTURE_METRICS_CLAIM_BOUNDARY,
    dockq_proxy,
    evaluate_structure_quality,
    lddt_pli_proxy,
    molprobity_clashscore_proxy,
    parse_pdb_atoms_with_coords,
    tm_score_proxy,
)

EXTERNAL_CLAIM_BOUNDARY = (
    "External metric adapters invoke locally installed tools when present. "
    "Absence of tools falls back to internal proxies; external parity is never implied without tool output."
)


def _which(name: str) -> str | None:
    return shutil.which(name)


def _write_temp_pdb(pdb_text: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8")
    tmp.write(pdb_text)
    tmp.close()
    return Path(tmp.name)


def _run_json_command(cmd: list[str], *, timeout_sec: int = 120) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=int(timeout_sec), check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def try_molprobity_clashscore(pdb_text: str) -> dict[str, Any]:
    """Attempt MolProbity clashscore via `phenix.clashscore` or proxy fallback."""
    proxy_atoms = parse_pdb_atoms_with_coords(pdb_text)
    coords = __import__("numpy").stack([a["xyz"] for a in proxy_atoms], axis=0) if proxy_atoms else None
    elements = [a.get("element", "C") for a in proxy_atoms]
    fallback = molprobity_clashscore_proxy(coords, elements) if coords is not None and coords.size else None
    cmd_name = _which("phenix.clashscore") or _which("clashscore")
    if not cmd_name:
        return {
            "metric": "molprobity_clashscore",
            "value": fallback,
            "source": "internal_proxy",
            "external_available": False,
            "claim_boundary": EXTERNAL_CLAIM_BOUNDARY,
        }
    pdb_path = _write_temp_pdb(pdb_text)
    try:
        proc = subprocess.run([cmd_name, str(pdb_path)], capture_output=True, text=True, timeout=120, check=False)
        value = None
        for line in (proc.stdout or "").splitlines():
            if "clashscore" in line.lower():
                parts = line.replace("=", " ").split()
                for part in parts:
                    try:
                        value = float(part)
                        break
                    except ValueError:
                        continue
        if value is None:
            value = fallback
            source = "internal_proxy"
        else:
            source = "external_tool"
        return {
            "metric": "molprobity_clashscore",
            "value": value,
            "source": source,
            "external_available": True,
            "tool": cmd_name,
            "claim_boundary": EXTERNAL_CLAIM_BOUNDARY,
        }
    finally:
        pdb_path.unlink(missing_ok=True)


def try_lddt_pli(model_pdb: str, reference_pdb: str) -> dict[str, Any]:
    """Attempt OST `ost compare-structures` lDDT-PLI or proxy fallback."""
    model_atoms = parse_pdb_atoms_with_coords(model_pdb)
    ref_atoms = parse_pdb_atoms_with_coords(reference_pdb)
    import numpy as np

    m = np.stack([a["xyz"] for a in model_atoms], axis=0) if model_atoms else np.zeros((0, 3))
    r = np.stack([a["xyz"] for a in ref_atoms], axis=0) if ref_atoms else np.zeros((0, 3))
    fallback = lddt_pli_proxy(m, r)
    ost = _which("ost") or _which("OpenStructure")
    if not ost:
        return {
            "metric": "lddt_pli",
            "value": fallback,
            "source": "internal_proxy",
            "external_available": False,
            "claim_boundary": EXTERNAL_CLAIM_BOUNDARY,
        }
    model_path = _write_temp_pdb(model_pdb)
    ref_path = _write_temp_pdb(reference_pdb)
    try:
        proc = subprocess.run(
            [ost, "compare-structures", "-m", str(model_path), "-r", str(ref_path)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        value = None
        for line in (proc.stdout or "").splitlines():
            low = line.lower()
            if "lddt" in low:
                parts = line.replace(":", " ").split()
                for part in reversed(parts):
                    try:
                        cand = float(part)
                        if 0.0 <= cand <= 1.0:
                            value = cand
                            break
                    except ValueError:
                        continue
        if value is None:
            value = fallback
            source = "internal_proxy"
        else:
            source = "external_tool"
        return {
            "metric": "lddt_pli",
            "value": value,
            "source": source,
            "external_available": True,
            "tool": ost,
            "claim_boundary": EXTERNAL_CLAIM_BOUNDARY,
        }
    finally:
        model_path.unlink(missing_ok=True)
        ref_path.unlink(missing_ok=True)


def evaluate_structure_quality_with_external(
    atoms: list[dict[str, Any]],
    *,
    pdb_text: str = "",
    reference_pdb_text: str = "",
) -> dict[str, Any]:
    """Proxy metrics plus optional external tool overlays."""
    quality = evaluate_structure_quality(atoms, reference_atoms=parse_pdb_atoms_with_coords(reference_pdb_text) if reference_pdb_text else None)
    quality["metric_sources"] = {"bundle": "internal_proxy", "claim_boundary": STRUCTURE_METRICS_CLAIM_BOUNDARY}
    if pdb_text:
        clash = try_molprobity_clashscore(pdb_text)
        quality["molprobity_clashscore"] = clash.get("value")
        quality["molprobity_clashscore_source"] = clash.get("source")
        quality["metric_sources"]["molprobity_clashscore"] = clash.get("source")
    if pdb_text and reference_pdb_text:
        lddt = try_lddt_pli(pdb_text, reference_pdb_text)
        quality["lddt_pli"] = lddt.get("value")
        quality["lddt_pli_source"] = lddt.get("source")
        quality["metric_sources"]["lddt_pli"] = lddt.get("source")
        import numpy as np

        m = np.stack([a["xyz"] for a in atoms], axis=0)
        r = np.stack([a["xyz"] for a in parse_pdb_atoms_with_coords(reference_pdb_text)], axis=0)
        quality["dockq_proxy"] = dockq_proxy(m, r)
        quality["tm_score_proxy"] = tm_score_proxy(m, r)
    return quality

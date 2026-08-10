#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
from typing import Any

from benchmarks.oracles.openmm import load_openmm
from tools.lib.artifacts import (
    artifact as _artifact,
    jsonable as _jsonable,
    read_csv as _read_csv,
    read_json as _read_json,
    resolve as _resolve,
    short_error as _short_error,
    text as _text,
    truthy as _truthy,
    write_json as _write_json,
)

DEFAULT_INPUT_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_full_forcefield_minimization_readiness_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_full_forcefield_minimization_readiness_current.md"
DEFAULT_TARGET = "CHEMBL217_DRD2_HUMAN"
DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"
DEFAULT_PARAMETERIZATION_PROBE_JSON = "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json"

CHIMERAX_AMBER14_ALL = (
    "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/lib/python3.11/"
    "site-packages/openmm/app/data/amber14-all.xml"
)
CHIMERAX_GAFF_XML = (
    "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/lib/python3.11/"
    "site-packages/chimerax/minimize/gaff-2.2.20.xml"
)
CHIMERAX_AMBERTOOLS_BIN = "tools/bin/chimerax/local_unpack/usr/lib/ucsf-chimerax/bin/amber20/bin"

OPTIONAL_DEPENDENCIES = (
    "openff",
    "openff.toolkit",
    "openmmforcefields",
    "pdbfixer",
    "parmed",
    "openbabel",
    "vina",
)


def _find_positive_row(rows: list[dict[str, str]], target: str, ligand_id: str) -> dict[str, str] | None:
    for row in rows:
        if _text(row.get("target")) == target and _text(row.get("ligand_id")) == ligand_id:
            return row
    for row in rows:
        if _truthy(row.get("is_positive")) or _text(row.get("ligand_id")) == ligand_id:
            return row
    return None


def _module_available(name: str) -> tuple[bool, str]:
    try:
        spec = importlib.util.find_spec(name)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if spec is None:
        return False, ""
    return True, _text(getattr(spec, "origin", "")) or "namespace"


def _dependency_status(overrides: dict[str, bool] | None = None) -> dict[str, dict[str, Any]]:
    overrides = dict(overrides or {})
    out: dict[str, dict[str, Any]] = {}
    for name in ("openmm", "rdkit", *OPTIONAL_DEPENDENCIES):
        if name in overrides:
            out[name] = {"available": bool(overrides[name]), "origin": "test_override" if overrides[name] else ""}
            continue
        available, origin = _module_available(name)
        out[name] = {"available": available, "origin": origin}
    return out


def _asset_status(asset_overrides: dict[str, str | Path] | None = None) -> dict[str, dict[str, Any]]:
    asset_overrides = dict(asset_overrides or {})
    ambertools_bin = _resolve(asset_overrides.get("ambertools_bin", CHIMERAX_AMBERTOOLS_BIN))
    assets = {
        "chimerax_amber14_all_xml": _resolve(asset_overrides.get("chimerax_amber14_all_xml", CHIMERAX_AMBER14_ALL)),
        "chimerax_gaff_xml": _resolve(asset_overrides.get("chimerax_gaff_xml", CHIMERAX_GAFF_XML)),
        "chimerax_antechamber": ambertools_bin / "antechamber",
        "chimerax_parmchk2": ambertools_bin / "parmchk2",
        "chimerax_sqm": ambertools_bin / "sqm",
        "chimerax_tleap": ambertools_bin / "tleap",
    }
    return {
        key: {"path": _artifact(path), "exists": path.exists(), "is_file": path.is_file()}
        for key, path in assets.items()
    }


def _probe_openmm_protein_build(protein_pdb: str) -> dict[str, Any]:
    if not protein_pdb:
        return {"attempted": False, "ready": False, "error": "protein_structure_source_path_missing"}
    path = _resolve(protein_pdb)
    if not path.exists():
        return {"attempted": False, "ready": False, "error": "protein_structure_source_path_not_found", "path": _artifact(path)}
    try:
        app = load_openmm().app
        ForceField = app.ForceField
        Modeller = app.Modeller
        NoCutoff = app.NoCutoff
        PDBFile = app.PDBFile

        pdb = PDBFile(str(path))
        forcefield = ForceField("amber14-all.xml")
        modeller = Modeller(pdb.topology, pdb.positions)
        try:
            modeller.addHydrogens(forcefield, pH=7.4)
            hydrogen_repair = "openmm_modeller_addHydrogens"
            topology = modeller.topology
        except Exception as exc:
            return {
                "attempted": True,
                "ready": False,
                "path": _artifact(path),
                "atom_count": sum(1 for _ in pdb.topology.atoms()),
                "residue_count": sum(1 for _ in pdb.topology.residues()),
                "repair_attempt": "openmm_modeller_addHydrogens",
                "error": _short_error(exc),
            }
        system = forcefield.createSystem(topology, nonbondedMethod=NoCutoff, constraints=None)
        return {
            "attempted": True,
            "ready": True,
            "path": _artifact(path),
            "hydrogen_repair": hydrogen_repair,
            "particle_count": system.getNumParticles(),
        }
    except Exception as exc:
        return {"attempted": True, "ready": False, "path": _artifact(path), "error": _short_error(exc)}


def _probe_ligand_template_build(ligand_pdb: str, gaff_xml: str | Path) -> dict[str, Any]:
    if not ligand_pdb:
        return {"attempted": False, "ready": False, "error": "backmapped_pdb_missing"}
    ligand_path = _resolve(ligand_pdb)
    if not ligand_path.exists():
        return {"attempted": False, "ready": False, "error": "backmapped_pdb_not_found", "path": _artifact(ligand_path)}
    gaff_path = _resolve(gaff_xml)
    if not gaff_path.exists():
        return {"attempted": False, "ready": False, "error": "gaff_xml_not_found", "path": _artifact(gaff_path)}
    try:
        app = load_openmm().app
        ForceField = app.ForceField
        NoCutoff = app.NoCutoff
        PDBFile = app.PDBFile

        pdb = PDBFile(str(ligand_path))
        forcefield = ForceField(str(gaff_path))
        system = forcefield.createSystem(pdb.topology, nonbondedMethod=NoCutoff, constraints=None)
        return {
            "attempted": True,
            "ready": True,
            "path": _artifact(ligand_path),
            "gaff_xml": _artifact(gaff_path),
            "particle_count": system.getNumParticles(),
            "note": "Unexpectedly created a ligand system directly from the supplied PDB and GAFF XML.",
        }
    except Exception as exc:
        return {
            "attempted": True,
            "ready": False,
            "path": _artifact(ligand_path),
            "gaff_xml": _artifact(gaff_path),
            "error": _short_error(exc),
        }


def _missing_from_status(status: dict[str, dict[str, Any]], names: list[str]) -> list[str]:
    return [name for name in names if not bool(status.get(name, {}).get("available"))]


def build_readiness(
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    target: str = DEFAULT_TARGET,
    ligand_id: str = DEFAULT_POSITIVE_LIGAND,
    attempt_build: bool = True,
    generated_at_local: str | None = None,
    dependency_overrides: dict[str, bool] | None = None,
    asset_overrides: dict[str, str | Path] | None = None,
    parameterization_probe_json: str | Path = DEFAULT_PARAMETERIZATION_PROBE_JSON,
) -> dict[str, Any]:
    generated_at_local = generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds")
    rows = _read_csv(input_csv)
    positive = _find_positive_row(rows, target, ligand_id)
    deps = _dependency_status(dependency_overrides)
    assets = _asset_status(asset_overrides)

    openmm_available = bool(deps["openmm"]["available"])
    rdkit_available = bool(deps["rdkit"]["available"])
    openff_available = bool(deps["openff"]["available"] or deps["openff.toolkit"]["available"])
    openmmforcefields_available = bool(deps["openmmforcefields"]["available"])
    pdbfixer_available = bool(deps["pdbfixer"]["available"])
    row_probe = {
        "target": _text(positive.get("target")) if positive else target,
        "ligand_id": _text(positive.get("ligand_id")) if positive else ligand_id,
        "row_found": positive is not None,
        "ligand_smiles": _text(positive.get("ligand_smiles") or positive.get("smiles")) if positive else "",
        "protein_structure_source_path": _artifact(positive.get("protein_structure_source_path", "")) if positive else "",
        "backmapped_pdb": _artifact(positive.get("backmapped_pdb", "")) if positive else "",
        "allatom_backmapping_status": _text(positive.get("allatom_backmapping_status")) if positive else "",
    }

    missing_dependencies = _missing_from_status(
        deps,
        ["openff.toolkit", "openmmforcefields", "pdbfixer", "parmed", "openbabel"],
    )
    missing_assets: list[str] = []
    if not bool(assets["chimerax_gaff_xml"]["exists"]):
        missing_assets.append("chimerax_gaff_xml")
    if not bool(assets["chimerax_amber14_all_xml"]["exists"]):
        missing_assets.append("chimerax_amber14_all_xml")
    if not bool(assets["chimerax_tleap"]["exists"]):
        missing_assets.append("chimerax_tleap")
    if positive is None:
        missing_assets.append("drd2_positive_repair_row")
    elif not _text(positive.get("backmapped_pdb")):
        missing_assets.append("drd2_positive_backmapped_pdb")

    protein_probe = {"attempted": False, "ready": False, "error": "build_attempt_disabled"}
    ligand_probe = {"attempted": False, "ready": False, "error": "build_attempt_disabled"}
    if attempt_build and openmm_available and positive is not None:
        protein_probe = _probe_openmm_protein_build(_text(positive.get("protein_structure_source_path")))
        ligand_probe = _probe_ligand_template_build(
            _text(positive.get("backmapped_pdb")),
            asset_overrides.get("chimerax_gaff_xml", CHIMERAX_GAFF_XML) if asset_overrides else CHIMERAX_GAFF_XML,
        )
    elif attempt_build and not openmm_available:
        protein_probe = {"attempted": False, "ready": False, "error": "openmm_missing"}
        ligand_probe = {"attempted": False, "ready": False, "error": "openmm_missing"}

    protein_parameterization_available = bool(protein_probe.get("ready"))
    ligand_template_generator_available = openff_available and openmmforcefields_available
    ambertools_partial_available = all(
        bool(assets[name]["exists"]) for name in ("chimerax_antechamber", "chimerax_parmchk2", "chimerax_sqm")
    )
    ligand_parameterization_available = bool(ligand_probe.get("ready") or ligand_template_generator_available)
    parameterization_probe = _read_json(parameterization_probe_json)
    probe_summary = parameterization_probe.get("summary", {}) if isinstance(parameterization_probe.get("summary"), dict) else {}
    probe_target = parameterization_probe.get("target_probe", {}) if isinstance(parameterization_probe.get("target_probe"), dict) else {}
    default_input = _resolve(input_csv) == _resolve(DEFAULT_INPUT_CSV)
    probe_matches = (
        default_input
        and _text(probe_target.get("target")) == target
        and _text(probe_target.get("ligand_id")) == ligand_id
    )
    integrated_parameterization_ready = bool(
        probe_matches
        and probe_summary.get("claim_grade_parameterization_ready")
        and probe_summary.get("integrated_system_parameterization_available")
    )
    if integrated_parameterization_ready:
        protein_parameterization_available = True
        ligand_parameterization_available = True

    if not integrated_parameterization_ready and not ligand_template_generator_available and "openff.toolkit" not in missing_dependencies:
        missing_dependencies.append("openff.toolkit")
    if not integrated_parameterization_ready and not ligand_template_generator_available and "openmmforcefields" not in missing_dependencies:
        missing_dependencies.append("openmmforcefields")
    if not integrated_parameterization_ready and not protein_parameterization_available and not pdbfixer_available and "pdbfixer" not in missing_dependencies:
        missing_dependencies.append("pdbfixer")
    if integrated_parameterization_ready:
        missing_dependencies = []
        missing_assets = [name for name in missing_assets if name != "chimerax_tleap"]

    full_ready = bool(
        openmm_available
        and rdkit_available
        and protein_parameterization_available
        and ligand_parameterization_available
        and positive is not None
    )

    if full_ready:
        status = "ready"
        next_required_step = (
            "Run claim-grade DRD2 full-forcefield local minimization with the positive repair row: "
            "use the integrated parameterization artifact from "
            f"{DEFAULT_PARAMETERIZATION_PROBE_JSON} before hard-decoy rebuild."
        )
    else:
        status = "blocked"
        next_required_step = (
            "Install/enable OpenFF Toolkit plus openmmforcefields for GAFF/SMIRNOFF template generation, "
            "install pdbfixer or provide a pre-repaired/protonated DRD2 protein PDB that OpenMM amber14 can parameterize, "
            "and provide a ligand residue template with charges/types; ChimeraX gaff-2.2.20.xml alone is not a ligand template."
        )
        if ambertools_partial_available and not bool(assets["chimerax_tleap"]["exists"]):
            next_required_step += " ChimeraX AmberTools has antechamber/parmchk2/sqm, but tleap is absent in the local bundle."

    claim_boundary = (
        "No broad/commercial or hard-decoy rebuild claim is opened unless one OpenMM System is actually parameterized "
        "for the DRD2 protein-ligand complex with real protein and ligand force-field templates. Bounded custom-force "
        "or ligand-only minimization remains non-claim-grade evidence."
    )

    summary = {
        "status": status,
        "full_forcefield_minimization_ready": full_ready,
        "openmm_available": openmm_available,
        "rdkit_available": rdkit_available,
        "ligand_parameterization_available": ligand_parameterization_available,
        "protein_parameterization_available": protein_parameterization_available,
        "integrated_parameterization_ready": integrated_parameterization_ready,
        "missing_dependencies": sorted(set(missing_dependencies)),
        "missing_assets": sorted(set(missing_assets)),
        "next_required_step": next_required_step,
        "claim_boundary": claim_boundary,
    }

    return {
        "packet_type": "gpcr_drd2_full_forcefield_minimization_readiness",
        "generated_at_local": generated_at_local,
        "input_csv": _artifact(input_csv),
        "summary": summary,
        "target_probe": row_probe,
        "dependency_status": deps,
        "asset_status": assets,
        "capability_probes": {
            "protein_openmm_amber14_build": protein_probe,
            "ligand_direct_gaff_xml_template_build": ligand_probe,
            "integrated_parameterization_probe": {
                "path": _artifact(parameterization_probe_json),
                "matched": probe_matches,
                "ready": integrated_parameterization_ready,
                "status": probe_summary.get("status"),
            },
            "ligand_template_generator_available": ligand_template_generator_available,
            "ambertools_partial_available": ambertools_partial_available,
            "chimerax_gaff_xml_has_parameters_but_no_ligand_residue_templates": True,
        },
        "safe_next_command_if_ready": (
            "python3 tools/build_gpcr_drd2_full_forcefield_minimization_readiness.py "
            f"--input-csv {DEFAULT_INPUT_CSV} --target {target} --ligand-id {ligand_id}"
            if full_ready
            else ""
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    probes = payload["capability_probes"]
    lines = [
        "# GPCR DRD2 Full-Forcefield Minimization Readiness",
        "",
        "## Summary",
    ]
    for key in (
        "status",
        "full_forcefield_minimization_ready",
        "openmm_available",
        "rdkit_available",
        "ligand_parameterization_available",
        "protein_parameterization_available",
        "integrated_parameterization_ready",
        "missing_dependencies",
        "missing_assets",
        "next_required_step",
        "claim_boundary",
    ):
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(
        [
            "",
            "## DRD2 Positive Probe",
            f"- target: `{payload['target_probe']['target']}`",
            f"- ligand_id: `{payload['target_probe']['ligand_id']}`",
            f"- row_found: `{payload['target_probe']['row_found']}`",
            f"- protein_structure_source_path: `{payload['target_probe']['protein_structure_source_path']}`",
            f"- backmapped_pdb: `{payload['target_probe']['backmapped_pdb']}`",
            "",
            "## Build Probes",
            f"- protein_openmm_amber14_build: `{probes['protein_openmm_amber14_build']}`",
            f"- ligand_direct_gaff_xml_template_build: `{probes['ligand_direct_gaff_xml_template_build']}`",
            f"- ligand_template_generator_available: `{probes['ligand_template_generator_available']}`",
            f"- ambertools_partial_available: `{probes['ambertools_partial_available']}`",
            "",
            "## Claim Boundary",
            "- This packet is a readiness probe, not claim authorization.",
            "- Full-forcefield readiness requires real protein parameterization and real ligand charge/type/template parameterization.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(payload: dict[str, Any], out_json: str | Path, out_md: str | Path) -> None:
    _write_json(out_json, payload)
    path = _resolve(out_md)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe DRD2 full-forcefield local-minimization readiness.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--ligand-id", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--no-attempt-build", action="store_true")
    args = parser.parse_args(argv)

    payload = build_readiness(
        input_csv=args.input_csv,
        target=args.target,
        ligand_id=args.ligand_id,
        attempt_build=not args.no_attempt_build,
    )
    write_outputs(payload, args.out_json, args.out_md)
    print(json.dumps(_jsonable(payload["summary"]), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

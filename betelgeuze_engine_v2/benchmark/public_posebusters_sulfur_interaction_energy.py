"""Preregister and execute a bounded neutral-thioether interaction-energy gate.

This module consumes the already-frozen sulfur QM-ESP and default-Vina
invariance receipts.  It binds three environment-matched neutral-thioether
models, a methanol O-H donor, fixed geometries, a Boys-Bernardi counterpoise
contract, and the exact AutoDock4 ``S-HD``/``SA-HD`` pair formulas before any
production interaction energy is calculated.

The result is deliberately narrow.  It can establish a local model-interaction
gate and compare AD4 pair-profile semantics.  It is not a representative
chemistry benchmark, a full AD4 score, a receptor/ligand calculation, or a
product-promotion receipt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Protocol

import numpy as np

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_external_preparation import _hash_regular_file
from . import public_posebusters_sulfur_qm_esp as qm_esp
from . import public_posebusters_vina_sulfur_type_invariance as vina_invariance


POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_protocol/1.0.0"
)
POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_observation/1.0.0"
)
POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_case/1.0.0"
)
POSEBUSTERS_SULFUR_INTERACTION_POINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_point/1.0.0"
)
POSEBUSTERS_SULFUR_INTERACTION_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_runtime/1.0.0"
)

POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR = 308
POSEBUSTERS_SULFUR_INTERACTION_MAX_PROTOCOL_BYTES = 8 * 1024 * 1024
POSEBUSTERS_SULFUR_INTERACTION_MAX_OBSERVATION_BYTES = 16 * 1024 * 1024
POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_FILE_BYTES = 64 * 1024 * 1024
POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_FILES = 4096
POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_BYTES = 256 * 1024 * 1024

POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_VERSION = "1.5.0"
POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_WHEEL_FILENAME = (
    "pyscf_dispersion-1.5.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
)
POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_WHEEL_SHA256 = (
    "c65aa46f24005794bf8198205a0d83f3431a23333868fbafff43bd82efc2294d"
)
POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_PYPI_URL = (
    "https://pypi.org/project/pyscf-dispersion/1.5.0/"
)

POSEBUSTERS_SULFUR_INTERACTION_SCOPE = {
    "7CIJ_G0C": {
        "environment": "aliphatic_thioether",
        "model_id": "dimethyl_sulfide",
        "source_smiles_atom_index": 2,
    },
    "7LT0_ONJ": {
        "environment": "diaryl_thioether",
        "model_id": "diphenyl_sulfide",
        "source_smiles_atom_index": 6,
    },
    "7NLV_UJE": {
        "environment": "cyclic_thioether",
        "model_id": "tetrahydrothiophene",
        "source_smiles_atom_index": 8,
    },
}
POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS = tuple(
    sorted(POSEBUSTERS_SULFUR_INTERACTION_SCOPE)
)

# Coordinates are a preregistered artifact, not a runtime conformer search.
# They were generated once with RDKit 2025.09.6 ETKDGv3 and MMFF94s using the
# recorded seed and then stored as exact binary64 values.
POSEBUSTERS_SULFUR_INTERACTION_MODELS = {
    "dimethyl_sulfide": {
        "canonical_isomeric_smiles": "CSC",
        "generation": {
            "embedder": "RDKit_ETKDGv3",
            "force_field": "MMFF94s",
            "maximum_iterations": 1000,
            "nonbonded_threshold_angstrom": float(100.0).hex(),
            "rdkit_version": "2025.09.6",
            "seed": 112358,
            "status": "converged",
        },
        "sulfur_atom_index": 1,
        "sulfur_neighbor_atom_indices": [0, 2],
        "atoms": [
            [
                "C",
                "-0x1.54939d7d44b37p+0",
                "-0x1.064adc041f47fp-2",
                "-0x1.ad54909cfebfbp-3",
            ],
            [
                "S",
                "-0x1.4fdff79a8315cp-6",
                "0x1.8179232096e1bp-1",
                "-0x1.e25776dff0d0dp-1",
            ],
            [
                "C",
                "0x1.5458afc7286cep+0",
                "0x1.281f32180cc74p-2",
                "0x1.58aadbaec93ccp-3",
            ],
            [
                "H",
                "-0x1.21035dd6f2347p+1",
                "-0x1.a4fa36d8ea0fep-4",
                "-0x1.88ff9cfeb747fp-1",
            ],
            [
                "H",
                "-0x1.112200998f6abp+0",
                "-0x1.50e01939bcbb4p+0",
                "-0x1.08594422ed1a3p-2",
            ],
            [
                "H",
                "-0x1.7f9ea34ee6cf6p+0",
                "0x1.1be793578b4b2p-5",
                "0x1.a9420bc683332p-1",
            ],
            [
                "H",
                "0x1.1e8447a280d5ep+1",
                "0x1.a35c474e2d15bp-1",
                "-0x1.07994756a4fd9p-3",
            ],
            [
                "H",
                "0x1.84daf4e51e514p+0",
                "-0x1.924ed1ed2803ep-1",
                "0x1.bf9073dc25377p-4",
            ],
            [
                "H",
                "0x1.165e4900c0f4fp+0",
                "0x1.21303c8d8b4b3p-1",
                "0x1.32b02d5fa6b6cp+0",
            ],
        ],
    },
    "diphenyl_sulfide": {
        "canonical_isomeric_smiles": "c1ccc(Sc2ccccc2)cc1",
        "generation": {
            "embedder": "RDKit_ETKDGv3",
            "force_field": "MMFF94s",
            "maximum_iterations": 1000,
            "nonbonded_threshold_angstrom": float(100.0).hex(),
            "rdkit_version": "2025.09.6",
            "seed": 271828,
            "status": "converged",
        },
        "sulfur_atom_index": 4,
        "sulfur_neighbor_atom_indices": [3, 5],
        "atoms": [
            [
                "C",
                "-0x1.ca8f01db85afdp+1",
                "0x1.6f083d5bc7eb8p-2",
                "0x1.bafc08619b5c2p-1",
            ],
            [
                "C",
                "-0x1.569aea2539ff6p+1",
                "-0x1.5524b81a70963p-1",
                "0x1.224d1f6d62a74p+0",
            ],
            [
                "C",
                "-0x1.96319b5eac264p+0",
                "-0x1.c09a59cbeab71p-1",
                "0x1.251dd05b8b389p-2",
            ],
            [
                "C",
                "-0x1.647450e46f0e4p+0",
                "-0x1.d10e5eb3f240ap-5",
                "-0x1.a9a0576e88a9dp-1",
            ],
            [
                "S",
                "-0x1.18180c801fbe5p-6",
                "-0x1.39f8f81f67d76p-2",
                "-0x1.f0d864ad0c02ep+0",
            ],
            [
                "C",
                "0x1.608b2074a2ea7p+0",
                "-0x1.bcfc5b651f125p-3",
                "-0x1.a926e6874da9dp-1",
            ],
            [
                "C",
                "0x1.9681c8112e7edp+0",
                "0x1.cbbf439f97d37p-1",
                "-0x1.8517c3cd921eap-7",
            ],
            [
                "C",
                "0x1.589dccd6a83e7p+1",
                "0x1.e55de6eea9d33p-1",
                "0x1.aee61bb6519f5p-1",
            ],
            [
                "C",
                "0x1.cc500de700982p+1",
                "-0x1.cd10edea59f7ep-4",
                "0x1.c0851a8b28249p-1",
            ],
            [
                "C",
                "0x1.b3128a666afebp+1",
                "-0x1.38d93d4965896p+0",
                "0x1.c785aa2063f1bp-5",
            ],
            [
                "C",
                "0x1.25ae14de98db3p+1",
                "-0x1.45ddc1df54304p+0",
                "-0x1.986424022f381p-1",
            ],
            [
                "C",
                "-0x1.27e4c10b5451dp+1",
                "0x1.ecf585d5299c9p-1",
                "-0x1.19993cbf3298ap+0",
            ],
            [
                "C",
                "-0x1.b36e8db66a085p+1",
                "0x1.2bfe409aab08fp+0",
                "-0x1.0247f61ac6409p-2",
            ],
            [
                "H",
                "-0x1.1b9e5991c93c7p+2",
                "0x1.0a70bccbe90b0p-1",
                "0x1.863fd3598c644p+0",
            ],
            [
                "H",
                "-0x1.68c6d4cda7f44p+1",
                "-0x1.4e006052dc3c7p+0",
                "0x1.004660cbabb65p+1",
            ],
            [
                "H",
                "-0x1.c8dccdae33ee0p-1",
                "-0x1.aeefae7f0dd32p+0",
                "0x1.0341119d305a0p-1",
            ],
            [
                "H",
                "0x1.ca5e38ad485fbp-1",
                "0x1.bc5c1f46562ffp+0",
                "-0x1.005ef064aa53bp-5",
            ],
            [
                "H",
                "0x1.6c6d80ad8677bp+1",
                "0x1.d0ece977b76c7p+0",
                "0x1.7a1fd3d0cd381p+0",
            ],
            [
                "H",
                "0x1.1d37622db2888p+2",
                "-0x1.28dac16591b79p-4",
                "0x1.8a0ea9e8f79f7p+0",
            ],
            [
                "H",
                "0x1.06c929730ef60p+2",
                "-0x1.060f126900c68p+1",
                "0x1.3c48efae80431p-4",
            ],
            [
                "H",
                "0x1.13e4daae3d356p+1",
                "-0x1.12498e53493f8p+1",
                "-0x1.6f62c9698a9f3p+0",
            ],
            [
                "H",
                "-0x1.17c0843c8dd6bp+1",
                "0x1.9a35f8c7a5aa4p+0",
                "-0x1.f8694453b6434p+0",
            ],
            [
                "H",
                "-0x1.0712273be6132p+2",
                "0x1.f7bbc7b687182p+0",
                "-0x1.dd7259b7ce7b8p-2",
            ],
        ],
    },
    "tetrahydrothiophene": {
        "canonical_isomeric_smiles": "C1CCSC1",
        "generation": {
            "embedder": "RDKit_ETKDGv3",
            "force_field": "MMFF94s",
            "maximum_iterations": 1000,
            "nonbonded_threshold_angstrom": float(100.0).hex(),
            "rdkit_version": "2025.09.6",
            "seed": 314159,
            "status": "converged",
        },
        "sulfur_atom_index": 3,
        "sulfur_neighbor_atom_indices": [2, 4],
        "atoms": [
            [
                "C",
                "-0x1.8e445f7a9dc5bp-1",
                "-0x1.46d8298526dc0p-1",
                "0x1.ccf689c23ff0bp-3",
            ],
            [
                "C",
                "0x1.1c18dbaf97f42p-1",
                "-0x1.6a6d51b5cf76fp-1",
                "-0x1.0230026021b2bp-1",
            ],
            [
                "C",
                "0x1.6ccf9f03fae24p+0",
                "0x1.903074182d417p-2",
                "0x1.4f721b6fa05fbp-4",
            ],
            [
                "S",
                "0x1.2e13d6df9cf2ap-2",
                "0x1.c7ed17219dfddp+0",
                "0x1.7a33a43025fd6p-2",
            ],
            [
                "C",
                "-0x1.39cd579b9e42ep+0",
                "0x1.9fcec19a2fccep-1",
                "0x1.57328f9e219bdp-3",
            ],
            [
                "H",
                "-0x1.500a274da912bp-1",
                "-0x1.eb7d6406e5534p-1",
                "0x1.44719d91e7879p+0",
            ],
            [
                "H",
                "-0x1.8554124c29cfbp+0",
                "-0x1.4c511b6373eb4p+0",
                "-0x1.e07aa7b536867p-3",
            ],
            [
                "H",
                "0x1.06abde20603cdp+0",
                "-0x1.b056813190b05p+0",
                "-0x1.8a14512439705p-2",
            ],
            [
                "H",
                "0x1.a0b6664fefbe3p-2",
                "-0x1.175e0a3137440p-1",
                "-0x1.94608e1c878d9p+0",
            ],
            [
                "H",
                "0x1.1e440fe228ce3p+1",
                "0x1.59759e9249194p-1",
                "-0x1.2fe13d9366e77p-1",
            ],
            [
                "H",
                "0x1.dae9a329a7aecp+0",
                "0x1.53ace4093540cp-4",
                "0x1.0a3f1d0549259p+0",
            ],
            [
                "H",
                "-0x1.aae9c0e8fdcb0p+0",
                "0x1.0c930dcda3fcbp+0",
                "-0x1.9c497961afb4ep-1",
            ],
            [
                "H",
                "-0x1.f379cf011a42bp+0",
                "0x1.0c4ed102710b2p+0",
                "0x1.e6d0d70130e8fp-1",
            ],
        ],
    },
}

POSEBUSTERS_SULFUR_INTERACTION_DONOR = {
    "model_id": "methanol_oh_donor",
    "canonical_isomeric_smiles": "CO",
    "donor_heavy_atom_index": 1,
    "donor_hydrogen_atom_index": 5,
    "reference_frame": "donor_H_origin_O_positive_z_C_projection_positive_x",
    "generation": {
        "embedder": "RDKit_ETKDGv3",
        "force_field": "MMFF94s",
        "maximum_iterations": 1000,
        "nonbonded_threshold_angstrom": float(100.0).hex(),
        "rdkit_version": "2025.09.6",
        "seed": 161803,
        "status": "converged",
    },
    "atoms": [
        ["C", "0x1.5a6c5ad40ebf6p+0", "0x1.4000000000000p-59", "0x1.636f1bae235d8p+0"],
        ["O", "0x0.0p+0", "-0x1.0000000000000p-61", "0x1.f1d7d258a360ep-1"],
        ["H", "0x1.63a6dc6e6a6c8p+0", "0x1.6101f2f888000p-20", "0x1.3d7c12d7c59c5p+1"],
        ["H", "0x1.da11fc5413c65p+0", "-0x1.ca834f59c7328p-1", "0x1.027388af2579ap+0"],
        ["H", "0x1.da1204de73f3ep+0", "0x1.ca831ee96e98fp-1", "0x1.0273621f35a03p+0"],
        ["H", "0x0.0p+0", "0x0.0p+0", "0x0.0p+0"],
    ],
}

_SCAN_DISTANCES_ANGSTROM = (2.0, 2.25, 2.5, 2.75, 3.0, 5.0)
_CONTROL_DISTANCE_ANGSTROM = 2.5
_HARTREE_TO_KCAL_PER_MOL = 627.5094740631

_AD4_PARAMETERS = {
    "cutoff_angstrom": 8.0,
    "smoothing_angstrom": 0.5,
    "cap_kcal_per_mol": 100000.0,
    "S": {
        "radius_angstrom": 2.0,
        "depth_kcal_per_mol": 0.2,
        "hb_depth_kcal_per_mol": 0.0,
        "hb_radius_angstrom": 0.0,
    },
    "SA": {
        "radius_angstrom": 2.0,
        "depth_kcal_per_mol": 0.2,
        "hb_depth_kcal_per_mol": -1.0,
        "hb_radius_angstrom": 2.5,
    },
    "HD": {
        "radius_angstrom": 1.0,
        "depth_kcal_per_mol": 0.02,
        "hb_depth_kcal_per_mol": 1.0,
        "hb_radius_angstrom": 0.0,
    },
    "weight_ad4_vdw": 0.1662,
    "weight_ad4_hb": 0.1209,
}

POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION = {
    "all_case_denominator": POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR,
    "scope_case_ids": list(POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS),
    "scope": POSEBUSTERS_SULFUR_INTERACTION_SCOPE,
    "acceptor_models": POSEBUSTERS_SULFUR_INTERACTION_MODELS,
    "donor_model": POSEBUSTERS_SULFUR_INTERACTION_DONOR,
    "geometry": {
        "acceptor_model_optimization_during_execution": False,
        "donor_model_optimization_during_execution": False,
        "complex_optimization": False,
        "primary_axis": (
            "least_sterically_occluded_of_two_idealized_tetrahedral_"
            "lone_pair_axes_selected_at_2.5_angstrom_without_energy"
        ),
        "control_axis": "positive_CSC_plane_normal",
        "donor_twist_reference": "projected_external_CSC_bisector",
        "scan_s_h_distances_angstrom_binary64_hex": [
            value.hex() for value in _SCAN_DISTANCES_ANGSTROM
        ],
        "control_s_h_distance_angstrom_binary64_hex": (
            _CONTROL_DISTANCE_ANGSTROM.hex()
        ),
    },
    "qm": {
        "basis": "def2-svp",
        "basis_cartesian": False,
        "boys_bernardi_counterpoise": True,
        "charge": 0,
        "density_fitting": True,
        "density_fitting_auxbasis": "def2-universal-jkfit",
        "direct_scf_tol": float(1.0e-12).hex(),
        "dispersion": "D3_Becke_Johnson_two_body",
        "dft_grid": {
            "alignment": 8,
            "becke_scheme": "pyscf.dft.gen_grid.original_becke",
            "level": 2,
            "prune": "pyscf.dft.gen_grid.nwchem_prune",
            "radi_method": "pyscf.dft.radi.treutler_ahlrichs",
            "radii_adjust": "pyscf.dft.radi.treutler_atomic_radii_adjust",
            "sort_grids": None,
        },
        "functional": "B3LYP-D3(BJ)",
        "initial_guess": "minao",
        "libxc_and_pyscf_code": "b3lyp-d3bj",
        "max_cycle": 150,
        "max_memory_mb": 4096,
        "scf_conv_tol": float(1.0e-9).hex(),
        "scf_conv_tol_grad": float(1.0e-5).hex(),
        "spin": 0,
        "threads": 1,
    },
    "ad4_pair_semantics": _AD4_PARAMETERS,
    "metrics": {
        "qm": [
            "counterpoise_interaction_energy_kcal_per_mol",
            "far_referenced_well_depth_kcal_per_mol",
            "minimum_distance_angstrom",
            "orientation_control_delta_kcal_per_mol",
            "scf_cycle_count",
            "dispersion_energy_hartree",
        ],
        "ad4": [
            "weighted_S_HD_vdw_profile",
            "weighted_SA_HD_hbond_profile",
            "far_referenced_normalized_rmse",
            "spearman_profile_correlation",
            "minimum_distance_error_angstrom",
        ],
    },
    "decision_contract": {
        "binding_minimum_at_most_kcal_per_mol": float(-1.0).hex(),
        "far_referenced_well_depth_at_most_kcal_per_mol": float(-0.5).hex(),
        "minimum_distance_allowed_angstrom": [
            float(2.0).hex(),
            float(3.0).hex(),
        ],
        "sa_normalized_rmse_improvement_margin": float(0.02).hex(),
        "case_acceptor_support_requires_all_binding_gates": True,
        "local_three_model_acceptor_gate_requires_case_count": 3,
        "ad4_sa_profile_gate_requires_preferred_case_count": 3,
        "chemical_acceptor_semantics_adjudicated": False,
        "product_promotion_allowed": False,
    },
    "literature_rationale": [
        {
            "doi": "10.1063/1.1588291",
            "role": "coupled_cluster_dimethylsulfide_methanol_reference",
        },
        {
            "doi": "10.1039/D2OB01602H",
            "role": "sulfur_non_covalent_interaction_methods_review",
        },
        {
            "doi": "10.1002/cphc.202300561",
            "role": "thioether_water_bsse_and_sapt_reference",
        },
    ],
}

POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION
)

POSEBUSTERS_SULFUR_INTERACTION_SCIENTIFIC_BLOCKERS = (
    "one_oh_donor_probe_does_not_cover_nh_or_other_donor_classes",
    "three_environment_models_are_not_full_posebusters_ligands",
    "fixed_model_geometries_are_not_an_optimized_complex_ensemble",
    "gas_phase_model_interactions_do_not_include_receptor_or_solvent_context",
    "ad4_pair_term_is_not_a_complete_ad4_score",
    "no_representative_chemistry_confidence_interval",
    "second_cpu_host_reproduction_missing",
    "independent_scientific_review_missing",
)


class PoseBustersSulfurInteractionError(ValueError):
    """The sulfur interaction protocol, runtime, input, or receipt is invalid."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PoseBustersSulfurInteractionError(f"{name} must be lowercase SHA-256")
    return value


def _utc_timestamp(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersSulfurInteractionError(f"{name} must be text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PoseBustersSulfurInteractionError(f"{name} must be RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PoseBustersSulfurInteractionError(f"{name} must be UTC")
    normalized = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if normalized != value:
        raise PoseBustersSulfurInteractionError(f"{name} must use canonical UTC form")
    return value


def _float_hex(value: float, *, name: str) -> str:
    result = float(value)
    if not math.isfinite(result):
        raise PoseBustersSulfurInteractionError(f"{name} must be finite")
    return result.hex()


def _normalized_error(error: BaseException) -> bytes:
    return " ".join(str(error).split()).encode("utf-8")[:4096]


def _write_private_no_overwrite(
    payload: Mapping[str, Any],
    output_path: str | os.PathLike[str],
) -> None:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = -1
    try:
        descriptor = os.open(
            output,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(_canonical_bytes(dict(payload)) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise PoseBustersSulfurInteractionError(
            f"receipt already exists: {output}"
        ) from exc
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _read_private_canonical_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_schema_id: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    expected = _digest(
        expected_receipt_sha256,
        name="expected receipt",
    )
    path = Path(receipt_path)
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size < 3
            or metadata.st_size > maximum_bytes
        ):
            raise PoseBustersSulfurInteractionError(
                "receipt must be a bounded private regular file"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            source = handle.read(maximum_bytes + 1)
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise PoseBustersSulfurInteractionError(
            "receipt cannot be read safely"
        ) from exc
    if len(source) > maximum_bytes or not source.endswith(b"\n"):
        raise PoseBustersSulfurInteractionError(
            "receipt is oversized or not newline terminated"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersSulfurInteractionError(
            "receipt is not canonical JSON"
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_id") != expected_schema_id
        or raw.get("receipt_sha256") != expected
    ):
        raise PoseBustersSulfurInteractionError(
            "receipt schema or payload identity disagrees"
        )
    payload = dict(raw)
    payload.pop("receipt_sha256")
    if _canonical_sha256(payload) != expected:
        raise PoseBustersSulfurInteractionError("receipt payload digest is invalid")
    if source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersSulfurInteractionError("receipt is not in canonical encoding")
    return raw, source


def _implementation_source_members() -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    modules = {
        "public_posebusters_sulfur_interaction_energy.py": sys.modules[__name__],
        "public_posebusters_sulfur_qm_esp.py": qm_esp,
        "public_posebusters_vina_sulfur_type_invariance.py": vina_invariance,
    }
    for relative_path, module in sorted(modules.items()):
        module_path = getattr(module, "__file__", None)
        if not isinstance(module_path, str) or not module_path:
            raise PoseBustersSulfurInteractionError(
                f"{relative_path} source path is unavailable"
            )
        members.append(
            {
                "relative_path": relative_path,
                "sha256": _source_file_sha256(module_path),
            }
        )
    return members


def _model_arrays(
    model_id: str,
) -> tuple[tuple[str, ...], np.ndarray, int, tuple[int, int]]:
    raw = POSEBUSTERS_SULFUR_INTERACTION_MODELS.get(model_id)
    if not isinstance(raw, dict):
        raise PoseBustersSulfurInteractionError("model identifier is invalid")
    atoms = raw.get("atoms")
    if not isinstance(atoms, list) or not atoms:
        raise PoseBustersSulfurInteractionError("model atom rows are invalid")
    symbols: list[str] = []
    coordinates: list[list[float]] = []
    for atom in atoms:
        if not isinstance(atom, list) or len(atom) != 4 or not isinstance(atom[0], str):
            raise PoseBustersSulfurInteractionError("model atom row is invalid")
        try:
            coordinate = [float.fromhex(str(value)) for value in atom[1:]]
        except (TypeError, ValueError) as exc:
            raise PoseBustersSulfurInteractionError(
                "model coordinate is invalid"
            ) from exc
        if not all(math.isfinite(value) for value in coordinate):
            raise PoseBustersSulfurInteractionError("model coordinate must be finite")
        symbols.append(atom[0])
        coordinates.append(coordinate)
    sulfur = raw.get("sulfur_atom_index")
    neighbors = raw.get("sulfur_neighbor_atom_indices")
    if (
        not isinstance(sulfur, int)
        or not isinstance(neighbors, list)
        or len(neighbors) != 2
        or not all(isinstance(value, int) for value in neighbors)
        or sulfur < 0
        or sulfur >= len(symbols)
        or any(value < 0 or value >= len(symbols) for value in neighbors)
        or symbols[sulfur] != "S"
        or any(symbols[value] != "C" for value in neighbors)
    ):
        raise PoseBustersSulfurInteractionError("model sulfur topology is invalid")
    return (
        tuple(symbols),
        np.asarray(coordinates, dtype=np.float64, order="C"),
        sulfur,
        (neighbors[0], neighbors[1]),
    )


def _donor_arrays() -> tuple[tuple[str, ...], np.ndarray, int]:
    atoms = POSEBUSTERS_SULFUR_INTERACTION_DONOR["atoms"]
    symbols = tuple(str(row[0]) for row in atoms)
    coordinates = np.asarray(
        [[float.fromhex(str(value)) for value in row[1:]] for row in atoms],
        dtype=np.float64,
        order="C",
    )
    donor_hydrogen = int(
        POSEBUSTERS_SULFUR_INTERACTION_DONOR["donor_hydrogen_atom_index"]
    )
    if (
        coordinates.shape != (len(symbols), 3)
        or not np.isfinite(coordinates).all()
        or symbols[donor_hydrogen] != "H"
        or not np.array_equal(
            coordinates[donor_hydrogen],
            np.zeros(3, dtype=np.float64),
        )
    ):
        raise PoseBustersSulfurInteractionError("donor reference geometry is invalid")
    return symbols, coordinates, donor_hydrogen


def _unit_vector(value: np.ndarray, *, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if vector.shape != (3,) or not math.isfinite(norm) or norm <= 1.0e-12:
        raise PoseBustersSulfurInteractionError(f"{name} is degenerate")
    return np.asarray(vector / norm, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class _AcceptorFrame:
    sulfur_coordinate: np.ndarray
    external_bisector: np.ndarray
    plane_normal: np.ndarray
    lone_pair_positive: np.ndarray
    lone_pair_negative: np.ndarray


def _acceptor_frame(
    coordinates: np.ndarray,
    sulfur_index: int,
    neighbor_indices: tuple[int, int],
) -> _AcceptorFrame:
    sulfur = np.asarray(coordinates[sulfur_index], dtype=np.float64)
    first = _unit_vector(
        coordinates[neighbor_indices[0]] - sulfur,
        name="first sulfur bond",
    )
    second = _unit_vector(
        coordinates[neighbor_indices[1]] - sulfur,
        name="second sulfur bond",
    )
    cosine = float(np.dot(first, second))
    if not -0.99 < cosine < 0.99:
        raise PoseBustersSulfurInteractionError("C-S-C geometry is degenerate")
    external = _unit_vector(-(first + second), name="external bisector")
    normal = _unit_vector(np.cross(first, second), name="C-S-C plane normal")
    half_angle_cosine = math.sqrt(max(0.0, (1.0 + cosine) * 0.5))
    lone_pair_bisector_component = 1.0 / (3.0 * half_angle_cosine)
    if not 0.0 < lone_pair_bisector_component < 1.0:
        raise PoseBustersSulfurInteractionError(
            "idealized lone-pair construction is invalid"
        )
    lone_pair_normal_component = math.sqrt(1.0 - lone_pair_bisector_component**2)
    positive = _unit_vector(
        lone_pair_bisector_component * external + lone_pair_normal_component * normal,
        name="positive lone-pair axis",
    )
    negative = _unit_vector(
        lone_pair_bisector_component * external - lone_pair_normal_component * normal,
        name="negative lone-pair axis",
    )
    return _AcceptorFrame(
        sulfur_coordinate=sulfur,
        external_bisector=external,
        plane_normal=normal,
        lone_pair_positive=positive,
        lone_pair_negative=negative,
    )


def _probe_coordinates(
    frame: _AcceptorFrame,
    axis: np.ndarray,
    distance_angstrom: float,
) -> np.ndarray:
    z_axis = _unit_vector(axis, name="probe approach axis")
    x_candidate = (
        frame.external_bisector
        - float(np.dot(frame.external_bisector, z_axis)) * z_axis
    )
    if float(np.linalg.norm(x_candidate)) <= 1.0e-10:
        x_candidate = (
            frame.plane_normal - float(np.dot(frame.plane_normal, z_axis)) * z_axis
        )
    x_axis = _unit_vector(x_candidate, name="probe twist axis")
    y_axis = _unit_vector(
        np.cross(z_axis, x_axis),
        name="probe secondary twist axis",
    )
    _symbols, reference, donor_hydrogen = _donor_arrays()
    origin = frame.sulfur_coordinate + float(distance_angstrom) * z_axis
    placed = (
        origin[None, :]
        + reference[:, 0, None] * x_axis[None, :]
        + reference[:, 1, None] * y_axis[None, :]
        + reference[:, 2, None] * z_axis[None, :]
    )
    if not np.array_equal(placed[donor_hydrogen], origin):
        raise PoseBustersSulfurInteractionError("donor hydrogen placement is not exact")
    return np.asarray(placed, dtype=np.float64, order="C")


def _minimum_interfragment_distance(
    acceptor_coordinates: np.ndarray,
    probe_coordinates: np.ndarray,
) -> float:
    distances = np.linalg.norm(
        acceptor_coordinates[:, None, :] - probe_coordinates[None, :, :],
        axis=2,
    )
    result = float(np.min(distances))
    if not math.isfinite(result) or result <= 0.0:
        raise PoseBustersSulfurInteractionError(
            "complex geometry has invalid interfragment separation"
        )
    return result


def _selected_primary_axis(
    frame: _AcceptorFrame,
    acceptor_coordinates: np.ndarray,
) -> tuple[str, np.ndarray, dict[str, str]]:
    candidates = {
        "lone_pair_positive": frame.lone_pair_positive,
        "lone_pair_negative": frame.lone_pair_negative,
    }
    clearances: dict[str, float] = {}
    for label, axis in candidates.items():
        probe = _probe_coordinates(
            frame,
            axis,
            _CONTROL_DISTANCE_ANGSTROM,
        )
        clearances[label] = _minimum_interfragment_distance(
            acceptor_coordinates,
            probe,
        )
    selected = sorted(
        candidates,
        key=lambda label: (-clearances[label], label),
    )[0]
    return (
        selected,
        candidates[selected],
        {
            label: _float_hex(value, name=f"{label} clearance")
            for label, value in sorted(clearances.items())
        },
    )


def _array_identity(value: np.ndarray, *, name: str) -> dict[str, Any]:
    array = np.asarray(value, dtype="<f8", order="C")
    if array.ndim != 2 or array.shape[1] != 3 or not np.isfinite(array).all():
        raise PoseBustersSulfurInteractionError(f"{name} array is invalid")
    payload = array.tobytes(order="C")
    return {
        "dtype": "<f8",
        "shape": list(array.shape),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _geometry_bindings(model_id: str) -> dict[str, Any]:
    symbols, acceptor, sulfur, neighbors = _model_arrays(model_id)
    donor_symbols, _reference, donor_hydrogen = _donor_arrays()
    frame = _acceptor_frame(acceptor, sulfur, neighbors)
    selected_label, selected_axis, clearances = _selected_primary_axis(
        frame,
        acceptor,
    )
    points: list[dict[str, Any]] = []
    for distance in _SCAN_DISTANCES_ANGSTROM:
        probe = _probe_coordinates(frame, selected_axis, distance)
        complex_coordinates = np.concatenate((acceptor, probe), axis=0)
        points.append(
            {
                "geometry_id": f"primary_{distance.hex()}",
                "orientation": selected_label,
                "distance_angstrom_binary64_hex": distance.hex(),
                "acceptor_coordinates": _array_identity(
                    acceptor,
                    name="acceptor coordinates",
                ),
                "probe_coordinates": _array_identity(
                    probe,
                    name="probe coordinates",
                ),
                "complex_coordinates": _array_identity(
                    complex_coordinates,
                    name="complex coordinates",
                ),
                "minimum_interfragment_distance_angstrom_binary64_hex": (
                    _minimum_interfragment_distance(acceptor, probe).hex()
                ),
            }
        )
    control_probe = _probe_coordinates(
        frame,
        frame.plane_normal,
        _CONTROL_DISTANCE_ANGSTROM,
    )
    points.append(
        {
            "geometry_id": "control_plane_normal_0x1.4000000000000p+1",
            "orientation": "positive_CSC_plane_normal",
            "distance_angstrom_binary64_hex": (_CONTROL_DISTANCE_ANGSTROM.hex()),
            "acceptor_coordinates": _array_identity(
                acceptor,
                name="acceptor coordinates",
            ),
            "probe_coordinates": _array_identity(
                control_probe,
                name="control probe coordinates",
            ),
            "complex_coordinates": _array_identity(
                np.concatenate((acceptor, control_probe), axis=0),
                name="control complex coordinates",
            ),
            "minimum_interfragment_distance_angstrom_binary64_hex": (
                _minimum_interfragment_distance(
                    acceptor,
                    control_probe,
                ).hex()
            ),
        }
    )
    return {
        "model_id": model_id,
        "model_spec_sha256": _canonical_sha256(
            POSEBUSTERS_SULFUR_INTERACTION_MODELS[model_id]
        ),
        "donor_model_id": POSEBUSTERS_SULFUR_INTERACTION_DONOR["model_id"],
        "donor_spec_sha256": _canonical_sha256(POSEBUSTERS_SULFUR_INTERACTION_DONOR),
        "acceptor_atom_count": len(symbols),
        "probe_atom_count": len(donor_symbols),
        "sulfur_atom_index": sulfur,
        "donor_hydrogen_atom_index": donor_hydrogen,
        "selected_primary_axis": selected_label,
        "primary_axis_binary64_hex": [value.hex() for value in selected_axis],
        "control_axis_binary64_hex": [value.hex() for value in frame.plane_normal],
        "candidate_clearance_angstrom_binary64_hex": clearances,
        "point_count": len(points),
        "points": points,
    }


def _smoothen(distance: float, equilibrium: float, smoothing: float) -> float:
    half = smoothing * 0.5
    if distance > equilibrium + half:
        return distance - half
    if distance < equilibrium - half:
        return distance + half
    return equilibrium


def _ad4_pair_terms(distance_angstrom: float) -> dict[str, str]:
    distance = float(distance_angstrom)
    cutoff = float(_AD4_PARAMETERS["cutoff_angstrom"])
    if not math.isfinite(distance) or distance <= 0.0:
        raise PoseBustersSulfurInteractionError(
            "AD4 pair distance must be positive and finite"
        )
    if distance >= cutoff:
        raw_s_vdw = 0.0
        raw_sa_hb = 0.0
    else:
        sulfur = _AD4_PARAMETERS["S"]
        acceptor = _AD4_PARAMETERS["SA"]
        donor_h = _AD4_PARAMETERS["HD"]
        smoothing = float(_AD4_PARAMETERS["smoothing_angstrom"])
        cap = float(_AD4_PARAMETERS["cap_kcal_per_mol"])

        vdw_rij = float(sulfur["radius_angstrom"]) + float(donor_h["radius_angstrom"])
        vdw_depth = math.sqrt(
            float(sulfur["depth_kcal_per_mol"]) * float(donor_h["depth_kcal_per_mol"])
        )
        vdw_distance = _smoothen(distance, vdw_rij, smoothing)
        raw_s_vdw = min(
            cap,
            (vdw_rij**12 * vdw_depth) / vdw_distance**12
            - (2.0 * vdw_rij**6 * vdw_depth) / vdw_distance**6,
        )

        hb_rij = float(acceptor["hb_radius_angstrom"]) + float(
            donor_h["hb_radius_angstrom"]
        )
        hb_depth = float(acceptor["hb_depth_kcal_per_mol"]) * float(
            donor_h["hb_depth_kcal_per_mol"]
        )
        hb_distance = _smoothen(distance, hb_rij, smoothing)
        raw_sa_hb = min(
            cap,
            (hb_rij**12 * -hb_depth * 10.0 / 2.0) / hb_distance**12
            - (hb_rij**10 * -hb_depth * 12.0 / 2.0) / hb_distance**10,
        )
    weighted_s = raw_s_vdw * float(_AD4_PARAMETERS["weight_ad4_vdw"])
    weighted_sa = raw_sa_hb * float(_AD4_PARAMETERS["weight_ad4_hb"])
    return {
        "distance_angstrom_binary64_hex": distance.hex(),
        "raw_S_HD_vdw_kcal_per_mol_binary64_hex": raw_s_vdw.hex(),
        "weighted_S_HD_vdw_kcal_per_mol_binary64_hex": weighted_s.hex(),
        "raw_SA_HD_hbond_kcal_per_mol_binary64_hex": raw_sa_hb.hex(),
        "weighted_SA_HD_hbond_kcal_per_mol_binary64_hex": weighted_sa.hex(),
        "weighted_SA_minus_S_kcal_per_mol_binary64_hex": (
            weighted_sa - weighted_s
        ).hex(),
    }


def _ad4_source_binding(
    source_root: str | os.PathLike[str],
) -> dict[str, Any]:
    try:
        root = Path(source_root).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersSulfurInteractionError(
            "Vina source root is unavailable"
        ) from exc
    if not root.is_dir():
        raise PoseBustersSulfurInteractionError("Vina source root is not a directory")
    required = {
        "src/lib/atom_constants.h",
        "src/lib/potentials.h",
        "src/lib/scoring_function.h",
        "src/lib/vina.h",
    }
    expected_files = (
        vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_FILES
    )
    if not required.issubset(expected_files):
        raise PoseBustersSulfurInteractionError(
            "frozen Vina source inventory is incomplete"
        )
    members: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    for relative_path in sorted(required):
        path = root.joinpath(*PurePosixPath(relative_path).parts)
        digest, size, _mode = _hash_regular_file(
            path,
            maximum_bytes=(
                vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_SOURCE_BYTES
            ),
        )
        expected = str(expected_files[relative_path])
        if digest != expected:
            raise PoseBustersSulfurInteractionError(
                f"{relative_path} does not match the frozen Vina tag"
            )
        try:
            texts[relative_path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise PoseBustersSulfurInteractionError(
                f"{relative_path} cannot be read as UTF-8"
            ) from exc
        members.append(
            {
                "relative_path": relative_path,
                "sha256": digest,
                "size_bytes": size,
            }
        )
    atom_constants = texts["src/lib/atom_constants.h"]
    potentials = texts["src/lib/potentials.h"]
    scoring = texts["src/lib/scoring_function.h"]
    vina_header = texts["src/lib/vina.h"]
    required_markers = {
        "atom_constants": (
            '{ "S", 2.00000, 0.20000, 0.0, 0.0,',
            '{"SA", 2.00000, 0.20000,-1.0, 2.5,',
            '{"HD", 1.00000, 0.02000, 1.0, 0.0,',
        ),
        "potentials": (
            "class ad4_vdw : public Potential",
            "class ad4_hb : public Potential",
            "smoothing *= 0.5;",
            "fl c_12 = int_pow<12>(hb_rij) * -hb_depth * 10 / 2.0;",
            "fl c_10 = int_pow<10>(hb_rij) * -hb_depth * 12 / 2.0;",
        ),
        "scoring": (
            "m_potentials.push_back(new ad4_vdw(0.5, 100000, 8.0));",
            "m_potentials.push_back(new ad4_hb(0.5, 100000, 8.0));",
            "m_atom_typing = atom_type::AD;",
        ),
        "weights": (
            "void set_ad4_weights(double weight_ad4_vdw=0.1662, "
            "double weight_ad4_hb=0.1209,",
        ),
    }
    if (
        not all(
            marker in atom_constants for marker in required_markers["atom_constants"]
        )
        or not all(marker in potentials for marker in required_markers["potentials"])
        or not all(marker in scoring for marker in required_markers["scoring"])
        or not all(marker in vina_header for marker in required_markers["weights"])
    ):
        raise PoseBustersSulfurInteractionError(
            "Vina AD4 source semantics failed exact marker validation"
        )
    return {
        "repository_url": (
            vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_URL
        ),
        "version": (vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_VERSION),
        "commit": (
            vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_COMMIT
        ),
        "source_members": members,
        "source_members_sha256": _canonical_sha256(members),
        "validated_semantics": {
            "S_HD_uses_ad4_vdw": True,
            "SA_HD_uses_ad4_hbond": True,
            "smoothing_full_width_angstrom_binary64_hex": float(0.5).hex(),
            "S_HD_vdw_equilibrium_angstrom_binary64_hex": float(3.0).hex(),
            "SA_HD_hbond_equilibrium_angstrom_binary64_hex": float(2.5).hex(),
            "weight_ad4_vdw_binary64_hex": float(0.1662).hex(),
            "weight_ad4_hb_binary64_hex": float(0.1209).hex(),
        },
    }


def _wheel_binding(
    wheel_path: str | os.PathLike[str],
    *,
    expected_sha256: str,
    expected_filename: str,
    name: str,
) -> dict[str, Any]:
    expected = _digest(expected_sha256, name=f"expected {name} wheel")
    path = Path(wheel_path)
    digest, size, _mode = _hash_regular_file(
        path,
        maximum_bytes=POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_FILE_BYTES,
    )
    if path.name != expected_filename or digest != expected:
        raise PoseBustersSulfurInteractionError(
            f"{name} wheel filename or digest is not frozen"
        )
    try:
        content_sha, file_count, content_size = qm_esp._wheel_content_manifest(path)
    except ValueError as exc:
        raise PoseBustersSulfurInteractionError(
            f"{name} wheel content is invalid"
        ) from exc
    return {
        "filename": path.name,
        "sha256": digest,
        "size_bytes": size,
        "content_sha256": content_sha,
        "content_file_count": file_count,
        "content_size_bytes": content_size,
    }


def _case_rows_by_id(
    receipt: Mapping[str, Any],
    *,
    name: str,
) -> dict[str, dict[str, Any]]:
    rows = receipt.get("case_rows")
    if not isinstance(rows, list) or len(rows) != 308:
        raise PoseBustersSulfurInteractionError(f"{name} must retain 308 case rows")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PoseBustersSulfurInteractionError(f"{name} case row is invalid")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in result:
            raise PoseBustersSulfurInteractionError(
                f"{name} case identifiers are invalid"
            )
        result[case_id] = row
    if tuple(result) != tuple(sorted(result)):
        raise PoseBustersSulfurInteractionError(f"{name} case rows are not canonical")
    return result


def _chain_receipts(
    qm_protocol_path: str | os.PathLike[str],
    qm_observation_path: str | os.PathLike[str],
    vina_protocol_path: str | os.PathLike[str],
    vina_observation_path: str | os.PathLike[str],
    *,
    expected_qm_protocol_sha256: str,
    expected_qm_observation_sha256: str,
    expected_vina_protocol_sha256: str,
    expected_vina_observation_sha256: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
]:
    qm_protocol, qm_protocol_source = _read_private_canonical_receipt(
        qm_protocol_path,
        expected_receipt_sha256=expected_qm_protocol_sha256,
        expected_schema_id=qm_esp.POSEBUSTERS_SULFUR_QM_ESP_PROTOCOL_SCHEMA_ID,
        maximum_bytes=qm_esp.POSEBUSTERS_SULFUR_QM_ESP_MAX_PROTOCOL_BYTES,
    )
    qm_observation, qm_observation_source = _read_private_canonical_receipt(
        qm_observation_path,
        expected_receipt_sha256=expected_qm_observation_sha256,
        expected_schema_id=(qm_esp.POSEBUSTERS_SULFUR_QM_ESP_OBSERVATION_SCHEMA_ID),
        maximum_bytes=qm_esp.POSEBUSTERS_SULFUR_QM_ESP_MAX_OBSERVATION_BYTES,
    )
    vina_protocol, vina_protocol_source = _read_private_canonical_receipt(
        vina_protocol_path,
        expected_receipt_sha256=expected_vina_protocol_sha256,
        expected_schema_id=(
            vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID
        ),
        maximum_bytes=(
            vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_PROTOCOL_BYTES
        ),
    )
    vina_observation, vina_observation_source = _read_private_canonical_receipt(
        vina_observation_path,
        expected_receipt_sha256=expected_vina_observation_sha256,
        expected_schema_id=(
            vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID
        ),
        maximum_bytes=(
            vina_invariance.POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_OBSERVATION_BYTES
        ),
    )
    if (
        qm_observation.get("protocol_receipt_sha256")
        != qm_protocol.get("receipt_sha256")
        or vina_observation.get("protocol_receipt_sha256")
        != vina_protocol.get("receipt_sha256")
        or not qm_observation.get("independent_qm_reference_executed")
        or not qm_observation.get("all_scoped_cases_evaluated")
        or not vina_observation.get("default_vina_fixed_pose_score_invariance_pass")
        or not vina_observation.get("bounded_default_vina_invariance_claim_safe")
        or any(
            receipt.get("all_case_denominator") != 308
            for receipt in (
                qm_protocol,
                qm_observation,
                vina_protocol,
                vina_observation,
            )
        )
    ):
        raise PoseBustersSulfurInteractionError(
            "upstream scientific receipt chain is not eligible"
        )
    file_hashes = {
        "qm_protocol_file_sha256": hashlib.sha256(qm_protocol_source).hexdigest(),
        "qm_observation_file_sha256": hashlib.sha256(qm_observation_source).hexdigest(),
        "vina_protocol_file_sha256": hashlib.sha256(vina_protocol_source).hexdigest(),
        "vina_observation_file_sha256": hashlib.sha256(
            vina_observation_source
        ).hexdigest(),
    }
    return (
        qm_protocol,
        qm_observation,
        vina_protocol,
        vina_observation,
        file_hashes,
    )


def _protocol_case_rows(
    qm_protocol: Mapping[str, Any],
    qm_observation: Mapping[str, Any],
    vina_protocol: Mapping[str, Any],
    vina_observation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    qm_protocol_rows = _case_rows_by_id(qm_protocol, name="QM protocol")
    qm_observation_rows = _case_rows_by_id(
        qm_observation,
        name="QM observation",
    )
    vina_protocol_rows = _case_rows_by_id(
        vina_protocol,
        name="Vina protocol",
    )
    vina_observation_rows = _case_rows_by_id(
        vina_observation,
        name="Vina observation",
    )
    identifiers = tuple(qm_protocol_rows)
    if any(
        tuple(rows) != identifiers
        for rows in (
            qm_observation_rows,
            vina_protocol_rows,
            vina_observation_rows,
        )
    ):
        raise PoseBustersSulfurInteractionError(
            "upstream receipts do not share one denominator"
        )
    result: list[dict[str, Any]] = []
    for case_id in identifiers:
        base = {
            "schema_id": POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
            "case_id": case_id,
        }
        if case_id not in POSEBUSTERS_SULFUR_INTERACTION_SCOPE:
            result.append(
                {
                    **base,
                    "status": "abstain_protocol_scope",
                    "disposition_code": (
                        "outside_preregistered_neutral_thioether_scope"
                    ),
                }
            )
            continue
        scope = POSEBUSTERS_SULFUR_INTERACTION_SCOPE[case_id]
        qm_protocol_row = qm_protocol_rows[case_id]
        qm_observation_row = qm_observation_rows[case_id]
        vina_protocol_row = vina_protocol_rows[case_id]
        vina_observation_row = vina_observation_rows[case_id]
        qm_target = qm_observation_row.get("target_sulfur")
        vina_target = vina_observation_row.get("target_comparison")
        if (
            qm_protocol_row.get("status") != "registered"
            or qm_observation_row.get("status") != "evaluated"
            or vina_protocol_row.get("status") != "registered"
            or vina_observation_row.get("status") != "evaluated"
            or not isinstance(qm_target, dict)
            or not isinstance(vina_target, dict)
            or qm_target.get("meeko_ad4_atom_type") != "SA"
            or qm_target.get("openbabel_ad4_atom_type") != "S"
            or vina_target.get("meeko_ad4_atom_type") != "SA"
            or vina_target.get("openbabel_ad4_atom_type") != "S"
            or qm_target.get("source_smiles_atom_index")
            != scope["source_smiles_atom_index"]
            or vina_target.get("source_smiles_atom_index")
            != scope["source_smiles_atom_index"]
            or qm_observation_row.get("source_sdf_sha256")
            != qm_protocol_row.get("source_sdf", {}).get("sha256")
        ):
            raise PoseBustersSulfurInteractionError(
                f"{case_id} upstream sulfur binding is inconsistent"
            )
        score_rows = vina_observation_row.get("score_rows")
        if (
            not isinstance(score_rows, list)
            or not score_rows
            or not all(
                isinstance(row, dict) and row.get("all_components_exact_equal") is True
                for row in score_rows
            )
        ):
            raise PoseBustersSulfurInteractionError(
                f"{case_id} Vina invariance rows are incomplete"
            )
        result.append(
            {
                **base,
                "status": "registered",
                "disposition_code": ("neutral_thioether_oh_donor_interaction_model"),
                "environment": scope["environment"],
                "source_sdf": dict(qm_protocol_row["source_sdf"]),
                "target_sulfur": dict(qm_target),
                "upstream_vina_pose_count": len(score_rows),
                "upstream_vina_all_pose_scores_exact_equal": True,
                "geometry_binding": _geometry_bindings(scope["model_id"]),
            }
        )
    return result


def _protocol_payload(
    *,
    registered_utc: str,
    qm_protocol: Mapping[str, Any],
    qm_observation: Mapping[str, Any],
    vina_protocol: Mapping[str, Any],
    vina_observation: Mapping[str, Any],
    chain_file_hashes: Mapping[str, str],
    pyscf_wheel_binding: Mapping[str, Any],
    dispersion_wheel_binding: Mapping[str, Any],
    vina_source_binding: Mapping[str, Any],
    case_rows: list[dict[str, Any]],
    source_members: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID,
        "registered_utc": registered_utc,
        "all_case_denominator": (POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR),
        "scope_case_count": len(POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS),
        "scope_abstention_case_count": (
            POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR
            - len(POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS)
        ),
        "configuration": POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION,
        "configuration_sha256": (POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256),
        "qm_esp_protocol_receipt_sha256": qm_protocol["receipt_sha256"],
        "qm_esp_observation_receipt_sha256": qm_observation["receipt_sha256"],
        "vina_invariance_protocol_receipt_sha256": (vina_protocol["receipt_sha256"]),
        "vina_invariance_observation_receipt_sha256": (
            vina_observation["receipt_sha256"]
        ),
        **dict(chain_file_hashes),
        "pyscf_wheel_binding": dict(pyscf_wheel_binding),
        "pyscf_dispersion_wheel_binding": dict(dispersion_wheel_binding),
        "vina_ad4_source_binding": dict(vina_source_binding),
        "implementation_source_members": source_members,
        "implementation_source_sha256": _canonical_sha256(source_members),
        "case_rows": case_rows,
        "protocol_registered_before_qm_execution": True,
        "qm_execution_performed": False,
        "ad4_pair_formula_executed": False,
        "benchmark_executed": False,
        "chemical_acceptor_semantics_adjudicated": False,
        "scientific_blockers": list(POSEBUSTERS_SULFUR_INTERACTION_SCIENTIFIC_BLOCKERS),
        "scientifically_validated": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_sulfur_interaction_protocol(
    qm_protocol_path: str | os.PathLike[str],
    qm_observation_path: str | os.PathLike[str],
    vina_protocol_path: str | os.PathLike[str],
    vina_observation_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    pyscf_dispersion_wheel_path: str | os.PathLike[str],
    *,
    expected_qm_protocol_sha256: str,
    expected_qm_observation_sha256: str,
    expected_vina_protocol_sha256: str,
    expected_vina_observation_sha256: str,
    expected_pyscf_wheel_sha256: str,
    expected_pyscf_dispersion_wheel_sha256: str,
    registered_utc: str,
) -> dict[str, Any]:
    """Materialize the complete protocol without running QM."""

    registered = _utc_timestamp(registered_utc, name="registration UTC")
    (
        qm_protocol,
        qm_observation,
        vina_protocol,
        vina_observation,
        chain_file_hashes,
    ) = _chain_receipts(
        qm_protocol_path,
        qm_observation_path,
        vina_protocol_path,
        vina_observation_path,
        expected_qm_protocol_sha256=expected_qm_protocol_sha256,
        expected_qm_observation_sha256=expected_qm_observation_sha256,
        expected_vina_protocol_sha256=expected_vina_protocol_sha256,
        expected_vina_observation_sha256=expected_vina_observation_sha256,
    )
    try:
        pyscf_binding = qm_esp._pyscf_wheel_binding(
            pyscf_wheel_path,
            expected_wheel_sha256=expected_pyscf_wheel_sha256,
        )
    except ValueError as exc:
        raise PoseBustersSulfurInteractionError(
            "PySCF wheel binding is invalid"
        ) from exc
    dispersion_binding = _wheel_binding(
        pyscf_dispersion_wheel_path,
        expected_sha256=expected_pyscf_dispersion_wheel_sha256,
        expected_filename=(
            POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_WHEEL_FILENAME
        ),
        name="PySCF-dispersion",
    )
    source_binding = _ad4_source_binding(vina_source_root)
    case_rows = _protocol_case_rows(
        qm_protocol,
        qm_observation,
        vina_protocol,
        vina_observation,
    )
    source_members = _implementation_source_members()
    return _protocol_payload(
        registered_utc=registered,
        qm_protocol=qm_protocol,
        qm_observation=qm_observation,
        vina_protocol=vina_protocol,
        vina_observation=vina_observation,
        chain_file_hashes=chain_file_hashes,
        pyscf_wheel_binding=pyscf_binding,
        dispersion_wheel_binding=dispersion_binding,
        vina_source_binding=source_binding,
        case_rows=case_rows,
        source_members=source_members,
    )


def verify_posebusters_sulfur_interaction_protocol(
    protocol_receipt_path: str | os.PathLike[str],
    qm_protocol_path: str | os.PathLike[str],
    qm_observation_path: str | os.PathLike[str],
    vina_protocol_path: str | os.PathLike[str],
    vina_observation_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    pyscf_dispersion_wheel_path: str | os.PathLike[str],
    *,
    expected_protocol_receipt_sha256: str,
    expected_qm_protocol_sha256: str,
    expected_qm_observation_sha256: str,
    expected_vina_protocol_sha256: str,
    expected_vina_observation_sha256: str,
    expected_pyscf_wheel_sha256: str,
    expected_pyscf_dispersion_wheel_sha256: str,
) -> dict[str, Any]:
    raw, source = _read_private_canonical_receipt(
        protocol_receipt_path,
        expected_receipt_sha256=expected_protocol_receipt_sha256,
        expected_schema_id=(POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID),
        maximum_bytes=POSEBUSTERS_SULFUR_INTERACTION_MAX_PROTOCOL_BYTES,
    )
    expected = materialize_posebusters_sulfur_interaction_protocol(
        qm_protocol_path,
        qm_observation_path,
        vina_protocol_path,
        vina_observation_path,
        vina_source_root,
        pyscf_wheel_path,
        pyscf_dispersion_wheel_path,
        expected_qm_protocol_sha256=expected_qm_protocol_sha256,
        expected_qm_observation_sha256=expected_qm_observation_sha256,
        expected_vina_protocol_sha256=expected_vina_protocol_sha256,
        expected_vina_observation_sha256=expected_vina_observation_sha256,
        expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
        expected_pyscf_dispersion_wheel_sha256=(expected_pyscf_dispersion_wheel_sha256),
        registered_utc=raw.get("registered_utc"),
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersSulfurInteractionError(
            "interaction protocol failed exact re-registration"
        )
    return expected


def _installed_distribution_manifest(
    distribution_name: str,
    imported_module: Any,
    *,
    expected_version: str,
) -> dict[str, Any]:
    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise PoseBustersSulfurInteractionError(
            f"{distribution_name} distribution is unavailable"
        ) from exc
    if distribution.version != expected_version:
        raise PoseBustersSulfurInteractionError(
            f"{distribution_name} version is not frozen"
        )
    module_file = getattr(imported_module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        raise PoseBustersSulfurInteractionError(
            f"{distribution_name} module path is unavailable"
        )
    try:
        observed_module = Path(module_file).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersSulfurInteractionError(
            f"{distribution_name} module path cannot be resolved"
        ) from exc
    files = distribution.files
    if files is None:
        raise PoseBustersSulfurInteractionError(
            f"{distribution_name} file inventory is unavailable"
        )
    metadata_exclusions = {
        "direct_url.json",
        "INSTALLER",
        "RECORD",
        "REQUESTED",
    }
    payload: dict[str, dict[str, Any]] = {}
    content: dict[str, dict[str, Any]] = {}
    total_size = 0
    module_owned = False
    for package_path in sorted(files, key=str):
        relative = PurePosixPath(str(package_path))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "__pycache__" in relative.parts
            or relative.suffix == ".pyc"
            or (
                relative.name in metadata_exclusions
                and any(part.endswith(".dist-info") for part in relative.parts)
            )
        ):
            continue
        path = Path(distribution.locate_file(package_path))
        try:
            resolved = path.resolve(strict=True)
            metadata = path.lstat()
        except OSError as exc:
            raise PoseBustersSulfurInteractionError(
                f"{distribution_name} payload file is unavailable"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersSulfurInteractionError(
                f"{distribution_name} payload is not regular"
            )
        if resolved == observed_module:
            module_owned = True
        digest, size, mode = _hash_regular_file(
            path,
            maximum_bytes=(POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_FILE_BYTES),
        )
        key = relative.as_posix()
        if key in payload:
            raise PoseBustersSulfurInteractionError(
                f"{distribution_name} payload path repeats"
            )
        payload[key] = {
            "mode": mode,
            "sha256": digest,
            "size_bytes": size,
        }
        content[key] = {"sha256": digest, "size_bytes": size}
        total_size += size
        if (
            len(payload) > POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_FILES
            or total_size > POSEBUSTERS_SULFUR_INTERACTION_MAX_DEPENDENCY_BYTES
        ):
            raise PoseBustersSulfurInteractionError(
                f"{distribution_name} payload exceeds frozen bounds"
            )
    if not module_owned or not payload:
        raise PoseBustersSulfurInteractionError(
            f"{distribution_name} import is not owned by its distribution"
        )
    return {
        "distribution_name": distribution_name.lower(),
        "distribution_version": distribution.version,
        "payload_sha256": _canonical_sha256(payload),
        "content_sha256": _canonical_sha256(content),
        "payload_file_count": len(payload),
        "payload_size_bytes": total_size,
    }


@dataclass(frozen=True, slots=True)
class _ScfResult:
    total_energy_hartree: float
    dispersion_energy_hartree: float
    electron_count: int
    cycle_count: int
    atomic_orbital_count: int
    integration_grid_point_count: int

    def __post_init__(self) -> None:
        if (
            not math.isfinite(float(self.total_energy_hartree))
            or not math.isfinite(float(self.dispersion_energy_hartree))
            or not isinstance(self.electron_count, int)
            or self.electron_count < 1
            or not isinstance(self.cycle_count, int)
            or self.cycle_count < 1
            or self.cycle_count > 150
            or not isinstance(self.atomic_orbital_count, int)
            or self.atomic_orbital_count < 1
            or not isinstance(self.integration_grid_point_count, int)
            or self.integration_grid_point_count < 1
        ):
            raise PoseBustersSulfurInteractionError(
                "SCF result is structurally invalid"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_energy_hartree_binary64_hex": (self.total_energy_hartree.hex()),
            "dispersion_energy_hartree_binary64_hex": (
                self.dispersion_energy_hartree.hex()
            ),
            "electron_count": self.electron_count,
            "cycle_count": self.cycle_count,
            "atomic_orbital_count": self.atomic_orbital_count,
            "integration_grid_point_count": (self.integration_grid_point_count),
            "converged": True,
        }


@dataclass(frozen=True, slots=True)
class _CounterpoiseResult:
    complex: _ScfResult
    acceptor_with_probe_ghost_basis: _ScfResult
    probe_with_acceptor_ghost_basis: _ScfResult

    @property
    def interaction_energy_hartree(self) -> float:
        return float(
            self.complex.total_energy_hartree
            - self.acceptor_with_probe_ghost_basis.total_energy_hartree
            - self.probe_with_acceptor_ghost_basis.total_energy_hartree
        )

    def to_dict(self) -> dict[str, Any]:
        interaction = self.interaction_energy_hartree
        return {
            "complex": self.complex.to_dict(),
            "acceptor_with_probe_ghost_basis": (
                self.acceptor_with_probe_ghost_basis.to_dict()
            ),
            "probe_with_acceptor_ghost_basis": (
                self.probe_with_acceptor_ghost_basis.to_dict()
            ),
            "counterpoise_interaction_energy_hartree_binary64_hex": (interaction.hex()),
            "counterpoise_interaction_energy_kcal_per_mol_binary64_hex": (
                interaction * _HARTREE_TO_KCAL_PER_MOL
            ).hex(),
        }


class _InteractionRuntimeProtocol(Protocol):
    identity: Mapping[str, Any]

    def run_counterpoise(
        self,
        acceptor_symbols: Sequence[str],
        acceptor_coordinates_angstrom: np.ndarray,
        probe_symbols: Sequence[str],
        probe_coordinates_angstrom: np.ndarray,
    ) -> _CounterpoiseResult: ...


class _PyscfInteractionRuntime:
    def __init__(
        self,
        pyscf_wheel_path: str | os.PathLike[str],
        pyscf_dispersion_wheel_path: str | os.PathLike[str],
        *,
        expected_pyscf_wheel_sha256: str,
        expected_pyscf_dispersion_wheel_sha256: str,
    ) -> None:
        try:
            base = qm_esp._PyscfQMEspRuntime(
                pyscf_wheel_path,
                expected_wheel_sha256=expected_pyscf_wheel_sha256,
            )
            from pyscf import dft, dispersion, gto, lib
        except (ImportError, ValueError) as exc:
            raise PoseBustersSulfurInteractionError(
                "interaction execution requires the frozen PySCF runtime"
            ) from exc
        plugin_binding = _wheel_binding(
            pyscf_dispersion_wheel_path,
            expected_sha256=expected_pyscf_dispersion_wheel_sha256,
            expected_filename=(
                POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_WHEEL_FILENAME
            ),
            name="PySCF-dispersion",
        )
        plugin_manifest = _installed_distribution_manifest(
            "pyscf-dispersion",
            dispersion,
            expected_version=(POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_VERSION),
        )
        if (
            plugin_manifest["content_sha256"] != plugin_binding["content_sha256"]
            or plugin_manifest["payload_file_count"]
            != plugin_binding["content_file_count"]
            or plugin_manifest["payload_size_bytes"]
            != plugin_binding["content_size_bytes"]
        ):
            raise PoseBustersSulfurInteractionError(
                "installed PySCF-dispersion payload is not wheel-equivalent"
            )
        lib.num_threads(1)
        self._dft = dft
        self._gto = gto
        self._lib = lib
        identity_payload = {
            "schema_id": POSEBUSTERS_SULFUR_INTERACTION_RUNTIME_SCHEMA_ID,
            "base_pyscf_runtime": base.identity.to_dict(),
            "base_pyscf_runtime_sha256": base.identity.fingerprint_sha256,
            "pyscf_dispersion_wheel_binding": plugin_binding,
            "pyscf_dispersion_distribution": plugin_manifest,
            "qm_configuration_sha256": _canonical_sha256(
                POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION["qm"]
            ),
            "all_observed_native_thread_pools_single_thread": True,
        }
        self.identity = {
            **identity_payload,
            "runtime_identity_sha256": _canonical_sha256(identity_payload),
        }

    def _run_scf(
        self,
        atoms: Sequence[tuple[str, tuple[float, float, float]]],
        *,
        expected_electron_count: int,
    ) -> _ScfResult:
        self._lib.num_threads(1)
        molecule = self._gto.M(
            atom=list(atoms),
            basis="def2-svp",
            unit="Angstrom",
            charge=0,
            spin=0,
            cart=False,
            max_memory=4096,
            verbose=0,
            output=None,
        )
        if int(molecule.nelectron) != expected_electron_count:
            raise PoseBustersSulfurInteractionError(
                "counterpoise fragment electron count is invalid"
            )
        mean_field = self._dft.RKS(
            molecule,
            xc="b3lyp-d3bj",
        ).density_fit(auxbasis="def2-universal-jkfit")
        mean_field.conv_tol = 1.0e-9
        mean_field.conv_tol_grad = 1.0e-5
        mean_field.max_cycle = 150
        mean_field.direct_scf_tol = 1.0e-12
        mean_field.grids.level = 2
        mean_field.grids.prune = self._dft.gen_grid.nwchem_prune
        mean_field.grids.radi_method = self._dft.radi.treutler_ahlrichs
        mean_field.grids.becke_scheme = self._dft.gen_grid.original_becke
        mean_field.grids.radii_adjust = self._dft.radi.treutler_atomic_radii_adjust
        mean_field.grids.alignment = 8
        mean_field.grids.sort_grids = None
        initial_density = mean_field.get_init_guess(
            molecule,
            key="minao",
        )
        total_energy = float(mean_field.kernel(dm0=initial_density))
        if not mean_field.converged:
            raise PoseBustersSulfurInteractionError(
                "B3LYP-D3(BJ)/def2-SVP failed SCF convergence"
            )
        dispersion_energy = float(mean_field.get_dispersion())
        summary_dispersion = float(
            np.asarray(mean_field.scf_summary.get("dispersion")).item()
        )
        if dispersion_energy != summary_dispersion:
            raise PoseBustersSulfurInteractionError(
                "D3(BJ) energy is not included consistently"
            )
        cycles = int(getattr(mean_field, "cycles", 0))
        grid_count = int(mean_field.grids.coords.shape[0])
        return _ScfResult(
            total_energy_hartree=total_energy,
            dispersion_energy_hartree=dispersion_energy,
            electron_count=int(molecule.nelectron),
            cycle_count=cycles,
            atomic_orbital_count=int(molecule.nao_nr()),
            integration_grid_point_count=grid_count,
        )

    def run_counterpoise(
        self,
        acceptor_symbols: Sequence[str],
        acceptor_coordinates_angstrom: np.ndarray,
        probe_symbols: Sequence[str],
        probe_coordinates_angstrom: np.ndarray,
    ) -> _CounterpoiseResult:
        acceptor_symbols_tuple = tuple(str(value) for value in acceptor_symbols)
        probe_symbols_tuple = tuple(str(value) for value in probe_symbols)
        acceptor = np.asarray(
            acceptor_coordinates_angstrom,
            dtype=np.float64,
            order="C",
        )
        probe = np.asarray(
            probe_coordinates_angstrom,
            dtype=np.float64,
            order="C",
        )
        if (
            not acceptor_symbols_tuple
            or not probe_symbols_tuple
            or len(acceptor_symbols_tuple) + len(probe_symbols_tuple) > 64
            or acceptor.shape != (len(acceptor_symbols_tuple), 3)
            or probe.shape != (len(probe_symbols_tuple), 3)
            or not np.isfinite(acceptor).all()
            or not np.isfinite(probe).all()
        ):
            raise PoseBustersSulfurInteractionError(
                "counterpoise molecular arrays are invalid"
            )
        atomic_numbers = {"H": 1, "C": 6, "O": 8, "S": 16}
        if any(
            symbol not in atomic_numbers
            for symbol in acceptor_symbols_tuple + probe_symbols_tuple
        ):
            raise PoseBustersSulfurInteractionError(
                "counterpoise model contains an unsupported element"
            )

        acceptor_atoms = [
            (symbol, tuple(float(value) for value in coordinate))
            for symbol, coordinate in zip(
                acceptor_symbols_tuple,
                acceptor,
                strict=True,
            )
        ]
        probe_atoms = [
            (symbol, tuple(float(value) for value in coordinate))
            for symbol, coordinate in zip(
                probe_symbols_tuple,
                probe,
                strict=True,
            )
        ]
        acceptor_electrons = sum(
            atomic_numbers[symbol] for symbol in acceptor_symbols_tuple
        )
        probe_electrons = sum(atomic_numbers[symbol] for symbol in probe_symbols_tuple)
        complex_result = self._run_scf(
            acceptor_atoms + probe_atoms,
            expected_electron_count=acceptor_electrons + probe_electrons,
        )
        acceptor_cp = self._run_scf(
            acceptor_atoms
            + [(f"ghost-{symbol}", coordinate) for symbol, coordinate in probe_atoms],
            expected_electron_count=acceptor_electrons,
        )
        probe_cp = self._run_scf(
            [(f"ghost-{symbol}", coordinate) for symbol, coordinate in acceptor_atoms]
            + probe_atoms,
            expected_electron_count=probe_electrons,
        )
        return _CounterpoiseResult(
            complex=complex_result,
            acceptor_with_probe_ghost_basis=acceptor_cp,
            probe_with_acceptor_ghost_basis=probe_cp,
        )


def _geometry_payloads(
    protocol_row: Mapping[str, Any],
) -> dict[
    str,
    tuple[tuple[str, ...], np.ndarray, tuple[str, ...], np.ndarray],
]:
    binding = protocol_row.get("geometry_binding")
    if not isinstance(binding, dict):
        raise PoseBustersSulfurInteractionError("protocol geometry binding is missing")
    model_id = binding.get("model_id")
    if not isinstance(model_id, str):
        raise PoseBustersSulfurInteractionError("protocol model identifier is invalid")
    expected_binding = _geometry_bindings(model_id)
    if binding != expected_binding:
        raise PoseBustersSulfurInteractionError(
            "protocol geometry binding does not reproduce"
        )
    acceptor_symbols, acceptor, sulfur, neighbors = _model_arrays(model_id)
    probe_symbols, _reference, _donor_hydrogen = _donor_arrays()
    frame = _acceptor_frame(acceptor, sulfur, neighbors)
    selected_label, selected_axis, _clearances = _selected_primary_axis(
        frame,
        acceptor,
    )
    if selected_label != binding["selected_primary_axis"]:
        raise PoseBustersSulfurInteractionError("protocol primary axis changed")
    result: dict[
        str,
        tuple[tuple[str, ...], np.ndarray, tuple[str, ...], np.ndarray],
    ] = {}
    for point in binding["points"]:
        geometry_id = point["geometry_id"]
        distance = float.fromhex(point["distance_angstrom_binary64_hex"])
        axis = (
            frame.plane_normal
            if point["orientation"] == "positive_CSC_plane_normal"
            else selected_axis
        )
        probe = _probe_coordinates(frame, axis, distance)
        if (
            _array_identity(
                acceptor,
                name="acceptor coordinates",
            )
            != point["acceptor_coordinates"]
            or _array_identity(
                probe,
                name="probe coordinates",
            )
            != point["probe_coordinates"]
            or _array_identity(
                np.concatenate((acceptor, probe), axis=0),
                name="complex coordinates",
            )
            != point["complex_coordinates"]
        ):
            raise PoseBustersSulfurInteractionError(
                "protocol point geometry does not reproduce"
            )
        result[geometry_id] = (
            acceptor_symbols,
            acceptor,
            probe_symbols,
            probe,
        )
    return result


def _rankdata(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size < 2 or not np.isfinite(array).all():
        raise PoseBustersSulfurInteractionError("profile rank values are invalid")
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(array.size, dtype=np.float64)
    start = 0
    while start < array.size:
        stop = start + 1
        while stop < array.size and array[order[stop]] == array[order[start]]:
            stop += 1
        rank = (start + stop - 1) * 0.5 + 1.0
        ranks[order[start:stop]] = rank
        start = stop
    return ranks


def _pearson(first: Sequence[float], second: Sequence[float]) -> float:
    left = np.asarray(first, dtype=np.float64)
    right = np.asarray(second, dtype=np.float64)
    if (
        left.shape != right.shape
        or left.ndim != 1
        or left.size < 2
        or not np.isfinite(left).all()
        or not np.isfinite(right).all()
    ):
        raise PoseBustersSulfurInteractionError(
            "profile correlation arrays are invalid"
        )
    centered_left = left - float(np.mean(left))
    centered_right = right - float(np.mean(right))
    denominator = float(np.linalg.norm(centered_left) * np.linalg.norm(centered_right))
    if denominator <= 0.0:
        return 0.0
    result = float(np.dot(centered_left, centered_right) / denominator)
    return max(-1.0, min(1.0, result))


def _normalized_far_referenced_profile(
    energies: Sequence[float],
) -> np.ndarray:
    array = np.asarray(energies, dtype=np.float64)
    if array.ndim != 1 or array.size < 3 or not np.isfinite(array).all():
        raise PoseBustersSulfurInteractionError("energy profile is invalid")
    relative = array - float(array[-1])
    depth = abs(float(np.min(relative)))
    if depth <= 1.0e-12:
        raise PoseBustersSulfurInteractionError(
            "energy profile has no resolvable attractive well"
        )
    return np.asarray(relative / depth, dtype=np.float64)


def _minimum_distance_set(
    distances: Sequence[float],
    energies: Sequence[float],
) -> tuple[float, ...]:
    distance_array = np.asarray(distances, dtype=np.float64)
    energy_array = np.asarray(energies, dtype=np.float64)
    if (
        distance_array.shape != energy_array.shape
        or distance_array.ndim != 1
        or distance_array.size < 2
    ):
        raise PoseBustersSulfurInteractionError("minimum-distance profile is invalid")
    minimum = float(np.min(energy_array))
    return tuple(
        float(distance)
        for distance, energy in zip(
            distance_array,
            energy_array,
            strict=True,
        )
        if float(energy) == minimum
    )


def _profile_comparison(
    distances: Sequence[float],
    qm_energies: Sequence[float],
    model_energies: Sequence[float],
) -> dict[str, Any]:
    qm_normalized = _normalized_far_referenced_profile(qm_energies)
    model_normalized = _normalized_far_referenced_profile(model_energies)
    rmse = math.sqrt(
        math.fsum(
            float(value) ** 2 for value in (model_normalized - qm_normalized)[:-1]
        )
        / (len(qm_normalized) - 1)
    )
    qm_minima = _minimum_distance_set(distances, qm_energies)
    model_minima = _minimum_distance_set(distances, model_energies)
    minimum_distance_error = min(
        abs(qm_distance - model_distance)
        for qm_distance in qm_minima
        for model_distance in model_minima
    )
    return {
        "far_referenced_normalized_profile_binary64_hex": [
            value.hex() for value in model_normalized
        ],
        "normalized_rmse_binary64_hex": rmse.hex(),
        "spearman_binary64_hex": _pearson(
            _rankdata(qm_energies),
            _rankdata(model_energies),
        ).hex(),
        "minimum_distances_angstrom_binary64_hex": [
            value.hex() for value in model_minima
        ],
        "minimum_distance_error_angstrom_binary64_hex": (minimum_distance_error.hex()),
    }


def _case_metrics(point_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    primary = [
        row
        for row in point_rows
        if row.get("orientation") != "positive_CSC_plane_normal"
    ]
    control = [
        row
        for row in point_rows
        if row.get("orientation") == "positive_CSC_plane_normal"
    ]
    if (
        len(primary) != len(_SCAN_DISTANCES_ANGSTROM)
        or len(control) != 1
        or any(row.get("status") != "evaluated" for row in point_rows)
    ):
        raise PoseBustersSulfurInteractionError("case point rows are incomplete")
    primary.sort(key=lambda row: float.fromhex(row["distance_angstrom_binary64_hex"]))
    distances = [
        float.fromhex(row["distance_angstrom_binary64_hex"]) for row in primary
    ]
    if tuple(distances) != _SCAN_DISTANCES_ANGSTROM:
        raise PoseBustersSulfurInteractionError("case scan distances changed")
    qm_energies = [
        float.fromhex(row["counterpoise_interaction_energy_kcal_per_mol_binary64_hex"])
        for row in primary
    ]
    minimum_index = min(
        range(len(qm_energies)),
        key=lambda index: (qm_energies[index], distances[index]),
    )
    minimum_energy = qm_energies[minimum_index]
    minimum_distance = distances[minimum_index]
    far_energy = qm_energies[-1]
    well_depth = minimum_energy - far_energy
    primary_at_control = next(
        row
        for row in primary
        if float.fromhex(row["distance_angstrom_binary64_hex"])
        == _CONTROL_DISTANCE_ANGSTROM
    )
    primary_control_energy = float.fromhex(
        primary_at_control["counterpoise_interaction_energy_kcal_per_mol_binary64_hex"]
    )
    control_energy = float.fromhex(
        control[0]["counterpoise_interaction_energy_kcal_per_mol_binary64_hex"]
    )
    orientation_delta = control_energy - primary_control_energy

    ad4_s_energies = [
        float.fromhex(
            row["ad4_pair_terms"]["weighted_S_HD_vdw_kcal_per_mol_binary64_hex"]
        )
        for row in primary
    ]
    ad4_sa_energies = [
        float.fromhex(
            row["ad4_pair_terms"]["weighted_SA_HD_hbond_kcal_per_mol_binary64_hex"]
        )
        for row in primary
    ]
    s_profile = _profile_comparison(
        distances,
        qm_energies,
        ad4_s_energies,
    )
    sa_profile = _profile_comparison(
        distances,
        qm_energies,
        ad4_sa_energies,
    )
    s_rmse = float.fromhex(s_profile["normalized_rmse_binary64_hex"])
    sa_rmse = float.fromhex(sa_profile["normalized_rmse_binary64_hex"])
    s_distance_error = float.fromhex(
        s_profile["minimum_distance_error_angstrom_binary64_hex"]
    )
    sa_distance_error = float.fromhex(
        sa_profile["minimum_distance_error_angstrom_binary64_hex"]
    )
    margin = float.fromhex(
        POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION["decision_contract"][
            "sa_normalized_rmse_improvement_margin"
        ]
    )
    sa_profile_preferred = (
        sa_rmse + margin <= s_rmse and sa_distance_error <= s_distance_error
    )
    decision = POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION["decision_contract"]
    minimum_threshold = float.fromhex(decision["binding_minimum_at_most_kcal_per_mol"])
    well_threshold = float.fromhex(
        decision["far_referenced_well_depth_at_most_kcal_per_mol"]
    )
    allowed_minimum = tuple(
        float.fromhex(value) for value in decision["minimum_distance_allowed_angstrom"]
    )
    binding_gates = {
        "minimum_energy_gate": minimum_energy <= minimum_threshold,
        "far_referenced_well_depth_gate": well_depth <= well_threshold,
        "minimum_distance_gate": (
            allowed_minimum[0] <= minimum_distance <= allowed_minimum[1]
        ),
    }
    case_acceptor_support = all(binding_gates.values())
    return {
        "qm_profile": {
            "distances_angstrom_binary64_hex": [value.hex() for value in distances],
            "counterpoise_interaction_energy_kcal_per_mol_binary64_hex": [
                value.hex() for value in qm_energies
            ],
            "far_referenced_normalized_profile_binary64_hex": [
                value.hex() for value in _normalized_far_referenced_profile(qm_energies)
            ],
            "minimum_energy_kcal_per_mol_binary64_hex": (minimum_energy.hex()),
            "minimum_distance_angstrom_binary64_hex": (minimum_distance.hex()),
            "far_distance_energy_kcal_per_mol_binary64_hex": (far_energy.hex()),
            "far_referenced_well_depth_kcal_per_mol_binary64_hex": (well_depth.hex()),
            "orientation_control_delta_kcal_per_mol_binary64_hex": (
                orientation_delta.hex()
            ),
        },
        "binding_gates": binding_gates,
        "case_acceptor_support": case_acceptor_support,
        "ad4_pair_profile": {
            "S_HD_vdw": s_profile,
            "SA_HD_hbond": sa_profile,
            "SA_normalized_rmse_improvement_binary64_hex": (s_rmse - sa_rmse).hex(),
            "SA_profile_preferred": sa_profile_preferred,
            "absolute_pair_magnitude_comparison_is_claimed": False,
        },
        "ad4_sa_pair_profile_preferred": sa_profile_preferred,
    }


def _observed_case(
    protocol_row: Mapping[str, Any],
    runtime: _InteractionRuntimeProtocol,
) -> dict[str, Any]:
    if protocol_row.get("status") != "registered":
        return {
            "schema_id": POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
            "case_id": protocol_row.get("case_id"),
            "protocol_status": protocol_row.get("status"),
            "status": "abstain_protocol_scope",
            "disposition_code": protocol_row.get("disposition_code"),
            "qm_attempted": False,
            "point_rows": [],
            "case_acceptor_support": None,
            "ad4_sa_pair_profile_preferred": None,
        }
    case_id = protocol_row.get("case_id")
    if case_id not in POSEBUSTERS_SULFUR_INTERACTION_SCOPE:
        raise PoseBustersSulfurInteractionError(
            "registered interaction case is outside scope"
        )
    binding = protocol_row.get("geometry_binding")
    if not isinstance(binding, dict):
        raise PoseBustersSulfurInteractionError(
            "registered interaction geometry is missing"
        )
    payloads = _geometry_payloads(protocol_row)
    point_rows: list[dict[str, Any]] = []
    failure_count = 0
    for point in binding["points"]:
        geometry_id = point["geometry_id"]
        (
            acceptor_symbols,
            acceptor_coordinates,
            probe_symbols,
            probe_coordinates,
        ) = payloads[geometry_id]
        base = {
            "schema_id": POSEBUSTERS_SULFUR_INTERACTION_POINT_SCHEMA_ID,
            "geometry_id": geometry_id,
            "orientation": point["orientation"],
            "distance_angstrom_binary64_hex": (point["distance_angstrom_binary64_hex"]),
            "complex_geometry_sha256": point["complex_coordinates"]["sha256"],
            "ad4_pair_terms": _ad4_pair_terms(
                float.fromhex(point["distance_angstrom_binary64_hex"])
            ),
            "qm_attempted": True,
        }
        try:
            result = runtime.run_counterpoise(
                acceptor_symbols,
                acceptor_coordinates,
                probe_symbols,
                probe_coordinates,
            )
        except Exception as exc:  # preserve every bounded runtime failure
            normalized = _normalized_error(exc)
            failure_count += 1
            point_rows.append(
                {
                    **base,
                    "status": "qm_failure",
                    "error_code": "counterpoise_execution_failed",
                    "error_type": type(exc).__name__,
                    "error_message_sha256": hashlib.sha256(normalized).hexdigest(),
                    "counterpoise": None,
                    "counterpoise_interaction_energy_kcal_per_mol_binary64_hex": (None),
                }
            )
            continue
        result_dict = result.to_dict()
        point_rows.append(
            {
                **base,
                "status": "evaluated",
                "error_code": None,
                "error_type": None,
                "error_message_sha256": None,
                "counterpoise": result_dict,
                "counterpoise_interaction_energy_kcal_per_mol_binary64_hex": (
                    result_dict[
                        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
                    ]
                ),
            }
        )
    base_case = {
        "schema_id": POSEBUSTERS_SULFUR_INTERACTION_CASE_SCHEMA_ID,
        "case_id": case_id,
        "protocol_status": "registered",
        "environment": protocol_row["environment"],
        "model_id": binding["model_id"],
        "target_sulfur": dict(protocol_row["target_sulfur"]),
        "qm_attempted": True,
        "attempted_point_count": len(point_rows),
        "qm_failure_point_count": failure_count,
        "point_rows": point_rows,
    }
    if failure_count:
        return {
            **base_case,
            "status": "qm_failure",
            "disposition_code": "interaction_counterpoise_failure",
            "metrics": None,
            "case_acceptor_support": None,
            "ad4_sa_pair_profile_preferred": None,
        }
    metrics = _case_metrics(point_rows)
    return {
        **base_case,
        "status": "evaluated",
        "disposition_code": ("neutral_thioether_oh_donor_interaction_complete"),
        "metrics": metrics,
        "case_acceptor_support": metrics["case_acceptor_support"],
        "ad4_sa_pair_profile_preferred": (metrics["ad4_sa_pair_profile_preferred"]),
    }


def _observation_payload(
    *,
    observation_utc: str,
    protocol: Mapping[str, Any],
    protocol_file_sha256: str,
    runtime_identity: Mapping[str, Any],
    case_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated = [row for row in case_rows if row["status"] == "evaluated"]
    failures = [row for row in case_rows if row["status"] == "qm_failure"]
    abstentions = [
        row for row in case_rows if row["status"] == "abstain_protocol_scope"
    ]
    acceptor_support_count = sum(
        row.get("case_acceptor_support") is True for row in evaluated
    )
    sa_preferred_count = sum(
        row.get("ad4_sa_pair_profile_preferred") is True for row in evaluated
    )
    all_scope_evaluated = (
        len(evaluated) == len(POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS)
        and not failures
    )
    local_acceptor_gate = (
        all_scope_evaluated
        and acceptor_support_count
        == POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION["decision_contract"][
            "local_three_model_acceptor_gate_requires_case_count"
        ]
    )
    ad4_sa_gate = (
        all_scope_evaluated
        and local_acceptor_gate
        and sa_preferred_count
        == POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION["decision_contract"][
            "ad4_sa_profile_gate_requires_preferred_case_count"
        ]
    )
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID,
        "observation_utc": observation_utc,
        "all_case_denominator": (POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR),
        "protocol_receipt_sha256": protocol["receipt_sha256"],
        "protocol_receipt_file_sha256": protocol_file_sha256,
        "protocol_registered_before_qm_execution": True,
        "configuration": POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION,
        "configuration_sha256": (POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256),
        "implementation_source_members": (protocol["implementation_source_members"]),
        "implementation_source_sha256": (protocol["implementation_source_sha256"]),
        "pyscf_interaction_runtime_identity": dict(runtime_identity),
        "pyscf_interaction_runtime_identity_sha256": runtime_identity[
            "runtime_identity_sha256"
        ],
        "case_rows": case_rows,
        "scope_case_count": len(POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS),
        "evaluated_case_count": len(evaluated),
        "qm_failure_case_count": len(failures),
        "scope_abstention_case_count": len(abstentions),
        "case_acceptor_support_count": acceptor_support_count,
        "ad4_sa_pair_profile_preferred_case_count": sa_preferred_count,
        "all_scoped_cases_evaluated": all_scope_evaluated,
        "local_three_model_oh_acceptor_gate_pass": local_acceptor_gate,
        "local_ad4_sa_pair_profile_gate_pass": ad4_sa_gate,
        "bounded_local_interaction_evidence_generated": all_scope_evaluated,
        "ad4_pair_formula_executed": True,
        "chemical_acceptor_semantics_adjudicated": False,
        "second_cpu_host_reproduced": False,
        "independent_reviewer_receipt_approved": False,
        "benchmark_executed": False,
        "scientific_blockers": list(POSEBUSTERS_SULFUR_INTERACTION_SCIENTIFIC_BLOCKERS),
        "scientifically_validated": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_sulfur_interaction_observation(
    protocol_receipt_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    pyscf_dispersion_wheel_path: str | os.PathLike[str],
    *,
    expected_protocol_receipt_sha256: str,
    expected_pyscf_wheel_sha256: str,
    expected_pyscf_dispersion_wheel_sha256: str,
    observation_utc: str,
    _runtime: _InteractionRuntimeProtocol | None = None,
) -> dict[str, Any]:
    """Execute every preregistered interaction point or retain its failure."""

    observed_utc = _utc_timestamp(observation_utc, name="observation UTC")
    protocol, protocol_source = _read_private_canonical_receipt(
        protocol_receipt_path,
        expected_receipt_sha256=expected_protocol_receipt_sha256,
        expected_schema_id=(POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID),
        maximum_bytes=POSEBUSTERS_SULFUR_INTERACTION_MAX_PROTOCOL_BYTES,
    )
    try:
        registered_time = datetime.fromisoformat(
            str(protocol["registered_utc"]).replace("Z", "+00:00")
        )
        observation_time = datetime.fromisoformat(observed_utc.replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise PoseBustersSulfurInteractionError(
            "protocol registration time is invalid"
        ) from exc
    if observation_time <= registered_time:
        raise PoseBustersSulfurInteractionError(
            "observation must occur after protocol registration"
        )
    source_members = _implementation_source_members()
    if (
        protocol.get("configuration") != POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION
        or protocol.get("configuration_sha256")
        != POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256
        or protocol.get("implementation_source_members") != source_members
        or protocol.get("implementation_source_sha256")
        != _canonical_sha256(source_members)
        or protocol.get("protocol_registered_before_qm_execution") is not True
        or protocol.get("qm_execution_performed") is not False
    ):
        raise PoseBustersSulfurInteractionError(
            "protocol source or configuration changed before observation"
        )
    if _ad4_source_binding(vina_source_root) != protocol.get("vina_ad4_source_binding"):
        raise PoseBustersSulfurInteractionError(
            "Vina source binding changed before observation"
        )
    try:
        pyscf_binding = qm_esp._pyscf_wheel_binding(
            pyscf_wheel_path,
            expected_wheel_sha256=expected_pyscf_wheel_sha256,
        )
    except ValueError as exc:
        raise PoseBustersSulfurInteractionError(
            "PySCF wheel binding is invalid"
        ) from exc
    dispersion_binding = _wheel_binding(
        pyscf_dispersion_wheel_path,
        expected_sha256=expected_pyscf_dispersion_wheel_sha256,
        expected_filename=(
            POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_WHEEL_FILENAME
        ),
        name="PySCF-dispersion",
    )
    if pyscf_binding != protocol.get(
        "pyscf_wheel_binding"
    ) or dispersion_binding != protocol.get("pyscf_dispersion_wheel_binding"):
        raise PoseBustersSulfurInteractionError(
            "QM wheel binding changed before observation"
        )
    runtime = _runtime
    if runtime is None:
        runtime = _PyscfInteractionRuntime(
            pyscf_wheel_path,
            pyscf_dispersion_wheel_path,
            expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
            expected_pyscf_dispersion_wheel_sha256=(
                expected_pyscf_dispersion_wheel_sha256
            ),
        )
    runtime_identity = dict(runtime.identity)
    runtime_sha = runtime_identity.get("runtime_identity_sha256")
    identity_payload = dict(runtime_identity)
    identity_payload.pop("runtime_identity_sha256", None)
    if runtime_sha != _canonical_sha256(identity_payload):
        raise PoseBustersSulfurInteractionError(
            "interaction runtime identity is invalid"
        )
    raw_protocol_rows = protocol.get("case_rows")
    if not isinstance(raw_protocol_rows, list) or len(raw_protocol_rows) != 308:
        raise PoseBustersSulfurInteractionError("protocol denominator is invalid")
    case_rows = [
        _observed_case(row, runtime)
        for row in raw_protocol_rows
        if isinstance(row, dict)
    ]
    if len(case_rows) != 308:
        raise PoseBustersSulfurInteractionError(
            "observation did not retain every protocol row"
        )
    return _observation_payload(
        observation_utc=observed_utc,
        protocol=protocol,
        protocol_file_sha256=hashlib.sha256(protocol_source).hexdigest(),
        runtime_identity=runtime_identity,
        case_rows=case_rows,
    )


def verify_posebusters_sulfur_interaction_observation(
    observation_receipt_path: str | os.PathLike[str],
    protocol_receipt_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    pyscf_dispersion_wheel_path: str | os.PathLike[str],
    *,
    expected_observation_receipt_sha256: str,
    expected_protocol_receipt_sha256: str,
    expected_pyscf_wheel_sha256: str,
    expected_pyscf_dispersion_wheel_sha256: str,
) -> dict[str, Any]:
    raw, source = _read_private_canonical_receipt(
        observation_receipt_path,
        expected_receipt_sha256=expected_observation_receipt_sha256,
        expected_schema_id=(POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID),
        maximum_bytes=POSEBUSTERS_SULFUR_INTERACTION_MAX_OBSERVATION_BYTES,
    )
    expected = materialize_posebusters_sulfur_interaction_observation(
        protocol_receipt_path,
        vina_source_root,
        pyscf_wheel_path,
        pyscf_dispersion_wheel_path,
        expected_protocol_receipt_sha256=expected_protocol_receipt_sha256,
        expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
        expected_pyscf_dispersion_wheel_sha256=(expected_pyscf_dispersion_wheel_sha256),
        observation_utc=raw.get("observation_utc"),
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersSulfurInteractionError(
            "interaction observation failed exact reexecution"
        )
    return expected


def _add_protocol_chain_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--qm-protocol", required=True)
    parser.add_argument("--qm-observation", required=True)
    parser.add_argument("--vina-invariance-protocol", required=True)
    parser.add_argument("--vina-invariance-observation", required=True)
    parser.add_argument("--expected-qm-protocol-sha256", required=True)
    parser.add_argument("--expected-qm-observation-sha256", required=True)
    parser.add_argument("--expected-vina-protocol-sha256", required=True)
    parser.add_argument("--expected-vina-observation-sha256", required=True)


def _add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vina-source-root", required=True)
    parser.add_argument("--pyscf-wheel", required=True)
    parser.add_argument("--pyscf-dispersion-wheel", required=True)
    parser.add_argument(
        "--expected-pyscf-wheel-sha256",
        default=qm_esp.POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_SHA256,
    )
    parser.add_argument(
        "--expected-pyscf-dispersion-wheel-sha256",
        default=(POSEBUSTERS_SULFUR_INTERACTION_PYSCF_DISPERSION_WHEEL_SHA256),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "preregister and execute the bounded neutral-thioether "
            "interaction-energy diagnostic"
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser(
        "register",
        help="write a no-overwrite protocol before QM execution",
    )
    _add_protocol_chain_arguments(register)
    _add_runtime_arguments(register)
    register.add_argument("--registered-utc", required=True)
    register.add_argument("--output", required=True)

    verify_protocol = commands.add_parser(
        "verify-protocol",
        help="re-register and compare a protocol exactly",
    )
    _add_protocol_chain_arguments(verify_protocol)
    _add_runtime_arguments(verify_protocol)
    verify_protocol.add_argument("--protocol", required=True)
    verify_protocol.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )

    observe = commands.add_parser(
        "observe",
        help="execute all preregistered counterpoise points",
    )
    _add_runtime_arguments(observe)
    observe.add_argument("--protocol", required=True)
    observe.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )
    observe.add_argument("--observation-utc", required=True)
    observe.add_argument("--output", required=True)

    verify_observation = commands.add_parser(
        "verify-observation",
        help="reexecute and compare an observation exactly",
    )
    _add_runtime_arguments(verify_observation)
    verify_observation.add_argument("--protocol", required=True)
    verify_observation.add_argument("--observation", required=True)
    verify_observation.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )
    verify_observation.add_argument(
        "--expected-observation-receipt-sha256",
        required=True,
    )
    return parser


def _cli_protocol_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "qm_protocol_path": args.qm_protocol,
        "qm_observation_path": args.qm_observation,
        "vina_protocol_path": args.vina_invariance_protocol,
        "vina_observation_path": args.vina_invariance_observation,
        "vina_source_root": args.vina_source_root,
        "pyscf_wheel_path": args.pyscf_wheel,
        "pyscf_dispersion_wheel_path": args.pyscf_dispersion_wheel,
        "expected_qm_protocol_sha256": args.expected_qm_protocol_sha256,
        "expected_qm_observation_sha256": (args.expected_qm_observation_sha256),
        "expected_vina_protocol_sha256": (args.expected_vina_protocol_sha256),
        "expected_vina_observation_sha256": (args.expected_vina_observation_sha256),
        "expected_pyscf_wheel_sha256": args.expected_pyscf_wheel_sha256,
        "expected_pyscf_dispersion_wheel_sha256": (
            args.expected_pyscf_dispersion_wheel_sha256
        ),
    }


def _cli_observation_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "protocol_receipt_path": args.protocol,
        "vina_source_root": args.vina_source_root,
        "pyscf_wheel_path": args.pyscf_wheel,
        "pyscf_dispersion_wheel_path": args.pyscf_dispersion_wheel,
        "expected_protocol_receipt_sha256": (args.expected_protocol_receipt_sha256),
        "expected_pyscf_wheel_sha256": args.expected_pyscf_wheel_sha256,
        "expected_pyscf_dispersion_wheel_sha256": (
            args.expected_pyscf_dispersion_wheel_sha256
        ),
    }


def _cli_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_id",
        "receipt_sha256",
        "registered_utc",
        "observation_utc",
        "all_case_denominator",
        "scope_case_count",
        "evaluated_case_count",
        "qm_failure_case_count",
        "scope_abstention_case_count",
        "local_three_model_oh_acceptor_gate_pass",
        "local_ad4_sa_pair_profile_gate_pass",
        "scientifically_validated",
        "claim_safe",
    )
    return {key: receipt[key] for key in keys if key in receipt}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "register":
        receipt = materialize_posebusters_sulfur_interaction_protocol(
            **_cli_protocol_kwargs(args),
            registered_utc=args.registered_utc,
        )
        _write_private_no_overwrite(receipt, args.output)
    elif args.command == "verify-protocol":
        protocol_kwargs = _cli_protocol_kwargs(args)
        receipt = verify_posebusters_sulfur_interaction_protocol(
            args.protocol,
            **protocol_kwargs,
            expected_protocol_receipt_sha256=(args.expected_protocol_receipt_sha256),
        )
    elif args.command == "observe":
        receipt = materialize_posebusters_sulfur_interaction_observation(
            **_cli_observation_kwargs(args),
            observation_utc=args.observation_utc,
        )
        _write_private_no_overwrite(receipt, args.output)
    else:
        observation_kwargs = _cli_observation_kwargs(args)
        receipt = verify_posebusters_sulfur_interaction_observation(
            args.observation,
            **observation_kwargs,
            expected_observation_receipt_sha256=(
                args.expected_observation_receipt_sha256
            ),
        )
    print(json.dumps(_cli_summary(receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

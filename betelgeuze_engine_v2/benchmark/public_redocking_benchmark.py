"""Frozen 300-case public redocking cohort and failure-complete scorecard.

This module defines an offline evaluation contract.  It does not download
inputs, launch Engine V2 or external binaries, or claim docking accuracy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import stat
import statistics
from types import MappingProxyType
from typing import Callable, Mapping, Sequence
import zipfile


PUBLIC_REDOCKING_COHORT_SCHEMA_ID = "betelgeuze.engine_v2_public_redocking_cohort/1.3.0"
PUBLIC_REDOCKING_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_evaluation_policy/1.3.0"
)
PUBLIC_REDOCKING_REPORT_SCHEMA_ID = "betelgeuze.engine_v2_public_redocking_report/1.10.0"
PUBLIC_REDOCKING_RUNNER_ID = "betelgeuze.engine_v2_public_redocking_300_runner/2.13.0"
PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_case_materialization/1.0.0"
)
PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_case_execution/1.1.0"
)
PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_engine_v2_diagnostics/1.5.0"
)
_SCORER_V1_BACKEND_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_scorer_v1_backend_receipt/1.0.0"
)
PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_contamination_registry/1.1.0"
)
PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SHA256 = (
    "89a58e6fbadd7e249df20bdf8db36f317e3e2e2dd6f32c32879d1a989dd28f31"
)
PUBLIC_REDOCKING_HISTORICAL_REPORT_SHA256 = (
    "2f701c05c6d073bab2542c9616ff177c0d7a3a601f913a4eceb07a99de790dda"
)
PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0"
)
PUBLIC_REDOCKING_PROPOSAL_MODES = (
    "donor_acceptor_hotspot",
    "charge_anchor",
    "hydrophobic_patch",
    "aromatic_plane",
    "shape_complementarity",
    "multi_anchor_hotspot",
    "pocket_center_baseline",
    "uniform_fallback",
    "uniform_v3_rigid_ensemble",
)
PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS = (
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "double_bond_flatness",
    "internal_energy",
)
PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS = (
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)
PUBLIC_REDOCKING_COHORT_ID = "posebusters-journal-subset-sha256-300"
PUBLIC_REDOCKING_COHORT_COUNT = 300
PUBLIC_REDOCKING_SOURCE_COUNT = 308
PUBLIC_REDOCKING_SELECTION_SALT = "betelgeuze-engine-v2-posebusters-300-v1"
PUBLIC_REDOCKING_CASE_SEED_BASE = 2_026_072_700
PUBLIC_REDOCKING_SOURCE_RECORD_ID = "8278563"
PUBLIC_REDOCKING_SOURCE_URL = "https://zenodo.org/records/8278563"
PUBLIC_REDOCKING_SOURCE_LICENSE = "CC-BY-4.0"
PUBLIC_REDOCKING_ARCHIVE_NAME = "posebusters_paper_data.zip"
PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES = 53_660_397
PUBLIC_REDOCKING_ARCHIVE_SHA256 = (
    "495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c"
)
PUBLIC_REDOCKING_SOURCE_IDS_URL = (
    "https://github.com/maabuu/posebusters/files/14516485/posebusters_pdb_ccd_ids.txt"
)
PUBLIC_REDOCKING_SOURCE_IDS_SIZE_BYTES = 2_772
PUBLIC_REDOCKING_SOURCE_IDS_SHA256 = (
    "a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6"
)
PUBLIC_REDOCKING_SELECTED_IDS_SHA256 = (
    "6829f1d2702560e42bebf21b3d9a8af4d5db902440f34561146373530b8a9065"
)
PUBLIC_REDOCKING_PROFILE_METHOD_ID = (
    "rdkit-2022.09.5-lipinski-num-rotatable-bonds-strict/1.0.0"
)
PUBLIC_REDOCKING_RING_PROFILE_METHOD_ID = (
    "rdkit-2022.09.5-rdmoldescriptors-calc-num-rings/1.0.0"
)
PUBLIC_REDOCKING_PROFILES_SHA256 = (
    "18ed3a4a50d5663a2dfb6f159ac515b15d6aebac9793831467aa2950e4710312"
)
PUBLIC_REDOCKING_RING_PROFILES_SHA256 = (
    "1b860ae64314b413dc83a2d858f55650c6e593d8fa82518e3fcdd844c46b017c"
)
PUBLIC_REDOCKING_MATERIALIZATIONS_SHA256 = (
    "94bb879b181ec3de581f3f098aff2bd50b9f988fd1d4eb0c3c46cc673cfd640a"
)
PUBLIC_REDOCKING_MATERIALIZATION_RECEIPTS_SHA256 = (
    "5182a24640c333944ca4b1e050a3cef348984a148cc784808881f7c57fce349b"
)
PUBLIC_REDOCKING_PRIMARY_ENGINES = ("engine_v2", "vina", "gnina")
_PUBLIC_REDOCKING_FAILURE_CODES = {
    "engine_v2": {
        "engine_v2_case_failed",
        "engine_v2_input_unsupported",
        "engine_v2_pose_count_incomplete",
    },
    "vina": {
        "external_timeout",
        "external_process_failed",
        "external_pose_output_invalid",
        "external_pose_count_incomplete",
    },
    "gnina": {
        "external_timeout",
        "external_process_failed",
        "external_pose_output_invalid",
        "external_pose_count_incomplete",
    },
}
_PUBLIC_REDOCKING_ENGINE_V2_PREPARATION_FAILURE_CODES = {
    "docking_context_preparation_failed",
    "input_parse_unsupported",
    "partial_charge_assignment_failed",
    "unsupported_large_ring_system",
    "unsupported_vdw_element",
    "unclassified_engine_v2_case_failure",
}
PUBLIC_REDOCKING_ANALYSIS_SCOPES = (
    "primary_blind_holdout",
    "fresh_internal_blind_holdout",
    "contaminated_development",
    "engineering_smoke",
    "supplementary_descriptive",
)
PUBLIC_REDOCKING_ALLOWED_TORCH_VERSIONS = (
    "2.6.0",
    "2.6.0+cpu",
    "2.6.0+rocm6.1",
)
PUBLIC_REDOCKING_TOP_KS = (1, 3, 5)
PUBLIC_REDOCKING_RMSD_THRESHOLD_ANGSTROM = 2.0
PUBLIC_REDOCKING_DEFAULT_BOOTSTRAP_SAMPLES = 2_000
PUBLIC_REDOCKING_DEFAULT_CONFIDENCE_LEVEL = 0.95
PUBLIC_REDOCKING_DEFAULT_BOOTSTRAP_SEED = 2_026_072_700
MAX_PUBLIC_REDOCKING_BOOTSTRAP_SAMPLES = 20_000
PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT = 64
PUBLIC_REDOCKING_SIZE_SUBGROUPS = (
    "size_small_1_20",
    "size_medium_21_40",
    "size_large_41_plus",
)
PUBLIC_REDOCKING_ROTOR_SUBGROUPS = (
    "rotor_rigid_0",
    "rotor_low_1_4",
    "rotor_flexible_5_plus",
)
PUBLIC_REDOCKING_RING_SUBGROUPS = (
    "ring_acyclic_0",
    "ring_single_1",
    "ring_multi_2_plus",
)
_CASE_ID_RE = re.compile(r"^[0-9][A-Z0-9]{3}_[A-Z0-9]{3}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CASE_ARTIFACT_ROLES = (
    ("receptor", "protein.pdb"),
    ("reference", "ligands.sdf"),
    ("native", "ligand.sdf"),
    ("seed", "ligand_start_conf.sdf"),
)
_VERIFIED_ARCHIVE_AUTHORITY = object()
_VERIFIED_EXECUTION_AUTHORITY = object()
_SCORER_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
    "total_score",
)


class PublicRedockingBenchmarkError(ValueError):
    """The frozen redocking cohort or scorecard contract was violated."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicRedockingBenchmarkError(
            "public redocking state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    result = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(result) is None:
        raise PublicRedockingBenchmarkError(f"{name} must be a lowercase SHA-256")
    return result


def _finite(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise PublicRedockingBenchmarkError(f"{name} must be finite numeric data")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        raise PublicRedockingBenchmarkError(f"{name} must be finite{suffix}")
    return result


def _execution_policy_mapping(tokens: Sequence[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for token in tokens:
        key, separator, encoded = str(token).partition("=")
        if not key or separator != "=" or key in result:
            raise PublicRedockingBenchmarkError(
                "result execution_policy token is malformed"
            )
        try:
            result[key] = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise PublicRedockingBenchmarkError(
                "result execution_policy value is malformed"
            ) from exc
    return result


def _command_option_value(command: Sequence[str], option: str) -> str:
    indexes = tuple(index for index, token in enumerate(command) if token == option)
    if len(indexes) != 1:
        raise PublicRedockingBenchmarkError(
            f"engine command must contain exactly one {option}"
        )
    index = indexes[0]
    if index + 1 >= len(command) or command[index + 1].startswith("--"):
        raise PublicRedockingBenchmarkError(
            f"engine command value is missing for {option}"
        )
    return command[index + 1]


def _command_seed(command: Sequence[str]) -> int:
    value = _command_option_value(command, "--seed")
    try:
        seed = int(value)
    except ValueError as exc:
        raise PublicRedockingBenchmarkError(
            "engine command --seed must be a canonical integer"
        ) from exc
    if str(seed) != value or not 0 <= seed <= 2_147_483_647:
        raise PublicRedockingBenchmarkError(
            "engine command --seed must be a canonical signed-32-bit integer"
        )
    return seed


def _require_command_flag(command: Sequence[str], flag: str) -> None:
    if sum(token == flag for token in command) != 1:
        raise PublicRedockingBenchmarkError(
            f"engine command must contain exactly one {flag}"
        )


def _require_case_input_path(
    command: Sequence[str],
    option: str,
    *,
    expected_path: Path,
    engine_id: str,
) -> None:
    value = _command_option_value(command, option)
    if value != str(expected_path):
        raise PublicRedockingBenchmarkError(
            f"{engine_id} command {option} is outside the canonical case path"
        )


def _command_run_root(
    command: Sequence[str],
    *,
    case_id: str,
    engine_id: str,
) -> Path:
    output_value = _command_option_value(command, "--out")
    output = Path(output_value)
    if (
        not output.is_absolute()
        or str(output) != output_value
        or output.name != f"{case_id}.sdf"
        or output.parent.name != engine_id
        or output.parent.parent.name != "poses"
    ):
        raise PublicRedockingBenchmarkError(
            f"{engine_id} command --out is outside the canonical run path"
        )
    return output.parents[2]


def _validate_engine_commands(
    identity: "PublicRedockingEngineIdentity",
    rows: Sequence["PublicRedockingCaseResult"],
    *,
    policy: "PublicRedockingEvaluationPolicy",
) -> Path:
    if any(row.execution_command[0] != identity.command[0] for row in rows):
        raise PublicRedockingBenchmarkError(
            f"{identity.engine_id} row command executable contradicts its identity"
        )
    run_roots = {
        _command_run_root(
            row.execution_command,
            case_id=row.case_id,
            engine_id=identity.engine_id,
        )
        for row in rows
    }
    if len(run_roots) != 1:
        raise PublicRedockingBenchmarkError(
            f"{identity.engine_id} rows do not share one canonical run root"
        )
    run_root = next(iter(run_roots))
    if identity.engine_id == "engine_v2":
        if identity.command[0] != PUBLIC_REDOCKING_RUNNER_ID:
            raise PublicRedockingBenchmarkError(
                "Engine V2 identity does not use the frozen runner"
            )
        torch_version = _command_option_value(identity.command, "--torch-version")
        expected_identity_command = (
            identity.command[0],
            "engine_v2",
            "--candidate-count",
            "64",
            "--cpu",
            str(policy.cpu_count),
            "--torch-version",
            torch_version,
        )
        if identity.command != expected_identity_command:
            raise PublicRedockingBenchmarkError(
                "Engine V2 identity command does not match the frozen grammar"
            )
        for row in rows:
            case_directory = run_root / "inputs" / row.case_id
            expected_command = (
                identity.command[0],
                "engine_v2",
                "--case-id",
                row.case_id,
                "--receptor",
                str(case_directory / f"{row.case_id}_protein.pdb"),
                "--ligand",
                str(case_directory / f"{row.case_id}_ligand_start_conf.sdf"),
                "--pocket-source",
                str(case_directory / f"{row.case_id}_ligand.sdf"),
                "--candidate-count",
                "64",
                "--cpu",
                str(policy.cpu_count),
                "--seed",
                str(frozen_public_redocking_case_seed(row.case_id)),
                "--out",
                str(run_root / "poses" / "engine_v2" / f"{row.case_id}.sdf"),
            )
            if row.execution_command != expected_command:
                raise PublicRedockingBenchmarkError(
                    "Engine V2 row command does not match the frozen grammar"
                )
            for option, suffix in (
                ("--receptor", "protein.pdb"),
                ("--ligand", "ligand_start_conf.sdf"),
                ("--pocket-source", "ligand.sdf"),
            ):
                _require_case_input_path(
                    row.execution_command,
                    option,
                    expected_path=case_directory / f"{row.case_id}_{suffix}",
                    engine_id="Engine V2",
                )
        return run_root

    mode_options = (
        ("--scoring", "vina", "--cnn_scoring", "none")
        if identity.engine_id == "vina"
        else (
            "--scoring",
            "vina",
            "--cnn_scoring",
            "rescore",
            "--cnn",
            "crossdock_default2018",
        )
    )
    expected_identity_command = (
        identity.command[0],
        *mode_options,
        "--cpu",
        str(policy.cpu_count),
        "--no_gpu",
        "--timeout-seconds",
        str(policy.external_timeout_seconds),
    )
    if identity.command != expected_identity_command:
        raise PublicRedockingBenchmarkError(
            f"{identity.engine_id} identity command does not match the frozen grammar"
        )
    expected_binary = (
        run_root / "private-external-binary" / identity.implementation_sha256
    )
    if identity.command[0] != str(expected_binary):
        raise PublicRedockingBenchmarkError(
            f"{identity.engine_id} identity does not use its canonical staged binary"
        )
    for row in rows:
        case_directory = run_root / "inputs" / row.case_id
        expected_command = (
            identity.command[0],
            "--receptor",
            str(case_directory / f"{row.case_id}_protein.pdb"),
            "--ligand",
            str(case_directory / f"{row.case_id}_ligand_start_conf.sdf"),
            "--autobox_ligand",
            str(case_directory / f"{row.case_id}_ligand.sdf"),
            "--autobox_add",
            "4",
            "--num_modes",
            "5",
            "--exhaustiveness",
            "1",
            "--cpu",
            str(policy.cpu_count),
            "--no_gpu",
            "--seed",
            str(frozen_public_redocking_case_seed(row.case_id)),
            "--out",
            str(run_root / "poses" / identity.engine_id / f"{row.case_id}.sdf"),
            *mode_options,
        )
        if row.execution_command != expected_command:
            raise PublicRedockingBenchmarkError(
                f"{identity.engine_id} row command does not match the frozen grammar"
            )
        for option, suffix in (
            ("--receptor", "protein.pdb"),
            ("--ligand", "ligand_start_conf.sdf"),
            ("--autobox_ligand", "ligand.sdf"),
        ):
            _require_case_input_path(
                row.execution_command,
                option,
                expected_path=case_directory / f"{row.case_id}_{suffix}",
                engine_id=identity.engine_id,
            )
    return run_root


def _selection_key(case_id: str) -> tuple[str, str]:
    payload = f"{PUBLIC_REDOCKING_SELECTION_SALT}:{case_id}".encode("ascii")
    return hashlib.sha256(payload).hexdigest(), case_id


def _selected_case_ids(source_ids: Sequence[str]) -> tuple[str, ...]:
    selected = sorted(source_ids, key=_selection_key)[:PUBLIC_REDOCKING_COHORT_COUNT]
    return tuple(sorted(selected))


_FROZEN_CASE_IDS_TEXT = """
5SAK_ZRY
5SB2_1K2
5SD5_HWI
5SIS_JSM
6M2B_EZO
6M73_FNR
6T88_MWQ
6TW5_9M2
6TW7_NZB
6VTA_AKN
6WTN_RXT
6XBO_5MC
6XCT_478
6XG5_TOP
6XHT_V2V
6XM9_V55
6YJA_2BA
6YMS_OZH
6YQV_8K2
6YQW_82I
6YR2_T1C
6YRV_PJ8
6YSP_PAL
6YT6_PKE
6YYO_Q1K
6Z0R_Q4H
6Z14_Q4Z
6Z1C_7EY
6Z2C_Q5E
6Z4N_Q7B
6ZAE_ACV
6ZC3_JOR
6ZCY_QF8
6ZK5_IMH
6ZPB_3D1
7A1P_QW2
7A9E_R4W
7A9H_TPP
7AFX_R9K
7AKL_RK5
7AN5_RDH
7B2C_TP7
7B94_ANP
7BCP_GCO
7BJJ_TVW
7BKA_4JC
7BMI_U4B
7BNH_BEZ
7BTT_F8R
7C0U_FGO
7C3U_AZG
7C8Q_DSG
7CD9_FVR
7CIJ_G0C
7CL8_TES
7CNQ_G8X
7CNS_PMV
7CTM_BDP
7CUO_PHB
7D5C_GV6
7D6O_MTE
7DKT_GLF
7DQL_4CL
7DUA_HJ0
7E4L_MDN
7EBG_J0L
7ECR_SIN
7ED2_A3P
7ELT_TYM
7EPV_FDA
7ES1_UDP
7F51_BA7
7F5D_EUO
7F8T_FAD
7FB7_8NF
7FHA_ADX
7FRX_O88
7FT9_4MB
7JG0_GAR
7JHQ_VAJ
7JMV_4NC
7JXX_VP7
7JY3_VUD
7K0V_VQP
7KB1_WBJ
7KC5_BJZ
7KM8_WPD
7KRU_ATP
7KZ9_XN7
7L00_XCJ
7L03_F9F
7L5F_XNG
7L7C_XQ1
7LCU_XTA
7LEV_0JO
7LJN_GTP
7LMO_NYO
7LOE_Y84
7LOU_IFM
7LT0_ONJ
7LZD_YHY
7M31_TDR
7M3H_YPV
7M6K_YRJ
7MFP_Z7P
7MGT_ZD4
7MGY_ZD1
7MMH_ZJY
7MOI_HPS
7MSR_DCA
7MWN_WI5
7MWU_ZPM
7MY1_IPE
7MYU_ZR7
7N03_ZRP
7N4N_0BK
7N4W_P4V
7N6F_0I1
7N7B_T3F
7N7H_CTP
7NF0_BYN
7NF3_4LU
7NFB_GEN
7NGW_UAW
7NLV_UJE
7NP6_UK8
7NPL_UKZ
7NR8_UOE
7NSW_HC4
7NU0_DCL
7NUT_GLP
7NXO_UU8
7O0N_CDP
7O1T_5X8
7ODY_DGI
7OFF_VCB
7OFK_VCH
7OLI_8HG
7OMX_CNA
7OP9_06K
7OPG_06N
7OSO_0V1
7OZ9_NGK
7OZC_G6S
7P1F_KFN
7P1M_4IU
7P2I_MFU
7P4C_5OV
7P5T_5YG
7PGX_FMN
7PIH_7QW
7PJQ_OWH
7PK0_BYC
7PL1_SFG
7POM_7VZ
7PRI_7TI
7PRM_81I
7PT3_3KK
7PUV_84Z
7Q25_8J9
7Q27_8KC
7Q2B_M6H
7Q5I_I0F
7QE4_NGA
7QF4_RBF
7QFM_AY3
7QGP_DJ8
7QHG_T3B
7QHL_D5P
7QPP_VDX
7QTA_URI
7R3D_APR
7R59_I5F
7R6J_2I7
7R7R_AWJ
7R9N_F97
7RC3_SAH
7RH3_59O
7RKW_5TV
7RNI_60I
7ROR_69X
7ROU_66I
7RSV_7IQ
7RWS_4UR
7RZL_NPO
7SCW_GSP
7SDD_4IP
7SFO_98L
7SIU_9ID
7SUC_COM
7SZA_DUI
7T0D_FPP
7T1D_E7K
7T3E_SLB
7TB0_UD1
7TBU_S3P
7TE8_P0T
7TH4_FFO
7THI_PGA
7TM6_GPJ
7TOM_5AD
7TS6_KMI
7TSF_H4B
7TUO_KL9
7TXK_LW8
7TYP_KUR
7U0U_FK5
7U3J_L6U
7UAS_MBU
7UAW_MF6
7UJ5_DGL
7UJF_R3V
7ULC_56B
7UMW_NAD
7UQ3_O2U
7UTW_NAI
7UXS_OJC
7UY4_SMI
7UYB_OK0
7V3N_AKG
7V3S_5I9
7V43_C4O
7VB8_STL
7VC5_9SF
7VKZ_NOJ
7VQ9_ISY
7VWF_K55
7W05_GMP
7W06_ITN
7WCF_ACP
7WDT_NGS
7WJB_BGC
7WKL_CAQ
7WL4_JFU
7WPW_F15
7WQQ_5Z6
7WUX_6OI
7WUY_76N
7WY1_D0L
7X5N_5M5
7X9K_8OG
7XBV_APC
7XFA_D9J
7XG5_PLP
7XI7_4RI
7XJN_NSD
7XPO_UPG
7XQZ_FPF
7XRL_FWK
7YZU_DO7
7Z1Q_NIO
7Z2O_IAJ
7Z7F_IF3
7ZCC_OGA
7ZF0_DHR
7ZHP_IQY
7ZL5_IWE
7ZOC_T8E
7ZTL_BCN
7ZU2_DHT
7ZXV_45D
7ZZW_KKW
8A1H_DLZ
8A2D_KXY
8AAU_LH0
8AEM_LVF
8AIE_M7L
8AP0_PRP
8AQL_PLG
8AUH_L9I
8AY3_OE3
8B8H_OJQ
8BOM_QU6
8BTI_RFO
8C3N_ADP
8C5M_MTA
8CNH_V6U
8CSD_C5P
8D19_GSH
8D39_QDB
8D5D_5DK
8DHG_T78
8DKO_TFB
8DP2_UMA
8DSC_NCA
8EAB_VN2
8EX2_Q2Q
8EXL_799
8EYE_X4I
8F4J_PHO
8F8E_XJI
8FAV_4Y5
8FLV_ZB9
8FO5_Y4U
8G0V_YHT
8G6P_API
8GFD_ZHR
8HFN_XGC
8HO0_3ZI
8SLG_G5A
""".strip()
FROZEN_PUBLIC_REDOCKING_CASE_IDS = tuple(_FROZEN_CASE_IDS_TEXT.splitlines())
PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS = (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
    FROZEN_PUBLIC_REDOCKING_CASE_IDS[1],
)
PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS = (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS
)
PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS = tuple(
    case_id
    for case_id in FROZEN_PUBLIC_REDOCKING_CASE_IDS
    if case_id not in PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
)
FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS = tuple(
    """
5S8I_2LY
6VS3_R6V
6W59_SZD
6X8D_ARA
6XAF_GDP
6XUM_30L
6Y7L_QMG
6YDY_K73
6Z5Z_BDF
6ZR8_QOZ
6ZT2_QPK
6ZX3_QRZ
6ZXQ_IMO
7AA0_R6B
7AMC_73B
7AS1_21G
7AVI_S2Q
7B0E_C2E
7BA0_T5H
7BHX_TO5
7BJ6_TVK
7BLA_WCS
7BLG_GAL
7C6P_SQH
7D0P_1VU
7D8Q_GZF
7D9L_GSF
7DIN_MPO
7E2S_BLA
7EN7_J79
7JGW_V9S
7JNB_A2G
7JR8_VH7
7JUD_MMA
7K41_VUA
7KFO_IAC
7KLX_WOV
7KP6_WTP
7KQU_YOF
7L6D_BMF
7L81_UD4
7LB3_XXS
7LZQ_YJV
7M41_YQG
7MAE_XUS
7MEU_MGP
7MRH_ZMJ
7MS7_ZQ1
7MZS_GLA
7NA4_1I9
7NB4_U6Q
7NLK_UHK
7NML_I7B
7NR6_UO8
7NTG_F6R
7OCB_V88
7ODX_DGP
7OEO_V9Z
7OKC_VFE
7OKF_VH5
7OLT_58J
7OMJ_GCP
7ORW_7WA
7OU8_1XI
7P2W_4QR
7P4J_5JK
7P4V_DAT
7P85_5ZG
7PA4_C
7Q19_DSM
7QK0_EBL
7QSW_CAP
7REE_4LY
7RH8_UTP
7RPZ_6IC
7RUI_7QZ
7RWO_7WN
7S45_ACO
7S9H_7PP
7SED_8VD
7SGV_L30
7SNE_9XR
7SSM_B7L
7T0U_E3I
7T2I_E9F
7T3F_EM0
7T9O_GEI
7TWC_CXS
7TXP_0FX
7UEY_N0R
7UF2_5SP
7UJ4_OQ4
7UMV_NUU
7UP3_NZ0
7USH_82V
7V14_ORU
7V8Z_5YH
7VBU_6I4
7VJT_7IJ
7VYJ_CA0
7W6F_8I6
7WN5_JGL
7XEK_9YX
7XIJ_EJ3
7ZDY_6MJ
7ZXZ_K9R
7ZYS_KNR
7ZZB_KGX
8ACL_LQL
8AEU_M0L
8AIJ_M9I
8AJX_FUM
8BN6_R53
8BPL_CP
8BRO_R7E
8C5D_GTB
8C7Y_TXV
8CGC_LMR
8CI0_8EL
8DW5_FQ7
8DZT_G4P
8E77_ULP
8EAD_UY0
8ERS_WQO
8FLN_Y7W
8FV9_80J
8G43_ZU6
8H0M_2EH
""".strip().splitlines()
)
PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256 = (
    "ecc91c660896245f62ad8b583cfa4f45e50038cf513c384f6bdb56d406278248"
)


def require_public_redocking_contamination_registry(
    payload: object,
) -> Mapping[str, object]:
    """Validate the result-blind reclassification of pre-freeze executions."""

    if not isinstance(payload, Mapping):
        raise PublicRedockingBenchmarkError(
            "contamination registry must be a mapping"
        )
    registry = dict(payload)
    observed_self_hash = registry.pop("registry_sha256", None)
    if observed_self_hash != _sha256(registry):
        raise PublicRedockingBenchmarkError(
            "contamination registry self-hash mismatch"
        )
    if observed_self_hash != PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SHA256:
        raise PublicRedockingBenchmarkError(
            "contamination registry identity drifted"
        )
    registry["registry_sha256"] = observed_self_hash
    if registry.get("schema_id") != (
        PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SCHEMA_ID
    ):
        raise PublicRedockingBenchmarkError(
            "contamination registry schema is unsupported"
        )
    if registry.get("contaminated_development_case_count") != 300:
        raise PublicRedockingBenchmarkError(
            "contaminated development denominator drifted"
        )
    if registry.get("contaminated_development_case_ids_sha256") != _sha256(
        list(PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS)
    ):
        raise PublicRedockingBenchmarkError(
            "contaminated development cases drifted"
        )
    if registry.get("fresh_internal_blind_candidate_count") != 128:
        raise PublicRedockingBenchmarkError(
            "fresh internal blind denominator drifted"
        )
    if registry.get("fresh_internal_blind_case_ids_sha256") != (
        PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256
    ):
        raise PublicRedockingBenchmarkError(
            "fresh internal blind case identity drifted"
        )
    if registry.get("source_report_execution_receipt_count") != 900:
        raise PublicRedockingBenchmarkError("historical receipt count drifted")
    if registry.get("source_report_sha256") != PUBLIC_REDOCKING_HISTORICAL_REPORT_SHA256:
        raise PublicRedockingBenchmarkError("historical report identity drifted")
    if registry.get("coverage_verified_before_metric_values_inspected") is not True:
        raise PublicRedockingBenchmarkError(
            "historical coverage was not verified before metrics were inspected"
        )
    if registry.get("result_values_inspected_before_reclassification") is not False:
        raise PublicRedockingBenchmarkError(
            "contamination reclassification was not result-blind"
        )
    if registry.get("old_298_holdout_claim_invalidated") is not True:
        raise PublicRedockingBenchmarkError(
            "obsolete 298-case claim was not invalidated"
        )
    if registry.get("fresh_result_values_inspected") is not False:
        raise PublicRedockingBenchmarkError(
            "fresh internal blind result values were inspected"
        )
    if registry.get("external_independent_validation_still_required_for_public_claim") is not True:
        raise PublicRedockingBenchmarkError(
            "external public-claim review boundary is missing"
        )
    return MappingProxyType(registry)


def frozen_public_redocking_case_seed(case_id: str) -> int:
    """Return the immutable shared Engine V2/Vina/GNINA seed for one case."""

    try:
        index = FROZEN_PUBLIC_REDOCKING_CASE_IDS.index(case_id)
    except ValueError as exc:
        raise PublicRedockingBenchmarkError(
            "case seed requested for a non-frozen case"
        ) from exc
    return PUBLIC_REDOCKING_CASE_SEED_BASE + index


_FROZEN_MATERIALIZATION_RECEIPT_SHA256S_TEXT = """
5SAK_ZRY,179800efd20944bc9ab41a479a9f9b586698419455971438cdc42006c572f99d
5SB2_1K2,687eb5d0edb3156d303371d6a4c851db4280b2bc2c817fd0c6e448e099c8f33d
5SD5_HWI,120d4d28e04604941b93b17d491682526b977971777db53bf964d1d5d2a12dfb
5SIS_JSM,92a2bfadcf27ec61a620e387aa8e21ac87ae4e09e15c4a0c2035c4de538c2201
6M2B_EZO,d9702520e85a459ae1e5fc4843bcd88c05dd0c3f316258971f3e61859088ec4e
6M73_FNR,fdf1646d366a4adad31ed9ef973e53cf576d07f22aff03b0c486baaf353eb07e
6T88_MWQ,82e4ad0942b85141a5f17b5a5c36744e40fe4ce863d4006ef29801d377bd5f06
6TW5_9M2,076e1fa07a885cd231a557162f73c2f56912a7a6d237d3f4972b12ff59ebef9e
6TW7_NZB,521cb3fa141424e0d7b57bfc667718b305e1cd8f02f12ac05ddffe264b76d6d1
6VTA_AKN,79d66ad929ee3c38b4f6af120167bd9bb719fe393534d74733268197611498a2
6WTN_RXT,35f47abe5e7ea517fa08a90a1a301d1672dba5a5e18c7cbf2211f21032b97adf
6XBO_5MC,eb2e0849175a0fef1e94108c00bfa1d39f83472b9b858d38546a26fd23ecd27c
6XCT_478,8878a110ad052b90faaec04fc3acfb6c4f46bccc8ecbd5d1d7a96d4ed607cb69
6XG5_TOP,bd17e9b77223a5ddeb413eb1827a2f85c13ce3080e496e73a7a23eebfaf0f6fa
6XHT_V2V,a312fbee13e507a7ea0627273a7382fcc1442a9a19cf1790b886c6fd8694a227
6XM9_V55,4949fed051c172ec8c17b535c28f19c0bf817b66c2ffc57c931b921aeea7c438
6YJA_2BA,d9a681373b084937bdce6ca055c0bdf062663dab71e3e858e2a5b4a78494e53a
6YMS_OZH,4cceaa292dbf549a5e8276db21d129b035768ecb234fea53d2c3fcad2b3f48fb
6YQV_8K2,4a4d922142bb305f00b2ee1691e53801fd78fb683261b774f4bc522b0090ecfa
6YQW_82I,81b9259af4702be17214742144cb8e41d74299f4a548a45d5dd83220f17520d4
6YR2_T1C,ccf5e437f8440edb93085456bfd5c599818e7c2bebb314c0ee0759b20912240f
6YRV_PJ8,428fd166417b9244116b5bdd5d5ae8039228b042865f116aa0ceec6f8d3c2610
6YSP_PAL,14bc466a724080d40135faeaef9d02628e50b2c0602a1a576c0ee0fcb2fb7837
6YT6_PKE,e665f0ae8706335fb02a231837077c28f0e4af94edd107d044b4e14916ba0fcd
6YYO_Q1K,a645580c93fe953241af5c5d145ca2512b673e753d1500f60c30a2ed53db62f3
6Z0R_Q4H,c5ffd4160ab6259326c555f60e2dcba8dcb2a6a3eae6aaf308e660fcdaffd4e1
6Z14_Q4Z,6fea6eac81ee14837109e6b1996c43c0b87953d2719dbb8f1fe84f0021dd3e83
6Z1C_7EY,93d3374eef2356840e494484e7640403da1a2d135effafdc61003c6f4c14a018
6Z2C_Q5E,cacbc2eab72c170e9daac1646aefdff466a7af93f99a0d1e8e73c7c9ac9e7ac7
6Z4N_Q7B,22802fc0835d8e5d36f4bce6adc056fce3b1e6e0c005924ab298ce6ad1f25735
6ZAE_ACV,a4faa1a419f622cd0cf358700e5a4295016c69d57904206728e5894a4cbea039
6ZC3_JOR,ab83b9b0983c6f7ca0cbf10a4db6d823d866829b3785b57eb0f1832d79010f13
6ZCY_QF8,b4a1c4a8470db0382d0bd4a7ef94baa0859b30de6c4b760b30c07409884a235c
6ZK5_IMH,ee6d1d3e5d196212de9ddf4bf565fe0346983b13df6833cc15bbc272ca7cb005
6ZPB_3D1,5c920d9e30c4296ad774905263fa4a30904dc6706e423b34d04bf21c69f96950
7A1P_QW2,47b0733814b409894a5c17b4d31511be60a1b87c1d673242320893386e282002
7A9E_R4W,9084a6359445d26567a24a9ed7b58e95b8d95d29fe6d75b38e154e0e6cf1958e
7A9H_TPP,e862dc75c10b13ff05e0c0cb65ae7e8714b7f003779948a1ecce5d9a5b436ee7
7AFX_R9K,bb6e6a32e9e83098478ea5467d26b55105577f8a974bfce464b8cc871c53841b
7AKL_RK5,3ea5e87075ca411a762a0be91e9a497ba939a7fc87c68d8301f4994130a0a3d4
7AN5_RDH,3e7d7b921581a7b2303de4aac82c5955133b3ea42617243647e499dff63f3f8e
7B2C_TP7,c900685326b08e997ed007dbf11c0be9b09f8e60cde9190f15bbecdb75fcc070
7B94_ANP,f0e2d18787ea56aad5dec47802a7185dd2bba8f807b4faf50650dca69ec08c4e
7BCP_GCO,98d21a30a363cb512c62a7dd0a07d7b17c9c6f44ba4b1f9095cfa308b6ca1d37
7BJJ_TVW,e0ebb52f02f6bcb693a5ccf501e4d01aba856042d6e11466915a1160a6a086c2
7BKA_4JC,713183db8209c7f85853a107873681e9531cb9cd87ee819a125d550ef5988914
7BMI_U4B,182ce3ed23d1c433f3005f48471dce169d416953014186651a8f3ad1b927223e
7BNH_BEZ,979f19672bc610a770f92f5eb54fc75d70063cb2cc45be924471a4af311d5f5d
7BTT_F8R,05be4d0655da27420ddd26a20947dcd335046e2e7629272fbb9673c6dbf62ac3
7C0U_FGO,89624c17d084394e2d86706e82f028a0d1da54b0b43c0f2b378baa0d55476a12
7C3U_AZG,35c0aca30f7f3c1f7a39f146a4b3b9bbc8628ca90a4612f098f4778c5ee97f57
7C8Q_DSG,ab35d2e81e7216e38f85d89694970cbaa61fec5febf2a577d99beed60a25cf37
7CD9_FVR,0b201a9574d7495f9f18af32920182c847429a8139ecfce55a99629ebef0573f
7CIJ_G0C,f5e6ae241bae5c22dc4d0e08b230f9b1ac13e05536910033ab1fc8e59258a92f
7CL8_TES,d1f7a112412b182be6e0446e426b1d2daf9027ff64ca1345cbcaf71a477e9012
7CNQ_G8X,501eee36e71ac142c12de528a25b4f06f5e818b3837c9aeae2464a42532a02d1
7CNS_PMV,6b628914bc0388e80c85aae52c2a443464db94617571bc93a5e576542bdcfeb6
7CTM_BDP,b4f6f2ef9a5c90da00e4fb068258848438b10ac9aeb2ecb829984d9d7f5bceb9
7CUO_PHB,e0f64ecf466511210f9fd8739c8a536ae795e4a4044f8cb88b46756a90036d66
7D5C_GV6,b8c263f55f70762ceb93cc6faddb7c130d1589a6a7f2a40e8da86f754c68ea4a
7D6O_MTE,554c1f56a0a92e081f1d55fc2c3a9896d7c41db5a81375a1d740bf1ba82ffb59
7DKT_GLF,5b0273d292800d2d287649a06f338bfec74c677e42ecc8c4f15cc790d797c3df
7DQL_4CL,6a1e17672096b0b9d6773fccf82ad84791524f157dcf4a384465c37a6267d59b
7DUA_HJ0,66c3485f9311876619efa99a8503e22319fd6ac118d8400dbec6e2ccd4bb25d3
7E4L_MDN,e409d185bbe15bc6f9b3f9e4d9709ac61952b1e13634cdab21cc3c83fdc002d3
7EBG_J0L,0c2dc8155f9360d4fc269be3e1ca67e5c5f7db99cd942afac75a802c4d6013d3
7ECR_SIN,d7196ff59a1e827cd6d878a864433844f9eb44bf2e49a7edf88eec2e6b48f843
7ED2_A3P,f758dbd9d404f7cf5442e54437d57e1aa15901f794d53aac42e6eb4e46622dbc
7ELT_TYM,d54f2cdc96989954922c23f96083a460ea25e1b9d732034a65d9ad0ca83741b9
7EPV_FDA,64a371d446ea625dfd70c15514359fce2f39cb2c157b2c6c7a89d70fa6fcd4e3
7ES1_UDP,df992947329e261c8b6fbad95ae027513265f064fde3661ab1a87f987aa681db
7F51_BA7,e865a3cc34d7475d4eb4c709da0989f8e36d3867e7e5d939568587d02ac2c792
7F5D_EUO,16bd3a2f91328ebcd54de16a6ff3ecc01f5bd557bb71f8edc39d14b15f947ba3
7F8T_FAD,7e499d51b38395f275a80348e0e98bea7e1a28e8649599d0a681fa69e121951a
7FB7_8NF,ce88cd8026c34cab8ee9d899df480de7d46a5733957f8db260b686a3eb877bfe
7FHA_ADX,67f17adc4c3ebf3fed7cf45614b472603b45fe1786ddc52248004385d27ffb76
7FRX_O88,bfa8800f5bf5bc3fae6b18cf77da04b28d1b99859e8d1e79728199f4b13a3a86
7FT9_4MB,59ce4d66dc1df7481f234709e6afc4ccab8286afa1fe29869e84e7b955ccce5c
7JG0_GAR,299f535d5afb3d6e83dde6f74c05398e60e6df62d3a7b0a1b8fdfb2eaf497f9d
7JHQ_VAJ,2cef9425fecf96740093751e245075e5355b06d6217c57c073d6408399fc1e3a
7JMV_4NC,8fe58891cf51ca218e46144eb09989c8b147ca3731a08aeb89c3853f54d1822c
7JXX_VP7,8e53f093fb0a2453847e56f3868df2e3142d788a5f4e1d80046b75912f815ebd
7JY3_VUD,b6aff5e9058724898da0f14cf6f567d438181dda464f38225ed67768c4d1f270
7K0V_VQP,1ea03fbd68ebfe2f559f8161bef9e153ce3e87272a80872edc93ff26fe183d97
7KB1_WBJ,77ba6ad547a39656c838f1de9330ce00c990840fa9db7f9aef7f70227f97b241
7KC5_BJZ,3231099baf83a6d17e2d164be3d859c6d54cb0659feb6dc33bd869cea82687a6
7KM8_WPD,0b83f0223255c65ca0d03138c46b2bc98b3caad9b2aeefc82aa9b58942566306
7KRU_ATP,be0b3857d3a0cf1e1d45d2fc06c156d0d679a698d821136f6661171e10729678
7KZ9_XN7,cb504865acc6555f15d5866b0da3a7f45db4f60455fd014c73f2020e03b19ce0
7L00_XCJ,982e7afe67916fa0a6f8e4e8fa108de6a46799811e1decdccba62d0bb9046d9b
7L03_F9F,8c7b03694ebacb6689c95a331e626e9b53d0b7c88d0e3af3b3be839ee65205db
7L5F_XNG,06ef5d6db1f3e2b6398d03103a25bbcacc73aeec45f29ac47b9d682164719324
7L7C_XQ1,05dcbde36846d4d492f1ceb07515bc7a22aee43d1d6ce76507530695b28cbd4f
7LCU_XTA,af067080e015319fa576c100358feeee4d2707f494e236352c885b56734565c6
7LEV_0JO,ebff3aa367fa30e48ecde0b5143c83101518b0cb39dda14852ea96f8103123eb
7LJN_GTP,07a2c2ae8409a2162be9914d03b2ab45368510b3150424a41014aa36e2513ebb
7LMO_NYO,4dce518e3df1ff6906819b1209feac5a47eaccaccdc611dbff402d9b9052a1c6
7LOE_Y84,4c6b45b03205d51cdd29e330c5d064ff81217910c6b78460273d504d2de77389
7LOU_IFM,69bb3ad30d31d11351aff0b4bb967b11ebf9cf7cf91d87a884733b038e05a844
7LT0_ONJ,c7c3a8ff49968a53194cb8b134a1be381829cc030cb9d45bfa100f6ceec1f5f2
7LZD_YHY,db6adf9c6c0ea80901c13a66390f8bf5a1fe5f7db88ef09cf46d2f38415e2777
7M31_TDR,9ae1f50a6695dae76cb45c617343c9967909882cf6450922bbc4e949b41054de
7M3H_YPV,c33cce97627fd81a4a1372bbf8a064de45f12e3ed6fef626cdf5dd5dd9c63577
7M6K_YRJ,2170538f3c8e5b5bd9094f44fcc5ca47ae67694ff0f97d66b86e9aeab81d4801
7MFP_Z7P,12655ae84b79a4594922abc0c9f5e645614ec3d2d4ebf49e54bc200c1e6b487d
7MGT_ZD4,268a1e825adf55e2d50a8a4528940124a22502a36b87a7269e1adf1be44a447d
7MGY_ZD1,574c4094b8ec0275c72e4734b1f0c0c3f1f0b5ba60e777caf7df955dfc1579f2
7MMH_ZJY,e0bbf924bb6d1f219738b8666c295571e264dbf7fb5e9ac2d6e6e7c36e7ec741
7MOI_HPS,21378ac85214fc7c9304ba8a2216381f4f28c389991551bc709c65a2fc284160
7MSR_DCA,464a6ab890bad2872be277451a3524af1f648279b1eb47b47516dfcef8cfd770
7MWN_WI5,f03b20cda8b7b6481014fc00d3770f56330eef5e8d14ac67b646ef7997582d80
7MWU_ZPM,28a6b39e2b396a85a43b466c9c00858e3b1f9ca72edaa068cae5391965cfa318
7MY1_IPE,257a3d86e1451f830ef1a5728a7c0f08a2d48f8c4b7b400f33fd7dd9fa4e7d5d
7MYU_ZR7,607a624c3da1e5732ab126952d2fbefce224e03b7404cc72c50ca9b78d844562
7N03_ZRP,8a1c2f237ba6cf2bf7d5fe1f10209c0533fd45716e2685646fe0241c6d89ea85
7N4N_0BK,cd3d5a321e63c4390a5e098eb76bd94f76d7b23346767dcc4d7858eff46e1d94
7N4W_P4V,e4a74c88ef45f2d003c65dd2f3f221106f3cda5d6a499dbde3ffc0ae445bd0a1
7N6F_0I1,8d7c79254466d9cb7c09bed8ef48c2895734afae5cf83996e4f57c4738926e0e
7N7B_T3F,c986f16ba96db9a40ace54bd6505ad24406bfcf1971d84c5ca4d70540c0fcddc
7N7H_CTP,7a5b6b7ea71410752e069674ddf9732ebf6830b0d515c4d6f322a8a688df8615
7NF0_BYN,35a4f5396a6f035301f51419609cf74757afcf4941c6a3319795b12e51591f2d
7NF3_4LU,5b90eb0768770fdbf0290964500fd34826dc3c33a9b09d4bb92e07b42f8f93dd
7NFB_GEN,b5fc36bf148f9b4877173011a8382f4ea8244c8d6170861e193fe3125ad1bdf3
7NGW_UAW,364ca67a43bc0c8ae932214c64a12eb129dbfca1d6736e22d9d82c69b40d865a
7NLV_UJE,ea2522a9dcbe90c6a12e3eaef830fc0db7759f96ebef3fbad783b79b73584b59
7NP6_UK8,2eec19bc3819d939110372e45f6461a1788edab719641b75b5649b2e7f189ed5
7NPL_UKZ,0179786b35208e550c3be39285cfdaea5c920144aa698c5aaf6d28b5b2085d4f
7NR8_UOE,5cd1751d888c919d9f08dab6d73ac7c073e0274ab196a3f8aad80bfe8b334c39
7NSW_HC4,855d02dffa306c523791c699d8753b9e0bd0d1c1d1a8ea674b7c95b501d0a060
7NU0_DCL,06041a9434a63aa5a47047739394f780fe8eb791fa1dfc6aac39180d09fad191
7NUT_GLP,4705f7b98a601db876b990abbe372bc7431b5dc3de3c06f470ad97ff68adc08e
7NXO_UU8,89982e07a65e09a374a1f2f5ea554ba2bb2dd73c6cb91a6425989018b7b6debb
7O0N_CDP,82057ffcf612f2e456575424d3efd808304a55f5c2383650bbc9c9eb8e04199b
7O1T_5X8,7218478f5e64d5fbec35be4f956a4f6e187d097fbc8dd170ac5b97b3badede28
7ODY_DGI,9652b0aa7dfcebcd124db497f6288f6fec2f2325a446f46ff088d2aa767827fd
7OFF_VCB,7719495174e814a71a7fbaf332dd7c5d94fe2f39295db30f83f42a99aa2fe0a8
7OFK_VCH,22b2d9ac57ef3affbd7e4c78a55cc6849ebe00777ebc29798d891f96b79aabef
7OLI_8HG,8c6b346f8f731db833ad5e02fc4cb7371018c6768fa952fde10280a7200ef467
7OMX_CNA,c26b8341e4900fc917753ad8404023fd2136c625e8201d454e74aebce8bc8305
7OP9_06K,f4094f0e115311a585e23874a8c7bf89ce384413291d6c51a463adf914bb4463
7OPG_06N,44c26f0f9ac9f3aea8ed429fd2e258d8bc65be1ab4346fb6ca2af25654f3aa1d
7OSO_0V1,83d683ef3d857d82a9859ec95ffd3cfaf0f0cb69c129ca35f8121d700f83d78c
7OZ9_NGK,d5c24645375f0af7eea38fda2fb75f88f30e13136e4d471af8307fc4e66458bb
7OZC_G6S,e078f6e759c931c5fe0078a81b6b36a54d9d7211db5e30e36a8e5f4e6932bc86
7P1F_KFN,3f97d14ba01f9aa070157e010f49710b4a97f12225eaf39571e44de27879ef0e
7P1M_4IU,879ec6240e61af266e6fb0074ed79264c0ce35574ce3d808ff9fa9bcc3d12eeb
7P2I_MFU,32800c18c5181d447980f81cbf72aeb8a00d9b591a97e7ba08e047cc568dc744
7P4C_5OV,f90e312c5a620abb99f378bb5709f2b0354f367246fdccaff9933f651a19bc6b
7P5T_5YG,9226e331bdaa6a123429566e2928fd089a87941fcfd7b40fe699808c46400390
7PGX_FMN,dfe1785923e4c06bff9a07533548d4751c92a337066a79cdd631f032a7d04220
7PIH_7QW,5f66ea26771deefaa54bc8e2a2c1821c52b43bfc30d98490a7743effef63cc92
7PJQ_OWH,673fa4396d668a7e90fdaf820728452be5da5d77e02eb89097d0250b085b3052
7PK0_BYC,b8bc94d9851d2fab84e229da00d86625971b9dc356c8aebbce04461d14b867a8
7PL1_SFG,0cfd9bf3628c2d5768c0d7635322e8f20c0aa1504ebd266cc635d94a2e0d7c2f
7POM_7VZ,7ec6a119e3f6697b8c51b8832b42a5419fac2a0d42380ca0e1f0f50ed477f9f1
7PRI_7TI,54b9e3cb7f2e48c5bbbdce47f785ac8d0cc6e1d8ddbca8541a4f7141d4540d47
7PRM_81I,819272df9fced08f25573086b524957f76d82311c9817fd92d7bba4623286668
7PT3_3KK,707a86ee46b2eb2ba216383caf967f7d35602e19cdc806ec272ed7b5bcc4cc97
7PUV_84Z,80d90288d54ba2f0f6306f96812c15658caaa735ec7a8d9303c89f9cbbd5fb53
7Q25_8J9,68eab67b7fc74a7a1d79106ce9d8e9f0d0b592f83abc8d8fd3b23458aabe9731
7Q27_8KC,b79bf7931c9d5352929968a84b7a46da2cb753165c9133ffceee998a86ae4939
7Q2B_M6H,1d72577cbf05bd7d8121e0d32ea133482ad05057268e99985b431c625a1b0d40
7Q5I_I0F,06770a754a708d3434fac29d2e1945d64f5cc9b9887d0617797b7786848c3904
7QE4_NGA,f8b99eaec186844d70f5f07c4e97e47c0340dbf0655956d4a78d7ce2a376f234
7QF4_RBF,01f87e01dc56ce26b104f29274f95127405ab3d9216b1aef0e33869d72270e3a
7QFM_AY3,c9527c161932a2a474d6abc80a3ab3688c32dc0320852f88a143596e152ef665
7QGP_DJ8,865da9ce5953035f2c2e9fcf24372eb9747d312b3ecf754f13b68b9e759f5b6e
7QHG_T3B,ae3f3ce6f87bc241710a65b1bf2af5a41c7af66b78a3b068c431e079b10b2af0
7QHL_D5P,1c042dba6e535402d08021e8021125e2201e08e2785ceb7884ffb5d873f6468a
7QPP_VDX,d8fceaa613b3e0cc30fa71f8e10e36d527a8b5d764c3c90bbb1cae29d2948bb3
7QTA_URI,e75b2b68accbc15f028bb679770d700e8ee3c9f8e442c1260b53ac3e716883b8
7R3D_APR,edd797064fce342639e9997daa32206d3cd04ddf87b28529f5baa68b61bd68ec
7R59_I5F,026c158a66168f8d5d721180837bc03044880d7b9560a24fa58c597891efeda9
7R6J_2I7,c8c5255fea873d3e8dc519e0a8e7f52d2bf5e706e575185886b4c2a5292b45ca
7R7R_AWJ,4f5b81c61961589117573910118606895b36cad5286296e822a9f2810b6653a8
7R9N_F97,12b02710cb08eae2a2261bbe154f4098d5194ef9e7eff00cdfa87faceb066a6e
7RC3_SAH,9da88819426f945d8469ab3269a55b7005c6de25a899fa141b4a69b913f3b8e8
7RH3_59O,069a69de481b89ec78d638060f4672e84fab010581775aae399b95eb7a3afc1a
7RKW_5TV,afd0b15695b61f0b4e7f4b5dba234f44cfa90a02f4d22e6ffeba1dd3af6c37b2
7RNI_60I,54b2f48e35099b9ce292ef4381dac0cb2ff88577128638d656473eb5756fb78c
7ROR_69X,d9354f2f278dd18556ddc9a9d3cf8a03504b01f2a7a83c3063f63ba07664301c
7ROU_66I,249257874d7459901bb8f2f9b14433950f254fa6c6f742dbf82f84b6d3774f7a
7RSV_7IQ,197526bb988d27d7db379c523af8642b6eedc2c4b67ec28d95d23f3e6ed41f39
7RWS_4UR,d8057655614dd71286b911142e521b229f0971b186b84e1430cd69b96da69b62
7RZL_NPO,3ae8a1fda8196d2f48104922618739c61391b796834acabfbfbfc36b0018b2c0
7SCW_GSP,5478fe1537b8262233a00eddc4c9fa4d901d20a79704b00c852c40de859b5c09
7SDD_4IP,1f66314ac45e392824f743331e5d2e6ef8037e801a0ffe431ff71c3b59db9119
7SFO_98L,eb965cd85f1fc9ce11e8f701082486a8127c6ec68af59fcbee42c432b8a25def
7SIU_9ID,a1488243e23954d5347b5815c41d0a7fd3700399168cb7fdb61016636f95fe91
7SUC_COM,d720d4f0d98883c59c50e3b5c466d18f4596a4d066b0b2d130fe95d180da50ec
7SZA_DUI,755abd4ff2195478024567fa223fff678ffeaab18ccc3acb53c6fc0ec89b1714
7T0D_FPP,6728b02f1517022b485d9d69ed603bd097bb93eb50a6b40e234c189705804bc7
7T1D_E7K,bceec808f36525c16fff8bef7245ed18f34afebf8221c50f1ef25df97f3df44d
7T3E_SLB,4b1e7075d411d71c147b32b04e1c734e8ec5bcbc059a319a846f6f1b91ef27d8
7TB0_UD1,d4c61c14f824945587ca6483ebec0dd90f7115bf7b93f9de2ef29d96459ef259
7TBU_S3P,a649eaf1234f1e387389552e33685709207c3f9affb0582279daf7eef82f7afa
7TE8_P0T,9696e3062982e9a53662504bfae9ffb3a98df7fa49dd3293e4a6d1c9e2b7681c
7TH4_FFO,53317b4ebc6ac60d7bcd2226c38b0677cbc1e7c55411abedc19551c8f2864196
7THI_PGA,d60b2a7950af309f6631a20f9f0aa8e58767b572b8fd4878ae48c10d30425d6a
7TM6_GPJ,3725c89cca2f3ce08fd575506b13ecfc161e6ccc1e8322d70b06ca5ffcd28bde
7TOM_5AD,e5d1161a6736becce25a8f9a5ede866c4a57ead1d0fea5279158f296d2b0660c
7TS6_KMI,2d93529cdd1b0dd3911e87a369698d31260261fa4550e02416af70c43199e20a
7TSF_H4B,155366649ab663ae6d5cba771e37dd4638b98489522e50ec52fb31d8a839e5a2
7TUO_KL9,35f03a9cfa4eb6940acc73d0cdcb4d7fcf3e37fd8142a11de44a63183dc0ff15
7TXK_LW8,6676a4abe6d507afe73da69087ac220dbdf9f5357198a6efe771223f2877651c
7TYP_KUR,506ec207e5dd77a4f2a363fc4b94156f53059eddb3c38341d14f82849d3f546e
7U0U_FK5,63a2109707d4fa94bff632a36207f438e5351b22936ed73b00a18a963f4d72cf
7U3J_L6U,e5264501530151156602692a3d92817461801993add21e9ccc67c88df8015427
7UAS_MBU,e16daa0324fa4a281c7bbbc401069b22846c582b40c11a54a543a9043709c728
7UAW_MF6,8bdf519d58267c52561a157f270192c146655aea9509dafbee96e405dbf32957
7UJ5_DGL,b5b15dfe9cda95f25cb583818ff01a4941151e0b74522c30e91c433004552e3f
7UJF_R3V,57326f333b9b3b4727c62e8d746f6674d1df6ac1f10476093e2befa01bfb0a75
7ULC_56B,5d9fb960a523438175b994d9e86f9f01ff2358605f941d41cebffe1c352c7ddc
7UMW_NAD,d5d9e02382c5f07fb6dff2dbdf014d03fe3e9c04aa1ac5d3eafc0a5533c90837
7UQ3_O2U,bc7e94d3d9e1830b8dc3b3e6b34eb12eb2aea0e1f65cd50eb9c9eef6be1d1529
7UTW_NAI,04cd0cabbdb0ca278d57976bd5623fe18ed670997fbd009e9e9a45932799493c
7UXS_OJC,e3770f446b777e45af653b26a45b56a9e57276b0d21dc7e241d05dacbd05c4a0
7UY4_SMI,9a89e35450ed870d089dee7f4a3ee2db5ae251f43412fa22fa85071876003a4d
7UYB_OK0,f6c6d3b4a22e8fa81666c9bf5351cf1f3cc5e03b92ccf4e7b158a307bb687e7f
7V3N_AKG,54ea5a5c22992d3e5b4baa94b7a795e73f36faa85bf8c5c2c7048228c133ecda
7V3S_5I9,bcb77d6f9fb1673c28e09cd8f1475e3425667d506321ae479d5f78e723005f68
7V43_C4O,657a4983aec19cb6ccc6b81be349a4bef14a8b64a0dc4321fdce867b89c2c1d6
7VB8_STL,8d1abfe14d2a2786e630ed0a56995128f064d340ff465af3de75fc03c21ffccd
7VC5_9SF,a6feca68ab2954dc58e8b0307f0e6f9bed2ad50bed081cb81ffbff1acd0fa857
7VKZ_NOJ,18599e984e288c6e629211db7c5a0b497052b02ba8eba5a3aa754ffbeef297b5
7VQ9_ISY,6894a6778fcec9e3c865714d77729fd7a97f2b516e22ec67117cd7ff67f83639
7VWF_K55,4f3d3f7c1b73c270a3c9797bc3762ffe15234bb8b384be97a4f894c92ecd2aaa
7W05_GMP,44ca34ee62f9364a1b75127a5b1178baabe0483c1794fe12e27d6c0701b85c64
7W06_ITN,e865786fcf863062916979339dc23297985565124556e36480453f62adc2d209
7WCF_ACP,1f5cd9ca26a8ab9e1d28d45fb8cf95bee162631c2ab31f9ce682bd29961295f1
7WDT_NGS,cc202dfcfc3adee68b5eef3ce0cc17f345464624f1f1ebf2757654f4c9d4291a
7WJB_BGC,d16cea10fd02ae72d7edfef3b449f78d9def3cd8eabe6e4baa3200d241d895b0
7WKL_CAQ,012735ee586c92aa574e30679d8986555fb8e78b7e6405fdc5fd018c9f436f1f
7WL4_JFU,78a34a2eef96d44964667dae0d5e99219735ab439570125c0dd794833e1f26b3
7WPW_F15,a538a298e2001b455a30c3a43dcc0cf4409dbd82449c41f8e90daa6aeac4b903
7WQQ_5Z6,7a5969c5e553368a5ef10334e6632e6841e02a16ba6fbdf19d2cdc7f81051f5d
7WUX_6OI,f6bf6c1ec1c62b96ae42a629605c17801be8cf1ab9313ea7f0ae7474b2fcf003
7WUY_76N,ad3b10e58c592e8cd58d0b08c652a8f9af2886ab6146912f398c51b35072a2bf
7WY1_D0L,792212dd484ee6bbff90f4fd2e2cc7bcb5c6728ec17496880a704d5bf668c153
7X5N_5M5,529d42b1d8d1fd20bbce817ba44cee9def073b87c4247bf813418f43b0aa352e
7X9K_8OG,6ef848fd60c133f233c81aa8a3a142765d4d6dbb53e74de65f5345805e7e492f
7XBV_APC,8f325155e20e40e700e62418654ec841e26c6fd56a9b3e5ae0c2c3f27b8476e6
7XFA_D9J,5f6fd15c512309ceacd64bf5509dc8c4d11036c4d033cd90675a688193d2f666
7XG5_PLP,48df3cbd33d7be33dd34e58b00797298b00cf29ed730ed5d462fc220a4dc45a2
7XI7_4RI,ab73686676f73c37a188b28c0242b1bb1b04bdc503bb98054684325c592de0ad
7XJN_NSD,def258a47229566dd19fe8cb368b139dfc42ea4aaf8ba6daf4d082cf250161a2
7XPO_UPG,30fd27e8f6c8b335a936872d420e96223bfc64e467e61d7dae22e6bdc91e86f7
7XQZ_FPF,a44511bf62c571080cc252cdfb4329afae702659976230d5f8335bf5bcdc37f1
7XRL_FWK,43b3fabd615bf59413a79fb8d77bb5957e93a1000845671faa5b001eb146f0a6
7YZU_DO7,3585c585c98fb317b4f78e2c8efa3adbec79261b209e2c5973f2ddc1dd555227
7Z1Q_NIO,5af557e34cee6b72bc7b6ca2cb1b6f7f2459c916503f3a9dc53be5a7432def88
7Z2O_IAJ,a77e6872f5d3cbe3f22ba987a03e59ebbc3b729695d53913fbb7e52a4fe8d642
7Z7F_IF3,ed65f155df6bd92f8a690cd6abc203f014bb01a6b7722911cee6c96b72f10443
7ZCC_OGA,73cf496c5d811fe8f48fb3fdab716869bc13033514914e3a1c9853398d7c25e8
7ZF0_DHR,0950373311fcdedbe6ca1c32f3ef872e6b2d8890d80c8b643a701aa86a8bb555
7ZHP_IQY,b22a919964850eddc15160e53481da4b4eb7d7039339c32c0fc399e90e60bc99
7ZL5_IWE,6347ee3112b8a480da17e2cdd02fe8fa2e411f68c69cd15ec65fa4bed359e6aa
7ZOC_T8E,a9cb1af25a4866b2feed9150d080511a5dfff1e7576fb1fc7970f7223e743700
7ZTL_BCN,05f59d728cdd820762ff2d27cded14982766aeea5261b60db97560c1cdec8f1c
7ZU2_DHT,72219f7085d001f74b00cb70023152740b8b62383cae0a336db96216dc23be5b
7ZXV_45D,2702eabd3de2113048021e1998251591b627c917bd4ab197ff9acaffaffd4e7c
7ZZW_KKW,a16e8b0f5d2faf7180e1c5fa40a264b492fab42e0efb73ed8849b4d4bc074dae
8A1H_DLZ,90d1923f85b1084f2ce5826b705cce974069477c6a3037185b8368d0918cb6a9
8A2D_KXY,b7deb079b77b2339128fe528457f1d58cf56f9ee9f6a215ed1e6bc1c20febda1
8AAU_LH0,79f647c04aac5f10489d424f2d6fa90f5710625fe9f2d748534f9cd2ed6c2870
8AEM_LVF,a2fc54b635ed63c78e7cc56e74fada9ef5dc3d97522617da5f87b08899dc0b82
8AIE_M7L,0e65521015f0c084d7aa421a3d2e05deba8a4d168f3b4212859770e3ccf1dec4
8AP0_PRP,d54a3a4a1f0ee825bd7b50105c401b0c3a6493e70c2f2707d8279cfa3117554c
8AQL_PLG,57d808b04c2ebba9215c838ebcc0799317c48233e0f3e1e85ef8db5bacf001d6
8AUH_L9I,decd26896f88a916ccba8405932a4d6e8a21a820c20a10b28b7a29247c2cc2cd
8AY3_OE3,b9e8781fcc8a021e68b11d9e076b0320ef7e1997bda6a47292e915b85727c71f
8B8H_OJQ,4b2fd35c54b96f8b04cd37b29bda37357cc3496eb323a36ead97c937dc25beb8
8BOM_QU6,1c8e004804e8bf4462aa11d59a98d2d3c2cb6c87496099b82ed62922b6cebaac
8BTI_RFO,f2b70f567a676fc447f0fa4ce602f7ebe6c90b1e50a9d473fd47e1b30c040f7d
8C3N_ADP,d8303e2f922bd5eb029baf42f4bf467703bbbfcbf0a2de999af340af5e01ccce
8C5M_MTA,5a36daaf5ed98d3baf58a0e69b8182c27e1641eb8981f0070e854fb8a48db09c
8CNH_V6U,6b2d9718f3211ca8efe7ae8007d49a8a20735f22688d5ce48e13035d50e05f0d
8CSD_C5P,f8834aa74d661d9c59f5128aa752c5327a1204239de82c20c63fe485534c950f
8D19_GSH,9573212dc8f0ed8c1e4f2dd5115a339d2ba238bb405eee0a1c791a415aebe8b2
8D39_QDB,aa061d95f21a6d6ca7713433c64db3074c1d19258dd68167301ac810cb96e488
8D5D_5DK,a507a17b3b24029a95747f5e17b40ca8f7097d83033af72efca2af9b7b790dae
8DHG_T78,b60667b2ef422808fb147fe20c3c57bfcc92f8af87b56e9746f0a5660d12cad9
8DKO_TFB,2ba8b9a9b65d2b9a203f5d4d0ee8f85ea1b2305fe02db5b665a5bc031f5743d3
8DP2_UMA,d8ab9c3fbe05ff6f41cbf69b8eadbfa2f8ccc6d4636ed08a11fd19aef119be83
8DSC_NCA,66dd3608fdd3a839635b44e230735306d08d181b5a49d2cb33a78619d3543d31
8EAB_VN2,d3963796ff08bfd15aac0715a2f7da0946f85a6612f6165709d7c37b534d3f04
8EX2_Q2Q,a1600cc37e18c2da12bc11afd0f69c6c6d4697c2c956943959f7f082601debb1
8EXL_799,9d9a5b9a9c0934432ce9bf71be3d2e8c1223dff80fbd70fa2a0611694ae9834a
8EYE_X4I,ca586a11225ed9aeaf98bde5bcf4c95e761a755e1cd5a9d98c8875992e990ce7
8F4J_PHO,bc1729eb503f527e40a1a00d19433580667831f8b7160972978bc7b46f921fd9
8F8E_XJI,e3b5d8d8ea50a200f7a93cb0fe5f0fb98f7f0a5152e3e968c4188b733a7fac46
8FAV_4Y5,448c87f36ca347a986764f4a0e1ef3bea133460ef609825dd0dfdb6c2905c2a9
8FLV_ZB9,0bbaa0086aced58138912fc5c4905cfbc7007176fcb9e6c55c04160f78b43829
8FO5_Y4U,e79c4efd14d96477e91469c41b68775034866e32d386edcb9a1e9ed678da808d
8G0V_YHT,7c748c817d54b54f5fdf9295997e7bddff51631578d21dc8578887bf90f5a876
8G6P_API,ce5af05035d116ab4b9b4296b1ef01c236c2a36e021946884542c3409c1ff6a0
8GFD_ZHR,cbc24e51f50590e86f27fcf37e54e5666499220f3b8fbfb6cfb3c5072c286b2f
8HFN_XGC,3a7a880112a5696927bb291c16ca71ab8cf6c85f7e9fa748ab414071d5aebfa9
8HO0_3ZI,b0395ff0c97c65278aba873188f478ebd15fb651628e7dfacac3a68f0111edad
8SLG_G5A,ad96c797101a65e45e4274dbca6462cb41d0f902a810225a5a187abd173e6722
""".strip()
_FROZEN_MATERIALIZATION_RECEIPT_ROWS = tuple(
    line.split(",", 1)
    for line in _FROZEN_MATERIALIZATION_RECEIPT_SHA256S_TEXT.splitlines()
)
if (
    tuple(row[0] for row in _FROZEN_MATERIALIZATION_RECEIPT_ROWS)
    != FROZEN_PUBLIC_REDOCKING_CASE_IDS
    or any(
        _SHA256_RE.fullmatch(row[1]) is None
        for row in _FROZEN_MATERIALIZATION_RECEIPT_ROWS
    )
    or _sha256([row[1] for row in _FROZEN_MATERIALIZATION_RECEIPT_ROWS])
    != PUBLIC_REDOCKING_MATERIALIZATION_RECEIPTS_SHA256
):
    raise RuntimeError("frozen materialization receipt manifest is invalid")
_FROZEN_MATERIALIZATION_RECEIPT_SHA256_BY_CASE = dict(
    _FROZEN_MATERIALIZATION_RECEIPT_ROWS
)


def frozen_public_redocking_materialization_receipt_sha256(case_id: str) -> str:
    """Return the archive-derived four-input receipt identity for one case."""

    try:
        return _FROZEN_MATERIALIZATION_RECEIPT_SHA256_BY_CASE[case_id]
    except KeyError as exc:
        raise PublicRedockingBenchmarkError(
            "materialization receipt requested for a non-frozen case"
        ) from exc


_FROZEN_PROFILE_ROWS_TEXT = """
5SAK_ZRY,18,2,3c6c4d669c5590e8bef81bbf9e201abffe3d8bbf5b0e563d264d42faae2514cb
5SB2_1K2,30,6,aa6d6115933d53e1f19dd5881bf09509f1dea519c8f44fae0a37b8f3d7bf6dcf
5SD5_HWI,29,9,5cb7355e18c0af38af55ab49824e34c8f97540ab0a6866d97dbc45c1dfc59fb3
5SIS_JSM,32,7,507806a7b4cc0d84929fb9570a3228d3abdee59d1443c69cc9893d8c5fe7e0ad
6M2B_EZO,25,5,13dab137d84a0d4dca8b6dfbbd2ee18f8f0194d3dfa8580864d20a688abcb989
6M73_FNR,31,7,f55d4e807d4c945db3ce8b84136e71d8034237d65553be35dd136a5123b32c93
6T88_MWQ,10,3,42791e5be6dd6c60bc8e5a04af5ff1a6c3ef5938140497d72f05996cfdc94f15
6TW5_9M2,31,7,95eaaa7830c9eccd0a86d7631914cd332f89700c22079b48318db146c24514df
6TW7_NZB,29,7,839a116b45f65b56a2e98542c6d4327e8837c2d26f6417da59d66c9446e34a53
6VTA_AKN,40,10,db18d13566c7fcedf8a5bfccf83979f4bf27a1ddd58a8723e8a4c9f1efa050db
6WTN_RXT,23,4,29681b97b5b0f75571d08ac27b622772057be141ddc03625c88400598eb49566
6XBO_5MC,22,4,c32c740287791b1d5c5d16ce021ed685d2bd51c26b879b5e3dcf2aa972c371be
6XCT_478,35,11,70fafc0be9c2af19ede78dbd54ef8f7c94585e6bdb5210563d5f4bee32aa6ef6
6XG5_TOP,21,5,05f68d8011a7f5ae467b960bd7b58200e806b48030705b4eb3fef20ba37d27b4
6XHT_V2V,34,12,b6a4d8367927510d28fb0b0b934011badda3b5f670dc6c741e4e1d9a0ede56ec
6XM9_V55,11,2,2591d42184dec00c9e647866f94c3a1f352e34603d951ace56e78607b0579d06
6YJA_2BA,44,2,d331d143bc65c943df74f007d06961e1d35fd540f135526c1a8be86808fe9900
6YMS_OZH,35,13,9fff9f031ec413c72712e654689e0c6c937bc589f2eb11531418b794ec7365aa
6YQV_8K2,10,1,ec62058786706d4e4f36c1bc3e8ea7f9671a33feffe67812290841ffb4b90a77
6YQW_82I,11,1,aabd5efdbc6035e125481f255c68a4abe9a137ab5415f1b3ed24d3b4a11b8687
6YR2_T1C,42,6,7b3131242fb9bde95e618745a1d2c32779f2ff675fd1e93e1d23b590fa2de41c
6YRV_PJ8,17,14,214622f000e7229458e8d6e5366de375b9ac906c337acd204fd1bf9abb4a97aa
6YSP_PAL,16,6,ccc87192638ee669e9d58a0f330328764cd1013c9e86f54675fe376e4563f07f
6YT6_PKE,31,7,3672745e53749f2651d030e48248644b87895ec43d32480ed672000b0369c21b
6YYO_Q1K,19,2,459ca0a81e7719bdcff4b1c0fb53a286210c2080e13f6144065831225e1079e7
6Z0R_Q4H,9,0,8d4a97c4bb4d038897d92e343742e9f35eeb066a36d411fea6268bef17d49355
6Z14_Q4Z,18,3,c0c8feddb54a72fa629185b0765a2a7198d6c4d31e95e7f6855ab5c39a600b26
6Z1C_7EY,22,5,8b0690e16342a18ec25d6967d44237af6c8a15efced704923316fbb35c914d60
6Z2C_Q5E,26,6,5fe9e31b6455ba4c51364f93ef4a773e060e6d43e8399eebe7059033092b1fb2
6Z4N_Q7B,20,4,63c7d128d190ff2282723ba35c8f4e47d767d0904d084272f8a24802c1f20760
6ZAE_ACV,24,11,0efedf0d975b452783a7729d9e407eefb11d0d8629d75b37b0d9c17b4fd421af
6ZC3_JOR,15,3,f0ca44dbbaaf4ffd180704905200490c2037651192f1c7899fc8f82e2c0992b4
6ZCY_QF8,33,6,e4bc15b8ba0ede78733d713ad9cff42657fadecaa43028053b7f393aa628574f
6ZK5_IMH,19,2,0eba9a2bd932322a0d1775b22efcb924c0a2bb77277bf5250aaf94f2b7c327e7
6ZPB_3D1,18,2,2d9d1d828fc1191b2af712575e124da8ddfe36f3c00e8b253bedf0da8998e92b
7A1P_QW2,13,6,cad155946759072a05d344979b0afcc233581858dc53f7feb6a150b97379c539
7A9E_R4W,6,1,21830bfc77f1ca37221c1197165f829ac19eebe0a171a00d49f1c8a35ecdb297
7A9H_TPP,26,8,029e24297b0e184c678cf475d5287b4bf31f392e0f1d6bbdbbf188563b81cc90
7AFX_R9K,20,2,855edd783a4ba537461612d309b4471163ddab58c4dad7a57934e1a3b1f6c2a1
7AKL_RK5,19,1,1f61e5d29feba38e477fc7215c376b48d724c139342e72959e42b4f71c9b1eea
7AN5_RDH,15,4,78df9a83755ec5424f22619ac8bbb97e9a3318d8672ae78aecb055b4d44ebdcd
7B2C_TP7,21,11,d4212eff4cbbb479931cc6ddf13e811ebc90ea5546dab3fb931826c321fa89f6
7B94_ANP,31,8,7805dcf2efabc5faf453ad13410447cc5578178ebb49123048bda12ecd259fb8
7BCP_GCO,13,5,7f9b2ae7db483ff0fe35e4481747ff5424383455b13b71ff971e08aa7ce23e76
7BJJ_TVW,10,0,c86851c55a713a01b641600d8db3e9dd6c5c5da00016437e5088c39560bc8735
7BKA_4JC,12,2,1550f3cf035351ee48e874dec38888bf16580ab05d5c6cff3f85119034e301eb
7BMI_U4B,13,2,561e593b03f9ec079907268df0b1eda371514e698be49ed750865fd56bae69b7
7BNH_BEZ,9,1,c26c0462ebb0f034405894f90e0f896ce1d751b636af66bf91dcfe64703cdaa6
7BTT_F8R,40,9,0b46689743b40a25378ca6c851b0b49ce8188b81fcf6ebb423e84378320873f8
7C0U_FGO,43,8,868aec9c05f5e81270be2236d54f18a586242e5275b0c9fef1d2864f3482b2c7
7C3U_AZG,11,0,0888156eabf907a07c00e699e96941c68f815aca6a9a13123aaefb7f493c73cb
7C8Q_DSG,9,3,33a4d420b958bf589647895c3b63d28094032edceb9dfe2d1c246d9524ce0669
7CD9_FVR,33,6,9a8ff224b850339d8c6e50cb5a380eaf56df5c0231e5912d7e9442cf00d3a130
7CIJ_G0C,21,8,b46b6ad9d1fd9919f6cfff24a6f58a417c3bb49b6e16b1b76a274e213cf17635
7CL8_TES,21,0,79c97f2b9ee31efda5faedcf7ce18a1865a5f897698149e77835753ac964fd12
7CNQ_G8X,9,1,e9159b0106d100c923840c545d18b5b71c85b888cfbe76b32d5a858c07aa9cab
7CNS_PMV,14,6,c0e388822ea89acd5eda9878a9c27e9e6d299a578d3253fcfea0060924adefcc
7CTM_BDP,13,1,aa7204badad0081b534cf80b554d38f7cd80bd43764a8a9a4499f787db347185
7CUO_PHB,10,1,a988a18779a2dc91c2a3c46d2dc918e891a3a5c582864a575b10e225e738a073
7D5C_GV6,31,8,6d52d0dab606c52604cd87afa48c6949ef6fb70b61d1c9fc4944dc0dd86bf1b3
7D6O_MTE,24,3,62aa029b0d2110d71b32a975e6cc1d0dd7e1ad45a608b05ed8e8d7c27e952374
7DKT_GLF,12,1,8220d2b33172c6df160b8484fd7722c8622213e264691f5c6130c4789bed038f
7DQL_4CL,9,0,60bd6dc1b4d62f896d4d2396e283cb7d33561591537c2a88d581183dff4b955c
7DUA_HJ0,23,3,6913934752e05eff24c6fdb708b268413668e366177cc0114955644600f359e2
7E4L_MDN,9,2,9618183387048701f6d1c0df2196f13cedbf04bde5fce63622c0786441d39b08
7EBG_J0L,14,1,d9af349491ead7b7d3d7e6e55a9d7aee94ef050be9fd651e29badf61e7a621c1
7ECR_SIN,8,3,af6d02a076cdd5a8ea4c1d92dabb876260e60e5b3b3ea96c08966161e5f3ca03
7ED2_A3P,27,6,087dfc0ad70ba529a603f788707c0ee8527498cfbe6d52d1a83e9a46faced537
7ELT_TYM,37,8,a0d6d6d0b1ad72ae351cfddff928821cefd534a4467f0962afc158fc7e42792c
7EPV_FDA,53,13,dc1f0f83007a969e795c029efcfdd65433420ea8e240319f95f3ec202c8e5566
7ES1_UDP,25,6,2860b567d31a95e111e82c36e2ffbf37d1157ae5c427e99aa29cbb316406c9ea
7F51_BA7,44,11,49a5ea24dc2b1bafe360ee5b7d84a8ac0c2065a52202ddb05b8961725c5bb499
7F5D_EUO,21,3,558bf5026c0f7de302d1cff97f8f8e14b55010597e661739443c98781198a8e3
7F8T_FAD,53,13,76da20325530bbf9a926a2e26f9567d3de509301701ea156237923e232329a4f
7FB7_8NF,9,0,0eb0249287ba88ddf66792470d07b058b03cc3cab4f0a05b96a617fcb1af70cd
7FHA_ADX,27,6,69f16151319c3c6aaa9c08d0eea231b99b51403ac5a881103d4d67eb9527c395
7FRX_O88,30,6,a5a1aba39b713153ed7bb6a6dce22d9edb0aa578e73731599fd0f8f42d6e1659
7FT9_4MB,14,3,8d6e7e99671202286d2ea36bfe2c4c30fe1481ec2a6f7bd0126a9eb86ce60b4d
7JG0_GAR,18,5,9e47d10008ab8c676560a800c709875e49bdfdcebd57d5a0fa9a34dcb72ff535
7JHQ_VAJ,18,3,1c3eb41454ba058f3768677b604b9fe84217dcbe2581caa8bd6a35b5d81e73ec
7JMV_4NC,11,1,3d7cd8061f417f337ea84df11992e9449864dae6c66d9efdbff59407d788079c
7JXX_VP7,25,0,69dd7367801b29081eb3baa14126d77e74fd27a9c004cbedd15ee2adfd53e1a5
7JY3_VUD,27,4,c3c0622849d5f5dadc34dfa2839fc6379dfad3ec3f6bc2991489e2b2dcc93a2d
7K0V_VQP,32,5,1356bc231c4ebc98b705977a32b6aca14fb4151dca424429744216fd4051e458
7KB1_WBJ,22,7,4e812a0bcb2a12f967b43ef627a1f485833d78c596b59522672a549bdeb2df46
7KC5_BJZ,37,4,10440d6863475a080280cdd4f35fdde4bdc2d50e2077c7f8ed224cf784abba8b
7KM8_WPD,29,11,17c3ce7eec0ec513ee45777bcd1d72ddc39296a95897dd4ae988df5c9ea1675c
7KRU_ATP,31,8,4aff86008966f60f33b9811bbf6a7d29bc2ad46eb6eea9580b0ae4dc5f52e176
7KZ9_XN7,11,6,ee28c0cec022c276626854069c1cc093f74aaaf57d7c452d304fe618b6252624
7L00_XCJ,27,5,b71a5144a8cd17e677486ca6b53d3bc031956740e2ffd5989382f198a4594d2c
7L03_F9F,22,7,0c66d6579c9fdc68c0dec5738e8dd5ce264177124ed8545324414718a051f0cd
7L5F_XNG,18,12,d39694b2640057e760583e340c94b00c5324e8b3c353ccb18a7e6c92bed22f7a
7L7C_XQ1,21,4,4c7b9be9b579ad1e246fd2d01150f7814c3f5c6f454a5aea093fb690bc49802d
7LCU_XTA,39,8,47b1982193a0da8f991055ae16606a51711687e40d72274434b563aa0a7dff57
7LEV_0JO,21,6,febc96fb1058e7bca70c80877557e2870081d98b404d41431cd556d30b5c1a13
7LJN_GTP,32,8,a9e4e356e2e9178622ed028c9e729233f0570ec404a83744c9be038ff1e8cc8c
7LMO_NYO,37,7,028e230f45c234e2841e00d9513df2a6b19942789d37065a5162ac83eec013c3
7LOE_Y84,11,0,c5824885d2611772645dd68ab53c7f78b3ec3654e56ce7e0ca278a88e9455e80
7LOU_IFM,10,1,851478979442ddb6e0bb691c6998441f17eb9f200ea4675f60b53dbc9eb22ead
7LT0_ONJ,27,3,9bcf15780d4fe1dc1c69fe93f42a99fb942ee0fbc709acbd4bf65b154032137e
7LZD_YHY,29,4,07d89fbad20fef05a103022640060e5251d1ba512ab213a52a20bb7a0ecc4bb5
7M31_TDR,9,0,44220515a92d4e0164eaf4904745b9235a30889afc41d8fa16e369a67c2e0854
7M3H_YPV,24,7,46c25ade7405181ed93e512615710b0ef86737f8a8a6ebd485cb06b9c02fd654
7M6K_YRJ,33,8,b0f46b70083bd0142810b3af1a96bd9838e85958aba377f8abfe9a5690220304
7MFP_Z7P,50,13,9404b24ba8917456f445cbaff0d442fec98cbfe4164ef64e2fefeb1d95908f8c
7MGT_ZD4,28,6,d9fc115aa8c07ee28fdfd1f81ce606fe4fe63f91192f6e590792b4f6f2b591e6
7MGY_ZD1,23,4,c391243fda00f2cb3a6ddbb41d6e04477cf4a2788d4ef0b8e5758c0d93df0251
7MMH_ZJY,57,9,a10a95dc3d1139ac508766de1dea527db15f9efef680d66e805ea0d6254aa99e
7MOI_HPS,11,2,d9e8155e65e3f53c5bf310cc0224a97743f1491b079e84c0661df407aefbe79a
7MSR_DCA,47,17,68563d8caa432ce86dcce66d4e5ebcd85eb71f25b642329a73aa13de690136e7
7MWN_WI5,32,4,4feb7036096c1b8884a78ecab773691d13d66add9eb96fffb7de61880d431dfd
7MWU_ZPM,7,1,dd2a24f24652154bf2bb7d34d60fcb2a2d62a16adf91ba4208757729eda41e74
7MY1_IPE,14,6,d9fe0d4bd6c6ef71f5db83b794d6ea4d8b1c88ac4a7b94c6eb7630368d8c2497
7MYU_ZR7,35,5,e838384903b8909d48e660914bd63dadacc60f59ef9d3d7d0dd6bf033a889055
7N03_ZRP,28,9,6d803db7fa7ea6dd5fa0abe286c38f83daf25e01c2f80b46b237bd7c5f2aa0ab
7N4N_0BK,32,6,ed981f35ca14ebafe8d81b32bddb5c5e34f0d95b53a2074431300f13248fa286
7N4W_P4V,26,4,39e6e71f5640d3233c9fc893708b691a837c0e693e6fd1dfd4e3cd3d9415787a
7N6F_0I1,26,3,8147ee54085ccd86efd11973d140b7a5d560a2867e5c21334dcfbd0caf839d1a
7N7B_T3F,35,8,d144224960f3fd208d327c18726a2a75a4bdb99fa38136d43e02674c0a3d33a1
7N7H_CTP,29,8,b011c4fc08a42f5419fa648b83f6dd58c923c18cc11d3261ad0acdc4ce629ae5
7NF0_BYN,37,7,f6600980bf2a5ba6644f76740953cb5e84cd1a9f208766a580a036cfc2391146
7NF3_4LU,36,7,95179a186420df569bd486eceecb57c38d95248a5320b52f3805de3c6a4d5835
7NFB_GEN,20,1,d43cbff5d291e673120e34e54fffc1f856076dd2bf3cba0a7276fafab125ae93
7NGW_UAW,17,1,0e10b06260ac067d4692888a37a5d4526eeb9f0575c9cc2553077262c3e5f6a9
7NLV_UJE,21,6,c8f2e0b4c2cd16a638d2eb9124aa4f997dcf84956dc76b63f31af0197ccecbdf
7NP6_UK8,32,6,ffb3c92f64135fdc422f2d7692106619df9705b27ac66fb00447c3a04977c2c6
7NPL_UKZ,27,6,4b7f6cac1fcbd641f6b768483acb18d47b125a1097788f8da4d5f64971041d4d
7NR8_UOE,45,9,ab6218b72f9a95c49aca78e25ccb57b7eca94ccb305d08a464bbace3edc5ab5f
7NSW_HC4,12,2,7b7e875bb9550fd520606c7619912a81047fda0fb62a304ee79d8b4ceb6b3f3f
7NU0_DCL,8,3,36d445440b25c6bc66e9637421b7440c5e249cf5e456d4f6c666d2af70d5b261
7NUT_GLP,16,3,1a4d7105f6b8cf6cbe55a31c6f1ae5cfa5bf4dc02356ce209cf52cb6a8da8b67
7NXO_UU8,34,5,7277e06f876b2dc4d5d07429c009b66ceaeee64b86101f996208af381c54bf41
7O0N_CDP,25,6,105797adb7164c8a8dd7e61930699ed004caf0a2e6e83395b696b4933460f2ff
7O1T_5X8,25,6,70c39c842961296eb3f78b32aea7ee8d22bb20f9746c685cb9a16bfa6b2a64e9
7ODY_DGI,27,6,685650aceeff5be7e9d22e064eaaf783b4de24f92a277c3f601191e4d74adb4a
7OFF_VCB,27,4,67b4e78c94e95601cac87448f7f10151abe01ac994062d3dbcdc1dbdc34b9509
7OFK_VCH,35,4,1ced7e58b0b5ac1a6182e59c09d26005bf8813284aa04b844cefbd91931f8889
7OLI_8HG,20,2,762f94a576f74f669c0c971a4792aba27c2aa3edc0bcd3036b1f55eb266f6912
7OMX_CNA,44,11,7b74586e27fecf4a4b6fc0bc3784955bf9a831b5c79164be0f960623d5d1f06e
7OP9_06K,11,0,fbfc8ea1798b3401eb4dcef98289063b756f425074f191df164c5508eceef6e5
7OPG_06N,19,4,0b9f0dcefc9cf087314dedb1297d3eb8e14d6fe57274f966d74ef47a92e006fb
7OSO_0V1,7,3,eb7578770630df26de67a17498f950b3cdf907bc9422acc509b1328c6e779e44
7OZ9_NGK,19,4,2fe3bc82978eefaca77970df09fbb8c63c97c37a78d4edc54a47338aa3937cd5
7OZC_G6S,16,3,0da3300b4beee39503b614b9c920dbea9864b9e8f9314354254ad314e59b87fb
7P1F_KFN,17,4,2c8d712b32f26db55747053b3632b7f150d73fbf82b2543957aba508b2e9e139
7P1M_4IU,24,5,fff9adc3320e2f0ba338ce0e91ab6d0a3857919d8ea090c932890ebe6ded275b
7P2I_MFU,12,1,bee235ed56b9f71a70ae4b3ad0fa40e5a5cf958aeb99bd46c71d025569661019
7P4C_5OV,16,1,fe126157b8b630cb587f54444b1fe1629c234da13a5fe439fbafa506a11972c6
7P5T_5YG,23,6,9be1ac57c4771ac95772b5a664481df3fe0cf49fd931ef6cd896f53cad3b9d14
7PGX_FMN,31,7,fa575facd46f929bbdba981fb74204f4b0fce1fcbf61d7b2c5aae3a7b1f100bb
7PIH_7QW,24,3,895f30d636a45e3ec5b58c2fd0798292b9e6cbc5a92a81e48d985db8cd7e4561
7PJQ_OWH,10,1,e96e80b2acc3d48ba590c65ae32d3be834aa9bbc702e0e7d7324cb3c7eb541af
7PK0_BYC,56,20,8224b2bb076b0ad6e2873b8dfc8ed01f3fae722ce65076494221524727d02786
7PL1_SFG,27,7,8f947b67d8924ee069a7c3d64193f4ae41d08a867e82c24735b9062f744a5dd8
7POM_7VZ,22,4,9fb7230d290443c7ea2870ac816b655acc3ffedd435bf6d5c55c5943cad2e0da
7PRI_7TI,20,3,41708ed29737c12690f88eb1076ff8df309095939f21837c746d5a351da16e75
7PRM_81I,32,4,a828d5bbbf9dd62b20b574e85a97dc5443a51144dca9c5d1a1a8b3d773180ae3
7PT3_3KK,54,20,fc97b8e2dffc1d02e13f01aeda679ebf72b17c0a9d2a63550f4c4f042d11cde1
7PUV_84Z,24,4,63d5d560cd70fa3df205ac392119ba413e897065194e7813449c53a6d24a636e
7Q25_8J9,33,14,cba4c840592296c0f2e744e2f450800e5632280684b90f3d17af7743a5f436ac
7Q27_8KC,35,14,0dfbfa9b942d2f3b072d73b0e312b5bea8d48d5ba4275e6c6f4e223c8d70bf9c
7Q2B_M6H,12,2,bfd5fa78e2802f5221f83aa482852854b0c80a2f4962fa03e866c1f0a481d316
7Q5I_I0F,27,5,1bac1ca0d558d4b7c8367e062a82d1f15fb302bf5173977cedea03b7e444b429
7QE4_NGA,15,2,e3490ccd517a489e89c1c57c68d9146161056d519eb15436781c5ffaf852f7ee
7QF4_RBF,27,5,55fd36b7da5cee5225c1bc4af8b3b9dced92c56e069d70bfb041c9e47d45d401
7QFM_AY3,20,2,9cbb86ee59c89a697df4b17dffc0d69cd956cd4ddc95474d0a9853404cd4c50e
7QGP_DJ8,35,3,b48554880d33e8319b9939c905a09997b8e12cb256daa1ae39e1d4b5b003d079
7QHG_T3B,42,12,5bc22ab53e8d9fbcb0281410476e6b23f63867264fec424b00227fd4220ae815
7QHL_D5P,30,8,647df8cc770d226cbe30d5ba43e8d173aeb2e28cbf091ab1f4e3f100c4864739
7QPP_VDX,30,6,4d98a8aa1b86e5263b219d4908c68cf1e633add4b40646510ef9a4e159410d0f
7QTA_URI,17,2,a7246e4c7f1b49dc3d17fe550426e5c17c9b564477cddc26d3127e89fd299790
7R3D_APR,36,9,e5789f7fe649a8922fe74e0b03392d8405a5746e93d664c64a3efd4b6086aa1e
7R59_I5F,13,0,2fb6a8d9b436384d139363e2ddc2f8dca14df507ea85ecaa4f7e3f9c16af3fe0
7R6J_2I7,33,7,39e31482bc9ea6a69cfe5487d49b010f3d9566466282a5397655b730ed37f20e
7R7R_AWJ,33,7,616cea7ac137705af9a7aaa079c5af41d113e54b14178c4ed2d26beea94a0dfa
7R9N_F97,31,5,9c1b84571a58187c29deb0bbc36830a320916b804cad197353a8dd818ad1273b
7RC3_SAH,26,7,6d3f666e0a4395d5f8970edf111c5d8f6136a8749cad8c0c58b95601fa618a8d
7RH3_59O,34,7,6c843895a59cce96120228af6bb44923946260cdc4c7c46ab35f259634fb347c
7RKW_5TV,25,5,e3fd87adc5c5180b37dc1949bcfee035737974e680de3ddcc16f39ec7670efeb
7RNI_60I,31,4,c29d1fb7eb67e68bccfb68303bb964d4e3215e559894e078f1ee4f25ab795baf
7ROR_69X,35,8,42a5b2552e83343a6c3a5ab470fb5b56a9fee4419661c7e44b1088b3b197167b
7ROU_66I,39,10,13a7d47bbbde6c31b72222e75b1db369beecbda8e0e97ed9dcf2a7eb50229cfe
7RSV_7IQ,20,1,7ccb1c8941f94eef4828608a03812ef27da9f3a8e1cbebc321829137bdfc845d
7RWS_4UR,45,2,dbf9521fe37244cb1e6bcf777b8916a7bdeda2c67053f1d7e5eea4796487a188
7RZL_NPO,10,1,47f245687788d1aca4e5d103dd718b47153dc3f94e35dd0229e6d0edb3fa1a1a
7SCW_GSP,32,8,dde21881746fa4886e5d92af48a9eec5f3732703ad2bc15df1b940b7d7f51856
7SDD_4IP,28,8,ef8cc6b588e61598c20e9c91e26e29e953c8e7207d2cb7b48169e7cdce57eac0
7SFO_98L,25,4,126f41f4644c865c0729a639b8d0c8d47de0f964eb15d5f5e969c05f1c3bbc62
7SIU_9ID,31,6,e18af15383031e5fdedd2725b24b9afb169ebbc69218d8d1bd02acb3d7a957ee
7SUC_COM,7,2,386dbf9b424ddbf36715f1cf20e16259e92a2cbf3fe4d7c99bfa4fbfcd1c83b5
7SZA_DUI,20,1,4957cc16ff15c7c649637feb15a576597b082101991d3b158c679562384b670f
7T0D_FPP,24,11,cf29bfb2f3f0ee40d30fc3e0b62f396b3e0676bbdbd524149dd87789abe53167
7T1D_E7K,34,5,4f87504ba6c28fd2db0bd419b120307b978f531e6088d6b1315770801446c064
7T3E_SLB,21,5,954b129b13c59add09ccae07fe4b3a86fa6bd1ccf3aaa2026614708d467eea2d
7TB0_UD1,39,10,460c6c088643225fbaaf1f3a1d256ad8101abd58fcde4e47f40726c7d89638da
7TBU_S3P,16,3,4d500f0b2d2c14f76d75b445682ff968f1a0b59436e6adba965a4c1eb26764ba
7TE8_P0T,23,6,58f265ab0bab1613cdd2aa844f4cad9d4dd9fe7fe8bc0fea48542e6d9fb6a84a
7TH4_FFO,34,10,7f919f0ce925cc97f2f8c708a4c2c4cee14e5104213dfffde69c5a8478d1903a
7THI_PGA,9,3,63f20d83cafa119444d7b48933564ca1e1bb5407fbd238a008d3b39a17bbf483
7TM6_GPJ,10,4,bcd7e15210da5a64f3fafba73e1f82026189c9ece2597d99ee1caf0ca51dd006
7TOM_5AD,18,1,21573b17204143b73728641af5be0b2da3104271258e4abf4e94f717050d8502
7TS6_KMI,17,3,a0993180c5fa3de9cd7fd39a4f3baae3b56f8ed2b752b4afbd90e55e320f5f8c
7TSF_H4B,17,2,0ba1654a7d49a38edf989aabf66d62a666a013e902af2f9088eae7b4c3a4530b
7TUO_KL9,30,5,9371a4a8d9fce331a1556b35cea7deeb4934f15ae6b8cea0cdafc93a96b3f72d
7TXK_LW8,15,4,b61bf5dd12f7e8bdad120041d06e72c6b0b1e261d9b116f08cb1df37d29772d0
7TYP_KUR,37,5,745323842ddeed8f2633b39d8b1be5bf23aeeefe7ba1c6b8c46c9e7dd549bbe4
7U0U_FK5,57,7,e127b2393c8f20a98673a9013c2786cc8656baf43e8f961ffe35a89a6e3aaa44
7U3J_L6U,38,14,7e59abef870bfbed5f960f2f5eab92a366a0fcd26430130c7a512a4fa5da1d5e
7UAS_MBU,40,7,f23decbc334ee4d49a19a11cb8edb1ecfd62d9f823df816b5f9a2b9413a557bd
7UAW_MF6,35,1,900572ff36858112067c80ffad0db2e5db96aeb1edaf370d0d6e291f72eea277
7UJ5_DGL,10,4,168add2da59c531c9963ce241dae79104333d09031c12653f64387d369b67a22
7UJF_R3V,32,6,0c0f7df3d39a1d0a43c6b30629a63b8d1a9327699f6f5339709d3fdaa0ba6d79
7ULC_56B,33,7,55b579a1432c97ac510999a655d6708d6bb09802fc4a6fad70899e637ccf99c8
7UMW_NAD,44,11,f33b65bdbde764c6e2532cb2662e50b5039160926005565cfa8743f064a0085c
7UQ3_O2U,12,2,1e4c5d60b8c29b9a6a42168227348420b4fa8a09b30f9258b1586c3ebd2d255e
7UTW_NAI,44,11,76ef9e287852c16f04d9e40520f82b2422a0fae563a4e54764b2f7c5d4105883
7UXS_OJC,35,1,c513c99cdc7d85347615e62a2272be39839f5989f6647c74534676350a8f838b
7UY4_SMI,24,2,80d2fab24b89770d96ecfef95913a6fc9f86f2fb7f761c3255ba00400687dcd3
7UYB_OK0,31,4,897b6b81f84f0d24be0f17cb5007ab256caeac851b3dd0fc11191ef76fdf3112
7V3N_AKG,10,4,867d95d23671765bee4a331bff0521f0be1c320afa196b6fbfb01d2eea9dd5ce
7V3S_5I9,38,6,db5ca7e9d98a6d1fe77178625fcb9142536d2b028a43e8982db996c644a028d5
7V43_C4O,8,0,b7ddd0a9bc6d4cd144dcb007648672b3bfdc1851947570046a383ffdb2e8db71
7VB8_STL,17,2,43e58f46440519bcd495821a21fdd2584fc9d6e474baea679f500a88422b6de6
7VC5_9SF,22,4,89195bf4b42662e590c7e255f800967a080352ef73debd421e69032ef2515c12
7VKZ_NOJ,11,1,136e2c12beb480e6e18f1934f5eb246dafe28b635b168175e9ef6f1f6b1c63fa
7VQ9_ISY,14,6,0cdca4a3a6c220e25996fec72d502ae6d0e0595c2c1f301bd8c8b9b61683f5b7
7VWF_K55,33,11,d0706dcf0fd2f86bb7819799add7d86a19409824f842b089e981cf044d82cc2a
7W05_GMP,20,2,07580331f3a215d79dcc277597bee4a556c8c10ca142c81b17c1fb795a4a3efc
7W06_ITN,9,3,20985e097897aefebec49a8276d48bd477d47b74e10d3b4e83cc9c80b9d5cbd2
7WCF_ACP,31,8,f8f841893c3c286b08ce0d13457668d4d9ac74e12248ce182ad92508d2dec68f
7WDT_NGS,19,4,1713bdf34ae768e8ca5b47ec49bce18d7fe2f58908e840a401bfee5fa617c398
7WJB_BGC,12,1,286c28e7239ff8ede11d3536b79d19d26063a3074a6f8cd3a0fa7a461e417da3
7WKL_CAQ,8,0,b815bb1aa6acfb3c58fa84975d79f40f26fb584dc30c3ce7c3401a93eed3d4b3
7WL4_JFU,34,5,79eeb92b3ff3dbd3f17b36177daa2c0915c1b619cd082f0b13e03623143c6e5e
7WPW_F15,17,13,1295e6464cc48ca1011468884c93560b33f5bb5137a3d9cb81ce4017dd6fdab6
7WQQ_5Z6,27,4,47087804db29902e76403397ee3c4a75aae7924806731fdffa8264ae41013f03
7WUX_6OI,17,8,15c424130160bf658b87dd686ba9fbdab7c8939c0f9e16e0f69020741f804131
7WUY_76N,30,3,870cc408bd18a41eecc958cb5aa9c9c0bf7d6526c886d4946d1be94ba54c271f
7WY1_D0L,26,11,1be6454da34727dd3c079f98333f2d3563659e402e41424ffd50c6851dee81e3
7X5N_5M5,30,4,6cde999a681777542b3e3da6da4fe255f7879ace81fd0a87b427f85e3f320158
7X9K_8OG,24,4,96e87c7e08337de0ab716251f1a94ae147765fa63948d372a4733031cece7072
7XBV_APC,31,8,49e180922e4f1f851eb1be4aeb51ec8d802d140862b64ce11c147f7421fa154b
7XFA_D9J,41,5,5a39de22be12cff7f22a979d6535824a13d890674210a8a12b0706b10a52d5e2
7XG5_PLP,16,4,daa4d885ef15fee225fd22f198ae453b369b0436863d942de04fcf33358bc4fa
7XI7_4RI,20,6,098fd1e1db9d1016b20ed219efc0406b82aca6c5ef3b0d9097ac4a9ec6382a71
7XJN_NSD,9,6,f0829ec793f2caaf1fa2b4cf192eb840994736eaed9217e01665975bde90d88d
7XPO_UPG,36,9,889be8cc5dfb8daf78e7265e85424cc52de1c2211200ef6da0584a758e62519d
7XQZ_FPF,25,11,d8f2f68f87eda5cd09c15fbac14db5f832e196460a8e6e42d880bf85b875e050
7XRL_FWK,19,2,93af486078dd83244b2a4364e78a5fbfa8e45bcc2c0635d77c8e476049963263
7YZU_DO7,16,3,ee581f6cee60590a2a6c9b5af2faeaf3ff4b1805e839daaba1c612976d09d979
7Z1Q_NIO,9,1,81cb41c70c15910ad687e5f4548c07af43f8594938a20f9928cbcff8a61e275d
7Z2O_IAJ,14,1,83570a1205b4ac31c8610cccf6d9ae6095a4c962ca4bef34f3665ce194cdb947
7Z7F_IF3,14,2,bd856284bb8ae51ac66647085f7bc459dcea28378cfa8b05f754331d74b015c9
7ZCC_OGA,10,2,31e5b1c1155bef4a4213a9d71b93ca2adab2700dfe936054d079bad264918145
7ZF0_DHR,11,1,70cdc8732a7225e1d72632bdd35cfbe2ed3956fe4d55ca0eb1ea62de0c5fbe4e
7ZHP_IQY,27,2,f31f83fef021c2b71fcd4e9a433c0c83bd7f10f053263e5b0a033751356063a8
7ZL5_IWE,23,5,6667be5f636077ff4726befb986329a8bda1755a97041615eafbb2e807485c1c
7ZOC_T8E,15,3,65d460029b4a89ffd2370f8e1ae4e95dc2ccafbec1bfce69d88f4fed7aeaaf9c
7ZTL_BCN,11,6,138c3ec80ed0a74318a350eac7db3aa84fd52ccc443d641a8985e8cccf00487e
7ZU2_DHT,21,0,39d5a444e9aec6608268c2829e5179d4b3040166451251fb070651dec58dd201
7ZXV_45D,42,10,604899b598d398abaf23fa18e2bf41a6caee33ef48b03d2de38eb34ac659aeb9
7ZZW_KKW,29,3,722201357c453ca3989e27c1c69d17d7ad5d3b838898a9a99a38a5a2742fb57a
8A1H_DLZ,23,5,8da9ffd3e0c1ea52d12cbf603fa9823a7bdb6eb5aac3e9dc9554ed5d8760002d
8A2D_KXY,49,8,d5ae7f117309d0f1916fd1d8f2f080f55ad1518b9b026c8d4718b8dea4c02e6e
8AAU_LH0,27,5,c6bf8b4683b8c3827b47246f2d3e20c73346e35737e5393c663978d39a2c616a
8AEM_LVF,13,1,293d0c46d86741ad66ab224f18f8a5d5132b89e4f630fd924c7683d219736b27
8AIE_M7L,23,8,7554428cb1d5ac712192424d24e6d6e0e561d3b87314d612f8200f4eb034366f
8AP0_PRP,22,7,e70864d0de5a0d630d9368eaf52bf84f2bcb1dcf2e2f96c8d4f4dbb54a9f4622
8AQL_PLG,20,7,f34b8b0d699c0b862ef401b2de872e51403567b9573e3e73d88be7e96c784c84
8AUH_L9I,11,3,9cff384412755578158c1a2b7b71821b71e00ed40e2c81adf371ceee3210b892
8AY3_OE3,25,5,6b2699354a18055e80a0835886e7dd71371d7f3aa2e30eac2f764aaa5ecb5624
8B8H_OJQ,22,6,8b9f39669e859f1a7e549c1e4442f00f720a1d9c3cb6dc410d3e12ba06c047a6
8BOM_QU6,35,6,88eb8b2f7712baeef413b8cfc3eddfb028bb1c23e578b54b1eb05ef4ada4a61e
8BTI_RFO,15,2,6f59e62d958f6c54f59a0c1b08fd5e3c24d1b0a9753584176461ec515584e0e4
8C3N_ADP,27,6,458c648fed0c5e2a912d334394563d86f066dbf2655f1f75dcc0d9eb105fa98b
8C5M_MTA,20,3,b929568432030c2efc54b04be0e75af2779820467ba024ab1f492ee388c95451
8CNH_V6U,25,4,18dba2583c207eac129dc05ba3ed7186497a760760c31ab6ea87d9e004915575
8CSD_C5P,21,4,0d1662a3175091aafcc765abb425fe550a2fa9181aa05c7e43f23d60324e1e96
8D19_GSH,20,9,0bfcf0225ec4a49c30d8f02ba6109ec185aace8f2ab46a2dd0dfb5bc96e3bf18
8D39_QDB,17,3,b47b6efbff6faab5512323389eb9c1c45a8739c125655b481a88ba4be7e7b7ed
8D5D_5DK,27,10,1ac480a62ac78445deb7f31132f6cddf4d1bf2024a2be5f5441913bf6f9e1589
8DHG_T78,35,7,e15c7efd56ed3af0827d299472839f85454e69e64abd8f99870a6a5896dcc8fc
8DKO_TFB,8,1,bc2de0ee19380cd9a0e91050515090ed23dfee03a8b5b65f8cf8874b8b6d5b1d
8DP2_UMA,49,15,06413579021329e21d0e0c434592b335a39b2b7ad73f05a6e8902eb995457dca
8DSC_NCA,9,1,13355f3faffa0ed3b01249828431f1b50148e1068e63f0f9faa48fd2b6801d59
8EAB_VN2,49,7,12affd46c7c320a118d587745dd0a087dbca6c6038cdaf9ed3290f2819f85293
8EX2_Q2Q,26,2,5cf928880a5cd304e0f48f1a244d8b109f5587bc883393748df7fd564b7163c5
8EXL_799,34,5,b38cb09928eaf48bb32b48e95a352f477921ce5f58c316c56a9cb9d4d9b287ec
8EYE_X4I,33,7,367a13419984387d5f01a4c5ba2fa2e7fc670622ac70bedf17490c0e803befc1
8F4J_PHO,64,20,fea187ff5efb5c129798ec4a971fab08a01443697a973845359bdc0d7dacfa52
8F8E_XJI,29,6,a8973a523022f778653b6ceb5a07c9cd72b222f76c4ff9c523a07bbfa7e2e1d0
8FAV_4Y5,33,3,8adedffaf4214d1c39db654d36b723ef6de2d54ede1bcb9dcf9ef89a2489a74c
8FLV_ZB9,29,5,410a3dcb8f7016388ea9b0850b9ab892944470d6ed78146699a34dcc91c5a03c
8FO5_Y4U,17,3,c055fed38d1650a41946aba131e0ac4e57a9aacd90e40258f941619e78f93ac0
8G0V_YHT,26,6,a2112406526b78b92512505c36aa28923e2d93d0bcbc14042429202ce6bb9924
8G6P_API,13,6,96d23c216faecdb0bffae5f2c628dd6dbd04bc113d91f7ffcefd825882914cb9
8GFD_ZHR,26,6,bbc986cc935022fcde5ddae04681963fc77d3810cdc6b10655e2f781d1476519
8HFN_XGC,24,6,a853e1913bf9c446334e3631ca7f890dec044b3d134cd0650bfb96ea2a056ca3
8HO0_3ZI,22,2,b9a99a4e6ce5ad831a755b704309c1d02476ae0034378b040365f174fa1c58b5
8SLG_G5A,27,6,ec2015f986a27af3d8a6e5b47f4693def675b0fdb0d5998e2331b897e475bb66
""".strip()
_FROZEN_RING_COUNTS_TEXT = (
    "353433144342322172114004312333015330023310302111562051410113311402035625"
    "361331121443152304103513521441234327136105334432443234361014233433523011"
    "131233414321532232213354532434453334444713144030613123003225164365054515"
    "534061231023031115020524335120303113201431042528321110325233320213131545"
    "363442303243"
)
if len(_FROZEN_RING_COUNTS_TEXT) != PUBLIC_REDOCKING_COHORT_COUNT:
    raise RuntimeError("frozen ring profile count is invalid")
_FROZEN_RING_COUNT_BY_CASE = dict(
    zip(
        FROZEN_PUBLIC_REDOCKING_CASE_IDS,
        (int(value) for value in _FROZEN_RING_COUNTS_TEXT),
        strict=True,
    )
)
if (
    hashlib.sha256(
        (
            "\n".join(
                f"{case_id},{_FROZEN_RING_COUNT_BY_CASE[case_id]}"
                for case_id in FROZEN_PUBLIC_REDOCKING_CASE_IDS
            )
            + "\n"
        ).encode("ascii")
    ).hexdigest()
    != PUBLIC_REDOCKING_RING_PROFILES_SHA256
):
    raise RuntimeError("frozen ring profiles are invalid")


@dataclass(frozen=True, slots=True)
class FrozenPublicRedockingCohort:
    """Exact 300-case subset selected before any benchmark result exists."""

    case_ids: tuple[str, ...] = FROZEN_PUBLIC_REDOCKING_CASE_IDS
    schema_id: str = PUBLIC_REDOCKING_COHORT_SCHEMA_ID
    cohort_id: str = PUBLIC_REDOCKING_COHORT_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REDOCKING_COHORT_SCHEMA_ID:
            raise PublicRedockingBenchmarkError("unsupported redocking cohort schema")
        if self.cohort_id != PUBLIC_REDOCKING_COHORT_ID:
            raise PublicRedockingBenchmarkError("unsupported redocking cohort ID")
        case_ids = tuple(self.case_ids)
        if (
            len(case_ids) != PUBLIC_REDOCKING_COHORT_COUNT
            or case_ids != tuple(sorted(case_ids))
            or len(set(case_ids)) != len(case_ids)
            or any(_CASE_ID_RE.fullmatch(case_id) is None for case_id in case_ids)
        ):
            raise PublicRedockingBenchmarkError(
                "redocking cohort must contain exactly 300 unique sorted case IDs"
            )
        selected_bytes = ("\n".join(case_ids) + "\n").encode("ascii")
        if hashlib.sha256(selected_bytes).hexdigest() != (
            PUBLIC_REDOCKING_SELECTED_IDS_SHA256
        ):
            raise PublicRedockingBenchmarkError("frozen redocking case IDs drifted")
        if (
            len(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS) != 2
            or PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS != case_ids
            or len(PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS) != 298
            or set(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS)
            & set(PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS)
            or tuple(
                sorted(
                    (
                        *PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
                        *PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS,
                    )
                )
            )
            != case_ids
        ):
            raise PublicRedockingBenchmarkError(
                "redocking historical smoke and primary partitions drifted"
            )
        object.__setattr__(self, "case_ids", case_ids)

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._projection())

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "cohort_id": self.cohort_id,
            "case_count": len(self.case_ids),
            "case_ids": list(self.case_ids),
            "source": {
                "zenodo_record_id": PUBLIC_REDOCKING_SOURCE_RECORD_ID,
                "record_url": PUBLIC_REDOCKING_SOURCE_URL,
                "license": PUBLIC_REDOCKING_SOURCE_LICENSE,
                "archive_name": PUBLIC_REDOCKING_ARCHIVE_NAME,
                "archive_size_bytes": PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES,
                "archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
                "source_ids_url": PUBLIC_REDOCKING_SOURCE_IDS_URL,
                "source_ids_size_bytes": PUBLIC_REDOCKING_SOURCE_IDS_SIZE_BYTES,
                "source_ids_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
                "source_case_count": PUBLIC_REDOCKING_SOURCE_COUNT,
            },
            "selection": {
                "algorithm": "lowest_sha256_then_case_id",
                "salt": PUBLIC_REDOCKING_SELECTION_SALT,
                "selected_count": PUBLIC_REDOCKING_COHORT_COUNT,
                "selected_ids_sha256": PUBLIC_REDOCKING_SELECTED_IDS_SHA256,
                "selected_before_results": True,
            },
            "contamination_registry": {
                "schema_id": PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SCHEMA_ID,
                "registry_sha256": PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SHA256,
                "historical_report_sha256": PUBLIC_REDOCKING_HISTORICAL_REPORT_SHA256,
                "old_298_holdout_claim_invalidated": True,
                "reclassification_was_result_blind": True,
            },
            "case_seed_policy": {
                "derivation": "base_plus_frozen_case_index",
                "base_seed": PUBLIC_REDOCKING_CASE_SEED_BASE,
                "case_seeds_sha256": _sha256(
                    [
                        {
                            "case_id": case_id,
                            "seed": frozen_public_redocking_case_seed(case_id),
                        }
                        for case_id in self.case_ids
                    ]
                ),
                "shared_across_engines": True,
            },
            "analysis_partitions": {
                "engineering_smoke": {
                    "case_count": len(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS),
                    "case_ids": list(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS),
                    "observed_before_primary_holdout": True,
                    "claim_role": "integration_and_engineering_smoke_only",
                },
                "primary_blind_holdout": {
                    "case_count": len(PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS),
                    "case_ids": list(PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS),
                    "historical_designation_invalidated": True,
                    "claim_role": "historical_nonclaimable_partition",
                },
                "contaminated_development": {
                    "case_count": len(
                        PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS
                    ),
                    "case_ids": list(
                        PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS
                    ),
                    "observed_before_stage0_numeric_freeze": True,
                    "contains_all_300_cases": True,
                    "claim_role": "development_and_threshold_derivation_only",
                },
                "supplementary_descriptive": {
                    "case_count": len(self.case_ids),
                    "case_ids": list(self.case_ids),
                    "includes_observed_smoke_cases": True,
                    "claim_role": "supplementary_descriptive_only",
                },
            },
            "profiles": {
                "method_id": PUBLIC_REDOCKING_PROFILE_METHOD_ID,
                "profiles_sha256": PUBLIC_REDOCKING_PROFILES_SHA256,
                "ring_method_id": PUBLIC_REDOCKING_RING_PROFILE_METHOD_ID,
                "ring_profiles_sha256": PUBLIC_REDOCKING_RING_PROFILES_SHA256,
                "heavy_atom_rotor_and_ring_subgroups_frozen_before_results": True,
            },
            "materializations": {
                "schema_id": PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID,
                "artifact_filenames": [
                    filename for _, filename in _CASE_ARTIFACT_ROLES
                ],
                "receipt_sha256s_sha256": (
                    PUBLIC_REDOCKING_MATERIALIZATION_RECEIPTS_SHA256
                ),
                "materializations_sha256": (PUBLIC_REDOCKING_MATERIALIZATIONS_SHA256),
                "derived_from_hash_verified_archive": True,
            },
            "raw_structure_data_bundled": False,
            "benchmark_executed": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


def frozen_public_redocking_cohort() -> FrozenPublicRedockingCohort:
    return FrozenPublicRedockingCohort()


def verify_public_redocking_source_identifiers(source: bytes) -> tuple[str, ...]:
    """Verify the published 308-ID document and reproduce the frozen selection."""

    if not isinstance(source, bytes):
        raise TypeError("source identifier document must be bytes")
    if len(source) != PUBLIC_REDOCKING_SOURCE_IDS_SIZE_BYTES:
        raise PublicRedockingBenchmarkError("source identifier document size mismatch")
    if hashlib.sha256(source).hexdigest() != PUBLIC_REDOCKING_SOURCE_IDS_SHA256:
        raise PublicRedockingBenchmarkError("source identifier document hash mismatch")
    try:
        text = source.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PublicRedockingBenchmarkError(
            "source identifier document must be ASCII"
        ) from exc
    ids = tuple(line.strip() for line in text.splitlines() if line.strip())
    if (
        len(ids) != PUBLIC_REDOCKING_SOURCE_COUNT
        or ids != tuple(sorted(ids))
        or len(set(ids)) != len(ids)
        or any(_CASE_ID_RE.fullmatch(case_id) is None for case_id in ids)
    ):
        raise PublicRedockingBenchmarkError(
            "source identifier document is not the canonical 308-case set"
        )
    selected = _selected_case_ids(ids)
    if selected != FROZEN_PUBLIC_REDOCKING_CASE_IDS:
        raise PublicRedockingBenchmarkError("source identifier selection drifted")
    return selected


@dataclass(frozen=True, slots=True, init=False)
class VerifiedCaseMaterialization:
    """Hash receipt created only from one opened, frozen source archive."""

    case_id: str
    frozen_case_seed: int
    receptor_artifact_sha256: str
    reference_artifact_sha256: str
    native_artifact_sha256: str
    seed_artifact_sha256: str
    source_archive_sha256: str
    archive_member_names: tuple[str, ...]
    schema_id: str
    _receipt_sha256: str = field(repr=False)

    @classmethod
    def _from_verified_archive(
        cls,
        *,
        case_id: str,
        artifact_sha256s: dict[str, str],
        archive_member_names: Sequence[str],
        verification_authority: object,
    ) -> "VerifiedCaseMaterialization":
        if verification_authority is not _VERIFIED_ARCHIVE_AUTHORITY:
            raise TypeError(
                "VerifiedCaseMaterialization requires verified archive authority"
            )
        if case_id not in FROZEN_PUBLIC_REDOCKING_CASE_IDS:
            raise PublicRedockingBenchmarkError(
                "materialization case is not in the frozen cohort"
            )
        expected_roles = tuple(role for role, _ in _CASE_ARTIFACT_ROLES)
        if tuple(artifact_sha256s) != expected_roles:
            raise PublicRedockingBenchmarkError(
                "materialization artifact hash roles are incomplete or unordered"
            )
        expected_members = tuple(
            f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
            for _, filename in _CASE_ARTIFACT_ROLES
        )
        members = tuple(str(value) for value in archive_member_names)
        if members != expected_members:
            raise PublicRedockingBenchmarkError(
                "materialization archive members are cross-wired"
            )
        digests = {
            role: _digest(
                artifact_sha256s[role],
                name=f"{role}_artifact_sha256",
            )
            for role in expected_roles
        }
        profile = next(
            profile
            for profile in frozen_public_redocking_profiles()
            if profile.case_id == case_id
        )
        if digests["native"] != profile.ligand_artifact_sha256:
            raise PublicRedockingBenchmarkError(
                "materialized native ligand is not the frozen profile artifact"
            )
        instance = object.__new__(cls)
        object.__setattr__(instance, "case_id", case_id)
        object.__setattr__(
            instance,
            "frozen_case_seed",
            frozen_public_redocking_case_seed(case_id),
        )
        object.__setattr__(
            instance,
            "receptor_artifact_sha256",
            digests["receptor"],
        )
        object.__setattr__(
            instance,
            "reference_artifact_sha256",
            digests["reference"],
        )
        object.__setattr__(
            instance,
            "native_artifact_sha256",
            digests["native"],
        )
        object.__setattr__(
            instance,
            "seed_artifact_sha256",
            digests["seed"],
        )
        object.__setattr__(
            instance,
            "source_archive_sha256",
            PUBLIC_REDOCKING_ARCHIVE_SHA256,
        )
        object.__setattr__(instance, "archive_member_names", members)
        object.__setattr__(
            instance,
            "schema_id",
            PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID,
        )
        object.__setattr__(
            instance,
            "_receipt_sha256",
            _sha256(instance._projection()),
        )
        return instance

    @property
    def input_artifact_sha256s(self) -> tuple[str, str, str, str]:
        return (
            self.receptor_artifact_sha256,
            self.reference_artifact_sha256,
            self.native_artifact_sha256,
            self.seed_artifact_sha256,
        )

    @property
    def input_artifact_sha256s_by_role(self) -> dict[str, str]:
        return dict(
            zip(
                (role for role, _ in _CASE_ARTIFACT_ROLES),
                self.input_artifact_sha256s,
                strict=True,
            )
        )

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PublicRedockingBenchmarkError(
                "verified materialization receipt changed"
            )
        return observed

    def _projection(self) -> dict[str, object]:
        artifact_sha256s = self.input_artifact_sha256s_by_role
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "frozen_case_seed": self.frozen_case_seed,
            "source_archive_sha256": self.source_archive_sha256,
            "archive_members": {
                filename: member
                for (_, filename), member in zip(
                    _CASE_ARTIFACT_ROLES,
                    self.archive_member_names,
                    strict=True,
                )
            },
            "artifact_sha256s": {
                filename: artifact_sha256s[role]
                for role, filename in _CASE_ARTIFACT_ROLES
            },
            "hash_verified_archive": True,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


class VerifiedPublicRedockingArchive:
    """An opened file descriptor whose complete bytes match the frozen archive."""

    __slots__ = ("_archive", "_closed", "_file_identity", "_handle", "_path")

    def __init__(self) -> None:
        raise TypeError("use VerifiedPublicRedockingArchive.open")

    @staticmethod
    def _status_identity(file_status: os.stat_result) -> tuple[int, ...]:
        return (
            file_status.st_dev,
            file_status.st_ino,
            file_status.st_size,
            file_status.st_mtime_ns,
            file_status.st_ctime_ns,
        )

    @classmethod
    def open(cls, path: str | Path) -> "VerifiedPublicRedockingArchive":
        candidate = Path(path).resolve()
        try:
            handle = candidate.open("rb")
        except OSError as exc:
            raise PublicRedockingBenchmarkError(
                "PoseBusters source archive cannot be opened"
            ) from exc
        try:
            file_status = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(file_status.st_mode)
                or file_status.st_size != PUBLIC_REDOCKING_ARCHIVE_SIZE_BYTES
            ):
                raise PublicRedockingBenchmarkError(
                    "PoseBusters source archive size or file type is invalid"
                )
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != PUBLIC_REDOCKING_ARCHIVE_SHA256:
                raise PublicRedockingBenchmarkError(
                    "PoseBusters source archive hash does not match the frozen cohort"
                )
            final_status = os.fstat(handle.fileno())
            if cls._status_identity(final_status) != cls._status_identity(file_status):
                raise PublicRedockingBenchmarkError(
                    "PoseBusters source archive changed during verification"
                )
            handle.seek(0)
            archive = zipfile.ZipFile(handle, mode="r")
        except zipfile.BadZipFile as exc:
            handle.close()
            raise PublicRedockingBenchmarkError(
                "PoseBusters source archive is not a valid ZIP"
            ) from exc
        except Exception:
            handle.close()
            raise
        instance = object.__new__(cls)
        instance._path = candidate
        instance._handle = handle
        instance._archive = archive
        instance._file_identity = cls._status_identity(final_status)
        instance._closed = False
        return instance

    @property
    def path(self) -> Path:
        return self._path

    @property
    def archive_sha256(self) -> str:
        return PUBLIC_REDOCKING_ARCHIVE_SHA256

    def verified_case(
        self,
        case_id: str,
    ) -> tuple[VerifiedCaseMaterialization, dict[str, bytes]]:
        if self._closed:
            raise PublicRedockingBenchmarkError("verified archive is closed")
        self._require_unchanged_file_identity()
        if case_id not in FROZEN_PUBLIC_REDOCKING_CASE_IDS:
            raise PublicRedockingBenchmarkError(
                "archive case is not in the frozen cohort"
            )
        info_by_name: dict[str, list[zipfile.ZipInfo]] = {}
        for info in self._archive.infolist():
            info_by_name.setdefault(info.filename, []).append(info)
        payloads: dict[str, bytes] = {}
        members: list[str] = []
        artifact_sha256s: dict[str, str] = {}
        for role, filename in _CASE_ARTIFACT_ROLES:
            member = f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
            matches = info_by_name.get(member, [])
            if len(matches) != 1:
                raise PublicRedockingBenchmarkError(
                    f"source archive does not contain exactly one {member}"
                )
            info = matches[0]
            if info.is_dir() or not 1 <= info.file_size <= 64 * 1024 * 1024:
                raise PublicRedockingBenchmarkError(
                    f"source archive member has invalid size: {member}"
                )
            try:
                payload = self._archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PublicRedockingBenchmarkError(
                    f"source archive member cannot be verified: {member}"
                ) from exc
            if len(payload) != info.file_size:
                raise PublicRedockingBenchmarkError(
                    f"source archive member size changed: {member}"
                )
            payloads[role] = payload
            members.append(member)
            artifact_sha256s[role] = hashlib.sha256(payload).hexdigest()
        self._require_unchanged_file_identity()
        receipt = VerifiedCaseMaterialization._from_verified_archive(
            case_id=case_id,
            artifact_sha256s=artifact_sha256s,
            archive_member_names=members,
            verification_authority=_VERIFIED_ARCHIVE_AUTHORITY,
        )
        if receipt.receipt_sha256 != (
            frozen_public_redocking_materialization_receipt_sha256(case_id)
        ):
            raise PublicRedockingBenchmarkError(
                "archive case inputs do not match the frozen materialization receipt"
            )
        return receipt, payloads

    def _require_unchanged_file_identity(self) -> None:
        current = self._status_identity(os.fstat(self._handle.fileno()))
        if current != self._file_identity:
            raise PublicRedockingBenchmarkError(
                "PoseBusters source archive changed after hash verification"
            )

    def verify_complete_sha256(self) -> str:
        if self._closed:
            raise PublicRedockingBenchmarkError("verified archive is closed")
        self._require_unchanged_file_identity()
        position = self._handle.tell()
        self._handle.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: self._handle.read(1024 * 1024), b""):
            digest.update(chunk)
        self._handle.seek(position)
        observed = digest.hexdigest()
        self._require_unchanged_file_identity()
        if observed != PUBLIC_REDOCKING_ARCHIVE_SHA256:
            raise PublicRedockingBenchmarkError(
                "PoseBusters source archive changed after hash verification"
            )
        return observed

    def close(self) -> None:
        if not self._closed:
            self._archive.close()
            self._handle.close()
            self._closed = True

    def __enter__(self) -> "VerifiedPublicRedockingArchive":
        if self._closed:
            raise PublicRedockingBenchmarkError("verified archive is closed")
        return self

    def __exit__(
        self,
        exception_type: object,
        *_: object,
    ) -> None:
        try:
            if exception_type is None:
                self.verify_complete_sha256()
        finally:
            self.close()


@dataclass(frozen=True, slots=True)
class PublicRedockingEvaluationPolicy:
    """One source-matched, fixed-output evaluation policy."""

    ranked_pose_count: int = 5
    top_ks: tuple[int, ...] = PUBLIC_REDOCKING_TOP_KS
    rmsd_threshold_angstrom: float = PUBLIC_REDOCKING_RMSD_THRESHOLD_ANGSTROM
    confidence_level: float = PUBLIC_REDOCKING_DEFAULT_CONFIDENCE_LEVEL
    bootstrap_samples: int = PUBLIC_REDOCKING_DEFAULT_BOOTSTRAP_SAMPLES
    bootstrap_seed: int = PUBLIC_REDOCKING_DEFAULT_BOOTSTRAP_SEED
    external_timeout_seconds: int = 300
    cpu_count: int = 1
    schema_id: str = PUBLIC_REDOCKING_POLICY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REDOCKING_POLICY_SCHEMA_ID:
            raise PublicRedockingBenchmarkError("unsupported evaluation policy schema")
        if type(self.ranked_pose_count) is not int or self.ranked_pose_count != 5:
            raise PublicRedockingBenchmarkError(
                "public redocking ranked_pose_count must equal 5"
            )
        top_ks = tuple(self.top_ks)
        if top_ks != PUBLIC_REDOCKING_TOP_KS:
            raise PublicRedockingBenchmarkError(
                "public redocking top_ks must equal (1,3,5)"
            )
        threshold = _finite(
            self.rmsd_threshold_angstrom,
            name="rmsd_threshold_angstrom",
            minimum=0.0,
        )
        if threshold.hex() != PUBLIC_REDOCKING_RMSD_THRESHOLD_ANGSTROM.hex():
            raise PublicRedockingBenchmarkError(
                "public redocking RMSD threshold must equal 2.0 angstrom"
            )
        level = _finite(self.confidence_level, name="confidence_level")
        if not 0.0 < level < 1.0:
            raise PublicRedockingBenchmarkError("confidence_level must be in (0,1)")
        if (
            type(self.bootstrap_samples) is not int
            or not 100
            <= self.bootstrap_samples
            <= MAX_PUBLIC_REDOCKING_BOOTSTRAP_SAMPLES
        ):
            raise PublicRedockingBenchmarkError(
                "bootstrap_samples must be in [100,20000]"
            )
        if type(self.bootstrap_seed) is not int:
            raise PublicRedockingBenchmarkError("bootstrap_seed must be an integer")
        if (
            type(self.external_timeout_seconds) is not int
            or not 1 <= self.external_timeout_seconds <= 86_400
        ):
            raise PublicRedockingBenchmarkError(
                "external_timeout_seconds must be in [1,86400]"
            )
        if type(self.cpu_count) is not int or self.cpu_count != 1:
            raise PublicRedockingBenchmarkError(
                "public redocking cpu_count must equal 1"
            )
        object.__setattr__(self, "top_ks", top_ks)
        object.__setattr__(self, "rmsd_threshold_angstrom", threshold)
        object.__setattr__(self, "confidence_level", level)

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "ranked_pose_count": self.ranked_pose_count,
            "top_ks": list(self.top_ks),
            "rmsd_threshold_angstrom": self.rmsd_threshold_angstrom,
            "confidence_level": self.confidence_level,
            "bootstrap_samples": self.bootstrap_samples,
            "bootstrap_seed": self.bootstrap_seed,
            "external_timeout_seconds": self.external_timeout_seconds,
            "cpu_count": self.cpu_count,
            "same_source_artifacts_required": True,
            "same_pocket_source_required": True,
            "same_pocket_geometry": False,
            "same_ranked_pose_count_required": True,
            "same_search_effort_required": False,
            "failure_denominator": "all_cases_in_each_analysis_scope",
            "historical_primary_failure_denominator": (
                "298_cases_invalidated_nonclaimable"
            ),
            "fresh_internal_failure_denominator": "128_untouched_cases",
            "engineering_smoke_failure_denominator": "2_observed_smoke_cases",
            "supplementary_failure_denominator": "all_300_frozen_cases",
            "missing_candidate_policy": "case_failure",
            "engine_v2_candidate_budget": (
                PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
            ),
            "engine_v2_candidate_denominator": (
                "all_64_predeclared_candidate_slots_per_prepared_case"
            ),
            "proposal_oracle_definition": (
                "minimum_posebusters_symmetry_aware_rmsd_across_all_successful_"
                "engine_v2_candidates"
            ),
            "valid_proposal_oracle_definition": (
                "proposal_oracle_candidate_also_passes_all_geometric_and_"
                "chemical_posebusters_checks"
            ),
            "top1_scoring_regret_definition": (
                "score_rank_1_rmsd_minus_proposal_oracle_rmsd"
            ),
            "top5_selection_regret_definition": (
                "best_score_ranked_top5_rmsd_minus_proposal_oracle_rmsd"
            ),
            "complete_partial_charge_coverage_definition": (
                "finite_partial_charge_present_for_every_prepared_receptor_"
                "and_ligand_atom"
            ),
            "hbond_feature_coverage_definition": (
                "scorer_context_has_at_least_one_complementary_ligand_"
                "donor_receptor_acceptor_or_ligand_acceptor_receptor_donor_pair"
            ),
            "candidate_diagnostic_evaluation_in_engine_runtime": False,
            "ring_subgroup_definition": (
                "rdkit_2022_09_5_calc_num_rings_grouped_as_0_1_or_2_plus"
            ),
        }


@dataclass(frozen=True, slots=True)
class PublicRedockingCaseProfile:
    case_id: str
    heavy_atom_count: int
    rotor_count: int
    ring_count: int
    ligand_artifact_sha256: str

    def __post_init__(self) -> None:
        if _CASE_ID_RE.fullmatch(str(self.case_id or "")) is None:
            raise PublicRedockingBenchmarkError("profile case_id is invalid")
        if (
            type(self.heavy_atom_count) is not int
            or not 1 <= self.heavy_atom_count <= 512
        ):
            raise PublicRedockingBenchmarkError("heavy_atom_count must be in [1,512]")
        if type(self.rotor_count) is not int or not 0 <= self.rotor_count <= 128:
            raise PublicRedockingBenchmarkError("rotor_count must be in [0,128]")
        if type(self.ring_count) is not int or not 0 <= self.ring_count <= 128:
            raise PublicRedockingBenchmarkError("ring_count must be in [0,128]")
        object.__setattr__(
            self,
            "ligand_artifact_sha256",
            _digest(
                self.ligand_artifact_sha256,
                name="ligand_artifact_sha256",
            ),
        )

    @property
    def size_subgroup(self) -> str:
        if self.heavy_atom_count <= 20:
            return "size_small_1_20"
        if self.heavy_atom_count <= 40:
            return "size_medium_21_40"
        return "size_large_41_plus"

    @property
    def rotor_subgroup(self) -> str:
        if self.rotor_count == 0:
            return "rotor_rigid_0"
        if self.rotor_count <= 4:
            return "rotor_low_1_4"
        return "rotor_flexible_5_plus"

    @property
    def ring_subgroup(self) -> str:
        if self.ring_count == 0:
            return "ring_acyclic_0"
        if self.ring_count == 1:
            return "ring_single_1"
        return "ring_multi_2_plus"

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "heavy_atom_count": self.heavy_atom_count,
            "rotor_count": self.rotor_count,
            "ring_count": self.ring_count,
            "ligand_artifact_sha256": self.ligand_artifact_sha256,
            "profile_method_id": PUBLIC_REDOCKING_PROFILE_METHOD_ID,
            "ring_profile_method_id": PUBLIC_REDOCKING_RING_PROFILE_METHOD_ID,
            "size_subgroup": self.size_subgroup,
            "rotor_subgroup": self.rotor_subgroup,
            "ring_subgroup": self.ring_subgroup,
        }


def frozen_public_redocking_profiles() -> tuple[PublicRedockingCaseProfile, ...]:
    """Return source-bound heavy-atom and strict-rotor profiles for all cases."""

    source = (_FROZEN_PROFILE_ROWS_TEXT + "\n").encode("ascii")
    if hashlib.sha256(source).hexdigest() != PUBLIC_REDOCKING_PROFILES_SHA256:
        raise PublicRedockingBenchmarkError("frozen redocking profiles drifted")
    profiles: list[PublicRedockingCaseProfile] = []
    for row in _FROZEN_PROFILE_ROWS_TEXT.splitlines():
        fields = row.split(",")
        if len(fields) != 4:
            raise PublicRedockingBenchmarkError(
                "frozen redocking profile row is malformed"
            )
        case_id, heavy_atoms, rotors, ligand_sha256 = fields
        try:
            profiles.append(
                PublicRedockingCaseProfile(
                    case_id=case_id,
                    heavy_atom_count=int(heavy_atoms),
                    rotor_count=int(rotors),
                    ring_count=_FROZEN_RING_COUNT_BY_CASE[case_id],
                    ligand_artifact_sha256=ligand_sha256,
                )
            )
        except (TypeError, ValueError) as exc:
            raise PublicRedockingBenchmarkError(
                "frozen redocking profile row is malformed"
            ) from exc
    result = tuple(profiles)
    if tuple(profile.case_id for profile in result) != (
        FROZEN_PUBLIC_REDOCKING_CASE_IDS
    ):
        raise PublicRedockingBenchmarkError("frozen redocking profiles are cross-wired")
    return result


@dataclass(frozen=True, slots=True)
class PublicRedockingEngineIdentity:
    engine_id: str
    version: str
    implementation_sha256: str
    evaluation_pipeline_sha256: str
    command: tuple[str, ...]

    def __post_init__(self) -> None:
        engine_id = str(self.engine_id or "").strip().lower()
        if engine_id not in PUBLIC_REDOCKING_PRIMARY_ENGINES:
            raise PublicRedockingBenchmarkError("unsupported redocking engine")
        if not str(self.version or "").strip():
            raise PublicRedockingBenchmarkError("engine version must be non-empty")
        command = tuple(str(value) for value in self.command)
        if not command or any(not value for value in command):
            raise PublicRedockingBenchmarkError("engine command must be non-empty")
        object.__setattr__(self, "engine_id", engine_id)
        object.__setattr__(
            self,
            "implementation_sha256",
            _digest(self.implementation_sha256, name="implementation_sha256"),
        )
        object.__setattr__(
            self,
            "evaluation_pipeline_sha256",
            _digest(
                self.evaluation_pipeline_sha256,
                name="evaluation_pipeline_sha256",
            ),
        )
        object.__setattr__(self, "command", command)

    def to_dict(self) -> dict[str, object]:
        return {
            "engine_id": self.engine_id,
            "version": self.version,
            "implementation_sha256": self.implementation_sha256,
            "evaluation_pipeline_sha256": self.evaluation_pipeline_sha256,
            "command": list(self.command),
        }


@dataclass(frozen=True, slots=True)
class PublicRedockingEngineV2CandidateDiagnostic:
    """One retained row from the fixed 64-candidate Engine V2 denominator."""

    proposal_index: int
    status: str
    proposal_mode: str = ""
    ensemble_source_proposal_index: int | None = None
    proposal_fingerprint_sha256: str = ""
    coordinate_fingerprint_sha256: str = ""
    score: float | None = None
    rmsd_angstrom: float | None = None
    geometric_valid: bool | None = None
    chemical_valid: bool | None = None
    pose_artifact_sha256: str = ""
    score_terms_receipt_sha256: str = ""
    hbond_count: int | None = None
    selection_eligible: bool | None = None
    posebusters_failed_check_ids: tuple[str, ...] = ()
    refinement_receipt_sha256: str = ""
    refinement_initial_penalty_binary64_hex: str = ""
    refinement_final_penalty_binary64_hex: str = ""
    refinement_accepted_steps: int | None = None
    refinement_accepted_rotation_steps: int | None = None
    refinement_original_pose_valid: bool | None = None
    refinement_total_translation_binary64_hex: tuple[str, ...] = ()
    refinement_total_rotation_vector_binary64_hex: tuple[str, ...] = ()
    refinement_receipt_payload: Mapping[str, object] = field(default_factory=dict)
    score_term_binary64_hex: Mapping[str, str] = field(default_factory=dict)
    error_code: str = ""
    schema_id: str = PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID:
            raise PublicRedockingBenchmarkError(
                "unsupported Engine V2 candidate diagnostic schema"
            )
        if (
            type(self.proposal_index) is not int
            or not 0
            <= self.proposal_index
            < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 candidate proposal_index is invalid"
            )
        status = str(self.status or "").strip().lower()
        if status not in {"success", "failure"}:
            raise PublicRedockingBenchmarkError(
                "Engine V2 candidate status must be success or failure"
            )
        error_code = str(self.error_code or "").strip()
        proposal_mode = str(self.proposal_mode or "").strip()
        ensemble_source = self.ensemble_source_proposal_index
        if proposal_mode == "uniform_v3_rigid_ensemble":
            if (
                type(ensemble_source) is not int
                or not 0
                <= ensemble_source
                < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
                or ensemble_source == self.proposal_index
            ):
                raise PublicRedockingBenchmarkError(
                    "uniform V3 ensemble candidate source index is invalid"
                )
        elif ensemble_source is not None:
            raise PublicRedockingBenchmarkError(
                "non-ensemble candidate cannot declare an ensemble source"
            )
        failed_checks = tuple(
            str(value or "").strip()
            for value in self.posebusters_failed_check_ids
        )
        allowed_checks = (
            *PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
            *PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
        )
        if (
            failed_checks
            != tuple(
                check for check in allowed_checks if check in set(failed_checks)
            )
            or len(failed_checks) != len(set(failed_checks))
        ):
            raise PublicRedockingBenchmarkError(
                "candidate PoseBusters failed checks are invalid"
            )
        score_terms = dict(self.score_term_binary64_hex)
        if status == "success":
            if proposal_mode not in PUBLIC_REDOCKING_PROPOSAL_MODES:
                raise PublicRedockingBenchmarkError(
                    "successful candidate proposal mode is invalid"
                )
            proposal_sha256 = _digest(
                self.proposal_fingerprint_sha256,
                name="proposal_fingerprint_sha256",
            )
            coordinate_sha256 = _digest(
                self.coordinate_fingerprint_sha256,
                name="coordinate_fingerprint_sha256",
            )
            pose_sha256 = _digest(
                self.pose_artifact_sha256,
                name="pose_artifact_sha256",
            )
            terms_sha256 = _digest(
                self.score_terms_receipt_sha256,
                name="score_terms_receipt_sha256",
            )
            score = _finite(self.score, name="candidate score")
            rmsd = _finite(
                self.rmsd_angstrom,
                name="candidate rmsd_angstrom",
                minimum=0.0,
            )
            if (
                type(self.geometric_valid) is not bool
                or type(self.chemical_valid) is not bool
                or type(self.hbond_count) is not int
                or self.hbond_count < 0
                or type(self.selection_eligible) is not bool
                or set(score_terms) != set(_SCORER_TERM_NAMES)
                or self.geometric_valid
                != (not bool(
                    set(failed_checks)
                    & set(PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS)
                ))
                or self.chemical_valid
                != (not bool(
                    set(failed_checks)
                    & set(PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS)
                ))
            ):
                raise PublicRedockingBenchmarkError(
                    "successful Engine V2 candidate diagnostics are incomplete"
                )
            try:
                decoded_terms = {
                    name: float.fromhex(score_terms[name])
                    for name in _SCORER_TERM_NAMES
                }
            except (TypeError, ValueError, OverflowError) as exc:
                raise PublicRedockingBenchmarkError(
                    "successful candidate score terms are invalid"
                ) from exc
            if any(
                not math.isfinite(value) or value.hex() != score_terms[name]
                for name, value in decoded_terms.items()
            ) or not math.isclose(
                decoded_terms["total_score"],
                sum(decoded_terms[name] for name in _SCORER_TERM_NAMES[:-1]),
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise PublicRedockingBenchmarkError(
                    "successful candidate score terms are inconsistent"
                )
            if error_code:
                raise PublicRedockingBenchmarkError(
                    "successful Engine V2 candidate cannot contain error_code"
                )
            object.__setattr__(self, "proposal_fingerprint_sha256", proposal_sha256)
            object.__setattr__(
                self, "coordinate_fingerprint_sha256", coordinate_sha256
            )
            object.__setattr__(self, "pose_artifact_sha256", pose_sha256)
            object.__setattr__(self, "score_terms_receipt_sha256", terms_sha256)
            object.__setattr__(self, "score", score)
            object.__setattr__(self, "rmsd_angstrom", rmsd)
            refinement_fields_present = bool(
                self.refinement_receipt_sha256
                or self.refinement_initial_penalty_binary64_hex
                or self.refinement_final_penalty_binary64_hex
                or self.refinement_accepted_steps is not None
                or self.refinement_accepted_rotation_steps is not None
                or self.refinement_original_pose_valid is not None
                or self.refinement_total_translation_binary64_hex
                or self.refinement_total_rotation_vector_binary64_hex
            )
            if refinement_fields_present:
                refinement_sha256 = _digest(
                    self.refinement_receipt_sha256,
                    name="refinement_receipt_sha256",
                )
                try:
                    initial_penalty = float.fromhex(
                        self.refinement_initial_penalty_binary64_hex
                    )
                    final_penalty = float.fromhex(
                        self.refinement_final_penalty_binary64_hex
                    )
                    translation = tuple(
                        float.fromhex(value)
                        for value in self.refinement_total_translation_binary64_hex
                    )
                    rotation = tuple(
                        float.fromhex(value)
                        for value in self.refinement_total_rotation_vector_binary64_hex
                    )
                except (TypeError, ValueError, OverflowError) as exc:
                    raise PublicRedockingBenchmarkError(
                        "candidate refinement diagnostics are invalid"
                    ) from exc
                if (
                    not math.isfinite(initial_penalty)
                    or not math.isfinite(final_penalty)
                    or initial_penalty < 0.0
                    or final_penalty < 0.0
                    or initial_penalty.hex()
                    != self.refinement_initial_penalty_binary64_hex
                    or final_penalty.hex()
                    != self.refinement_final_penalty_binary64_hex
                    or type(self.refinement_accepted_steps) is not int
                    or self.refinement_accepted_steps < 0
                    or type(self.refinement_accepted_rotation_steps) is not int
                    or not 0
                    <= self.refinement_accepted_rotation_steps
                    <= self.refinement_accepted_steps
                    or type(self.refinement_original_pose_valid) is not bool
                    or len(translation) != 3
                    or len(rotation) != 3
                    or any(
                        not math.isfinite(value)
                        or value.hex()
                        != self.refinement_total_translation_binary64_hex[index]
                        for index, value in enumerate(translation)
                    )
                    or any(
                        not math.isfinite(value)
                        or value.hex()
                        != self.refinement_total_rotation_vector_binary64_hex[index]
                        for index, value in enumerate(rotation)
                    )
                ):
                    raise PublicRedockingBenchmarkError(
                        "candidate refinement diagnostics are incomplete"
                    )
                object.__setattr__(
                    self, "refinement_receipt_sha256", refinement_sha256
                )
                receipt_payload = dict(self.refinement_receipt_payload)
                if receipt_payload:
                    claimed_payload_sha256 = receipt_payload.pop(
                        "receipt_sha256", ""
                    )
                    if (
                        claimed_payload_sha256 != refinement_sha256
                        or _sha256(receipt_payload) != refinement_sha256
                    ):
                        raise PublicRedockingBenchmarkError(
                            "candidate refinement receipt payload is invalid"
                        )
                    receipt_payload["receipt_sha256"] = claimed_payload_sha256
                elif proposal_mode == "uniform_v3_rigid_ensemble":
                    raise PublicRedockingBenchmarkError(
                        "V3 ensemble candidate lacks refinement receipt payload"
                    )
                object.__setattr__(
                    self,
                    "refinement_receipt_payload",
                    MappingProxyType(receipt_payload),
                )
        elif (
            self.proposal_fingerprint_sha256
            or self.coordinate_fingerprint_sha256
            or self.score is not None
            or self.rmsd_angstrom is not None
            or self.geometric_valid is not None
            or self.chemical_valid is not None
            or self.pose_artifact_sha256
            or self.score_terms_receipt_sha256
            or self.hbond_count is not None
            or self.selection_eligible is not None
            or score_terms
            or failed_checks
            or self.refinement_receipt_sha256
            or self.refinement_initial_penalty_binary64_hex
            or self.refinement_final_penalty_binary64_hex
            or self.refinement_accepted_steps is not None
            or self.refinement_accepted_rotation_steps is not None
            or self.refinement_original_pose_valid is not None
            or self.refinement_total_translation_binary64_hex
            or self.refinement_total_rotation_vector_binary64_hex
            or self.refinement_receipt_payload
            or not error_code
        ):
            raise PublicRedockingBenchmarkError(
                "failed Engine V2 candidate requires error_code and optional mode"
            )
        elif proposal_mode and proposal_mode not in PUBLIC_REDOCKING_PROPOSAL_MODES:
            raise PublicRedockingBenchmarkError(
                "failed candidate proposal mode is invalid"
            )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "proposal_mode", proposal_mode)
        object.__setattr__(self, "posebusters_failed_check_ids", failed_checks)
        object.__setattr__(
            self,
            "refinement_total_translation_binary64_hex",
            tuple(self.refinement_total_translation_binary64_hex),
        )
        object.__setattr__(
            self,
            "refinement_total_rotation_vector_binary64_hex",
            tuple(self.refinement_total_rotation_vector_binary64_hex),
        )
        if not self.refinement_receipt_payload:
            object.__setattr__(
                self,
                "refinement_receipt_payload",
                MappingProxyType({}),
            )
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(
            self,
            "score_term_binary64_hex",
            MappingProxyType(
                {
                    name: score_terms[name]
                    for name in _SCORER_TERM_NAMES
                    if name in score_terms
                }
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "proposal_index": self.proposal_index,
            "status": self.status,
            "proposal_mode": self.proposal_mode,
            "ensemble_source_proposal_index": (
                self.ensemble_source_proposal_index
            ),
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_fingerprint_sha256": self.coordinate_fingerprint_sha256,
            "score": self.score,
            "rmsd_angstrom": self.rmsd_angstrom,
            "geometric_valid": self.geometric_valid,
            "chemical_valid": self.chemical_valid,
            "pose_artifact_sha256": self.pose_artifact_sha256,
            "score_terms_receipt_sha256": self.score_terms_receipt_sha256,
            "hbond_count": self.hbond_count,
            "selection_eligible": self.selection_eligible,
            "posebusters_failed_check_ids": list(self.posebusters_failed_check_ids),
            "refinement_receipt_sha256": self.refinement_receipt_sha256,
            "refinement_initial_penalty_binary64_hex": (
                self.refinement_initial_penalty_binary64_hex
            ),
            "refinement_final_penalty_binary64_hex": (
                self.refinement_final_penalty_binary64_hex
            ),
            "refinement_accepted_steps": self.refinement_accepted_steps,
            "refinement_accepted_rotation_steps": (
                self.refinement_accepted_rotation_steps
            ),
            "refinement_original_pose_valid": self.refinement_original_pose_valid,
            "refinement_total_translation_binary64_hex": list(
                self.refinement_total_translation_binary64_hex
            ),
            "refinement_total_rotation_vector_binary64_hex": list(
                self.refinement_total_rotation_vector_binary64_hex
            ),
            "refinement_receipt_payload": dict(self.refinement_receipt_payload),
            "score_term_binary64_hex": dict(self.score_term_binary64_hex),
            "error_code": self.error_code,
        }


def _validated_scorer_backend_receipt(
    value: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("scorer backend receipt must be a mapping")
    payload = dict(value)
    required = {
        "schema_id",
        "backend",
        "backend_version",
        "implementation_source_sha256",
        "options_fingerprint_sha256",
        "extension_sha256",
        "cargo_lock_sha256",
        "rustc_version",
        "target_triple",
        "build_flags",
        "implicit_fallback_allowed",
        "receipt_sha256",
    }
    if set(payload) != required:
        raise PublicRedockingBenchmarkError(
            "scorer backend receipt fields are incomplete"
        )
    if payload["schema_id"] != _SCORER_V1_BACKEND_RECEIPT_SCHEMA_ID:
        raise PublicRedockingBenchmarkError(
            "scorer backend receipt schema is unsupported"
        )
    backend = str(payload["backend"] or "").strip()
    if backend not in {"python_reference", "rust_cpu_required"}:
        raise PublicRedockingBenchmarkError("scorer backend is unsupported")
    if not str(payload["backend_version"] or "").strip():
        raise PublicRedockingBenchmarkError("scorer backend version is missing")
    for field_name in (
        "implementation_source_sha256",
        "options_fingerprint_sha256",
        "receipt_sha256",
    ):
        _digest(payload[field_name], name=field_name)
    flags = payload["build_flags"]
    if (
        not isinstance(flags, (list, tuple))
        or any(not isinstance(flag, str) or not flag.strip() for flag in flags)
        or len(flags) != len(set(flags))
    ):
        raise PublicRedockingBenchmarkError(
            "scorer backend build flags are invalid"
        )
    native_fields = (
        "extension_sha256",
        "cargo_lock_sha256",
        "rustc_version",
        "target_triple",
    )
    if backend == "rust_cpu_required":
        _digest(payload["extension_sha256"], name="extension_sha256")
        _digest(payload["cargo_lock_sha256"], name="cargo_lock_sha256")
        if any(not str(payload[name] or "").strip() for name in native_fields[2:]):
            raise PublicRedockingBenchmarkError(
                "Rust scorer backend build identity is incomplete"
            )
        if not flags:
            raise PublicRedockingBenchmarkError(
                "Rust scorer backend build flags are missing"
            )
    elif any(payload[name] not in ("", None) for name in native_fields) or flags:
        raise PublicRedockingBenchmarkError(
            "Python scorer backend cannot claim native build identity"
        )
    if payload["implicit_fallback_allowed"] is not False:
        raise PublicRedockingBenchmarkError(
            "scorer backend receipt permits implicit fallback"
        )
    receipt_sha256 = payload.pop("receipt_sha256")
    payload["build_flags"] = list(flags)
    if receipt_sha256 != _sha256(payload):
        raise PublicRedockingBenchmarkError("scorer backend receipt hash mismatch")
    payload["receipt_sha256"] = receipt_sha256
    payload["build_flags"] = tuple(flags)
    return MappingProxyType(payload)


@dataclass(frozen=True, slots=True)
class PublicRedockingEngineV2Diagnostics:
    """Preparation, search-oracle, scoring, charge, and H-bond evidence."""

    preparation_status: str
    receptor_atom_count: int
    ligand_atom_count: int
    receptor_partial_charge_count: int
    ligand_partial_charge_count: int
    receptor_donor_count: int
    receptor_acceptor_count: int
    ligand_donor_count: int
    ligand_acceptor_count: int
    receptor_ion_proxy_count: int = 0
    candidates: tuple[PublicRedockingEngineV2CandidateDiagnostic, ...] = ()
    scorer_backend_receipt: Mapping[str, object] | None = None
    preparation_failure_code: str = ""
    diagnostic_evaluation_seconds: float = 0.0
    candidate_budget: int = PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
    schema_id: str = PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID:
            raise PublicRedockingBenchmarkError(
                "unsupported Engine V2 diagnostic schema"
            )
        if self.candidate_budget != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT:
            raise PublicRedockingBenchmarkError(
                "Engine V2 diagnostic candidate budget must equal 64"
            )
        status = str(self.preparation_status or "").strip().lower()
        if status not in {"success", "failure"}:
            raise PublicRedockingBenchmarkError(
                "Engine V2 preparation status must be success or failure"
            )
        counts = tuple(
            getattr(self, name)
            for name in (
                "receptor_atom_count",
                "ligand_atom_count",
                "receptor_partial_charge_count",
                "ligand_partial_charge_count",
                "receptor_donor_count",
                "receptor_acceptor_count",
                "ligand_donor_count",
                "ligand_acceptor_count",
                "receptor_ion_proxy_count",
            )
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise PublicRedockingBenchmarkError(
                "Engine V2 preparation counts must be non-negative integers"
            )
        candidates = tuple(self.candidates)
        backend_receipt = _validated_scorer_backend_receipt(
            self.scorer_backend_receipt
        )
        failure_code = str(self.preparation_failure_code or "").strip()
        diagnostic_evaluation_seconds = _finite(
            self.diagnostic_evaluation_seconds,
            name="diagnostic_evaluation_seconds",
            minimum=0.0,
        )
        if status == "failure":
            if (
                any(counts)
                or candidates
                or backend_receipt is not None
                or failure_code
                not in _PUBLIC_REDOCKING_ENGINE_V2_PREPARATION_FAILURE_CODES
                or diagnostic_evaluation_seconds != 0.0
            ):
                raise PublicRedockingBenchmarkError(
                    "failed Engine V2 preparation cannot fabricate diagnostics"
                )
        else:
            if (
                self.receptor_atom_count < 1
                or self.ligand_atom_count < 1
                or self.receptor_ion_proxy_count > self.receptor_atom_count
                or self.receptor_partial_charge_count != self.receptor_atom_count
                or self.ligand_partial_charge_count != self.ligand_atom_count
                or failure_code
                or len(candidates) != self.candidate_budget
                or backend_receipt is None
                or tuple(row.proposal_index for row in candidates)
                != tuple(range(self.candidate_budget))
            ):
                raise PublicRedockingBenchmarkError(
                    "successful Engine V2 preparation diagnostics are incomplete"
                )
            successful_fingerprints = tuple(
                row.proposal_fingerprint_sha256
                for row in candidates
                if row.status == "success"
            )
            if len(successful_fingerprints) != len(set(successful_fingerprints)):
                raise PublicRedockingBenchmarkError(
                    "Engine V2 candidate proposal fingerprints must be unique"
                )
        if any(
            type(row) is not PublicRedockingEngineV2CandidateDiagnostic
            for row in candidates
        ):
            raise TypeError(
                "Engine V2 candidates must be typed candidate diagnostics"
            )
        if status == "success":
            ensemble_sources = tuple(
                row.ensemble_source_proposal_index
                for row in candidates
                if row.ensemble_source_proposal_index is not None
            )
            if (
                len(ensemble_sources) != len(set(ensemble_sources))
                or any(
                    candidates[source_index].proposal_mode != "uniform_fallback"
                    for source_index in ensemble_sources
                )
            ):
                raise PublicRedockingBenchmarkError(
                    "uniform V3 ensemble candidate lineage is invalid"
                )
        object.__setattr__(self, "preparation_status", status)
        object.__setattr__(self, "preparation_failure_code", failure_code)
        object.__setattr__(
            self,
            "diagnostic_evaluation_seconds",
            diagnostic_evaluation_seconds,
        )
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "scorer_backend_receipt", backend_receipt)

    @property
    def charge_coverage_complete(self) -> bool:
        return bool(
            self.preparation_status == "success"
            and self.receptor_partial_charge_count == self.receptor_atom_count
            and self.ligand_partial_charge_count == self.ligand_atom_count
        )

    @property
    def hbond_feature_covered(self) -> bool:
        return bool(
            self.preparation_status == "success"
            and (
                (
                    self.ligand_donor_count > 0
                    and self.receptor_acceptor_count > 0
                )
                or (
                    self.ligand_acceptor_count > 0
                    and self.receptor_donor_count > 0
                )
            )
        )

    @property
    def successful_candidates(
        self,
    ) -> tuple[PublicRedockingEngineV2CandidateDiagnostic, ...]:
        return tuple(row for row in self.candidates if row.status == "success")

    @property
    def score_ranked_candidates(
        self,
    ) -> tuple[PublicRedockingEngineV2CandidateDiagnostic, ...]:
        return tuple(
            sorted(
                self.successful_candidates,
                key=lambda row: (float(row.score), row.proposal_index),
            )
        )

    @property
    def proposal_oracle_rmsd_angstrom(self) -> float | None:
        values = tuple(
            float(row.rmsd_angstrom) for row in self.successful_candidates
        )
        return None if not values else min(values)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "preparation_status": self.preparation_status,
            "preparation_failure_code": self.preparation_failure_code,
            "diagnostic_evaluation_seconds": self.diagnostic_evaluation_seconds,
            "diagnostic_evaluation_excluded_from_runtime": True,
            "receptor_atom_count": self.receptor_atom_count,
            "ligand_atom_count": self.ligand_atom_count,
            "receptor_partial_charge_count": self.receptor_partial_charge_count,
            "ligand_partial_charge_count": self.ligand_partial_charge_count,
            "receptor_donor_count": self.receptor_donor_count,
            "receptor_acceptor_count": self.receptor_acceptor_count,
            "ligand_donor_count": self.ligand_donor_count,
            "ligand_acceptor_count": self.ligand_acceptor_count,
            "receptor_ion_proxy_count": self.receptor_ion_proxy_count,
            "receptor_ion_proxy_used": self.receptor_ion_proxy_count > 0,
            "receptor_ion_coordination_modeled": False,
            "ligand_metal_support": False,
            "charge_coverage_complete": self.charge_coverage_complete,
            "hbond_feature_covered": self.hbond_feature_covered,
            "candidate_budget": self.candidate_budget,
            "scorer_backend_receipt": (
                None
                if self.scorer_backend_receipt is None
                else {
                    **dict(self.scorer_backend_receipt),
                    "build_flags": list(
                        self.scorer_backend_receipt["build_flags"]
                    ),
                }
            ),
            "candidate_success_count": len(self.successful_candidates),
            "candidate_failure_count": (
                self.candidate_budget - len(self.successful_candidates)
                if self.preparation_status == "success"
                else 0
            ),
            "proposal_oracle_rmsd_angstrom": (
                self.proposal_oracle_rmsd_angstrom
            ),
            "candidates": [row.to_dict() for row in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class PublicRedockingCaseResult:
    """One engine/case row; failures retain runtime and the full denominator."""

    case_id: str
    engine_id: str
    status: str
    runtime_seconds: float
    receptor_artifact_sha256: str
    reference_artifact_sha256: str
    native_artifact_sha256: str
    seed_artifact_sha256: str
    execution_command: tuple[str, ...]
    execution_policy: tuple[str, ...]
    rmsd_angstroms: tuple[float, ...] = ()
    geometric_valid: tuple[bool, ...] = ()
    chemical_valid: tuple[bool, ...] = ()
    pose_artifact_sha256s: tuple[str, ...] = ()
    failure_code: str = ""
    engine_v2_diagnostics: PublicRedockingEngineV2Diagnostics | None = None

    def __post_init__(self) -> None:
        if _CASE_ID_RE.fullmatch(str(self.case_id or "")) is None:
            raise PublicRedockingBenchmarkError("result case_id is invalid")
        engine_id = str(self.engine_id or "").strip().lower()
        if engine_id not in PUBLIC_REDOCKING_PRIMARY_ENGINES:
            raise PublicRedockingBenchmarkError("unsupported result engine")
        status = str(self.status or "").strip().lower()
        if status not in {"success", "failure"}:
            raise PublicRedockingBenchmarkError(
                "result status must be success or failure"
            )
        runtime = _finite(
            self.runtime_seconds,
            name="runtime_seconds",
            minimum=0.0,
        )
        for field_name in (
            "receptor_artifact_sha256",
            "reference_artifact_sha256",
            "native_artifact_sha256",
            "seed_artifact_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), name=field_name),
            )
        command = tuple(str(value) for value in self.execution_command)
        execution_policy = tuple(str(value) for value in self.execution_policy)
        if not command or any(not value for value in command):
            raise PublicRedockingBenchmarkError(
                "result execution_command must be non-empty"
            )
        if (
            not execution_policy
            or execution_policy != tuple(sorted(execution_policy))
            or any("=" not in value for value in execution_policy)
        ):
            raise PublicRedockingBenchmarkError(
                "result execution_policy must be non-empty sorted key=value tokens"
            )
        _execution_policy_mapping(execution_policy)
        rmsds = tuple(
            _finite(value, name="rmsd_angstrom", minimum=0.0)
            for value in self.rmsd_angstroms
        )
        geometric = tuple(self.geometric_valid)
        chemical = tuple(self.chemical_valid)
        pose_artifacts = tuple(self.pose_artifact_sha256s)
        if any(type(value) is not bool for value in (*geometric, *chemical)):
            raise PublicRedockingBenchmarkError("pose-validity values must be booleans")
        failure_code = str(self.failure_code or "").strip()
        diagnostics = self.engine_v2_diagnostics
        if diagnostics is not None and type(diagnostics) is not (
            PublicRedockingEngineV2Diagnostics
        ):
            raise TypeError(
                "engine_v2_diagnostics must be typed Engine V2 diagnostics"
            )
        if engine_id != "engine_v2" and diagnostics is not None:
            raise PublicRedockingBenchmarkError(
                "external result rows cannot contain Engine V2 diagnostics"
            )
        if status == "success":
            if not (
                len(rmsds)
                == len(geometric)
                == len(chemical)
                == len(pose_artifacts)
                == 5
            ):
                raise PublicRedockingBenchmarkError(
                    "success rows require exactly five ranked pose outcomes"
                )
            pose_artifacts = tuple(
                _digest(value, name="pose_artifact_sha256") for value in pose_artifacts
            )
            if failure_code:
                raise PublicRedockingBenchmarkError(
                    "success rows cannot contain failure_code"
                )
        elif rmsds or geometric or chemical or pose_artifacts or not failure_code:
            raise PublicRedockingBenchmarkError(
                "failure rows require only a non-empty failure_code"
            )
        object.__setattr__(self, "engine_id", engine_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "runtime_seconds", runtime)
        object.__setattr__(self, "execution_command", command)
        object.__setattr__(self, "execution_policy", execution_policy)
        object.__setattr__(self, "rmsd_angstroms", rmsds)
        object.__setattr__(self, "geometric_valid", geometric)
        object.__setattr__(self, "chemical_valid", chemical)
        object.__setattr__(self, "pose_artifact_sha256s", pose_artifacts)
        object.__setattr__(self, "failure_code", failure_code)
        object.__setattr__(self, "engine_v2_diagnostics", diagnostics)

    def recovery(self, top_k: int, threshold: float) -> float:
        if self.status == "failure":
            return 0.0
        return float(min(self.rmsd_angstroms[:top_k]) <= threshold)

    @property
    def input_artifact_sha256s(self) -> tuple[str, str, str, str]:
        return (
            self.receptor_artifact_sha256,
            self.reference_artifact_sha256,
            self.native_artifact_sha256,
            self.seed_artifact_sha256,
        )

    def valid_recovery(self, top_k: int, threshold: float) -> float:
        if self.status == "failure":
            return 0.0
        return float(
            any(
                rmsd <= threshold and geometric and chemical
                for rmsd, geometric, chemical in zip(
                    self.rmsd_angstroms[:top_k],
                    self.geometric_valid[:top_k],
                    self.chemical_valid[:top_k],
                    strict=True,
                )
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "engine_id": self.engine_id,
            "status": self.status,
            "runtime_seconds": self.runtime_seconds,
            "receptor_artifact_sha256": self.receptor_artifact_sha256,
            "reference_artifact_sha256": self.reference_artifact_sha256,
            "native_artifact_sha256": self.native_artifact_sha256,
            "seed_artifact_sha256": self.seed_artifact_sha256,
            "execution_command": list(self.execution_command),
            "execution_policy": list(self.execution_policy),
            "rmsd_angstroms": list(self.rmsd_angstroms),
            "geometric_valid": list(self.geometric_valid),
            "chemical_valid": list(self.chemical_valid),
            "pose_artifact_sha256s": list(self.pose_artifact_sha256s),
            "failure_code": self.failure_code,
            "engine_v2_diagnostics": (
                None
                if self.engine_v2_diagnostics is None
                else self.engine_v2_diagnostics.to_dict()
            ),
        }


def _validate_engine_v2_result_diagnostics(
    row: PublicRedockingCaseResult,
) -> None:
    diagnostics = row.engine_v2_diagnostics
    if type(diagnostics) is not PublicRedockingEngineV2Diagnostics:
        raise PublicRedockingBenchmarkError(
            "every Engine V2 result must retain typed diagnostics"
        )
    execution_policy = _execution_policy_mapping(row.execution_policy)
    scorer_backend = execution_policy.get("scorer_backend")
    if scorer_backend not in {"python_reference", "rust_cpu_required"}:
        raise PublicRedockingBenchmarkError(
            "Engine V2 scorer backend policy is unsupported"
        )
    if execution_policy.get("scorer_thread_count") != 1:
        raise PublicRedockingBenchmarkError(
            "Engine V2 scorer thread count must equal one"
        )
    if diagnostics.preparation_status == "success":
        receipt = diagnostics.scorer_backend_receipt
        if receipt is None or receipt["backend"] != scorer_backend:
            raise PublicRedockingBenchmarkError(
                "Engine V2 scorer backend receipt contradicts execution policy"
            )
    if row.status == "failure":
        if (
            row.failure_code == "engine_v2_input_unsupported"
            and (
                diagnostics.preparation_status != "failure"
                or diagnostics.preparation_failure_code
                != "input_parse_unsupported"
            )
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 input failure contradicts preparation diagnostics"
            )
        if (
            row.failure_code == "engine_v2_pose_count_incomplete"
            and (
                diagnostics.preparation_status != "success"
                or len(diagnostics.successful_candidates) >= 5
            )
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 incomplete pose failure contradicts candidate diagnostics"
            )
        return
    if diagnostics.preparation_status != "success":
        raise PublicRedockingBenchmarkError(
            "successful Engine V2 result requires successful preparation"
        )
    ranked = diagnostics.score_ranked_candidates
    if len(ranked) < 5:
        raise PublicRedockingBenchmarkError(
            "successful Engine V2 result requires five diagnostic candidates"
        )
    for index, candidate in enumerate(ranked[:5]):
        if (
            float(candidate.rmsd_angstrom).hex()
            != row.rmsd_angstroms[index].hex()
            or candidate.geometric_valid is not row.geometric_valid[index]
            or candidate.chemical_valid is not row.chemical_valid[index]
            or candidate.pose_artifact_sha256
            != row.pose_artifact_sha256s[index]
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 ranked result contradicts candidate diagnostics"
            )


@dataclass(frozen=True, slots=True, init=False)
class VerifiedPublicRedockingCaseExecution:
    """A fresh-run row sealed with every identity needed by the report."""

    result: PublicRedockingCaseResult
    materialization_receipt_sha256: str
    implementation_sha256: str
    evaluation_pipeline_sha256: str
    execution_environment_sha256: str
    schema_id: str
    _receipt_sha256: str = field(repr=False)
    _verification_authority: object = field(repr=False)

    @classmethod
    def _from_fresh_execution(
        cls,
        *,
        result: PublicRedockingCaseResult,
        materialization_receipt_sha256: str,
        implementation_sha256: str,
        evaluation_pipeline_sha256: str,
        execution_environment_sha256: str,
        verification_authority: object,
    ) -> "VerifiedPublicRedockingCaseExecution":
        if verification_authority is not _VERIFIED_EXECUTION_AUTHORITY:
            raise TypeError(
                "VerifiedPublicRedockingCaseExecution requires fresh-run authority"
            )
        if type(result) is not PublicRedockingCaseResult:
            raise TypeError(
                "fresh execution result must be PublicRedockingCaseResult"
            )
        instance = object.__new__(cls)
        object.__setattr__(instance, "result", result)
        object.__setattr__(
            instance,
            "materialization_receipt_sha256",
            _digest(
                materialization_receipt_sha256,
                name="materialization_receipt_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "implementation_sha256",
            _digest(implementation_sha256, name="implementation_sha256"),
        )
        object.__setattr__(
            instance,
            "evaluation_pipeline_sha256",
            _digest(
                evaluation_pipeline_sha256,
                name="evaluation_pipeline_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "execution_environment_sha256",
            _digest(
                execution_environment_sha256,
                name="execution_environment_sha256",
            ),
        )
        object.__setattr__(
            instance,
            "schema_id",
            PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
        )
        object.__setattr__(
            instance,
            "_verification_authority",
            _VERIFIED_EXECUTION_AUTHORITY,
        )
        object.__setattr__(
            instance,
            "_receipt_sha256",
            _sha256(instance._projection()),
        )
        return instance

    @property
    def receipt_sha256(self) -> str:
        if self.schema_id != PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID:
            raise PublicRedockingBenchmarkError(
                "unsupported case execution schema"
            )
        if self._verification_authority is not _VERIFIED_EXECUTION_AUTHORITY:
            raise PublicRedockingBenchmarkError(
                "case execution was not sealed by the fresh-run verifier"
            )
        if type(self.result) is not PublicRedockingCaseResult:
            raise TypeError(
                "verified execution result must be PublicRedockingCaseResult"
            )
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise PublicRedockingBenchmarkError(
                "verified case execution receipt changed"
            )
        return observed

    def _projection(self) -> dict[str, object]:
        input_sha256s = dict(
            zip(
                (role for role, _ in _CASE_ARTIFACT_ROLES),
                self.result.input_artifact_sha256s,
                strict=True,
            )
        )
        return {
            "schema_id": self.schema_id,
            "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
            "archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
            "source_ids_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
            "command": list(self.result.execution_command),
            "execution_policy": _execution_policy_mapping(
                self.result.execution_policy
            ),
            "input_sha256s": input_sha256s,
            "materialization_receipt_sha256": (
                self.materialization_receipt_sha256
            ),
            "implementation_sha256": self.implementation_sha256,
            "evaluation_pipeline_sha256": self.evaluation_pipeline_sha256,
            "execution_environment_sha256": (
                self.execution_environment_sha256
            ),
            "cache_read_allowed": False,
            "fresh_execution": True,
            "result": self.result.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class PublicRedockingMetricEstimate:
    engine_id: str
    metric_id: str
    analysis_scope: str
    subgroup: str
    case_count: int
    value: float
    confidence_interval_low: float
    confidence_interval_high: float
    paired_baseline_engine_id: str = ""

    def __post_init__(self) -> None:
        if self.engine_id not in PUBLIC_REDOCKING_PRIMARY_ENGINES:
            raise PublicRedockingBenchmarkError("metric engine_id is invalid")
        if self.analysis_scope not in PUBLIC_REDOCKING_ANALYSIS_SCOPES:
            raise PublicRedockingBenchmarkError("metric analysis_scope is invalid")
        if not self.metric_id or not self.subgroup:
            raise PublicRedockingBenchmarkError(
                "metric_id and subgroup must be non-empty"
            )
        if type(self.case_count) is not int or self.case_count < 1:
            raise PublicRedockingBenchmarkError("metric case_count must be positive")
        value = _finite(self.value, name="metric value")
        low = _finite(self.confidence_interval_low, name="confidence interval")
        high = _finite(self.confidence_interval_high, name="confidence interval")
        if low > high:
            raise PublicRedockingBenchmarkError(
                "confidence interval low cannot exceed high"
            )
        baseline = str(self.paired_baseline_engine_id or "").strip().lower()
        if baseline and baseline not in {"vina", "gnina"}:
            raise PublicRedockingBenchmarkError("paired baseline is invalid")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "confidence_interval_low", low)
        object.__setattr__(self, "confidence_interval_high", high)
        object.__setattr__(self, "paired_baseline_engine_id", baseline)

    def to_dict(self) -> dict[str, object]:
        return {
            "engine_id": self.engine_id,
            "metric_id": self.metric_id,
            "analysis_scope": self.analysis_scope,
            "subgroup": self.subgroup,
            "case_count": self.case_count,
            "value": self.value,
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
            "paired_baseline_engine_id": self.paired_baseline_engine_id,
        }


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _bootstrap_interval(
    values: Sequence[float],
    *,
    statistic: Callable[[Sequence[float]], float],
    policy: PublicRedockingEvaluationPolicy,
    identity: str,
) -> tuple[float, float, float]:
    observed = float(statistic(values))
    seed_digest = hashlib.sha256(identity.encode("ascii")).digest()
    seed = policy.bootstrap_seed ^ int.from_bytes(seed_digest[:8], "big")
    generator = random.Random(seed)
    size = len(values)
    estimates = [
        float(statistic([values[generator.randrange(size)] for _ in range(size)]))
        for _ in range(policy.bootstrap_samples)
    ]
    tail = (1.0 - policy.confidence_level) / 2.0
    return observed, _percentile(estimates, tail), _percentile(estimates, 1.0 - tail)


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values)


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def _metric(
    *,
    engine_id: str,
    metric_id: str,
    analysis_scope: str,
    subgroup: str,
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float],
    policy: PublicRedockingEvaluationPolicy,
    baseline: str = "",
) -> PublicRedockingMetricEstimate:
    value, low, high = _bootstrap_interval(
        values,
        statistic=statistic,
        policy=policy,
        identity=(f"{analysis_scope}:{engine_id}:{baseline}:{metric_id}:{subgroup}"),
    )
    return PublicRedockingMetricEstimate(
        engine_id=engine_id,
        metric_id=metric_id,
        analysis_scope=analysis_scope,
        subgroup=subgroup,
        case_count=len(values),
        value=value,
        confidence_interval_low=low,
        confidence_interval_high=high,
        paired_baseline_engine_id=baseline,
    )


@dataclass(frozen=True, slots=True)
class PublicRedockingBenchmarkReport:
    cohort: FrozenPublicRedockingCohort
    policy: PublicRedockingEvaluationPolicy
    profiles: tuple[PublicRedockingCaseProfile, ...]
    materializations: tuple[VerifiedCaseMaterialization, ...]
    engine_identities: tuple[PublicRedockingEngineIdentity, ...]
    executions: tuple[VerifiedPublicRedockingCaseExecution, ...]
    metrics: tuple[PublicRedockingMetricEstimate, ...]
    schema_id: str = PUBLIC_REDOCKING_REPORT_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REDOCKING_REPORT_SCHEMA_ID:
            raise PublicRedockingBenchmarkError("unsupported report schema")
        if not isinstance(self.cohort, FrozenPublicRedockingCohort):
            raise TypeError("cohort must be FrozenPublicRedockingCohort")
        if not isinstance(self.policy, PublicRedockingEvaluationPolicy):
            raise TypeError("policy must be PublicRedockingEvaluationPolicy")
        profiles = tuple(self.profiles)
        materializations = tuple(self.materializations)
        identities = tuple(self.engine_identities)
        executions = tuple(self.executions)
        if any(
            type(execution) is not VerifiedPublicRedockingCaseExecution
            for execution in executions
        ):
            raise TypeError(
                "executions must be VerifiedPublicRedockingCaseExecution receipts"
            )
        execution_receipt_sha256s = tuple(
            execution.receipt_sha256 for execution in executions
        )
        if len(set(execution_receipt_sha256s)) != len(executions):
            raise PublicRedockingBenchmarkError(
                "verified case execution receipts must be unique"
            )
        rows = tuple(execution.result for execution in executions)
        metrics = tuple(self.metrics)
        if tuple(profile.case_id for profile in profiles) != self.cohort.case_ids:
            raise PublicRedockingBenchmarkError(
                "profiles must cover every frozen case in exact order"
            )
        if profiles != frozen_public_redocking_profiles():
            raise PublicRedockingBenchmarkError(
                "profiles must match the frozen source-derived values"
            )
        if (
            any(
                type(row) is not VerifiedCaseMaterialization for row in materializations
            )
            or tuple(row.case_id for row in materializations) != self.cohort.case_ids
        ):
            raise TypeError(
                "materializations must be ordered VerifiedCaseMaterialization rows"
            )
        if len({row.receipt_sha256 for row in materializations}) != len(
            materializations
        ):
            raise PublicRedockingBenchmarkError(
                "verified materialization receipts must be unique"
            )
        if any(
            row.receipt_sha256
            != frozen_public_redocking_materialization_receipt_sha256(row.case_id)
            for row in materializations
        ):
            raise PublicRedockingBenchmarkError(
                "verified materializations do not match per-case frozen receipts"
            )
        if (
            _sha256([row.to_dict() for row in materializations])
            != PUBLIC_REDOCKING_MATERIALIZATIONS_SHA256
        ):
            raise PublicRedockingBenchmarkError(
                "verified materializations do not match the frozen archive receipt set"
            )
        if tuple(identity.engine_id for identity in identities) != (
            PUBLIC_REDOCKING_PRIMARY_ENGINES
        ):
            raise PublicRedockingBenchmarkError(
                "engine identities must be ordered engine_v2, vina, gnina"
            )
        if len({identity.evaluation_pipeline_sha256 for identity in identities}) != 1:
            raise PublicRedockingBenchmarkError(
                "all engines must use one evaluation pipeline"
            )
        expected_rows = tuple(
            (engine_id, case_id)
            for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
            for case_id in self.cohort.case_ids
        )
        if tuple((row.engine_id, row.case_id) for row in rows) != expected_rows:
            raise PublicRedockingBenchmarkError(
                "rows must retain one ordered row for every engine/case"
            )
        if any(
            row.status == "failure"
            and row.failure_code not in _PUBLIC_REDOCKING_FAILURE_CODES[row.engine_id]
            for row in rows
        ):
            raise PublicRedockingBenchmarkError(
                "failure rows must use an engine-derived frozen failure code"
            )
        for row in rows:
            if row.engine_id == "engine_v2":
                _validate_engine_v2_result_diagnostics(row)
            elif row.engine_v2_diagnostics is not None:
                raise PublicRedockingBenchmarkError(
                    "external rows cannot retain Engine V2 diagnostics"
                )
        profile_map = {profile.case_id: profile for profile in profiles}
        materialization_map = {
            materialization.case_id: materialization
            for materialization in materializations
        }
        row_map = {(row.engine_id, row.case_id): row for row in rows}
        engine_v2_policies = {
            row.execution_policy for row in rows if row.engine_id == "engine_v2"
        }
        if len(engine_v2_policies) != 1:
            raise PublicRedockingBenchmarkError(
                "Engine V2 rows must use one execution policy"
            )
        engine_v2_policy = _execution_policy_mapping(next(iter(engine_v2_policies)))
        required_engine_v2_policy = {
            "cpu_count",
            "scorer_backend",
            "scorer_thread_count",
            "torch_intraop_threads",
            "torch_interop_threads",
            "torch_version",
        }
        if set(engine_v2_policy) != required_engine_v2_policy:
            raise PublicRedockingBenchmarkError(
                "Engine V2 row policy fields contradict the report policy"
            )
        for field_name in (
            "cpu_count",
            "scorer_thread_count",
            "torch_intraop_threads",
            "torch_interop_threads",
        ):
            if type(engine_v2_policy[field_name]) is not int:
                raise PublicRedockingBenchmarkError(
                    "Engine V2 row policy integer fields must be integers"
                )
        torch_version = engine_v2_policy["torch_version"]
        if (
            engine_v2_policy.get("cpu_count") != self.policy.cpu_count
            or engine_v2_policy.get("torch_intraop_threads") != 1
            or engine_v2_policy.get("torch_interop_threads") != 1
            or engine_v2_policy.get("scorer_thread_count") != 1
            or engine_v2_policy.get("scorer_backend")
            not in {"python_reference", "rust_cpu_required"}
            or type(torch_version) is not str
            or torch_version not in PUBLIC_REDOCKING_ALLOWED_TORCH_VERSIONS
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 row policy contradicts the report policy"
            )
        engine_v2_identity = identities[0]
        if (
            _command_option_value(
                engine_v2_identity.command,
                "--torch-version",
            )
            != torch_version
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 Torch policy contradicts its identity"
            )
        expected_external_policy = {
            "cpu_count": self.policy.cpu_count,
            "timeout_seconds": self.policy.external_timeout_seconds,
        }
        for engine_id in ("vina", "gnina"):
            policies = {
                row.execution_policy for row in rows if row.engine_id == engine_id
            }
            if len(policies) != 1:
                raise PublicRedockingBenchmarkError(
                    f"{engine_id} row policy contradicts the report policy"
                )
            external_policy = _execution_policy_mapping(next(iter(policies)))
            if (
                set(external_policy) != set(expected_external_policy)
                or any(
                    type(external_policy[field_name]) is not int
                    for field_name in expected_external_policy
                )
                or external_policy != expected_external_policy
            ):
                raise PublicRedockingBenchmarkError(
                    f"{engine_id} row policy contradicts the report policy"
                )
        identity_map = {identity.engine_id: identity for identity in identities}
        if len({row.execution_environment_sha256 for row in executions}) != 1:
            raise PublicRedockingBenchmarkError(
                "all case executions must use one execution environment"
            )
        for execution in executions:
            result = execution.result
            identity = identity_map[result.engine_id]
            materialization = materialization_map[result.case_id]
            if execution.materialization_receipt_sha256 != (
                materialization.receipt_sha256
            ):
                raise PublicRedockingBenchmarkError(
                    "case execution does not bind the verified materialization"
                )
            if execution.implementation_sha256 != identity.implementation_sha256:
                raise PublicRedockingBenchmarkError(
                    "case execution implementation contradicts its engine identity"
                )
            if execution.evaluation_pipeline_sha256 != (
                identity.evaluation_pipeline_sha256
            ):
                raise PublicRedockingBenchmarkError(
                    "case execution evaluator contradicts its engine identity"
                )
        if (
            identities[1].implementation_sha256 != identities[2].implementation_sha256
            or identities[1].command[0] != identities[2].command[0]
        ):
            raise PublicRedockingBenchmarkError(
                "Vina and GNINA must use one identical staged binary"
            )
        command_run_roots = {
            _validate_engine_commands(
                identity_map[engine_id],
                tuple(row for row in rows if row.engine_id == engine_id),
                policy=self.policy,
            )
            for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
        }
        if len(command_run_roots) != 1:
            raise PublicRedockingBenchmarkError(
                "all engine commands must share one canonical run root"
            )
        for case_id in self.cohort.case_ids:
            case_rows = tuple(
                row_map[(engine_id, case_id)]
                for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
            )
            materialization = materialization_map[case_id]
            if len({row.input_artifact_sha256s for row in case_rows}) != 1:
                raise PublicRedockingBenchmarkError(
                    "engines must use identical source artifacts per case"
                )
            if case_rows[0].input_artifact_sha256s != (
                materialization.input_artifact_sha256s
            ):
                raise PublicRedockingBenchmarkError(
                    "result inputs do not match the verified case materialization"
                )
            if materialization.native_artifact_sha256 != (
                profile_map[case_id].ligand_artifact_sha256
            ):
                raise PublicRedockingBenchmarkError(
                    "verified native ligand is not the frozen profile artifact"
                )
            case_seeds = tuple(
                _command_seed(row.execution_command) for row in case_rows
            )
            if (
                len(set(case_seeds)) != 1
                or case_seeds[0] != materialization.frozen_case_seed
                or case_seeds[0] != frozen_public_redocking_case_seed(case_id)
            ):
                raise PublicRedockingBenchmarkError(
                    "engine commands must use the identical frozen case seed"
                )
        expected_metrics = _derive_public_redocking_metrics(
            profiles,
            identities,
            rows,
            cohort=self.cohort,
            policy=self.policy,
        )
        if metrics and metrics != expected_metrics:
            raise PublicRedockingBenchmarkError(
                "report metrics do not match the retained result rows"
            )
        metrics = expected_metrics
        object.__setattr__(self, "profiles", profiles)
        object.__setattr__(self, "materializations", materializations)
        object.__setattr__(self, "engine_identities", identities)
        object.__setattr__(self, "executions", executions)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    @property
    def rows(self) -> tuple[PublicRedockingCaseResult, ...]:
        return tuple(execution.result for execution in self.executions)

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise PublicRedockingBenchmarkError("redocking report state changed")
        return observed

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "cohort_fingerprint_sha256": self.cohort.fingerprint_sha256,
            "policy_fingerprint_sha256": self.policy.fingerprint_sha256,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "materializations": [
                materialization.to_dict() for materialization in self.materializations
            ],
            "engine_identities": [
                identity.to_dict() for identity in self.engine_identities
            ],
            "execution_receipts": [
                execution.to_dict() for execution in self.executions
            ],
            "rows": [row.to_dict() for row in self.rows],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "case_count": len(self.cohort.case_ids),
            "row_count": len(self.rows),
            "engineering_smoke_case_count": len(
                PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
            ),
            "engineering_smoke_case_ids": list(
                PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
            ),
            "contaminated_development_case_count": len(
                PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS
            ),
            "contaminated_development_case_ids_sha256": _sha256(
                list(PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS)
            ),
            "primary_blind_holdout_case_count": len(
                PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
            ),
            "primary_blind_holdout_case_ids_sha256": _sha256(
                list(PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS)
            ),
            "supplementary_descriptive_case_count": len(self.cohort.case_ids),
            "primary_metrics_exclude_engineering_smoke": True,
            "primary_metrics_exclude_contaminated_development": False,
            "historical_298_holdout_claim_invalidated": True,
            "historical_300_development_only": True,
            "all_300_metrics_are_supplementary_descriptive": True,
            "internal_provisional_evidence_only": True,
            "external_independent_review_complete": False,
            "full_failure_denominator_retained": True,
            "policy": self.policy.to_dict(),
            "same_ranked_pose_count": True,
            "exact_case_commands_bound": True,
            "same_pocket_source": True,
            "same_pocket_geometry": False,
            "same_search_effort_budget": False,
            "search_effort_comparable": False,
            "runtime_boundary_comparable": False,
            "cpu_limit_comparable": True,
            "bootstrap_confidence_intervals": True,
            "benchmark_executed": True,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


def _derive_engine_v2_diagnostic_metrics(
    rows: Sequence[PublicRedockingCaseResult],
    *,
    policy: PublicRedockingEvaluationPolicy,
    analysis_scope: str,
    subgroup: str,
) -> tuple[PublicRedockingMetricEstimate, ...]:
    selected = tuple(rows)
    diagnostics = tuple(row.engine_v2_diagnostics for row in selected)
    if (
        not selected
        or any(row.engine_id != "engine_v2" for row in selected)
        or any(type(value) is not PublicRedockingEngineV2Diagnostics for value in diagnostics)
    ):
        raise PublicRedockingBenchmarkError(
            "Engine V2 diagnostic metrics require typed Engine V2 rows"
        )

    def successful(value: PublicRedockingEngineV2Diagnostics):
        return value.successful_candidates

    def ranked(value: PublicRedockingEngineV2Diagnostics):
        return value.score_ranked_candidates

    threshold = policy.rmsd_threshold_angstrom
    preparation = [
        float(value.preparation_status == "success") for value in diagnostics
    ]
    charge_coverage = [
        float(value.charge_coverage_complete) for value in diagnostics
    ]
    hbond_feature_coverage = [
        float(value.hbond_feature_covered) for value in diagnostics
    ]
    receptor_ion_proxy_usage = [
        float(value.receptor_ion_proxy_count > 0) for value in diagnostics
    ]
    candidate_generation_coverage = [
        len(successful(value)) / PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        for value in diagnostics
    ]
    proposal_oracle_recovery = [
        float(
            any(
                float(candidate.rmsd_angstrom) <= threshold
                for candidate in successful(value)
            )
        )
        for value in diagnostics
    ]
    valid_proposal_oracle_recovery = [
        float(
            any(
                float(candidate.rmsd_angstrom) <= threshold
                and candidate.geometric_valid
                and candidate.chemical_valid
                for candidate in successful(value)
            )
        )
        for value in diagnostics
    ]
    top1_scoring_regret_events: list[float] = []
    top5_selection_regret_events: list[float] = []
    top1_hbond_realization: list[float] = []
    top1_regret_angstrom: list[float] = []
    top5_regret_angstrom: list[float] = []
    for value in diagnostics:
        candidates = successful(value)
        score_ranked = ranked(value)
        oracle = (
            None
            if not candidates
            else min(float(candidate.rmsd_angstrom) for candidate in candidates)
        )
        top1 = (
            None
            if not score_ranked
            else float(score_ranked[0].rmsd_angstrom)
        )
        top5 = (
            None
            if len(score_ranked) < 5
            else min(
                float(candidate.rmsd_angstrom)
                for candidate in score_ranked[:5]
            )
        )
        top1_scoring_regret_events.append(
            float(
                oracle is not None
                and oracle <= threshold
                and (top1 is None or top1 > threshold)
            )
        )
        top5_selection_regret_events.append(
            float(
                oracle is not None
                and oracle <= threshold
                and (top5 is None or top5 > threshold)
            )
        )
        top1_hbond_realization.append(
            float(
                bool(score_ranked)
                and int(score_ranked[0].hbond_count) > 0
            )
        )
        if oracle is not None and top1 is not None:
            top1_regret_angstrom.append(top1 - oracle)
        if oracle is not None and top5 is not None:
            top5_regret_angstrom.append(top5 - oracle)

    metrics = [
        _metric(
            engine_id="engine_v2",
            metric_id=metric_id,
            analysis_scope=analysis_scope,
            subgroup=subgroup,
            values=values,
            statistic=_mean,
            policy=policy,
        )
        for metric_id, values in (
            ("preparation_success_rate", preparation),
            ("complete_partial_charge_coverage_rate", charge_coverage),
            ("hbond_feature_coverage_rate", hbond_feature_coverage),
            ("receptor_ion_proxy_usage_rate", receptor_ion_proxy_usage),
            (
                "candidate_generation_coverage_rate",
                candidate_generation_coverage,
            ),
            ("proposal_oracle_recovery_rate", proposal_oracle_recovery),
            (
                "valid_proposal_oracle_recovery_rate",
                valid_proposal_oracle_recovery,
            ),
            (
                "top1_scoring_regret_event_rate",
                top1_scoring_regret_events,
            ),
            (
                "top5_selection_regret_event_rate",
                top5_selection_regret_events,
            ),
            ("top1_hbond_realization_rate", top1_hbond_realization),
        )
    ]
    for metric_id, values in (
        ("top1_scoring_regret_median_angstrom", top1_regret_angstrom),
        ("top5_selection_regret_median_angstrom", top5_regret_angstrom),
    ):
        if values:
            metrics.append(
                _metric(
                    engine_id="engine_v2",
                    metric_id=metric_id,
                    analysis_scope=analysis_scope,
                    subgroup=subgroup,
                    values=values,
                    statistic=_median,
                    policy=policy,
                )
            )
    for term_name in _SCORER_TERM_NAMES:
        per_case_medians = [
            statistics.median(
                float.fromhex(candidate.score_term_binary64_hex[term_name])
                for candidate in successful(value)
            )
            for value in diagnostics
            if successful(value)
        ]
        if per_case_medians:
            metrics.append(
                _metric(
                    engine_id="engine_v2",
                    metric_id=f"candidate_term_{term_name}_median",
                    analysis_scope=analysis_scope,
                    subgroup=subgroup,
                    values=per_case_medians,
                    statistic=_median,
                    policy=policy,
                )
            )
    for mode in PUBLIC_REDOCKING_PROPOSAL_MODES:
        mode_subgroup = f"{subgroup}:proposal_mode={mode}"
        allocation_values: list[float] = []
        native_like_values: list[float] = []
        valid_values: list[float] = []
        duplicate_values: list[float] = []
        oracle_contribution_values: list[float] = []
        refinement_reduction_values: list[float] = []
        for value in diagnostics:
            allocated = tuple(
                candidate
                for candidate in value.candidates
                if candidate.proposal_mode == mode
            )
            allocation_values.append(len(allocated) / value.candidate_budget)
            mode_success = tuple(
                candidate
                for candidate in allocated
                if candidate.status == "success"
            )
            if not mode_success:
                continue
            native_like_values.append(
                sum(
                    float(candidate.rmsd_angstrom) <= threshold
                    for candidate in mode_success
                )
                / len(mode_success)
            )
            valid_values.append(
                sum(
                    candidate.geometric_valid and candidate.chemical_valid
                    for candidate in mode_success
                )
                / len(mode_success)
            )
            coordinate_counts = Counter(
                candidate.coordinate_fingerprint_sha256
                for candidate in mode_success
            )
            duplicate_values.append(
                sum(
                    coordinate_counts[candidate.coordinate_fingerprint_sha256] > 1
                    for candidate in mode_success
                )
                / len(mode_success)
            )
            oracle_contribution_values.append(
                float(
                    any(
                        float(candidate.rmsd_angstrom) <= threshold
                        for candidate in mode_success
                    )
                )
            )
            refinement_rows = tuple(
                candidate
                for candidate in mode_success
                if candidate.refinement_receipt_sha256
            )
            if refinement_rows:
                refinement_reduction_values.append(
                    sum(
                        float.fromhex(
                            candidate.refinement_final_penalty_binary64_hex
                        )
                        < float.fromhex(
                            candidate.refinement_initial_penalty_binary64_hex
                        )
                        for candidate in refinement_rows
                    )
                    / len(refinement_rows)
                )
        for metric_id, values in (
            ("proposal_mode_allocation_rate", allocation_values),
            ("proposal_mode_native_like_candidate_rate", native_like_values),
            ("proposal_mode_valid_candidate_rate", valid_values),
            ("proposal_mode_exact_duplicate_candidate_rate", duplicate_values),
            ("proposal_mode_oracle_contribution_rate", oracle_contribution_values),
            ("proposal_mode_refinement_penalty_reduction_rate", refinement_reduction_values),
        ):
            if values:
                metrics.append(
                    _metric(
                        engine_id="engine_v2",
                        metric_id=metric_id,
                        analysis_scope=analysis_scope,
                        subgroup=mode_subgroup,
                        values=values,
                        statistic=_mean,
                        policy=policy,
                    )
                )
    for check_id in (
        *PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
        *PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
    ):
        failure_rates = [
            sum(
                check_id in candidate.posebusters_failed_check_ids
                for candidate in successful(value)
            )
            / len(successful(value))
            for value in diagnostics
            if successful(value)
        ]
        if failure_rates:
            metrics.append(
                _metric(
                    engine_id="engine_v2",
                    metric_id=f"posebusters_{check_id}_failure_rate",
                    analysis_scope=analysis_scope,
                    subgroup=subgroup,
                    values=failure_rates,
                    statistic=_mean,
                    policy=policy,
                )
            )
    return tuple(metrics)


def _derive_scope_all_metrics(
    row_map: dict[tuple[str, str], PublicRedockingCaseResult],
    *,
    policy: PublicRedockingEvaluationPolicy,
    analysis_scope: str,
    case_ids: Sequence[str],
) -> tuple[PublicRedockingMetricEstimate, ...]:
    metrics: list[PublicRedockingMetricEstimate] = []
    for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
        selected = [row_map[(engine_id, case_id)] for case_id in case_ids]
        metrics.extend(
            (
                _metric(
                    engine_id=engine_id,
                    metric_id="full_case_failure_rate",
                    analysis_scope=analysis_scope,
                    subgroup="all",
                    values=[float(row.status == "failure") for row in selected],
                    statistic=_mean,
                    policy=policy,
                ),
                _metric(
                    engine_id=engine_id,
                    metric_id="runtime_median_seconds",
                    analysis_scope=analysis_scope,
                    subgroup="all",
                    values=[row.runtime_seconds for row in selected],
                    statistic=_median,
                    policy=policy,
                ),
            )
        )
        if engine_id == "engine_v2":
            metrics.extend(
                _derive_engine_v2_diagnostic_metrics(
                    selected,
                    policy=policy,
                    analysis_scope=analysis_scope,
                    subgroup="all",
                )
            )
        for top_k in policy.top_ks:
            metrics.extend(
                (
                    _metric(
                        engine_id=engine_id,
                        metric_id=f"top{top_k}_rmsd_success_rate",
                        analysis_scope=analysis_scope,
                        subgroup="all",
                        values=[
                            row.recovery(
                                top_k,
                                policy.rmsd_threshold_angstrom,
                            )
                            for row in selected
                        ],
                        statistic=_mean,
                        policy=policy,
                    ),
                    _metric(
                        engine_id=engine_id,
                        metric_id=(f"top{top_k}_valid_pose_success_rate"),
                        analysis_scope=analysis_scope,
                        subgroup="all",
                        values=[
                            row.valid_recovery(
                                top_k,
                                policy.rmsd_threshold_angstrom,
                            )
                            for row in selected
                        ],
                        statistic=_mean,
                        policy=policy,
                    ),
                )
            )
        metrics.extend(
            (
                _metric(
                    engine_id=engine_id,
                    metric_id="top1_geometric_validity_rate",
                    analysis_scope=analysis_scope,
                    subgroup="all",
                    values=[
                        float(row.status == "success" and row.geometric_valid[0])
                        for row in selected
                    ],
                    statistic=_mean,
                    policy=policy,
                ),
                _metric(
                    engine_id=engine_id,
                    metric_id="top1_chemical_validity_rate",
                    analysis_scope=analysis_scope,
                    subgroup="all",
                    values=[
                        float(row.status == "success" and row.chemical_valid[0])
                        for row in selected
                    ],
                    statistic=_mean,
                    policy=policy,
                ),
            )
        )

    for baseline in ("vina", "gnina"):
        failure_deltas = [
            float(row_map[("engine_v2", case_id)].status == "failure")
            - float(row_map[(baseline, case_id)].status == "failure")
            for case_id in case_ids
        ]
        runtime_deltas = [
            (
                row_map[("engine_v2", case_id)].runtime_seconds
                - row_map[(baseline, case_id)].runtime_seconds
            )
            for case_id in case_ids
        ]
        metrics.extend(
            (
                _metric(
                    engine_id="engine_v2",
                    metric_id="full_case_failure_rate_paired_delta",
                    analysis_scope=analysis_scope,
                    subgroup="all",
                    values=failure_deltas,
                    statistic=_mean,
                    policy=policy,
                    baseline=baseline,
                ),
                _metric(
                    engine_id="engine_v2",
                    metric_id="runtime_seconds_paired_median_delta",
                    analysis_scope=analysis_scope,
                    subgroup="all",
                    values=runtime_deltas,
                    statistic=_median,
                    policy=policy,
                    baseline=baseline,
                ),
            )
        )
        for top_k in policy.top_ks:
            recovery_deltas = [
                (
                    row_map[("engine_v2", case_id)].recovery(
                        top_k,
                        policy.rmsd_threshold_angstrom,
                    )
                    - row_map[(baseline, case_id)].recovery(
                        top_k,
                        policy.rmsd_threshold_angstrom,
                    )
                )
                for case_id in case_ids
            ]
            valid_recovery_deltas = [
                (
                    row_map[("engine_v2", case_id)].valid_recovery(
                        top_k,
                        policy.rmsd_threshold_angstrom,
                    )
                    - row_map[(baseline, case_id)].valid_recovery(
                        top_k,
                        policy.rmsd_threshold_angstrom,
                    )
                )
                for case_id in case_ids
            ]
            metrics.extend(
                (
                    _metric(
                        engine_id="engine_v2",
                        metric_id=(f"top{top_k}_rmsd_success_rate_paired_delta"),
                        analysis_scope=analysis_scope,
                        subgroup="all",
                        values=recovery_deltas,
                        statistic=_mean,
                        policy=policy,
                        baseline=baseline,
                    ),
                    _metric(
                        engine_id="engine_v2",
                        metric_id=(f"top{top_k}_valid_pose_success_rate_paired_delta"),
                        analysis_scope=analysis_scope,
                        subgroup="all",
                        values=valid_recovery_deltas,
                        statistic=_mean,
                        policy=policy,
                        baseline=baseline,
                    ),
                )
            )
    return tuple(metrics)


def _derive_public_redocking_metrics(
    profiles: Sequence[PublicRedockingCaseProfile],
    engine_identities: Sequence[PublicRedockingEngineIdentity],
    rows: Sequence[PublicRedockingCaseResult],
    *,
    cohort: FrozenPublicRedockingCohort | None = None,
    policy: PublicRedockingEvaluationPolicy | None = None,
) -> tuple[PublicRedockingMetricEstimate, ...]:
    """Derive exact metrics from the failure-complete result ledger."""

    active_cohort = frozen_public_redocking_cohort() if cohort is None else cohort
    active_policy = PublicRedockingEvaluationPolicy() if policy is None else policy
    profile_rows = tuple(profiles)
    identity_rows = tuple(engine_identities)
    result_rows = tuple(rows)
    profile_map = {profile.case_id: profile for profile in profile_rows}
    row_map = {(row.engine_id, row.case_id): row for row in result_rows}
    if len(profile_map) != len(profile_rows) or len(row_map) != len(result_rows):
        raise PublicRedockingBenchmarkError("profiles and result rows must be unique")
    expected_profiles = active_cohort.case_ids
    if tuple(profile.case_id for profile in profile_rows) != expected_profiles:
        raise PublicRedockingBenchmarkError(
            "profiles must cover every frozen case in exact order"
        )
    if profile_rows != frozen_public_redocking_profiles():
        raise PublicRedockingBenchmarkError(
            "profiles must match the frozen source-derived values"
        )
    size_subgroups = {profile.size_subgroup for profile in profile_rows}
    rotor_subgroups = {profile.rotor_subgroup for profile in profile_rows}
    ring_subgroups = {profile.ring_subgroup for profile in profile_rows}
    if size_subgroups != set(PUBLIC_REDOCKING_SIZE_SUBGROUPS) or rotor_subgroups != set(
        PUBLIC_REDOCKING_ROTOR_SUBGROUPS
    ) or ring_subgroups != set(PUBLIC_REDOCKING_RING_SUBGROUPS):
        raise PublicRedockingBenchmarkError(
            "profiles must represent every frozen size, rotor, and ring subgroup"
        )
    if tuple(identity.engine_id for identity in identity_rows) != (
        PUBLIC_REDOCKING_PRIMARY_ENGINES
    ):
        raise PublicRedockingBenchmarkError(
            "engine identities must be ordered engine_v2, vina, gnina"
        )
    expected_rows = tuple(
        (engine_id, case_id)
        for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
        for case_id in active_cohort.case_ids
    )
    if tuple((row.engine_id, row.case_id) for row in result_rows) != expected_rows:
        raise PublicRedockingBenchmarkError(
            "results must cover every engine/case pair in exact order"
        )

    metric_case_ids = PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
    subgroup_ids: dict[str, tuple[str, ...]] = {
        "all": metric_case_ids,
    }
    for attribute in ("size_subgroup", "rotor_subgroup", "ring_subgroup"):
        for subgroup in sorted(
            {getattr(profile, attribute) for profile in profile_rows}
        ):
            subgroup_ids[subgroup] = tuple(
                profile.case_id
                for profile in profile_rows
                if (
                    profile.case_id in metric_case_ids
                    and getattr(profile, attribute) == subgroup
                )
            )

    metrics: list[PublicRedockingMetricEstimate] = []
    for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
        engine_rows = {
            case_id: row_map[(engine_id, case_id)] for case_id in active_cohort.case_ids
        }
        for subgroup, case_ids in subgroup_ids.items():
            selected = [engine_rows[case_id] for case_id in case_ids]
            failure_values = [float(row.status == "failure") for row in selected]
            runtime_values = [row.runtime_seconds for row in selected]
            metrics.extend(
                (
                    _metric(
                        engine_id=engine_id,
                        metric_id="full_case_failure_rate",
                        analysis_scope="primary_blind_holdout",
                        subgroup=subgroup,
                        values=failure_values,
                        statistic=_mean,
                        policy=active_policy,
                    ),
                    _metric(
                        engine_id=engine_id,
                        metric_id="runtime_median_seconds",
                        analysis_scope="primary_blind_holdout",
                        subgroup=subgroup,
                        values=runtime_values,
                        statistic=_median,
                        policy=active_policy,
                    ),
                )
            )
            for top_k in active_policy.top_ks:
                recovery = [
                    row.recovery(top_k, active_policy.rmsd_threshold_angstrom)
                    for row in selected
                ]
                valid_recovery = [
                    row.valid_recovery(
                        top_k,
                        active_policy.rmsd_threshold_angstrom,
                    )
                    for row in selected
                ]
                metrics.extend(
                    (
                        _metric(
                            engine_id=engine_id,
                            metric_id=f"top{top_k}_rmsd_success_rate",
                            analysis_scope="primary_blind_holdout",
                            subgroup=subgroup,
                            values=recovery,
                            statistic=_mean,
                            policy=active_policy,
                        ),
                        _metric(
                            engine_id=engine_id,
                            metric_id=f"top{top_k}_valid_pose_success_rate",
                            analysis_scope="primary_blind_holdout",
                            subgroup=subgroup,
                            values=valid_recovery,
                            statistic=_mean,
                            policy=active_policy,
                        ),
                    )
                )
            top1_geometric = [
                float(row.status == "success" and row.geometric_valid[0])
                for row in selected
            ]
            top1_chemical = [
                float(row.status == "success" and row.chemical_valid[0])
                for row in selected
            ]
            metrics.extend(
                (
                    _metric(
                        engine_id=engine_id,
                        metric_id="top1_geometric_validity_rate",
                        analysis_scope="primary_blind_holdout",
                        subgroup=subgroup,
                        values=top1_geometric,
                        statistic=_mean,
                        policy=active_policy,
                    ),
                    _metric(
                        engine_id=engine_id,
                        metric_id="top1_chemical_validity_rate",
                        analysis_scope="primary_blind_holdout",
                        subgroup=subgroup,
                        values=top1_chemical,
                        statistic=_mean,
                        policy=active_policy,
                    ),
                )
            )
            if engine_id == "engine_v2":
                metrics.extend(
                    _derive_engine_v2_diagnostic_metrics(
                        selected,
                        policy=active_policy,
                        analysis_scope="primary_blind_holdout",
                        subgroup=subgroup,
                    )
                )

    for baseline in ("vina", "gnina"):
        engine_failures = [
            float(row_map[("engine_v2", case_id)].status == "failure")
            for case_id in metric_case_ids
        ]
        baseline_failures = [
            float(row_map[(baseline, case_id)].status == "failure")
            for case_id in metric_case_ids
        ]
        failure_deltas = [
            engine - external
            for engine, external in zip(
                engine_failures,
                baseline_failures,
                strict=True,
            )
        ]
        runtime_deltas = [
            (
                row_map[("engine_v2", case_id)].runtime_seconds
                - row_map[(baseline, case_id)].runtime_seconds
            )
            for case_id in metric_case_ids
        ]
        metrics.extend(
            (
                _metric(
                    engine_id="engine_v2",
                    metric_id="full_case_failure_rate_paired_delta",
                    analysis_scope="primary_blind_holdout",
                    subgroup="all",
                    values=failure_deltas,
                    statistic=_mean,
                    policy=active_policy,
                    baseline=baseline,
                ),
                _metric(
                    engine_id="engine_v2",
                    metric_id="runtime_seconds_paired_median_delta",
                    analysis_scope="primary_blind_holdout",
                    subgroup="all",
                    values=runtime_deltas,
                    statistic=_median,
                    policy=active_policy,
                    baseline=baseline,
                ),
            )
        )
        for top_k in active_policy.top_ks:
            engine_values = [
                row_map[("engine_v2", case_id)].recovery(
                    top_k,
                    active_policy.rmsd_threshold_angstrom,
                )
                for case_id in metric_case_ids
            ]
            baseline_values = [
                row_map[(baseline, case_id)].recovery(
                    top_k,
                    active_policy.rmsd_threshold_angstrom,
                )
                for case_id in metric_case_ids
            ]
            deltas = [
                engine - external
                for engine, external in zip(
                    engine_values,
                    baseline_values,
                    strict=True,
                )
            ]
            metrics.append(
                _metric(
                    engine_id="engine_v2",
                    metric_id=f"top{top_k}_rmsd_success_rate_paired_delta",
                    analysis_scope="primary_blind_holdout",
                    subgroup="all",
                    values=deltas,
                    statistic=_mean,
                    policy=active_policy,
                    baseline=baseline,
                )
            )
            engine_valid_values = [
                row_map[("engine_v2", case_id)].valid_recovery(
                    top_k,
                    active_policy.rmsd_threshold_angstrom,
                )
                for case_id in metric_case_ids
            ]
            baseline_valid_values = [
                row_map[(baseline, case_id)].valid_recovery(
                    top_k,
                    active_policy.rmsd_threshold_angstrom,
                )
                for case_id in metric_case_ids
            ]
            valid_deltas = [
                engine - external
                for engine, external in zip(
                    engine_valid_values,
                    baseline_valid_values,
                    strict=True,
                )
            ]
            metrics.append(
                _metric(
                    engine_id="engine_v2",
                    metric_id=(f"top{top_k}_valid_pose_success_rate_paired_delta"),
                    analysis_scope="primary_blind_holdout",
                    subgroup="all",
                    values=valid_deltas,
                    statistic=_mean,
                    policy=active_policy,
                    baseline=baseline,
                )
            )

    metrics.extend(
        _derive_scope_all_metrics(
            row_map,
            policy=active_policy,
            analysis_scope="contaminated_development",
            case_ids=PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS,
        )
    )
    metrics.extend(
        _derive_scope_all_metrics(
            row_map,
            policy=active_policy,
            analysis_scope="engineering_smoke",
            case_ids=PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
        )
    )
    metrics.extend(
        _derive_scope_all_metrics(
            row_map,
            policy=active_policy,
            analysis_scope="supplementary_descriptive",
            case_ids=active_cohort.case_ids,
        )
    )
    return tuple(metrics)


def build_public_redocking_benchmark_report(
    profiles: Sequence[PublicRedockingCaseProfile],
    engine_identities: Sequence[PublicRedockingEngineIdentity],
    executions: Sequence[VerifiedPublicRedockingCaseExecution],
    *,
    materializations: Sequence[VerifiedCaseMaterialization],
    cohort: FrozenPublicRedockingCohort | None = None,
    policy: PublicRedockingEvaluationPolicy | None = None,
) -> PublicRedockingBenchmarkReport:
    """Build Top-1/3/5, validity, failure, runtime, subgroup, and paired metrics."""

    active_cohort = frozen_public_redocking_cohort() if cohort is None else cohort
    active_policy = PublicRedockingEvaluationPolicy() if policy is None else policy
    profile_rows = tuple(profiles)
    materialization_rows = tuple(materializations)
    if any(
        type(row) is not VerifiedCaseMaterialization for row in materialization_rows
    ):
        raise TypeError("materializations must be VerifiedCaseMaterialization rows")
    identity_rows = tuple(engine_identities)
    execution_rows = tuple(executions)
    if any(
        type(execution) is not VerifiedPublicRedockingCaseExecution
        for execution in execution_rows
    ):
        raise TypeError(
            "executions must be VerifiedPublicRedockingCaseExecution receipts"
        )
    tuple(execution.receipt_sha256 for execution in execution_rows)
    return PublicRedockingBenchmarkReport(
        cohort=active_cohort,
        policy=active_policy,
        profiles=profile_rows,
        materializations=materialization_rows,
        engine_identities=identity_rows,
        executions=execution_rows,
        metrics=(),
    )


__all__ = [
    "FROZEN_PUBLIC_REDOCKING_CASE_IDS",
    "FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS",
    "MAX_PUBLIC_REDOCKING_BOOTSTRAP_SAMPLES",
    "PUBLIC_REDOCKING_ANALYSIS_SCOPES",
    "PUBLIC_REDOCKING_ARCHIVE_SHA256",
    "PUBLIC_REDOCKING_CASE_SEED_BASE",
    "PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID",
    "PUBLIC_REDOCKING_COHORT_COUNT",
    "PUBLIC_REDOCKING_COHORT_ID",
    "PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT",
    "PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID",
    "PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID",
    "PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS",
    "PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS",
    "PUBLIC_REDOCKING_PROPOSAL_MODES",
    "PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS",
    "PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SCHEMA_ID",
    "PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SHA256",
    "PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS",
    "PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS_SHA256",
    "PUBLIC_REDOCKING_HISTORICAL_REPORT_SHA256",
    "PUBLIC_REDOCKING_MATERIALIZATION_RECEIPTS_SHA256",
    "PUBLIC_REDOCKING_MATERIALIZATIONS_SHA256",
    "PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID",
    "PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS",
    "PUBLIC_REDOCKING_PRIMARY_ENGINES",
    "PUBLIC_REDOCKING_PROFILE_METHOD_ID",
    "PUBLIC_REDOCKING_PROFILES_SHA256",
    "PUBLIC_REDOCKING_RING_PROFILE_METHOD_ID",
    "PUBLIC_REDOCKING_RING_PROFILES_SHA256",
    "PUBLIC_REDOCKING_RING_SUBGROUPS",
    "PUBLIC_REDOCKING_REPORT_SCHEMA_ID",
    "PUBLIC_REDOCKING_ROTOR_SUBGROUPS",
    "PUBLIC_REDOCKING_RUNNER_ID",
    "PUBLIC_REDOCKING_SIZE_SUBGROUPS",
    "PUBLIC_REDOCKING_SOURCE_IDS_SHA256",
    "PUBLIC_REDOCKING_TOP_KS",
    "FrozenPublicRedockingCohort",
    "PublicRedockingBenchmarkError",
    "PublicRedockingBenchmarkReport",
    "PublicRedockingCaseProfile",
    "PublicRedockingCaseResult",
    "PublicRedockingEngineV2CandidateDiagnostic",
    "PublicRedockingEngineV2Diagnostics",
    "PublicRedockingEngineIdentity",
    "PublicRedockingEvaluationPolicy",
    "PublicRedockingMetricEstimate",
    "VerifiedCaseMaterialization",
    "VerifiedPublicRedockingCaseExecution",
    "VerifiedPublicRedockingArchive",
    "build_public_redocking_benchmark_report",
    "frozen_public_redocking_case_seed",
    "frozen_public_redocking_materialization_receipt_sha256",
    "frozen_public_redocking_cohort",
    "frozen_public_redocking_profiles",
    "require_public_redocking_contamination_registry",
    "verify_public_redocking_source_identifiers",
]

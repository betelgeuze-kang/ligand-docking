"""Frozen 300-case public redocking cohort and failure-complete scorecard.

This module defines an offline evaluation contract.  It does not download
inputs, launch Engine V2 or external binaries, or claim docking accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import random
import re
import statistics
from typing import Callable, Sequence


PUBLIC_REDOCKING_COHORT_SCHEMA_ID = "betelgeuze.engine_v2_public_redocking_cohort/1.0.0"
PUBLIC_REDOCKING_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_evaluation_policy/1.0.0"
)
PUBLIC_REDOCKING_REPORT_SCHEMA_ID = "betelgeuze.engine_v2_public_redocking_report/1.0.0"
PUBLIC_REDOCKING_COHORT_ID = "posebusters-journal-subset-sha256-300"
PUBLIC_REDOCKING_COHORT_COUNT = 300
PUBLIC_REDOCKING_SOURCE_COUNT = 308
PUBLIC_REDOCKING_SELECTION_SALT = "betelgeuze-engine-v2-posebusters-300-v1"
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
PUBLIC_REDOCKING_PROFILES_SHA256 = (
    "18ed3a4a50d5663a2dfb6f159ac515b15d6aebac9793831467aa2950e4710312"
)
PUBLIC_REDOCKING_PRIMARY_ENGINES = ("engine_v2", "vina", "gnina")
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
_CASE_ID_RE = re.compile(r"^[0-9][A-Z0-9]{3}_[A-Z0-9]{3}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
    indexes = tuple(
        index for index, token in enumerate(command) if token == option
    )
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


def _require_command_flag(command: Sequence[str], flag: str) -> None:
    if sum(token == flag for token in command) != 1:
        raise PublicRedockingBenchmarkError(
            f"engine command must contain exactly one {flag}"
        )


def _require_case_input_path(
    command: Sequence[str],
    option: str,
    *,
    expected_basename: str,
    engine_id: str,
) -> None:
    value = _command_option_value(command, option)
    basename = value.replace("\\", "/").rsplit("/", 1)[-1]
    if basename != expected_basename:
        raise PublicRedockingBenchmarkError(
            f"{engine_id} command {option} is cross-wired to another case"
        )


def _validate_engine_commands(
    identity: "PublicRedockingEngineIdentity",
    rows: Sequence["PublicRedockingCaseResult"],
    *,
    policy: "PublicRedockingEvaluationPolicy",
) -> None:
    if any(row.execution_command[0] != identity.command[0] for row in rows):
        raise PublicRedockingBenchmarkError(
            f"{identity.engine_id} row command executable contradicts its identity"
        )
    if identity.engine_id == "engine_v2":
        if (
            len(identity.command) < 2
            or identity.command[1] != "engine_v2"
            or any(
                len(row.execution_command) < 2
                or row.execution_command[1] != "engine_v2"
                for row in rows
            )
        ):
            raise PublicRedockingBenchmarkError(
                "Engine V2 row command contradicts its identity"
            )
        expected_options = {
            "--candidate-count": "64",
            "--cpu": str(policy.cpu_count),
        }
        for option, expected in expected_options.items():
            if _command_option_value(identity.command, option) != expected or any(
                _command_option_value(row.execution_command, option) != expected
                for row in rows
            ):
                raise PublicRedockingBenchmarkError(
                    f"Engine V2 command contradicts frozen {option}"
                )
        for row in rows:
            if _command_option_value(row.execution_command, "--case-id") != row.case_id:
                raise PublicRedockingBenchmarkError(
                    "Engine V2 row command is cross-wired to another case"
                )
            for option, suffix in (
                ("--receptor", "protein.pdb"),
                ("--ligand", "ligand_start_conf.sdf"),
                ("--pocket-source", "ligand.sdf"),
            ):
                _require_case_input_path(
                    row.execution_command,
                    option,
                    expected_basename=f"{row.case_id}_{suffix}",
                    engine_id="Engine V2",
                )
            for option in ("--seed", "--out"):
                _command_option_value(row.execution_command, option)
        return

    expected_options = {
        "--scoring": "vina",
        "--cnn_scoring": "none" if identity.engine_id == "vina" else "rescore",
        "--cpu": str(policy.cpu_count),
    }
    if identity.engine_id == "gnina":
        expected_options["--cnn"] = "crossdock_default2018"
    for option, expected in expected_options.items():
        if _command_option_value(identity.command, option) != expected or any(
            _command_option_value(row.execution_command, option) != expected
            for row in rows
        ):
            raise PublicRedockingBenchmarkError(
                f"{identity.engine_id} command contradicts frozen {option}"
            )
    if (
        _command_option_value(identity.command, "--timeout-seconds")
        != str(policy.external_timeout_seconds)
    ):
        raise PublicRedockingBenchmarkError(
            f"{identity.engine_id} identity timeout contradicts report policy"
        )
    _require_command_flag(identity.command, "--no_gpu")
    for row in rows:
        _require_command_flag(row.execution_command, "--no_gpu")
        for option, suffix in (
            ("--receptor", "protein.pdb"),
            ("--ligand", "ligand_start_conf.sdf"),
            ("--autobox_ligand", "ligand.sdf"),
        ):
            _require_case_input_path(
                row.execution_command,
                option,
                expected_basename=f"{row.case_id}_{suffix}",
                engine_id=identity.engine_id,
            )
        for option, expected in (
            ("--autobox_add", "4"),
            ("--num_modes", "5"),
            ("--exhaustiveness", "1"),
            ("--seed", None),
            ("--out", None),
        ):
            observed = _command_option_value(row.execution_command, option)
            if expected is not None and observed != expected:
                raise PublicRedockingBenchmarkError(
                    f"{identity.engine_id} command contradicts frozen {option}"
                )


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
            "profiles": {
                "method_id": PUBLIC_REDOCKING_PROFILE_METHOD_ID,
                "profiles_sha256": PUBLIC_REDOCKING_PROFILES_SHA256,
                "heavy_atom_and_rotor_subgroups_frozen_before_results": True,
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
            "failure_denominator": "all_300_frozen_cases",
            "missing_candidate_policy": "case_failure",
        }


@dataclass(frozen=True, slots=True)
class PublicRedockingCaseProfile:
    case_id: str
    heavy_atom_count: int
    rotor_count: int
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

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "heavy_atom_count": self.heavy_atom_count,
            "rotor_count": self.rotor_count,
            "ligand_artifact_sha256": self.ligand_artifact_sha256,
            "profile_method_id": PUBLIC_REDOCKING_PROFILE_METHOD_ID,
            "size_subgroup": self.size_subgroup,
            "rotor_subgroup": self.rotor_subgroup,
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
        }


@dataclass(frozen=True, slots=True)
class PublicRedockingMetricEstimate:
    engine_id: str
    metric_id: str
    subgroup: str
    case_count: int
    value: float
    confidence_interval_low: float
    confidence_interval_high: float
    paired_baseline_engine_id: str = ""

    def __post_init__(self) -> None:
        if self.engine_id not in PUBLIC_REDOCKING_PRIMARY_ENGINES:
            raise PublicRedockingBenchmarkError("metric engine_id is invalid")
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
        identity=f"{engine_id}:{baseline}:{metric_id}:{subgroup}",
    )
    return PublicRedockingMetricEstimate(
        engine_id=engine_id,
        metric_id=metric_id,
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
    engine_identities: tuple[PublicRedockingEngineIdentity, ...]
    rows: tuple[PublicRedockingCaseResult, ...]
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
        identities = tuple(self.engine_identities)
        rows = tuple(self.rows)
        metrics = tuple(self.metrics)
        if tuple(profile.case_id for profile in profiles) != self.cohort.case_ids:
            raise PublicRedockingBenchmarkError(
                "profiles must cover every frozen case in exact order"
            )
        if profiles != frozen_public_redocking_profiles():
            raise PublicRedockingBenchmarkError(
                "profiles must match the frozen source-derived values"
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
                "rows must retain one ordered row per engine and frozen case"
            )
        profile_map = {profile.case_id: profile for profile in profiles}
        row_map = {(row.engine_id, row.case_id): row for row in rows}
        engine_v2_policies = {
            row.execution_policy for row in rows if row.engine_id == "engine_v2"
        }
        if len(engine_v2_policies) != 1:
            raise PublicRedockingBenchmarkError(
                "Engine V2 rows must use one execution policy"
            )
        engine_v2_policy = _execution_policy_mapping(
            next(iter(engine_v2_policies))
        )
        required_engine_v2_policy = {
            "cpu_count",
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
        for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
            _validate_engine_commands(
                identity_map[engine_id],
                tuple(row for row in rows if row.engine_id == engine_id),
                policy=self.policy,
            )
        for case_id in self.cohort.case_ids:
            case_rows = tuple(
                row_map[(engine_id, case_id)]
                for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
            )
            if len({row.input_artifact_sha256s for row in case_rows}) != 1:
                raise PublicRedockingBenchmarkError(
                    "engines must use identical source artifacts per case"
                )
            if (
                case_rows[0].native_artifact_sha256
                != profile_map[case_id].ligand_artifact_sha256
            ):
                raise PublicRedockingBenchmarkError(
                    "result native ligand is not the frozen profile artifact"
                )
        if not metrics:
            raise PublicRedockingBenchmarkError("report metrics cannot be empty")
        expected_metrics = _derive_public_redocking_metrics(
            profiles,
            identities,
            rows,
            cohort=self.cohort,
            policy=self.policy,
        )
        if metrics != expected_metrics:
            raise PublicRedockingBenchmarkError(
                "report metrics do not match the retained result rows"
            )
        object.__setattr__(self, "profiles", profiles)
        object.__setattr__(self, "engine_identities", identities)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

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
            "engine_identities": [
                identity.to_dict() for identity in self.engine_identities
            ],
            "rows": [row.to_dict() for row in self.rows],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "case_count": len(self.cohort.case_ids),
            "row_count": len(self.rows),
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
    if size_subgroups != set(PUBLIC_REDOCKING_SIZE_SUBGROUPS) or rotor_subgroups != set(
        PUBLIC_REDOCKING_ROTOR_SUBGROUPS
    ):
        raise PublicRedockingBenchmarkError(
            "profiles must represent every frozen size and rotor subgroup"
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

    subgroup_ids: dict[str, tuple[str, ...]] = {
        "all": active_cohort.case_ids,
    }
    for attribute in ("size_subgroup", "rotor_subgroup"):
        for subgroup in sorted(
            {getattr(profile, attribute) for profile in profile_rows}
        ):
            subgroup_ids[subgroup] = tuple(
                profile.case_id
                for profile in profile_rows
                if getattr(profile, attribute) == subgroup
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
                        subgroup=subgroup,
                        values=failure_values,
                        statistic=_mean,
                        policy=active_policy,
                    ),
                    _metric(
                        engine_id=engine_id,
                        metric_id="runtime_median_seconds",
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
                            subgroup=subgroup,
                            values=recovery,
                            statistic=_mean,
                            policy=active_policy,
                        ),
                        _metric(
                            engine_id=engine_id,
                            metric_id=f"top{top_k}_valid_pose_success_rate",
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
                        subgroup=subgroup,
                        values=top1_geometric,
                        statistic=_mean,
                        policy=active_policy,
                    ),
                    _metric(
                        engine_id=engine_id,
                        metric_id="top1_chemical_validity_rate",
                        subgroup=subgroup,
                        values=top1_chemical,
                        statistic=_mean,
                        policy=active_policy,
                    ),
                )
            )

    for baseline in ("vina", "gnina"):
        engine_failures = [
            float(row_map[("engine_v2", case_id)].status == "failure")
            for case_id in active_cohort.case_ids
        ]
        baseline_failures = [
            float(row_map[(baseline, case_id)].status == "failure")
            for case_id in active_cohort.case_ids
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
            for case_id in active_cohort.case_ids
        ]
        metrics.extend(
            (
                _metric(
                    engine_id="engine_v2",
                    metric_id="full_case_failure_rate_paired_delta",
                    subgroup="all",
                    values=failure_deltas,
                    statistic=_mean,
                    policy=active_policy,
                    baseline=baseline,
                ),
                _metric(
                    engine_id="engine_v2",
                    metric_id="runtime_seconds_paired_median_delta",
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
                for case_id in active_cohort.case_ids
            ]
            baseline_values = [
                row_map[(baseline, case_id)].recovery(
                    top_k,
                    active_policy.rmsd_threshold_angstrom,
                )
                for case_id in active_cohort.case_ids
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
                for case_id in active_cohort.case_ids
            ]
            baseline_valid_values = [
                row_map[(baseline, case_id)].valid_recovery(
                    top_k,
                    active_policy.rmsd_threshold_angstrom,
                )
                for case_id in active_cohort.case_ids
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
                    subgroup="all",
                    values=valid_deltas,
                    statistic=_mean,
                    policy=active_policy,
                    baseline=baseline,
                )
            )

    return tuple(metrics)


def build_public_redocking_benchmark_report(
    profiles: Sequence[PublicRedockingCaseProfile],
    engine_identities: Sequence[PublicRedockingEngineIdentity],
    rows: Sequence[PublicRedockingCaseResult],
    *,
    cohort: FrozenPublicRedockingCohort | None = None,
    policy: PublicRedockingEvaluationPolicy | None = None,
) -> PublicRedockingBenchmarkReport:
    """Build Top-1/3/5, validity, failure, runtime, subgroup, and paired metrics."""

    active_cohort = frozen_public_redocking_cohort() if cohort is None else cohort
    active_policy = PublicRedockingEvaluationPolicy() if policy is None else policy
    profile_rows = tuple(profiles)
    identity_rows = tuple(engine_identities)
    result_rows = tuple(rows)
    metrics = _derive_public_redocking_metrics(
        profile_rows,
        identity_rows,
        result_rows,
        cohort=active_cohort,
        policy=active_policy,
    )
    return PublicRedockingBenchmarkReport(
        cohort=active_cohort,
        policy=active_policy,
        profiles=profile_rows,
        engine_identities=identity_rows,
        rows=result_rows,
        metrics=tuple(metrics),
    )


__all__ = [
    "FROZEN_PUBLIC_REDOCKING_CASE_IDS",
    "MAX_PUBLIC_REDOCKING_BOOTSTRAP_SAMPLES",
    "PUBLIC_REDOCKING_ARCHIVE_SHA256",
    "PUBLIC_REDOCKING_COHORT_COUNT",
    "PUBLIC_REDOCKING_COHORT_ID",
    "PUBLIC_REDOCKING_PRIMARY_ENGINES",
    "PUBLIC_REDOCKING_PROFILE_METHOD_ID",
    "PUBLIC_REDOCKING_PROFILES_SHA256",
    "PUBLIC_REDOCKING_REPORT_SCHEMA_ID",
    "PUBLIC_REDOCKING_ROTOR_SUBGROUPS",
    "PUBLIC_REDOCKING_SIZE_SUBGROUPS",
    "PUBLIC_REDOCKING_SOURCE_IDS_SHA256",
    "PUBLIC_REDOCKING_TOP_KS",
    "FrozenPublicRedockingCohort",
    "PublicRedockingBenchmarkError",
    "PublicRedockingBenchmarkReport",
    "PublicRedockingCaseProfile",
    "PublicRedockingCaseResult",
    "PublicRedockingEngineIdentity",
    "PublicRedockingEvaluationPolicy",
    "PublicRedockingMetricEstimate",
    "build_public_redocking_benchmark_report",
    "frozen_public_redocking_cohort",
    "frozen_public_redocking_profiles",
    "verify_public_redocking_source_identifiers",
]

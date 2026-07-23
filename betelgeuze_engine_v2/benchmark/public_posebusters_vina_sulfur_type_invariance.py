"""Preregister and execute the bounded default-Vina sulfur-type invariance audit.

The exact AutoDock Vina 1.2.7 source maps both AutoDock ``S`` and ``SA`` atom
types to the same Vina ``XS_TYPE_S_P`` type.  This module binds that source
claim before execution and then rescores every retained Vina pose for the three
neutral-thioether discrepancies after changing only the target PDBQT type from
``SA`` to ``S``.

The resulting receipt is deliberately narrow.  It can establish fixed-pose
score invariance in the active default-Vina lane.  It cannot decide whether a
neutral thioether is chemically a hydrogen-bond acceptor, validate AutoDock4
scoring, or promote a docking or chemistry claim.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Protocol

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
)
from .public_posebusters_generated_pose_evaluation import (
    _load_vina_receipt,
)
from .public_posebusters_intake import (
    _read_exact_regular_file,
)
from .public_posebusters_openbabel_charge_type_comparison import (
    POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID,
    _read_canonical_receipt as _read_openbabel_comparison_receipt,
)
from .public_posebusters_vina_execution import (
    POSEBUSTERS_VINA_EXECUTION_CONFIGURATION,
    POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256,
    _DigestingTextSink,
    _load_preparation_receipt,
    _load_vina_runtime,
)


POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_sulfur_invariance_protocol/1.0.0"
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_sulfur_invariance_observation/1.0.0"
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_sulfur_invariance_case/1.0.0"
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_sulfur_invariance_score/1.0.0"
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_ALL_CASE_DENOMINATOR = 308
POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_PROTOCOL_BYTES = 8 * 1024 * 1024
POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_OBSERVATION_BYTES = 16 * 1024 * 1024
POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_SOURCE_BYTES = 4 * 1024 * 1024
POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_MODEL_BYTES = 256 * 1024
POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_COMPONENTS = (
    "total",
    "ligand_receptor_inter",
    "ligand_flexible_inter",
    "other_inter",
    "flexible_receptor_intra",
    "ligand_intra",
    "torsions",
    "ligand_intra_best_pose",
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE = {
    "7CIJ_G0C": {
        "environment": "aliphatic_thioether",
        "target_pdbqt_serial": 13,
    },
    "7LT0_ONJ": {
        "environment": "diaryl_thioether",
        "target_pdbqt_serial": 18,
    },
    "7NLV_UJE": {
        "environment": "bicyclic_aliphatic_thioether",
        "target_pdbqt_serial": 16,
    },
}
POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE_CASE_IDS = tuple(
    sorted(POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE)
)

POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_VERSION = "1.2.7"
POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_COMMIT = (
    "8eb40404f4f45608acb3b01427587ac049f27c1f"
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_URL = (
    "https://github.com/ccsb-scripps/AutoDock-Vina/tree/v1.2.7"
)
POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_FILES = {
    "src/lib/atom_constants.h": (
        "b416af5cdcf5a3fe1fd05dac09ed1998731dd0a9fbdefa41e6f9ae97bd2067fd"
    ),
    "src/lib/model.cpp": (
        "9f356a53be56047f6a8a9b5ebc443ea6cb69db73e69f8d2bbd4bab4afdfb05cc"
    ),
    "src/lib/potentials.h": (
        "ceb6625eaa0a2278193b11e22d0565f854f35442e9a5ee97bed2cc84a0d194a4"
    ),
    "src/lib/scoring_function.h": (
        "c982b04d140aa1a349213172d34224f0aa6c9d79f96a6afa109a547a001d6c1f"
    ),
    "src/lib/vina.h": (
        "8ec33a87203da3c68ec25014eb4fffdf4368eb3a4baba4283aa57c86f1df364a"
    ),
}

POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION = {
    "all_case_denominator": (
        POSEBUSTERS_VINA_SULFUR_INVARIANCE_ALL_CASE_DENOMINATOR
    ),
    "active_scoring_lane": "vina",
    "counterfactual_mutation": {
        "field": "pdbqt_ad4_atom_type_columns_78_79",
        "original": "SA",
        "variant": "S",
        "target_atom_only": True,
        "coordinates_unchanged": True,
        "charges_unchanged": True,
        "topology_unchanged": True,
    },
    "pose_scope": (
        "every_model_in_exact_vina_execution_pose_artifact_for_scope_cases"
    ),
    "runtime_score_api": "vina.Vina.score",
    "runtime_score_precision": "public_api_three_decimal_kcal_per_mol",
    "score_components": list(
        POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_COMPONENTS
    ),
    "decision_contract": {
        "default_vina_fixed_pose_score_invariance_pass": (
            "all_scoped_poses_all_public_components_exact_binary64_equal"
        ),
        "post_result_tolerance": False,
        "docking_search_reexecuted": False,
        "ad4_scoring_evaluated": False,
        "chemical_acceptor_semantics_adjudicated": False,
        "product_promotion_allowed": False,
    },
    "source_semantics": {
        "active_vina_scoring_uses_xs_atom_typing": True,
        "ad_s_maps_to_element_s_then_xs_type_s_p": True,
        "ad_sa_maps_to_element_s_then_xs_type_s_p": True,
        "xs_type_s_p_is_absent_from_xs_acceptor_set": True,
        "default_vina_hydrogen_bond_term_uses_xs_acceptor_set": True,
    },
    "upstream_vina_execution_configuration_sha256": (
        POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256
    ),
}
POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256 = (
    "b523ff9b98ff1b006db70d4d1900ee6dce599fb4a1f7646bad89fba8979637ea"
)

POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCIENTIFIC_BLOCKERS = (
    "fixed_pose_rescoring_does_not_reexecute_docking_search",
    "default_vina_xs_invariance_does_not_apply_to_ad4_scoring",
    "atom_type_invariance_does_not_adjudicate_chemical_acceptor_semantics",
    "three_neutral_thioether_cases_are_not_representative_chemistry",
    "no_donor_acceptor_interaction_energy_reference",
    "second_cpu_host_reproduction_missing",
    "independent_scientific_review_missing",
)

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_MODEL_PREFIX = b"MODEL"
_MODEL_SUFFIX = b"ENDMDL"


class PoseBustersVinaSulfurInvarianceError(ValueError):
    """Protocol, runtime, source, mutation, or receipt input is invalid."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _utc_timestamp(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersVinaSulfurInvarianceError(f"{name} must be text")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            f"{name} must use second-resolution UTC"
        ) from exc
    text = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    if text != value:
        raise PoseBustersVinaSulfurInvarianceError(
            f"{name} must be canonical UTC"
        )
    return text


def _float_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersVinaSulfurInvarianceError(f"{name} must be finite")
    return number.hex()


def _normalized_error(error: BaseException) -> bytes:
    text = " ".join(str(error).split())
    if not text:
        text = type(error).__name__
    return text[:4096].encode("utf-8", errors="backslashreplace")


def _write_private_no_overwrite(
    payload: Mapping[str, Any],
    output_path: str | os.PathLike[str],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = _canonical_bytes(dict(payload)) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina sulfur-invariance output already exists"
            ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _read_private_canonical_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_schema_id: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    source = _read_exact_regular_file(receipt_path, maximum_bytes=maximum_bytes)
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    if (
        raw.get("schema_id") != expected_schema_id
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance receipt fingerprint or schema is invalid"
        )
    return raw, source


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    source = Path(__file__)
    return tuple(
        sorted(
            {
                "generated_pose_receipt_loader": _source_file_sha256(
                    source.with_name(
                        "public_posebusters_generated_pose_evaluation.py"
                    )
                ),
                "openbabel_comparison_contract": _source_file_sha256(
                    source.with_name(
                        "public_posebusters_openbabel_charge_type_comparison.py"
                    )
                ),
                "vina_execution_contract": _source_file_sha256(
                    source.with_name("public_posebusters_vina_execution.py")
                ),
                "vina_sulfur_invariance": _source_file_sha256(source),
            }.items()
        )
    )


def _vina_source_binding(
    source_root: str | os.PathLike[str],
) -> dict[str, Any]:
    root = Path(source_root).resolve(strict=False)
    members: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for relative_path, expected_sha in sorted(
        POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_FILES.items()
    ):
        payload = _read_exact_regular_file(
            root / relative_path,
            maximum_bytes=POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_SOURCE_BYTES,
        )
        observed_sha = hashlib.sha256(payload).hexdigest()
        if observed_sha != expected_sha:
            raise PoseBustersVinaSulfurInvarianceError(
                f"Vina source file is not the frozen v1.2.7 member: {relative_path}"
            )
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PoseBustersVinaSulfurInvarianceError(
                f"Vina source file is not UTF-8: {relative_path}"
            ) from exc
        payloads[relative_path] = payload
        members.append(
            {
                "relative_path": relative_path,
                "sha256": observed_sha,
                "size_bytes": len(payload),
            }
        )

    atom_constants = payloads["src/lib/atom_constants.h"].decode(
        "utf-8"
    ).replace("\r\n", "\n")
    model = payloads["src/lib/model.cpp"].decode("utf-8").replace(
        "\r\n",
        "\n",
    )
    potentials = payloads["src/lib/potentials.h"].decode("utf-8").replace(
        "\r\n",
        "\n",
    )
    scoring = payloads["src/lib/scoring_function.h"].decode("utf-8").replace(
        "\r\n",
        "\n",
    )
    required_snippets = {
        "model_sulfur_to_xs_s_p": "case EL_TYPE_S    : x = XS_TYPE_S_P; break;",
        "s_and_sa_to_element_s": (
            "case AD_TYPE_SA   : return EL_TYPE_S;",
            "case AD_TYPE_S    : return EL_TYPE_S;",
        ),
        "xs_acceptor_function": (
            "inline bool xs_is_acceptor(sz xs)",
            "return xs == XS_TYPE_N_A",
            "xs == XS_TYPE_O_DA;",
        ),
        "vina_hbond_uses_xs": "if (xs_h_bond_possible(a.xs, b.xs))",
        "vina_scoring_uses_xs": "m_atom_typing = atom_type::XS;",
    }
    if required_snippets["model_sulfur_to_xs_s_p"] not in model:
        raise PoseBustersVinaSulfurInvarianceError(
            "frozen Vina model source no longer maps sulfur to XS_TYPE_S_P"
        )
    if any(
        snippet not in atom_constants
        for snippet in required_snippets["s_and_sa_to_element_s"]
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "frozen Vina atom source no longer maps S and SA to sulfur"
        )
    acceptor_start = atom_constants.find(
        required_snippets["xs_acceptor_function"][0]
    )
    acceptor_end = atom_constants.find("}\n", acceptor_start)
    if (
        acceptor_start < 0
        or acceptor_end < 0
        or any(
            snippet not in atom_constants[acceptor_start:acceptor_end]
            for snippet in required_snippets["xs_acceptor_function"][1:]
        )
        or "XS_TYPE_S_P" in atom_constants[acceptor_start:acceptor_end]
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "frozen Vina XS acceptor source semantics are not exact"
        )
    if required_snippets["vina_hbond_uses_xs"] not in potentials:
        raise PoseBustersVinaSulfurInvarianceError(
            "frozen Vina hydrogen-bond potential no longer uses XS types"
        )
    if required_snippets["vina_scoring_uses_xs"] not in scoring:
        raise PoseBustersVinaSulfurInvarianceError(
            "frozen default Vina scoring no longer selects XS typing"
        )
    semantic_projection = {
        "ad_s_element_type": "EL_TYPE_S",
        "ad_sa_element_type": "EL_TYPE_S",
        "element_s_xs_type": "XS_TYPE_S_P",
        "xs_type_s_p_is_acceptor": False,
        "default_vina_atom_typing": "XS",
        "default_vina_hbond_dispatch": "xs_h_bond_possible",
    }
    return {
        "source_url": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_URL
        ),
        "source_commit": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_COMMIT
        ),
        "source_tag": "v1.2.7",
        "members": members,
        "members_sha256": _canonical_sha256(members),
        "semantic_projection": semantic_projection,
        "semantic_projection_sha256": _canonical_sha256(
            semantic_projection
        ),
    }


def _split_vina_pose_models(payload: bytes) -> tuple[bytes, ...]:
    if (
        not isinstance(payload, bytes)
        or not payload
        or b"\x00" in payload
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina pose artifact must be bounded non-empty bytes"
        )
    try:
        payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina pose artifact must be ASCII"
        ) from exc
    models: list[bytes] = []
    current: list[bytes] | None = None
    expected_index = 1
    for line in payload.splitlines(keepends=True):
        stripped = line.rstrip(b"\r\n")
        if stripped.startswith(_MODEL_PREFIX + b" "):
            if current is not None:
                raise PoseBustersVinaSulfurInvarianceError(
                    "nested Vina pose MODEL blocks are invalid"
                )
            try:
                observed_index = int(stripped.split()[1])
            except (IndexError, ValueError) as exc:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina pose MODEL index is invalid"
                ) from exc
            if observed_index != expected_index:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina pose MODEL indices are not canonical"
                )
            current = []
            continue
        if stripped == _MODEL_SUFFIX:
            if current is None or not current:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina pose ENDMDL is unmatched"
                )
            model = b"".join(current)
            if (
                len(model)
                > POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_MODEL_BYTES
                or b"ROOT" not in model
                or b"TORSDOF" not in model
            ):
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina pose model is incomplete or exceeds its bound"
                )
            models.append(model)
            current = None
            expected_index += 1
            continue
        if current is None:
            if stripped:
                raise PoseBustersVinaSulfurInvarianceError(
                    "bytes outside Vina MODEL blocks are forbidden"
                )
        else:
            current.append(line)
    if current is not None or not models:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina pose artifact has an incomplete model set"
        )
    return tuple(models)


def _pdbqt_atom_type(
    model: bytes,
    *,
    target_serial: int,
) -> str:
    matches: list[str] = []
    for raw_line in model.splitlines():
        if not raw_line.startswith((b"ATOM  ", b"HETATM")):
            continue
        if len(raw_line) < 79:
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina PDBQT atom line is too short"
            )
        try:
            serial = int(raw_line[6:11])
            atom_type = raw_line[77:79].decode("ascii").strip()
        except (ValueError, UnicodeDecodeError) as exc:
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina PDBQT target atom fields are invalid"
            ) from exc
        if serial == target_serial:
            matches.append(atom_type)
    if len(matches) != 1:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina pose does not contain exactly one target serial"
        )
    return matches[0]


def _mutate_target_sa_to_s(
    model: bytes,
    *,
    target_serial: int,
) -> bytes:
    output: list[bytes] = []
    mutation_count = 0
    for line in model.splitlines(keepends=True):
        raw_line = line.rstrip(b"\r\n")
        if raw_line.startswith((b"ATOM  ", b"HETATM")):
            if len(raw_line) < 79:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina PDBQT atom line is too short"
                )
            try:
                serial = int(raw_line[6:11])
            except ValueError as exc:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina PDBQT serial is invalid"
                ) from exc
            if serial == target_serial:
                if raw_line[77:79] != b"SA":
                    raise PoseBustersVinaSulfurInvarianceError(
                        "target Vina PDBQT atom is not exact type SA"
                    )
                line = line[:77] + b" S" + line[79:]
                mutation_count += 1
        output.append(line)
    if mutation_count != 1:
        raise PoseBustersVinaSulfurInvarianceError(
            "counterfactual must mutate exactly one target atom"
        )
    variant = b"".join(output)
    if len(variant) != len(model) or _pdbqt_atom_type(
        variant,
        target_serial=target_serial,
    ) != "S":
        raise PoseBustersVinaSulfurInvarianceError(
            "counterfactual Vina PDBQT mutation is invalid"
        )
    return variant


def _non_type_projection_sha256(
    model: bytes,
    *,
    target_serial: int,
) -> str:
    projection: list[bytes] = []
    target_count = 0
    for line in model.splitlines(keepends=True):
        raw_line = line.rstrip(b"\r\n")
        if raw_line.startswith((b"ATOM  ", b"HETATM")):
            if len(raw_line) < 79:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina PDBQT atom line is too short"
                )
            try:
                serial = int(raw_line[6:11])
            except ValueError as exc:
                raise PoseBustersVinaSulfurInvarianceError(
                    "Vina PDBQT serial is invalid"
                ) from exc
            if serial == target_serial:
                line = line[:77] + b"??" + line[79:]
                target_count += 1
        projection.append(line)
    if target_count != 1:
        raise PoseBustersVinaSulfurInvarianceError(
            "non-type projection target is not unique"
        )
    return hashlib.sha256(b"".join(projection)).hexdigest()


def _openbabel_case_rows(
    receipt: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    raw_rows = receipt.get("case_rows")
    if not isinstance(raw_rows, list):
        raise PoseBustersVinaSulfurInvarianceError(
            "Open Babel comparison case rows are invalid"
        )
    rows: dict[str, Mapping[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise PoseBustersVinaSulfurInvarianceError(
                "Open Babel comparison case row is invalid"
            )
        case_id = row["case_id"]
        if case_id in rows:
            raise PoseBustersVinaSulfurInvarianceError(
                "Open Babel comparison case row is duplicated"
            )
        rows[case_id] = row
    return rows


def _target_comparison_binding(
    case_id: str,
    comparison_row: Mapping[str, Any],
) -> dict[str, Any]:
    target_serial = int(
        POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE[case_id][
            "target_pdbqt_serial"
        ]
    )
    raw_atoms = comparison_row.get("atom_rows")
    if (
        comparison_row.get("status") != "evaluated"
        or not isinstance(raw_atoms, list)
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} has no evaluated Open Babel comparison"
        )
    matches = [
        atom
        for atom in raw_atoms
        if isinstance(atom, dict)
        and atom.get("pdbqt_serial") == target_serial
        and atom.get("element_symbol") == "S"
        and atom.get("meeko_ad4_atom_type") == "SA"
        and atom.get("openbabel_ad4_atom_type") == "S"
    ]
    if len(matches) != 1:
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} target SA/S comparison is not unique"
        )
    target = matches[0]
    return {
        "pdbqt_serial": target_serial,
        "element_symbol": "S",
        "meeko_ad4_atom_type": "SA",
        "openbabel_ad4_atom_type": "S",
        "source_smiles_atom_index": _positive_int(
            target.get("source_smiles_atom_index"),
            name="target source SMILES atom index",
            allow_zero=True,
        ),
        "meeko_charge_binary64_hex": target.get(
            "meeko_charge_binary64_hex"
        ),
        "openbabel_charge_binary64_hex": target.get(
            "openbabel_charge_binary64_hex"
        ),
    }


def _artifact_by_role(case: Any, role: str) -> Any:
    matches = [artifact for artifact in case.artifacts if artifact.role == role]
    if len(matches) != 1:
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case.case_id} preparation artifact role is not unique: {role}"
        )
    return matches[0]


def _read_vina_receipt_identity(
    receipt_path: str | os.PathLike[str],
) -> dict[str, Any]:
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=8 * 1024 * 1024,
    )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina execution receipt is not JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina execution receipt is not canonical"
        )
    identity = raw.get("engine_identity")
    if (
        not isinstance(identity, dict)
        or _canonical_sha256(identity) != raw.get("engine_identity_sha256")
        or identity.get("engine_id") != "vina"
        or identity.get("engine_version")
        != POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_VERSION
        or raw.get("configuration")
        != POSEBUSTERS_VINA_EXECUTION_CONFIGURATION
        or raw.get("configuration_sha256")
        != POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina execution engine identity or configuration is invalid"
        )
    return {
        "engine_identity": identity,
        "engine_identity_sha256": raw["engine_identity_sha256"],
        "configuration": raw["configuration"],
        "configuration_sha256": raw["configuration_sha256"],
    }


def _protocol_payload(
    *,
    registered_utc: str,
    preparation: Any,
    vina_receipt: Any,
    vina_identity: Mapping[str, Any],
    openbabel_receipt: Mapping[str, Any],
    source_binding: Mapping[str, Any],
    case_rows: Sequence[Mapping[str, Any]],
    source_members: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    rows = [dict(row) for row in case_rows]
    source_member_map = dict(source_members)
    payload = {
        "schema_id": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID
        ),
        "registered_utc": registered_utc,
        "protocol_registered_before_rescoring": True,
        "runtime_rescoring_performed": False,
        "configuration": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION
        ),
        "configuration_sha256": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256
        ),
        "preparation_receipt_sha256": preparation.receipt_sha256,
        "preparation_receipt_file_sha256": (
            preparation.receipt_file_sha256
        ),
        "preparation_artifact_set_sha256": preparation.artifact_set_sha256,
        "vina_execution_receipt_sha256": vina_receipt.receipt_sha256,
        "vina_execution_receipt_file_sha256": (
            vina_receipt.receipt_file_sha256
        ),
        "vina_execution_artifact_set_sha256": (
            vina_receipt.artifact_set_sha256
        ),
        "openbabel_comparison_receipt_sha256": (
            openbabel_receipt["receipt_sha256"]
        ),
        "vina_engine_identity": dict(vina_identity["engine_identity"]),
        "vina_engine_identity_sha256": (
            vina_identity["engine_identity_sha256"]
        ),
        "vina_execution_configuration": dict(
            vina_identity["configuration"]
        ),
        "vina_execution_configuration_sha256": (
            vina_identity["configuration_sha256"]
        ),
        "vina_source_binding": dict(source_binding),
        "implementation_source_members": source_member_map,
        "implementation_source_sha256": _canonical_sha256(
            source_member_map
        ),
        "all_case_denominator": len(rows),
        "scope_case_count": len(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE_CASE_IDS
        ),
        "scope_pose_count": sum(
            int(row.get("pose_count", 0))
            for row in rows
            if row.get("status") == "registered"
        ),
        "scope_abstention_case_count": sum(
            row.get("status") == "abstain_protocol_scope" for row in rows
        ),
        "case_rows": rows,
        "default_vina_fixed_pose_score_invariance_pass": None,
        "bounded_default_vina_invariance_claim_safe": False,
        "chemical_acceptor_semantics_adjudicated": False,
        "ad4_scoring_evaluated": False,
        "docking_search_reexecuted": False,
        "scientifically_validated": False,
        "benchmark_executed": False,
        "product_promotion_allowed": False,
        "scientific_blockers": list(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCIENTIFIC_BLOCKERS
        ),
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_vina_sulfur_invariance_protocol(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_execution_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_vina_execution_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
    registered_utc: str,
) -> dict[str, Any]:
    """Bind the complete default-Vina invariance protocol without rescoring."""

    registered = _utc_timestamp(registered_utc, name="registration UTC")
    if (
        _canonical_sha256(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION
        )
        != POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance frozen configuration was mutated"
        )
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except ValueError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "preparation receipt or artifacts are invalid"
        ) from exc
    try:
        vina_receipt, vina_payloads = _load_vina_receipt(
            vina_execution_receipt_path,
            vina_artifact_root,
            expected_receipt_sha256=expected_vina_execution_receipt_sha256,
            expected_preparation_receipt_sha256=(
                preparation.receipt_sha256
            ),
            expected_preparation_receipt_file_sha256=(
                preparation.receipt_file_sha256
            ),
            expected_preparation_artifact_set_sha256=(
                preparation.artifact_set_sha256
            ),
        )
    except ValueError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina execution receipt or pose artifacts are invalid"
        ) from exc
    openbabel_raw, _openbabel_source = _read_openbabel_comparison_receipt(
        openbabel_comparison_receipt_path,
        expected_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
    )
    if (
        openbabel_raw.get("schema_id")
        != POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID
        or openbabel_raw.get("preparation_receipt_sha256")
        != preparation.receipt_sha256
        or openbabel_raw.get("preparation_receipt_file_sha256")
        != preparation.receipt_file_sha256
        or openbabel_raw.get("preparation_artifact_set_sha256")
        != preparation.artifact_set_sha256
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Open Babel comparison is not bound to exact preparation"
        )
    source_binding = _vina_source_binding(vina_source_root)
    vina_identity = _read_vina_receipt_identity(
        vina_execution_receipt_path
    )

    preparation_rows = {
        row.case_id: row for row in preparation.case_rows
    }
    vina_rows = {row.case_id: row for row in vina_receipt.case_rows}
    comparison_rows = _openbabel_case_rows(openbabel_raw)
    case_ids = tuple(sorted(preparation_rows))
    if (
        len(case_ids)
        != POSEBUSTERS_VINA_SULFUR_INVARIANCE_ALL_CASE_DENOMINATOR
        or case_ids != tuple(sorted(vina_rows))
        or case_ids != tuple(sorted(comparison_rows))
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina invariance inputs do not share the 308-case denominator"
        )

    protocol_rows: list[dict[str, Any]] = []
    for case_id in case_ids:
        base = {
            "schema_id": (
                POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID
            ),
            "case_id": case_id,
        }
        if case_id not in POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE:
            protocol_rows.append(
                {
                    **base,
                    "status": "abstain_protocol_scope",
                    "disposition_code": (
                        "outside_preregistered_neutral_thioether_scope"
                    ),
                    "pose_count": 0,
                }
            )
            continue
        prepared = preparation_rows[case_id]
        vina_case = vina_rows[case_id]
        if (
            prepared.status != "prepared"
            or vina_case.status != "success"
            or vina_case.artifact is None
            or vina_case.pose_count < 1
        ):
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} is not an exact successful Vina input"
            )
        receptor = _artifact_by_role(
            prepared,
            "prepared_receptor_pdbqt",
        )
        ligand = _artifact_by_role(
            prepared,
            "prepared_ligand_pdbqt",
        )
        receptor_payload = prepared_payloads.get(receptor.relative_path)
        ligand_payload = prepared_payloads.get(ligand.relative_path)
        pose_payload = vina_payloads.get(vina_case.artifact.relative_path)
        if (
            receptor_payload is None
            or ligand_payload is None
            or pose_payload is None
        ):
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} bound artifacts are unavailable"
            )
        target = _target_comparison_binding(
            case_id,
            comparison_rows[case_id],
        )
        target_serial = int(target["pdbqt_serial"])
        if _pdbqt_atom_type(
            ligand_payload,
            target_serial=target_serial,
        ) != "SA":
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} prepared target is not exact type SA"
            )
        models = _split_vina_pose_models(pose_payload)
        if len(models) != vina_case.pose_count or any(
            _pdbqt_atom_type(model, target_serial=target_serial) != "SA"
            for model in models
        ):
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} exact pose artifact target types are invalid"
            )
        protocol_rows.append(
            {
                **base,
                "status": "registered",
                "disposition_code": (
                    "default_vina_neutral_thioether_type_invariance"
                ),
                "environment": (
                    POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE[
                        case_id
                    ]["environment"]
                ),
                "target_comparison": target,
                "pocket_center_binary64_hex": list(
                    prepared.pocket_center_binary64_hex
                ),
                "prepared_receptor": {
                    "relative_path": receptor.relative_path,
                    "sha256": receptor.sha256,
                    "size_bytes": receptor.size_bytes,
                },
                "prepared_ligand": {
                    "relative_path": ligand.relative_path,
                    "sha256": ligand.sha256,
                    "size_bytes": ligand.size_bytes,
                },
                "vina_pose_artifact": {
                    "relative_path": vina_case.artifact.relative_path,
                    "sha256": vina_case.artifact.sha256,
                    "size_bytes": vina_case.artifact.size_bytes,
                },
                "pose_count": len(models),
                "pose_model_sha256": [
                    hashlib.sha256(model).hexdigest() for model in models
                ],
            }
        )
    source_members = _implementation_source_members()
    return _protocol_payload(
        registered_utc=registered,
        preparation=preparation,
        vina_receipt=vina_receipt,
        vina_identity=vina_identity,
        openbabel_receipt=openbabel_raw,
        source_binding=source_binding,
        case_rows=protocol_rows,
        source_members=source_members,
    )


def verify_posebusters_vina_sulfur_invariance_protocol(
    protocol_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_execution_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    *,
    expected_protocol_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_vina_execution_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
) -> dict[str, Any]:
    raw, source = _read_private_canonical_receipt(
        protocol_receipt_path,
        expected_receipt_sha256=expected_protocol_receipt_sha256,
        expected_schema_id=(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID
        ),
        maximum_bytes=(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_PROTOCOL_BYTES
        ),
    )
    expected = materialize_posebusters_vina_sulfur_invariance_protocol(
        preparation_receipt_path,
        preparation_artifact_root,
        vina_execution_receipt_path,
        vina_artifact_root,
        openbabel_comparison_receipt_path,
        vina_source_root,
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_vina_execution_receipt_sha256=(
            expected_vina_execution_receipt_sha256
        ),
        expected_openbabel_comparison_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
        registered_utc=raw.get("registered_utc"),
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance protocol failed exact re-registration"
        )
    return expected


class _VinaScoreRuntimeProtocol(Protocol):
    identity: Mapping[str, Any]

    def score_models(
        self,
        receptor_pdbqt: bytes,
        pocket_center_binary64_hex: Sequence[str],
        original_models: Sequence[bytes],
        counterfactual_models: Sequence[bytes],
    ) -> tuple[
        tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
        str,
        int,
    ]: ...


def _private_scratch_root(path: Path) -> Path:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.lstat()
    except OSError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance scratch root is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance scratch root must be mode 0700"
        )
    return path


class _VinaScoreRuntime:
    def __init__(
        self,
        *,
        Vina: Any,
        identity: Mapping[str, Any],
        scratch_root: Path,
    ) -> None:
        self._Vina = Vina
        self.identity = dict(identity)
        self._scratch_root = _private_scratch_root(scratch_root)

    def _engine(
        self,
        receptor_path: Path,
        initial_ligand: bytes,
        center: Sequence[float],
        sink: _DigestingTextSink,
    ) -> Any:
        try:
            ligand_text = initial_ligand.decode("ascii")
        except UnicodeDecodeError as exc:
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina score ligand is not ASCII"
            ) from exc
        with redirect_stdout(sink), redirect_stderr(sink):
            engine = self._Vina(
                sf_name=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                    "scoring_function"
                ],
                cpu=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION["cpu_count"],
                seed=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION["seed"],
                no_refine=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                    "no_refine"
                ],
                verbosity=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                    "verbosity"
                ],
            )
            engine.set_receptor(str(receptor_path))
            engine.set_ligand_from_string(ligand_text)
            engine.compute_vina_maps(
                center=list(center),
                box_size=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                    "box_size_angstrom"
                ],
                spacing=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                    "spacing_angstrom"
                ],
                force_even_voxels=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                    "force_even_voxels"
                ],
            )
        return engine

    def score_models(
        self,
        receptor_pdbqt: bytes,
        pocket_center_binary64_hex: Sequence[str],
        original_models: Sequence[bytes],
        counterfactual_models: Sequence[bytes],
    ) -> tuple[
        tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
        str,
        int,
    ]:
        if (
            not original_models
            or len(original_models) != len(counterfactual_models)
        ):
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina score model pairs are incomplete"
            )
        center = [
            float.fromhex(str(value))
            for value in pocket_center_binary64_hex
        ]
        if len(center) != 3 or not all(math.isfinite(value) for value in center):
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina score pocket center is invalid"
            )
        sink = _DigestingTextSink()
        with tempfile.TemporaryDirectory(
            prefix="vina-sulfur-invariance-",
            dir=self._scratch_root,
        ) as temporary:
            receptor_path = Path(temporary) / "receptor.pdbqt"
            descriptor = os.open(
                receptor_path,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o600,
            )
            try:
                observed = 0
                while observed < len(receptor_pdbqt):
                    written = os.write(
                        descriptor,
                        receptor_pdbqt[observed:],
                    )
                    if written < 1:
                        raise PoseBustersVinaSulfurInvarianceError(
                            "Vina receptor staging made no progress"
                        )
                    observed += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            original_engine = self._engine(
                receptor_path,
                original_models[0],
                center,
                sink,
            )
            counterfactual_engine = self._engine(
                receptor_path,
                counterfactual_models[0],
                center,
                sink,
            )
            results: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
            for original, counterfactual in zip(
                original_models,
                counterfactual_models,
                strict=True,
            ):
                scores: list[tuple[str, ...]] = []
                for engine, model in (
                    (original_engine, original),
                    (counterfactual_engine, counterfactual),
                ):
                    try:
                        text = model.decode("ascii")
                    except UnicodeDecodeError as exc:
                        raise PoseBustersVinaSulfurInvarianceError(
                            "Vina score model is not ASCII"
                        ) from exc
                    with redirect_stdout(sink), redirect_stderr(sink):
                        engine.set_ligand_from_string(text)
                        values = engine.score()
                    row = tuple(
                        _float_hex(float(value), name="Vina score component")
                        for value in values
                    )
                    if len(row) != len(
                        POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_COMPONENTS
                    ):
                        raise PoseBustersVinaSulfurInvarianceError(
                            "Vina public score component count is invalid"
                        )
                    scores.append(row)
                results.append((scores[0], scores[1]))
        return tuple(results), sink.sha256, sink.size_bytes


def _load_score_runtime(
    scratch_root: str | os.PathLike[str],
) -> _VinaScoreRuntime:
    runtime = _load_vina_runtime(Path(scratch_root))
    Vina = getattr(runtime, "_Vina", None)
    if Vina is None:
        raise PoseBustersVinaSulfurInvarianceError(
            "pinned Vina runtime does not expose its bound API class"
        )
    return _VinaScoreRuntime(
        Vina=Vina,
        identity=runtime.identity.to_dict(),
        scratch_root=Path(scratch_root),
    )


def _observed_scope_case(
    *,
    protocol_row: Mapping[str, Any],
    receptor_payload: bytes,
    pose_payload: bytes,
    runtime: _VinaScoreRuntimeProtocol,
) -> dict[str, Any]:
    case_id = str(protocol_row.get("case_id"))
    target = protocol_row.get("target_comparison")
    if not isinstance(target, dict):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} protocol target binding is invalid"
        )
    target_serial = _positive_int(
        target.get("pdbqt_serial"),
        name="target PDBQT serial",
    )
    models = _split_vina_pose_models(pose_payload)
    if len(models) != protocol_row.get("pose_count"):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} pose count changed after registration"
        )
    expected_model_hashes = protocol_row.get("pose_model_sha256")
    if (
        not isinstance(expected_model_hashes, list)
        or [
            hashlib.sha256(model).hexdigest() for model in models
        ]
        != expected_model_hashes
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} pose model identities changed after registration"
        )
    variants = tuple(
        _mutate_target_sa_to_s(model, target_serial=target_serial)
        for model in models
    )
    if any(
        _non_type_projection_sha256(original, target_serial=target_serial)
        != _non_type_projection_sha256(variant, target_serial=target_serial)
        for original, variant in zip(models, variants, strict=True)
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} counterfactual changed a non-type field"
        )
    score_pairs, diagnostic_sha256, diagnostic_size_bytes = (
        runtime.score_models(
            receptor_payload,
            protocol_row.get("pocket_center_binary64_hex", ()),
            models,
            variants,
        )
    )
    if len(score_pairs) != len(models):
        raise PoseBustersVinaSulfurInvarianceError(
            f"{case_id} runtime score result count is incomplete"
        )
    score_rows: list[dict[str, Any]] = []
    exact_equal_count = 0
    maximum_absolute_delta = 0.0
    for index, (original, variant, scores) in enumerate(
        zip(models, variants, score_pairs, strict=True),
        start=1,
    ):
        original_scores, variant_scores = scores
        if (
            len(original_scores)
            != len(POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_COMPONENTS)
            or len(variant_scores) != len(original_scores)
        ):
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} score component rows are invalid"
            )
        deltas = tuple(
            abs(float.fromhex(first) - float.fromhex(second))
            for first, second in zip(
                original_scores,
                variant_scores,
                strict=True,
            )
        )
        exact_equal = original_scores == variant_scores
        exact_equal_count += int(exact_equal)
        maximum_absolute_delta = max(maximum_absolute_delta, *deltas)
        score_rows.append(
            {
                "schema_id": (
                    POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_SCHEMA_ID
                ),
                "pose_index": index,
                "original_model_sha256": hashlib.sha256(original).hexdigest(),
                "counterfactual_model_sha256": hashlib.sha256(
                    variant
                ).hexdigest(),
                "non_type_projection_sha256": (
                    _non_type_projection_sha256(
                        original,
                        target_serial=target_serial,
                    )
                ),
                "original_target_type": "SA",
                "counterfactual_target_type": "S",
                "original_score_binary64_hex": list(original_scores),
                "counterfactual_score_binary64_hex": list(variant_scores),
                "component_exact_equal": [
                    first == second
                    for first, second in zip(
                        original_scores,
                        variant_scores,
                        strict=True,
                    )
                ],
                "all_components_exact_equal": exact_equal,
                "maximum_absolute_score_delta_kcal_per_mol_binary64_hex": (
                    _float_hex(max(deltas), name="pose score delta")
                ),
            }
        )
    case_pass = exact_equal_count == len(models)
    return {
        "schema_id": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID
        ),
        "case_id": case_id,
        "protocol_status": protocol_row.get("status"),
        "status": "evaluated",
        "disposition_code": (
            "default_vina_fixed_pose_score_invariance_evaluated"
        ),
        "environment": protocol_row.get("environment"),
        "target_comparison": dict(target),
        "rescoring_attempted": True,
        "pose_count": len(models),
        "exact_equal_pose_count": exact_equal_count,
        "all_pose_components_exact_equal": case_pass,
        "default_vina_fixed_pose_score_invariance_pass": case_pass,
        "maximum_absolute_score_delta_kcal_per_mol_binary64_hex": (
            _float_hex(
                maximum_absolute_delta,
                name="case score delta",
            )
        ),
        "score_rows": score_rows,
        "diagnostic_sha256": diagnostic_sha256,
        "diagnostic_size_bytes": _positive_int(
            diagnostic_size_bytes,
            name="Vina score diagnostic size",
            allow_zero=True,
        ),
        "chemical_acceptor_semantics_adjudicated": False,
        "ad4_scoring_evaluated": False,
        "error_code": None,
        "error_type": None,
        "error_message_sha256": None,
    }


def _observation_payload(
    *,
    observation_utc: str,
    protocol: Mapping[str, Any],
    protocol_file_sha256: str,
    runtime: _VinaScoreRuntimeProtocol,
    case_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in case_rows]
    evaluated = [row for row in rows if row.get("status") == "evaluated"]
    failures = [row for row in rows if row.get("status") == "score_failure"]
    pose_count = sum(int(row.get("pose_count", 0)) for row in evaluated)
    exact_pose_count = sum(
        int(row.get("exact_equal_pose_count", 0)) for row in evaluated
    )
    pass_value = (
        len(evaluated)
        == len(POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE_CASE_IDS)
        and not failures
        and pose_count > 0
        and exact_pose_count == pose_count
        and all(
            row.get("default_vina_fixed_pose_score_invariance_pass") is True
            for row in evaluated
        )
    )
    payload = {
        "schema_id": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID
        ),
        "observation_utc": observation_utc,
        "protocol_receipt_sha256": protocol["receipt_sha256"],
        "protocol_receipt_file_sha256": protocol_file_sha256,
        "protocol_registered_before_rescoring": True,
        "preparation_receipt_sha256": (
            protocol["preparation_receipt_sha256"]
        ),
        "vina_execution_receipt_sha256": (
            protocol["vina_execution_receipt_sha256"]
        ),
        "openbabel_comparison_receipt_sha256": (
            protocol["openbabel_comparison_receipt_sha256"]
        ),
        "configuration": protocol["configuration"],
        "configuration_sha256": protocol["configuration_sha256"],
        "vina_source_binding": protocol["vina_source_binding"],
        "vina_runtime_identity": dict(runtime.identity),
        "vina_runtime_identity_sha256": _canonical_sha256(runtime.identity),
        "implementation_source_members": (
            protocol["implementation_source_members"]
        ),
        "implementation_source_sha256": (
            protocol["implementation_source_sha256"]
        ),
        "all_case_denominator": len(rows),
        "scope_case_count": len(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE_CASE_IDS
        ),
        "evaluated_case_count": len(evaluated),
        "score_failure_case_count": len(failures),
        "scope_abstention_case_count": sum(
            row.get("status") == "abstain_protocol_scope" for row in rows
        ),
        "evaluated_pose_count": pose_count,
        "exact_equal_pose_count": exact_pose_count,
        "case_rows": rows,
        "source_semantics_invariance_supported": True,
        "default_vina_fixed_pose_score_invariance_pass": pass_value,
        "bounded_default_vina_invariance_claim_safe": pass_value,
        "chemical_acceptor_semantics_adjudicated": False,
        "ad4_scoring_evaluated": False,
        "docking_search_reexecuted": False,
        "scientifically_validated": False,
        "benchmark_executed": False,
        "product_promotion_allowed": False,
        "scientific_blockers": list(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCIENTIFIC_BLOCKERS
        ),
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_vina_sulfur_invariance_observation(
    protocol_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_execution_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_protocol_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_vina_execution_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
    observation_utc: str,
    runtime: _VinaScoreRuntimeProtocol | None = None,
) -> dict[str, Any]:
    """Rescore every preregistered pose under the exact SA/S mutation."""

    observed_utc = _utc_timestamp(observation_utc, name="observation UTC")
    protocol = verify_posebusters_vina_sulfur_invariance_protocol(
        protocol_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        vina_execution_receipt_path,
        vina_artifact_root,
        openbabel_comparison_receipt_path,
        vina_source_root,
        expected_protocol_receipt_sha256=(
            expected_protocol_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_vina_execution_receipt_sha256=(
            expected_vina_execution_receipt_sha256
        ),
        expected_openbabel_comparison_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
    )
    protocol_source = _read_exact_regular_file(
        protocol_receipt_path,
        maximum_bytes=(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_PROTOCOL_BYTES
        ),
    )
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
        vina_receipt, vina_payloads = _load_vina_receipt(
            vina_execution_receipt_path,
            vina_artifact_root,
            expected_receipt_sha256=expected_vina_execution_receipt_sha256,
            expected_preparation_receipt_sha256=(
                preparation.receipt_sha256
            ),
            expected_preparation_receipt_file_sha256=(
                preparation.receipt_file_sha256
            ),
            expected_preparation_artifact_set_sha256=(
                preparation.artifact_set_sha256
            ),
        )
    except ValueError as exc:
        raise PoseBustersVinaSulfurInvarianceError(
            "observation-time upstream artifacts are invalid"
        ) from exc
    active_runtime = runtime or _load_score_runtime(scratch_root)
    if (
        not isinstance(active_runtime.identity, Mapping)
        or dict(active_runtime.identity)
        != protocol.get("vina_engine_identity")
        or _canonical_sha256(active_runtime.identity)
        != protocol.get("vina_engine_identity_sha256")
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "observation Vina runtime is not the preregistered identity"
        )

    preparation_rows = {
        row.case_id: row for row in preparation.case_rows
    }
    vina_rows = {row.case_id: row for row in vina_receipt.case_rows}
    protocol_rows = protocol.get("case_rows")
    if (
        not isinstance(protocol_rows, list)
        or len(protocol_rows)
        != POSEBUSTERS_VINA_SULFUR_INVARIANCE_ALL_CASE_DENOMINATOR
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance protocol denominator is invalid"
        )
    observed_rows: list[dict[str, Any]] = []
    for protocol_row in protocol_rows:
        if not isinstance(protocol_row, dict):
            raise PoseBustersVinaSulfurInvarianceError(
                "Vina sulfur-invariance protocol case row is invalid"
            )
        case_id = str(protocol_row.get("case_id"))
        if case_id not in POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE:
            observed_rows.append(
                {
                    "schema_id": (
                        POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID
                    ),
                    "case_id": case_id,
                    "protocol_status": protocol_row.get("status"),
                    "status": "abstain_protocol_scope",
                    "disposition_code": protocol_row.get(
                        "disposition_code"
                    ),
                    "rescoring_attempted": False,
                    "pose_count": 0,
                    "default_vina_fixed_pose_score_invariance_pass": None,
                    "chemical_acceptor_semantics_adjudicated": False,
                    "ad4_scoring_evaluated": False,
                    "error_code": None,
                    "error_type": None,
                    "error_message_sha256": None,
                }
            )
            continue
        prepared = preparation_rows.get(case_id)
        vina_case = vina_rows.get(case_id)
        if (
            prepared is None
            or vina_case is None
            or vina_case.artifact is None
        ):
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} disappeared from the exact upstream denominator"
            )
        receptor = _artifact_by_role(
            prepared,
            "prepared_receptor_pdbqt",
        )
        receptor_payload = prepared_payloads.get(receptor.relative_path)
        pose_payload = vina_payloads.get(vina_case.artifact.relative_path)
        if receptor_payload is None or pose_payload is None:
            raise PoseBustersVinaSulfurInvarianceError(
                f"{case_id} exact rescoring payload is unavailable"
            )
        try:
            observed_rows.append(
                _observed_scope_case(
                    protocol_row=protocol_row,
                    receptor_payload=receptor_payload,
                    pose_payload=pose_payload,
                    runtime=active_runtime,
                )
            )
        except Exception as exc:
            normalized = _normalized_error(exc)
            observed_rows.append(
                {
                    "schema_id": (
                        POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID
                    ),
                    "case_id": case_id,
                    "protocol_status": protocol_row.get("status"),
                    "status": "score_failure",
                    "disposition_code": (
                        "default_vina_sulfur_type_rescoring_failed"
                    ),
                    "rescoring_attempted": True,
                    "pose_count": 0,
                    "default_vina_fixed_pose_score_invariance_pass": False,
                    "chemical_acceptor_semantics_adjudicated": False,
                    "ad4_scoring_evaluated": False,
                    "error_code": (
                        "default_vina_sulfur_type_rescoring_failed"
                    ),
                    "error_type": type(exc).__name__,
                    "error_message_sha256": hashlib.sha256(
                        normalized
                    ).hexdigest(),
                }
            )
    if (
        tuple(row["case_id"] for row in observed_rows)
        != tuple(sorted(row["case_id"] for row in observed_rows))
        or len({row["case_id"] for row in observed_rows})
        != len(observed_rows)
    ):
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance observation rows are not canonical"
        )
    return _observation_payload(
        observation_utc=observed_utc,
        protocol=protocol,
        protocol_file_sha256=hashlib.sha256(protocol_source).hexdigest(),
        runtime=active_runtime,
        case_rows=observed_rows,
    )


def verify_posebusters_vina_sulfur_invariance_observation(
    observation_receipt_path: str | os.PathLike[str],
    protocol_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    vina_execution_receipt_path: str | os.PathLike[str],
    vina_artifact_root: str | os.PathLike[str],
    openbabel_comparison_receipt_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_observation_receipt_sha256: str,
    expected_protocol_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_vina_execution_receipt_sha256: str,
    expected_openbabel_comparison_receipt_sha256: str,
) -> dict[str, Any]:
    raw, source = _read_private_canonical_receipt(
        observation_receipt_path,
        expected_receipt_sha256=(
            expected_observation_receipt_sha256
        ),
        expected_schema_id=(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID
        ),
        maximum_bytes=(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_MAX_OBSERVATION_BYTES
        ),
    )
    expected = materialize_posebusters_vina_sulfur_invariance_observation(
        protocol_receipt_path,
        preparation_receipt_path,
        preparation_artifact_root,
        vina_execution_receipt_path,
        vina_artifact_root,
        openbabel_comparison_receipt_path,
        vina_source_root,
        scratch_root,
        expected_protocol_receipt_sha256=(
            expected_protocol_receipt_sha256
        ),
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_vina_execution_receipt_sha256=(
            expected_vina_execution_receipt_sha256
        ),
        expected_openbabel_comparison_receipt_sha256=(
            expected_openbabel_comparison_receipt_sha256
        ),
        observation_utc=raw.get("observation_utc"),
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersVinaSulfurInvarianceError(
            "Vina sulfur-invariance observation failed exact reexecution"
        )
    return expected


def _add_common_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preparation-receipt", required=True)
    parser.add_argument("--preparation-artifact-root", required=True)
    parser.add_argument("--vina-execution-receipt", required=True)
    parser.add_argument("--vina-artifact-root", required=True)
    parser.add_argument("--openbabel-comparison-receipt", required=True)
    parser.add_argument("--vina-source-root", required=True)
    parser.add_argument(
        "--expected-preparation-receipt-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-vina-execution-receipt-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-openbabel-comparison-receipt-sha256",
        required=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "preregister and execute the failure-inclusive default-Vina "
            "neutral-thioether S/SA fixed-pose score invariance audit"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register")
    _add_common_cli_arguments(register)
    register.add_argument("--registered-utc", required=True)
    register.add_argument("--output", required=True)

    verify_protocol = subparsers.add_parser("verify-protocol")
    _add_common_cli_arguments(verify_protocol)
    verify_protocol.add_argument("--protocol-receipt", required=True)
    verify_protocol.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )

    observe = subparsers.add_parser("observe")
    _add_common_cli_arguments(observe)
    observe.add_argument("--protocol-receipt", required=True)
    observe.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )
    observe.add_argument("--scratch-root", required=True)
    observe.add_argument("--observation-utc", required=True)
    observe.add_argument("--output", required=True)

    verify_observation = subparsers.add_parser("verify-observation")
    _add_common_cli_arguments(verify_observation)
    verify_observation.add_argument("--protocol-receipt", required=True)
    verify_observation.add_argument(
        "--expected-protocol-receipt-sha256",
        required=True,
    )
    verify_observation.add_argument("--observation-receipt", required=True)
    verify_observation.add_argument(
        "--expected-observation-receipt-sha256",
        required=True,
    )
    verify_observation.add_argument("--scratch-root", required=True)
    return parser


def _cli_common(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "vina_execution_receipt_path": args.vina_execution_receipt,
        "vina_artifact_root": args.vina_artifact_root,
        "openbabel_comparison_receipt_path": (
            args.openbabel_comparison_receipt
        ),
        "vina_source_root": args.vina_source_root,
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
        "expected_vina_execution_receipt_sha256": (
            args.expected_vina_execution_receipt_sha256
        ),
        "expected_openbabel_comparison_receipt_sha256": (
            args.expected_openbabel_comparison_receipt_sha256
        ),
    }


def _cli_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_id",
        "receipt_sha256",
        "all_case_denominator",
        "scope_case_count",
        "scope_pose_count",
        "evaluated_case_count",
        "evaluated_pose_count",
        "exact_equal_pose_count",
        "score_failure_case_count",
        "scope_abstention_case_count",
        "default_vina_fixed_pose_score_invariance_pass",
        "bounded_default_vina_invariance_claim_safe",
        "chemical_acceptor_semantics_adjudicated",
        "claim_safe",
    )
    return {key: receipt[key] for key in keys if key in receipt}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = _cli_common(args)
    if args.command == "register":
        receipt = materialize_posebusters_vina_sulfur_invariance_protocol(
            **common,
            registered_utc=args.registered_utc,
        )
        _write_private_no_overwrite(receipt, args.output)
    elif args.command == "verify-protocol":
        receipt = verify_posebusters_vina_sulfur_invariance_protocol(
            args.protocol_receipt,
            **common,
            expected_protocol_receipt_sha256=(
                args.expected_protocol_receipt_sha256
            ),
        )
    elif args.command == "observe":
        receipt = materialize_posebusters_vina_sulfur_invariance_observation(
            args.protocol_receipt,
            **common,
            scratch_root=args.scratch_root,
            expected_protocol_receipt_sha256=(
                args.expected_protocol_receipt_sha256
            ),
            observation_utc=args.observation_utc,
        )
        _write_private_no_overwrite(receipt, args.output)
    elif args.command == "verify-observation":
        receipt = verify_posebusters_vina_sulfur_invariance_observation(
            args.observation_receipt,
            args.protocol_receipt,
            **common,
            scratch_root=args.scratch_root,
            expected_observation_receipt_sha256=(
                args.expected_observation_receipt_sha256
            ),
            expected_protocol_receipt_sha256=(
                args.expected_protocol_receipt_sha256
            ),
        )
    else:  # pragma: no cover
        raise AssertionError("unreachable command")
    print(
        json.dumps(
            _cli_summary(receipt),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_ALL_CASE_DENOMINATOR",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCOPE_CASE_IDS",
    "POSEBUSTERS_VINA_SULFUR_INVARIANCE_SCORE_SCHEMA_ID",
    "PoseBustersVinaSulfurInvarianceError",
    "main",
    "materialize_posebusters_vina_sulfur_invariance_observation",
    "materialize_posebusters_vina_sulfur_invariance_protocol",
    "verify_posebusters_vina_sulfur_invariance_observation",
    "verify_posebusters_vina_sulfur_invariance_protocol",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

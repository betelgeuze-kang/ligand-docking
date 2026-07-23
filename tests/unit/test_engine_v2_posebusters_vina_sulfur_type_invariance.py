from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION,
    POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256,
    PoseBustersVinaSulfurInvarianceError,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_corpus_audit import (
    _canonical_sha256,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_vina_sulfur_type_invariance import (
    POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID,
    POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID,
    POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID,
    _mutate_target_sa_to_s,
    _non_type_projection_sha256,
    _observation_payload,
    _observed_scope_case,
    _parser,
    _pdbqt_atom_type,
    _read_private_canonical_receipt,
    _split_vina_pose_models,
    _vina_source_binding,
    _write_private_no_overwrite,
)


_TARGET_LINE = (
    b"ATOM     13  S   UNL     1      30.441 -11.116  60.160"
    b"  1.00  0.00    -0.165 SA\n"
)


def _model(*, shift: float = 0.0) -> bytes:
    line = bytearray(_TARGET_LINE)
    if shift:
        token = f"{30.441 + shift:8.3f}".encode("ascii")
        line[30:38] = token
    return b"ROOT\n" + bytes(line) + b"ENDROOT\nTORSDOF 0\n"


def _pose_artifact(count: int = 1) -> bytes:
    return b"".join(
        b"MODEL "
        + str(index).encode("ascii")
        + b"\n"
        + _model(shift=float(index - 1))
        + b"ENDMDL\n"
        for index in range(1, count + 1)
    )


class _FakeRuntime:
    def __init__(self, *, equal: bool = True) -> None:
        self.identity = {"engine_id": "vina", "engine_version": "1.2.7"}
        self.equal = equal

    def score_models(
        self,
        receptor_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
        original_models: tuple[bytes, ...],
        counterfactual_models: tuple[bytes, ...],
    ):
        assert receptor_pdbqt == b"RECEPTOR\n"
        assert tuple(pocket_center_binary64_hex) == (
            "0x0.0p+0",
            "0x0.0p+0",
            "0x0.0p+0",
        )
        rows = []
        for original, counterfactual in zip(
            original_models,
            counterfactual_models,
            strict=True,
        ):
            assert _pdbqt_atom_type(original, target_serial=13) == "SA"
            assert _pdbqt_atom_type(counterfactual, target_serial=13) == "S"
            baseline = tuple(float(index).hex() for index in range(8))
            variant = baseline
            if not self.equal:
                variant = (float(0.001).hex(), *baseline[1:])
            rows.append((baseline, variant))
        return tuple(rows), hashlib.sha256(b"").hexdigest(), 0


def _protocol_row(pose_payload: bytes) -> dict[str, object]:
    models = _split_vina_pose_models(pose_payload)
    return {
        "schema_id": POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID,
        "case_id": "7CIJ_G0C",
        "status": "registered",
        "environment": "aliphatic_thioether",
        "target_comparison": {
            "pdbqt_serial": 13,
            "element_symbol": "S",
            "meeko_ad4_atom_type": "SA",
            "openbabel_ad4_atom_type": "S",
        },
        "pocket_center_binary64_hex": [
            "0x0.0p+0",
            "0x0.0p+0",
            "0x0.0p+0",
        ],
        "pose_count": len(models),
        "pose_model_sha256": [
            hashlib.sha256(model).hexdigest() for model in models
        ],
    }


def test_exact_sa_to_s_mutation_changes_only_target_type() -> None:
    assert _canonical_sha256(
        POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION
    ) == POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256
    artifact = _pose_artifact(2)
    models = _split_vina_pose_models(artifact)

    assert len(models) == 2
    for model in models:
        variant = _mutate_target_sa_to_s(model, target_serial=13)
        assert len(variant) == len(model)
        assert _pdbqt_atom_type(model, target_serial=13) == "SA"
        assert _pdbqt_atom_type(variant, target_serial=13) == "S"
        assert _non_type_projection_sha256(
            model,
            target_serial=13,
        ) == _non_type_projection_sha256(
            variant,
            target_serial=13,
        )

    with pytest.raises(PoseBustersVinaSulfurInvarianceError):
        _split_vina_pose_models(artifact.replace(b"MODEL 2", b"MODEL 3"))
    with pytest.raises(PoseBustersVinaSulfurInvarianceError):
        _mutate_target_sa_to_s(models[0].replace(b" SA\n", b" S \n"), target_serial=13)


def test_exact_score_equality_is_the_only_bounded_pass() -> None:
    artifact = _pose_artifact(2)
    exact = _observed_scope_case(
        protocol_row=_protocol_row(artifact),
        receptor_payload=b"RECEPTOR\n",
        pose_payload=artifact,
        runtime=_FakeRuntime(equal=True),
    )
    changed = _observed_scope_case(
        protocol_row=_protocol_row(artifact),
        receptor_payload=b"RECEPTOR\n",
        pose_payload=artifact,
        runtime=_FakeRuntime(equal=False),
    )

    assert exact["pose_count"] == 2
    assert exact["exact_equal_pose_count"] == 2
    assert exact["default_vina_fixed_pose_score_invariance_pass"] is True
    assert exact["maximum_absolute_score_delta_kcal_per_mol_binary64_hex"] == "0x0.0p+0"
    assert changed["exact_equal_pose_count"] == 0
    assert changed["default_vina_fixed_pose_score_invariance_pass"] is False
    assert changed["chemical_acceptor_semantics_adjudicated"] is False
    assert changed["ad4_scoring_evaluated"] is False


def test_observation_keeps_bounded_and_broad_claims_separate() -> None:
    evaluated = []
    for case_id in ("7CIJ_G0C", "7LT0_ONJ", "7NLV_UJE"):
        evaluated.append(
            {
                "schema_id": POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID,
                "case_id": case_id,
                "status": "evaluated",
                "pose_count": 20,
                "exact_equal_pose_count": 20,
                "default_vina_fixed_pose_score_invariance_pass": True,
            }
        )
    abstentions = [
        {
            "schema_id": POSEBUSTERS_VINA_SULFUR_INVARIANCE_CASE_SCHEMA_ID,
            "case_id": f"{index:04d}_AAA",
            "status": "abstain_protocol_scope",
            "pose_count": 0,
        }
        for index in range(305)
    ]
    protocol = {
        "receipt_sha256": "a" * 64,
        "preparation_receipt_sha256": "b" * 64,
        "vina_execution_receipt_sha256": "c" * 64,
        "openbabel_comparison_receipt_sha256": "d" * 64,
        "configuration": POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_CONFIGURATION_SHA256
        ),
        "vina_source_binding": {"source_tag": "v1.2.7"},
        "implementation_source_members": {},
        "implementation_source_sha256": _canonical_sha256({}),
    }
    runtime = _FakeRuntime()

    receipt = _observation_payload(
        observation_utc="2026-07-23T00:00:01Z",
        protocol=protocol,
        protocol_file_sha256="e" * 64,
        runtime=runtime,
        case_rows=[*evaluated, *abstentions],
    )

    assert receipt["schema_id"] == (
        POSEBUSTERS_VINA_SULFUR_INVARIANCE_OBSERVATION_SCHEMA_ID
    )
    assert receipt["all_case_denominator"] == 308
    assert receipt["evaluated_pose_count"] == 60
    assert receipt["exact_equal_pose_count"] == 60
    assert receipt["default_vina_fixed_pose_score_invariance_pass"] is True
    assert receipt["bounded_default_vina_invariance_claim_safe"] is True
    assert receipt["chemical_acceptor_semantics_adjudicated"] is False
    assert receipt["scientifically_validated"] is False
    assert receipt["benchmark_executed"] is False
    assert receipt["claim_safe"] is False


def test_source_binding_requires_exact_files_and_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = {
        "src/lib/atom_constants.h": (
            b"case AD_TYPE_SA   : return EL_TYPE_S;\n"
            b"case AD_TYPE_S    : return EL_TYPE_S;\n"
            b"inline bool xs_is_acceptor(sz xs) {\n"
            b"return xs == XS_TYPE_N_A || xs == XS_TYPE_O_DA;\n}\n"
        ),
        "src/lib/model.cpp": (
            b"case EL_TYPE_S    : x = XS_TYPE_S_P; break;\n"
        ),
        "src/lib/potentials.h": (
            b"if (xs_h_bond_possible(a.xs, b.xs))\n"
        ),
        "src/lib/scoring_function.h": (
            b"m_atom_typing = atom_type::XS;\n"
        ),
        "src/lib/vina.h": b"v1.2.7\n",
    }
    for relative, payload in payloads.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark."
        "public_posebusters_vina_sulfur_type_invariance."
        "POSEBUSTERS_VINA_SULFUR_INVARIANCE_VINA_SOURCE_FILES",
        {
            relative: hashlib.sha256(payload).hexdigest()
            for relative, payload in payloads.items()
        },
    )

    binding = _vina_source_binding(tmp_path)
    assert binding["semantic_projection"]["ad_s_element_type"] == "EL_TYPE_S"
    assert binding["semantic_projection"]["ad_sa_element_type"] == "EL_TYPE_S"
    assert binding["semantic_projection"]["element_s_xs_type"] == "XS_TYPE_S_P"
    assert binding["semantic_projection"]["xs_type_s_p_is_acceptor"] is False

    (tmp_path / "src/lib/model.cpp").write_bytes(b"tampered\n")
    with pytest.raises(PoseBustersVinaSulfurInvarianceError):
        _vina_source_binding(tmp_path)


def test_receipts_are_private_canonical_and_no_overwrite(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_id": POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID,
        "value": 1,
    }
    receipt = {**payload, "receipt_sha256": _canonical_sha256(payload)}
    path = tmp_path / "receipt.json"

    _write_private_no_overwrite(receipt, path)
    loaded, source = _read_private_canonical_receipt(
        path,
        expected_receipt_sha256=receipt["receipt_sha256"],
        expected_schema_id=(
            POSEBUSTERS_VINA_SULFUR_INVARIANCE_PROTOCOL_SCHEMA_ID
        ),
        maximum_bytes=4096,
    )

    assert loaded == receipt
    assert source.endswith(b"\n")
    assert stat_mode(path) == 0o600
    with pytest.raises(PoseBustersVinaSulfurInvarianceError):
        _write_private_no_overwrite(receipt, path)


def stat_mode(path: Path) -> int:
    return os.stat(path, follow_symlinks=False).st_mode & 0o777


def test_cli_exposes_preregistration_and_exact_verification() -> None:
    help_text = _parser().format_help()
    assert "register" in help_text
    assert "verify-protocol" in help_text
    assert "observe" in help_text
    assert "verify-observation" in help_text

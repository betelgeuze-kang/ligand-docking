from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

import betelgeuze_engine_v2.benchmark.source_paired_clearance_activation as activation_module
import betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_full_evidence as full_module
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_full_evidence import (
    build_full_comparison_evidence_artifact,
    build_result_document_from_full_evidence_file,
    verify_full_comparison_evidence_artifact,
)


_FIXTURES = runpy.run_path(
    str(Path(__file__).with_name("test_source_paired_clearance_activation_evidence.py"))
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _run_start(*, suffix: str = "current") -> dict[str, object]:
    return {
        "policy_sha256": EXPECTED_POLICY_SHA256,
        "receipt_sha256": _digest(f"run-start:{suffix}"),
        "source_commit_git_sha1": "1" * 40,
        "execution_environment_sha256": _digest(f"environment:{suffix}"),
        "required_scorer_backend": "rust_cpu_required",
        "expected_scored_candidate_rows": 1024,
    }


@pytest.fixture
def synthetic_case_authority(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    authority: dict[str, dict[str, str]] = {}
    monkeypatch.setattr(
        activation_module,
        "_FROZEN_CASE_SOURCE_AUTHORITY_BY_CASE",
        authority,
    )
    monkeypatch.setattr(
        activation_module,
        "_frozen_case_source_authority",
        authority.get,
    )
    monkeypatch.setattr(full_module, "_frozen_case_source_authority", authority.get)
    return authority


def test_one_real_case_receipt_is_fully_parsed(
    synthetic_case_authority: dict[str, dict[str, str]],
) -> None:
    del synthetic_case_authority
    evidence = _FIXTURES["_complete_activation_evidence"]()
    receipt = _FIXTURES["_outer"](evidence).to_dict()

    verified = full_module._verify_case_activation_receipt(
        receipt,
        case_id="5SD5_HWI",
    )

    assert len(verified["baseline_rows"]) == 64
    assert len(verified["experimental_rows"]) == 64
    assert verified["selected_indices"] == (evidence["target"],)
    assert verified["baseline_rows"][0]["scorer"]["receipt_sha256"]
    assert len(
        verified["baseline_rows"][0]["posebusters"]["check_results"]
    ) == 22
    assert verified["baseline_rows"][0]["rmsd"] == 1.5


def test_resealed_candidate_score_projection_drift_is_rejected(
    synthetic_case_authority: dict[str, dict[str, str]],
) -> None:
    del synthetic_case_authority
    evidence = _FIXTURES["_complete_activation_evidence"]()
    receipt = _FIXTURES["_outer"](evidence).to_dict()
    candidate = receipt["baseline_arm_ranking"][
        "candidate_rows_by_proposal_index"
    ][0]
    candidate["raw_score_binary64_hex"] = float(99.0).hex()
    candidate["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in candidate.items() if key != "receipt_sha256"}
    )
    ranking = receipt["baseline_arm_ranking"]
    ranking["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in ranking.items() if key != "receipt_sha256"}
    )
    receipt["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )

    with pytest.raises(OneShotABAuthorityError, match="score or RMSD projection"):
        full_module._verify_case_activation_receipt(
            receipt,
            case_id="5SD5_HWI",
        )


def _fake_row(case_id: str, arm: str, index: int, *, changed: bool) -> dict[str, object]:
    identity = f"{case_id}:{arm if changed else 'shared'}:{index}"
    return {
        "payload": {
            "case_id": case_id,
            "arm": arm if changed else "shared",
            "proposal_index": index,
            "identity": identity,
        },
        "receipt_sha256": _digest(f"candidate:{identity}"),
        "candidate_id": f"{case_id}:{index:02d}",
        "proposal_index": index,
        "candidate_fingerprint": _digest(f"proposal:{identity}"),
        "source_fingerprint": _digest(f"source:{case_id}:{index}"),
        "score": float(index),
        "rank": index + 1,
        "rmsd": 1.5 if index == 0 else 3.0,
        "internal_valid": index != 0 or case_id == "6T88_MWQ",
        "internal_checks": {
            "receptor_ligand_clash_free": index != 0,
        },
        "posebusters_valid": index != 0 or case_id == "6T88_MWQ",
        "exact_valid": index == 0 and case_id == "6T88_MWQ",
        "scorer": {},
        "internal": {},
        "posebusters": {},
        "rmsd_evidence": {},
    }


def _fake_cases() -> dict[str, dict[str, object]]:
    cases: dict[str, dict[str, object]] = {}
    for case_position, case_id in enumerate(SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS):
        changed_index = 1 if case_position < 2 else None
        baseline = tuple(
            _fake_row(case_id, "baseline", index, changed=False)
            for index in range(64)
        )
        experimental = tuple(
            _fake_row(
                case_id,
                "experimental",
                index,
                changed=index == changed_index,
            )
            if index == changed_index
            else copy.deepcopy(baseline[index])
            for index in range(64)
        )
        case_receipt_sha256 = _digest(f"case-receipt:{case_id}")
        cases[case_id] = {
            "payload": {"case_id": case_id, "receipt_sha256": case_receipt_sha256},
            "receipt_sha256": case_receipt_sha256,
            "case_source": {},
            "baseline_ranking": {},
            "experimental_ranking": {},
            "baseline_rows": baseline,
            "experimental_rows": experimental,
            "selected_indices": () if changed_index is None else (changed_index,),
            "shadow_eligible_count": 0 if changed_index is None else 1,
            "penetrating_without_validity_change_count": 0,
        }
    return cases


def _patch_fake_case_verifier(
    monkeypatch: pytest.MonkeyPatch,
    cases: dict[str, dict[str, object]],
) -> None:
    def verify(_value: object, *, case_id: str) -> dict[str, object]:
        return copy.deepcopy(cases[case_id])

    monkeypatch.setattr(full_module, "_verify_case_activation_receipt", verify)


def _build_fake_artifact(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, object], dict[str, object]]:
    cases = _fake_cases()
    _patch_fake_case_verifier(monkeypatch, cases)
    run_start = _run_start()
    artifact = build_full_comparison_evidence_artifact(
        run_start=run_start,
        case_activation_receipts=[
            {"case_id": case_id}
            for case_id in SOURCE_PAIRED_CLEARANCE_SCORED_CASE_IDS
        ],
    )
    return artifact, run_start


def test_full_artifact_retains_exact_8_by_64_by_2_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, run_start = _build_fake_artifact(monkeypatch)

    verified = verify_full_comparison_evidence_artifact(
        artifact,
        run_start=run_start,
    )

    assert len(artifact["case_activation_receipts"]) == 8
    assert len(artifact["baseline_arm"]["candidate_bindings"]) == 512
    assert len(artifact["experimental_arm"]["candidate_bindings"]) == 512
    assert verified.changed_slot_count == 2
    assert verified.shadow_eligible_candidate_count == 2
    assert len(set(artifact["baseline_arm"]["candidate_binding_receipt_sha256s"])) == 512
    assert len(set(artifact["experimental_arm"]["candidate_binding_receipt_sha256s"])) == 512


def test_resealed_fabricated_candidate_wrapper_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, run_start = _build_fake_artifact(monkeypatch)
    changed = copy.deepcopy(artifact)
    binding = changed["baseline_arm"]["candidate_bindings"][0]
    binding["candidate_receipt"] = {"fabricated": True}
    binding["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in binding.items() if key != "receipt_sha256"}
    )
    changed["baseline_arm"]["candidate_binding_receipt_sha256s"][0] = binding[
        "receipt_sha256"
    ]
    arm = changed["baseline_arm"]
    arm["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in arm.items() if key != "receipt_sha256"}
    )
    changed["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in changed.items() if key != "receipt_sha256"}
    )

    with pytest.raises(OneShotABAuthorityError, match="fabricated"):
        verify_full_comparison_evidence_artifact(changed, run_start=run_start)


def test_duplicate_candidate_wrapper_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, run_start = _build_fake_artifact(monkeypatch)
    changed = copy.deepcopy(artifact)
    arm = changed["experimental_arm"]
    arm["candidate_bindings"][1] = copy.deepcopy(arm["candidate_bindings"][0])
    arm["candidate_binding_receipt_sha256s"][1] = arm[
        "candidate_binding_receipt_sha256s"
    ][0]
    arm["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in arm.items() if key != "receipt_sha256"}
    )
    changed["receipt_sha256"] = full_module._sha256(
        {key: value for key, value in changed.items() if key != "receipt_sha256"}
    )

    with pytest.raises(
        OneShotABAuthorityError,
        match="cross-wired|missing or duplicated",
    ):
        verify_full_comparison_evidence_artifact(changed, run_start=run_start)


def test_full_artifact_cannot_be_reused_for_another_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, _run_start_value = _build_fake_artifact(monkeypatch)

    with pytest.raises(OneShotABAuthorityError, match="reused across runs"):
        verify_full_comparison_evidence_artifact(
            artifact,
            run_start=_run_start(suffix="other"),
        )


def test_compact_result_is_derived_from_full_file_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact, run_start = _build_fake_artifact(monkeypatch)
    path = tmp_path / "full-evidence.json"
    path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = build_result_document_from_full_evidence_file(
        path,
        run_start=run_start,
    )

    assert result["baseline_arm"]["candidate_count"] == 512
    assert result["experimental_arm"]["candidate_count"] == 512
    assert result["cross_arm"]["changed_slot_count"] == 2
    assert result["fresh_holdout_execution_authorized"] is False
    assert result["product_execution_authorized"] is False
    assert result["public_or_scientific_claim_authorized"] is False

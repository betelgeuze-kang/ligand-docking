from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from api.config import settings
from betelgeuze_product.docking_materialization_errors import DockingMaterializationError
from betelgeuze_product.docking_private_payload import build_store, store_docking_request
from betelgeuze_product.job_orchestration import write_job_record
from betelgeuze_product.private_payload_store import (
    PrivatePayloadKeyring,
    canonical_request_sha256,
)
from betelgeuze_product.scientific_input_provenance import build_scientific_input_provenance
from tools.product.materialize_docking_backmapping_request import (
    materialize_from_docking_request as materialize_backmapping,
)
from tools.product.materialize_docking_htvs_request import (
    materialize_from_docking_request as materialize_htvs,
)


PDB_TEXT = (
    "ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 10.00           N\n"
    "ATOM      2  CA  GLY A   1       1.458   0.000   0.000  1.00 10.00           C\n"
    "END\n"
)


def _manifest(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "target_id": "ADRB2",
        "family": "gpcr",
        "runner_profile_id": "backmapping_scoring.production",
        "execution_mode": "restricted-production",
        "customer_submission_allowed": True,
        "synthetic_input_allowed": False,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
    }


def _raw_request(*, smiles: str = "CCO", pocket_kind: str = "center_box") -> dict:
    request = {
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_content": PDB_TEXT,
        "ligands": [{"ligand_id": "LIG-001", "smiles": smiles}],
    }
    if pocket_kind == "center_box":
        request.update(
            {
                "pocket_center": [1.25, -2.5, 3.75],
                "pocket_box_size": [20.0, 18.0, 16.0],
            }
        )
    elif pocket_kind == "center_radius":
        request.update(
            {
                "pocket_center": [1.25, -2.5, 3.75],
                "pocket_radius_a": 8.5,
            }
        )
    elif pocket_kind == "residue_indices":
        request["pocket_residue_indices"] = [0]
    else:  # pragma: no cover - test helper guard
        raise AssertionError(pocket_kind)
    return request


def _redacted_ligand() -> dict:
    return {
        "ligand_id": "LIG-001",
        "source_kind": "smiles",
        "source_value_sha256": "a" * 64,
        "source_redacted": True,
    }


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    raw_request: dict,
    stored_request: dict | None = None,
) -> tuple[Path, dict, dict]:
    import betelgeuze_product.docking_private_payload as dpp

    job_id = "job-materialization-recheck"
    manifest = _manifest(job_id)
    request_sha256 = canonical_request_sha256(raw_request)
    receipt = build_scientific_input_provenance(
        raw_request,
        request_sha256=request_sha256,
        dispatch_manifest=manifest,
        root=tmp_path,
    )
    assert receipt["execution_input_ready"] is True

    store = build_store(
        keys_config=f"k1:{PrivatePayloadKeyring.generate_secret_b64()}",
        root_dir=tmp_path / "private",
        ttl_seconds=3600,
    )
    assert store is not None
    store_docking_request(
        store,
        job_id=job_id,
        request_sha256=request_sha256,
        request=stored_request or raw_request,
    )
    monkeypatch.setattr(dpp, "configured_store", lambda: store)

    results_root = tmp_path / "results"
    monkeypatch.setattr(settings, "results_storage_path", str(results_root))
    ledger = {
        "job_id": job_id,
        "request_sha256": request_sha256,
        "family": "gpcr",
        "target_id": "ADRB2",
        "ligand_count": 1,
        "private_payload_stored": True,
        "scientific_input_provenance": receipt,
        "scientific_input_provenance_sha256": receipt["receipt_sha256"],
        "engine_dispatch_manifest": manifest,
        "materialization_ligands": [_redacted_ligand()],
        "intake_payload": {
            "family": "gpcr",
            "target_id": "ADRB2",
            "ligand_count": 1,
            "ligands": [_redacted_ligand()],
        },
    }
    jobs_dir = results_root / "product_docking_jobs"
    write_job_record(jobs_dir, ledger)

    params = {
        "docking_job_id": job_id,
        "request_sha256": request_sha256,
        "family": "gpcr",
        "ligand_count": 1,
        "ligands": [_redacted_ligand()],
        "runner_execution_mode": "restricted-production",
        "runner_synthetic_input_allowed": False,
        "allow_synthetic_ligand_input": False,
        "scientific_input_provenance_required": True,
        "scientific_input_provenance": receipt,
        "scientific_input_provenance_sha256": receipt["receipt_sha256"],
        "private_payload_stored": True,
        "engine_dispatch_manifest": manifest,
    }
    request_path = tmp_path / "simulation_request.json"
    request_path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "target_name": "ADRB2",
                "runner_profile_params": params,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return request_path, receipt, ledger


def test_htvs_rechecks_receipt_snapshots_receptor_and_uses_explicit_pocket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, receipt, _ledger = _prepare(
        tmp_path,
        monkeypatch,
        raw_request=_raw_request(pocket_kind="center_box"),
    )

    materialized = materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))

    recheck = materialized["scientific_input_provenance_recheck"]
    assert recheck["verified"] is True
    assert recheck["receipt_sha256"] == receipt["receipt_sha256"]
    assert recheck["pocket_definition_kind"] == "center_box"
    snapshot = materialized["receptor_snapshot"]
    assert Path(snapshot["path"]).read_bytes() == PDB_TEXT.encode("utf-8")
    assert snapshot["sha256"] == receipt["structure"]["source_sha256"]

    with Path(materialized["queue_csv"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert float(row["pocket_x"]) == pytest.approx(1.25)
    assert float(row["pocket_y"]) == pytest.approx(-2.5)
    assert float(row["pocket_z"]) == pytest.approx(3.75)
    assert row["pocket_definition_kind"] == "center_box"
    assert row["pocket_definition_sha256"] == receipt["pocket"]["definition_sha256"]
    assert row["native_pdb_path"] == snapshot["path"]


def test_center_radius_is_materialized_into_trajectory_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, receipt, _ledger = _prepare(
        tmp_path,
        monkeypatch,
        raw_request=_raw_request(pocket_kind="center_radius"),
    )

    materialized = materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))

    with Path(materialized["queue_csv"]).open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["pocket_definition_kind"] == "center_radius"
    assert float(row["pocket_x"]) == pytest.approx(1.25)
    assert float(row["pocket_radius_a"]) == pytest.approx(8.5)
    assert row["pocket_definition_sha256"] == receipt["pocket"]["definition_sha256"]


def test_backmapping_rechecks_same_receipt_without_exposing_raw_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, receipt, _ledger = _prepare(
        tmp_path,
        monkeypatch,
        raw_request=_raw_request(),
    )

    materialized = materialize_backmapping(str(request_path), out_dir=str(tmp_path / "backmap"))

    assert materialized["scientific_input_provenance_recheck"]["verified"] is True
    assert materialized["scientific_input_provenance_recheck"]["receipt_sha256"] == receipt["receipt_sha256"]
    with Path(materialized["queue_csv"]).open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["ligand_smiles"] == "CCO"


def test_materializer_rejects_private_payload_content_changed_after_intake(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _raw_request(smiles="CCO")
    changed = _raw_request(smiles="CCN")
    request_path, _receipt, _ledger = _prepare(
        tmp_path,
        monkeypatch,
        raw_request=original,
        stored_request=changed,
    )

    with pytest.raises(
        DockingMaterializationError,
        match="scientific_input_provenance_recheck_mismatch",
    ):
        materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))


def test_materializer_rejects_residue_indices_until_mapping_contract_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, _receipt, _ledger = _prepare(
        tmp_path,
        monkeypatch,
        raw_request=_raw_request(pocket_kind="residue_indices"),
    )

    with pytest.raises(DockingMaterializationError) as excinfo:
        materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))

    assert excinfo.value.reason_code == "scientific_input_pocket_definition_not_materializable"
    assert excinfo.value.reason_detail == "residue_indices"


def test_required_materialization_rejects_missing_private_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_product.docking_private_payload as dpp

    request_path, _receipt, _ledger = _prepare(
        tmp_path,
        monkeypatch,
        raw_request=_raw_request(),
    )
    monkeypatch.setattr(dpp, "configured_store", lambda: None)

    with pytest.raises(
        DockingMaterializationError,
        match="scientific_input_private_payload_unavailable",
    ):
        materialize_backmapping(str(request_path), out_dir=str(tmp_path / "backmap"))

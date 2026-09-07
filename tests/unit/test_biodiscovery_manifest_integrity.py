from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

from betelgeuze_product.tier_beta_vertical_slice import (
    build_tier_beta_request_from_api,
    run_tier_beta_vertical_slice_job,
)


@pytest.fixture
def manifest_helpers(monkeypatch):
    # Exercise the actual standard-library helpers without importing the engine.
    path = Path(__file__).resolve().parents[2] / "betelgeuze_engine/biodiscovery/manifest.py"
    spec = importlib.util.spec_from_file_location("_standalone_screening_manifest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "betelgeuze_engine.biodiscovery.manifest", module)
    return module


def _payload():
    return {
        "timestamp_utc": "2026-09-07T00:00:00Z",
        "pose_scores": [{"coordinates": [[0.0, 1.0, 2.0]], "score": -2.5}],
        "claim_metadata": {"claim_safe": False},
        "stage_records": [],
    }


def test_finite_representation_is_signed_before_json_save_and_reload(manifest_helpers, tmp_path):
    payload = _payload()
    payload["diagnostics"] = {"missing": float("nan"), "overflow": float("inf"), "nested": (-float("inf"),)}
    signed = manifest_helpers.sign_screening_manifest(payload)
    assert signed["diagnostics"] == {"missing": None, "overflow": None, "nested": [None]}
    assert payload["diagnostics"]["overflow"] == float("inf")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(signed, allow_nan=False), encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert manifest_helpers.verify_screening_manifest(reloaded)
    assert reloaded == signed
    assert reloaded["signature_scope"] == "local_integrity_only_not_external_authority"
    assert reloaded["claim_metadata"]["claim_safe"] is False


@pytest.mark.parametrize("field", ["replay_hash", "content_hash", "signature"])
def test_each_integrity_field_is_verified(manifest_helpers, field):
    manifest = manifest_helpers.sign_screening_manifest(_payload())
    manifest[field] = "0" * 64
    if field != "signature":
        # Even a recomputed outer HMAC cannot conceal a bad inner hash.
        unsigned = {key: value for key, value in manifest.items() if key != "signature"}
        manifest["signature"] = hmac.new(
            manifest_helpers.LOCAL_MANIFEST_KEY.encode(),
            json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(),
            hashlib.sha256,
        ).hexdigest()
    assert not manifest_helpers.verify_screening_manifest(manifest)


@pytest.mark.parametrize("mutation", ["coordinates", "claim", "algorithm", "scope", "nonfinite", "missing_hash"])
def test_modified_or_nonfinite_received_manifest_is_rejected(manifest_helpers, mutation):
    signed = manifest_helpers.sign_screening_manifest(_payload())
    if mutation == "coordinates":
        signed["pose_scores"][0]["coordinates"][0][0] += 1
    elif mutation == "claim":
        signed["claim_metadata"]["claim_safe"] = True
    elif mutation == "algorithm":
        signed["signature_algorithm"] = "none"
    elif mutation == "scope":
        signed["signature_scope"] = "external_authority"
    elif mutation == "nonfinite":
        signed["pose_scores"][0]["score"] = float("nan")
    else:
        del signed["replay_hash"]
    assert not manifest_helpers.verify_screening_manifest(signed)


def test_operational_timings_change_content_but_not_replay(manifest_helpers):
    first = _payload()
    first["execution_observations"] = {"preparation_elapsed_seconds": 0.1, "total_elapsed_seconds": 1.0}
    first["stage_records"] = [{"diagnostics": {"elapsed_seconds": 0.1, "dt_fs": 0.5}}]
    second = deepcopy(first)
    second["timestamp_utc"] = "2026-09-08T00:00:00Z"
    second["execution_observations"]["total_elapsed_seconds"] = 3.0
    second["stage_records"][0]["diagnostics"]["elapsed_seconds"] = 1.0
    a = manifest_helpers.sign_screening_manifest(first)
    b = manifest_helpers.sign_screening_manifest(second)
    assert a["replay_hash"] == b["replay_hash"]
    assert a["content_hash"] != b["content_hash"]
    assert a["signature"] != b["signature"]
    second["stage_records"][0]["diagnostics"]["dt_fs"] = 1.0
    assert manifest_helpers.sign_screening_manifest(second)["replay_hash"] != a["replay_hash"]


def test_signing_a_previous_manifest_rebuilds_all_hashes(manifest_helpers):
    first = manifest_helpers.sign_screening_manifest(_payload())
    first["pose_scores"][0]["coordinates"][0][0] = 4.0
    assert not manifest_helpers.verify_screening_manifest(first)
    second = manifest_helpers.sign_screening_manifest(first)
    assert second["replay_hash"] != first["replay_hash"]
    assert manifest_helpers.verify_screening_manifest(second)


@pytest.fixture
def runner_adapter(monkeypatch):
    package = ModuleType("betelgeuze_engine.biodiscovery")
    package.TierBetaScreening = None
    package.TierBetaScreeningResult = object
    monkeypatch.setitem(sys.modules, package.__name__, package)
    path = Path(__file__).resolve().parents[2] / "betelgeuze_engine/product/runners/tier_beta_service_adapter.py"
    spec = importlib.util.spec_from_file_location("_synthetic_tier_beta_adapter", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("name,value", [
    ("pose_count", 1.75), ("pose_count", 0), ("top_k", True), ("top_k", None),
    ("stability_steps", "bad"), ("stability_steps", -1), ("seed", True), ("seed", 2**31),
    ("seed", float("inf")), ("pocket_residue_indices", [0.9]),
    ("pocket_residue_indices", [False]), ("pocket_residue_indices", "0,1"),
])
def test_compatibility_adapter_rejects_malformed_parameters_before_execution(runner_adapter, nested, name, value):
    params = {name: value}
    payload = {"runner_profile_params": params} if nested else params
    with pytest.raises(ValueError, match=f"invalid_{name}"):
        runner_adapter.run_tier_beta_vertical_slice_from_payload(payload)


@pytest.mark.parametrize("nested", [False, True])
def test_compatibility_adapter_preserves_seed_zero_device_and_metadata(runner_adapter, nested):
    metadata = {"receipt_label": "synthetic"}
    params = {"pdb_content": "protein fixture", "smiles": "CCO", "seed": 0,
              "pose_count": 2, "top_k": 1, "stability_steps": 0,
              "pocket_residue_indices": [0, 3], "device": "explicit-test-device", "metadata": metadata}
    request = runner_adapter.parse_tier_beta_runner_payload({"runner_profile_params": params} if nested else params)
    assert request.protein_input == "protein fixture"
    assert request.ligand_input == "CCO"
    assert request.seed == 0
    assert request.pocket_residue_indices == [0, 3]
    assert request.device == "explicit-test-device"
    assert request.metadata == metadata
    assert request.metadata is not metadata


def test_compatibility_adapter_forwards_validated_values_to_synthetic_service(runner_adapter, monkeypatch):
    observed = {}
    sentinel = object()

    class Service:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def screen(self, **kwargs):
            observed.update(kwargs)
            return sentinel

    monkeypatch.setattr(runner_adapter, "TierBetaScreening", Service)
    result = runner_adapter.run_tier_beta_vertical_slice_from_payload({"runner_profile_params": {
        "protein_input": "protein fixture", "ligand_input": "CCO", "seed": "0",
        "pocket_residue_indices": [0, 3], "device": "explicit-test-device",
    }})
    assert result is sentinel
    assert observed == {"protein_input": "protein fixture", "ligand_input": "CCO", "seed": 0,
                        "pocket_residue_indices": [0, 3], "device": "explicit-test-device",
                        "pose_count": 8, "top_k": 3, "stability_steps": 0}


@pytest.mark.parametrize("name", ["seed", "pose_count", "top_k", "stability_steps"])
@pytest.mark.parametrize("value", [None, True, False, "", "broken", "1.5", 1.5, -1, float("nan"), float("inf"), [], {}])
def test_api_explicit_malformed_integers_are_rejected(name, value):
    with pytest.raises(ValueError, match=f"invalid_{name}"):
        build_tier_beta_request_from_api({"runner_profile_params": {name: value}})


@pytest.mark.parametrize("name,value", [("pose_count", 0), ("top_k", 0), ("seed", 2**31)])
def test_api_parameter_domain_limits(name, value):
    with pytest.raises(ValueError, match=f"invalid_{name}"):
        build_tier_beta_request_from_api({"runner_profile_params": {name: value}})


def test_api_defaults_and_exact_integer_values_preserve_zero():
    defaults = build_tier_beta_request_from_api({})
    assert (defaults["seed"], defaults["pose_count"], defaults["top_k"], defaults["stability_steps"]) == (42, 8, 3, 0)
    request = build_tier_beta_request_from_api({"runner_profile_params": {
        "seed": 0, "stability_steps": "0", "pose_count": 2.0, "top_k": "4",
        "pocket_residue_indices": [0, 2.0, "4"],
    }})
    assert (request["seed"], request["stability_steps"], request["pose_count"], request["top_k"]) == (0, 0, 2, 4)
    assert request["pocket_residue_indices"] == [0, 2, 4]


@pytest.mark.parametrize("indices", [[], "0,1", (0, 1), {}, False, [True], [1.5], [-1], [0, 0], [None], [float("nan")]])
def test_api_invalid_pocket_indices_are_not_silently_defaulted(indices):
    with pytest.raises(ValueError, match="invalid_pocket_residue_indices"):
        build_tier_beta_request_from_api({"runner_profile_params": {"pocket_residue_indices": indices}})


def test_api_request_builder_does_not_import_scientific_stack():
    code = """
import importlib.abc
import sys
class BlockScientificImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'rdkit', 'betelgeuze_engine'}:
            raise AssertionError('request builder imported ' + fullname)
sys.meta_path.insert(0, BlockScientificImports())
from betelgeuze_product.tier_beta_vertical_slice import build_tier_beta_request_from_api
assert build_tier_beta_request_from_api({'runner_profile_params': {'seed': 0}})['seed'] == 0
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


@dataclass
class _SyntheticResult:
    result_manifest: dict
    ok: bool = True
    claim_metadata: dict = field(default_factory=lambda: {"claim_safe": False})
    blocked_reason: str = "restricted_diagnostic"
    diagnostics: dict = field(default_factory=lambda: {"unmeasured": float("nan")})


def _stub_service(monkeypatch, manifest, *, ok=True):
    observed = {}

    class Service:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def screen(self, **kwargs):
            observed.update(kwargs)
            return _SyntheticResult(manifest, ok=ok)

    package = ModuleType("betelgeuze_engine.biodiscovery")
    package.TierBetaScreening = Service
    monkeypatch.setitem(sys.modules, package.__name__, package)
    return observed


def test_job_persists_and_verifies_consumed_byte_snapshots_without_rereading_inputs(manifest_helpers, monkeypatch, tmp_path):
    payload = _payload()
    snapshots = {
        f"{name}_input_snapshot": {
            "sha256": hashlib.sha256(content).hexdigest(), "byte_count": len(content), "source_kind": "file",
        }
        for name, content in [("protein", b"used protein bytes"), ("ligand", b"used ligand bytes")]
    }
    payload["stage_records"] = [{"stage_id": "preparation", "diagnostics": snapshots}]
    signed = manifest_helpers.sign_screening_manifest(payload)
    observed = _stub_service(monkeypatch, signed)
    protein_path = str(tmp_path / "never_read_or_reopened.pdb")
    status = run_tier_beta_vertical_slice_job(
        job_id="synthetic", results_dir=tmp_path / "results",
        request_data={"runner_profile_params": {"protein_input": protein_path, "ligand_input": "absent.sdf", "seed": 0}},
    )
    saved = json.loads(Path(status["result_file"]).read_text())
    assert observed["seed"] == 0
    assert status["result_manifest_verified"] is True
    assert manifest_helpers.verify_screening_manifest(saved["result_manifest"])
    assert saved["result"]["diagnostics"]["unmeasured"] is None
    assert saved["request"]["protein_input_sha256"] == snapshots["protein_input_snapshot"]["sha256"]
    assert saved["request"]["protein_input_spec_sha256"] == hashlib.sha256(protein_path.encode()).hexdigest()
    assert saved["request"]["protein_input_spec_sha256"] != saved["request"]["protein_input_sha256"]
    assert not Path(protein_path).exists()


def test_job_does_not_invent_missing_consumed_byte_hashes(manifest_helpers, monkeypatch, tmp_path):
    _stub_service(monkeypatch, manifest_helpers.sign_screening_manifest(_payload()))
    status = run_tier_beta_vertical_slice_job(job_id="synthetic", request_data={}, results_dir=tmp_path)
    saved = json.loads(Path(status["result_file"]).read_text())
    assert saved["request"]["protein_input_sha256"] is None
    assert saved["request"]["ligand_input_sha256"] is None


def test_job_rejects_tampering_during_artifact_publication(manifest_helpers, monkeypatch, tmp_path):
    _stub_service(monkeypatch, manifest_helpers.sign_screening_manifest(_payload()))

    def corrupt_writer(path, text):
        saved = json.loads(text)
        saved["result_manifest"]["pose_scores"][0]["coordinates"][0][0] += 3
        path.write_text(json.dumps(saved))

    with pytest.raises(ValueError, match="persisted_screening_manifest_integrity_mismatch"):
        run_tier_beta_vertical_slice_job(
            job_id="synthetic", request_data={}, results_dir=tmp_path, artifact_writer=corrupt_writer,
        )
    assert not (tmp_path / "status.json").exists()


def test_job_rejects_an_unverified_signature_before_publishing(manifest_helpers, monkeypatch, tmp_path):
    _stub_service(monkeypatch, {"signature": "not-a-valid-manifest"})
    with pytest.raises(ValueError, match="invalid_screening_manifest_integrity"):
        run_tier_beta_vertical_slice_job(job_id="synthetic", request_data={}, results_dir=tmp_path)
    assert not (tmp_path / "tier_beta_result.json").exists()


def test_job_does_not_publish_a_hash_for_bytes_changed_after_verification(manifest_helpers, monkeypatch, tmp_path):
    _stub_service(monkeypatch, manifest_helpers.sign_screening_manifest(_payload()))

    def changed_artifact_hasher(path):
        path.write_text('{"replaced":true}')
        return hashlib.sha256(path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="persisted_screening_artifact_changed"):
        run_tier_beta_vertical_slice_job(
            job_id="synthetic", request_data={}, results_dir=tmp_path, artifact_hasher=changed_artifact_hasher,
        )
    assert not (tmp_path / "status.json").exists()


def test_signed_failure_manifest_is_saved_and_verified(manifest_helpers, monkeypatch, tmp_path):
    _stub_service(monkeypatch, manifest_helpers.sign_screening_manifest(_payload()), ok=False)
    with pytest.raises(RuntimeError, match="restricted_diagnostic"):
        run_tier_beta_vertical_slice_job(job_id="synthetic", request_data={}, results_dir=tmp_path)
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["status"] == "failed"
    assert status["result_manifest_verified"] is True
    saved = json.loads((tmp_path / "tier_beta_result.json").read_text())
    assert saved["docking_results_emitted"] is False
    assert manifest_helpers.verify_screening_manifest(saved["result_manifest"])

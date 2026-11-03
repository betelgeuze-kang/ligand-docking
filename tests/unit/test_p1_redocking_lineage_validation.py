from copy import deepcopy
import hashlib
import json
import subprocess
import sys

import pytest

from tools.redocking_lineage_validation import (
    EVENT_SCHEMA, LINEAGE_SCHEMA, PROFILE, STAGES, LineageValidationError,
    coordinate_payload_fingerprint, validate_observation_events,
)


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def valid():
    stages = {stage: [] for stage in STAGES}
    candidates = []
    for index in range(64):
        states = {}
        for stage, offset in (("proposal_generated", 0), ("post_v6", 1), ("post_v7_optimization", 2)):
            payload = {"shape": [1, 3], "values_hex": [float(index + offset).hex(), (0.0).hex(), (-0.0).hex()]}
            states[stage] = {"schema_id": LINEAGE_SCHEMA, "proposal_index": index,
                "candidate_id": f"candidate-{index}", "proposal_fingerprint_sha256": _sha(f"original-{index}"),
                "coordinate_fingerprint_sha256": coordinate_payload_fingerprint(payload),
                "coordinates_binary64": payload, "coordinate_unit": "angstrom"}
            stages[stage].append(states[stage])
        selected = deepcopy(states["post_v7_optimization" if index % 2 else "post_v6"])
        selected.update(proposal_fingerprint_sha256=_sha(f"selected-{index}"),
            parent_proposal_fingerprint_sha256=_sha(f"original-{index}"),
            refinement_receipt_sha256=_sha(f"refinement-{index}"), torsion_selected=bool(index % 2),
            final_penalty_binary64_hex=(5.0).hex())
        stages["refinement_selected"].append(selected)
        candidates.append({"proposal_index": index, "status": "success", "score": float(64-index),
            "coordinate_fingerprint_sha256": selected["coordinate_fingerprint_sha256"],
            "proposal_fingerprint_sha256": selected["proposal_fingerprint_sha256"],
            "refinement_receipt_sha256": selected["refinement_receipt_sha256"],
            "refinement_final_penalty_binary64_hex": (5.0).hex(),
            "pose_artifact_sha256": _sha(f"pose-{index}"), "rmsd_angstrom": float(index)/100,
            "geometric_valid": True, "chemical_valid": True})
    ranked = sorted(candidates, key=lambda c: (c["score"], c["proposal_index"]))[:5]
    row = {"case_id": "fixture", "engine_id": "engine_v2", "status": "success",
        "engine_v2_diagnostics": {"candidates": candidates},
        "pose_artifact_sha256s": [c["pose_artifact_sha256"] for c in ranked],
        "rmsd_angstroms": [c["rmsd_angstrom"] for c in ranked],
        "geometric_valid": [True]*5, "chemical_valid": [True]*5}
    rows = [(stage, details) for stage in STAGES for details in stages[stage]]
    for rank, candidate in enumerate(ranked, 1):
        detail = deepcopy(stages["refinement_selected"][candidate["proposal_index"]])
        detail.update(rank_1based=rank, evaluated_pose_record_sha256=candidate["pose_artifact_sha256"])
        rows.append(("final_ranked", detail))
    events = [{"schema_id": EVENT_SCHEMA, "profile": PROFILE, "case_id": "fixture",
        "sequence": sequence, "evaluator_identity": "a"*64, "stage": stage, "phase": "snapshot",
        "elapsed_seconds": 0.0, "monotonic_elapsed_seconds": float(sequence), "details": details}
        for sequence, (stage, details) in enumerate(rows, 1)]
    return events, row


def check(valid):
    events, row = valid
    return validate_observation_events(events, case_id="fixture", canonical_row=row)


def test_complete_lineage_binds_every_candidate_and_top5_without_mutation(valid):
    original = deepcopy(valid)
    events, row = valid
    report = validate_observation_events(
        [{"stage": "worker", "phase": "start"}, *events, {"stage": "worker", "phase": "complete"}],
        case_id="fixture", canonical_row=row)
    assert report["status"] == "verified" and report["evaluator_identity"] == "a"*64
    assert report["canonical_candidate_bindings"] == 64 and report["top5_bindings"] == 5
    assert report["coordinate_snapshot_count"] == 261
    assert valid == original
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("key,value", [("schema_id", "unknown"), ("profile", "legacy_v7"),
    ("case_id", "other"), ("sequence", 1), ("evaluator_identity", "b"*64),
    ("elapsed_seconds", float("nan")), ("monotonic_elapsed_seconds", -1.0)])
def test_inner_identity_sequence_and_clock_are_enforced(valid, key, value):
    valid[0][10][key] = value
    with pytest.raises(LineageValidationError): check(valid)


@pytest.mark.parametrize("change", ["duplicate", "shape", "count", "nan", "noncanonical", "hash", "parent", "selected", "rank", "pose", "canonical"])
def test_corrupted_coordinate_or_lineage_binding_is_rejected(valid, change):
    events, row = valid
    first = events[0]["details"]
    selected = events[192]["details"]
    if change == "duplicate": events[63]["details"]["proposal_index"] = 0
    elif change == "shape": first["coordinates_binary64"]["shape"] = [1, 2]
    elif change == "count": first["coordinates_binary64"]["values_hex"].pop()
    elif change == "nan": first["coordinates_binary64"]["values_hex"][0] = "nan"
    elif change == "noncanonical": first["coordinates_binary64"]["values_hex"][0] = "0x0p+0"
    elif change == "hash": first["coordinate_fingerprint_sha256"] = "b"*64
    elif change == "parent": selected["parent_proposal_fingerprint_sha256"] = "b"*64
    elif change == "selected": selected["torsion_selected"] = True
    elif change == "rank": events[-1]["details"]["rank_1based"] = 1
    elif change == "pose": events[-1]["details"]["evaluated_pose_record_sha256"] = "b"*64
    else: row["engine_v2_diagnostics"]["candidates"][63]["refinement_receipt_sha256"] = "b"*64
    with pytest.raises(LineageValidationError): check(valid)


def test_missing_coordinate_event_cannot_be_hidden_as_p0(valid):
    for key in ("schema_id", "profile", "sequence", "evaluator_identity", "monotonic_elapsed_seconds"):
        valid[0][0].pop(key)
    with pytest.raises(LineageValidationError, match="schema/profile/case"): check(valid)


def test_coordinate_hash_matches_actual_torch_identity_for_both_dtypes():
    torch = pytest.importorskip("torch")
    from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
    for dtype in (torch.float32, torch.float64):
        tensor = torch.tensor([[1.25, -0.0], [2.5, -7.75], [0.0, 0.125]], dtype=dtype).T
        assert not tensor.is_contiguous()
        payload = {"shape": list(tensor.shape), "values_hex": [float(v).hex() for v in
                   tensor.to(dtype=torch.float64).contiguous().reshape(-1).tolist()]}
        assert coordinate_payload_fingerprint(payload) == coordinate_fingerprint(tensor)


def test_validator_import_is_standard_library_only():
    subprocess.run([sys.executable, "-c", "import sys; import tools.redocking_lineage_validation; "
                    "assert 'torch' not in sys.modules and 'rdkit' not in sys.modules"], check=True)


def test_actual_tiny_runner_events_satisfy_complete_validator(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    Chem = pytest.importorskip("rdkit.Chem")
    from rdkit.Chem import Lipinski, rdMolDescriptors
    from tools import run_engine_v2_public_redocking_300 as runner
    from tools.redocking_development_p1 import DevelopmentObservation
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("_p1_lineage_runner_fixture", Path(__file__).with_name("test_p1_redocking_runner.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    _molecule, _fake_evaluator = fixture._molecule, fixture._fake_evaluator
    monkeypatch.setattr(runner, "_load_rdkit_modules", lambda: (Chem, Lipinski, rdMolDescriptors))
    case_id = runner.FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True)
    molecule = Chem.AddHs(_molecule(paths["native"]), addCoords=True)
    payload = (Chem.MolToMolBlock(molecule) + "\n$$$$\n").encode("ascii")
    for role in ("native", "reference", "seed"): paths[role].write_bytes(payload)
    receptor = Chem.MolFromSmiles("C")
    conformer = Chem.Conformer(1)
    conformer.SetAtomPosition(0, (6.0, 0.0, 0.0))
    receptor.AddConformer(conformer)
    paths["receptor"].write_bytes(Chem.MolToPDBBlock(receptor).encode("ascii"))
    _fake_evaluator(monkeypatch)
    events = []
    observer = DevelopmentObservation(case_id, event_sink=events.append, evaluator_identity="a"*64)
    result = runner._engine_v2_result(case_id, paths, input_sha256s=runner._input_sha256s(paths),
        output=tmp_path / "poses.sdf", seed=runner.frozen_public_redocking_case_seed(case_id),
        development_observation=observer)
    report = validate_observation_events(events, case_id=case_id, canonical_row=result.to_dict())
    assert report["canonical_candidate_bindings"] == 64 and report["top5_bindings"] == 5

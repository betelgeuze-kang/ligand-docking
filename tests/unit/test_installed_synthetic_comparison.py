"""Installed synthetic comparison execution, recovery, and integrity contracts."""

import copy
import json
import shutil
from pathlib import Path
import subprocess
import sys
import time

import pytest

from betelgeuze_product import installed_synthetic_comparison as installed


def _installed_protocol(tmp_path):
    import copy
    import hashlib
    import json
    root = Path(tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'installed-inputs'
    source.mkdir()
    def write(name, content):
        path = source / name
        path.write_text(content)
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'source_id': 'installed-synthetic-constants:' + name}
    pdb = f"ATOM  {1:5d} {'C1':>4s} {'SYN':>3s} A{1:4d}    {0.0:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}          {'C':>2s}  \nEND\n"
    sdf = ("Synthetic explicit carbon\n  local synthetic test\n\n"
           "  1  0  0  0  0  0            999 V2000\n"
           f"{4.0:10.4f}{0.0:10.4f}{0.0:10.4f} C   0  0  0  0  0  0  0  0  0  0  0  0\nM  END\n$$$$\n")
    gro = ("Synthetic explicit carbon\n1\n"
           f"{1:5d}{'LIG':<5s}{'C1':>5s}{1:5d}{0.4:8.3f}{0.0:8.3f}{0.0:8.3f}\n0.0 0.0 0.0\n")
    atomtypes = "[ atomtypes ]\nC 6 12.011 0.0 A 0.300000 0.836800\n"
    defaults = "[ defaults ]\n1 2 yes 0.5 0.833333\n"
    protein_itp = "[ moleculetype ]\nSYN 3\n[ atoms ]\n1 C 1 SYN C1 1 0.2 12.011\n"
    ligand_itp = "[ moleculetype ]\nLIG 3\n[ atoms ]\n1 C 1 LIG C1 1 -0.3 12.011\n"
    files = {'protein_pdb': ('receptor.pdb', pdb),
             'protein_atomtypes': ('receptor-types.itp', atomtypes),
             'protein_defaults': ('receptor-defaults.itp', defaults),
             'ligand_sdf': ('ligand.sdf', sdf),
             'ligand_gro': ('ligand.gro', gro),
             'ligand_itp': ('ligand.itp', ligand_itp),
             'ligand_atomtypes': ('ligand-types.itp', atomtypes),
             'ligand_defaults': ('ligand-defaults.itp', defaults)}
    prepared = {key: write(*value) for key, value in files.items()}
    prepared.update(schema_version='prepared_gromacs_components_v1',
                    protein_chains=[{'chain_id':'A','molecule_itp':write('receptor.itp', protein_itp)}],
                    ligand_atomtype_name_mapping={},
                    ligand_residue_name_mapping={'gro':'LIG','itp':'LIG'},
                    naming_convention='exact', pdb_element_policy='reject_missing',
                    source_relationship='independent synthetic text constants in a declared frame',
                    source_declarations={'coordinate_frame_id':'synthetic-frame',
                                         'prepared_state_id':'synthetic-state',
                                         'parameter_source_id':'synthetic-explicit-tables',
                                         'charge_source_id':'synthetic-explicit-charge'})
    base = {'schema_version':'prepared_rigid_pose_cross_request_v1',
            'prepared_input':prepared,
            'evaluation':{'pocket_center_angstrom':[0.0,0.0,0.0],
                          'pocket_radius_angstrom':10.0,'cutoff_angstrom':10.0,
                          'switch_start_angstrom':8.0,'dielectric':4.0,
                          'screening_kappa_per_angstrom':0.1},
            'execution':{'projection_partition':'source_order_v1',
                         'preparation_reuse':'request'},
            'poses':[{'pose_id':'reference',
                      'rotation_matrix':[[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],
                      'translation_angstrom':[0.0,0.0,0.0]}]}
    rows = [{'record_id':rid,'role':role,'component_id':rid+'-component',
             'smiles':smiles,'fit_value':value,'assay_id':'synthetic-one-assay'}
            for rid,role,smiles,value in [
                ('fit-a','fit','CCCC',5.0),('fit-b','fit','CCNCC',7.0),
                ('fit-c','fit','CCCCCO',6.0),('cal-a','calibration','c1ccccc1',None),
                ('a','development_test','CCCCN',None),
                ('b','development_test','CCCCCC',None),
                ('c','development_test','CCCCS',None),
                ('d','development_test',None,None)]]
    requests = {}
    for rid, shift in [('a',0.0),('b',0.8),('c',1000.0)]:
        request = copy.deepcopy(base)
        request['poses'][0]['translation_angstrom'][0] = shift
        path = source / (rid + '.request.json')
        path.write_text(json.dumps(request,sort_keys=True)+'\n')
        requests[rid] = {'path':str(path),
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    requests['d'] = None
    protocol = {'schema_version':installed.PROTOCOL,
                'source':{'kind':'synthetic_constants','rows':rows},
                'requests':requests,'budget_seconds_per_arm':20.0,
                'max_engine_calls_per_arm':10,
                'arm_order':['similarity','engine','ai_engine','similarity_engine'],
                'selection_seed':17,'tie_policy':'seeded_pool_order'}
    return protocol


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp("installed-four-arm-run")
    protocol = _installed_protocol(root / "inputs")
    protocol_path = root / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    for command in ("run", "verify-run", "resume"):
        subprocess.run([sys.executable, "-I", "-m",
                        "betelgeuze_product.installed_synthetic_comparison", command,
                        "--protocol", str(protocol_path), "--run-dir", str(root / "run")],
                       check=True, cwd=root, capture_output=True, text=True)
    result = json.loads((root / "run" / "comparison.json").read_text())
    return root, protocol, result


def test_real_four_arm_run_read_only_verify_and_idempotent_resume(completed):
    root, protocol, result = completed
    run_dir = root / "run"
    assert result["arm_order"] == protocol["arm_order"]
    assert result["pool"] == list("abcd")
    assert set(result["arms"]) == set(installed.ARMS)
    assert result["evaluation_labels_read"] == 0
    assert result["source_authenticated"] is False
    assert result["scientifically_validated"] is False
    for arm in installed.ARMS:
        data = result["arms"][arm]
        assert data["denominator"]["requested"] == 4
        assert data["completion"]["status"] == "complete"
        assert data["completion"]["budget_seconds"] == 20.0
        if arm == "engine":
            assert data["priority"]["order"] == list("abcd")
        else:
            assert set(data["priority"]["order"]) == set("abc")
    assert result["arms"]["similarity"]["denominator"] == {
        "requested": 4, "evaluated": 3, "unsupported": 1}
    assert result["arms"]["engine"]["denominator"] == {
        "requested": 4, "evaluated": 2, "failed": 1, "unsupported": 1}
    before = {str(path.relative_to(run_dir)): path.read_bytes()
              for path in run_dir.rglob("*") if path.is_file()}
    assert installed.verify_run(protocol, run_dir)["status"] == "verified"
    assert installed.run(protocol, run_dir, resume=True) == result
    after = {str(path.relative_to(run_dir)): path.read_bytes()
             for path in run_dir.rglob("*") if path.is_file()}
    assert before == after


def test_resealed_priority_and_result_still_rejected(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "resealed"
    shutil.copytree(root / "run", copied)
    priority_path = copied / "ai_engine" / "priority.json"
    priority = json.loads(priority_path.read_text())
    priority["order"][:2] = reversed(priority["order"][:2])
    priority_path.write_bytes(installed._canonical(priority) + b"\n")
    result_path = copied / "comparison.json"
    result = json.loads(result_path.read_text())
    result["arms"]["ai_engine"]["priority"] = priority
    result_path.write_bytes(installed._canonical(result) + b"\n")
    verdict = installed.verify_run(protocol, copied)
    assert verdict["reason"] == "installed_priority_recalculation_mismatch"
    with pytest.raises(ValueError, match="installed_priority_recalculation_mismatch"):
        installed.run(protocol, copied, resume=True)


def test_resealed_row_and_result_cannot_detach_score_from_pose(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "resealed-score"
    shutil.copytree(root / "run", copied)
    rid = "a"
    path = copied / "engine" / f"{installed._sha(rid)}.row.json"
    wrapped = json.loads(path.read_text())
    wrapped["payload"]["score"] += 1.0
    wrapped["sha256"] = installed._sha(wrapped["payload"])
    path.write_bytes(installed._canonical(wrapped) + b"\n")
    result_path = copied / "comparison.json"
    result = json.loads(result_path.read_text())
    row = next(item for item in result["arms"]["engine"]["rows"]
               if item["record_id"] == rid)
    row["score"] = wrapped["payload"]["score"]
    result_path.write_bytes(installed._canonical(result) + b"\n")
    assert installed.verify_run(protocol, copied)["reason"] == "installed_pose_report_score_mismatch"


def test_bound_input_change_blocks_read_only_verification_and_resume(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "input-drift"
    shutil.copytree(root / "run", copied)
    altered = copy.deepcopy(protocol)
    altered["source"]["rows"][0]["fit_value"] += 1.0
    before = (copied / "comparison.json").read_bytes()
    assert installed.verify_run(altered, copied)["reason"] == "installed_verify_input_or_runtime_changed"
    with pytest.raises(ValueError, match="installed_resume_input_or_runtime_changed"):
        installed.run(altered, copied, resume=True)
    assert (copied / "comparison.json").read_bytes() == before


def test_runtime_dependency_change_blocks_verification_and_resume(completed, tmp_path, monkeypatch):
    root, protocol, _ = completed
    copied = tmp_path / "runtime-drift"
    shutil.copytree(root / "run", copied)
    original = installed.importlib.metadata.version

    def changed(name):
        value = original(name)
        return value + ".drift" if name == "scikit-learn" else value

    monkeypatch.setattr(installed.importlib.metadata, "version", changed)
    assert installed.verify_run(protocol, copied)["reason"] == "installed_verify_input_or_runtime_changed"
    with pytest.raises(ValueError, match="installed_resume_input_or_runtime_changed"):
        installed.run(protocol, copied, resume=True)


def test_noncanonical_result_bytes_rejected(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "raw-tamper"
    shutil.copytree(root / "run", copied)
    with (copied / "comparison.json").open("ab") as stream:
        stream.write(b" ")
    assert installed.verify_run(protocol, copied)["reason"] == "noncanonical_installed_receipt"
    command = subprocess.run([sys.executable, "-I", "-m",
                              "betelgeuze_product.installed_synthetic_comparison", "verify-run",
                              "--protocol", str(root / "protocol.json"), "--run-dir", str(copied)],
                             cwd=tmp_path, capture_output=True, text=True)
    assert command.returncode == 2
    assert json.loads(command.stdout)["reason"] == "noncanonical_installed_receipt"


def test_resealed_authority_claim_rejected(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "authority"
    shutil.copytree(root / "run", copied)
    result_path = copied / "comparison.json"
    result = json.loads(result_path.read_text())
    result["scientifically_validated"] = True
    result_path.write_bytes(installed._canonical(result) + b"\n")
    assert installed.verify_run(protocol, copied)["reason"] == "invalid_installed_result_header"
    with pytest.raises(ValueError, match="invalid_installed_result_header"):
        installed.run(protocol, copied, resume=True)


def test_orphaned_attempt_forfeits_original_budget_without_replaying(tmp_path):
    protocol = _installed_protocol(tmp_path / "inputs")
    protocol["arm_order"] = list(installed.ARMS)
    frozen = installed.freeze(protocol)
    binding = installed._sha(frozen)
    root = tmp_path / "orphan"
    root.mkdir(mode=0o700)
    lock = installed._lock(root / "run.lock", create=True)
    installed.os.close(lock)
    installed._publish(root / "frozen.json", {"payload": frozen, "sha256": binding})
    arm = root / "similarity"
    arm.mkdir(mode=0o700)
    started = time.monotonic()
    installed._publish(arm / "attempt.json", {
        "receipt_version": installed.EXECUTION_VERSION, "arm": "similarity",
        "binding": binding, "started_monotonic": started,
        "deadline": started + 20.0})
    lease = installed._lock(arm / "worker.lock", create=True)
    installed.os.close(lease)
    result = installed.run(protocol, root, resume=True)
    lost = result["arms"]["similarity"]
    assert lost["completion"]["status"] == "interrupted_budget_forfeited"
    assert lost["denominator"] == {"requested": 4, "not_processed": 4}
    assert lost["priority"] is None
    assert installed.verify_run(protocol, root)["status"] == "verified"
    assert installed.run(protocol, root, resume=True) == result


def test_actual_timeout_retains_denominator_and_cannot_retry(tmp_path):
    protocol = _installed_protocol(tmp_path / "inputs")
    protocol["budget_seconds_per_arm"] = 0.001
    root = tmp_path / "timed-out"
    result = installed.run(protocol, root)
    assert all(result["arms"][arm]["completion"]["status"] == "budget_exhausted"
               for arm in installed.ARMS)
    assert all(result["arms"][arm]["denominator"] == {
        "requested": 4, "not_processed": 4} for arm in installed.ARMS)
    assert installed.verify_run(protocol, root)["status"] == "verified"
    assert installed.run(protocol, root, resume=True) == result


def test_legacy_schema_does_not_create_installed_run(tmp_path):
    old = _installed_protocol(tmp_path / "inputs")
    old["schema_version"] = "installed_synthetic_prepared_comparison_protocol_v1"
    destination = tmp_path / "not-created"
    with pytest.raises(ValueError, match="unsupported_installed_comparison_protocol"):
        installed.run(old, destination)
    assert not destination.exists()

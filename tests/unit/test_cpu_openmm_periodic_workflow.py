"""The new physics identity survives actual publication and interruption/resume."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_product.reference_minimization_workflow import _parameters, _bound
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import (
    OpenMMPeriodicParameters, OPENMM_PERIODIC_EVALUATOR_ID,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from betelgeuze_product.cpu_refinement_v1_2.resume_verification import verify_resume_summary
from betelgeuze_product.cpu_refinement_v1_2.workflow import run_request, verify_output
from betelgeuze_product.cpu_refinement_v1_2.resumable_workflow import (
    run_resumable_request, verify_resumable_output,
)
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture as fixed_request
from tests.unit.test_cpu_refinement_v1_2_workflow import request_fixture as internal_request


def request_fixture(path, fixed):
    request = (fixed_request if fixed else internal_request)(path)
    parameters = OpenMMPeriodicParameters(
        _parameters(_bound(request['parameters'])),
        constant_energy_offset_kcal_per_mol=-2.5,
        metadata={'scope': 'synthetic workflow regression, not source translation'},
    )
    data = json.dumps(parameters.to_dict()).encode()
    file = path / 'openmm-periodic.json'
    file.write_bytes(data)
    request['extensions'] = {'path': str(file.absolute()), 'sha256': hashlib.sha256(data).hexdigest()}
    return request, parameters


@pytest.mark.parametrize('fixed', [False, True])
def test_new_schema_runs_publishes_verifies_and_resumes(tmp_path, fixed):
    request, parameters = request_fixture(tmp_path, fixed)
    report = run_request(request, tmp_path / 'complete')
    assert verify_output(tmp_path / 'complete')['structural_verification_passed']
    assert report['result']['evaluator']['parameter_fingerprint_sha256'] == parameters.fingerprint_sha256
    if not fixed:
        assert report['result']['evaluator']['evaluator_id'] == OPENMM_PERIODIC_EVALUATOR_ID
    assert report['result']['arms']['refined']['failure_count'] == 0
    run_resumable_request(request, tmp_path / 'resumed', stop_after=1)
    run_resumable_request(request, tmp_path / 'resumed', resume=True)
    assert verify_resumable_output(tmp_path / 'resumed')['structural_verification_passed']
    if not fixed:
        forged = deepcopy(report['result'])
        forged['evaluator']['solvation_fingerprint_sha256'] = 'a' * 64
        forged['report_sha256'] = digest({k: v for k, v in forged.items() if k != 'report_sha256'})
        with pytest.raises(ResearchError, match='unsupported solvent'):
            verify_report(forged)
        forged = json.loads((tmp_path / 'resumed' / 'report.json').read_bytes())['summary']
        forged['plan']['evaluator']['solvation_fingerprint_sha256'] = 'a' * 64
        forged['plan_sha256'] = digest(forged['plan'])
        forged['summary_sha256'] = digest({k: v for k, v in forged.items() if k != 'summary_sha256'})
        with pytest.raises(ResearchError, match='unsupported solvent'):
            verify_resume_summary(forged)


@pytest.mark.parametrize('mutation', ['strip_periodic_terms', 'old_schema', 'base_fingerprint'])
def test_rehashed_inconsistent_extension_rejected_before_execution(tmp_path, mutation):
    request, _ = request_fixture(tmp_path, True)
    file = Path(request['extensions']['path'])
    value = json.loads(file.read_bytes())
    if mutation == 'strip_periodic_terms':
        del value['periodic_impropers']
    elif mutation == 'old_schema':
        value['schema_id'] = 'betelgeuze.reference_forcefield_v2_parameters/2.0.0'
    else:
        value['base_parameter_fingerprint_sha256'] = '0' * 64
    data = json.dumps(value).encode()
    file.write_bytes(data)
    request['extensions']['sha256'] = hashlib.sha256(data).hexdigest()
    with pytest.raises((ResearchError, ValueError, KeyError)):
        run_request(request, tmp_path / 'output')
    assert not (tmp_path / 'output' / 'complete.json').exists()

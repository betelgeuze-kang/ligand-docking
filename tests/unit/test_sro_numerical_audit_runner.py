import copy

import pytest

from docs.research.human_5ht6_sro_numerical_preparation import run_numerical_audit as module


def fixture():
    def ref(name):
        return {'path': '/synthetic/' + name, 'sha256': 'a' * 64, 'bytes': 10}
    plan = {'native_source_sha256': 'b' * 64, 'request': ref('request'),
            'inputs': {'ligand_xml': ref('ligand'), 'receptor_xml': ref('receptor')}}
    oracle = ref('oracle')
    report = {'audit_source_sha256': oracle['sha256'],
              'native_source_manifest_sha256': plan['native_source_sha256'],
              'protocol': dict(module.AUDIT_PROTOCOL),
              'inputs': {'request': module.request_reference(plan['request']),
                         'ligand_XML': module.request_reference(plan['inputs']['ligand_xml']),
                         'receptor_XML': module.request_reference(plan['inputs']['receptor_xml'])},
              'denominator': {'requested': 4, 'evaluated': 4, 'rejected': 0, 'passed': 4},
              'snapshots': [{'snapshot': name, 'passed': True} for name in
                            ('initial', 'perturbation_1', 'perturbation_2', 'perturbation_3')],
              'all_same_math_checks_passed': True, 'ligand_atom_count': 26,
              'receptor_atom_count': 4376, 'reference_platform': 'Reference',
              'intrareceptor_energy_evaluated': False}
    return report, plan, oracle


def test_oracle_default_magnitude_cannot_replace_frozen_magnitude():
    report, plan, oracle = fixture()
    module.verify_result(report, plan, oracle)
    report['protocol']['perturbation_angstrom'] = 0.0001
    with pytest.raises(ValueError, match='numerical_protocol_changed'):
        module.verify_result(report, plan, oracle)


@pytest.mark.parametrize('mutation', ['lost_failure', 'row_failed', 'wrong_xml', 'wrong_source'])
def test_numerical_coverage_and_identity_are_required(mutation):
    report, plan, oracle = copy.deepcopy(fixture())
    if mutation == 'lost_failure':
        report['snapshots'].pop()
        report['denominator'] = {'requested': 3, 'evaluated': 3, 'rejected': 0, 'passed': 3}
    elif mutation == 'row_failed':
        report['snapshots'][-1]['passed'] = False
    elif mutation == 'wrong_xml':
        report['inputs']['ligand_XML']['sha256'] = 'c' * 64
    else:
        report['native_source_manifest_sha256'] = 'c' * 64
    with pytest.raises(ValueError):
        module.verify_result(report, plan, oracle)

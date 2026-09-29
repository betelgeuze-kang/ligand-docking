"""Compare the completed installed SRO run with retained independent evidence."""

from pathlib import Path
import hashlib
import json
import os
import struct


heavy = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
old = heavy / 'engine-v2-sro-sd-lbfgs-comparison-20260930-v2/run/lbfgs'
new = heavy / 'engine-v2-installed-cartesian-sro-20260930-25b0ef44'


def same(a, b):
    return struct.pack('>d', a) == struct.pack('>d', float.fromhex(b))


historical = json.loads((old / 'optimizer.json').read_bytes())
historical_result = json.loads((old / 'result.json').read_bytes())
execution = json.loads((new / 'resume.stdout.json').read_bytes())
product = execution['result']
numerical = product['numerical_result']
state, work = numerical['checkpoint']['state'], numerical['work']
old_rows = [item['row'] for line in (old / 'trials.jsonl').read_bytes().splitlines()
            if (item := json.loads(line))['event'] == 'finish']
new_rows = [item['payload']['observation'] for line in (new / 'run/numerical/events.jsonl').read_bytes().splitlines()
            if (item := json.loads(line))['kind'] == 'objective_finished']
assert len(old_rows) == len(new_rows) == 253
checks = 0
for left, right in zip(old_rows, new_rows, strict=True):
    assert left['attempt'] == right['attempt']
    for a, b in [('energy_kcal_mol', 'energy'), ('maximum_raw_atom_force', 'maximum_raw_atom_force')]:
        assert same(left[a], right[b]), (left['attempt'], a)
        checks += 1
    for a, b in [('coordinates_angstrom', 'coordinates'),
                 ('force_kcal_mol_angstrom', 'forces')]:
        for old_atom, new_atom in zip(left[a], right[b], strict=True):
            for x, y in zip(old_atom, new_atom, strict=True):
                assert same(x, y), (left['attempt'], a)
                checks += 1
    for name, value in left['components'].items():
        assert same(value, right['components'][name]), (left['attempt'], name)
        checks += 1
assert state['status'] == numerical['status'] == historical['status'] == 'force_converged'
assert state['attempts'] == work['optimizer_objective_attempts'] == historical['attempts'] == 253
assert state['accepted'] == historical['accepted'] == 244
assert work['restart_verification_attempts'] == 1
assert work['optimizer_force_calls'] == 253
assert work['actual_force_calls'] == 254
assert work['failed_optimizer_force_calls'] == work['failed_restart_force_calls'] == 0
assert work['unknown_pending_attempts'] == 0
assert product['paired_decision']['variant'] == historical_result['selection'] == 'refined'
assert product['attempt']['converged'] is True
assert same(historical_result['final_energy'], state['current']['energy'])
assert same(historical_result['final_raw_force'], state['current']['maximum_raw_atom_force'])
final_score = product['rows']['refined']['score']
historical_score = historical_result['scores']['final']['score']
score_exact = struct.pack('>d', final_score) == struct.pack('>d', historical_score)
assert score_exact, (final_score, historical_score)
verified = json.loads((new / 'verify.stdout.json').read_bytes())
assert verified['structural_verification_passed']
assert not verified['numerical_evaluation_reexecuted']
assert not verified['scoring_reexecuted']
original_oracle = json.loads((old / 'numerical-audit.json').read_bytes())
assert original_oracle['all_same_math_checks_passed'] is True
report = {
    'schema_id': 'installed_cartesian_sro_retained_reference_audit/1',
    'status': 'exact_retained_reference_match',
    'historical_comparison_role': 'same_prepared_state_and_math_retained_reference',
    'new_installed_real_objective_attempts': 253,
    'new_installed_real_force_calls': 254,
    'separately_counted_restart_force_calls': 1,
    'exact_binary64_values_checked': checks,
    'final_energy_kcal_per_mol': float.fromhex(state['current']['energy']),
    'final_raw_force_kcal_per_mol_angstrom': float.fromhex(state['current']['maximum_raw_atom_force']),
    'selected_variant': product['paired_decision']['variant'],
    'final_dimensionless_score_exact': True,
    'retained_oracle_endpoint_arrays_reused_as_new_oracle_computation': False,
    'independent_new_OpenMM_oracle_calls': 0,
    'new_assay_admissions': 0,
    'scientific_qualification': False,
    'affinity_or_pose_recovery_validated': False,
    'HIP_or_service_qualified': False,
    'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
target = new / 'retained-reference-audit.json'
assert not target.exists()
with target.open('x') as stream:
    json.dump(report, stream, indent=2, sort_keys=True)
    stream.write('\n')
    stream.flush()
    os.fsync(stream.fileno())
print(json.dumps(report, sort_keys=True))

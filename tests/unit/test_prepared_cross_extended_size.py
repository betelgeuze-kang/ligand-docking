"""Extended size consumer contracts using synthetic source files only."""
import copy
import json
import pytest
from tests.unit.test_score_prepared_cross_interactions import _prepared, _write_source, _case, _run
from tools.product import score_prepared_cross_interactions as consumer


def test_extended_315_atom_source_files_keep_all_parameters_and_failed_default(tmp_path):
    directory = tmp_path / 'sources'
    prepared = _prepared(directory)
    count = 315
    sdf = ('Synthetic independent carbon sites\n local numerical constants\n\n'
           f'{count:3d}  0  0  0  0  0            999 V2000\n' + ''.join(
               f'{1.4*i:10.4f}{4.:10.4f}{0.:10.4f} C   0  0  0  0  0  0  0  0  0  0  0  0\n'
               for i in range(count)) + 'M  END\n$$$$\n')
    gro = f'Synthetic independent carbon sites\n{count}\n' + ''.join(
        f'{1:5d}{"LIG":<5s}{"C"+str(i+1):>5s}{i+1:5d}{.14*i:8.3f}{.4:8.3f}{0.:8.3f}\n'
        for i in range(count)) + '0.0 0.0 0.0\n'
    itp = '[ moleculetype ]\nLIG 3\n[ atoms ]\n' + ''.join(
        f'{i+1} C 1 LIG C{i+1} {i+1} -0.3 12.011\n' for i in range(count))
    for key, name, value in [('ligand_sdf','large.sdf',sdf),('ligand_gro','large.gro',gro),('ligand_itp','large.itp',itp)]:
        prepared[key] = _write_source(directory,name,value)
    case = _case(prepared)
    case['evaluation']['pocket_radius_angstrom'] = 1000.
    case['execution'] = {'projection_partition':'spatial_median_v1','ligand_size_profile':'extended_512_v1'}
    standard = copy.deepcopy(case)
    del standard['execution']['ligand_size_profile']
    request, output = tmp_path/'request.json', tmp_path/'report.json'
    request.write_text(json.dumps({'schema_version':consumer.SCHEMA_V2,'cases':[case,standard]}))
    process = _run(request,output,tmp_path)
    assert process.returncode == 2, process.stderr
    report = json.loads(output.read_text())
    assert report['denominator'] == {'requested':2,'evaluated':1,'failed':1,'skipped':0}, report
    result = report['rows'][0]['result']
    assert len(result['sources']['ligand']['nonbonded_parameters']) == count
    assert len(result['quantities']['ligand_cross_forces_kcal_per_mol_angstrom']) == count
    assert result['pair_accounting']['requested_cross_pairs'] == count
    assert result['input_domain']['ligand_size_profile'] == 'extended_512_v1'
    assert 'bounded' in report['rows'][1]['reason']


@pytest.mark.parametrize('profile',[None,True,512,[],{},'unbounded'])
def test_consumer_rejects_invalid_size_profile_before_loading(tmp_path,profile):
    case = _case({'must_not_be_loaded':True})
    case['execution']={'projection_partition':'source_order_v1','ligand_size_profile':profile}
    report=consumer.evaluate_request({'schema_version':consumer.SCHEMA_V2,'cases':[case]})
    assert report['denominator']['failed']==1
    assert 'ligand_size_profile' in report['rows'][0]['reason']

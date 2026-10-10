"""Thin P2 sidecar bridge for the independently source-bound long shape route."""
from betelgeuze_product.cpu_refinement_diagnostics_v1 import workflow as retained
from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import DiagnosticConfig
from . import cartesian


def diagnose_shape_run(system, parameters, config, *, fixed_environment, run_dir, binding,
                       base_profile, reference, strength, output_dir,
                       diagnostic_config=DiagnosticConfig()):
    options = dict(fixed_environment=fixed_environment, run_dir=run_dir, binding=binding,
                   base_profile=base_profile, reference=reference, strength=strength)
    result = cartesian.verify_shape(system, parameters, config, **options)
    evaluator, identity, profile, sources, guard = cartesian._context(
        system, parameters, config, fixed_environment, binding,
        base_profile=base_profile, reference=reference, strength=strength)
    return retained._collect(system, config, evaluator, identity, run_dir, output_dir=output_dir,
                             diagnostic_config=diagnostic_config, source_result=result,
                             source_manifest=sources, result_schema=cartesian.RESULT_SCHEMA,
                             model_guard=guard, profile=profile)


def verify_shape_sidecar(system, parameters, config, *, fixed_environment, run_dir, binding,
                         base_profile, reference, strength, output_dir, expected_report_sha256):
    options = dict(fixed_environment=fixed_environment, run_dir=run_dir, binding=binding,
                   base_profile=base_profile, reference=reference, strength=strength)
    result = cartesian.verify_shape(system, parameters, config, **options)
    _, identity, _, _, _ = cartesian._context(system, parameters, config, fixed_environment, binding,
                                             base_profile=base_profile, reference=reference,
                                             strength=strength)
    report = retained._verify_sidecar(output_dir, expected_report_sha256, result, identity)
    retained.require(cartesian.verify_shape(system, parameters, config, **options) == result,
                     'source changed during sidecar verification')
    return report


def diagnose_baseline(system, evaluator, config, identity, *, baseline_dir, plan_sha256, output_dir):
    """Separately reserved P2 arithmetic for the verified single-point B0 receipt."""
    from . import workflow
    from .contracts import require
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
    from betelgeuze_product.cpu_refinement_diagnostics_v1.evaluation import diagnose_observation
    source = workflow._path(baseline_dir).resolve(strict=True)
    requested_output = workflow._path(output_dir)
    resolved_output = requested_output.parent.resolve(strict=True) / requested_output.name
    require(resolved_output != source and source not in resolved_output.parents,
            'baseline diagnostics must be outside original evidence')
    baseline = workflow.verify_baseline(system, config, identity, output_dir=baseline_dir,
                                        plan_sha256=plan_sha256)
    observation = baseline['receipt']['observation']
    require(observation is not None, 'baseline diagnostic observation unavailable')
    binding = {'schema_id': 'cpu_unrefined_diagnostic_binding/1.0.0',
               'baseline_result_sha256': baseline['result_sha256'], 'plan_sha256': plan_sha256,
               'implementation_sha256': digest(cartesian.implementation_sources(identity['external_binding']['model']))}
    with retained._OutputDirectory(workflow._path(output_dir)) as destination:
        destination.write('binding.json', binding)
        destination.write('diagnostic-started.json', {'binding_sha256': digest(binding)})
        record = diagnose_observation(system, evaluator, config, observation,
            observation_ref={'kind': 'verified_baseline', 'result_sha256': baseline['result_sha256']})
        require(workflow.verify_baseline(system, config, identity, output_dir=baseline_dir,
                plan_sha256=plan_sha256) == baseline, 'baseline changed during diagnostics')
        record.pop('record_sha256')
        record['source_evidence_verified'] = True
        record['record_sha256'] = digest(record)
        destination.write('diagnostic-finished.json', record)
        return record


def verify_baseline_sidecar(system, config, identity, *, baseline_dir, plan_sha256,
                            output_dir, expected_record_sha256):
    from . import workflow
    from .contracts import require
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, require_digest
    baseline = workflow.verify_baseline(system, config, identity, output_dir=baseline_dir,
                                        plan_sha256=plan_sha256)
    path = workflow._path(output_dir)
    require(path.is_dir() and not path.is_symlink(), 'regular baseline diagnostic directory required')
    require({p.name for p in path.iterdir()} == {'binding.json', 'diagnostic-started.json',
            'diagnostic-finished.json'}, 'unfinished baseline diagnostics; retry forbidden')
    binding = {'schema_id': 'cpu_unrefined_diagnostic_binding/1.0.0',
               'baseline_result_sha256': baseline['result_sha256'], 'plan_sha256': plan_sha256,
               'implementation_sha256': digest(cartesian.implementation_sources(identity['external_binding']['model']))}
    require(workflow._read(path / 'binding.json') == binding
            and workflow._read(path / 'diagnostic-started.json') == {'binding_sha256': digest(binding)},
            'baseline diagnostic binding mismatch')
    record = workflow._read(path / 'diagnostic-finished.json')
    require_digest(expected_record_sha256)
    require(record['record_sha256'] == expected_record_sha256 == digest(
        {k: v for k, v in record.items() if k != 'record_sha256'}), 'baseline diagnostic digest mismatch')
    require(record['source_evidence_verified'] is True and record['observation_ref'] == {
        'kind': 'verified_baseline', 'result_sha256': baseline['result_sha256']},
        'baseline diagnostic source mismatch')
    return record

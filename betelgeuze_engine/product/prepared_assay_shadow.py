"""Run the existing public assay predictor alongside explicit prepared cases.

Caller metadata is kept separate from prepared particles. This module performs
no chemical-state join, score combination, selection, training or preparation.
"""
from __future__ import annotations

import copy
import time


def evaluate_assay_shadow(cases: list, configuration) -> tuple[list[dict], dict]:
    started, cpu = time.perf_counter(), time.process_time()
    rows, indices, inputs = [], [], []
    for index, case in enumerate(cases):
        present = isinstance(case, dict) and 'assay_metadata' in case
        metadata = case.get('assay_metadata') if present else None
        row = {'request_index': index, 'status': 'unsupported' if present else 'not_requested',
               'reason': 'invalid_assay_metadata' if present else 'assay_metadata_not_supplied',
               'input_metadata': copy.deepcopy(metadata), 'prediction': None,
               'evidence_kind': 'ai_prediction', 'mean_baseline_evidence_kind': 'heuristic',
               'input_scope': 'caller_supplied_catalogue_metadata_not_prepared_particles',
               'same_prepared_or_assay_state_verified': False,
               'combined_score': None, 'residual_training_eligible': False,
               'affects_physical_evaluation_or_ranking': False}
        rows.append(row)
        if present and isinstance(metadata, dict):
            indices.append(index)
            inputs.append(metadata)
    model_metadata, model_error = None, None
    if indices:
        try:
            if (not isinstance(configuration, dict)
                    or set(configuration) != {'checkpoint', 'checkpoint_sha256'}
                    or any(type(configuration[k]) is not str or not configuration[k]
                           for k in ('checkpoint', 'checkpoint_sha256'))):
                raise ValueError('invalid_assay_selector_configuration')
            from betelgeuze_engine.product.public_assay_selector_shadow import load_public_assay_selector
            model = load_public_assay_selector(configuration['checkpoint'],
                                               expected_sha256=configuration['checkpoint_sha256'])
            model_metadata = model.metadata
            predictions = model.predict_rows(inputs)
            if len(predictions) != len(indices):
                raise ValueError('selector_prediction_count_mismatch')
            for index, prediction in zip(indices, predictions):
                rows[index].update(status=prediction['status'], reason=prediction['reason'],
                                   prediction={**prediction, 'row_index': index})
        except Exception as exc:
            model_error = f'{type(exc).__name__}:{exc}'
            for index in indices:
                rows[index].update(status='unsupported', reason='model_unavailable:' + model_error,
                                   prediction=None)
    summary = {'schema_version': 'prepared_assay_selector_shadow_v1',
               'model': model_metadata, 'model_error': model_error,
               'denominator': {'requested_cases': len(rows),
                               **{key: sum(r['status'] == key for r in rows)
                                  for key in ('evaluated', 'unsupported', 'not_requested')}},
               'customer_execution': False, 'product_ranking_enabled': False,
               'uncertainty_calibrated': False, 'same_state_residual_available': False,
               'cost': {'wall_seconds': time.perf_counter() - started,
                        'cpu_seconds': time.process_time() - cpu,
                        'scope': 'one model load, metadata admission, all features and predictions; before physical case evaluation'}}
    return rows, summary

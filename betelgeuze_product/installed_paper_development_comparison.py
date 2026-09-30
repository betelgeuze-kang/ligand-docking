"""Label-free retained-paper development execution using the unchanged CPU solver.

Source descriptors never assign dataset roles or admit experimental values.
Preparation evidence is a role-neutral representation/geometry binding. Numerical
results remain baseline/refined computational observations, never affinity labels.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re

from .comparison_receipts import HEX, MAX_JSON_BYTES, _canonical, _json, _private_dir, _regular_file, _require, _sha
from . import comparison_receipts as receipts
from . import installed_synthetic_comparison as publication
from .installed_synthetic_comparison import _lock, _publish, _committed
from . import installed_native_v4_registered_binding as structural
from . import native_v4_chemical_identity as chemistry
from . import registered_cartesian_policy_adapter as adapter
from .cpu_refinement_v1_2 import registered_policy_adapter as original_adapter
from .cpu_refinement_v1_3 import workflow
from .cpu_refinement_v1_3.contracts import SolverConfig

SOURCE = "retained_paper_label_free_development_source_v1"
IDENTITY = "retained_paper_label_free_identity_statement_v1"
PREPARED = "retained_paper_registered_preparation_evidence_v1"
PROTOCOL = "installed_paper_development_cartesian_protocol_v1"
FROZEN = "installed_paper_development_cartesian_frozen_v1"
RESULT = "installed_paper_development_cartesian_result_v1"
MAX_CANDIDATES = 64
BOUNDARY = {
    "assigned_role": None, "independent_measurement_denominator": None,
    "source_authenticated": False, "same_prepared_assay_state_verified": False,
    "assayed_microstate_verified": False, "training_admitted": False,
    "calibration_admitted": False, "independent_evaluation_admitted": False,
    "product_ranking_enabled": False, "scientifically_validated": False,
}
TARGET = {"species": "Homo sapiens", "gene_symbol": "HTR6",
          "catalogue_target_annotation": "CHEMBL3371", "physical_state_verified": False}


def _fields(value, names):
    _require(type(value) is dict and set(value) == set(names), "paper_development_exact_fields_required")


def _text(value):
    _require(type(value) is str and value.strip() and len(value) <= 2048,
             "paper_development_bounded_text_required")


def _raw(ref):
    _fields(ref, {"path", "sha256"})
    _text(ref["path"])
    path = Path(ref["path"])
    _require(path.is_absolute() and str(path.resolve(strict=True)) == ref["path"],
             "paper_development_canonical_source_path_required")
    _require(type(ref["sha256"]) is str and HEX.fullmatch(ref["sha256"]),
             "paper_development_source_sha256_required")
    raw = _regular_file(path, MAX_JSON_BYTES)
    _require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "paper_development_source_hash_mismatch")
    return raw


def _document(ref):
    return _json(_raw(ref))


def _source(ref):
    source = _document(ref)
    _fields(source, {"schema_version", "doi", "local_compound_id", "occurrence_id",
                     "target", "method", "evidence", "chemical_identity", "boundary"})
    _require(source["schema_version"] == SOURCE, "retained_paper_source_required")
    doi, compound, occurrence = (source[k] for k in ("doi", "local_compound_id", "occurrence_id"))
    _require(type(doi) is str and re.fullmatch(r"10\.[0-9]{4,9}/[^\s#]+", doi)
             and doi == doi.lower(), "paper_development_normalized_doi_required")
    _require(type(compound) is str and re.fullmatch(r"PR[1-9][0-9]{0,3}", compound),
             "paper_development_local_study_compound_required")
    _require(type(occurrence) is str and re.fullmatch(r"[a-z0-9_.-]+:" + compound, occurrence),
             "paper_development_local_occurrence_required")
    _require(_canonical(source["target"]) == _canonical(TARGET), "paper_development_target_annotation_required")
    _require(_canonical(source["boundary"]) == _canonical(BOUNDARY), "paper_development_authority_promotion")
    method = source["method"]
    _fields(method, {"local_method_id", "endpoint_context", "physical_pages", "evidence"})
    _require(type(method["local_method_id"]) is str
             and re.fullmatch(r"section_[0-9.]+", method["local_method_id"]), "paper_local_method_id_required")
    _require(method["endpoint_context"] == "reported_human_5ht6_radioligand_binding_Ki",
             "paper_binding_endpoint_context_required")
    pages = method["physical_pages"]
    _require(type(pages) is list and 1 <= len(pages) <= 8
             and all(type(p) is int and 1 <= p <= 10000 for p in pages)
             and len(set(pages)) == len(pages), "paper_method_pages_required")
    _fields(source["evidence"], {"article", "identity_statement"})
    _require(method["evidence"] == source["evidence"]["article"], "paper_method_article_binding_required")
    _raw(source["evidence"]["article"])
    identity = _document(source["evidence"]["identity_statement"])
    _fields(identity, {"schema_version", "doi", "local_compound_id", "occurrence_id", "chemical_identity", "source_evidence"})
    _require(identity["schema_version"] == IDENTITY
             and all(identity[k] == source[k] for k in ("doi", "local_compound_id", "occurrence_id", "chemical_identity")),
             "paper_identity_statement_candidate_mismatch")
    _raw(identity["source_evidence"])
    proposed = source["chemical_identity"]
    _require(type(proposed) is dict and type(proposed.get("canonical_isomeric_smiles")) is str,
             "paper_chemical_identity_required")
    _require(_canonical(chemistry.chemical_identity(proposed["canonical_isomeric_smiles"])) == _canonical(proposed),
             "paper_chemical_identity_not_canonical")
    _raw(ref)
    return source


def candidate_id(source):
    return "paper:" + source["doi"] + ":" + source["occurrence_id"]


def _preparation(source_ref, request_ref, charge_ref, initial_protocol_ref, model_evidence_ref):
    """Rederive representation checks, never fabricate a native assay row."""
    from betelgeuze_engine_v2.molecular.serialization import (
        all_atom_system_from_canonical_json, canonical_coordinates_sha256, canonical_system_sha256,
    )
    from .reference_minimization_workflow import _parameters
    from .cpu_refinement_v1_2.workflow import _extension
    from .cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment

    source, request = _source(source_ref), _document(request_ref)
    _raw(initial_protocol_ref)
    _raw(model_evidence_ref)
    original_binding = original_adapter.input_binding(request)
    receptor, ligand = (all_atom_system_from_canonical_json(_raw(request[k])) for k in ("receptor", "ligand"))
    base = _parameters(_document(request["parameters"]))
    parameters = _extension(_document(request["extensions"]), base)
    _require(not parameters.constraints, "paper_development_unconstrained_model_required")
    cross_doc = _document(request["cross_parameters"])
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(cross_doc))
    fixed.validate_ligand(ligand, base)
    identity = structural._ligand_identity(ligand, source["chemical_identity"])
    charge = structural._charge_screen(charge_ref, request, ligand, base)
    _require(charge["rank_eligible"] is True, "paper_development_charge_representation_ineligible")
    geometry = structural._pose_geometry_status(receptor, ligand, request)
    _require(geometry["rank_eligible_inside_pocket"] == 1, "paper_development_registered_geometry_ineligible")
    receptor_doc = {"system_sha256": canonical_system_sha256(receptor),
                    "coordinates_sha256": canonical_coordinates_sha256(receptor),
                    "construct_sha256": _sha(structural._construct(receptor)), "atom_count": receptor.atom_count}
    cohort = {
        "doi": source["doi"], "target_sha256": _sha(source["target"]), "method_sha256": _sha(source["method"]),
        "article_sha256": source["evidence"]["article"]["sha256"],
        "initial_pose_protocol_sha256": initial_protocol_ref["sha256"],
        "receptor_source_sha256": request["receptor"]["sha256"], "receptor": receptor_doc,
        "receptor_cross_parameters_sha256": _sha(cross_doc["receptor_atoms"]),
        "cross_model_sha256": _sha({k: v for k, v in cross_doc.items() if k not in {
            "receptor_atoms", "ligand_topology_sha256", "ligand_base_parameters_sha256",
            "receptor_system_sha256", "parameter_source_sha256", "parameter_set_id"}}),
        "pocket_sha256": _sha(request["pocket"]), "coordinate_frame_id": request["pocket"]["coordinate_frame_id"],
        "original_settings_sha256": _sha({k: request[k] for k in (
            "schema_id", "backend", "budget", "solver", "comparison", "selection", "solvation", "receptor_margin_angstrom")}),
    }
    descriptor = {"schema_version": PREPARED, "candidate_id": candidate_id(source),
                  "source_sha256": source_ref["sha256"], "original_request_sha256": _sha(request),
                  "original_request_file_sha256": request_ref["sha256"], "original_binding_sha256": _sha(original_binding),
                  "charge_origin": deepcopy(charge_ref), "initial_pose_protocol": deepcopy(initial_protocol_ref),
                  "declared_model_evidence": deepcopy(model_evidence_ref),
                  "original_source_parameter_equivalence_verified": False,
                  "xml_origin_scope": "original_decimal_charge_tokens_and_index_map_only",
                  "parameter_model_scope": "declared_native_model_not_automatic_XML_conversion_equivalence",
                  "ligand": identity, "receptor": receptor_doc, "charge_screen": charge,
                  "geometry": geometry, "cohort": cohort, "boundary": deepcopy(BOUNDARY)}
    for ref in (source_ref, request_ref, charge_ref, initial_protocol_ref, model_evidence_ref):
        _raw(ref)
    return descriptor, request


def derive_prepared_evidence(source_ref, original_request_ref, charge_origin_ref, *, initial_pose_protocol, declared_model_evidence):
    """Create metadata to save separately; no force, score or role assignment."""
    return _preparation(source_ref, original_request_ref, charge_origin_ref,
                        initial_pose_protocol, declared_model_evidence)[0]


def freeze(protocol):
    _fields(protocol, {"schema_version", "candidates", "cartesian_solver"})
    _require(protocol["schema_version"] == PROTOCOL, "explicit_paper_development_protocol_required")
    config = SolverConfig.from_dict(protocol["cartesian_solver"])
    candidates = protocol["candidates"]
    _require(type(candidates) is list and 1 <= len(candidates) <= MAX_CANDIDATES,
             "bounded_paper_development_candidates_required")
    seen, rows, cohorts = set(), [], set()
    for entry in candidates:
        _fields(entry, {"candidate_id", "source", "original_request", "prepared_evidence"})
        source = _source(entry["source"])
        rid = candidate_id(source)
        _require(entry["candidate_id"] == rid and rid not in seen, "paper_development_candidate_identity_mismatch")
        seen.add(rid)
        row = {"candidate_id": rid, "source": source, "blockers": [], "original_request": None,
               "prepared_evidence": None, "request": None, "input_binding": None}
        rows.append(row)
        if entry["original_request"] is None or entry["prepared_evidence"] is None:
            row["blockers"].append("paper_registered_preparation_missing")
            continue
        try:
            supplied = _document(entry["prepared_evidence"])
            _fields(supplied, {"schema_version", "candidate_id", "source_sha256", "original_request_sha256",
                              "original_request_file_sha256", "original_binding_sha256", "charge_origin",
                              "initial_pose_protocol", "declared_model_evidence", "original_source_parameter_equivalence_verified",
                              "xml_origin_scope", "parameter_model_scope",
                              "ligand", "receptor", "charge_screen", "geometry", "cohort", "boundary"})
            expected, original = _preparation(entry["source"], entry["original_request"], supplied["charge_origin"],
                                              supplied["initial_pose_protocol"], supplied["declared_model_evidence"])
            _require(_canonical(expected) == _canonical(supplied), "paper_registered_prepared_evidence_mismatch")
            converted = workflow.prepare_cartesian_request(original, config)
            binding = adapter.input_binding(converted)
            row.update(original_request=original, prepared_evidence=expected, request=converted, input_binding=binding)
            cohorts.add(_sha(expected["cohort"]))
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            row["blockers"].append(type(exc).__name__ + ":" + str(exc))
    if len(cohorts) > 1:
        for row in rows:
            row["blockers"].append("paper_development_common_cohort_mismatch")
    ready = sum(not row["blockers"] for row in rows)
    return {"schema_version": FROZEN, "protocol": deepcopy(protocol), "candidates": rows,
            "requested_candidate_count": len(rows), "prepared_candidate_count": ready,
            "distinct_prepared_chemical_count": len({row["source"]["chemical_identity"]["canonical_isomeric_smiles_sha256"]
                                                      for row in rows if not row["blockers"]}),
            "runtime_sha256": _sha({Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                     for p in (__file__, structural.__file__, chemistry.__file__, adapter.__file__,
                                               receipts.__file__, publication.__file__)}),
            "evaluation_labels_read": 0, "model_fit_performed": False, "boundary": deepcopy(BOUNDARY)}


def preflight(protocol):
    frozen = freeze(protocol)
    return {"schema_version": PROTOCOL + "/preflight", "status": "ready" if frozen["prepared_candidate_count"] else "blocked",
            "frozen_sha256": _sha(frozen), "requested_candidate_count": frozen["requested_candidate_count"],
            "prepared_candidate_count": frozen["prepared_candidate_count"],
            "blockers": {r["candidate_id"]: r["blockers"] for r in frozen["candidates"] if r["blockers"]},
            "evaluation_labels_read": 0, "model_fit_performed": False, "boundary": deepcopy(BOUNDARY)}


def _candidate_directory(directory, rid):
    return directory / (_sha(rid) + ".cartesian")


def _complete_row(row, directory):
    request = row["request"]
    report = _committed(directory / "result.json")
    indices, unfinished, problems = workflow._invocation_inventory(directory)
    _require(not unfinished and not problems, "paper_development_completed_invocation_evidence_missing")
    _require(not workflow._unresolved_numerical_invocations(directory, indices),
             "paper_development_prior_numerical_work_unknown")
    matching = []
    for index in indices:
        end = _committed(directory / f"invocation-{index:06d}.end.json")
        if end.get("completed_result_sha256") == report["result_sha256"]:
            matching.append(end)
    _require(bool(matching), "paper_development_completed_invocation_evidence_missing")
    invocation = matching[-1]
    _require(invocation.get("error") is None and invocation.get("finalization_error") is None,
             "paper_development_completed_invocation_error")
    wrapped = {"schema_version": adapter.RESULT_SCHEMA, "backend": adapter.BACKEND,
               "request": request, "comparison": report, "invocation": invocation}
    summary = adapter.summarize(wrapped, request=request, run_dir=directory)
    _require(report["binding"] == row["input_binding"],
             "paper_development_saved_result_binding_mismatch")
    attempt = report["attempt"]
    accepted = report["numerical_result"]["checkpoint"]["state"]["accepted"]
    admitted = bool(report["per_arm_selection"]["refined"]["selected_candidates"])
    state = ("rejected" if not admitted else "no_refinement" if accepted == 0 else "converged")
    return {"candidate_id": row["candidate_id"], "status": "completed", "refinement_state": state,
            "refined_selection_admitted": admitted, "attempt": deepcopy(attempt),
            "paired_decision": deepcopy(report["paired_decision"]), "result_sha256": report["result_sha256"],
            "baseline": deepcopy(report["rows"]["baseline"]), "refined": deepcopy(report["rows"]["refined"]),
            "raw_per_arm_selection": deepcopy(report["raw_per_arm_selection"]),
            "per_arm_selection": deepcopy(report["per_arm_selection"]),
            "final_selection": deepcopy(report["final_selection"]),
            "work": {"force_work": deepcopy(report["force_work"]), "score_calls": report["score_calls"]},
            "registered_summary": summary,
            "original_source_parameter_equivalence_verified": False,
            "source_model_domain": "declared_native_cutoff_switch_model_not_global_OpenMM_NoCutoff_equivalence",
            "boundary": deepcopy(BOUNDARY)}


def _summary(frozen, rows):
    _require([r["candidate_id"] for r in rows] == [r["candidate_id"] for r in frozen["candidates"]],
             "paper_development_result_denominator_mismatch")
    counts = Counter(row["status"] for row in rows)
    return {"schema_version": RESULT, "frozen_sha256": _sha(frozen), "rows": rows,
            "status": "complete" if all(r["status"] in {"completed", "preparation_blocked"} for r in rows) else "partial",
            "denominator": {"requested": len(rows), **dict(counts)},
            "independent_measurement_denominator": None, "evaluation_labels_read": 0,
            "model_fit_performed": False, "physical_affinity_computed": False,
            "durations_are_inclusive_do_not_sum": True, "boundary": deepcopy(BOUNDARY)}


def _verify_saved(frozen, directory, result):
    expected = []
    for row in frozen["candidates"]:
        if row["blockers"]:
            expected.append({"candidate_id": row["candidate_id"], "status": "preparation_blocked",
                             "blockers": row["blockers"], "force_calls": 0, "score_calls": 0})
        else:
            expected.append(_complete_row(row, _candidate_directory(directory, row["candidate_id"])))
    _require(_canonical(result) == _canonical(_summary(frozen, expected)), "paper_development_result_rederivation_mismatch")
    return result


def run(protocol, output_dir, *, resume=False, pause_after_objective_attempts=None):
    """Retain blocked candidates; explicit known continuation uses durable CPU receipts."""
    _require(type(resume) is bool, "paper_development_explicit_resume_required")
    frozen = freeze(protocol)
    directory = Path(output_dir).absolute()
    _require(str(directory.parent.resolve(strict=True)) == str(directory.parent), "paper_development_canonical_output_parent_required")
    if not resume:
        directory.mkdir(mode=0o700)
    _private_dir(directory)
    fd = _lock(directory / "lock", create=not resume)
    try:
        if resume:
            _require(_committed(directory / "frozen.json") == frozen, "paper_development_frozen_input_changed")
        else:
            _publish(directory / "frozen.json", frozen)
        if (directory / "result.json").exists():
            return _verify_saved(frozen, directory, _committed(directory / "result.json"))
        rows, interrupted = [], False
        for row in frozen["candidates"]:
            rid, child = row["candidate_id"], _candidate_directory(directory, row["candidate_id"])
            if row["blockers"]:
                rows.append({"candidate_id": rid, "status": "preparation_blocked", "blockers": row["blockers"], "force_calls": 0, "score_calls": 0})
                continue
            if interrupted:
                rows.append({"candidate_id": rid, "status": "not_started", "force_calls": 0, "score_calls": 0})
                continue
            intent = directory / (_sha(rid) + ".intent.json")
            expected_intent = {"candidate_id": rid, "frozen_sha256": _sha(frozen), "request_sha256": _sha(row["request"])}
            existed = intent.exists()
            if existed:
                _require(_committed(intent) == expected_intent, "paper_development_candidate_intent_mismatch")
            else:
                _publish(intent, expected_intent)
            if (child / "result.json").exists():
                try:
                    rows.append(_complete_row(row, child))
                except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
                    rows.append({"candidate_id": rid, "status": "interrupted_unknown", "refinement_state": "unknown",
                                 "error_type": type(exc).__name__, "work": adapter.inspect_partial_work(row["request"], child)})
                continue
            if existed and not child.exists():
                rows.append({"candidate_id": rid, "status": "interrupted_unknown", "refinement_state": "unknown",
                             "work": None, "reason": "reserved_candidate_has_no_durable_work"})
                continue
            try:
                envelope = workflow.evaluate(row["request"], child, resume=child.exists(),
                                             pause_after_objective_attempts=pause_after_objective_attempts)
                if envelope["result"]["execution_complete"]:
                    rows.append(_complete_row(row, child))
                else:
                    rows.append({"candidate_id": rid, "status": "checkpointed", "refinement_state": "unfinished",
                                 "work": adapter.inspect_partial_work(row["request"], child)})
            except BaseException as exc:
                rows.append({"candidate_id": rid, "status": "interrupted_unknown", "refinement_state": "unknown",
                             "error_type": type(exc).__name__, "work": adapter.inspect_partial_work(row["request"], child)})
                interrupted = not isinstance(exc, Exception)
        result = _summary(frozen, rows)
        if result["status"] == "complete":
            _publish(directory / "result.json", result)
        else:
            index = len(list(directory.glob("partial-*.json")))
            _publish(directory / f"partial-{index:06d}.json", result)
        return result
    finally:
        os.close(fd)


def verify_run(protocol, output_dir):
    frozen = freeze(protocol)
    directory = Path(output_dir).absolute()
    _private_dir(directory)
    fd = _lock(directory / "lock", create=False, shared=True)
    try:
        _require(_committed(directory / "frozen.json") == frozen, "paper_development_frozen_input_changed")
        result = _verify_saved(frozen, directory, _committed(directory / "result.json"))
        return {"schema_version": RESULT + "/verification", "status": "verified", "result_sha256": _sha(result),
                "denominator": result["denominator"], "execution_performed": False, "boundary": deepcopy(BOUNDARY)}
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run", "resume", "verify"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--pause-after-objective-attempts", type=int)
    args = parser.parse_args(argv)
    protocol = _document({"path": str(args.protocol.absolute()), "sha256": args.expected_protocol_sha256})
    if args.action == "preflight":
        result = preflight(protocol)
    else:
        if args.run_dir is None:
            parser.error("--run-dir is required for execution or verification")
        result = (verify_run(protocol, args.run_dir) if args.action == "verify" else
                  run(protocol, args.run_dir, resume=args.action == "resume",
                      pause_after_objective_attempts=args.pause_after_objective_attempts))
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] in {"ready", "complete", "verified"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

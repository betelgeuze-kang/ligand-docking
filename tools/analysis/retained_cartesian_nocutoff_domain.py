"""Read-only inventory of every retained Cartesian objective/restart coordinate.

Uses JSON seals, serialized binary64 coordinates and pair distances only. No
product evaluator, graph, scorer, optimizer or model loader is imported. A full
trace domain claim fails closed on unknown work or incomplete call inventory.
This is additive evidence; installed deterministic replay remains separately
required and hash-bound, rather than being reimplemented here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time


class TraceDomainError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise TraceDomainError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def no_duplicates(rows):
    value = {}
    for key, item in rows:
        require(key not in value, "duplicate_JSON_key")
        value[key] = item
    return value


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=no_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(TraceDomainError("nonfinite_JSON:" + value)))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TraceDomainError("invalid_JSON:" + str(exc)) from exc


def sealed(value, field):
    require(type(value) is dict and value.get(field) == digest({k: v for k, v in value.items() if k != field}),
            "invalid_" + field)


def integer(value):
    require(type(value) is int and value >= 0, "nonnegative_integer_required")
    return value


def coordinates(values, count):
    require(type(values) is list and len(values) == count and 1 <= count <= 256, "coordinate_atom_count_mismatch")
    parsed = []
    for row in values:
        require(type(row) is list and len(row) == 3, "three_coordinate_components_required")
        atoms = []
        for item in row:
            require(type(item) is str and len(item) <= 32, "binary64_hex_coordinate_required")
            try:
                number = float.fromhex(item)
            except ValueError as exc:
                raise TraceDomainError("invalid_hex_coordinate") from exc
            require(math.isfinite(number) and number.hex() == item, "noncanonical_or_nonfinite_coordinate")
            atoms.append(number)
        parsed.append(atoms)
    return parsed


def domain(values, count, switch_start=90.):
    require(switch_start == 90., "unchanged_90_angstrom_domain_required")
    xyz = coordinates(values, count)
    maximum, pair = 0., None
    for i in range(count):
        for j in range(i):
            distance = math.dist(xyz[i], xyz[j])
            if not math.isfinite(distance):
                return {"passed": False, "maximum_pair_distance_angstrom": None,
                        "pair": [j, i], "reason": "nonfinite_pair_distance"}
            if distance > maximum:
                maximum, pair = distance, [j, i]
    return {"passed": maximum < switch_start, "maximum_pair_distance_angstrom": maximum,
            "pair": pair, "reason": None if maximum < switch_start else "pair_at_or_beyond_switch_start"}


def inventory_events(events, binding_sha256, atom_count):
    require(len(events) <= 16448, "journal_event_capacity_exceeded")
    head, pending, current = binding_sha256, None, None
    counts = {"optimizer_objective_attempts": 0, "optimizer_graph_calls": 0, "optimizer_force_calls": 0,
              "failed_optimizer_force_calls": 0, "restart_verification_attempts": 0,
              "restart_graph_calls": 0, "restart_force_calls": 0, "failed_restart_force_calls": 0}
    rows, outcomes = [], {}
    for index, event in enumerate(events):
        require(set(event) == {"index", "kind", "payload", "previous_sha256", "event_sha256"}, "journal_event_fields_invalid")
        require(type(event["index"]) is int and event["index"] == index, "journal_event_index_invalid")
        require(event["previous_sha256"] == head, "journal_prefix_hash_invalid")
        sealed(event, "event_sha256")
        head = event["event_sha256"]
        kind, payload = event["kind"], event["payload"]
        require(type(payload) is dict and kind in {"objective_started", "objective_finished", "restart_started", "restart_finished"}, "journal_event_kind_invalid")
        if kind.endswith("_started"):
            require(pending is None, "overlapping_or_unfinished_intent")
            restart = kind == "restart_started"
            key = "restart_verification_attempts" if restart else "optimizer_objective_attempts"
            counts[key] += 1
            identity = "verification" if restart else "attempt"
            require(payload.get(identity) == counts[key] and type(payload.get(identity)) is int, "attempt_or_restart_sequence_incomplete")
            if restart:
                require(current is not None and payload.get("current_attempt") == current["attempt"]
                        and payload.get("coordinates") == current["coordinates"], "restart_coordinate_not_current_accepted_state")
            row = {"event_index": index, "kind": kind, "attempt_or_verification": payload[identity],
                   "coordinates_sha256": digest(payload["coordinates"]), "domain": domain(payload["coordinates"], atom_count),
                   "completed": False, "graph_calls": None, "force_calls": None, "failed_force_calls": None, "decision": None}
            rows.append(row)
            pending = (kind, payload, row)
        else:
            require(pending is not None and kind == pending[0].replace("_started", "_finished"), "finish_without_matching_intent")
            restart = kind == "restart_finished"
            identity = "verification" if restart else "attempt"
            require(payload.get(identity) == pending[1][identity], "finish_identity_mismatch")
            work = payload.get("work")
            require(type(work) is dict and set(work) == {"graph_calls", "force_calls", "failed_force_calls"}, "finished_work_fields_invalid")
            graph, force, failed = [integer(work[k]) for k in ("graph_calls", "force_calls", "failed_force_calls")]
            require(0 <= failed <= force <= graph <= 1, "finished_force_call_denominator_invalid")
            observation = payload.get("observation")
            if observation is not None:
                require(payload.get("failure") is None and payload.get("error_type") is None
                        and (graph, force, failed) == (1, 1, 0), "successful_work_denominator_invalid")
                require(observation.get("coordinates") == pending[1]["coordinates"], "observation_coordinate_differs_from_reserved_intent")
                require(observation.get("attempt") == (pending[1].get("current_attempt") if restart else pending[1]["attempt"]), "observation_attempt_mismatch")
            else:
                require(payload.get("failure") in {"fatal", "retryable"} and type(payload.get("error_type")) is str
                        and failed == force, "failed_work_denominator_invalid")
            prefix = "restart" if restart else "optimizer"
            counts[prefix + "_graph_calls"] += graph
            counts[prefix + "_force_calls"] += force
            counts["failed_" + prefix + "_force_calls"] += failed
            decision = None if restart else payload.get("decision", {}).get("outcome")
            if restart:
                require(type(payload.get("matched")) is bool and payload["matched"] == (observation == current), "restart_match_receipt_invalid")
            else:
                require(decision in {"initial", "accepted", "rejected_evaluation", "rejected_displacement", "rejected_non_descent", "rejected_armijo"}, "objective_decision_invalid")
                outcomes[decision] = outcomes.get(decision, 0) + 1
                if decision in {"initial", "accepted"}:
                    require(observation is not None, "accepted_objective_has_no_observation")
                    current = observation
            pending[2].update(completed=True, graph_calls=graph, force_calls=force, failed_force_calls=failed, decision=decision)
            pending = None
    known = counts["optimizer_force_calls"] + counts["restart_force_calls"]
    return {"counts": {**counts, "known_completed_force_calls": known,
                       "unknown_pending_attempts": int(pending is not None),
                       "actual_force_calls": None if pending is not None else known},
            "rows": rows, "outcomes": outcomes, "head_sha256": head, "current": current,
            "complete": pending is None, "all_reserved_coordinates_inside_domain": all(r["domain"]["passed"] for r in rows)}


def invocation_inventory(receipts, request_sha256, trace_counts):
    problems, unknown, known_outer_calls = [], [], 0
    indices = sorted({index for index, _ in receipts})
    if indices != list(range(len(indices))):
        problems.append("outer_invocation_indices_not_contiguous")
    if not indices:
        problems.append("outer_invocation_history_absent")
    for index in indices:
        start, end = receipts.get((index, "start")), receipts.get((index, "end"))
        if start is None:
            unknown.append({"index": index, "reason": "invocation_start_missing"})
        else:
            require(start.get("request_sha256") == request_sha256, "invocation_request_binding_invalid")
        if end is None:
            unknown.append({"index": index, "reason": "invocation_end_missing"})
            continue
        require(end.get("index") == index and type(end.get("numerical_entrypoint_invoked")) is bool, "invocation_end_fields_invalid")
        invoked, calls = end["numerical_entrypoint_invoked"], end.get("new_force_calls")
        if calls is None:
            unknown.append({"index": index, "reason": "new_force_calls_unknown"})
        else:
            known_outer_calls += integer(calls)
            require(invoked or calls == 0, "uninvoked_entrypoint_reports_force_calls")
        for field in ("numerical_work_before", "numerical_work_after"):
            saved = end.get(field)
            if saved is None:
                if invoked:
                    unknown.append({"index": index, "reason": field + "_unknown"})
                continue
            require(type(saved) is dict, "invocation_work_dictionary_required")
            if saved.get("actual_force_calls") is None or saved.get("unknown_pending_attempts", 0) != 0:
                unknown.append({"index": index, "reason": field + "_contains_unknown_work"})
            for key, value in trace_counts.items():
                if key == "unknown_pending_attempts" or value is None or saved.get(key) is None:
                    continue
                require(integer(saved[key]) <= value, "journal_behind_retained_outer_work:" + key)
        if end.get("prior_unresolved_numerical_invocations"):
            unknown.append({"index": index, "reason": "prior_unresolved_numerical_invocation"})
    if trace_counts["actual_force_calls"] is not None and known_outer_calls != trace_counts["actual_force_calls"]:
        problems.append("outer_new_force_calls_do_not_cover_journal_calls")
    return {"known_new_force_calls_in_outer_receipts": known_outer_calls, "unknown_invocations": unknown,
            "problems": problems, "unknown_invocation_count": len({item["index"] for item in unknown}),
            "complete": not problems and not unknown}


def source_coordinates(document):
    require(document.get("system_sha256") == digest(document["system"]), "canonical_ligand_system_seal_invalid")
    tensor = document["system"]["coordinates"]["coordinates"]["$tensor"]
    shape = tensor["shape"]
    require(shape[0] == 1 and shape[2] == 3 and tensor["dtype"] == "float64", "canonical_ligand_coordinate_shape_invalid")
    tokens = [row["$float_hex"] for row in tensor["values"]]
    require(len(tokens) == shape[1] * 3, "canonical_ligand_coordinate_count_invalid")
    return [tokens[i:i + 3] for i in range(0, len(tokens), 3)]


def verify_run(run_directory, installed_verification_receipt, switch_start=90.):
    directory = Path(run_directory).absolute()
    before = {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(directory.rglob("*")) if p.is_file() and p.name != ".journal.lock" and not p.is_symlink()}
    require(not any(p.is_symlink() for p in directory.rglob("*")), "trace_symlinks_unsupported")
    def read(path):
        raw = Path(path).read_bytes()
        require(len(raw) <= 128 * 1024 * 1024, "bounded_trace_file_required")
        return decode(raw)
    require({p.name for p in (directory / "numerical").iterdir()} <= {".journal.lock", "meta.json", "events.jsonl", "checkpoints", "result.json"}, "unexpected_or_partial_numerical_trace_files")
    request, binding = read(directory / "request.json"), read(directory / "binding.json")
    sealed(binding, "receipt_sha256")
    require(binding["request_sha256"] == digest(request), "outer_request_binding_invalid")
    require(binding["input_files"] == {k: request[k] for k in ("receptor", "ligand", "parameters", "extensions", "cross_parameters")}, "outer_input_binding_invalid")
    inputs = {}
    for key, item in binding["input_files"].items():
        raw = Path(item["path"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == item["sha256"], "prepared_input_hash_invalid:" + key)
        inputs[key] = decode(raw)
    require(inputs["parameters"]["switch_start_angstrom"] == switch_start == 90.
            and inputs["extensions"]["nonbonded_domain"] == "nocutoff_equivalent_inside_switch"
            and inputs["parameters"]["dielectric"] == 1. and inputs["parameters"]["screening_kappa_per_angstrom"] == 0., "unchanged_source_domain_contract_required")
    reservation = read(directory / "numerical-start-intent.json")
    require(reservation.get("binding_sha256") == binding["receipt_sha256"]
            and reservation.get("numerical_directory") == "numerical" and reservation.get("reserved_numerical_runs") == 1, "single_numerical_run_reservation_required")
    initial = source_coordinates(inputs["ligand"])
    meta = read(directory / "numerical/meta.json")
    require(meta["binding_sha256"] == digest(meta["binding"]) and meta["binding"]["external_binding"] == binding
            and meta["binding"]["source_system_sha256"] == inputs["ligand"]["system_sha256"], "numerical_source_binding_invalid")
    raw_events = (directory / "numerical/events.jsonl").read_bytes()
    events = []
    for line in raw_events.splitlines(keepends=True):
        event = decode(line)
        require(line == (canonical(event) + "\n").encode("ascii"), "noncanonical_or_truncated_journal_record")
        events.append(event)
    inventory = inventory_events(events, meta["binding_sha256"], len(initial))
    require(events and events[0]["kind"] == "objective_started" and events[0]["payload"]["coordinates"] == initial, "first_objective_not_immutable_initial_coordinates")
    heads = [meta["binding_sha256"]] + [event["event_sha256"] for event in events]
    for path in sorted((directory / "numerical/checkpoints").glob("*")):
        require(re.fullmatch(r"checkpoint-\d{5}\.json", path.name) is not None, "unexpected_checkpoint_file")
        checkpoint = read(path)
        sealed(checkpoint, "checkpoint_sha256")
        count = integer(checkpoint["journal_count"])
        require(count <= len(events) and int(path.stem.split("-")[-1]) == count
                and checkpoint["journal_sha256"] == heads[count], "checkpoint_prefix_invalid")
        if count and events[count - 1]["kind"].endswith("_finished"):
            require(digest(checkpoint["state"]) == events[count - 1]["payload"]["state_sha256"], "checkpoint_state_differs_from_finished_event")
    outer = read(directory / "result.json")
    sealed(outer, "result_sha256")
    require(outer["binding"] == binding, "outer_result_binding_invalid")
    numerical = outer["numerical_result"]
    sealed(numerical, "result_sha256")
    require(numerical["binding_sha256"] == meta["binding_sha256"], "numerical_result_binding_invalid")
    checkpoint = numerical["checkpoint"]
    sealed(checkpoint, "checkpoint_sha256")
    require(checkpoint["journal_count"] == len(events) and checkpoint["journal_sha256"] == inventory["head_sha256"], "final_checkpoint_prefix_invalid")
    require(checkpoint["state"]["current"] == inventory["current"], "final_current_not_last_retained_accepted_observation")
    for key, value in inventory["counts"].items():
        require(numerical["work"].get(key) == value, "final_work_differs_from_all_event_inventory:" + key)
    envelope = read(directory / "numerical/result.json")
    sealed(envelope, "result_sha256")
    require(envelope["result"] == numerical and envelope["journal_count"] == len(events)
            and envelope["journal_sha256"] == inventory["head_sha256"], "terminal_numerical_result_differs_from_outer")
    receipts = {}
    for path in directory.glob("invocation-*"):
        match = re.fullmatch(r"invocation-(\d{6})\.(start|end)\.json", path.name)
        require(match is not None, "unexpected_outer_invocation_file")
        receipts[(int(match[1]), match[2])] = read(path)
    invocations = invocation_inventory(receipts, digest(request), inventory["counts"])
    verification_raw = Path(installed_verification_receipt).read_bytes()
    verification = decode(verification_raw)
    require(verification.get("structural_verification_passed") is True
            and verification.get("result_sha256") == outer["result_sha256"]
            and verification.get("numerical_evaluation_reexecuted") is False
            and verification.get("scoring_reexecuted") is False, "separate_installed_semantic_replay_receipt_required")
    for key, item in binding["input_files"].items():
        require(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"], "prepared_input_changed_during_domain_audit:" + key)
    after = {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(directory.rglob("*")) if p.is_file() and p.name != ".journal.lock"}
    require(before == after, "retained_trace_changed_during_audit")
    require(Path(installed_verification_receipt).read_bytes() == verification_raw, "installed_verification_receipt_changed_during_audit")
    passed = inventory["complete"] and invocations["complete"] and inventory["all_reserved_coordinates_inside_domain"]
    known = inventory["counts"]["known_completed_force_calls"]
    return {"schema_id": "retained_cartesian_nocutoff_domain/1", "status": "passed" if passed else "blocked",
            "full_retained_trace_source_domain_claim_passed": passed, "switch_start_angstrom": switch_start,
            "strict_pair_distance_inequality": "every_pair_distance_angstrom < 90",
            "trace_files": before, "installed_verification_receipt": {"path": str(installed_verification_receipt),
                "sha256": hashlib.sha256(verification_raw).hexdigest()},
            "prepared_input_files": binding["input_files"], "event_count": len(events), "work": {**inventory["counts"],
                "actual_force_calls": known if inventory["complete"] and invocations["complete"] else None},
            "objective_decisions": inventory["outcomes"], "coordinate_rows": inventory["rows"],
            "outer_invocation_inventory": invocations, "initial_coordinate_domain": domain(initial, len(initial)),
            "final_coordinates_binary64_hex": inventory["current"]["coordinates"] if inventory["current"] is not None else None,
            "no_new_force_score_graph_or_optimization_calls": True,
            "same_math_at_every_trial_verified": False, "scientific_qualification": False}


def recover_prefix_for_blocked_report(directory):
    """Retain only a validated sealed prefix; unknown suffix work stays unknown."""
    try:
        directory = Path(directory)
        meta = decode((directory / "numerical/meta.json").read_bytes())
        require(meta["binding_sha256"] == digest(meta["binding"]), "partial_meta_seal_invalid")
        request = decode((directory / "request.json").read_bytes())
        ref = request["ligand"]
        raw = Path(ref["path"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "partial_ligand_pin_invalid")
        initial = source_coordinates(decode(raw))
        require(meta["binding"]["source_system_sha256"] == decode(raw)["system_sha256"], "partial_source_binding_invalid")
        count = len(initial)
        journal = (directory / "numerical/events.jsonl").read_bytes()
        require(len(journal) <= 128 * 1024 * 1024, "bounded_partial_journal_required")
        events, offset, syntax_reason = [], 0, None
        for line in journal.splitlines(keepends=True):
            try:
                event = decode(line)
                require(line == (canonical(event) + "\n").encode("ascii"), "partial_event_canonical_form_invalid")
            except (TraceDomainError, ValueError, TypeError) as exc:
                syntax_reason = str(exc)
                break
            events.append(event)
            offset += len(line)
            if len(events) > 16448:
                syntax_reason = "partial_journal_event_capacity_exceeded"
                events.pop()
                offset -= len(line)
                break
        # A semantically bad record cannot erase its earlier valid sealed prefix.
        # Prefix validity is monotone, so bounded binary search avoids quadratic replay.
        low, high = 0, len(events)
        while low < high:
            middle = (low + high + 1) // 2
            try:
                inventory_events(events[:middle], meta["binding_sha256"], count)
            except (TraceDomainError, KeyError, TypeError, IndexError, ValueError):
                high = middle - 1
            else:
                low = middle
        prefix = events[:low]
        require(not prefix or (prefix[0]["kind"] == "objective_started"
            and prefix[0]["payload"]["coordinates"] == initial), "partial_first_objective_not_immutable_initial")
        inventory = inventory_events(prefix, meta["binding_sha256"], count)
        prefix_bytes = sum(len((canonical(event) + "\n").encode("ascii")) for event in prefix)
        unparsed = len(journal) - prefix_bytes
        semantic_reason = None
        if low < len(events):
            try:
                inventory_events(events[:low + 1], meta["binding_sha256"], count)
            except (TraceDomainError, KeyError, TypeError, IndexError, ValueError) as exc:
                semantic_reason = str(exc)
        return {"work": {**inventory["counts"], "actual_force_calls": None,
                    "known_pending_reserved_attempts": inventory["counts"]["unknown_pending_attempts"],
                    "unknown_pending_attempts": None if unparsed else inventory["counts"]["unknown_pending_attempts"],
                    "known_work_scope": "valid_retained_event_prefix_only_outer_completeness_not_established"},
                "event_count": low, "coordinate_rows": inventory["rows"], "objective_decisions": inventory["outcomes"],
                "valid_prefix_head_sha256": inventory["head_sha256"],
                "valid_prefix_bytes": prefix_bytes, "unparsed_journal_bytes": unparsed,
                "unparsed_journal_sha256": hashlib.sha256(journal[prefix_bytes:]).hexdigest() if unparsed else None,
                "journal_sha256": hashlib.sha256(journal).hexdigest(),
                "unparsed_journal_reason": semantic_reason or syntax_reason,
                "all_valid_prefix_reserved_coordinates_inside_domain": inventory["all_reserved_coordinates_inside_domain"]}
    except (TraceDomainError, KeyError, TypeError, IndexError, OSError, ValueError) as exc:
        return {"work": {"actual_force_calls": None, "known_completed_force_calls": None,
                    "unknown_pending_attempts": None, "known_work_scope": "not_established"},
                "event_count": None, "coordinate_rows": [], "recovery_error": str(exc)}


def recover_known_work_for_blocked_report(directory):
    return recover_prefix_for_blocked_report(directory)["work"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--installed-verification-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    try:
        report = verify_run(args.run_directory, args.installed_verification_receipt)
    except (TraceDomainError, KeyError, TypeError, IndexError, OSError, ValueError) as exc:
        report = {"schema_id": "retained_cartesian_nocutoff_domain/1", "status": "blocked",
            "full_retained_trace_source_domain_claim_passed": False, "error_type": type(exc).__name__, "reason": str(exc),
            **recover_prefix_for_blocked_report(args.run_directory),
            "no_new_force_score_graph_or_optimization_calls": True, "scientific_qualification": False}
    report["elapsed_read_and_pair_distance_seconds"] = time.perf_counter() - start
    report["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"coordinate_rows", "trace_files", "final_coordinates_binary64_hex"}}, sort_keys=True))
    if report["status"] != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

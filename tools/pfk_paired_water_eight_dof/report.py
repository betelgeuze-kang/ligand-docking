"""Post-campaign labels and costs for all six declared paired research arms.

No evaluator, optimizer, pose selection or preparation is invoked. Reference
alignment and structural measurements run only after exact frozen-plan admission.
Missing endpoints remain missing; failed criteria remain failed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
import platform
from pathlib import Path
import sys
import time

from . import journal, protocol


ARMS = ("P0-dry", "P0-wet", "Qplus-dry", "Qplus-wet", "Qminus-dry", "Qminus-wet")


class ReportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReportError(message)


class Artifacts:
    """Read regular artifacts and bind their exact bytes; never mutates them."""
    def __init__(self):
        self.files = {}

    def read(self, path, optional=False):
        path = Path(path)
        if optional and not path.exists() and not path.is_symlink():
            return None
        before = protocol.hash_file(path)
        self.files[str(path)] = before
        value = protocol._json_file(path)
        require(protocol.hash_file(path) == before, "artifact changed during read")
        return value

    def bind(self, path):
        self.files[str(path)] = protocol.hash_file(path)

    def verify(self):
        for path, checksum in self.files.items():
            require(protocol.hash_file(path) == checksum, "artifact changed during reporting: " + path)


def coordinates_from_hex(value):
    require(isinstance(value, list) and value, "coordinate rows required")
    result = []
    for row in value:
        require(isinstance(row, list) and len(row) == 3, "coordinate triplets required")
        numbers = []
        for item in row:
            require(isinstance(item, str), "binary64 hex coordinates required")
            number = float.fromhex(item)
            require(math.isfinite(number) and number.hex() == item, "canonical finite hex required")
            numbers.append(number)
        result.append(numbers)
    return result


def pose_criterion(start_name, labels, margin):
    """New frozen reference metric only; never promotes execution or chemistry."""
    if labels is None or "final" not in labels["states"]:
        return {"criterion": "P0_no_harm" if start_name == "P0" else "Q_own_start_improvement",
                "passed": None, "status": "unavailable_missing_endpoint"}
    comparison = labels["comparison"]
    key = ("final_minus_P0_reference_rmsd_angstrom" if start_name == "P0"
           else "final_minus_start_reference_rmsd_angstrom")
    change = comparison[key]
    return {"criterion": "P0_no_harm" if start_name == "P0" else "Q_own_start_improvement",
            "difference_angstrom": change,
            "margin_angstrom": margin if start_name == "P0" else 0.,
            "passed": change <= margin if start_name == "P0" else change < 0.,
            "status": "measured_new_reference_diagnostic", "historical_reference_reproduced": False}


def phase_cost(plan, phase, route, artifacts):
    caps = plan["stage_caps_by_phase"][phase]
    path = route / "work/dispatch-events.jsonl"
    if not route.exists():
        return {"status": "not_run", "total_work_known": True,
                "total_started_calls": 0, "known_started_calls": 0,
                "counts": {k: {n: 0 for n in ("started", "finished", "succeeded", "failed")}
                           for k in caps}, "pending": {}, "errors": [], "partial_tail_bytes": 0}
    if not path.exists():
        return {"status": "unknown_missing_dispatch_journal", "total_work_known": False,
                "total_started_calls": None, "known_started_calls": 0,
                "counts": {}, "pending": {}, "errors": ["missing dispatch journal"]}
    artifacts.bind(path)
    try:
        result = journal.inspect(path, caps)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return {"status": "unknown_unreadable_dispatch_journal", "total_work_known": False,
                "total_started_calls": None, "known_started_calls": 0, "counts": {},
                "pending": {}, "errors": [type(exc).__name__ + ": " + str(exc)]}
    artifacts.verify()
    result["elapsed_by_kind"] = journal_elapsed(path, result)
    failed = sum(row["failed"] for row in result["counts"].values())
    result["status"] = ("unknown" if not result["total_work_known"] else
                        "known_failed_work" if failed else "known_completed_work")
    result["known_finished_calls"] = sum(row["finished"] for row in result["counts"].values())
    result["known_failed_calls"] = failed
    result["unresolved_reserved_calls"] = sum(
        row["started"] - row["finished"] for row in result["counts"].values())
    return result


def journal_elapsed(path, inspected):
    """Durable paired wall intervals; nested intervals must not be added together."""
    starts, measured = {}, {}
    stop_line = min((e["line"] for e in inspected.get("errors", [])
                     if isinstance(e, dict) and "line" in e), default=float("inf"))
    for number, line in enumerate(Path(path).read_bytes().splitlines(), 1):
        if number >= stop_line:
            break
        try:
            row = json.loads(line)
            elapsed = row["elapsed_seconds"]
            require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
                    "invalid journal elapsed time")
            if row["event"] == "started":
                starts[row["id"]] = elapsed
            elif row["event"] == "finished":
                delta = elapsed - starts.pop(row["id"])
                require(delta >= 0, "decreasing journal time")
                measured.setdefault(row["kind"], []).append(delta)
        except (ValueError, KeyError, TypeError):
            break
    return {"scope": "paired durable stage intervals; nested and nonadditive",
            "geometry_seconds": None, "geometry_timing_measured": False,
            "kinds": {kind: {"finished_intervals": len(values),
                "sum_seconds": math.fsum(values), "minimum_seconds": min(values),
                "maximum_seconds": max(values)} for kind, values in measured.items()}}


def merge_runtime_uncertainty(cost, summary, parent):
    """A readable finish row cannot erase a worker-reported fsync uncertainty."""
    runtime = summary.get("journal_runtime", {}) if summary else {}
    declared = summary.get("ledger", {}) if summary else {}
    parent_ledger = parent.get("ledger", {}) if parent else {}
    uncertain = (runtime.get("publication_uncertain") is True or bool(runtime.get("pending"))
                 or declared.get("runtime_publication_uncertain") is True
                 or bool(declared.get("runtime_pending"))
                 or declared.get("total_work_known") is False
                 or parent_ledger.get("total_work_known") is False)
    if uncertain:
        cost["durable_reparse_total_work_known"] = cost["total_work_known"]
        cost["total_work_known"] = False
        cost["total_started_calls"] = None
        cost["status"] = "unknown_runtime_or_publication_uncertainty"
        cost["runtime_uncertainty"] = {"worker_runtime": runtime,
            "worker_declared_ledger_known": declared.get("total_work_known"),
            "supervisor_declared_ledger_known": parent_ledger.get("total_work_known")}
    return cost


def aggregate_costs(phases):
    """Nested stages are separate counters, never a scalar EF equivalence."""
    known = all(row["cost"]["total_work_known"] for row in phases.values())
    counts = {}
    for row in phases.values():
        for stage, values in row["cost"]["counts"].items():
            target = counts.setdefault(stage, Counter())
            target.update(values)
    return {"total_work_known": known,
            "known_started_stage_calls": sum(row["cost"]["known_started_calls"] for row in phases.values()),
            "total_started_stage_calls": sum(row["cost"]["total_started_calls"] for row in phases.values()) if known else None,
            "known_finished_stage_calls": sum(sum(v["finished"] for v in row["cost"]["counts"].values()) for row in phases.values()),
            "known_failed_stage_calls": sum(sum(v["failed"] for v in row["cost"]["counts"].values()) for row in phases.values()),
            "unknown_phases": [name for name, row in phases.items() if not row["cost"]["total_work_known"]],
            "not_run_phases": [name for name, row in phases.items() if row["cost"]["status"] == "not_run"],
            "verified_prefix_stage_counts": {k: dict(v) for k, v in counts.items()},
            "total_stage_counts": {k: dict(v) for k, v in counts.items()} if known else None,
            "counter_scope": "nested objective/EF/backward/graph/screen counters; their sum is not an EF count",
            "automatic_retry_admitted": False}


def physical_endpoint(work, artifacts):
    endpoint = artifacts.read(work / "endpoint-observation.json", optional=True)
    if endpoint is None:
        return None
    attempt = endpoint["attempt"]
    require(type(attempt) is int and attempt > 0, "retained attempt invalid")
    observed = artifacts.read(work / "observations" / (str(attempt).zfill(5) + ".json"))
    require(endpoint == observed, "endpoint differs from counted observation")
    for key in ("raw_force_max", "allowed_force_max", "reaction_force_max", "energy"):
        require(type(endpoint[key]) in (int, float) and math.isfinite(endpoint[key]),
                "nonfinite endpoint quantity")
    fields = (("raw_force_max", endpoint["physical_observation"]["forces"]),
              ("allowed_force_max", endpoint["allowed_cartesian_forces_hex"]),
              ("reaction_force_max", endpoint["reaction_forces_hex"]))
    for name, packed in fields:
        forces = coordinates_from_hex(packed)
        maximum = max(math.sqrt(math.fsum(v * v for v in row)) for row in forces)
        require(abs(maximum - endpoint[name]) <= 1e-12 * max(1., maximum),
                "retained force norm differs from full array: " + name)
    require(float.fromhex(endpoint["physical_observation"]["energy"]) == endpoint["energy"],
            "retained energy differs from full observation")
    return endpoint


def water_stationarity(plan, endpoint, summary, work, artifacts, wet):
    if endpoint is None:
        return {"status": "unavailable_missing_ligand_endpoint", "restricted_joint_passed": None,
                "raw_joint_passed": None, "dry_counterfactual": not wet}
    observed = artifacts.read(work / "terminal-water-observation.json", optional=True)
    if observed is None:
        return {"status": "unavailable_missing_terminal_water_observation", "restricted_joint_passed": None,
                "raw_joint_passed": None, "dry_counterfactual": not wet}
    require(observed["state_sha256"] == plan["water_checkpoint"]["state_sha256"], "terminal water state differs")
    require(observed.get("mode") == "global" and observed["water_indices"] == list(range(362))
            and all(type(i) is int for i in observed["water_indices"]),
            "complete same-state water census required")
    torque = observed["torques_kcal_per_mol_radian"]
    require(len(torque) == 362 and all(len(row) == 3 for row in torque), "water torque coverage differs")
    require(all(type(v) in (int, float) and math.isfinite(v) for row in torque for v in row),
            "finite numerical water torques required")
    components = dict(observed["components"])
    require(set(components) == {"WP_LJ", "WP_Q", "WL_LJ", "WL_Q", "WW_LJ", "WW_Q"}
            and all(type(v) in (int, float) and math.isfinite(v) for v in components.values()),
            "complete finite water component accounting required")
    norms = [math.sqrt(math.fsum(float(v) ** 2 for v in row)) for row in torque]
    require(all(math.isfinite(value) for value in norms), "nonfinite water torque")
    terminal = summary.get("terminal_water", {}) if summary else {}
    retained_binding = terminal.get("same_state_retained_attempt")
    water_binding = terminal.get("same_fixed_water_state_sha256")
    if retained_binding is None or water_binding is None:
        return {"status": "unavailable_unbound_terminal_summary",
                "restricted_joint_passed": None, "raw_joint_passed": None,
                "dry_counterfactual": not wet, "water_torque_maximum": max(norms),
                "all_362_water_torque_norms": norms, "water_state_sha256": observed["state_sha256"],
                "observed_terminal_components": dict(observed["components"]),
                "retained_ligand_binding_verified": False}
    require(retained_binding == endpoint["attempt"], "conflicting terminal ligand endpoint binding")
    require(water_binding == observed["state_sha256"], "conflicting terminal summary water binding")
    force_tolerance = plan["stopping_policy"]["ligand_force_tolerance"]
    torque_tolerance = plan["stopping_policy"]["water_torque_tolerance"]
    water_pass = max(norms) <= torque_tolerance
    allowed_pass = endpoint["allowed_force_max"] <= force_tolerance
    raw_pass = endpoint["raw_force_max"] <= force_tolerance
    return {"status": "passed" if water_pass and allowed_pass else "failed",
            "dry_counterfactual": not wet,
            "criterion_scope": "wet objective ligand force and fixed-oxygen water torque" if wet else
                "dry objective ligand force plus counterfactual wet water stress; not wet-objective stationarity",
            "retained_attempt": endpoint["attempt"], "water_state_sha256": observed["state_sha256"],
            "water_torque_units": "kcal/mol/radian", "water_torque_tolerance": torque_tolerance,
            "water_torque_maximum": max(norms), "all_362_water_torque_norms": norms,
            "water_torque_passed": water_pass, "ligand_allowed_force_passed": allowed_pass,
            "ligand_raw_force_passed": raw_pass,
            "restricted_joint_passed": water_pass and allowed_pass,
            "raw_joint_passed": water_pass and raw_pass,
            "fixed_oxygen_translation_stationarity_claimed": False,
            "terminal_components": dict(observed["components"]),
            "water_reoptimized": False, "hydration_equilibrium_qualified": False}


def configure_runtime(plan):
    """Post-processing has its own measured CPU scope and the same frozen runtime."""
    affinity = plan["runtime"]["cpu_affinity"]
    require(len(affinity) == 1 and set(affinity) <= os.sched_getaffinity(0),
            "report CPU affinity unavailable")
    os.sched_setaffinity(0, set(affinity))
    import torch
    import numpy
    require(platform.python_version() == plan["runtime"]["python"]
            and torch.__version__ == plan["runtime"]["torch"]
            and numpy.__version__ == plan["runtime"]["numpy"], "report runtime differs")
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    return {"python": platform.python_version(), "torch": torch.__version__,
            "numpy": numpy.__version__, "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "cpu_threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads()}


def check_archive_origins(snapshot):
    for name, module in tuple(sys.modules.items()):
        if name.startswith("betelgeuze") and getattr(module, "__file__", None):
            require(Path(module.__file__).resolve().is_relative_to(snapshot.resolve()),
                    "archived geometry dependency origin differs: " + name)


def reference_and_structure(plan, artifacts):
    """One receptor-only fit, then reuse the same immutable reference for every arm."""
    import torch
    from . import metrics
    admission = artifacts.read(plan["reference"]["path"])
    policy = artifacts.read(plan["metrics_policy"]["path"])
    raw, graph = admission["raw_coordinates"], admission["graph_admission"]
    reference = metrics.admit_crystal_reference(raw["crystal_ca_angstrom"], raw["prepared_ca_angstrom"],
        raw["crystal_gv5_heavy_ccd_order_angstrom"], graph["prepared_heavy_indices"],
        graph["prepared_to_ccd_heavy_index_arrays"], prepared_atom_count=graph["prepared_total_atom_count"],
        source_facts={"primary_reference_admission_sha256": plan["reference"]["sha256"],
                      "metric_policy_sha256": plan["metrics_policy"]["sha256"],
                      "new_reference_metric": True, "historical_reference_reproduced": False},
        metric_policy_sha256=plan["metrics_policy"]["sha256"])
    require("structural_policy" in plan, "frozen structural policy required for full report")
    structural = artifacts.read(plan["structural_policy"]["path"])
    dry = Path(plan["source_roots"]["dry"])
    snapshot = dry / "snapshot/source"
    sys.path.insert(0, str(snapshot))
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
    from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import geometry
    relocated = artifacts.read(plan["protocol"]["path"])
    original = all_atom_system_from_canonical_json(Path(relocated["ligand"]["path"]).read_bytes())
    receptor = all_atom_system_from_canonical_json(Path(relocated["receptor"]["path"]).read_bytes())
    parameters = FourierParameters.from_dict(artifacts.read(relocated["parameters"]["path"]))
    check_archive_origins(snapshot)
    implementation = str(Path(geometry.__file__).resolve())
    require(Path(implementation).is_relative_to(snapshot.resolve()), "geometry callback origin differs")
    require(plan["source_files"].get(implementation) == protocol.hash_file(implementation), "geometry callback hash differs")
    metric_path = str(Path(metrics.__file__).resolve())
    metric_hash = plan["source_files"].get(metric_path)
    require(metric_hash == protocol.hash_file(metric_path), "metric implementation not frozen")
    receptor_heavy = receptor.coordinates[0][structural["receptor_heavy_indices"]]
    ligand_heavy = structural["ligand_heavy_indices"]
    require(ligand_heavy == graph["prepared_heavy_indices"], "structural/reference heavy order differs")
    radii = {"ligand": structural["ligand_vdw_radii_angstrom"], "receptor": structural["receptor_vdw_radii_angstrom"]}

    def diagnostics(states):
        def callback(_name, coordinates):
            trial = original.with_coordinates(coordinates.unsqueeze(0), operation="post_campaign_geometry_label_only")
            return {"source_geometry_changes_from_P0": geometry.geometry_changes(original, trial, parameters),
                    "geometry_callback_path": implementation,
                    "geometry_callback_sha256": plan["source_files"][implementation],
                    "ring_planarity": metrics.ring_planarity(coordinates,
                        structural["ligand_ring_groups_prepared_indices"],
                        source_sha256=structural["source_SDF_sha256"], policy_sha256=plan["structural_policy"]["sha256"]),
                    "closest_contacts": metrics.closest_contacts(coordinates[ligand_heavy], receptor_heavy,
                        radii, ratio_threshold=policy["pose_contact_ratio_threshold"],
                        source_sha256=plan["structural_policy"]["sha256"], policy_sha256=plan["metrics_policy"]["sha256"])}
        tensors = {name: torch.tensor(value, dtype=torch.float64) for name, value in states.items()}
        return metrics.evaluate_structural_diagnostics(tensors, callback,
            criteria_sha256=structural["historical_criteria_sha256"], implementation_sha256=metric_hash)

    return reference, diagnostics, policy


def build_report(plan_path, expected_plan_sha256, output_path, campaign_root=None):
    """Read a terminal or partial campaign; publish one new, source-bound report."""
    started, cpu = time.monotonic(), time.process_time()
    plan = protocol.verify_plan(plan_path, expected_plan_sha256)
    root = Path(campaign_root) if campaign_root is not None else Path(plan_path).parent
    require(root.is_absolute(), "absolute campaign root required")
    artifacts = Artifacts()
    report_runtime = configure_runtime(plan)
    reference, diagnostics, policy = reference_and_structure(plan, artifacts)
    p0_contract = artifacts.read(plan["phases"]["P0-dry"]["chart_path"])["P0"]
    p0 = coordinates_from_hex(p0_contract["reference_coordinates"])
    from .supervisor import reconcile_phase
    phases, arms = {}, {}
    for phase in plan["phase_order"]:
        route, work = root / "runs" / phase, root / "runs" / phase / "work"
        errors = []
        try:
            cost = phase_cost(plan, phase, route, artifacts)
        except Exception as exc:
            errors.append("unreadable phase ledger: " + type(exc).__name__ + ": " + str(exc))
            cost = {"status": "unknown_unreadable_phase", "total_work_known": False,
                    "total_started_calls": None, "known_started_calls": 0, "counts": {},
                    "pending": {}, "errors": errors.copy()}
        summary = parent = None
        for label, path in (("worker", work / "summary.json"), ("parent", route / "supervisor-exit.json")):
            try:
                document = artifacts.read(path, optional=True)
                require(document is None or isinstance(document, dict), "receipt must be an object")
                if label == "worker":
                    summary = document
                else:
                    parent = document
            except Exception as exc:
                errors.append("invalid " + label + " receipt: " + type(exc).__name__ + ": " + str(exc))
        try:
            admission = reconcile_phase(root, plan, phase)
        except Exception as exc:
            admission = {"admitted": False, "reconciliation_error": type(exc).__name__ + ": " + str(exc)}
        cost = merge_runtime_uncertainty(cost, summary, parent)
        if summary and summary.get("ledger") is not None:
            declared = summary["ledger"]
            for key in ("counts", "pending"):
                if declared.get(key) != cost.get(key):
                    errors.append("worker ledger reconciliation differs: " + key)
        if parent and parent.get("cleanup_remaining_pids"):
            errors.append("supervisor reports remaining owned processes")
        phases[phase] = {"cost": cost, "limits": plan["limits_by_phase"][phase],
                         "worker_status": summary.get("status") if summary else None,
                         "worker_wall_seconds": summary.get("worker_wall_seconds") if summary else None,
                         "worker_CPU_seconds": summary.get("worker_CPU_seconds") if summary else None,
                         "supervisor": parent, "reconciliation_errors": errors,
                         "physical_census_admitted": admission.get("physical_census_admitted"),
                         "phase_evidence_admitted": admission.get("admitted", False),
                         "admission_error": admission.get("reconciliation_error")}
        if phase not in ARMS:
            phases[phase]["calibration_passed"] = bool(summary and summary.get("status") == "diagnostic_passed"
                and summary.get("all_gradient_components_passed") is True and cost["total_work_known"]
                and admission.get("admitted") is True and not errors)
            continue
        spec = plan["phases"][phase]
        start_contract = artifacts.read(spec["chart_path"])[spec["chart_key"]]
        states = {"P0": p0, "start": coordinates_from_hex(start_contract["reference_coordinates"])}
        endpoint = labels = structure = None
        try:
            endpoint = physical_endpoint(work, artifacts)
            if endpoint is not None:
                states["final"] = coordinates_from_hex(endpoint["physical_observation"]["coordinates"])
        except Exception as exc:
            errors.append("endpoint: " + type(exc).__name__ + ": " + str(exc))
            endpoint = None
        try:
            labels = reference.evaluate_states(states)
        except Exception as exc:
            errors.append("reference label: " + type(exc).__name__ + ": " + str(exc))
        try:
            structure = diagnostics(states)
        except Exception as exc:
            errors.append("structure: " + type(exc).__name__ + ": " + str(exc))
        try:
            water = water_stationarity(plan, endpoint, summary, work, artifacts, spec["wet"])
        except Exception as exc:
            errors.append("terminal water: " + type(exc).__name__ + ": " + str(exc))
            water = {"status": "unavailable_invalid_endpoint_evidence", "restricted_joint_passed": None,
                     "raw_joint_passed": None, "dry_counterfactual": not spec["wet"]}
        execution = ("not_run" if cost["status"] == "not_run" else "unknown" if not cost["total_work_known"] else
                     "completed" if summary and summary.get("status") == "completed" and not errors
                     and admission.get("admitted") is True
                     and not cost.get("known_failed_calls") and parent and parent.get("returncode") == 0
                     and parent.get("reason") == "completed"
                     else "failed_or_incomplete")
        water["provisional_due_to_unknown_work"] = not cost["total_work_known"]
        water["eligible_for_joint_success_claim"] = (execution == "completed"
            and cost["total_work_known"] and water.get("restricted_joint_passed") is True)
        arms[phase] = {"start": spec["start"], "wet": spec["wet"], "execution_status": execution,
                      "solver_status": summary.get("solver_status") if summary else None,
                      "endpoint_available": endpoint is not None, "pose_labels": labels,
                      "physical_metrics_provisional": execution != "completed",
                      "new_reference_pose_criterion": pose_criterion(spec["start"], labels, policy["P0_no_harm_margin_angstrom"]),
                      "same_endpoint_stationarity": water, "structural_diagnostics": structure,
                      "ligand_forces": {key: endpoint[key] for key in
                        ("allowed_force_max", "raw_force_max", "reaction_force_max")} if endpoint else None,
                      "retained_attempt": endpoint["attempt"] if endpoint else None,
                      "retained_objective_energy": endpoint["energy"] if endpoint else None,
                      "energy_comparison_scope": "within the declared arm Hamiltonian only",
                      "chemical_validity": None, "errors": errors}
    aggregate = aggregate_costs(phases)
    report = {"schema": "pfk_paired_dry_wet_eight_dof_report/1.0.0", "plan_sha256": expected_plan_sha256,
              "run_id": plan["run_id"], "campaign_root": str(root), "report_runtime": report_runtime,
              "status": "all_declared_arms_completed" if all(a["execution_status"] == "completed" for a in arms.values()) else "incomplete_campaign", "declared_arms": list(ARMS),
              "all_six_declared_arms_reported": set(arms) == set(ARMS), "arms": arms, "phases": phases,
              "costs": aggregate, "aggregate_stage_caps": plan["aggregate_stage_caps"],
              "installation": {"runtime": plan["runtime"], "installation_wall_seconds": None,
                  "installation_CPU_seconds": None, "included_in_phase_timings": False},
              "reference_alignment": reference.transform.document(),
              "reference": plan["reference"], "metrics_policy": plan["metrics_policy"],
              "structural_policy": plan["structural_policy"], "source_git_commit": plan["own_source"]["git_commit"],
              "artifact_sha256": dict(sorted(artifacts.files.items())),
              "report_wall_seconds": time.monotonic() - started, "report_CPU_seconds": time.process_time() - cpu,
              "report_prepared_real_EF_calls": 0,
              "boundary": {**plan["boundary"], "chemical_validity": None,
                  "reference_used_in_objective_or_selection": False, "absolute_dry_wet_energy_winner": None,
                  "historical_reference_reproduced": False, "scientific_qualification_admitted": False,
                  "dry_water_torques_are_counterfactual_stress": True, "automatic_retry_admitted": False}}
    artifacts.verify()
    protocol.verify_plan(plan_path, expected_plan_sha256)
    protocol.write_json_absent(Path(output_path).absolute(), report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--campaign-root", type=Path)
    args = parser.parse_args(argv)
    build_report(args.plan, args.expected_plan_sha256, args.output, args.campaign_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

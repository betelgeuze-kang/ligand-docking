"""Fresh, supervised paired eight-DOF phases; never resumes or retries work.

The archived chart, solver and Torch kernels own the numerical algorithms. This
worker owns admission, durable dispatch accounting, and retained-state reporting.
"""
from __future__ import annotations

import argparse
from collections import Counter
import ctypes
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import sys
import time
import traceback


PHASES = ("diagnostic-dry", "diagnostic-wet", "P0-dry", "P0-wet",
          "Qplus-dry", "Qplus-wet", "Qminus-dry", "Qminus-wet")
OWN_ROOT = Path(__file__).resolve().parents[2]


class WorkerError(RuntimeError):
    pass


class OptimizerBudgetExhausted(RuntimeError):
    """No new objective was reserved; the last accepted state is retained."""


def require(condition, message):
    if not condition:
        raise WorkerError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    """Publish a new record durably; historical records are never replaced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical(value) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        remaining = memoryview(data)
        while remaining:
            count = os.write(fd, remaining)
            if count <= 0:
                raise OSError("zero-byte record write")
            remaining = remaining[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    require(canonical(read(path)) == canonical(value), "durable record readback differs")


def require_supervision():
    expected = os.environ.get("PFK_PAIRED_SUPERVISOR_PID")
    require(expected == str(os.getppid()), "owned paired supervisor required")
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.prctl(1, signal.SIGKILL, 0, 0, 0) == 0, "parent-death guard failed")
    require(expected == str(os.getppid()), "supervisor exited during admission")
    require(sys.flags.isolated == 1, "isolated Python (-I) required")
    require(sys.dont_write_bytecode, "bytecode writes must be disabled (-B)")


def set_limits(limits):
    for kind, key in ((resource.RLIMIT_CPU, "cpu_seconds"),
                      (resource.RLIMIT_AS, "address_space_bytes"),
                      (resource.RLIMIT_FSIZE, "file_bytes")):
        value = limits[key]
        require(type(value) is int and value > 0, "invalid process limit")
        resource.setrlimit(kind, (value, value))


def check_origins(plan):
    source = Path(plan["source_roots"]["dry"]) / "snapshot/source"
    own = OWN_ROOT / "tools/pfk_paired_water_eight_dof"
    archive = {"model_adapter": Path(plan["source_roots"]["dry"]),
               "model_common": Path(plan["source_roots"]["dry"]),
               "common": Path(plan["source_roots"]["dry"]),
               "kinematics": Path(plan["source_roots"]["dry"]),
               "generalized_solver": Path(plan["source_roots"]["dry"]),
               "coulomb_taper_profile": Path(plan["source_roots"]["dry"]),
               "internal_coulomb_untruncated_profile": Path(plan["source_roots"]["dry"]),
               "rigid_water_adapter": Path(plan["source_roots"]["water"]) / "adapter",
               "pair_kernel": Path(plan["source_roots"]["water"]) / "adapter",
               "global_candidate": Path(plan["source_roots"]["water"]) / "adapter",
               "batched_fixed_pairs": Path(plan["source_roots"]["water"]) / "adapter",
               "coulomb_force_taper_kernel": Path(plan["source_roots"]["water"]) / "adapter"}
    origins = {}
    for name, module in tuple(sys.modules.items()):
        require(name != "pytest" and not name.startswith(("pytest.", "tests.")),
                "test modules are forbidden in the worker")
        path = getattr(module, "__file__", None)
        if path is None:
            continue
        path = Path(path).resolve()
        expected = source if name.startswith("betelgeuze") else archive.get(name.split(".")[0])
        if name.startswith("tools.pfk_paired_water_eight_dof"):
            expected = own
        if expected is not None:
            require(path.is_relative_to(expected.resolve()), "module origin differs: " + name)
            origins[name] = str(path)
    return origins


class LedgerCompatibility:
    """Adapt archived label metadata without passing it to numerical callables."""
    def __init__(self, journal):
        self.journal = journal
        self.started = journal.started

    def event(self, kind, event, success=None, *, label=None):
        self.journal.event(kind, event, success)

    def invoke(self, kind, function, *args, label=None, **kwargs):
        return self.journal.invoke(kind, function, *args, **kwargs)


class GeometryCounter:
    """Count method entries, including nested chart calls; not internal JVP ops."""
    def __init__(self, chart, caps):
        self.counts = Counter()
        for method in ("admit", "pullback", "coordinates"):
            kind = "geometry_" + method
            original = getattr(chart, method)

            def wrapped(*args, _kind=kind, _original=original, **kwargs):
                self.counts[_kind] += 1
                require(self.counts[_kind] <= caps[_kind], "geometry method-entry cap exceeded")
                return _original(*args, **kwargs)

            setattr(chart, method, wrapped)


class Tracker:
    """New accounting only; no historical parity or optimizer admission bypass."""
    def __init__(self, profile, journal, output):
        self.profile, self.ledger, self.output = profile, LedgerCompatibility(journal), output
        self.active = self.label = None
        self.before = {}
        self.stages = None

    def __getattr__(self, name):
        return getattr(self.profile, name)

    def work_observer(self, kind, event, success):
        if event == "started":
            require(self.active is None, "nested dry profile dispatch")
            self.ledger.event(kind, event)
            self.active, self.before = kind, self.ledger.started.copy()
            return
        require(self.active == kind, "unpaired dry profile dispatch")
        if success:
            backward = {"source_base_full_EF": "backward_base",
                        "cross_correction_EF": "backward_cross",
                        "internal_correction_EF": "backward_internal"}[kind]
            count = self.ledger.started[backward] - self.before[backward]
            require(2 <= count <= 55 if kind == "source_base_full_EF" else count == 1,
                    "unexpected dry backward count")
            if kind == "source_base_full_EF":
                require(self.ledger.started["source_admission_graph"]
                        - self.before["source_admission_graph"] == 1,
                        "source graph admission count differs")
        self.ledger.event(kind, event, success)
        self.active = None

    def evaluate(self, state, neighbors):
        from model_adapter import observe
        self.label = str(self.ledger.started["source_base_full_EF"] + 1)
        new, cross, source = self.profile.evaluate_with_stages(state, neighbors, self.work_observer)
        self.stages = {"objective_attempt": int(self.label),
                       "model_identity": self.profile.identity(),
                       "model_fingerprint_sha256": self.profile.fingerprint_sha256,
                       "new": observe(state, new), "cross_only": observe(state, cross),
                       "source_base": observe(state, source),
                       "calibration_scope": "new_counted_same_state_triple_no_historical_parity_claim",
                       "extra_stage_EF": 0}
        for stage in ("new", "cross_only", "source_base"):
            self.stages[stage]["attempt"] = int(self.label)
        write_new(self.output / "stages" / (self.label.zfill(5) + ".json"), self.stages)
        for key in ("ligand_internal", "cross_lennard_jones"):
            require(self.stages["cross_only"]["components"][key]
                    == self.stages["source_base"]["components"][key], "unchanged base term differs")
        for key in ("cross_lennard_jones", "cross_screened_coulomb"):
            require(self.stages["new"]["components"][key]
                    == self.stages["cross_only"]["components"][key], "unchanged cross term differs")
        return new


class Context:
    def __init__(self, plan, phase, output, journal, started_wall, started_cpu):
        import torch
        import numpy
        import model_adapter
        import rigid_water_adapter as rw
        import pair_kernel
        from betelgeuze_product import cpu_prepared_cartesian_long_budget as long
        from kinematics import Chart, bridge_rotor
        from tools.pfk_paired_water_eight_dof.backend import MobileLigandWaterTerms

        self.plan, self.phase, self.output, self.journal = plan, phase, output, journal
        self.wall0, self.cpu0 = started_wall, started_cpu
        self.limits = plan["limits_by_phase"][phase]
        self.selection = plan["phases"][phase]
        self.terminal_wall = self.terminal_cpu = None
        self.last_checkpoint, self.checkpoint_serial = None, 0
        self.observations = {}
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        require(platform.python_version() == plan["runtime"]["python"], "Python runtime differs")
        require(torch.__version__ == plan["runtime"]["torch"], "Torch runtime differs")
        require(numpy.__version__ == plan["runtime"]["numpy"], "NumPy runtime differs")
        _, loaded = long.shared._read(Path(plan["protocol"]["path"]),
                                      plan["protocol"]["sha256"], "fourier", 600, 0,
                                      _profile=long._PROFILE)
        self.system, self.parameters, self.config, self.fixed, base, identity = loaded
        dry = Path(plan["source_roots"]["dry"])
        profile, binding = model_adapter.bind(dry, self.system, base, identity)
        self.tracker = Tracker(profile, journal, output)
        contract = read(self.selection["chart_path"])[self.selection["chart_key"]]
        xyz = torch.tensor([[float.fromhex(v) for v in row]
                            for row in contract["reference_coordinates"]], dtype=torch.float64)
        bonds = [(b.atom_i, b.atom_j) for b in self.system.bonds]
        rotors = [bridge_rotor(self.system.atom_count, bonds, r["parent"], r["child"])
                  for r in contract["rotors"]]
        self.chart = Chart(xyz, bonds, rotors)
        require(self.chart.dof == 8 and [{"parent": r.parent, "child": r.child,
                                        "mobile": list(r.mobile)} for r in rotors]
                == contract["rotors"], "eight-DOF rotor contract differs")
        self.geometry = GeometryCounter(self.chart, plan["geometry_caps_by_phase"][phase])
        checkpoint = read(plan["water_checkpoint"]["path"])
        self.water_state = rw.WaterState(tuple(rw.RigidWater(**w)
                                              for w in checkpoint["state"]["waters"]))
        require(len(self.water_state.waters) == 362 and self.water_state.sha256
                == plan["water_checkpoint"]["state_sha256"], "fixed water state differs")
        water_xyz = torch.tensor([w.coordinates for w in self.water_state.waters],
                                 dtype=torch.float64).reshape(-1, 3)
        self.wl = MobileLigandWaterTerms(pair_kernel._evaluate_validated_cross_terms,
                                        self.parameters.atom_parameters, water_xyz,
                                        rw.TIP3P_PARAMETERS * 362, rw.PairSettings(),
                                        observer=journal.event) if self.selection["wet"] else None
        write_new(output / "admission.json", {"binding": binding,
                  "runtime": plan["runtime"], "module_origins": check_origins(plan),
                  "fixed_water_state_sha256": self.water_state.sha256,
                  "no_historical_parity_claim": True,
                  "no_reference_coordinates_in_objective": True})

    def stop_check(self):
        limits = self.limits
        if (time.monotonic() - self.wall0 >= limits["wall_seconds"]
                or time.process_time() - self.cpu0 >= limits["cpu_seconds"]):
            raise WorkerError("total phase deadline reached; no new dispatch")
        if self.terminal_wall is not None:
            if (time.monotonic() - self.terminal_wall >= limits["terminal_budget_seconds"]
                    or time.process_time() - self.terminal_cpu >= limits["terminal_budget_seconds"]):
                raise WorkerError("terminal diagnostic deadline reached")
        require(not (self.output / "STOP_REQUESTED").exists(), "stop requested")
        require(os.environ.get("PFK_PAIRED_SUPERVISOR_PID") == str(os.getppid()),
                "supervisor changed")

    def evaluate(self, q, attempt):
        import torch
        from model_adapter import instrument
        from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
        from betelgeuze_product.cpu_refinement_v1_2.provenance import coordinates_hex
        self.stop_check()
        if self.selection["kind"] == "optimizer" and (
                time.monotonic() - self.wall0 >= self.limits["optimizer_budget_seconds"]
                or time.process_time() - self.cpu0 >= self.limits["optimizer_budget_seconds"]):
            raise OptimizerBudgetExhausted("optimizer window exhausted before new objective")
        self.chart.admit(q)
        self.fixed.assert_intact()
        xyz = self.chart.coordinates(q)
        intent = {"attempt": attempt, "coordinates": coordinates_hex(xyz.unsqueeze(0))}
        write_new(self.output / "intents" / (str(attempt).zfill(5) + ".json"),
                  {**intent, "q": q.tolist(), "q_hex": [float(v).hex() for v in q]})

        def objective():
            # This instrumentation has ended before WL instruments autograd.
            with instrument(self.tracker):
                receipt = execution._invoke(self.system, self.tracker, self.config, intent)
            write_new(self.output / "receipts" / (str(attempt).zfill(5) + ".json"), receipt)
            base = receipt["observation"]
            require(base is not None and receipt["failure"] is None,
                    "full dry EF failed; retry forbidden: " + str(receipt["error_type"]))
            require(base["coordinates"] == intent["coordinates"], "physical coordinates differ")
            forces = torch.tensor([[float.fromhex(v) for v in row] for row in base["forces"]],
                                  dtype=torch.float64)
            energy = float.fromhex(base["energy"])
            components = {k: float.fromhex(v) for k, v in base["components"].items() if k != "total"}
            water_work = None
            if self.wl is not None:
                wet = self.wl.evaluate(xyz)
                forces = forces + wet.forces
                energy = energy + wet.energy
                components.update(wet.components)
                water_work = dict(wet.work)
            require(math.isfinite(energy) and bool(torch.isfinite(forces).all()), "nonfinite paired EF")
            require(abs(math.fsum(components.values()) - energy) <= 1e-10 * max(1., abs(energy)),
                    "paired component accounting differs")
            projected = self.chart.pullback(q, forces)
            def norm(value):
                return float(torch.linalg.vector_norm(value, dim=1).max())
            physical = {"attempt": attempt, "coordinates": intent["coordinates"],
                        "energy": energy.hex(), "forces": coordinates_hex(forces.unsqueeze(0)),
                        "components": {k: float(v).hex() for k, v in {**components, "total": energy}.items()},
                        "maximum_raw_atom_force": norm(forces).hex()}
            observation = {"attempt": attempt, "q": q.tolist(), "q_hex": [float(v).hex() for v in q],
                           "energy": energy, "raw_force_max": norm(forces),
                           "allowed_force_max": norm(projected["allowed_cartesian_force"]),
                           "reaction_force_max": norm(projected["reaction_force"]),
                           "generalized_gradient": (-projected["generalized_force"]).tolist(),
                           "generalized_gradient_hex": [float(v).hex() for v in -projected["generalized_force"]],
                           "generalized_gradient_units": ["kcal/mol/Angstrom"] * 3 + ["kcal/mol/radian"] * 5,
                           "allowed_cartesian_forces_hex": coordinates_hex(projected["allowed_cartesian_force"].unsqueeze(0)),
                           "reaction_forces_hex": coordinates_hex(projected["reaction_force"].unsqueeze(0)),
                           "gram_eigenvalues": projected["gram_eigenvalues"].tolist(),
                           "constraint_residual": self.chart.residual(q),
                           "physical_observation": physical, "dry_observation": base,
                           "WL_work": water_work,
                           "objective_definition": "D(q)+WL(q)" if self.wl else "D(q)",
                           "fixed_water_WP_WW_constant_in_objective": False}
            write_new(self.output / "observations" / (str(attempt).zfill(5) + ".json"), observation)
            self.observations[attempt] = observation
            return observation

        # Recheck after geometry and intent publication, before reserving work.
        self.stop_check()
        if self.selection["kind"] == "optimizer" and (
                time.monotonic() - self.wall0 >= self.limits["optimizer_budget_seconds"]
                or time.process_time() - self.cpu0 >= self.limits["optimizer_budget_seconds"]):
            raise OptimizerBudgetExhausted("optimizer window exhausted before physical reservation")
        return self.journal.invoke("objective", objective)

    def checkpoint(self, state):
        self.checkpoint_serial += 1
        write_new(self.output / "checkpoints" / (str(self.checkpoint_serial).zfill(5) + ".json"), state)
        self.last_checkpoint = state

    def diagnostic(self):
        import torch
        policy = self.plan["stopping_policy"]
        h = policy["fd_step"]
        q = torch.zeros(8, dtype=torch.float64)
        observations = [self.evaluate(q, 1)]
        for index in range(8):
            for sign in (1, -1):
                trial = q.clone()
                trial[index] = sign * h
                observations.append(self.evaluate(trial, len(observations) + 1))
        rows = []
        for index in range(8):
            plus, minus = observations[1 + 2 * index:3 + 2 * index]
            numerical = (plus["energy"] - minus["energy"]) / (2 * h)
            analytic = observations[0]["generalized_gradient"][index]
            error = abs(numerical - analytic)
            tolerance = policy["fd_atol"] + policy["fd_rtol"] * abs(analytic)
            rows.append({"index": index, "numerical": numerical, "analytic": analytic,
                         "absolute_error": error, "tolerance": tolerance,
                         "passed": error <= tolerance, "step": h})
        write_new(self.output / "gradient-components.json", rows)
        passed = all(row["passed"] for row in rows)
        return {"status": "diagnostic_passed" if passed else "diagnostic_failed",
                "all_gradient_components_passed": passed, "new_objectives": 17, "result": rows,
                "separate_dry_wet_calibration": True, "historical_parity_claimed": False}

    def terminal_water(self, retained):
        import torch
        import rigid_water_adapter as rw
        from global_candidate import SyntheticGlobalEvaluator
        self.terminal_wall, self.terminal_cpu = time.monotonic(), time.process_time()
        self.stop_check()
        def rows(parameters):
            return tuple(rw.SiteParameter(p.sigma_angstrom, p.epsilon_kcal_per_mol, p.charge_e)
                         for p in parameters)
        protein = rw.FixedSites(tuple(map(tuple, self.fixed.receptor.coordinates[0].tolist())),
                                rows(self.fixed.cross.receptor_atoms))
        ligand_xyz = tuple(tuple(float.fromhex(v) for v in row)
                           for row in retained["physical_observation"]["coordinates"])
        ligand = rw.FixedSites(ligand_xyz, rows(self.parameters.atom_parameters))
        raw_journal = rw.EvaluationJournal(self.output / "terminal-water-original-events.jsonl")
        original_append = raw_journal.append

        def append(event):
            kind = event["kind"]
            if kind == "WW_screen_reserved":
                self.journal.event("terminal_water_screen", "started")
            original_append(event)
            if kind in ("WW_screen_completed", "WW_screen_failed", "WW_screen_interrupted_unknown"):
                self.journal.event("terminal_water_screen", "finished", kind == "WW_screen_completed")

        raw_journal.append = append
        evaluator = SyntheticGlobalEvaluator(tile_size=32, protein=protein, fixed_ligand=ligand,
                    journal=raw_journal, enable_rigid_water_adapter=True,
                    enable_coulomb_force_taper=True)
        original_dispatch = evaluator._dispatch
        evaluator._dispatch = lambda *a, **kw: self.journal.invoke(
            "terminal_water_kernel", original_dispatch, *a, **kw)
        original_grad = torch.autograd.grad

        def dispatch():
            torch.autograd.grad = lambda *a, **kw: self.journal.invoke(
                "terminal_water_backward", original_grad, *a, **kw)
            try:
                result = evaluator.evaluate_global(self.water_state)
                document = result.to_dict()
                write_new(self.output / "terminal-water-observation.json", document)
                # Retain the same observation additionally in binary64 hex form.
                write_new(self.output / "terminal-water-observation-hex.json", hex_floats(document))
                criterion = rw.global_torque_criterion(result, self.water_state,
                            self.plan["stopping_policy"]["water_torque_tolerance"])
                require(result.accounting_dict["actual_batch_dispatches"]
                        == self.journal.started["terminal_water_kernel"], "terminal kernel counts differ")
                require(result.accounting_dict["actual_backwards"]
                        == self.journal.started["terminal_water_backward"], "terminal backward counts differ")
                return criterion, result.component_dict
            finally:
                torch.autograd.grad = original_grad

        criterion, components = self.journal.invoke("terminal_water_global", dispatch)
        stationary = criterion["rotational_stationary"]
        force = self.plan["stopping_policy"]["ligand_force_tolerance"]
        constant = math.fsum(components[k] for k in ("WP_LJ", "WP_Q", "WW_LJ", "WW_Q"))
        return {"water_criterion": criterion, "water_components": components,
                "fixed_WP_WW_constant": constant,
                "dry_counterfactual_water_context": not self.selection["wet"],
                "joint_criterion_scope": ("wet D(q)+WL(q) ligand force and fixed-oxygen water torque"
                    if self.selection["wet"] else
                    "dry D(q) ligand force plus counterfactual wet torque; not wet-objective stationarity"),
                "fixed_oxygen_translation_stationarity_claimed": False,
                "same_state_retained_attempt": retained["attempt"],
                "same_fixed_water_state_sha256": self.water_state.sha256,
                "restricted_joint_stationary": stationary and retained["allowed_force_max"] <= force,
                "raw_joint_stationary": stationary and retained["raw_force_max"] <= force,
                "water_reoptimized": False, "hydration_equilibrium_claimed": False}

    def optimizer(self):
        from generalized_solver import solve
        policy = self.plan["stopping_policy"]
        try:
            result = solve(self.chart, self.evaluate, self.checkpoint,
                           max_calls=self.selection["objective_cap"],
                           max_accepted=self.selection["accepted_cap"],
                           force_tolerance=policy["ligand_force_tolerance"])
        except OptimizerBudgetExhausted:
            require(not self.journal.pending and not self.journal.poisoned,
                    "deadline inside unresolved dispatch; terminal forbidden")
            require(self.last_checkpoint and self.last_checkpoint["current"],
                    "optimizer window ended before a retained observation")
            result = {**self.last_checkpoint, "status": "optimizer_wall_budget_exhausted",
                      "original_solver_completed": False}
        retained = result["current"]
        require(self.observations.get(retained["attempt"]) == retained,
                "retained endpoint absent from counted observation cache")
        write_new(self.output / "optimizer-result.json", result)
        write_new(self.output / "retained-observation.json", retained)
        write_new(self.output / "endpoint-observation.json", retained)
        terminal = self.terminal_water(retained)
        force_pass = retained["allowed_force_max"] <= policy["ligand_force_tolerance"]
        return {"status": "completed", "solver_status": result["status"], "result": result,
                "original_solver_completed": result.get("original_solver_completed", True),
                "restricted_force_converged": force_pass,
                "raw_force_converged": retained["raw_force_max"] <= policy["ligand_force_tolerance"],
                "attempts": self.journal.started["objective"], "accepted_steps": result["accepted"],
                "retained_attempt": retained["attempt"], "retained_energy": retained["energy"],
                "allowed_force_max": retained["allowed_force_max"],
                "raw_force_max": retained["raw_force_max"],
                "terminal_water": terminal, "extra_final_or_replay_ligand_EF": 0,
                "no_reference_pose_objective": True,
                "near_native_source_not_blind_docking": True}


def hex_floats(value):
    if isinstance(value, float):
        require(math.isfinite(value), "nonfinite terminal record")
        return value.hex()
    if isinstance(value, dict):
        return {key: hex_floats(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [hex_floats(item) for item in value]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    require_supervision()
    # Explicit own-tool bootstrap is required by isolated script execution.
    sys.path.insert(0, str(OWN_ROOT))
    from tools.pfk_paired_water_eight_dof.protocol import verify_plan
    from tools.pfk_paired_water_eight_dof.journal import StageJournal, inspect
    plan = verify_plan(args.plan, args.expected_plan_sha256)
    require(str(Path(sys.executable).absolute()) == str(Path(plan["runtime"]["python_executable"]).absolute()),
            "interpreter path differs")
    limits = plan["limits_by_phase"][args.phase]
    set_limits(limits)
    affinity = plan["runtime"]["cpu_affinity"]
    require(isinstance(affinity, list) and len(affinity) == 1
            and type(affinity[0]) is int and affinity[0] in os.sched_getaffinity(0),
            "one admitted available CPU required")
    os.sched_setaffinity(0, set(affinity))
    args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    output = args.output_dir.resolve()
    wall0, cpu0 = time.monotonic(), time.process_time()
    summary = {"status": "failed", "scientific_qualification_claimed": False}
    journal = context = None
    try:
        source = Path(plan["source_roots"]["dry"])
        for path in (source / "snapshot/source", source,
                     Path(plan["source_roots"]["water"]) / "adapter"):
            sys.path.insert(0, str(path))
        journal = StageJournal(output / "dispatch-events.jsonl", plan["stage_caps_by_phase"][args.phase])
        context = Context(plan, args.phase, output, journal, wall0, cpu0)
        journal.stop_check = context.stop_check
        summary = context.diagnostic() if plan["phases"][args.phase]["kind"] == "diagnostic" else context.optimizer()
        verify_plan(args.plan, args.expected_plan_sha256)
        summary.update(frozen_sources_and_inputs_unchanged=True, module_origins=check_origins(plan))
    except BaseException as exc:
        if journal is not None:
            journal.poisoned = True
        summary = {"status": "failed", "error": type(exc).__name__, "message": str(exc),
                   "no_further_numerical_dispatch": True}
        write_new(output / "failure.json", {**summary, "traceback": traceback.format_exc()})
    finally:
        if journal is not None:
            journal.close()
            summary["ledger"] = inspect(output / "dispatch-events.jsonl", plan["stage_caps_by_phase"][args.phase])
            summary["journal_runtime"] = {"poisoned": journal.poisoned,
                                          "pending": dict(journal.pending),
                                          "publication_uncertain": journal.publication_uncertain}
            # A complete visible finish row does not prove its fsync succeeded.
            # Preserve the process observation alongside independent byte parsing.
            if journal.publication_uncertain or journal.pending:
                summary["ledger"]["total_work_known"] = False
                summary["ledger"]["total_started_calls"] = None
                summary["ledger"]["runtime_publication_uncertain"] = journal.publication_uncertain
                summary["ledger"]["runtime_pending"] = dict(journal.pending)
        if context is not None:
            summary["geometry_method_entries"] = dict(context.geometry.counts)
            summary["geometry_counter_scope"] = "method entries including nested calls; not all JVP operations"
            summary["WL_work"] = context.wl.work_snapshot() if context.wl is not None else None
        summary.update(phase=args.phase, plan_sha256=args.expected_plan_sha256,
                       limits=limits, worker_wall_seconds=time.monotonic() - wall0,
                       worker_CPU_seconds=time.process_time() - cpu0,
                       peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       automatic_retry_admitted=False, scientific_qualification_claimed=False,
                       historical_2400_optimizer_only_timing_comparable=False,
                       optimizer_deadline_scope="before each objective dispatch; in-flight work bounded by total2400")
        write_new(output / "summary.json", summary)
    return 0 if summary["status"] in ("completed", "diagnostic_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

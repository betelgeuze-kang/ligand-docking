"""Synthetic evidence bookkeeping only: no prepared source, fit, metric or EF."""
import json

import pytest

from tools.pfk_paired_water_eight_dof import journal, protocol, report


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class SyntheticReference:
    class Transform:
        def document(self):
            return {"synthetic": True, "ligand_used_in_fit": False}

    transform = Transform()

    def evaluate_states(self, states):
        # Deliberately fixed labels; this fixture never fits or measures a pose.
        return {"states": {name: {"all_graph_mapping_rmsd_angstrom": [1., 2., 3., 4.],
                                  "symmetry_aware_heavy_rmsd_angstrom": 1.}
                           for name in states},
                "comparison": None if "final" not in states else {
                    "final_minus_P0_reference_rmsd_angstrom": 0.,
                    "final_minus_start_reference_rmsd_angstrom": 0.}}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    chart = tmp_path / "chart.json"
    packed = [[float(v).hex() for v in (0., 0., 0.)]]
    put(chart, {name: {"reference_coordinates": packed} for name in ("P0", "Qplus", "Qminus")})
    plan = {"phase_order": list(protocol.PHASE_ORDER), "phases": {},
            "stage_caps_by_phase": {}, "limits_by_phase": {}, "runtime": {},
            "reference": {}, "metrics_policy": {}, "structural_policy": {},
            "own_source": {"git_commit": "synthetic"}, "run_id": "synthetic",
            "aggregate_stage_caps": protocol.aggregate_caps(), "boundary": {},
            "water_checkpoint": {"state_sha256": "a" * 64},
            "stopping_policy": protocol.STOPPING}
    for phase in protocol.PHASE_ORDER:
        start = "P0" if phase.startswith("diagnostic") else phase.rsplit("-", 1)[0]
        plan["phases"][phase] = {"chart_path": str(chart), "chart_key": start,
                                 "wet": phase.endswith("-wet"), "start": start}
        plan["stage_caps_by_phase"][phase] = protocol.stage_caps(phase)
        plan["limits_by_phase"][phase] = protocol.phase_limits(phase)
    verification_calls = []

    def verify(*args):
        verification_calls.append(args)
        return plan

    monkeypatch.setattr(report.protocol, "verify_plan", verify)
    monkeypatch.setattr(report, "configure_runtime", lambda _: {"synthetic_no_torch_work": True})
    monkeypatch.setattr(report, "reference_and_structure", lambda *_: (
        SyntheticReference(), lambda states: {"states": list(states), "synthetic_no_metrics": True},
        protocol.METRICS_POLICY))
    return tmp_path, plan, verification_calls


def build(campaign, name="report.json"):
    root, _, _ = campaign
    return report.build_report(root / "plan.json", "a" * 64, root / name)


def retained(campaign):
    root, plan, _ = campaign
    work = root / "runs/P0-dry/work"
    work.mkdir(parents=True)
    ledger = journal.StageJournal(work / "dispatch-events.jsonl", plan["stage_caps_by_phase"]["P0-dry"])
    ledger.invoke("objective", lambda: "synthetic metadata callable; no molecular work")
    ledger.close()
    counts = journal.inspect(work / "dispatch-events.jsonl", plan["stage_caps_by_phase"]["P0-dry"])
    packed = [[float(v).hex() for v in (0., 0., 0.)]]
    endpoint = {"attempt": 1, "raw_force_max": 0., "allowed_force_max": 0.,
                "reaction_force_max": 0., "energy": 0.,
                "physical_observation": {"coordinates": packed, "forces": packed, "energy": 0.0.hex()},
                "allowed_cartesian_forces_hex": packed, "reaction_forces_hex": packed}
    put(work / "endpoint-observation.json", endpoint)
    put(work / "observations/00001.json", endpoint)
    water = {"mode": "global", "state_sha256": "a" * 64,
             "water_indices": list(range(362)), "torques_kcal_per_mol_radian": [[0., 0., 0.]] * 362,
             "components": [[key, 0.] for key in ("WP_LJ", "WP_Q", "WL_LJ", "WL_Q", "WW_LJ", "WW_Q")]}
    put(work / "terminal-water-observation.json", water)
    return work, counts, water


def test_all_six_missing_arms_are_not_run_with_no_fabricated_endpoint(campaign):
    result = build(campaign)
    assert result["status"] == "incomplete_campaign"
    assert set(result["arms"]) == set(report.ARMS)
    assert len(campaign[2]) == 2  # Both source verification boundaries were reached.
    for arm in result["arms"].values():
        assert arm["execution_status"] == "not_run"
        assert arm["endpoint_available"] is False
        assert set(arm["pose_labels"]["states"]) == {"P0", "start"}
        assert arm["pose_labels"]["comparison"] is None
        assert arm["new_reference_pose_criterion"]["passed"] is None
        assert arm["chemical_validity"] is None
    assert result["costs"]["total_started_stage_calls"] == 0
    assert len(result["costs"]["not_run_phases"]) == 8


def test_readable_paired_finish_cannot_erase_runtime_publication_uncertainty(campaign):
    work, counts, _ = retained(campaign)
    put(work / "summary.json", {"status": "failed",
        "ledger": {**counts, "total_work_known": False, "total_started_calls": None},
        "journal_runtime": {"publication_uncertain": True, "pending": {}}})
    result = build(campaign)
    arm = result["arms"]["P0-dry"]
    cost = result["phases"]["P0-dry"]["cost"]
    assert cost["durable_reparse_total_work_known"] is True
    assert cost["total_work_known"] is False
    assert result["costs"]["total_started_stage_calls"] is None
    assert result["costs"]["known_started_stage_calls"] == 1
    assert arm["execution_status"] == "unknown"
    assert arm["physical_metrics_provisional"] is True
    assert arm["same_endpoint_stationarity"]["eligible_for_joint_success_claim"] is False
    assert cost["elapsed_by_kind"]["kinds"]["objective"]["finished_intervals"] == 1
    assert cost["elapsed_by_kind"]["geometry_seconds"] is None


def test_process_death_pending_intent_has_unknown_cost_not_zero(campaign):
    root, plan, _ = campaign
    work = root / "runs/Qplus-wet/work"
    work.mkdir(parents=True)
    ledger = journal.StageJournal(work / "dispatch-events.jsonl", plan["stage_caps_by_phase"]["Qplus-wet"])
    ledger.event("objective", "started")
    ledger.close()  # Represents a terminal process without a numerical outcome.
    result = build(campaign)
    assert result["arms"]["Qplus-wet"]["execution_status"] == "unknown"
    assert result["costs"]["known_started_stage_calls"] == 1
    assert result["costs"]["total_started_stage_calls"] is None
    assert result["costs"]["automatic_retry_admitted"] is False


def test_terminal_file_without_summary_binding_retains_observation_not_joint_pass(campaign):
    retained(campaign)
    result = build(campaign)
    water = result["arms"]["P0-dry"]["same_endpoint_stationarity"]
    assert len(result["arms"]) == 6
    assert water["status"] == "unavailable_unbound_terminal_summary"
    assert len(water["all_362_water_torque_norms"]) == 362
    assert water["restricted_joint_passed"] is None
    assert water["retained_ligand_binding_verified"] is False


def test_conflicting_terminal_binding_is_local_failure_and_keeps_other_arms(campaign):
    work, counts, _ = retained(campaign)
    put(work / "summary.json", {"status": "failed", "ledger": counts,
        "terminal_water": {"same_state_retained_attempt": 2, "same_fixed_water_state_sha256": "a" * 64}})
    result = build(campaign)
    assert len(result["arms"]) == 6
    arm = result["arms"]["P0-dry"]
    assert arm["same_endpoint_stationarity"]["status"] == "unavailable_invalid_endpoint_evidence"
    assert any("conflicting terminal" in error for error in arm["errors"])
    assert arm["pose_labels"] is not None
    assert result["arms"]["Qminus-wet"]["execution_status"] == "not_run"


def test_counterfactual_water_torque_failure_stays_failure(campaign):
    work, counts, water = retained(campaign)
    water["torques_kcal_per_mol_radian"][0] = [.002, 0., 0.]
    put(work / "terminal-water-observation.json", water)
    put(work / "summary.json", {"status": "failed", "ledger": counts,
        "terminal_water": {"same_state_retained_attempt": 1, "same_fixed_water_state_sha256": "a" * 64}})
    observed = build(campaign)["arms"]["P0-dry"]["same_endpoint_stationarity"]
    assert observed["status"] == "failed"
    assert observed["dry_counterfactual"] is True
    assert observed["water_torque_passed"] is False
    assert observed["restricted_joint_passed"] is False
    assert observed["raw_joint_passed"] is False
    assert observed["eligible_for_joint_success_claim"] is False


def test_bad_phase_summary_does_not_remove_declared_denominator(campaign):
    root, _, _ = campaign
    put(root / "runs/Qminus-dry/work/summary.json", ["invalid receipt type"])
    result = build(campaign)
    assert len(result["arms"]) == 6
    arm = result["arms"]["Qminus-dry"]
    assert arm["execution_status"] == "unknown"
    assert any("receipt must be an object" in error for error in arm["errors"])
    assert result["costs"]["total_started_stage_calls"] is None


def test_new_pose_flags_use_own_start_and_fixed_no_harm_margin():
    labels = {"states": {"final": {}}, "comparison": {
        "final_minus_P0_reference_rmsd_angstrom": 1e-6,
        "final_minus_start_reference_rmsd_angstrom": 0.}}
    assert report.pose_criterion("P0", labels, 1e-6)["passed"] is True
    assert report.pose_criterion("Qplus", labels, 1e-6)["passed"] is False
    labels["comparison"]["final_minus_P0_reference_rmsd_angstrom"] = 2e-6
    labels["comparison"]["final_minus_start_reference_rmsd_angstrom"] = -.01
    assert report.pose_criterion("P0", labels, 1e-6)["passed"] is False
    assert report.pose_criterion("Qplus", labels, 1e-6)["passed"] is True


def test_report_output_is_absent_only_and_retains_first_bytes(campaign):
    build(campaign)
    path = campaign[0] / "report.json"
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        build(campaign)
    assert path.read_bytes() == before

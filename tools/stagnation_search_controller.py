"""Bounded observation-to-action controller; no molecular transforms or evaluator."""
import math

POLICIES = ("continuation", "uniform_restart", "stagnation_escape")


class ContractError(ValueError):
    """Rejected caller contract; not an engine/scientific failure."""


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError("integer outside contract")
    return value


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ContractError("finite scalar required")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ContractError("finite scalar required") from None
    if not math.isfinite(value):
        raise ContractError("finite scalar required")
    return value


class Controller:
    """One in-flight action, one evaluation allowance per action.

    The adapter must enforce the allowance before calling its evaluator. This
    object accounts receipts; it cannot sandbox an arbitrary external engine.
    Energy is a lower-is-better scalar; no reference pose/goal is accepted.
    """

    def __init__(self, policy, budget, *, patience=8, improvement_epsilon=1e-5,
                 restart_interval=20, maximum_actions=None):
        if policy not in POLICIES:
            raise ContractError("unsupported policy")
        self.policy = policy
        self.budget = _integer(budget, 1, 100000)
        self.patience = _integer(patience, 1, 100000)
        self.restart_interval = _integer(restart_interval, 1, 100000)
        self.epsilon = _finite(improvement_epsilon)
        if self.epsilon < 0:
            raise ContractError("negative improvement threshold")
        self.maximum_actions = _integer(2 * budget if maximum_actions is None else maximum_actions,
                                        1, 200000)
        self.charged = self.known_evaluations = self.unknown_evaluation_allowance = 0
        self.issued = self.observed = self.stale = self.cycle_steps = 0
        self.current_energy = self.best_observed_energy = self.cycle_best = None
        self.pending = None
        self.action_counts = {kind: 0 for kind in ("initialize", "refine", "restart", "escape")}
        self.outcome_counts = {kind: 0 for kind in ("ok", "failed", "unavailable", "interrupted")}
        self.accepted = self.rejected = 0

    def issue(self):
        if self.pending is not None:
            raise ContractError("an action is already in flight")
        if self.charged >= self.budget or self.issued >= self.maximum_actions:
            return None
        if self.current_energy is None:
            kind = "initialize"
        elif self.policy == "uniform_restart" and self.cycle_steps >= self.restart_interval:
            kind = "restart"
        elif self.policy == "stagnation_escape" and self.stale >= self.patience:
            kind = "escape"
        else:
            kind = "refine"
        self.issued += 1
        self.pending = (self.issued, kind)
        self.action_counts[kind] += 1
        return {"action_id": self.issued, "kind": kind, "evaluation_allowance": 1}

    def observe(self, action_id, *, status, evaluations, energy=None, accepted=False):
        """Commit exactly one matching receipt atomically after validation.

        An interrupted call has unknown actual cost: evaluations must be None
        and the full allowance is conservatively charged, never refunded.
        Unavailable proposals may cost zero but still consume an action slot.
        """
        if type(action_id) is not int or self.pending is None or action_id != self.pending[0]:
            raise ContractError("stale or missing action receipt")
        if type(status) is not str or status not in self.outcome_counts or type(accepted) is not bool:
            raise ContractError("invalid outcome")
        if status == "interrupted":
            if evaluations is not None:
                raise ContractError("interrupted receipt must declare unknown cost")
            charged, known, unknown = 1, 0, 1
        else:
            known = _integer(evaluations, 0, 1)
            charged, unknown = known, 0
        if status == "ok":
            if known != 1:
                raise ContractError("successful evaluation must cost one call")
            energy = _finite(energy)
        elif energy is not None or accepted:
            raise ContractError("unsuccessful outcome cannot supply accepted energy")
        kind = self.pending[1]
        self.pending = None
        self.charged += charged
        self.known_evaluations += known
        self.unknown_evaluation_allowance += unknown
        self.observed += 1
        self.outcome_counts[status] += 1
        self.cycle_steps += 1
        improved = False
        if status == "ok":
            self.best_observed_energy = energy if self.best_observed_energy is None else min(self.best_observed_energy, energy)
            if accepted:
                self.accepted += 1
                self.current_energy = energy
                if kind in ("initialize", "restart", "escape"):
                    self.cycle_best = energy
                    self.cycle_steps = 0
                    self.stale = 0
                    return
                if self.cycle_best is None or energy < self.cycle_best - self.epsilon:
                    improved = True
                    self.cycle_best = energy
            else:
                self.rejected += 1
        self.stale = 0 if improved else self.stale + 1

    def snapshot(self):
        return {"schema": "stagnation_search_controller/1", "policy": self.policy,
                "budget": self.budget, "charged_evaluations": self.charged,
                "known_evaluations": self.known_evaluations,
                "unknown_evaluation_allowance": self.unknown_evaluation_allowance,
                "remaining_evaluations": self.budget - self.charged,
                "issued_actions": self.issued, "observed_actions": self.observed,
                "maximum_actions": self.maximum_actions,
                "pending_action_id": None if self.pending is None else self.pending[0],
                "reserved_evaluations": int(self.pending is not None),
                "available_unreserved_evaluations": self.budget - self.charged - int(self.pending is not None),
                "action_counts": self.action_counts.copy(), "outcome_counts": self.outcome_counts.copy(),
                "accepted": self.accepted, "rejected": self.rejected,
                "current_energy": self.current_energy, "best_observed_energy": self.best_observed_energy,
                "stale_observations": self.stale, "cycle_steps": self.cycle_steps,
                "stop_reason": "budget_exhausted" if self.charged == self.budget else
                    "action_limit" if self.issued == self.maximum_actions and self.pending is None else None,
                "molecular_adapter_connected": False, "engine_qualification": "not_performed"}

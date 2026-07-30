"""PocketMD Lite admission, grading, and governance contract.

PocketMD Lite refines only candidates admitted by a bounded AND policy. Family
eligibility never implies admission, caller-provided force flags are ignored,
and missing or non-finite inputs fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


POCKETMD_LITE_SCHEMA_VERSION = "pocketmd_lite_contract_v2"
POCKETMD_ADMISSION_POLICY_SCHEMA_VERSION = "pocketmd_admission_policy_v2"

TOPK_DEFAULT_THRESHOLD_PCT = 0.05
POCKETMD_DEFAULT_MAX_PER_TARGET = 8
POCKETMD_DEFAULT_MAX_PER_JOB = 32
POCKETMD_DEFAULT_COST_BUDGET = 32.0
POCKETMD_DEFAULT_UNIT_COST = 1.0
POCKETMD_DEFAULT_COST_UNIT = "normalized_refinement_unit"
POCKETMD_DEFAULT_TOPK_GLOBAL = 32
POCKETMD_DEFAULT_TOPK_PER_TARGET = 8
POCKETMD_DEFAULT_SELECTION_MODE = "union"
POCKETMD_REQUIRED_SELECTION_AUTHORITY_SCHEMA_VERSION = "selection_score_authority_v2"
_REFINE_FAMILIES = frozenset({"gpcr", "kinase", "ion_channel"})

LOCAL_MIN_SURVIVAL_RMSD_A = 2.0
HBOND_PERSISTENCE_MIN = 0.5
CONTACT_PERSISTENCE_MIN = 0.5
MAX_CLASH_COUNT = 0

BAND_GREEN = "green"
BAND_YELLOW = "yellow"
BAND_RED = "red"
BAND_ABSTAIN = "abstain"
BAND_COARSE_ONLY = "coarse_only"

CLAIM_BOUNDARY = (
    "PocketMD Lite admits candidates only when family eligibility, a finite base proxy, upstream Top-K selection, "
    "rank threshold, per-target cap, per-job cap, and remaining normalized-cost budget all pass. A green refinement "
    "additionally requires local-min survival, H-bond and contact persistence, and no residual clash. Missing or "
    "non-finite evidence abstains. It is not all-atom MD and not a binding-affinity claim."
)

_POLICY_FIELDS = frozenset(
    {
        "eligible_families",
        "rank_threshold_pct",
        "max_per_target",
        "max_per_job",
        "cost_budget",
        "unit_cost",
        "cost_unit",
        "selection_policy_sha256",
        "selection_authority_schema_version",
        "topk_global",
        "topk_per_target",
        "selection_mode",
        "target_column",
        "family_column",
        "cost_column",
        "base_proxy_column",
        "policy_sha256",
    }
)


class PocketMdLiteError(ValueError):
    """Raised when a PocketMD contract or evidence value is malformed."""


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize_family(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _num(value: Any, *, field_name: str = "value", strict: bool = True) -> float | None:
    if value is None or value == "":
        return None
    if type(value) is bool:
        if strict:
            raise PocketMdLiteError(f"non-numeric {field_name}: {value!r}")
        return None
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        if strict:
            raise PocketMdLiteError(f"non-numeric {field_name}: {value!r}") from exc
        return None
    return float(out) if math.isfinite(out) else None


def _nonnegative_int(value: Any) -> int | None:
    numeric = _num(value, strict=False)
    if numeric is None or numeric < 0.0 or not float(numeric).is_integer():
        return None
    return int(numeric)


def _config_int(value: Any, *, field_name: str, allow_zero: bool) -> int:
    if type(value) is bool:
        raise PocketMdLiteError(f"{field_name} must be an integer")
    numeric = _num(value, field_name=field_name)
    if numeric is None or not numeric.is_integer():
        raise PocketMdLiteError(f"{field_name} must be an integer")
    result = int(numeric)
    if result < 0 or (not allow_zero and result == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise PocketMdLiteError(f"{field_name} must be {qualifier}")
    return result


def _config_float(value: Any, *, field_name: str) -> float:
    numeric = _num(value, field_name=field_name)
    if numeric is None:
        raise PocketMdLiteError(f"{field_name} must be finite")
    return numeric


def _policy_hash(unsigned: Mapping[str, Any]) -> str:
    payload = {
        "schema_version": POCKETMD_ADMISSION_POLICY_SCHEMA_VERSION,
        "policy": dict(unsigned),
        "admission_expression": (
            "selection_authority_bound && explicit_authority_rank && eligible_family && "
            "finite_base_proxy && upstream_topk_selected && rank_threshold && "
            "target_cap && job_cap && cost_budget"
        ),
        "rank_policy": {
            "rank_pct": "one_based_authority_rank_over_finite_population",
            "admission_count": "max(1,floor(population*threshold))_when_threshold_positive",
        },
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PocketMdAdmissionPolicy:
    eligible_families: tuple[str, ...]
    rank_threshold_pct: float
    max_per_target: int
    max_per_job: int
    cost_budget: float
    unit_cost: float
    cost_unit: str
    selection_policy_sha256: str
    selection_authority_schema_version: str
    topk_global: int
    topk_per_target: int
    selection_mode: str
    target_column: str
    family_column: str
    cost_column: str
    base_proxy_column: str
    policy_sha256: str

    def __post_init__(self) -> None:
        self._validate()
        if self.policy_sha256 != _policy_hash(self._unsigned_mapping()):
            raise PocketMdLiteError("PocketMD admission policy_sha256 mismatch")

    @classmethod
    def create(
        cls,
        *,
        eligible_families: Sequence[str] = tuple(sorted(_REFINE_FAMILIES)),
        rank_threshold_pct: float = TOPK_DEFAULT_THRESHOLD_PCT,
        max_per_target: int = POCKETMD_DEFAULT_MAX_PER_TARGET,
        max_per_job: int = POCKETMD_DEFAULT_MAX_PER_JOB,
        cost_budget: float = POCKETMD_DEFAULT_COST_BUDGET,
        unit_cost: float = POCKETMD_DEFAULT_UNIT_COST,
        cost_unit: str = POCKETMD_DEFAULT_COST_UNIT,
        selection_policy_sha256: str = "",
        selection_authority_schema_version: str = "",
        topk_global: int = POCKETMD_DEFAULT_TOPK_GLOBAL,
        topk_per_target: int = POCKETMD_DEFAULT_TOPK_PER_TARGET,
        selection_mode: str = POCKETMD_DEFAULT_SELECTION_MODE,
        target_column: str = "target",
        family_column: str = "family",
        cost_column: str = "",
        base_proxy_column: str = "binding_energy_mmpbsa_kcal_mol_proxy",
    ) -> "PocketMdAdmissionPolicy":
        if isinstance(eligible_families, (str, bytes)):
            raise PocketMdLiteError("PocketMD eligible_families must be a sequence")
        families = tuple(sorted({_normalize_family(item) for item in eligible_families if _normalize_family(item)}))
        unsigned = {
            "eligible_families": list(families),
            "rank_threshold_pct": _config_float(
                rank_threshold_pct,
                field_name="rank_threshold_pct",
            ),
            "max_per_target": _config_int(
                max_per_target, field_name="max_per_target", allow_zero=False
            ),
            "max_per_job": _config_int(
                max_per_job, field_name="max_per_job", allow_zero=False
            ),
            "cost_budget": _config_float(cost_budget, field_name="cost_budget"),
            "unit_cost": _config_float(unit_cost, field_name="unit_cost"),
            "cost_unit": str(cost_unit or "").strip(),
            "selection_policy_sha256": str(selection_policy_sha256 or "").strip().lower(),
            "selection_authority_schema_version": str(
                selection_authority_schema_version or ""
            ).strip(),
            "topk_global": _config_int(
                topk_global, field_name="topk_global", allow_zero=True
            ),
            "topk_per_target": _config_int(
                topk_per_target, field_name="topk_per_target", allow_zero=True
            ),
            "selection_mode": str(selection_mode or "").strip().lower(),
            "target_column": str(target_column or "").strip(),
            "family_column": str(family_column or "").strip(),
            "cost_column": str(cost_column or "").strip(),
            "base_proxy_column": str(base_proxy_column or "").strip(),
        }
        policy = cls(
            eligible_families=families,
            rank_threshold_pct=unsigned["rank_threshold_pct"],
            max_per_target=unsigned["max_per_target"],
            max_per_job=unsigned["max_per_job"],
            cost_budget=unsigned["cost_budget"],
            unit_cost=unsigned["unit_cost"],
            cost_unit=unsigned["cost_unit"],
            selection_policy_sha256=unsigned["selection_policy_sha256"],
            selection_authority_schema_version=unsigned[
                "selection_authority_schema_version"
            ],
            topk_global=unsigned["topk_global"],
            topk_per_target=unsigned["topk_per_target"],
            selection_mode=unsigned["selection_mode"],
            target_column=unsigned["target_column"],
            family_column=unsigned["family_column"],
            cost_column=unsigned["cost_column"],
            base_proxy_column=unsigned["base_proxy_column"],
            policy_sha256=_policy_hash(unsigned),
        )
        return policy

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PocketMdAdmissionPolicy":
        if not isinstance(payload, Mapping):
            raise PocketMdLiteError("PocketMD admission policy must be a mapping")
        keys = frozenset(str(key) for key in payload)
        missing = sorted(_POLICY_FIELDS - keys)
        extra = sorted(keys - _POLICY_FIELDS)
        if missing or extra:
            raise PocketMdLiteError(
                f"PocketMD admission policy fields mismatch: missing={missing}, extra={extra}"
            )
        families = payload.get("eligible_families")
        if not isinstance(families, (list, tuple)):
            raise PocketMdLiteError("PocketMD eligible_families must be a list")
        policy = cls(
            eligible_families=tuple(str(item) for item in families),
            rank_threshold_pct=_config_float(
                payload.get("rank_threshold_pct"),
                field_name="rank_threshold_pct",
            ),
            max_per_target=_config_int(
                payload.get("max_per_target"),
                field_name="max_per_target",
                allow_zero=False,
            ),
            max_per_job=_config_int(
                payload.get("max_per_job"),
                field_name="max_per_job",
                allow_zero=False,
            ),
            cost_budget=_config_float(
                payload.get("cost_budget"), field_name="cost_budget"
            ),
            unit_cost=_config_float(
                payload.get("unit_cost"), field_name="unit_cost"
            ),
            cost_unit=str(payload.get("cost_unit") or "").strip(),
            selection_policy_sha256=str(
                payload.get("selection_policy_sha256") or ""
            ).strip().lower(),
            selection_authority_schema_version=str(
                payload.get("selection_authority_schema_version") or ""
            ).strip(),
            topk_global=_config_int(
                payload.get("topk_global"), field_name="topk_global", allow_zero=True
            ),
            topk_per_target=_config_int(
                payload.get("topk_per_target"),
                field_name="topk_per_target",
                allow_zero=True,
            ),
            selection_mode=str(payload.get("selection_mode") or "").strip().lower(),
            target_column=str(payload.get("target_column") or "").strip(),
            family_column=str(payload.get("family_column") or "").strip(),
            cost_column=str(payload.get("cost_column") or "").strip(),
            base_proxy_column=str(payload.get("base_proxy_column") or "").strip(),
            policy_sha256=str(payload.get("policy_sha256") or "").strip().lower(),
        )
        return policy

    def _validate(self) -> None:
        if not isinstance(self.eligible_families, tuple):
            raise PocketMdLiteError("PocketMD eligible_families must be a tuple")
        normalized = tuple(sorted({_normalize_family(item) for item in self.eligible_families if _normalize_family(item)}))
        if normalized != self.eligible_families or not normalized:
            raise PocketMdLiteError("PocketMD eligible_families must be non-empty, normalized, and sorted")
        if type(self.rank_threshold_pct) not in {int, float} or not math.isfinite(
            self.rank_threshold_pct
        ) or not 0.0 <= self.rank_threshold_pct <= 1.0:
            raise PocketMdLiteError("PocketMD rank_threshold_pct must be finite and within [0, 1]")
        if type(self.max_per_target) is not int or type(self.max_per_job) is not int:
            raise PocketMdLiteError("PocketMD target and job caps must be integers")
        if self.max_per_target <= 0 or self.max_per_job <= 0:
            raise PocketMdLiteError("PocketMD target and job caps must be positive")
        if self.max_per_target > self.max_per_job:
            raise PocketMdLiteError("PocketMD max_per_target cannot exceed max_per_job")
        if type(self.cost_budget) not in {int, float} or not math.isfinite(
            self.cost_budget
        ) or self.cost_budget <= 0.0:
            raise PocketMdLiteError("PocketMD cost_budget must be finite and positive")
        if type(self.unit_cost) not in {int, float} or not math.isfinite(
            self.unit_cost
        ) or self.unit_cost <= 0.0:
            raise PocketMdLiteError("PocketMD unit_cost must be finite and positive")
        string_fields = {
            "cost_unit": self.cost_unit,
            "selection_policy_sha256": self.selection_policy_sha256,
            "selection_authority_schema_version": self.selection_authority_schema_version,
            "selection_mode": self.selection_mode,
            "target_column": self.target_column,
            "family_column": self.family_column,
            "cost_column": self.cost_column,
            "base_proxy_column": self.base_proxy_column,
            "policy_sha256": self.policy_sha256,
        }
        if any(type(value) is not str for value in string_fields.values()):
            raise PocketMdLiteError("PocketMD policy text fields must be strings")
        if not self.cost_unit:
            raise PocketMdLiteError("PocketMD cost_unit is required")
        if self.selection_policy_sha256 and not re.fullmatch(
            r"[0-9a-f]{64}", self.selection_policy_sha256
        ):
            raise PocketMdLiteError(
                "PocketMD selection_policy_sha256 must be empty or lowercase sha256"
            )
        if bool(self.selection_policy_sha256) != bool(
            self.selection_authority_schema_version
        ):
            raise PocketMdLiteError(
                "PocketMD selection authority schema and policy hash must be provided together"
            )
        if self.selection_authority_schema_version not in {
            "",
            POCKETMD_REQUIRED_SELECTION_AUTHORITY_SCHEMA_VERSION,
        }:
            raise PocketMdLiteError(
                "PocketMD selection authority schema must be empty or current v2"
            )
        if type(self.topk_global) is not int or self.topk_global < 0:
            raise PocketMdLiteError("PocketMD topk_global must be a non-negative integer")
        if type(self.topk_per_target) is not int or self.topk_per_target < 0:
            raise PocketMdLiteError(
                "PocketMD topk_per_target must be a non-negative integer"
            )
        if self.selection_mode not in {"union", "intersection"}:
            raise PocketMdLiteError("PocketMD selection_mode must be union or intersection")
        if not self.target_column or not self.family_column or not self.base_proxy_column:
            raise PocketMdLiteError(
                "PocketMD target_column, family_column, and base_proxy_column are required"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.policy_sha256):
            raise PocketMdLiteError("PocketMD policy_sha256 must be lowercase sha256")

    def _unsigned_mapping(self) -> dict[str, Any]:
        return {
            "eligible_families": list(self.eligible_families),
            "rank_threshold_pct": self.rank_threshold_pct,
            "max_per_target": self.max_per_target,
            "max_per_job": self.max_per_job,
            "cost_budget": self.cost_budget,
            "unit_cost": self.unit_cost,
            "cost_unit": self.cost_unit,
            "selection_policy_sha256": self.selection_policy_sha256,
            "selection_authority_schema_version": self.selection_authority_schema_version,
            "topk_global": self.topk_global,
            "topk_per_target": self.topk_per_target,
            "selection_mode": self.selection_mode,
            "target_column": self.target_column,
            "family_column": self.family_column,
            "cost_column": self.cost_column,
            "base_proxy_column": self.base_proxy_column,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._unsigned_mapping(), "policy_sha256": self.policy_sha256}


DEFAULT_POCKETMD_ADMISSION_POLICY = PocketMdAdmissionPolicy.create()


def _decide_pocketmd_admission_from_derived_inputs(
    *,
    family: str,
    target: str,
    base_proxy_value: Any,
    upstream_topk_selected: bool,
    rank_pct: Any,
    authority_rank_global: Any = None,
    authority_population_size: Any = None,
    target_selected_count: Any,
    job_selected_count: Any,
    cumulative_cost: Any,
    estimated_cost: Any = None,
    policy: PocketMdAdmissionPolicy = DEFAULT_POCKETMD_ADMISSION_POLICY,
    selection_authority_bound: bool = False,
) -> dict[str, Any]:
    """Evaluate gates for evidence derived by the engine authority bridge."""

    if not isinstance(policy, PocketMdAdmissionPolicy):
        raise PocketMdLiteError("PocketMD admission policy must be validated")
    policy = PocketMdAdmissionPolicy.from_mapping(policy.to_dict())
    family_normalized = _normalize_family(family)
    target_id = _text(target)
    base_proxy = _num(
        base_proxy_value,
        field_name=policy.base_proxy_column,
        strict=False,
    )
    rank = _num(rank_pct, field_name="rank_pct", strict=False)
    rank_global = _nonnegative_int(authority_rank_global)
    population_size = _nonnegative_int(authority_population_size)
    target_count = _nonnegative_int(target_selected_count)
    job_count = _nonnegative_int(job_selected_count)
    spent = _num(cumulative_cost, field_name="cumulative_cost", strict=False)
    cost = policy.unit_cost if estimated_cost in {None, ""} else _num(
        estimated_cost,
        field_name="estimated_cost",
        strict=False,
    )
    projected = (
        float(spent + cost)
        if spent is not None and spent >= 0.0 and cost is not None and cost > 0.0
        else None
    )

    reasons: list[str] = []
    if type(selection_authority_bound) is not bool or not selection_authority_bound:
        reasons.append("untrusted_or_missing_derived_admission")
    if family_normalized not in policy.eligible_families:
        reasons.append("ineligible_family")
    if not target_id:
        reasons.append("missing_target")
    if base_proxy is None:
        reasons.append("base_proxy_ineligible")
    if not (type(upstream_topk_selected) is bool and upstream_topk_selected):
        reasons.append("not_upstream_topk_selected")
    rank_limit: int | None = None
    explicit_rank_evidence = (
        authority_rank_global is not None or authority_population_size is not None
    )
    if rank is None or not 0.0 <= rank <= 1.0:
        reasons.append("invalid_rank_pct")
    if explicit_rank_evidence:
        if (
            rank_global is None
            or population_size is None
            or rank_global <= 0
            or population_size <= 0
            or rank_global > population_size
        ):
            reasons.append("invalid_authority_rank_evidence")
        else:
            expected_rank_pct = rank_global / population_size
            if rank is None or not math.isclose(
                rank,
                expected_rank_pct,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                reasons.append("inconsistent_authority_rank_pct")
            rank_limit = (
                max(1, math.floor(population_size * policy.rank_threshold_pct))
                if policy.rank_threshold_pct > 0.0
                else 0
            )
            if rank_global > rank_limit:
                reasons.append("rank_threshold_exceeded")
    else:
        reasons.append("missing_authority_rank_evidence")
        if rank is not None and 0.0 <= rank <= 1.0 and rank > policy.rank_threshold_pct:
            reasons.append("rank_threshold_exceeded")
    if target_count is None:
        reasons.append("invalid_target_selected_count")
    elif target_count >= policy.max_per_target:
        reasons.append("target_cap_reached")
    if job_count is None:
        reasons.append("invalid_job_selected_count")
    elif job_count >= policy.max_per_job:
        reasons.append("job_cap_reached")
    if spent is None or spent < 0.0:
        reasons.append("invalid_cumulative_cost")
    if cost is None or cost <= 0.0:
        reasons.append("invalid_estimated_cost")
    elif projected is not None and projected > policy.cost_budget:
        reasons.append("cost_budget_exceeded")

    admitted = not reasons
    return {
        "admitted": admitted,
        "reason_codes": reasons,
        "primary_reason": reasons[0] if reasons else "",
        "family": family_normalized,
        "target": target_id,
        "base_proxy_column": policy.base_proxy_column,
        "base_proxy_value": base_proxy,
        "upstream_topk_selected": bool(type(upstream_topk_selected) is bool and upstream_topk_selected),
        "rank_pct": rank,
        "authority_rank_global": rank_global,
        "authority_population_size": population_size,
        "rank_admission_limit": rank_limit,
        "selection_authority_bound": bool(
            selection_authority_bound
            and policy.selection_policy_sha256
            and policy.selection_authority_schema_version
            == POCKETMD_REQUIRED_SELECTION_AUTHORITY_SCHEMA_VERSION
            and rank_global is not None
            and population_size is not None
            and rank_global > 0
            and population_size > 0
            and rank_global <= population_size
            and rank is not None
            and math.isclose(
                rank,
                rank_global / population_size,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ),
        "target_selected_count_before": target_count,
        "job_selected_count_before": job_count,
        "cumulative_cost_before": spent,
        "estimated_cost": cost,
        "projected_cumulative_cost": projected,
        "cost_unit": policy.cost_unit,
        "policy_sha256": policy.policy_sha256,
    }


def decide_pocketmd_admission(
    *,
    family: str,
    target: str,
    base_proxy_value: Any,
    upstream_topk_selected: bool,
    rank_pct: Any,
    authority_rank_global: Any = None,
    authority_population_size: Any = None,
    target_selected_count: Any,
    job_selected_count: Any,
    cumulative_cost: Any,
    estimated_cost: Any = None,
    policy: PocketMdAdmissionPolicy = DEFAULT_POCKETMD_ADMISSION_POLICY,
) -> dict[str, Any]:
    """Compatibility preflight that can never authorize refinement or claims."""

    return _decide_pocketmd_admission_from_derived_inputs(
        family=family,
        target=target,
        base_proxy_value=base_proxy_value,
        upstream_topk_selected=upstream_topk_selected,
        rank_pct=rank_pct,
        authority_rank_global=authority_rank_global,
        authority_population_size=authority_population_size,
        target_selected_count=target_selected_count,
        job_selected_count=job_selected_count,
        cumulative_cost=cumulative_cost,
        estimated_cost=estimated_cost,
        policy=policy,
        selection_authority_bound=False,
    )


def is_refine_selected(
    *,
    family: str = "",
    target: str = "",
    base_proxy_value: float | None = None,
    upstream_topk_selected: bool = False,
    rank_pct: float | None = None,
    authority_rank_global: int | None = None,
    authority_population_size: int | None = None,
    target_selected_count: int = 0,
    job_selected_count: int = 0,
    cumulative_cost: float = 0.0,
    estimated_cost: float | None = None,
    top_k_threshold_pct: float = TOPK_DEFAULT_THRESHOLD_PCT,
    selection_policy_sha256: str = "",
    selection_authority_schema_version: str = "",
) -> bool:
    """Compatibility boolean over the fail-closed admission decision."""

    policy = PocketMdAdmissionPolicy.create(
        rank_threshold_pct=top_k_threshold_pct,
        selection_policy_sha256=selection_policy_sha256,
        selection_authority_schema_version=selection_authority_schema_version,
    )
    return bool(
        decide_pocketmd_admission(
            family=family,
            target=target,
            base_proxy_value=base_proxy_value,
            upstream_topk_selected=upstream_topk_selected,
            rank_pct=rank_pct,
            authority_rank_global=authority_rank_global,
            authority_population_size=authority_population_size,
            target_selected_count=target_selected_count,
            job_selected_count=job_selected_count,
            cumulative_cost=cumulative_cost,
            estimated_cost=estimated_cost,
            policy=policy,
        )["admitted"]
    )


def _grade_pocketmd_lite_candidate(
    candidate: dict[str, Any],
    *,
    decision: Mapping[str, Any],
    admission_policy: PocketMdAdmissionPolicy,
    admission_population_sha256: str,
    local_min_survival_rmsd_a: float = LOCAL_MIN_SURVIVAL_RMSD_A,
    hbond_persistence_min: float = HBOND_PERSISTENCE_MIN,
    contact_persistence_min: float = CONTACT_PERSISTENCE_MIN,
    max_clash_count: int = MAX_CLASH_COUNT,
) -> dict[str, Any]:
    """Grade one candidate from a decision already authenticated as a batch."""

    if "entry_id" not in candidate:
        raise PocketMdLiteError("candidate missing required field: entry_id")
    if not isinstance(decision, Mapping) or type(decision.get("admitted")) is not bool:
        raise PocketMdLiteError("PocketMD admission decision is invalid")
    policy = PocketMdAdmissionPolicy.from_mapping(admission_policy.to_dict())
    local_min_threshold = _num(
        local_min_survival_rmsd_a,
        field_name="local_min_survival_rmsd_a threshold",
    )
    hbond_threshold = _num(
        hbond_persistence_min,
        field_name="hbond_persistence_min threshold",
    )
    contact_threshold = _num(
        contact_persistence_min,
        field_name="contact_persistence_min threshold",
    )
    clash_threshold = _config_int(
        max_clash_count,
        field_name="max_clash_count threshold",
        allow_zero=True,
    )
    if local_min_threshold is None or local_min_threshold < 0.0:
        raise PocketMdLiteError(
            "local_min_survival_rmsd_a threshold must be finite and non-negative"
        )
    if hbond_threshold is None or not 0.0 <= hbond_threshold <= 1.0:
        raise PocketMdLiteError(
            "hbond_persistence_min threshold must be finite and within [0, 1]"
        )
    if contact_threshold is None or not 0.0 <= contact_threshold <= 1.0:
        raise PocketMdLiteError(
            "contact_persistence_min threshold must be finite and within [0, 1]"
        )
    entry_id = _text(candidate["entry_id"])
    if not entry_id:
        raise PocketMdLiteError("candidate entry_id must be non-empty")
    family = str(decision.get("family") or "")
    target = str(decision.get("target") or "")
    selected = bool(decision.get("admitted") is True)

    ligand_rmsd = _num(candidate.get("local_min_ligand_rmsd_a"), field_name="local_min_ligand_rmsd_a")
    hbond = _num(candidate.get("hbond_persistence"), field_name="hbond_persistence")
    contact = _num(candidate.get("contact_persistence"), field_name="contact_persistence")
    clash_value = _num(candidate.get("clash_count"), field_name="clash_count")
    clash_count = int(clash_value) if clash_value is not None and clash_value.is_integer() else None
    invalid_evidence = bool(
        (ligand_rmsd is not None and ligand_rmsd < 0.0)
        or (hbond is not None and not 0.0 <= hbond <= 1.0)
        or (contact is not None and not 0.0 <= contact <= 1.0)
        or (clash_value is not None and (clash_value < 0.0 or not clash_value.is_integer()))
    )

    reason_code = ""
    review_flags: list[str] = []
    if not selected:
        band = BAND_COARSE_ONLY
        reason_code = str(decision.get("primary_reason") or "not_admitted_for_refine")
        local_min_survived = None
    elif invalid_evidence:
        band = BAND_ABSTAIN
        reason_code = "invalid_refinement_evidence"
        local_min_survived = None
    elif ligand_rmsd is None or hbond is None or contact is None or clash_count is None:
        band = BAND_ABSTAIN
        reason_code = "missing_or_nonfinite_refinement_evidence"
        local_min_survived = None
    else:
        local_min_survived = ligand_rmsd <= local_min_threshold
        if not local_min_survived:
            band = BAND_RED
            reason_code = "local_min_did_not_survive"
        else:
            if clash_count > clash_threshold:
                review_flags.append("residual_clash")
            if hbond < hbond_threshold:
                review_flags.append("weak_hbond_persistence")
            if contact < contact_threshold:
                review_flags.append("weak_contact_persistence")
            if review_flags:
                band = BAND_YELLOW
                reason_code = review_flags[0]
            else:
                band = BAND_GREEN

    return {
        "entry_id": entry_id,
        "target": target,
        "family": family,
        "selected_for_refine": selected,
        "selected_for_refine_override_ignored": bool(candidate.get("selected_for_refine") is True),
        "admission": dict(decision),
        "admission_population_sha256": admission_population_sha256,
        "admission_policy": policy.to_dict(),
        "band": band,
        "claim_safe": band == BAND_GREEN,
        "abstained": band == BAND_ABSTAIN,
        "local_min_ligand_rmsd_a": ligand_rmsd,
        "local_min_survived": local_min_survived,
        "hbond_persistence": hbond,
        "contact_persistence": contact,
        "clash_count": clash_count,
        "reason_code": reason_code,
        "review_flags": review_flags,
        "thresholds": {
            "local_min_survival_rmsd_a": local_min_threshold,
            "hbond_persistence_min": hbond_threshold,
            "contact_persistence_min": contact_threshold,
            "max_clash_count": clash_threshold,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_pocketmd_lite_assessment(
    candidate: dict[str, Any],
    *,
    admission: Any | None = None,
    admission_policy: PocketMdAdmissionPolicy | None = None,
    top_k_threshold_pct: float = TOPK_DEFAULT_THRESHOLD_PCT,
    local_min_survival_rmsd_a: float = LOCAL_MIN_SURVIVAL_RMSD_A,
    hbond_persistence_min: float = HBOND_PERSISTENCE_MIN,
    contact_persistence_min: float = CONTACT_PERSISTENCE_MIN,
    max_clash_count: int = MAX_CLASH_COUNT,
) -> dict[str, Any]:
    """Grade one candidate conservatively; single-row admission is never authoritative.

    Admission depends on a complete ranked population, so even an authentic
    receipt detached from its batch is deliberately ignored here.  Claim-safe
    grading is available only through :func:`build_pocketmd_lite_report`.
    """

    policy = PocketMdAdmissionPolicy.from_mapping(
        (
            admission_policy
            or PocketMdAdmissionPolicy.create(
                rank_threshold_pct=top_k_threshold_pct
            )
        ).to_dict()
    )
    reason_codes = ["untrusted_or_missing_derived_admission"]
    if admission is not None:
        reason_codes.append("detached_admission_receipt_ignored")
    decision = {
        "admitted": False,
        "reason_codes": reason_codes,
        "primary_reason": reason_codes[0],
        "family": _normalize_family(candidate.get("family")),
        "target": _text(candidate.get("target")),
        "selection_authority_bound": False,
        "policy_sha256": policy.policy_sha256,
    }
    return _grade_pocketmd_lite_candidate(
        candidate,
        decision=decision,
        admission_policy=policy,
        admission_population_sha256="",
        local_min_survival_rmsd_a=local_min_survival_rmsd_a,
        hbond_persistence_min=hbond_persistence_min,
        contact_persistence_min=contact_persistence_min,
        max_clash_count=max_clash_count,
    )


def build_pocketmd_lite_report(
    candidates: list[dict[str, Any]],
    *,
    admission_batch: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Grade candidates using an authenticated, population-bound admission batch."""

    from betelgeuze_engine.product.pocketmd_admission_authority import (
        validate_pocketmd_admission_batch,
    )

    validated = validate_pocketmd_admission_batch(admission_batch, candidates)
    admission_policy = validated["policy"]
    selection_authority = validated["selection_authority"]
    entry_id_column = str(validated["entry_id_column"])
    rows: list[dict[str, Any]] = []
    target_counts: dict[str, int] = {}
    cumulative_cost = 0.0
    admission_reason_counts: dict[str, int] = {}
    for record in validated["records"]:
        source_index = int(record["source_index"])
        candidate = candidates[source_index]
        entry_id = _text(candidate.get(entry_id_column))
        assessment_candidate = {
            **candidate,
            "entry_id": entry_id,
        }
        row = _grade_pocketmd_lite_candidate(
            assessment_candidate,
            decision=record["decision"],
            admission_policy=admission_policy,
            admission_population_sha256=validated["population_sha256"],
            **kwargs,
        )
        decision = row["admission"]
        row["authority_rank_global"] = decision.get("authority_rank_global")
        row["authority_population_size"] = decision.get(
            "authority_population_size"
        )
        row["selection_policy_sha256"] = admission_policy.selection_policy_sha256
        row["caller_rank_pct_ignored"] = "rank_pct" in candidate
        row["caller_upstream_topk_selected_ignored"] = (
            "upstream_topk_selected" in candidate
        )
        rows.append(row)
        if decision["admitted"]:
            target = str(decision.get("target") or "")
            target_counts[target] = target_counts.get(target, 0) + 1
            cumulative_cost = max(
                cumulative_cost,
                float(decision.get("cumulative_cost_after") or 0.0),
            )
        else:
            for reason in decision["reason_codes"]:
                admission_reason_counts[reason] = admission_reason_counts.get(reason, 0) + 1

    band_counts = {
        BAND_GREEN: 0,
        BAND_YELLOW: 0,
        BAND_RED: 0,
        BAND_ABSTAIN: 0,
        BAND_COARSE_ONLY: 0,
    }
    for row in rows:
        band_counts[row["band"]] += 1
    refined = sum(band_counts[band] for band in (BAND_GREEN, BAND_YELLOW, BAND_RED, BAND_ABSTAIN))
    summary = {
        "schema_version": POCKETMD_LITE_SCHEMA_VERSION,
        "candidate_count": len(rows),
        "refined_count": refined,
        "coarse_only_count": band_counts[BAND_COARSE_ONLY],
        "band_counts": band_counts,
        "refine_claim_safe_rate": (round(band_counts[BAND_GREEN] / refined, 6) if refined else 0.0),
        "abstention_rate": (round(band_counts[BAND_ABSTAIN] / refined, 6) if refined else 0.0),
        "admission_policy": admission_policy.to_dict(),
        "selection_score_authority": selection_authority,
        "selection_policy_sha256": admission_policy.selection_policy_sha256,
        "authority_population_size": validated["authority_eligible_count"],
        "population_sha256": validated["population_sha256"],
        "admitted_target_counts": target_counts,
        "admitted_cost": cumulative_cost,
        "admission_reason_counts": admission_reason_counts,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


__all__ = [
    "POCKETMD_LITE_SCHEMA_VERSION",
    "POCKETMD_ADMISSION_POLICY_SCHEMA_VERSION",
    "TOPK_DEFAULT_THRESHOLD_PCT",
    "POCKETMD_DEFAULT_MAX_PER_TARGET",
    "POCKETMD_DEFAULT_MAX_PER_JOB",
    "POCKETMD_DEFAULT_COST_BUDGET",
    "POCKETMD_DEFAULT_UNIT_COST",
    "POCKETMD_DEFAULT_COST_UNIT",
    "LOCAL_MIN_SURVIVAL_RMSD_A",
    "HBOND_PERSISTENCE_MIN",
    "CONTACT_PERSISTENCE_MIN",
    "MAX_CLASH_COUNT",
    "BAND_GREEN",
    "BAND_YELLOW",
    "BAND_RED",
    "BAND_ABSTAIN",
    "BAND_COARSE_ONLY",
    "CLAIM_BOUNDARY",
    "PocketMdLiteError",
    "PocketMdAdmissionPolicy",
    "DEFAULT_POCKETMD_ADMISSION_POLICY",
    "build_pocketmd_lite_assessment",
    "build_pocketmd_lite_report",
]

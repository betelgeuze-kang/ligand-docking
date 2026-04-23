from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping, Optional

from core.definitions import ResearchConstants


# Derived from 2026-02-14 sweep artifacts.
# Conservative profile prioritizes long-horizon stability.
_CONSERVATIVE_V1: Dict[str, int] = {
    "BBA5": 1,
    "Chignolin": 10,
    "Crambin": 10,
    "FSD_1": 4,
    "GB1_Mini": 1,
    "Protein_A_Bdomain": 1,
    "Trp_Cage": 1,
    "Ubiquitin_Mini": 10,
    "Villin_HP35": 1,
    "WW_Domain_FiP35": 1,
}

# Aggressive profile prioritizes throughput and short-horizon stability.
_AGGRESSIVE_V1: Dict[str, int] = {
    "BBA5": 10,
    "Chignolin": 10,
    "Crambin": 10,
    "FSD_1": 10,
    "GB1_Mini": 10,
    "Protein_A_Bdomain": 10,
    "Trp_Cage": 10,
    "Ubiquitin_Mini": 10,
    "Villin_HP35": 10,
    "WW_Domain_FiP35": 6,
}

# Speed-optimized profile derived from 2026-02-18 all-target
# interval/top-k sweep (topk=1 constraint).
_SPEED_OPT_2026_02_18_V1: Dict[str, int] = {
    "BBA5": 4,
    "Chignolin": 4,
    "Crambin": 2,
    "FSD_1": 4,
    "GB1_Mini": 4,
    "Protein_A_Bdomain": 4,
    "Trp_Cage": 4,
    "Ubiquitin_Mini": 4,
    "Villin_HP35": 4,
    "WW_Domain_FiP35": 4,
}

PRESET_TARGET_INTERVAL_POLICIES: Dict[str, Dict[str, int]] = {
    "conservative_v1": _CONSERVATIVE_V1,
    "aggressive_v1": _AGGRESSIVE_V1,
    "speed_opt_2026_02_18_v1": _SPEED_OPT_2026_02_18_V1,
    "speed_opt_v2": _SPEED_OPT_2026_02_18_V1,
}

# Drift-threshold profile used by adaptive MTS guard.
# Higher value = less aggressive forced AI re-evaluation.
_DRIFT_BALANCED_V1: Dict[str, float] = {
    "BBA5": 1.0,
    "Chignolin": 2.5,
    "Crambin": 1.0,
    "FSD_1": 2.5,
    "GB1_Mini": 1.0,
    "Protein_A_Bdomain": 1.0,
    "Trp_Cage": 1.0,
    "Ubiquitin_Mini": 1.0,
    "Villin_HP35": 1.0,
    "WW_Domain_FiP35": 1.0,
}

_DRIFT_STRICT_V1: Dict[str, float] = {k: 0.25 for k in ResearchConstants.CHALLENGES.keys()}

PRESET_TARGET_DRIFT_THRESHOLD_POLICIES: Dict[str, Dict[str, float]] = {
    "balanced_v1": _DRIFT_BALANCED_V1,
    "strict_v1": _DRIFT_STRICT_V1,
}


def parse_target_interval_policy(
    spec: Optional[str] = None,
    policy_map: Optional[Mapping[str, int]] = None,
) -> Dict[str, int]:
    if policy_map is not None:
        return _normalize_policy_map(policy_map)

    s = "" if spec is None else str(spec).strip()
    if not s:
        return {}

    preset = PRESET_TARGET_INTERVAL_POLICIES.get(s.lower())
    if preset is not None:
        return dict(preset)
    file_policy = _try_load_interval_policy_from_json_spec(s)
    if file_policy is not None:
        return file_policy

    out: Dict[str, int] = {}
    for token in s.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            k, v = token.split("=", 1)
        elif ":" in token:
            k, v = token.split(":", 1)
        else:
            raise ValueError(f"Invalid target policy entry '{token}' (expected target=interval)")
        target = k.strip()
        interval = max(int(v.strip()), 1)
        if target not in ResearchConstants.CHALLENGES:
            known = ", ".join(sorted(ResearchConstants.CHALLENGES.keys()))
            raise ValueError(f"Unknown target '{target}'. Known targets: {known}")
        out[target] = interval
    return out


def resolve_target_ai_interval(
    target: str,
    default_interval: int,
    policy: Optional[Mapping[str, int]] = None,
) -> int:
    base = max(int(default_interval), 1)
    if not policy:
        return base
    return max(int(policy.get(target, base)), 1)


def parse_target_drift_threshold_policy(
    spec: Optional[str] = None,
    policy_map: Optional[Mapping[str, float]] = None,
) -> Dict[str, float]:
    if policy_map is not None:
        return _normalize_float_policy_map(policy_map, floor=0.0)

    s = "" if spec is None else str(spec).strip()
    if not s:
        return {}

    preset = PRESET_TARGET_DRIFT_THRESHOLD_POLICIES.get(s.lower())
    if preset is not None:
        return dict(preset)

    out: Dict[str, float] = {}
    for token in s.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            k, v = token.split("=", 1)
        elif ":" in token:
            k, v = token.split(":", 1)
        else:
            raise ValueError(f"Invalid target float policy entry '{token}' (expected target=value)")
        target = k.strip()
        value = max(float(v.strip()), 0.0)
        if target not in ResearchConstants.CHALLENGES:
            known = ", ".join(sorted(ResearchConstants.CHALLENGES.keys()))
            raise ValueError(f"Unknown target '{target}'. Known targets: {known}")
        out[target] = value
    return out


def resolve_target_float_value(
    target: str,
    default_value: float,
    policy: Optional[Mapping[str, float]] = None,
    floor: float = 0.0,
) -> float:
    base = max(float(default_value), float(floor))
    if not policy:
        return base
    return max(float(policy.get(target, base)), float(floor))


def _normalize_policy_map(policy_map: Mapping[str, int]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for target, interval in policy_map.items():
        if target not in ResearchConstants.CHALLENGES:
            known = ", ".join(sorted(ResearchConstants.CHALLENGES.keys()))
            raise ValueError(f"Unknown target '{target}'. Known targets: {known}")
        out[str(target)] = max(int(interval), 1)
    return out


def _normalize_float_policy_map(
    policy_map: Mapping[str, float],
    floor: float = 0.0,
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for target, value in policy_map.items():
        if target not in ResearchConstants.CHALLENGES:
            known = ", ".join(sorted(ResearchConstants.CHALLENGES.keys()))
            raise ValueError(f"Unknown target '{target}'. Known targets: {known}")
        out[str(target)] = max(float(value), float(floor))
    return out


def _try_load_interval_policy_from_json_spec(spec: str) -> Optional[Dict[str, int]]:
    s = str(spec).strip()
    if not s:
        return None

    candidate_path = ""
    if s.startswith("@"):
        candidate_path = s[1:].strip()
    elif s.lower().endswith(".json") and os.path.exists(s):
        candidate_path = s
    if not candidate_path:
        return None

    path_i = os.path.abspath(candidate_path)
    if not os.path.exists(path_i):
        raise FileNotFoundError(f"target interval policy json not found: {path_i}")
    with open(path_i, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return _extract_interval_policy_from_payload(payload, source_path=path_i)


def _extract_interval_policy_from_payload(payload: Any, source_path: str) -> Dict[str, int]:
    # Case 1) flat mapping: {"Chignolin": 8, ...}
    if isinstance(payload, dict) and payload:
        if all(isinstance(k, str) for k in payload.keys()) and all(
            isinstance(v, (int, float)) for v in payload.values()
        ):
            return _normalize_policy_map({k: int(v) for k, v in payload.items()})

    # Case 2) nested known keys
    if isinstance(payload, dict):
        for key in ("policy", "target_ai_interval_policy", "interval_policy"):
            item = payload.get(key)
            if isinstance(item, dict) and item:
                if all(isinstance(v, (int, float)) for v in item.values()):
                    return _normalize_policy_map({k: int(v) for k, v in item.items()})

        # Case 3) targets schema:
        # {"targets": {"Chignolin": {"ai_interval": 8}, "Trp_Cage": 2}}
        targets = payload.get("targets")
        if isinstance(targets, dict) and targets:
            out: Dict[str, int] = {}
            for target, val in targets.items():
                if isinstance(val, (int, float)):
                    out[str(target)] = int(val)
                    continue
                if isinstance(val, dict):
                    for k in ("ai_interval", "interval", "target_ai_interval"):
                        if k in val:
                            out[str(target)] = int(val[k])
                            break
            if out:
                return _normalize_policy_map(out)

    raise ValueError(
        "invalid target interval policy json format "
        f"(path={source_path}). Expected flat mapping or payload.policy mapping."
    )


class AdaptiveMTSController:
    """적응형 MTS AI 호출 간격 컨트롤러.

    기본 ``base_interval`` (8) ~ ``max_interval`` (16) 범위에서 동작하며,
    drift 또는 잔차가 임계값을 초과하면 ``min_interval`` (1)로 즉시 축소합니다.
    ``stable_upshift_window`` 연속 안정 스텝 후 interval을 1씩 복구합니다.

    사용법::

        ctrl = AdaptiveMTSController()
        for step in range(total_steps):
            interval, info = ctrl.step(residual_norm, displacement_norm)
            if step % interval == 0:
                run_ai_correction()
    """

    def __init__(
        self,
        base_interval: int = 8,
        max_interval: int = 16,
        min_interval: int = 1,
        drift_threshold: float = 0.25,
        residual_threshold: float = 1.0,
        stable_upshift_window: int = 50,
    ) -> None:
        self.base_interval = max(int(base_interval), 1)
        self.max_interval = max(int(max_interval), self.base_interval)
        self.min_interval = max(int(min_interval), 1)
        if self.min_interval > self.base_interval:
            self.min_interval = self.base_interval
        self.drift_threshold = max(float(drift_threshold), 0.0)
        self.residual_threshold = max(float(residual_threshold), 0.0)
        self.stable_upshift_window = max(int(stable_upshift_window), 0)

        self._current_interval: int = self.base_interval
        self._stable_count: int = 0
        self._total_downshifts: int = 0
        self._total_upshifts: int = 0

    @property
    def current_interval(self) -> int:
        return self._current_interval

    @property
    def total_downshifts(self) -> int:
        return self._total_downshifts

    @property
    def total_upshifts(self) -> int:
        return self._total_upshifts

    def reset(self) -> None:
        """컨트롤러 상태를 초기화합니다."""
        self._current_interval = self.base_interval
        self._stable_count = 0
        self._total_downshifts = 0
        self._total_upshifts = 0

    def step(
        self,
        residual_norm: float,
        displacement_norm: float,
    ) -> "tuple[int, dict]":
        """한 스텝의 drift/잔차를 평가하고 interval을 조정합니다.

        Args:
            residual_norm: AI 보정력 잔차 노름 (또는 불확실도 스코어).
            displacement_norm: 평균 원자 변위 노름.

        Returns:
            ``(current_interval, info_dict)`` 튜플.
            ``info_dict``에는 ``'action'`` (``'downshift'``, ``'upshift'``, ``'hold'``),
            ``'stable_count'``, ``'interval'`` 키가 포함됩니다.
        """
        residual_norm_f = float(residual_norm)
        displacement_norm_f = float(displacement_norm)

        exceeded_drift = (
            self.drift_threshold > 0.0 and displacement_norm_f > self.drift_threshold
        )
        exceeded_residual = (
            self.residual_threshold > 0.0 and residual_norm_f > self.residual_threshold
        )

        if exceeded_drift or exceeded_residual:
            # 즉시 최소 interval로 축소
            old = self._current_interval
            self._current_interval = self.min_interval
            self._stable_count = 0
            if old > self.min_interval:
                self._total_downshifts += 1
            return self._current_interval, {
                "action": "downshift",
                "stable_count": 0,
                "interval": self._current_interval,
                "exceeded_drift": exceeded_drift,
                "exceeded_residual": exceeded_residual,
            }

        # 안정 상태
        self._stable_count += 1

        if (
            self.stable_upshift_window > 0
            and self._stable_count >= self.stable_upshift_window
            and self._current_interval < self.max_interval
        ):
            self._current_interval = min(self._current_interval + 1, self.max_interval)
            self._stable_count = 0
            self._total_upshifts += 1
            return self._current_interval, {
                "action": "upshift",
                "stable_count": 0,
                "interval": self._current_interval,
                "exceeded_drift": False,
                "exceeded_residual": False,
            }

        return self._current_interval, {
            "action": "hold",
            "stable_count": self._stable_count,
            "interval": self._current_interval,
            "exceeded_drift": False,
            "exceeded_residual": False,
        }

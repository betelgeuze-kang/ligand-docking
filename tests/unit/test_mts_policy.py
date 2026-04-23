import pytest

from core.definitions import ResearchConstants
from core.mts_policy import (
    PRESET_TARGET_INTERVAL_POLICIES,
    parse_target_interval_policy,
    resolve_target_ai_interval,
)


def test_parse_target_interval_policy_preset_contains_all_targets():
    policy = parse_target_interval_policy("conservative_v1")
    assert set(policy.keys()) == set(ResearchConstants.CHALLENGES.keys())
    assert all(v >= 1 for v in policy.values())


def test_parse_target_interval_policy_custom_spec():
    policy = parse_target_interval_policy("Chignolin=8,Trp_Cage:2")
    assert policy["Chignolin"] == 8
    assert policy["Trp_Cage"] == 2


def test_parse_target_interval_policy_invalid_target_raises():
    with pytest.raises(ValueError):
        parse_target_interval_policy("UnknownTarget=4")


def test_resolve_target_ai_interval_fallback_and_override():
    policy = {"Chignolin": 7}
    assert resolve_target_ai_interval("Chignolin", default_interval=1, policy=policy) == 7
    assert resolve_target_ai_interval("Trp_Cage", default_interval=3, policy=policy) == 3


def test_presets_are_registered():
    assert "conservative_v1" in PRESET_TARGET_INTERVAL_POLICIES
    assert "aggressive_v1" in PRESET_TARGET_INTERVAL_POLICIES
    assert "speed_opt_2026_02_18_v1" in PRESET_TARGET_INTERVAL_POLICIES
    assert "speed_opt_v2" in PRESET_TARGET_INTERVAL_POLICIES


def test_parse_target_interval_policy_from_json_policy_key(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text(
        '{"policy":{"Chignolin":8,"Trp_Cage":2}}',
        encoding="utf-8",
    )
    out = parse_target_interval_policy(str(p))
    assert out["Chignolin"] == 8
    assert out["Trp_Cage"] == 2


def test_parse_target_interval_policy_from_json_targets_schema(tmp_path):
    p = tmp_path / "policy_targets.json"
    p.write_text(
        '{"targets":{"Chignolin":{"ai_interval":6},"Trp_Cage":3}}',
        encoding="utf-8",
    )
    out = parse_target_interval_policy(f"@{p}")
    assert out["Chignolin"] == 6
    assert out["Trp_Cage"] == 3

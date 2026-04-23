import json

from tools import speed_profile_defaults as spd


def test_load_speed_profile_section_sections_shape(tmp_path):
    p = tmp_path / "speed_defaults.json"
    p.write_text(
        json.dumps(
            {
                "sections": {
                    "nightly": {
                        "speed_mode": "max",
                        "speed_mode_replicas": 128,
                        "speed_profile_max_replicas": 128,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    sec = spd.load_speed_profile_section(str(p), "nightly")
    assert sec["speed_mode"] == "max"
    assert int(sec["speed_mode_replicas"]) == 128


def test_resolve_speed_profile_prefers_explicit_over_defaults():
    out = spd.resolve_speed_profile(
        explicit_mode="turbo",
        explicit_replicas=64,
        explicit_max_replicas=256,
        section_defaults={
            "speed_mode": "fast",
            "speed_mode_replicas": 32,
            "speed_profile_max_replicas": 128,
        },
        fallback={
            "speed_mode": "balanced",
            "speed_mode_replicas": 4,
            "speed_profile_max_replicas": 64,
        },
    )
    assert out["speed_mode"] == "turbo"
    assert out["speed_mode_replicas"] == 64
    assert out["speed_profile_max_replicas"] == 256


def test_resolve_retry_ladder_from_explicit_string():
    ladder = spd.resolve_retry_ladder(
        explicit_ladder="fast:32:128,turbo:64:256,extreme:128:512",
        section_defaults={},
        fallback_ladder=[{"speed_mode": "balanced", "speed_mode_replicas": 4, "speed_profile_max_replicas": 64}],
    )
    assert len(ladder) == 3
    assert ladder[0]["speed_mode"] == "fast"
    assert ladder[1]["speed_mode_replicas"] == 64
    assert ladder[2]["speed_profile_max_replicas"] == 512


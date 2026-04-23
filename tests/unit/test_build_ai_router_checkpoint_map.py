import json
from pathlib import Path

import pytest

from tools.build_ai_router_checkpoint_map import build_ai_router_checkpoint_map


def _write_ckpt(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mock")


def test_build_checkpoint_map_from_curriculum_summary(tmp_path):
    ckpt_a = tmp_path / "models" / "a.pth"
    ckpt_b = tmp_path / "models" / "b.pth"
    _write_ckpt(ckpt_a)
    _write_ckpt(ckpt_b)

    src = tmp_path / "curriculum.json"
    src.write_text(
        json.dumps(
            {
                "distilled_manifest": "runs/distilled_residual_manifest_bigdata.csv",
                "schedule": "size_ascending",
                "run_tag": "x",
                "targets": [
                    {"target": "Chignolin", "best_checkpoint_path": str(ckpt_a)},
                    {"target": "Trp_Cage", "best_checkpoint_path": str(ckpt_b)},
                ],
            }
        ),
        encoding="utf-8",
    )

    out_json = tmp_path / "map.json"
    payload = build_ai_router_checkpoint_map(
        curriculum_summary_json=str(src),
        out_json=str(out_json),
        default_target="Trp_Cage",
        allow_missing_checkpoint=False,
    )
    assert out_json.exists()
    assert payload["target_checkpoints"]["Chignolin"] == str(ckpt_a.resolve())
    assert payload["default"] == str(ckpt_b.resolve())


def test_build_checkpoint_map_fails_when_missing_checkpoint(tmp_path):
    src = tmp_path / "curriculum_missing.json"
    src.write_text(
        json.dumps(
            {
                "targets": [
                    {"target": "Chignolin", "best_checkpoint_path": str(tmp_path / "nope.pth")},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        build_ai_router_checkpoint_map(
            curriculum_summary_json=str(src),
            out_json=str(tmp_path / "map.json"),
            allow_missing_checkpoint=False,
        )

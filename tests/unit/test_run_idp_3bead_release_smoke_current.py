import json
from pathlib import Path

from tools import run_idp_3bead_release_smoke_current as smoke_current


def test_run_current_uses_smoke_current_and_release_manifest_defaults(tmp_path, monkeypatch):
    smoke_current_json = tmp_path / "smoke_current.json"
    smoke_current_json.write_text(
        json.dumps(
            {
                "release_label": "smoke_current",
                "smoke_baseline_manifest_json": str(tmp_path / "smoke_baseline_manifest.json"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    def _fake_run_smoke(args):
        captured["args"] = args
        return {"pass": True, "summary": {"pass": True}}

    monkeypatch.setattr(smoke_current, "run_smoke", _fake_run_smoke)

    args = smoke_current.build_parser().parse_args(
        [
            "--smoke-current-json",
            str(smoke_current_json),
            "--release-manifest-current-json",
            str(tmp_path / "release_manifest_current.json"),
            "--config-json",
            str(tmp_path / "config.json"),
            "--device",
            "cpu",
            "--tag",
            "check",
        ]
    )
    payload = smoke_current.run_current(args)

    smoke_args = captured["args"]
    assert smoke_args.baseline_manifest_json == str(tmp_path / "smoke_baseline_manifest.json")
    assert smoke_args.frozen_labels_manifest_json == str(tmp_path / "release_manifest_current.json")
    assert "check" in smoke_args.out_prefix
    assert payload["pass"] is True

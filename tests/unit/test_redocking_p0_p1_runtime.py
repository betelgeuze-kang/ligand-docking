import json
import pytest
from tools import redocking_p0_p1_runtime as runtime


def test_missing_native_bootstrap_reference_fails_before_download(
    tmp_path, monkeypatch
):
    called = []
    monkeypatch.setattr(runtime, "command", lambda *a, **k: called.append(a))
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with pytest.raises(RuntimeError, match="bootstrap native reference"):
        runtime.native_runtime(bundle, tmp_path / "native", tmp_path / "output")
    assert not called
    assert not (tmp_path / "native-wheels").exists()


def test_missing_evaluator_bootstrap_reference_cannot_be_recreated(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    output = tmp_path / "output"
    with pytest.raises(RuntimeError, match="bootstrap environment reference"):
        runtime.preflight(bundle, tmp_path / "inputs", output)
    assert not (bundle / "reference-environment.json").exists()
    assert not (tmp_path / "inputs").exists()
    report = json.loads((output / "preflight.json").read_text())
    assert report["status"] == "failed"
    assert report["environment_role"] == "worker_comparison"


def test_only_admission_may_create_reference():
    import yaml

    workflow = yaml.load(
        (runtime.ROOT / ".github/workflows/redocking_p0_p1.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    for job, expected in [("admission", 2), ("development", 0), ("aggregate", 0)]:
        commands = "\n".join(
            step.get("run", "") for step in workflow["jobs"][job]["steps"]
        )
        assert commands.count("--create-reference") == expected

import types

from tools import run_rust_native_inference_poc as mod


def test_extract_json_from_stdout_direct():
    payload = mod._extract_json_from_stdout('{"ok": true, "v": 1}')
    assert payload["ok"] is True
    assert payload["v"] == 1


def test_extract_json_from_stdout_tail():
    text = "log line\nmore log\n{\"ok\": false, \"reason\": \"x\"}"
    payload = mod._extract_json_from_stdout(text)
    assert payload["ok"] is False
    assert payload["reason"] == "x"


def test_run_poc_with_existing_onnx(monkeypatch, tmp_path):
    onnx = tmp_path / "x.onnx"
    onnx.write_text("dummy", encoding="utf-8")

    def fake_run(cmd, capture_output, text, check):
        return types.SimpleNamespace(returncode=0, stdout='{"ok": true, "elapsed_ms": 1.0}', stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    args = mod.build_parser().parse_args([])
    args.target = "Chignolin"
    args.onnx_path = str(onnx)
    args.out_json = str(tmp_path / "summary.json")
    args.cargo_manifest = "rust_engine/Cargo.toml"
    out = mod.run_poc(args)
    assert out["ok"] is True
    assert out["returncode"] == 0
    assert out["rust_stdout_json"]["ok"] is True

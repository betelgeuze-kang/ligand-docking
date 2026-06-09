from __future__ import annotations

import json
from pathlib import Path

from tools import builder_json_utils as mod


def test_read_summary_accepts_flat_and_wrapped_packets() -> None:
    assert mod.read_summary({"status": "flat_ready", "goal_complete": True})["goal_complete"] is True
    assert mod.read_summary({"summary": {"status": "wrapped_ready"}})["status"] == "wrapped_ready"


def test_fingerprint_digest_changes_when_input_changes(tmp_path: Path) -> None:
    csv_a = tmp_path / "a.csv"
    csv_b = tmp_path / "b.csv"
    deriv = tmp_path / "deriv.json"
    csv_a.write_text("a\n", encoding="utf-8")
    csv_b.write_text("b\n", encoding="utf-8")
    deriv.write_text("{}", encoding="utf-8")
    fp_a = mod.build_score_model_train_fingerprint(
        input_csv=csv_a,
        force_derivation_json=deriv,
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        lr=1e-3,
        weight_decay=1e-5,
        train_ratio=0.8,
        seed=1,
        root=tmp_path,
    )
    fp_b = mod.build_score_model_train_fingerprint(
        input_csv=csv_b,
        force_derivation_json=deriv,
        epochs=2,
        hidden_dim=8,
        batch_size=8,
        lr=1e-3,
        weight_decay=1e-5,
        train_ratio=0.8,
        seed=1,
        root=tmp_path,
    )
    assert mod.fingerprint_digest(fp_a) != mod.fingerprint_digest(fp_b)

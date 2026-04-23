from tools import classify_runs_files as mod


def test_role_for_latest_gate_attempts_csv():
    role = mod._role_for_latest("post_gate_pipeline_2026-02-19_gate_attempts.csv")
    assert role == "gate_attempts_csv"


from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_aqp1_p0_packet_plan as mod


def test_aqp1_plan_current_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, 'RUNS', tmp_path)
    mod.main()
    payload = json.loads((tmp_path / 'aqp1_p0_packet_plan_current.json').read_text())
    summary = payload['summary']
    assert summary['target_id'] == 'Aquaporin_1'
    assert summary['task_id'] == 'aqp1_core_full'
    assert summary['ready_count'] >= 1
    assert 'aqp1_ligand_reference' in summary['next_priority_steps']
    rows = {row['step_id']: row for row in payload['rows']}
    assert rows['aqp1_profile_json']['status'] == 'ready'
    assert rows['aqp1_ligand_reference']['status'] == 'todo'

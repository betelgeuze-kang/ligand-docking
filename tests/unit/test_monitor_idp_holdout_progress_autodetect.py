from __future__ import annotations

import json
from pathlib import Path

from tools import monitor_idp_holdout_progress as mod


def test_infer_total_folds_from_running_config(tmp_path: Path) -> None:
    cfg = tmp_path / 'subset.json'
    cfg.write_text(json.dumps({
        'targets': [
            {'split_group': 'a'},
            {'split_group': 'a'},
            {'split_group': 'b'},
            {'split_group': 'c'},
        ]
    }, ensure_ascii=False), encoding='utf-8')
    mod._proc_lines = lambda prefix: [f"123 python3 tools/run_idp_3bead_holdout_pipeline.py --config-json {cfg} --out-prefix {prefix}"]
    total = mod._infer_total_folds(str(tmp_path / 'runprefix'), 0)
    assert total == 3

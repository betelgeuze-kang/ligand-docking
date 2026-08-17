#!/usr/bin/env python3
"""Apply the one-line D1 manifest type hardening on the exact known base."""

from __future__ import annotations

from pathlib import Path
import subprocess

EXPECTED_BLOB = "59fa587f2aee0950c2379003cce181dc100745d4"
OLD = '''        result.append(
            (
                _case_id(row["case_id"], name=f"manifest case {index}"),
                str(row["result_path"]),
            )
        )
'''
NEW = '''        result_path = row["result_path"]
        if type(result_path) is not str or not result_path:
            raise D1DevelopmentError(
                f"manifest row {index} result_path must be a non-empty string"
            )
        result.append(
            (
                _case_id(row["case_id"], name=f"manifest case {index}"),
                result_path,
            )
        )
'''


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "tools/run_engine_v2_d1_development_v1.py"
    observed = subprocess.check_output(
        ["git", "hash-object", str(path)], text=True
    ).strip()
    if observed != EXPECTED_BLOB:
        raise SystemExit(
            f"D1 runner base drift: expected {EXPECTED_BLOB}, observed {observed}"
        )
    text = path.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise SystemExit("D1 manifest patch context is not unique")
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied exact D1 result_path type hardening")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

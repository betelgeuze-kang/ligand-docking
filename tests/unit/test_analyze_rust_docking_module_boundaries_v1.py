from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "module_boundaries", ROOT / "tools/analyze_rust_docking_module_boundaries_v1.py"
)
assert SPEC is not None and SPEC.loader is not None
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_detects_common_top_level_rust_items(tmp_path: Path) -> None:
    source = tmp_path / "docking.rs"
    source.write_text(
        """
pub(crate) struct PreparedInputV1 {}
pub enum ScorerStatus { Ok }
const CANDIDATE_COUNT: usize = 64;
pub unsafe extern \"C\" fn as_raw_descriptor() {}
fn stable_rank() {}
impl PreparedInputV1 {}
    fn nested_method() {}
""".lstrip(),
        encoding="utf-8",
    )
    report = M.analyze(source)
    names = {
        item["name"]
        for items in report["groups"].values()
        for item in items
    }
    assert {
        "PreparedInputV1",
        "ScorerStatus",
        "CANDIDATE_COUNT",
        "as_raw_descriptor",
        "stable_rank",
        "PreparedInputV1",
    } <= names
    assert "nested_method" not in names
    assert report["top_level_item_count"] == 6
    assert report["authority"]["abi_change_authorized"] is False

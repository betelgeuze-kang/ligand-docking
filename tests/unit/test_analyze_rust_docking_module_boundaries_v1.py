from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "analyze_rust_docking_module_boundaries_v1",
    ROOT / "tools/analyze_rust_docking_module_boundaries_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
ANALYZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYZER)


def test_default_path_tracks_physical_module_root() -> None:
    assert ANALYZER.DEFAULT_DOCKING_SOURCE == Path(
        "rust/betelgeuze-runtime/src/docking/mod.rs"
    )
    assert (ROOT / ANALYZER.DEFAULT_DOCKING_SOURCE).is_file()


def test_classifies_top_level_items_without_authority(tmp_path: Path) -> None:
    path = tmp_path / "docking.rs"
    path.write_text(
        """
pub struct PreparedDockingInput {}
struct GeometricAdmissionReceipt {}
fn score_candidate() {}
const MAX_CANDIDATES: usize = 64;
impl PreparedDockingInput {}
""",
        encoding="utf-8",
    )
    report = ANALYZER.analyze(path)
    assert report["top_level_item_count"] == 5
    assert report["groups"]["prepared_input"][0]["public"] is True
    assert report["groups"]["admission"][0]["name"] == "GeometricAdmissionReceipt"
    assert report["authority"]["abi_change_authorized"] is False
    assert report["authority"]["scientific_change_authorized"] is False

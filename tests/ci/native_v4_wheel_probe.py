"""Prepare and check a bounded installed-wheel native-v4 comparison probe.

Preparation reuses checkout test fixtures. Checking runs with isolated Python
outside the checkout and imports the product only from the installed wheel.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def prepare(root: Path) -> None:
    from betelgeuze_product import installed_synthetic_comparison as comparison
    from tests.unit.test_installed_native_v4_comparison import (
        _linked_protocol, _two_linked_protocol, bounded_source,
    )

    root.mkdir(parents=True)
    bounded = bounded_source.__wrapped__(root)
    linked, _, candidate = _linked_protocol(bounded, root)
    assert linked["schema_version"] == comparison.NATIVE_PROTOCOL_V2
    assert linked["requests"][candidate] is not None
    unlinked_root = root / "unlinked-source"
    unlinked_root.mkdir()
    unlinked_bounded = bounded_source.__wrapped__(unlinked_root)
    unlinked = copy.deepcopy(linked)
    unlinked["source"] = unlinked_bounded[2]
    assert unlinked["requests"][candidate] == linked["requests"][candidate]
    _write(root / "linked-protocol.json", linked)
    _write(root / "unlinked-protocol.json", unlinked)
    _write(root / "source-reference.json", linked["source"])
    _write(root / "probe.json", {"candidate": candidate})
    two_root = root / "two-candidate"
    two_root.mkdir()
    _write(root / "two-linked-draft.json", _two_linked_protocol(
        two_root, sd_value="SYNTHETIC_PRIVATE_SD_VALUE_DO_NOT_EXPORT",
    ))


def check(root: Path) -> None:
    assert sys.prefix != sys.base_prefix, "wheel probe requires a fresh venv"
    assert importlib.util.find_spec("tools") is None, "checkout tools are importable"

    import betelgeuze_product

    package_path = Path(betelgeuze_product.__file__).resolve()
    assert package_path.is_relative_to(Path(sys.prefix).resolve())
    assert "site-packages" in package_path.parts
    config = (Path(sys.prefix) / "pyvenv.cfg").read_text().lower()
    assert "include-system-site-packages = false" in config

    source = _read(root / "source-verification.json")
    assert source["requested_metadata_rows"] == 7
    assert source["assigned_role_counts"] == {
        "fit": 6, "calibration": 0, "development_test": 1,
    }
    assert source["evaluation_labels_read"] == 0
    assert source["source_authenticated"] is False
    assert source["scientifically_validated"] is False
    assert Path(source["implementation_runtime"]["implementation_root"]).resolve() == package_path.parent

    run = _read(root / "run.json")
    verify = _read(root / "verify.json")
    resume = _read(root / "resume.json")
    assert run["status"] == resume["status"] == "committed"
    assert run == resume
    assert verify["status"] == "verified"
    assert verify["exit_code"] == 0

    candidate = _read(root / "probe.json")["candidate"]
    result = _read(root / "linked-run" / "comparison.json")
    assert result["schema_version"] == "installed_native_v4_fit_prepared_comparison_result_v2"
    assert result["candidate_prepared_identity_bound"] == {candidate: True}
    assert result["same_prepared_assay_state_verified"] is False
    assert result["scientifically_validated"] is False
    assert result["evaluation_labels_read"] == 0
    assert result["arms"]["engine"]["worker_complete"]["engine_calls"] == 1

    assert not (root / "unlinked-run").exists()
    assert "native_prepared_source_link_missing" in (root / "unlinked.stderr").read_text()

    preflight = _read(root / "two-linked-preflight.json")
    assert preflight["status"] == "ready"
    assert preflight["candidate_count"] == 2
    assert preflight["distinct_Ki_chemical_identity_count"] == 2
    assert preflight["blockers"] == []
    assert preflight["evaluation_labels_read"] == 0
    assert preflight["scientifically_validated"] is False
    assert _read(root / "two-linked-protocol.json") == _read(root / "two-linked-draft.json")
    two_run = _read(root / "two-linked-run.json")
    two_verify = _read(root / "two-linked-verify.json")
    two_resume = _read(root / "two-linked-resume.json")
    assert two_run == two_resume
    assert two_run["status"] == "committed"
    assert two_verify["status"] == "verified"
    two_result = _read(root / "two-linked-run" / "comparison.json")
    assert len(two_result["pool"]) == 2
    for arm in ("similarity", "engine", "ai_engine", "similarity_engine"):
        assert two_result["arms"][arm]["denominator"] == {
            "requested": 2, "evaluated": 2,
        }
    sentinel = "SYNTHETIC_PRIVATE_SD_VALUE_DO_NOT_EXPORT"
    pose_reports = list((root / "two-linked-run").rglob("*.poses.json"))
    assert pose_reports
    for path in pose_reports:
        assert sentinel not in path.read_text(encoding="utf-8")
    blocked = _read(root / "one-linked-preflight.json")
    assert blocked["status"] == "blocked"
    assert "two_distinct_Ki_chemical_identities_required" in {
        item["code"] for item in blocked["blockers"]
    }
    assert not (root / "one-linked-must-not-exist.json").exists()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.root)
    else:
        check(args.root)


if __name__ == "__main__":
    main()

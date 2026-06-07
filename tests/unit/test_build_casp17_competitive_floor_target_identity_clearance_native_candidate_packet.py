from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_native_candidate_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "--workorder-json",
        str(tmp_path / "workorder.json"),
        "--current-target-csv",
        str(tmp_path / "current_targets.csv"),
        "--target-watchlist-csv",
        str(tmp_path / "watchlist.csv"),
        "--discovery-json",
        str(tmp_path / "discovery.json"),
        "--out-json",
        str(tmp_path / "native_candidates.json"),
        "--out-csv",
        str(tmp_path / "native_candidates.csv"),
        "--out-md",
        str(tmp_path / "NATIVE_CANDIDATES.md"),
        *extra,
    ]


def _fixture(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "workorder.json",
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [
                {"target_id": "H1001", "target_name": "Example spike - antibody 7C8 complex"},
                {"target_id": "H1002", "target_name": "Rare T Cell Receptor N17.2, complex (5 chains)"},
            ],
        },
    )
    _write_csv(
        tmp_path / "current_targets.csv",
        [
            {
                "target_id": "H2001",
                "protein_name": "Example spike - antibody 7C8 complex",
                "folder_status": "ready",
            }
        ],
    )
    _write_csv(
        tmp_path / "watchlist.csv",
        [
            {"target_id": "H1001", "entry_date": "2026-05-01", "qa_expiration": "2026-05-10"},
            {"target_id": "H1002", "entry_date": "2026-05-02", "qa_expiration": "2026-05-11"},
        ],
    )
    _write_json(tmp_path / "discovery.json", {"summary": {"target_identity_discovery_status": "review_required"}})


def test_native_candidate_packet_prepares_queries_without_fetch(tmp_path: Path) -> None:
    _fixture(tmp_path)
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["native_candidate_packet_status"] == "search_prepared"
    assert payload["summary"]["search_prepared_count"] == 2
    assert payload["summary"]["current_target_collision_count"] == 1
    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert by_id["H1001"]["candidate_status"] == "search_prepared"
    assert by_id["H1001"]["current_target_collision_ids"] == "H2001"
    assert "rcsb_fetch_not_enabled" in by_id["H1002"]["blockers"]
    assert (tmp_path / "NATIVE_CANDIDATES.md").is_file()


def test_native_candidate_packet_fetches_and_blocks_collision(monkeypatch, tmp_path: Path) -> None:
    _fixture(tmp_path)

    def fake_search(query_text: str, *, rows: int, timeout_seconds: int) -> list[dict]:
        if "Rare T Cell Receptor N17.2" in query_text:
            return []
        return [{"identifier": "1ABC", "score": 0.99}]

    def fake_entry(pdb_id: str, *, timeout_seconds: int) -> dict:
        return {
            "struct": {"title": "Example spike antibody reference"},
            "rcsb_accession_info": {"initial_release_date": "2027-01-01T00:00:00+00:00"},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_entry_info": {"resolution_combined": [2.1]},
        }

    monkeypatch.setattr(mod, "_rcsb_search", fake_search)
    monkeypatch.setattr(mod, "_rcsb_entry", fake_entry)
    args = mod.parse_args(_args(tmp_path, "--fetch-rcsb"))

    payload = mod.build_payload(args)

    assert payload["summary"]["native_candidate_packet_status"] == "review_required"
    assert payload["summary"]["blocked_candidate_count"] >= 1
    assert payload["summary"]["no_candidate_target_count"] == 1
    h1001_rows = [row for row in payload["rows"] if row["target_id"] == "H1001"]
    assert h1001_rows
    assert h1001_rows[0]["candidate_status"] == "blocked_current_target_collision"
    assert h1001_rows[0]["pdb_id"] == "1ABC"
    assert "current_target_name_collision" in h1001_rows[0]["blockers"]
    h1002 = [row for row in payload["rows"] if row["target_id"] == "H1002"][0]
    assert h1002["candidate_status"] == "no_rcsb_candidate_found"

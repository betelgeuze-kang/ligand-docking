from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--source-route-board-json",
        str(tmp_path / "source_route.json"),
        "--archive-source-json",
        str(tmp_path / "sources.json"),
        "--source-dir",
        str(tmp_path / "source_candidates"),
        "--max-candidates-per-source",
        "2",
        "--no-check-native-pdb-downloads",
        "--out-json",
        str(tmp_path / "official_sources.json"),
        "--out-csv",
        str(tmp_path / "official_sources.csv"),
        "--out-md",
        str(tmp_path / "OFFICIAL_SOURCES.md"),
    ]


def _write_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "source_route.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_source_route_board_status": (
                    "first_slot_requires_pre_native_monomer_source_or_replacement"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
            }
        },
    )
    (tmp_path / "casp16_regular.html").write_text(
        """
<tr><td><a href="T0208s1.tar.gz">T0208s1.tar.gz</a></td><td align="right">2024-05-21 09:20  </td><td align="right"> 18M</td></tr>
<tr><td><a href="T0206.tar.gz">T0206.tar.gz</a></td><td align="right">2024-05-23 20:09  </td><td align="right"> 12M</td></tr>
<tr><td><a href="H0208.tar.gz">H0208.tar.gz</a></td><td align="right">2024-05-21 09:20  </td><td align="right"> 42M</td></tr>
""",
        encoding="utf-8",
    )
    (tmp_path / "casp16_targets.html").write_text(
        """
<tr class=datarow><td>1.</td><td><a href="target.cgi?id=62&view=all">T0206</a></td><td>Prot</td><td>237</td><td>UNK</td><td>2024-05-06</td><td>2024-05-09</td><td>2024-05-20</td><td>2024-05-20</td><td class="table_row_right">Porcine astrovirus 4 capsid spike<br>PDB code <a href="https://www.rcsb.org/structure/9abc">9abc</a></td></tr>
<tr class=datarow><td>2.</td><td><a href="target.cgi?id=63&view=all">T0208s1</a></td><td>Prot</td><td>328</td><td>A1</td><td>2024-05-07</td><td>2024-05-10</td><td>2024-05-21</td><td>2024-05-21</td><td class="table_row_right">dahAB<br><em>subunit 1</em></td></tr>
""",
        encoding="utf-8",
    )
    (tmp_path / "casp15_regular.html").write_text(
        """
<tr><td><a href="T1104.tar.gz">T1104.tar.gz</a></td><td align="right">2022-05-24 07:50  </td><td align="right">6.4M</td></tr>
<tr><td><a href="T1105v1.tar.gz">T1105v1.tar.gz</a></td><td align="right">2022-05-25 07:50  </td><td align="right">8.5M</td></tr>
""",
        encoding="utf-8",
    )
    (tmp_path / "casp15_targets.html").write_text(
        """
<tr class=datarow><td>1.</td><td><a href="target.cgi?id=28&view=all">T1104</a></td><td>All groups</td><td>117</td><td>A1</td><td>2022-05-02</td><td>2022-05-05</td><td>2022-05-23</td><td class="table_row_right">EntV136<br>PDB code <a href="https://www.rcsb.org/structure/7roa">7roa</a></td></tr>
<tr class=datarow><td>2.</td><td><a href="target.cgi?id=29&view=all">T1105v1</a></td><td>Server /Ligand</td><td>331</td><td>A1</td><td>2022-05-06</td><td>2022-05-09</td><td>2022-05-24</td><td class="table_row_right">Queuine salvage enzyme DUF2419</td></tr>
""",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "sources.json",
        {
            "sources": [
                {
                    "source_id": "casp16_regular_predictions",
                    "competition": "CASP16",
                    "prediction_index_path": str(tmp_path / "casp16_regular.html"),
                    "prediction_index_url": "https://predictioncenter.org/download_area/CASP16/predictions/regular/",
                    "targetlist_path": str(tmp_path / "casp16_targets.html"),
                    "targetlist_url": "https://predictioncenter.org/casp16/targetlist.cgi?view_targets=all",
                    "native_public_anchor_url": "https://predictioncenter.org/download_area/CASP16/targets/",
                    "native_public_anchor_date": "2025-02-01",
                },
                {
                    "source_id": "casp15_regular_predictions",
                    "competition": "CASP15",
                    "prediction_index_path": str(tmp_path / "casp15_regular.html"),
                    "prediction_index_url": "https://predictioncenter.org/download_area/CASP15/predictions/regular/",
                    "targetlist_path": str(tmp_path / "casp15_targets.html"),
                    "targetlist_url": "https://predictioncenter.org/casp15/targetlist.cgi?view_targets=all",
                    "native_public_anchor_url": "https://predictioncenter.org/download_area/CASP15/targets/",
                    "native_public_anchor_date": "2022-12-20",
                },
            ]
        },
    )


def test_official_archive_source_candidates_parse_pre_native_monomer_archives(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_first_slot_official_archive_source_candidates_status"] == (
        "first_slot_official_archive_native_authority_candidates_available"
    )
    assert summary["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert summary["source_count"] == 2
    assert summary["candidate_count"] == 4
    assert summary["pre_native_candidate_count"] == 4
    assert summary["ready_candidate_count"] == 2
    assert summary["blocked_candidate_count"] == 2
    assert summary["native_authority_ready_count"] == 2
    assert summary["native_authority_lookup_required_count"] == 2
    assert summary["native_pdb_download_ready_count"] == 0
    assert summary["native_mmcif_only_count"] == 0
    assert summary["targetlist_metadata_present_count"] == 4
    assert summary["regular_monomer_count"] == 2
    assert summary["domain_subunit_count"] == 1
    assert summary["variant_count"] == 1
    assert summary["first_ready_competition"] == "CASP16"
    assert summary["first_ready_target_id"] == "T0206"
    assert summary["first_ready_native_pdb_code"] == "9abc"
    assert summary["first_ready_native_pdb_download_status"] == "not_checked"
    assert "prediction_pdb=extract_from:" in summary["first_ready_operator_value_preview"]
    assert "native_pdb=fetch_from:https://files.rcsb.org/download/9ABC.pdb" in summary["first_ready_operator_value_preview"]

    rows = payload["rows"]
    assert rows[0]["prediction_tarball_url"].endswith("T0206.tar.gz")
    assert rows[0]["pre_native_by_archive_timing"] == "True"
    assert rows[0]["source_category"] == "regular_monomer"
    assert rows[0]["candidate_status"] == "pre_native_archive_candidate_native_authority_ready_for_download"
    assert rows[0]["native_authority_status"] == "native_pdb_code_present"
    assert rows[0]["native_pdb_download_status"] == "not_checked"

    written_rows = _read_csv(tmp_path / "official_sources.csv")
    assert len(written_rows) == 4
    assert (tmp_path / "source_candidates" / "001_casp16_t0206" / "SOURCE_CANDIDATE.md").is_file()
    assert (tmp_path / "OFFICIAL_SOURCES.md").read_text(encoding="utf-8").startswith("# CASP17")


def test_official_archive_source_candidates_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_official_archive_source_candidates_status"] == (
        "blocked_official_archive_index_unavailable"
    )
    assert "first_slot_source_route_board_json_missing" in payload["summary"]["input_blockers"]
    assert "archive_source_config_missing" in payload["summary"]["input_blockers"]

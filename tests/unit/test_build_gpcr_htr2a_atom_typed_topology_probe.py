from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_htr2a_atom_typed_topology_probe as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_probe_separates_current_htr2a_slice_diagnostic_only(tmp_path: Path) -> None:
    repair_rows = tmp_path / "repair_rows.csv"
    stage3 = tmp_path / "stage3.csv"
    _write_csv(
        repair_rows,
        [
            {
                "target_rank": 1,
                "row_role": "decoy_above_positive",
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "decoy_1",
                "exact_anchor_signature_matches_positive": "True",
                "generic_anchor_signature_matches_positive": "True",
            },
            {
                "target_rank": 2,
                "row_role": "positive",
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "exact_anchor_signature_matches_positive": "True",
                "generic_anchor_signature_matches_positive": "True",
            },
        ],
    )
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "decoy_1",
                "ligand_smiles": "CNCC1CC=CN=CC=C2CCC2C1S(N)(=O)=O",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "ligand_smiles": "O=S1(=O)c2cccc3cccc(c23)N1CCCN1CCN(c2ccc(F)cc2)CC1",
            },
        ],
    )

    payload, rows = mod.build_probe(
        repair_rows_csv=repair_rows,
        stage3_scores_csv=stage3,
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    positive = next(row for row in rows if row["row_role"] == "positive")
    decoy = next(row for row in rows if row["row_role"] == "decoy_above_positive")
    assert summary["status"] == "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only"
    assert summary["claim_promotion_allowed"] is False
    assert summary["positive_topology_probe_support"] == 1.0
    assert summary["max_decoy_topology_probe_support"] == 0.0
    assert summary["decoy_support_positive_or_higher_count"] == 0
    assert positive["topology_probe_support"] == 1.0
    assert decoy["topology_probe_support"] == 0.0
    assert payload["feature_contract"]["requires_replay_before_apply"] is True


def test_build_probe_cli_writes_outputs(tmp_path: Path) -> None:
    repair_rows = tmp_path / "repair_rows.csv"
    stage3 = tmp_path / "stage3.csv"
    out_json = tmp_path / "probe.json"
    out_csv = tmp_path / "probe.csv"
    out_md = tmp_path / "probe.md"
    _write_csv(
        repair_rows,
        [
            {
                "target_rank": 1,
                "row_role": "positive",
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "exact_anchor_signature_matches_positive": "True",
                "generic_anchor_signature_matches_positive": "True",
            }
        ],
    )
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "ligand_smiles": "O=S1(=O)c2cccc3cccc(c23)N1CCCN1CCN(c2ccc(F)cc2)CC1",
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_htr2a_atom_typed_topology_probe.py"),
            "--repair-rows-csv",
            str(repair_rows),
            "--stage3-scores-csv",
            str(stage3),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["positive_topology_probe_support"] == 1.0
    assert "GPCR HTR2A Atom-Typed Topology Probe" in out_md.read_text(encoding="utf-8")
    assert "topology_probe_support" in out_csv.read_text(encoding="utf-8")

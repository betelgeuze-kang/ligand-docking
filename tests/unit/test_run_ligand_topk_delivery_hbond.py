from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from betelgeuze_engine.product.runners import topk_delivery as mod


def test_topk_delivery_embeds_child_hbond_evidence_for_parent_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scores_csv = tmp_path / "scores.csv"
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame(
        [
            {
                "queue_id": "ADRB2__lig1__rep0001",
                "target": "ADRB2",
                "ligand_id": "lig1",
                "binding_score_composite_v7": -8.0,
            }
        ]
    ).to_csv(scores_csv, index=False)
    pd.DataFrame(
        [
            {
                "queue_id": "ADRB2__lig1__rep0001",
                "target": "ADRB2",
                "ligand_id": "lig1",
                "ligand_smiles": "CCO",
            }
        ]
    ).to_csv(queue_csv, index=False)

    out_prefix = tmp_path / "topk"
    child_summary_path = tmp_path / "topk_delivery_summary.json"
    hbond_evidence = {
        "schema_version": "hbond_evidence_v1",
        "status": "pass",
        "claim_safe": True,
        "blocked_reason": "",
        "site_count": 1,
        "donor_site_count": 0,
        "acceptor_site_count": 1,
        "donor_acceptor_pairs": [
            {
                "site_index": 0,
                "atom_idx": 2,
                "element": "O",
                "role": "acceptor",
                "nearest_distance": 2.9,
                "distance_pass": True,
                "angle_score": 0.7,
                "angle_pass": True,
            }
        ],
        "hbond_confidence": 0.8,
        "unsatisfied_donor_count": 0,
        "unsatisfied_acceptor_count": 0,
        "overanchoring_flag": False,
    }
    child_summary = {
        "hbond_evidence_summary": {
            "schema_version": "hbond_evidence_v1",
            "status": "pass",
            "evaluated_row_count": 1,
        },
        "topk": [
            {
                "queue_id": "ADRB2__lig1__rep0001",
                "target": "ADRB2",
                "ligand_id": "lig1",
                "ligand_smiles": "CCO",
                "hbond_evidence": hbond_evidence,
            }
        ],
    }

    def _fake_run(_cmd):
        child_summary_path.write_text(
            json.dumps(child_summary, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"ok": True, "returncode": 0, "cmd": [], "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(mod, "_run", _fake_run)
    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--queue-csv",
            str(queue_csv),
            "--trajectory-root",
            str(tmp_path / "trajectories"),
            "--out-prefix",
            str(out_prefix),
            "--score-col",
            "binding_score_composite_v7",
            "--score-direction",
            "ascending",
            "--topk-global",
            "1",
            "--topk-per-target",
            "0",
            "--selection-mode",
            "global_only",
            "--no-make-bundle-zip",
        ]
    )

    payload = mod.build_delivery(args)

    assert payload["hbond_evidence_summary"] == child_summary["hbond_evidence_summary"]
    assert payload["hbond_evidence_candidates"] == child_summary["topk"]
    assert payload["hbond_evidence_source"]["source_kind"] == (
        "topk_delivery_backmapping_result"
    )
    assert payload["hbond_evidence_source"]["result_file_sha256"] == hashlib.sha256(
        child_summary_path.read_bytes()
    ).hexdigest()

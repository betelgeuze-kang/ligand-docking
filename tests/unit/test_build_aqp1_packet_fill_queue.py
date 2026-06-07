from __future__ import annotations

from pathlib import Path

from tools.product import build_aqp1_packet_fill_queue as mod


def test_build_aqp1_packet_fill_queue(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "ligand_binding_reference_blind_aqp1_v1.csv").write_text(
        "target,ligand_id,reference_binding_kcal_mol,is_binder,source\n"
        "AQP1_TRANSPORT_BLIND,aqp1_placeholder_binder_01,-8.0,1,template_placeholder_needs_curation\n"
        "AQP1_TRANSPORT_BLIND,aqp1_placeholder_nonbinder_01,-0.8,0,template_placeholder_needs_curation\n",
        encoding="utf-8",
    )
    (config / "ligand_eval_splits_blind_aqp1_v1.csv").write_text(
        "target,ligand_id,role\n"
        "AQP1_TRANSPORT_BLIND,aqp1_placeholder_binder_01,far_ood_eval\n"
        "AQP1_TRANSPORT_BLIND,aqp1_placeholder_nonbinder_01,far_ood_eval\n",
        encoding="utf-8",
    )
    (config / "ligand_meta_blind_aqp1_v1.csv").write_text(
        "ligand_id,smiles,molecular_weight,logp,h_donors,h_acceptors,rot_bonds,scaffold\n"
        "aqp1_placeholder_binder_01,O,18.0,-1.4,0,0,0,template_placeholder\n"
        "aqp1_placeholder_nonbinder_01,c1ccccc1,78.1,2.1,0,0,0,template_placeholder\n",
        encoding="utf-8",
    )
    mod.ROOT = tmp_path
    monkeypatch.chdir(tmp_path)
    payload = mod.build_payload()
    assert payload["summary"]["queue_count"] == 2
    assert payload["summary"]["binder_slots"] == 1
    assert payload["summary"]["non_binder_slots"] == 1
    assert payload["queue_rows"][0]["packet"] == "core"
    assert payload["queue_rows"][0]["curation_status"] == "pending_replacement"

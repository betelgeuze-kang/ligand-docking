from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_glut1_second_wave_source_confirmation_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_glut1_second_wave_source_confirmation_packet_reads_current_artifacts() -> None:
    payload = mod.build_payload(
        json.loads((ROOT / "runs/transporter_seed_row_promotion_board_current.json").read_text(encoding="utf-8"))
    )

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}

    assert summary["status"] == "glut1_second_wave_source_confirmation_packet_ready"
    assert summary["row_count"] == 3
    assert summary["primary_focus_ligand"] == "cytochalasin B"
    assert summary["primary_confirmation_target"] == "core_binder_01"
    assert summary["primary_anchor_pmid"] == "1716731"
    assert summary["second_wave_targets"] == "core_binder_01, core_binder_02, core_binder_03"
    assert summary["canonical_target_gene"] == "SLC2A1"
    assert summary["canonical_target_alias"] == "GLUT1"
    assert summary["canonical_target_uniprot"] == "P11166"
    assert summary["canonical_target_chembl_id"] == "CHEMBL2535"
    assert summary["direct_quantitative_binding_count"] == 1
    assert summary["exact_target_pair_activity_count"] == 2
    assert summary["structured_pair_absent_count"] == 1
    assert summary["apparent_functional_affinity_count"] == 1
    assert summary["source_anchor_pmid_count"] == 3
    assert summary["claim_safe_kcal_ready_count"] == 0
    _contains_tokens(
        summary["next_required_step"],
        "aqp1",
        "cytochalasin b",
        "wzb117",
        "stf-31",
        "replacement_reference_binding_kcal_mol",
        "blank",
        "apparent functional affinity",
    )

    row_01 = rows["core_binder_01"]
    assert row_01["candidate_name"] == "cytochalasin B"
    assert row_01["confirmation_scope"] == "direct_quantitative_binding_source_confirmation"
    assert row_01["source_anchor"] == "PMID 1716731"
    assert row_01["source_anchor_pmid"] == "1716731"
    assert row_01["public_provenance_status"] == "exact_human_glut1_direct_binding_present_no_kcal"
    assert row_01["chembl_molecule_chembl_id"] == "CHEMBL411729"
    assert row_01["chembl_target_chembl_id"] == "CHEMBL2535"
    assert row_01["chembl_activity_record_count"] == 2
    assert row_01["direct_binding_measure"] == "Kd=190 nM"
    _contains_tokens(row_01["acceptance_gate"], "direct quantitative binding", "blank")
    _contains_tokens(row_01["rejection_gate"], "claim-safe kcal", "authoritative apply")

    row_02 = rows["core_binder_02"]
    assert row_02["candidate_name"] == "WZB117"
    assert row_02["confirmation_scope"] == "exact_target_pair_activity_source_confirmation"
    assert row_02["source_anchor"] == "PMID 27836974"
    assert row_02["source_anchor_pmid"] == "27836974"
    assert row_02["public_provenance_status"] == "exact_human_glut1_activity_present_nonbinding"
    assert row_02["chembl_molecule_chembl_id"] == "CHEMBL3092944"
    assert row_02["chembl_activity_record_count"] == 3
    _contains_tokens(row_02["representative_activity"], "10.9", "6.2 uM")
    assert row_02["apparent_affinity_measure"] == "Ki(app)=6.2 uM"
    assert row_02["apparent_delta_g_298k_kcal_mol"] == "-7.1045"
    assert row_02["claim_safe_binding_kcal_ready"] == "no"
    _contains_tokens(row_02["rejection_gate"], "binder", "direct binding")

    row_03 = rows["core_binder_03"]
    assert row_03["candidate_name"] == "STF-31"
    assert row_03["confirmation_scope"] == "literature_direct_binding_claim_source_confirmation"
    assert row_03["source_anchor"] == "PMID 21813754"
    assert row_03["source_anchor_pmid"] == "21813754"
    assert row_03["public_provenance_status"] == "human_glut1_functional_anchor_direct_binding_claim_structured_pair_absent"
    assert row_03["chembl_activity_record_count"] == 0
    _contains_tokens(row_03["supportive_pmids"], "25058389", "29949049")
    _contains_tokens(row_03["rejection_gate"], "binding constant", "nampt")


def test_build_glut1_second_wave_source_confirmation_packet_cli(tmp_path: Path) -> None:
    out_json = tmp_path / "glut1_second_wave_source_confirmation_packet.json"
    out_csv = tmp_path / "glut1_second_wave_source_confirmation_packet.csv"
    out_md = tmp_path / "glut1_second_wave_source_confirmation_packet.md"

    subprocess.run(
        [
            sys.executable,
            "tools/build_glut1_second_wave_source_confirmation_packet.py",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "glut1_second_wave_source_confirmation_packet_ready"
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["primary_anchor_pmid"] == "1716731"
    assert payload["summary"]["source_anchor_pmid_count"] == 3
    assert payload["rows"][0]["packet_step"] == "core_binder_01"
    assert payload["rows"][2]["packet_step"] == "core_binder_03"
    assert out_csv.read_text(encoding="utf-8").splitlines()[0].startswith("confirmation_rank,")
    assert out_md.read_text(encoding="utf-8").startswith("# GLUT1 Second-Wave Source Confirmation Packet")

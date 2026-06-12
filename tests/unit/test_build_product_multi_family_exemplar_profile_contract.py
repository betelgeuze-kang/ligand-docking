from __future__ import annotations

from tools.product.build_product_multi_family_exemplar_profile_contract import build_contract


def test_multi_family_exemplar_contract_ready() -> None:
    payload = build_contract()
    summary = payload["summary"]
    assert summary["exemplar_count"] == 3
    assert summary["ready_exemplar_count"] == 3
    assert summary["status"] == "product_multi_family_exemplar_profile_contract_ready"
    families = {row["family"]: row for row in payload["rows"]}
    assert families["gpcr"]["bundle_tag"] == "product_gpcr_adrb2"
    assert families["kinase"]["bundle_tag"] == "product_kinase_egfr"
    assert families["ion_channel"]["bundle_tag"] == "product_ion_channel_trpv1"
    assert all(row["execution_command"].startswith("python3 tools/run_ligand_htvs_pipeline.py") for row in payload["rows"])

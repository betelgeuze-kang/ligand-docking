from __future__ import annotations

from tools import build_wetlab_priority3_repurposing_seed_pool as mod


def test_build_wetlab_priority3_repurposing_seed_pool() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_priority3_repurposing_seed_pool_ready"
    assert summary["target_count"] == 3
    assert summary["row_count"] == 9

    by_target = {}
    for row in rows:
        by_target.setdefault(row["target_id"], []).append(row)

    assert [row["compound_name"] for row in by_target["T. cruzi PDE"]] == ["Dipyridamole", "Sildenafil", "Tadalafil"]
    assert [row["compound_name"] for row in by_target["CA IX"]] == ["Acetazolamide", "Methazolamide", "Dichlorphenamide"]
    assert [row["compound_name"] for row in by_target["SARS-CoV-2 Mpro"]] == ["Nirmatrelvir", "Boceprevir", "Telaprevir"]
    assert by_target["SARS-CoV-2 Mpro"][0]["compound_role"] == "current clinical Mpro benchmark"

from __future__ import annotations

from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_priority3_repurposing_fill_map as mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod


def test_build_wetlab_priority3_repurposing_fill_map() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())

    payload = mod.build_payload(seed_mod.build_payload(), fill_queue, queue)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_priority3_repurposing_fill_map_ready"
    assert summary["priority_target_count"] == 3
    assert summary["seed_row_count"] == 9
    assert summary["bulk_override_target_count"] == 0

    by_target = {}
    for row in rows:
        by_target.setdefault(row["target_id"], []).append(row)

    tcruzi = by_target["T. cruzi PDE"]
    assert tcruzi[0]["first_contact_use_mode"] == "proceed_now"
    assert tcruzi[1]["first_contact_use_mode"] == "comparator_only"

    caix = by_target["CA IX"]
    assert all(row["first_contact_use_mode"] == "benchmark_control" for row in caix)

    mpro = by_target["SARS-CoV-2 Mpro"]
    assert mpro[0]["cost_check_required"] is True
    assert mpro[1]["first_contact_use_mode"] == "proceed_now"


def test_build_wetlab_priority3_repurposing_fill_map_prefers_bulk_override_when_present() -> None:
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    fill_queue = fill_queue_mod.build_payload(queue, schema_mod.build_payload())
    bulk_autofill = {
        "rows": [
            {
                "target_id": "CA IX",
                "compound_name": "BulkCandidateA",
                "bulk_rank": 1,
                "bulk_score": 9.1,
            },
            {
                "target_id": "CA IX",
                "compound_name": "BulkCandidateB",
                "bulk_rank": 2,
                "bulk_score": 8.4,
            },
            {
                "target_id": "CA IX",
                "compound_name": "BulkCandidateC",
                "bulk_rank": 3,
                "bulk_score": 7.7,
            },
        ]
    }

    payload = mod.build_payload(seed_mod.build_payload(), fill_queue, queue, bulk_autofill)
    summary = payload["summary"]
    caix_rows = [row for row in payload["rows"] if row["target_id"] == "CA IX"]

    assert summary["bulk_override_target_count"] == 1
    assert [row["compound_name"] for row in caix_rows] == ["BulkCandidateA", "BulkCandidateB", "BulkCandidateC"]
    assert all(row["row_status"] == "bulk_override_ready" for row in caix_rows)

from __future__ import annotations

import json
from pathlib import Path

from tests.unit.test_betelgeuze_product_delivery_evidence import (
    _bundle_contract,
    _engine,
    _environment,
    _local_preflight,
    _nightly,
    _preflight,
    _queue,
    _readiness,
    _requirements,
    _verdict,
    _wetlab,
)
from tools import build_product_delivery_evidence_contract as mod


def test_build_product_delivery_evidence_contract_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "readiness": tmp_path / "readiness.json",
        "preflight": tmp_path / "preflight.json",
        "bundle": tmp_path / "bundle.json",
        "verdict": tmp_path / "verdict.json",
        "local_preflight": tmp_path / "local_preflight.json",
        "environment": tmp_path / "environment.json",
        "requirements": tmp_path / "requirements.json",
        "engine": tmp_path / "engine.json",
        "queue": tmp_path / "queue.json",
        "nightly": tmp_path / "nightly.json",
        "wetlab": tmp_path / "wetlab.json",
    }
    payloads = {
        "readiness": _readiness(),
        "preflight": _preflight(),
        "bundle": _bundle_contract(),
        "verdict": _verdict(),
        "local_preflight": _local_preflight(),
        "environment": _environment(),
        "requirements": _requirements(),
        "engine": _engine(),
        "queue": _queue(),
        "nightly": _nightly(),
        "wetlab": _wetlab(),
    }
    for key, payload in payloads.items():
        paths[key].write_text(json.dumps(payload) + "\n", encoding="utf-8")
    out_json = tmp_path / "delivery_evidence.json"
    out_csv = tmp_path / "delivery_evidence.csv"
    out_md = tmp_path / "delivery_evidence.md"

    mod.main(
        [
            "--product-readiness-json",
            str(paths["readiness"]),
            "--product-preflight-json",
            str(paths["preflight"]),
            "--product-bundle-contract-json",
            str(paths["bundle"]),
            "--local-delivery-verdict-json",
            str(paths["verdict"]),
            "--local-delivery-preflight-json",
            str(paths["local_preflight"]),
            "--environment-manifest-json",
            str(paths["environment"]),
            "--requirements-lock-json",
            str(paths["requirements"]),
            "--engine-provenance-json",
            str(paths["engine"]),
            "--commercialization-queue-json",
            str(paths["queue"]),
            "--nightly-gate-json",
            str(paths["nightly"]),
            "--wetlab-gate-json",
            str(paths["wetlab"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_delivery_evidence_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Delivery Evidence Contract" in out_md.read_text(encoding="utf-8")

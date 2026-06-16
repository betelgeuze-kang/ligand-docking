from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import torch

from betelgeuze_ai_md.contracts import (
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
    TopologyValidityReport,
    build_topology_validity_report,
)
from core.definitions import StrategyType
from core.topology import TopologyFactory


def test_topology_adapter_module_does_not_import_torch() -> None:
    source = importlib.util.find_spec("betelgeuze_ai_md.contracts.topology_adapter")
    assert source is not None
    assert source.origin is not None
    text = Path(source.origin).read_text(encoding="utf-8")
    assert "import torch" not in text
    assert "from torch" not in text


def test_placeholder_metadata_emits_fail_closed_topology_report() -> None:
    report = build_topology_validity_report(
        {
            "topology_fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            "n_res": 4,
        }
    )

    assert isinstance(report, TopologyValidityReport)
    assert report.status == "not_assessed"
    assert report.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert "topology_validity_not_assessed" in report.claim_blockers
    assert "placeholder_topology_fidelity" in report.claim_blockers
    assert report.validity_rows == []


def test_sequence_mapped_metadata_with_coherent_counts_emits_passing_report() -> None:
    report = build_topology_validity_report(
        {
            "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "residue_types_source": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "n_res": 3,
            "residue_types_count": 3,
        }
    )

    assert report.status == "pass"
    assert report.topology_fidelity == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    assert report.claim_blockers == []
    assert any(row.get("check_id") == "residue_count_coherent" for row in report.validity_rows)
    assert any(row.get("check_id") == "topology_fidelity_accounting" for row in report.validity_rows)


def test_sequence_mapped_incoherent_counts_emit_blockers() -> None:
    report = build_topology_validity_report(
        {
            "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "residue_types_source": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "n_res": 4,
            "residue_types_count": 3,
        }
    )

    assert report.status == "fail"
    assert "residue_count_incoherent" in report.claim_blockers


def test_topology_factory_placeholder_is_fail_closed() -> None:
    topo = TopologyFactory(
        n_res=4,
        t_type=1,
        box_size=[10.0, 10.0, 10.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )

    report = build_topology_validity_report(topo)

    assert report.status == "not_assessed"
    assert report.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert "placeholder_topology_fidelity" in report.claim_blockers


def test_topology_factory_sequence_mapped_is_passing_when_coherent() -> None:
    topo = TopologyFactory(
        n_res=3,
        t_type=1,
        box_size=[10.0, 10.0, 10.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )
    topo.set_residue_types_from_sequence(torch.tensor([1, 2, 3], dtype=torch.long))

    report = build_topology_validity_report(topo)

    assert report.status == "pass"
    assert report.topology_fidelity == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    assert report.claim_blockers == []
    assert report.metadata["n_res"] == 3
    assert report.metadata["residue_types_count"] == 3


def test_duck_typed_topology_object_without_torch_tensor() -> None:
    class FakeTopology:
        n_res = 2
        residue_types_source = TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
        claim_metadata = {"topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED}

        def topology_fidelity(self) -> str:
            return TOPOLOGY_FIDELITY_SEQUENCE_MAPPED

        residue_types = [11, 12]

    report = build_topology_validity_report(FakeTopology())

    assert report.status == "pass"
    assert report.claim_blockers == []

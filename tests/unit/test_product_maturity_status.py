"""Four-axis product status contract tests (P0-6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from betelgeuze_product.maturity_status import (
    BENCHMARK_MATURITY_LEVELS,
    MATURITY_STATUS_SCHEMA_VERSION,
    PRODUCT_MATURITY_LEVELS,
    SCIENTIFIC_MATURITY_LEVELS,
    STATUS_AXES,
    MaturityStatus,
    MaturityStatusError,
    parse_maturity_status,
)
from tools.product import build_product_maturity_status as mod


def _status() -> MaturityStatus:
    return MaturityStatus(
        distribution_version="0.3.0rc1",
        scientific_maturity="known_pocket_scaffold",
        benchmark_maturity="evaluator_only",
        product_maturity="restricted_internal",
    )


def test_status_axes_are_the_four_required_axes() -> None:
    assert STATUS_AXES == (
        "distribution_version",
        "scientific_maturity",
        "benchmark_maturity",
        "product_maturity",
    )


def test_receipt_reports_every_axis_separately() -> None:
    receipt = _status().receipt()

    assert receipt["maturity_status_schema_version"] == MATURITY_STATUS_SCHEMA_VERSION
    for axis in STATUS_AXES:
        assert axis in receipt
    assert "overall_maturity" not in receipt
    assert "readiness_score" not in receipt


def test_markdown_lines_render_one_line_per_axis() -> None:
    lines = _status().as_markdown_lines()

    assert len(lines) == len(STATUS_AXES)
    assert lines[0] == "- distribution_version: `0.3.0rc1`"
    assert lines[3] == "- product_maturity: `restricted_internal`"


@pytest.mark.parametrize(
    ("axis", "value"),
    [
        ("scientific_maturity", "bogus"),
        ("benchmark_maturity", "public"),
        ("product_maturity", "shipping"),
    ],
)
def test_undeclared_axis_level_fails_closed(axis: str, value: str) -> None:
    kwargs = {
        "distribution_version": "0.3.0rc1",
        "scientific_maturity": "known_pocket_scaffold",
        "benchmark_maturity": "evaluator_only",
        "product_maturity": "restricted_internal",
    }
    kwargs[axis] = value

    with pytest.raises(MaturityStatusError) as excinfo:
        MaturityStatus(**kwargs)

    assert str(excinfo.value).startswith(f"{axis}_invalid")


def test_blank_distribution_version_fails_closed() -> None:
    with pytest.raises(MaturityStatusError) as excinfo:
        MaturityStatus(
            distribution_version="  ",
            scientific_maturity="known_pocket_scaffold",
            benchmark_maturity="evaluator_only",
            product_maturity="restricted_internal",
        )

    assert str(excinfo.value) == "distribution_version_missing"


def test_parse_reports_every_missing_axis() -> None:
    with pytest.raises(MaturityStatusError) as excinfo:
        parse_maturity_status({"distribution_version": "0.3.0rc1"})

    detail = str(excinfo.value)
    assert detail.startswith("maturity_status_axis_missing:")
    for axis in ("scientific_maturity", "benchmark_maturity", "product_maturity"):
        assert axis in detail


def test_declared_levels_are_ordered_weakest_first() -> None:
    assert SCIENTIFIC_MATURITY_LEVELS[0] == "not_assessed"
    assert SCIENTIFIC_MATURITY_LEVELS[-1] == "prospectively_validated"
    assert BENCHMARK_MATURITY_LEVELS.index("evaluator_only") < BENCHMARK_MATURITY_LEVELS.index(
        "public_frozen_suite"
    )
    assert PRODUCT_MATURITY_LEVELS.index("restricted_internal") < PRODUCT_MATURITY_LEVELS.index(
        "external_beta"
    )


def test_builder_emits_ready_packet_from_source_config(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "summary": {
                    "distribution_version": "0.3.0rc1",
                    "scientific_maturity": "known_pocket_scaffold",
                    "benchmark_maturity": "evaluator_only",
                    "product_maturity": "restricted_internal",
                }
            }
        ),
        encoding="utf-8",
    )

    packet = mod.build_product_maturity_status(source_json=source)
    summary = packet["summary"]

    assert summary["status"] == "product_maturity_status_ready"
    assert summary["axes_reported_separately"] is True
    assert summary["axis_count"] == 4
    assert summary["blocked_checks"] == []
    assert summary["product_maturity"] == "restricted_internal"
    assert summary["external_state_mutated"] is False


def test_builder_blocks_when_source_missing(tmp_path: Path) -> None:
    packet = mod.build_product_maturity_status(source_json=tmp_path / "absent.json")
    summary = packet["summary"]

    assert summary["status"] == "blocked_product_maturity_status"
    assert summary["blocked_checks"] == ["product_maturity_status_source_missing"]


def test_builder_blocks_on_invalid_axis_value(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "distribution_version": "0.3.0rc1",
                "scientific_maturity": "known_pocket_scaffold",
                "benchmark_maturity": "evaluator_only",
                "product_maturity": "generally_available_everywhere",
            }
        ),
        encoding="utf-8",
    )

    packet = mod.build_product_maturity_status(source_json=source)
    summary = packet["summary"]

    assert summary["status"] == "blocked_product_maturity_status"
    assert summary["blocked_checks"] == ["product_maturity_invalid:generally_available_everywhere"]


def test_rendered_markdown_lists_each_axis() -> None:
    packet = mod.build_product_maturity_status(
        source_json="config/product_maturity_status_current.json"
    )
    rendered = mod.render_markdown(packet)

    for axis in STATUS_AXES:
        assert f"- {axis}: " in rendered
    assert "never merged" in rendered


def test_committed_source_config_is_valid() -> None:
    packet = mod.build_product_maturity_status(
        source_json="config/product_maturity_status_current.json"
    )

    assert packet["summary"]["status"] == "product_maturity_status_ready"


def test_status_index_points_at_the_four_axis_packet_as_authoritative() -> None:
    index = (
        Path(__file__).resolve().parents[2] / "docs" / "commercialization_status_summary.md"
    ).read_text(encoding="utf-8")

    assert "docs/PRODUCT_MATURITY_STATUS_CURRENT.md" in index
    assert "runs/product_maturity_status_current.json" in index
    assert "authoritative" in index.lower()
    assert "tools/product/build_product_maturity_status.py" in index
    for axis in STATUS_AXES:
        assert f"`{axis}`" in index


def test_status_index_states_axes_are_not_merged() -> None:
    index = (
        Path(__file__).resolve().parents[2] / "docs" / "commercialization_status_summary.md"
    ).read_text(encoding="utf-8")

    assert "never merged" in index
    assert "does not raise any other axis" in index

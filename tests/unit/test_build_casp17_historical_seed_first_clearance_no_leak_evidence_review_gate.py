from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_first_clearance_no_leak_evidence_review_gate as mod


TEMPLATE_COLUMNS = [
    "field_name",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "required_operator_value_format",
    "evidence_stub_md",
    "notes",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_stub(path: Path, *, filled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = "evidence/no-leak.md" if filled else ""
    operator_value = "2025-01-01" if filled and path.stem == "prediction_created_at" else "tester"
    path.write_text(
        "\n".join(
            [
                f"# Evidence Stub: {path.stem}",
                "",
                "## Operator Evidence",
                "",
                f"- evidence_ref: {suffix}",
                f"- operator_value: {operator_value if filled else ''}",
                f"- operator_clearance: {'clear' if filled else ''}",
                f"- operator_id: {'tester' if filled else ''}",
                "- notes:",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_packet(tmp_path: Path, *, filled: bool) -> Path:
    packet_dir = tmp_path / "packet" / "hist_chignolin"
    template_csv = packet_dir / "operator_evidence_template.csv"
    fields = [
        ("operator", "operator_id", "stable operator id or initials", "tester"),
        ("prediction_created_at", "iso_date", "YYYY-MM-DD", "2025-01-01"),
    ]
    rows = []
    packet_rows = []
    for field_name, policy, required_format, value in fields:
        stub = packet_dir / "field_evidence" / f"{field_name}.md"
        _write_stub(stub, filled=filled)
        rows.append(
            {
                "field_name": field_name,
                "operator_value": value if filled else "",
                "operator_evidence_ref": str(stub),
                "operator_clearance": "clear" if filled else "",
                "operator_id": "tester" if filled else "",
                "required_operator_value_format": required_format,
                "evidence_stub_md": str(stub),
                "notes": "",
            }
        )
        packet_rows.append(
            {
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "field_name": field_name,
                "required_value_policy": policy,
                "required_operator_value_format": required_format,
                "evidence_stub_md": str(stub),
                "packet_status": "awaiting_operator_evidence",
            }
        )
    _write_csv(template_csv, rows)
    packet_json = tmp_path / "packet.json"
    _write_json(
        packet_json,
        {
            "summary": {
                "first_clearance_no_leak_evidence_packet_status": (
                    "first_clearance_no_leak_evidence_packet_ready_for_review"
                    if filled
                    else "awaiting_first_clearance_no_leak_evidence_collection"
                ),
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "packet_folder": str(packet_dir),
                "operator_evidence_template_csv": str(template_csv),
            },
            "rows": packet_rows,
        },
    )
    return packet_json


def _args(tmp_path: Path, packet: Path) -> list[str]:
    return [
        "--evidence-packet-json",
        str(packet),
        "--out-json",
        str(tmp_path / "review.json"),
        "--out-csv",
        str(tmp_path / "review.csv"),
        "--out-md",
        str(tmp_path / "REVIEW.md"),
    ]


def test_evidence_review_gate_blocks_blank_template_and_stubs(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path, filled=False)

    args = mod.parse_args(_args(tmp_path, packet))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_clearance_no_leak_evidence_review_gate_status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert summary["field_count"] == 2
    assert summary["ready_field_count"] == 0
    assert summary["blocked_field_count"] == 2
    assert summary["template_operator_value_missing_count"] == 2
    assert summary["template_operator_clearance_missing_count"] == 2
    assert summary["template_operator_id_missing_count"] == 2
    assert summary["stub_present_count"] == 2
    assert summary["stub_evidence_missing_count"] == 2
    assert summary["policy_blocked_count"] == 2
    assert summary["first_blocked_field"] == "operator"
    assert summary["first_blocker"] == "template_operator_value_missing"
    assert (tmp_path / "review.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "REVIEW.md").read_text(encoding="utf-8")


def test_evidence_review_gate_marks_filled_packet_ready(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path, filled=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, packet)))

    summary = payload["summary"]
    assert summary["first_clearance_no_leak_evidence_review_gate_status"] == (
        "first_clearance_no_leak_evidence_ready_for_operator_fill"
    )
    assert summary["ready_field_count"] == 2
    assert summary["blocked_field_count"] == 0
    assert summary["template_operator_value_missing_count"] == 0
    assert summary["stub_evidence_missing_count"] == 0
    assert summary["policy_pass_count"] == 2
    assert {row["review_gate_status"] for row in payload["rows"]} == {
        "ready_for_no_leak_gate_operator_fill"
    }


def test_evidence_review_gate_blocks_missing_packet(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path, tmp_path / "missing_packet.json")))

    assert payload["summary"]["first_clearance_no_leak_evidence_review_gate_status"] == (
        "blocked_evidence_packet_missing"
    )
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []

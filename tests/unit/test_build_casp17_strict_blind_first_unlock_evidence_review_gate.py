from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_first_unlock_evidence_review_gate as mod


TEMPLATE_COLUMNS = [
    "field_key",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "required_operator_value_format",
    "evidence_stub_md",
    "destination",
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


def _write_stub(path: Path, *, filled: bool, value: str = "internal_run_001") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"# Evidence Stub: {path.stem}",
                "",
                "## Operator Evidence",
                "",
                f"- operator_value: {value if filled else ''}",
                f"- operator_evidence_ref: {'evidence/source.md' if filled else ''}",
                f"- operator_clearance: {'clear' if filled else ''}",
                f"- operator_id: {'operator_a' if filled else ''}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )


def _write_packet(tmp_path: Path, *, filled: bool) -> Path:
    packet_dir = tmp_path / "packet" / "source_request_001_hist_bba5"
    template_csv = packet_dir / "operator_evidence_template.csv"
    pdb_path = tmp_path / "source" / "prediction.pdb"
    if filled:
        _write_pdb(pdb_path)
    fields = [
        ("source_id", "internal_run_001", "internal source id"),
        ("prediction_pdb", str(pdb_path), "local pre-native prediction PDB path"),
        ("prediction_created_at", "2001-01-01", "YYYY-MM-DD prediction creation date"),
        ("operator_clearance", "clear", "approved/clear/cleared/true/yes/operator_clear/operator_approved"),
    ]
    template_rows = []
    packet_rows = []
    for order, (field_key, value, required_format) in enumerate(fields, start=1):
        stub = packet_dir / "field_evidence" / f"{field_key}.md"
        _write_stub(stub, filled=filled, value=value)
        template_rows.append(
            {
                "field_key": field_key,
                "operator_value": value if filled else "",
                "operator_evidence_ref": str(stub) if filled else "",
                "operator_clearance": "clear" if filled else "",
                "operator_id": "operator_a" if filled else "",
                "required_operator_value_format": required_format,
                "evidence_stub_md": str(stub),
                "destination": "manifest.csv",
                "notes": "",
            }
        )
        packet_rows.append(
            {
                "field_order": order,
                "field_key": field_key,
                "required_evidence_kind": "pre_native_prediction_pdb"
                if field_key == "prediction_pdb"
                else "operator_field_evidence",
                "required_operator_value_format": required_format,
                "evidence_stub_md": str(stub),
                "packet_status": "awaiting_operator_evidence",
            }
        )
    _write_csv(template_csv, template_rows)
    packet_json = tmp_path / "packet.json"
    _write_json(
        packet_json,
        {
            "summary": {
                "first_unlock_evidence_packet_status": (
                    "first_unlock_evidence_packet_ready_for_source_gate_review"
                    if filled
                    else "awaiting_first_unlock_evidence_collection"
                ),
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "operator_evidence_template_csv": str(template_csv),
                "packet_folder": str(packet_dir),
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


def test_first_unlock_evidence_review_gate_blocks_blank_template_and_stubs(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path, filled=False)

    args = mod.parse_args(_args(tmp_path, packet))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_unlock_evidence_review_gate_status"] == "awaiting_first_unlock_evidence_review"
    assert summary["field_count"] == 4
    assert summary["ready_field_count"] == 0
    assert summary["blocked_field_count"] == 4
    assert summary["template_operator_value_missing_count"] == 4
    assert summary["template_operator_clearance_missing_count"] == 4
    assert summary["template_operator_id_missing_count"] == 4
    assert summary["stub_present_count"] == 4
    assert summary["stub_evidence_missing_count"] == 4
    assert summary["policy_blocked_count"] == 4
    assert summary["file_blocked_count"] == 1
    assert summary["first_blocked_field"] == "source_id"
    assert summary["first_blocker"] == "template_operator_value_missing"
    assert (tmp_path / "review.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "REVIEW.md").read_text(encoding="utf-8")


def test_first_unlock_evidence_review_gate_marks_filled_packet_ready(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path, filled=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, packet)))

    summary = payload["summary"]
    assert summary["first_unlock_evidence_review_gate_status"] == (
        "first_unlock_evidence_ready_for_source_gate_sync"
    )
    assert summary["ready_field_count"] == 4
    assert summary["blocked_field_count"] == 0
    assert summary["template_operator_value_missing_count"] == 0
    assert summary["stub_evidence_missing_count"] == 0
    assert summary["policy_pass_count"] == 4
    assert summary["file_ready_count"] == 1
    assert {row["review_gate_status"] for row in payload["rows"]} == {"field_ready_for_source_gate_sync"}


def test_first_unlock_evidence_review_gate_rejects_external_source_id(tmp_path: Path) -> None:
    packet = _write_packet(tmp_path, filled=True)
    packet_payload = json.loads(packet.read_text(encoding="utf-8"))
    template_csv = Path(packet_payload["summary"]["operator_evidence_template_csv"])
    rows = list(csv.DictReader(template_csv.open("r", encoding="utf-8", newline="")))
    rows[0]["operator_value"] = "official_archive_t1212"
    _write_csv(template_csv, rows)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, packet)))

    assert payload["summary"]["first_unlock_evidence_review_gate_status"] == (
        "awaiting_first_unlock_evidence_review"
    )
    assert payload["rows"][0]["policy_status"] == "policy_fail_external_or_official_source_id"


def test_first_unlock_evidence_review_gate_blocks_missing_packet(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path, tmp_path / "missing_packet.json")))

    assert payload["summary"]["first_unlock_evidence_review_gate_status"] == (
        "blocked_first_unlock_evidence_packet_missing"
    )
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []

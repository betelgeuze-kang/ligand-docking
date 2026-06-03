from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO intake scaffold only; no registration, prediction generation, outbound email, "
    "native-accuracy claim, or external-state mutation is performed."
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_email(value: str) -> str:
    text = str(value or "").strip()
    if not text or "@" not in text:
        return ""
    name, domain = text.split("@", 1)
    return f"{name[:1]}***@{domain}"


def extract_fasta_sequences(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current_id = ""
    current_parts: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_parts:
                records.append({"id": current_id, "sequence": "".join(current_parts)})
            current_id = line[1:].strip() or f"sequence_{len(records) + 1}"
            current_parts = []
            continue
        if re.fullmatch(r"[A-Za-z*.-]+", line):
            current_parts.append(line.replace(" ", "").upper())
    if current_parts:
        records.append({"id": current_id or f"sequence_{len(records) + 1}", "sequence": "".join(current_parts)})
    return records


def sequence_records_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    sequences = payload.get("sequences")
    if isinstance(sequences, list):
        for idx, item in enumerate(sequences, start=1):
            if isinstance(item, dict):
                seq = str(item.get("sequence") or item.get("seq") or "").strip()
                ident = str(item.get("id") or item.get("name") or f"sequence_{idx}").strip()
            else:
                seq = str(item or "").strip()
                ident = f"sequence_{idx}"
            if seq:
                records.append({"id": ident, "sequence": seq.upper()})
    for key in ("sequence", "target_sequence"):
        if payload.get(key):
            records.append({"id": key, "sequence": str(payload[key]).strip().upper()})
    if payload.get("fasta"):
        records.extend(extract_fasta_sequences(str(payload["fasta"])))
    if payload.get("raw_body") and not records:
        records.extend(extract_fasta_sequences(str(payload["raw_body"])))
    return records


def target_id_from_payload(payload: dict[str, Any]) -> str:
    for key in ("target_id", "target", "cameo_target_id", "project_title", "title"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return "unknown_target"


def results_email_from_payload(payload: dict[str, Any]) -> str:
    for key in ("results_email", "result_email", "email", "contact_email"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def payload_to_raw_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def build_intake_record(
    *,
    payload: dict[str, Any],
    raw_request: bytes,
    request_method: str,
    source_host: str = "",
    capability_lane: str = "polymer_complex_receiver_dry_run",
    job_id: str | None = None,
) -> dict[str, Any]:
    sequences = sequence_records_from_payload(payload)
    return {
        "job_id": job_id or str(uuid.uuid4()),
        "status": "received_fail_closed",
        "received_at_utc": utc_now_iso(),
        "request_method": request_method,
        "source_host": source_host,
        "raw_request_sha256": hashlib.sha256(raw_request).hexdigest(),
        "target_id": target_id_from_payload(payload),
        "parsed_sequences": sequences,
        "parsed_sequence_count": len(sequences),
        "results_email_redacted": redact_email(results_email_from_payload(payload)),
        "capability_lane": capability_lane,
        "outbound_email_enabled": False,
        "prediction_generation_enabled": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def persist_intake_record(record: dict[str, Any], jobs_dir: Path) -> Path:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    out_path = jobs_dir / f"{record['job_id']}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


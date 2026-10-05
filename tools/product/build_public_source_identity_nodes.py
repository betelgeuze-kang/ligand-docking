"""Project every declared CSV row in a frozen public archive to identity nodes.

Only the configured ID and SMILES cells are interpreted. Assay values, docking
scores and other columns are never emitted. The result is input to the joint
preflight, not an admission decision or a complete-source-family assertion.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from betelgeuze_product import public_assay_components as components
from betelgeuze_product import public_assay_preflight as preflight
from betelgeuze_product import residual_evidence
from tools.product import public_assay_dataset

SCHEMA = "public_source_csv_identity_manifest_v1"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_ROWS_PER_MEMBER = 200_000
MAX_ARCHIVE_ENTRIES = 10_000
ID_COLUMN_NAMES = frozenset({"name", "id", "compound_id", "compound id", "hit#", "hit"})
POLICY_COLUMN_NAMES = frozenset(residual_evidence.POLICY_FIELDS) | frozenset(
    residual_evidence.PROVENANCE_FIELDS) | frozenset({
        "protected", "training_allowed", "calibration_allowed",
        "independent_evaluation_allowed", "prepared"})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_hashes() -> dict[str, str]:
    result = {"builder": _sha(Path(__file__).read_bytes())}
    result.update({name: _sha(Path(module.__file__).read_bytes()) for name, module in (
        ("dataset", public_assay_dataset), ("components", components),
        ("preflight", preflight), ("residual_evidence", residual_evidence))})
    return result


def _manifest(raw: bytes) -> dict:
    manifest = components.loads(raw.decode("utf-8"))
    if (type(manifest) is not dict or set(manifest) !=
            {"schema_version", "archive", "document", "members"} or
            manifest["schema_version"] != SCHEMA):
        raise ValueError("invalid_source_identity_manifest")
    archive = manifest["archive"]
    document = manifest["document"]
    members = manifest["members"]
    if (type(archive) is not dict or set(archive) != {"path", "sha256"} or
            not isinstance(archive["path"], str) or not archive["path"] or
            not components.is_sha(archive["sha256"])):
        raise ValueError("invalid_source_archive_declaration")
    if (type(document) is not dict or set(document) != {"doi", "pmid"} or
            not isinstance(document["doi"], str) or
            re.fullmatch(r"10\.[0-9]{4,9}/\S+", document["doi"], re.I) is None or
            not isinstance(document["pmid"], str) or
            (document["pmid"] and re.fullmatch(r"[1-9][0-9]*", document["pmid"]) is None)):
        raise ValueError("invalid_declared_document_identity")
    if type(members) is not list or not members:
        raise ValueError("empty_or_invalid_source_members")
    names = set()
    for member in members:
        if (type(member) is not dict or set(member) !=
                {"name", "sha256", "id_column", "smiles_column"} or
                not isinstance(member["name"], str) or
                not member["name"].endswith(".csv") or
                member["name"].startswith("/") or
                any(part in {"", ".", ".."} for part in member["name"].split("/")) or
                not components.is_sha(member["sha256"]) or
                not all(isinstance(member[key], str) and member[key]
                        for key in ("id_column", "smiles_column")) or
                member["id_column"].strip().casefold() not in ID_COLUMN_NAMES or
                member["id_column"] == member["smiles_column"] or
                member["name"] in names):
            raise ValueError("invalid_or_duplicate_source_member")
        names.add(member["name"])
    return manifest


def _member_nodes(data: bytes, member: dict, document: dict) -> list[dict]:
    try:
        stream = io.StringIO(data.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError as exc:
        raise ValueError("non_utf8_source_member") from exc
    reader = csv.reader(stream, strict=True)
    try:
        header = next(reader)
        if (not header or any(not name for name in header) or
                len(header) != len(set(header)) or
                member["id_column"] not in header or
                member["smiles_column"] not in header):
            raise ValueError("invalid_source_csv_header")
        if any(name.strip().casefold() in POLICY_COLUMN_NAMES for name in header):
            raise ValueError("policy_bearing_source_csv_requires_separate_intake")
        id_index = header.index(member["id_column"])
        smiles_index = header.index(member["smiles_column"])
        nodes = []
        seen_ids = set()
        previous_line = reader.line_num
        for ordinal, row in enumerate(reader, 1):
            start_line = previous_line + 1
            previous_line = reader.line_num
            if ordinal > MAX_ROWS_PER_MEMBER:
                raise ValueError("source_csv_row_capacity_exceeded")
            if len(row) != len(header):
                raise ValueError(f"source_csv_width_mismatch:{start_line}")
            source_id = row[id_index].strip()
            smiles = row[smiles_index].strip()
            if not source_id or len(source_id) > 128 or source_id in seen_ids or not smiles:
                raise ValueError(f"missing_or_duplicate_source_identity:{start_line}")
            seen_ids.add(source_id)
            try:
                identity = public_assay_dataset.chemical_identity(smiles)
            except ValueError as exc:
                raise ValueError(f"invalid_source_smiles:{start_line}") from exc
            # Never emit source ID cells: a misdeclared ID field might contain
            # an assay value. It is read only to detect missing/duplicate IDs.
            occurrence = components.digest(member["name"] + ":" + member["sha256"])
            node_id = f"public-source:{occurrence}:{ordinal}"
            node = components.node_from_raw(
                {"Article DOI": document["doi"], "PMID": document["pmid"]}, identity,
                node_id=node_id, record_id=node_id, ligand_id="",
                origin={"source_sha256": member["sha256"],
                        "source_member": member["name"], "source_line": start_line},
                extra_declarations=[{"role": "development_source"}])
            # The DOI is a conservative graph key. A manifest declaration alone
            # cannot prove that the archive belongs to that document.
            node["document_identity_available"] = False
            nodes.append(node)
    except csv.Error as exc:
        raise ValueError("malformed_source_csv") from exc
    if not nodes:
        raise ValueError("empty_source_csv")
    return nodes


def build_nodes(manifest: dict, archive_raw: bytes) -> tuple[list[dict], dict]:
    if _sha(archive_raw) != manifest["archive"]["sha256"]:
        raise ValueError("source_archive_sha256_mismatch")
    nodes = []
    counts = {}
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise ValueError("source_archive_entry_capacity_exceeded")
        if len(entries) != len({entry.filename for entry in entries}):
            raise ValueError("duplicate_archive_member")
        available = {entry.filename: entry for entry in entries}
        for member in manifest["members"]:
            entry = available.get(member["name"])
            if entry is None or entry.is_dir() or entry.file_size > MAX_MEMBER_BYTES:
                raise ValueError("missing_or_oversize_source_member")
            with archive.open(entry) as stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) > MAX_MEMBER_BYTES or _sha(data) != member["sha256"]:
                raise ValueError("source_member_sha256_mismatch")
            subset = _member_nodes(data, member, manifest["document"])
            nodes.extend(subset)
            counts[member["name"]] = len(subset)
    components.component_index(nodes)
    return nodes, {"schema_version": SCHEMA, "archive_sha256": manifest["archive"]["sha256"],
                   "member_rows": counts, "node_count": len(nodes),
                   "scope": "declared CSV members only; not complete source or admission"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("refuse_existing_identity_output")
    sources = _source_hashes()
    manifest_raw = preflight.checked_bytes(args.manifest, args.manifest_sha256)
    manifest = _manifest(manifest_raw)
    archive_raw = preflight.checked_bytes(manifest["archive"]["path"],
                                          manifest["archive"]["sha256"])
    if len(archive_raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("source_archive_capacity_exceeded")
    nodes, summary = build_nodes(manifest, archive_raw)
    if _source_hashes() != sources:
        raise ValueError("source_identity_implementation_changed")
    preflight.checked_bytes(args.manifest, args.manifest_sha256)
    preflight.checked_bytes(manifest["archive"]["path"], manifest["archive"]["sha256"])
    payload = json.dumps(nodes, sort_keys=True, indent=2, allow_nan=False) + "\n"
    preflight._publish(args.output, payload)
    summary.update(manifest_sha256=args.manifest_sha256,
                   output_sha256=_sha(payload.encode()), implementation_sha256=sources)
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

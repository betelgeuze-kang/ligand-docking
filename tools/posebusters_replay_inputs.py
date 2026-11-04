"""Prepare byte-bound saved poses from four fixed run-41697499611 artifacts.

Standard library only: no docking, scoring, molecular parsing, or dependencies.
All source members are verified before exposing selected inputs. Reconstructing
candidate SDFs must use the original seed and match every expected record hash.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from typing import Any
import zipfile

from tools.redocking_lineage_validation import validate_observation_events

SOURCE_RUN_ID = "41697499611"
SOURCE_COMMIT = "16980a83cd425994bdb596077785ebe3a96542a6"
SOURCE_TREE = "fa82392f58eaf47f347ce04ca1b1a0ae9b3b35cd"
SOURCE_ARCHIVE_SHA256 = "495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c"
EVALUATION_PIPELINE_SHA256 = "482bc5f90c385108e9f2b5803c3176c14c9fea67731d3b9718b194c3d188b0b6"
ENVIRONMENT_CONTENT_IDENTITY_SHA256 = "1fde260ffa4da0d973aa4c4a2f5ba10f7a29c547251eb06afdbd17f47b6d938f"
SCHEMA_ID = "betelgeuze.posebusters_saved_pose_replay_inputs/1.0.0"
MAX_ZIP_BYTES = 32 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 6000
_SHA = re.compile(r"^[0-9a-f]{64}$")
EVENT_SCHEMA = "betelgeuze.redocking_phase_journal_event/1.0.0"
INVENTORY_SCHEMA = "betelgeuze.redocking_artifact_inventory/1.0.0"
PROFILE = "development_observation_v1"


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    artifact_id: int
    outer_sha256: str
    sealed_sha256: str
    inventory_sha256: str


ARTIFACT_SPECS = (
    ArtifactSpec("admission", 13261659499,
        "137f6ca8e304fcf5f560aa04267da553062767285779274ddd24c8b7fbe77fe5",
        "2e1eb135d5ba5d656396d3fb2ccfb8e95731754ecaacc3a4b04fdc9106dcd0a0",
        "a9b863fa84afd82d6418d8167d393b4b5810540a9cf79b6e6af6bedc2f64c7ee"),
    ArtifactSpec("development-2", 13265279407,
        "389fd632342b462f135b5b9eefd277805049b29e036c19c33a2fca650e6257a9",
        "0e5e7c7f5ed3cab433013d8c319f26b9b998819a88535ca9e61910654002cf7b",
        "f9bf04e93ffe4568144a65f68b86ae1252c641a381360e3bced974aae8ae20ec"),
    ArtifactSpec("development-10", 13265624269,
        "9377a01b2d992ef5a9047cd19d25fdd856260b8afe4e45c96790102cb70d4450",
        "b65cfa10390685227b268b9290fe8d677ba034f2a2b1672e76de5f6f0f61b216",
        "f793658f517dbdc3c884ec7ec6eeb0d49155cf16ca806db56638a50974be277f"),
    ArtifactSpec("development-18", 13263599742,
        "b227b82996e422f4f3a8354ededd8b6ea7650e4efab2ae5bcda8c0f43c1d7419",
        "73144dd853ff29ced0d1cc5eee13f942908d4c583821a93de081d04a92e469b2",
        "648f27aac9adc1b3e709c5e773cb93bad55fe213fb354e98e1c7d78272532f2f"),
)
CASE_SPECS = (
    ("5SAK_ZRY", "admission", "paired/0-p1/cases/5SAK_ZRY", 0),
    ("5SB2_1K2", "admission", "paired/1-p1/cases/5SB2_1K2", 1),
    ("6TW5_9M2", "development-2", "development/cases/6TW5_9M2", 7),
    ("6XHT_V2V", "development-10", "development/cases/6XHT_V2V", 14),
    ("6YSP_PAL", "development-18", "development/cases/6YSP_PAL", 22),
    ("6T88_MWQ", "development-2", "development/cases/6T88_MWQ", 6),
)
ROLE_SUFFIXES = {"seed": "ligand_start_conf.sdf", "native": "ligand.sdf",
                 "reference": "ligands.sdf", "receptor": "protein.pdb"}


class ReplayInputError(ValueError):
    """Frozen evidence or its local path failed a replay input invariant."""


def _require(condition, message):
    if not condition:
        raise ReplayInputError(message)


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _json(payload, label):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ReplayInputError(f"nonfinite JSON constant in {label}: {value}")

    try:
        result = json.loads(payload, object_pairs_hook=pairs, parse_constant=constant)
        stack = [result]
        while stack:
            value = stack.pop()
            if isinstance(value, float):
                _require(math.isfinite(value), f"nonfinite JSON number in {label}")
            elif isinstance(value, dict):
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        return result
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReplayInputError(f"invalid JSON in {label}") from exc


def _safe_member_name(name):
    _require(isinstance(name, str) and bool(name), "empty ZIP member path")
    _require("\\" not in name and ":" not in name and not any(ord(c) < 32 or ord(c) == 127 for c in name),
             f"unsafe ZIP member path: {name!r}")
    _require(not name.startswith("/") and all(part not in ("", ".", "..") for part in name.split("/")),
             f"unsafe ZIP member path: {name!r}")
    _require(str(PurePosixPath(name)) == name, f"noncanonical ZIP path: {name!r}")
    return name


def _safe_zip_members(archive, *, limit=MAX_PAYLOAD_BYTES):
    infos = archive.infolist()
    _require(len(infos) <= MAX_MEMBERS, "ZIP member count exceeds bound")
    result, total = {}, 0
    for info in infos:
        name = _safe_member_name(info.filename)
        _require(name not in result, f"duplicate ZIP member: {name}")
        _require(not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG),
                 f"ZIP member is not a regular file: {name}")
        _require(not (info.flag_bits & 1), f"encrypted ZIP member: {name}")
        _require(0 <= info.file_size <= MAX_MEMBER_BYTES, f"ZIP member exceeds bound: {name}")
        _require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                 f"unsupported ZIP compression: {name}")
        total += info.file_size
        _require(total <= limit, "ZIP expanded bytes exceed bound")
        result[name] = info
    return result


@dataclass
class VerifiedArchive:
    archive: zipfile.ZipFile
    inventory: dict
    summary: dict

    def read(self, name):
        _require(name in self.inventory, f"missing inventoried payload: {name}")
        return self.archive.read(name)

    def document(self, name):
        return _json(self.read(name), name)

    def close(self):
        self.archive.close()


def _verify_sealed(payload, *, expected_sha256, expected_inventory_sha256=None):
    """Verify every payload member before exposing any selected source bytes."""
    _require(len(payload) <= MAX_ZIP_BYTES, "sealed ZIP exceeds compressed byte bound")
    _require(_sha256(payload) == expected_sha256, "sealed ZIP SHA256 mismatch")
    archive = None
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
        members = _safe_zip_members(archive)
        _require("artifact-inventory.json" in members, "missing artifact inventory")
        inventory_payload = archive.read("artifact-inventory.json")
        if expected_inventory_sha256 is not None:
            _require(_sha256(inventory_payload) == expected_inventory_sha256, "inventory SHA256 mismatch")
        inventory = _json(inventory_payload, "artifact-inventory.json")
        _require(isinstance(inventory, dict) and inventory.get("schema_id") == INVENTORY_SCHEMA,
                 "unsupported artifact inventory schema")
        rows = inventory.get("files")
        _require(isinstance(rows, list), "inventory files must be a list")
        entries, byte_total = {}, 0
        for row in rows:
            _require(isinstance(row, dict) and set(row) == {"path", "sha256", "size"}, "invalid inventory entry")
            name = _safe_member_name(row["path"])
            _require(name not in entries and name != "artifact-inventory.json", "duplicate/self inventory entry")
            _require(type(row["size"]) is int and row["size"] >= 0, "invalid inventory size")
            _require(isinstance(row["sha256"], str) and _SHA.fullmatch(row["sha256"]) is not None,
                     "invalid inventory SHA256")
            _require(name in members and members[name].file_size == row["size"], f"inventory size/member mismatch: {name}")
            digest, observed_bytes = hashlib.sha256(), 0
            with archive.open(name) as source:
                while chunk := source.read(1024 * 1024):
                    observed_bytes += len(chunk)
                    _require(observed_bytes <= row["size"], f"expanded size mismatch: {name}")
                    digest.update(chunk)
            _require(observed_bytes == row["size"] and digest.hexdigest() == row["sha256"],
                     f"inventory payload hash mismatch: {name}")
            byte_total += observed_bytes
            entries[name] = row
        _require(set(members) == set(entries) | {"artifact-inventory.json"}, "unlisted/missing ZIP payload")
        _require(type(inventory.get("payload_file_count")) is int and inventory["payload_file_count"] == len(entries),
                 "inventory payload count mismatch")
        _require(type(inventory.get("archive_member_count")) is int and inventory["archive_member_count"] == len(members),
                 "inventory archive count mismatch")
        _require(type(inventory.get("bytes")) is int and inventory["bytes"] == byte_total, "inventory total bytes mismatch")
        _require(inventory.get("excluded_paths") == [] and inventory.get("hidden_files_included") is True,
                 "inventory omitted payload paths")
        return VerifiedArchive(archive, entries, {
            "sealed_sha256": expected_sha256, "sealed_size_bytes": len(payload),
            "inventory_sha256": _sha256(inventory_payload), "verified_payload_count": len(entries),
            "verified_payload_bytes": byte_total, "all_inventory_members_verified": True})
    except (ReplayInputError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        if archive is not None:
            archive.close()
        if isinstance(exc, ReplayInputError):
            raise
        raise ReplayInputError("invalid sealed ZIP") from exc


def _no_symlink_path(path):
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        try:
            _require(not stat.S_ISLNK(component.lstat().st_mode), f"symlink path is not permitted: {component}")
        except FileNotFoundError:
            pass
    return path


def _load_artifact(artifact_root, spec):
    candidates = (artifact_root / f"{spec.key}.zip", artifact_root / f"{spec.key}-artifact.zip",
                  artifact_root / f"{spec.key}-sealed-evidence.zip", artifact_root / spec.key / "sealed-evidence.zip")
    present = [p for p in candidates if p.exists() or p.is_symlink()]
    _require(len(present) == 1, f"expected exactly one archive path for {spec.key}, found {len(present)}")
    path = _no_symlink_path(present[0])
    _require(stat.S_ISREG(path.stat().st_mode), f"artifact input is not a regular file: {path}")
    _require(path.stat().st_size <= MAX_ZIP_BYTES, "input ZIP exceeds byte bound")
    payload = path.read_bytes()
    digest = _sha256(payload)
    if digest == spec.outer_sha256:
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as outer:
                members = _safe_zip_members(outer)
                _require(set(members) == {"sealed-evidence.zip"}, "outer ZIP must contain only sealed-evidence.zip")
                payload = outer.read("sealed-evidence.zip")
        except zipfile.BadZipFile as exc:
            raise ReplayInputError("invalid outer artifact ZIP") from exc
    else:
        _require(digest == spec.sealed_sha256, f"artifact SHA256 mismatch for {spec.key}")
    verified = _verify_sealed(payload, expected_sha256=spec.sealed_sha256,
                              expected_inventory_sha256=spec.inventory_sha256)
    verified.summary.update(artifact_key=spec.key, artifact_id=spec.artifact_id,
                            source_archive_path=str(path), downloaded_sha256=digest,
                            expected_outer_sha256=spec.outer_sha256)
    return verified, path


def _self_hash(document, key, label):
    _require(isinstance(document, dict) and key in document, f"missing self hash: {label}")
    projection = dict(document)
    observed = projection.pop(key)
    _require(isinstance(observed, str) and _SHA.fullmatch(observed) is not None, f"invalid self hash: {label}")
    _require(_sha256(_canonical(projection)) == observed, f"self hash mismatch: {label}")
    return observed


def _validate_source(source):
    _require(isinstance(source, dict) and source.get("commit") == SOURCE_COMMIT and
             source.get("tree") == SOURCE_TREE and source.get("workflow_run_id") == SOURCE_RUN_ID and
             source.get("workflow_run_attempt") == "1", "source run/commit/tree mismatch")
    _require(source.get("entrypoint_sha256s", {}).get("tools/run_engine_v2_public_redocking_300.py") ==
             "ad32d38b48764c167496e9abd4b2e4e3e41d41a42014a78649ef4e2c31e88d2a", "source runner payload mismatch")


def _verify_journal(archive, prefix, *, request, request_sha256, receipt_sha256, case_id):
    identity = archive.document(prefix + "identity.json")
    _require(isinstance(identity, dict), "journal identity must be an object")
    identity_sha256 = _sha256(_canonical(identity))
    _require(identity.get("case_id") == case_id and identity.get("profile") == PROFILE and
             identity.get("task") == "engine_v2" and identity.get("source") == request["source"] and
             identity.get("request_sha256") == request_sha256, "journal/request identity mismatch")
    checkpoint = archive.document(prefix + "checkpoint.json")
    _require(isinstance(checkpoint, dict) and checkpoint.get("schema_id") ==
             "betelgeuze.redocking_phase_checkpoint/1.0.0", "invalid journal checkpoint")
    sequence = checkpoint.get("last_sequence")
    _require(type(sequence) is int and 1 <= sequence <= 2000, "invalid journal event count")
    expected_names = [prefix + f"event-{n:06d}.json" for n in range(1, sequence + 1)]
    observed_names = sorted(name for name in archive.inventory if name.startswith(prefix + "event-"))
    _require(observed_names == expected_names, "journal event sequence gap/extra member")
    previous, events, event_bytes = None, [], 0
    for number, name in enumerate(expected_names, 1):
        payload = archive.read(name)
        event_bytes += len(payload)
        envelope = _json(payload, name)
        _require(isinstance(envelope, dict) and envelope.get("schema_id") == EVENT_SCHEMA and
                 envelope.get("journal_sequence") == number and type(envelope.get("journal_sequence")) is int and
                 envelope.get("identity_sha256") == identity_sha256 and
                 envelope.get("previous_event_sha256") == previous, f"journal chain mismatch: {name}")
        previous = _self_hash(envelope, "event_sha256", name)
        event = envelope.get("event")
        _require(isinstance(event, dict), "journal event must be an object")
        events.append(event)
    _require(checkpoint.get("identity_sha256") == identity_sha256 and
             checkpoint.get("event_path") == PurePosixPath(expected_names[-1]).name and
             checkpoint.get("event_sha256") == previous and checkpoint.get("last_event") == events[-1] and
             checkpoint.get("event_bytes_total") == event_bytes, "journal checkpoint binding mismatch")
    last = events[-1]
    _require(last.get("stage") == "worker" and last.get("phase") == "complete" and
             last.get("details", {}).get("receipt_sha256") == receipt_sha256 and
             last.get("details", {}).get("scientific_status") == "success" and
             last.get("details", {}).get("status") == "completed", "journal worker receipt completion mismatch")
    return events, {"identity_sha256": identity_sha256, "event_count": sequence,
        "event_bytes_total": event_bytes, "last_event_sha256": previous,
        "identity_file_sha256": archive.inventory[prefix + "identity.json"]["sha256"],
        "checkpoint_file_sha256": archive.inventory[prefix + "checkpoint.json"]["sha256"]}


def split_sdf_records(payload):
    records, offset = [], 0
    for match in re.finditer(rb"(?m)^\$\$\$\$\r?\n", payload):
        records.append(payload[offset:match.end()])
        offset = match.end()
    _require(bool(records) and offset == len(payload), "SDF missing delimiter or has trailing bytes")
    _require(all(record.splitlines()[0] for record in records), "SDF record has empty title")
    return records


def _coordinates(payload):
    _require(isinstance(payload, dict) and set(payload) == {"shape", "values_hex"}, "invalid coordinate object")
    shape = payload["shape"]
    _require(isinstance(shape, list) and len(shape) == 2 and type(shape[0]) is int and
             1 <= shape[0] <= 10000 and type(shape[1]) is int and shape[1] == 3, "invalid coordinate shape")
    values = payload["values_hex"]
    _require(isinstance(values, list) and len(values) == shape[0] * 3, "coordinate value count mismatch")
    for value in values:
        _require(isinstance(value, str), "coordinate must be a binary64 hex string")
        try:
            parsed = float.fromhex(value)
        except (OverflowError, ValueError) as exc:
            raise ReplayInputError("invalid binary64 coordinate") from exc
        _require(math.isfinite(parsed) and parsed.hex() == value, "nonfinite/noncanonical binary64 coordinate")
    return shape[0], _canonical(payload) + b"\n"


def _legacy_outcome(candidate, *, rank):
    rmsd = candidate.get("rmsd_angstrom")
    _require(type(rmsd) in (int, float) and math.isfinite(rmsd) and rmsd >= 0, "invalid legacy RMSD")
    _require(type(candidate.get("geometric_valid")) is bool and type(candidate.get("chemical_valid")) is bool,
             "invalid legacy validity value")
    failed = candidate.get("posebusters_failed_check_ids")
    _require(isinstance(failed, list) and all(isinstance(value, str) and value for value in failed) and
             len(failed) == len(set(failed)), "invalid failed-check identity list")
    return {"rank": rank, "proposal_index": candidate["proposal_index"],
        "record_sha256": candidate["pose_artifact_sha256"], "rmsd_angstrom": rmsd,
        "rmsd_binary64_hex": float(rmsd).hex(), "geometric_valid": candidate["geometric_valid"],
        "chemical_valid": candidate["chemical_valid"], "failed_check_ids": failed}


def _write_file(staging, final_root, relative, payload):
    relative = _safe_member_name(relative)
    path = staging / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(payload)
    return {"path": str(final_root / relative), "relative_path": relative,
            "sha256": _sha256(payload), "size_bytes": len(payload)}


def _prepare_case(archive, *, case_id, artifact_key, case_root, global_index, staging, final_root):
    engine = case_root + "/engines/engine_v2/"
    request_path, receipt_path = engine + "request.json", engine + "receipt.json"
    request = archive.document(request_path)
    _require(isinstance(request, dict) and request.get("case_id") == case_id and
             request.get("global_index") == global_index and type(request.get("global_index")) is int and
             request.get("task") == "engine_v2" and request.get("profile") == PROFILE,
             "request case/profile/global-index mismatch")
    _validate_source(request.get("source"))
    preflight_payload = archive.read("preflight.json")
    _require(request.get("job_preflight", {}).get("sha256") == _sha256(preflight_payload), "request/preflight hash mismatch")
    preflight = _json(preflight_payload, "preflight.json")
    _require(preflight.get("commit") == SOURCE_COMMIT and
             preflight.get("evaluation_pipeline_sha256") == EVALUATION_PIPELINE_SHA256 and
             preflight.get("environment_content_identity_sha256") == ENVIRONMENT_CONTENT_IDENTITY_SHA256,
             "frozen evaluator preflight mismatch")
    receipt = archive.document(receipt_path)
    receipt_sha256 = _self_hash(receipt, "receipt_sha256", receipt_path)
    materialization_path = case_root + "/materialization/materialization.json"
    materialization = archive.document(materialization_path)
    materialization_sha256 = _self_hash(materialization, "receipt_sha256", materialization_path)
    _require(materialization.get("case_id") == case_id and materialization.get("hash_verified_archive") is True and
             materialization.get("source_archive_sha256") == SOURCE_ARCHIVE_SHA256 and
             receipt.get("materialization_receipt_sha256") == materialization_sha256 and
             receipt.get("archive_sha256") == SOURCE_ARCHIVE_SHA256 and
             receipt.get("evaluation_pipeline_sha256") == EVALUATION_PIPELINE_SHA256 and
             receipt.get("cache_read_allowed") is False and receipt.get("fresh_execution") is True,
             "materialization/execution binding mismatch")
    _require(receipt.get("implementation_sha256") == preflight.get("engine_source_sha256"), "execution/preflight implementation mismatch")
    row = receipt.get("result")
    _require(isinstance(row, dict) and row.get("case_id") == case_id and row.get("engine_id") == "engine_v2" and
             row.get("status") == "success" and row.get("failure_code") == "", "source case is not successful Engine V2")
    inputs, expected_hashes = {}, {}
    _require(set(materialization.get("artifact_sha256s", {})) == set(ROLE_SUFFIXES.values()), "materialization input set mismatch")
    for role, suffix in ROLE_SUFFIXES.items():
        source_path = f"{case_root}/materialization/inputs/{case_id}/{case_id}_{suffix}"
        payload = archive.read(source_path)
        digest = _sha256(payload)
        _require(materialization["artifact_sha256s"].get(suffix) == digest and
                 row.get(f"{role}_artifact_sha256") == digest and materialization.get("archive_members", {}).get(suffix) ==
                 f"posebusters_benchmark_set/{case_id}/{case_id}_{suffix}", f"{role} input binding mismatch")
        expected_hashes[role] = digest
        inputs[role] = _write_file(staging, final_root, f"cases/{case_id}/{case_id}_{suffix}", payload)
        inputs[role]["source_member"] = source_path
    _require(receipt.get("input_sha256s") == expected_hashes, "execution input hashes mismatch")
    events, journal = _verify_journal(archive, engine + "journal/", request=request,
        request_sha256=archive.inventory[request_path]["sha256"], receipt_sha256=receipt_sha256, case_id=case_id)
    identity = archive.document(engine + "journal/identity.json")
    _require(identity.get("seed") == materialization.get("frozen_case_seed"), "journal seed mismatch")
    lineage = validate_observation_events(events, case_id=case_id, canonical_row=row)
    _require(lineage.get("evaluator_identity") == EVALUATION_PIPELINE_SHA256 and
             lineage.get("canonical_candidate_bindings") == 64 and lineage.get("top5_bindings") == 5,
             "candidate lineage coverage mismatch")
    candidates = row.get("engine_v2_diagnostics", {}).get("candidates")
    _require(isinstance(candidates, list) and len(candidates) == 64 and
             [c.get("proposal_index") for c in candidates] == list(range(64)) and
             all(type(c.get("proposal_index")) is int and c.get("status") == "success" and
                 type(c.get("score")) in (int, float) and math.isfinite(c["score"]) for c in candidates),
             "expected 64 finite successful candidates in proposal order")
    ranked = sorted(candidates, key=lambda c: (float(c["score"]), c["proposal_index"]))
    selected, full_order_events = {}, []
    for event in events:
        if event.get("phase") != "snapshot":
            continue
        details = event.get("details", {})
        if event.get("stage") == "refinement_selected":
            index = details.get("proposal_index")
            _require(type(index) is int and index not in selected, "duplicate selected coordinate snapshot")
            selected[index] = details
        elif event.get("stage") == "evaluation_cache_lookup" and details.get("record_count") == 64:
            full_order_events.append(details)
    _require(set(selected) == set(range(64)) and len(full_order_events) == 1, "missing/ambiguous final coordinate or evaluation order")
    expected_record_hashes = [candidate["pose_artifact_sha256"] for candidate in ranked]
    order = full_order_events[0]
    _require(order.get("record_sha256s") == expected_record_hashes and
             order.get("native_sha256") == expected_hashes["native"] and
             order.get("receptor_sha256") == expected_hashes["receptor"], "64-record evaluation order/input mismatch")
    top5_path = engine + f"poses/engine_v2/{case_id}.sdf"
    top5_payload = archive.read(top5_path)
    records = split_sdf_records(top5_payload)
    _require(len(records) == 5 and [_sha256(record) for record in records] == expected_record_hashes[:5] and
             row.get("pose_artifact_sha256s") == expected_record_hashes[:5], "saved Top5 record hashes/order mismatch")
    top5 = _write_file(staging, final_root, f"cases/{case_id}/top5.sdf", top5_payload)
    top5.update(record_count=5, record_sha256s=expected_record_hashes[:5], source_member=top5_path)
    descriptors, outcomes = [], []
    for rank, candidate in enumerate(ranked, 1):
        index = candidate["proposal_index"]
        details = selected[index]
        count, coordinates = _coordinates(details.get("coordinates_binary64"))
        _require(details.get("coordinate_fingerprint_sha256") == candidate.get("coordinate_fingerprint_sha256") and
                 details.get("proposal_fingerprint_sha256") == candidate.get("proposal_fingerprint_sha256") and
                 details.get("refinement_receipt_sha256") == candidate.get("refinement_receipt_sha256"),
                 "candidate/final-coordinate binding mismatch")
        coordinate_file = _write_file(staging, final_root, f"cases/{case_id}/coordinates/rank-{rank:03d}.json", coordinates)
        outcome = _legacy_outcome(candidate, rank=rank)
        descriptors.append({"rank": rank, "proposal_index": index,
            "expected_sdf_record_sha256": candidate["pose_artifact_sha256"],
            "expected_title": f"{case_id}_engine_v2_rank_{rank}", "score_binary64_hex": float(candidate["score"]).hex(),
            "coordinates_path": coordinate_file["path"], "coordinates_relative_path": coordinate_file["relative_path"],
            "coordinate_count": count, "coordinate_sha256": coordinate_file["sha256"],
            "coordinate_fingerprint_sha256": candidate["coordinate_fingerprint_sha256"], "legacy_outcome": outcome})
        if rank <= 5:
            _require(records[rank-1].splitlines()[0].decode("ascii") == f"{case_id}_engine_v2_rank_{rank}", "saved Top5 title mismatch")
            _require(float(row["rmsd_angstroms"][rank-1]).hex() == outcome["rmsd_binary64_hex"] and
                     row["geometric_valid"][rank-1] is outcome["geometric_valid"] and
                     row["chemical_valid"][rank-1] is outcome["chemical_valid"], "Top5 legacy outcome mismatch")
            outcomes.append(outcome)
    return {"case_id": case_id, "artifact_key": artifact_key, "source_case_root": case_root,
        "source_global_index": global_index, "purpose": "positive_validity_guard" if case_id == "6T88_MWQ" else "requested_replay_cohort",
        **inputs, "top5": top5, "legacy_top5_outcomes": outcomes, "candidates_sorted": descriptors,
        "candidate_count": 64, "native_for_posebusters_role": "native", "candidate_template_role": "seed",
        "full64_sdf_retained": False, "full64_reconstruction_requires_all_record_hash_matches": True,
        "historical_full_report_or_energy_scalars_retained": False,
        "receipt_sha256": receipt_sha256, "receipt_file_sha256": archive.inventory[receipt_path]["sha256"],
        "request_file_sha256": archive.inventory[request_path]["sha256"],
        "materialization_receipt_sha256": materialization_sha256, "journal": journal,
        "lineage_validation": lineage, "frozen_evaluator_versions": preflight["evaluator_versions"],
        "frozen_evaluator_payload_sha256s": preflight["evaluator_payload_sha256s"]}


def prepare_cases(artifact_root: Path, output_root: Path) -> dict[str, Any]:
    """Verify fixed archives and atomically publish six case descriptors.

    Each key (admission, development-2, development-10, development-18) requires
    exactly one <key>.zip, <key>-artifact.zip, <key>-sealed-evidence.zip or
    <key>/sealed-evidence.zip. Both original outer and sealed ZIP hashes are
    pinned. output_root must not exist; its parent must exist. Returned paths
    are absolute. manifest.json contains the same document as the return value.
    """
    artifact_root = _no_symlink_path(Path(artifact_root))
    output_root = _no_symlink_path(Path(output_root))
    _require(artifact_root.is_dir(), "artifact_root must be an existing directory")
    _require(not output_root.exists() and not output_root.is_symlink(), "output_root must be fresh")
    _require(output_root.parent.is_dir(), "output_root parent must already exist")
    staging = Path(tempfile.mkdtemp(prefix=f".{output_root.name}-preparing-", dir=output_root.parent))
    try:
        cases, artifacts = {}, []
        for spec in ARTIFACT_SPECS:
            archive, _ = _load_artifact(artifact_root, spec)
            try:
                artifacts.append(archive.summary)
                for case_id, key, case_root, global_index in CASE_SPECS:
                    if key == spec.key:
                        cases[case_id] = _prepare_case(archive, case_id=case_id, artifact_key=key,
                            case_root=case_root, global_index=global_index, staging=staging, final_root=output_root)
            finally:
                archive.close()
        _require(len(cases) == 6, "replay cohort incomplete")
        positive = cases["6T88_MWQ"]["legacy_top5_outcomes"]
        _require(sum(row["geometric_valid"] and row["chemical_valid"] for row in positive) == 3,
                 "positive validity guard changed")
        manifest = {"schema_id": SCHEMA_ID, "source_run_id": SOURCE_RUN_ID,
            "source_execution_commit": SOURCE_COMMIT, "source_execution_tree": SOURCE_TREE,
            "source_evaluation_pipeline_sha256": EVALUATION_PIPELINE_SHA256,
            "source_environment_content_identity_sha256": ENVIRONMENT_CONTENT_IDENTITY_SHA256,
            "artifact_root": str(artifact_root), "output_root": str(output_root),
            "molecular_evaluation_performed": False, "candidate_generation_performed": False,
            "case_count": len(cases), "exact_saved_top5_record_count": 30,
            "artifacts": artifacts, "cases": [cases[case_id] for case_id, *_ in CASE_SPECS]}
        _write_file(staging, output_root, "manifest.json", _canonical(manifest) + b"\n")
        _require(not output_root.exists() and not output_root.is_symlink(), "output_root appeared during preparation")
        staging.rename(output_root)
        return manifest
    except Exception:
        shutil.rmtree(staging)
        raise

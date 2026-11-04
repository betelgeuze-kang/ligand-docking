"""Adversarial admission tests; no molecular dependency or evaluator is loaded."""
from copy import deepcopy
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from tools import posebusters_replay_inputs as replay


def zip_bytes(entries):
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)
    return buffer.getvalue()


def sealed(files=None, *, mutate_inventory=None, extra=()):
    files = {"inputs/seed.sdf": b"seed\n$$$$\n", "journal/sample.json": b'{"ok":true}\n'} if files is None else files
    entries = [(name, payload) for name, payload in files.items()]
    inventory = {"schema_id": replay.INVENTORY_SCHEMA, "hidden_files_included": True,
        "excluded_paths": [], "payload_file_count": len(entries), "archive_member_count": len(entries) + 1,
        "bytes": sum(len(payload) for _, payload in entries),
        "files": [{"path": name, "sha256": replay._sha256(payload), "size": len(payload)} for name, payload in entries]}
    if mutate_inventory is not None:
        mutate_inventory(inventory)
    body = replay._canonical(inventory) + b"\n"
    return zip_bytes([*entries, ("artifact-inventory.json", body), *extra]), body


def verified(payload):
    return replay._verify_sealed(payload, expected_sha256=replay._sha256(payload))


def signed(document, key):
    return {**document, key: replay._sha256(replay._canonical(document))}


def journal_fixture():
    request = {"source": {"commit": "fixture"}}
    request_sha, receipt_sha = "a" * 64, "b" * 64
    identity = {"case_id": "fixture", "profile": replay.PROFILE, "task": "engine_v2",
        "source": request["source"], "request_sha256": request_sha}
    identity_sha = replay._sha256(replay._canonical(identity))
    events = [{"stage": "worker", "phase": "start"},
        {"stage": "worker", "phase": "complete", "details": {
            "receipt_sha256": receipt_sha, "scientific_status": "success", "status": "completed"}}]
    files = {"journal/identity.json": replay._canonical(identity)}
    previous, total = None, 0
    for sequence, event in enumerate(events, 1):
        envelope = signed({"schema_id": replay.EVENT_SCHEMA, "identity_sha256": identity_sha,
            "journal_sequence": sequence, "previous_event_sha256": previous, "event": event}, "event_sha256")
        payload = replay._canonical(envelope) + b"\n"
        files[f"journal/event-{sequence:06d}.json"] = payload
        total += len(payload)
        previous = envelope["event_sha256"]
    checkpoint = {"schema_id": "betelgeuze.redocking_phase_checkpoint/1.0.0", "identity_sha256": identity_sha,
        "last_sequence": 2, "event_path": "event-000002.json", "event_sha256": previous,
        "event_bytes_total": total, "last_event": events[-1]}
    files["journal/checkpoint.json"] = replay._canonical(checkpoint)
    arguments = dict(request=request, request_sha256=request_sha, receipt_sha256=receipt_sha, case_id="fixture")
    return files, arguments


class TestArchiveAdmission(unittest.TestCase):
    def test_verified_member_bytes_are_preserved(self):
        payload, body = sealed()
        archive = replay._verify_sealed(payload, expected_sha256=replay._sha256(payload),
            expected_inventory_sha256=replay._sha256(body))
        try:
            self.assertEqual(archive.read("inputs/seed.sdf"), b"seed\n$$$$\n")
            self.assertEqual(archive.summary["verified_payload_count"], 2)
            self.assertTrue(archive.summary["all_inventory_members_verified"])
            with self.assertRaises(replay.ReplayInputError):
                archive.read("not-in-inventory")
        finally:
            archive.close()

    def test_outer_bytes_and_inventory_hashes_are_independently_pinned(self):
        payload, _ = sealed()
        with self.assertRaisesRegex(replay.ReplayInputError, "sealed ZIP SHA256"):
            replay._verify_sealed(payload, expected_sha256="0" * 64)
        with self.assertRaisesRegex(replay.ReplayInputError, "inventory SHA256"):
            replay._verify_sealed(payload, expected_sha256=replay._sha256(payload), expected_inventory_sha256="0" * 64)

    def test_traversal_absolute_windows_and_control_names_are_rejected(self):
        for name in ("../escape", "/absolute", "a/../b", "a//b", "a/./b", "a\\b", "C:/escape", "a\nb"):
            with self.subTest(name=name):
                payload, _ = sealed({name: b"bad"})
                with self.assertRaises(replay.ReplayInputError):
                    verified(payload)

    def test_symlink_and_nonregular_members_are_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFDIR):
            with self.subTest(mode=mode):
                info = zipfile.ZipInfo("unsafe")
                info.create_system = 3
                info.external_attr = (mode | 0o700) << 16
                payload = zip_bytes([(info, b"target")])
                with self.assertRaisesRegex(replay.ReplayInputError, "not a regular file"):
                    verified(payload)

    def test_duplicate_and_unlisted_members_are_rejected(self):
        for extra in (("inputs/seed.sdf", b"different"), ("extra.txt", b"unlisted")):
            with self.subTest(name=extra[0]):
                payload, _ = sealed(extra=(extra,))
                with self.assertRaises(replay.ReplayInputError):
                    verified(payload)

    def test_inventory_hash_size_counts_and_omissions_are_enforced(self):
        mutations = {
            "hash": lambda i: i["files"][0].update(sha256="0" * 64),
            "size": lambda i: i["files"][0].update(size=1),
            "bool_size": lambda i: i["files"][0].update(size=True),
            "missing_member": lambda i: i["files"].pop(),
            "duplicate_entry": lambda i: i["files"].append(deepcopy(i["files"][0])),
            "file_count": lambda i: i.update(payload_file_count=0),
            "archive_count": lambda i: i.update(archive_member_count=0),
            "byte_count": lambda i: i.update(bytes=0),
            "hidden": lambda i: i.update(hidden_files_included=False),
            "excluded": lambda i: i.update(excluded_paths=["secret"]),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                payload, _ = sealed(mutate_inventory=mutation)
                with self.assertRaises(replay.ReplayInputError):
                    verified(payload)

    def test_member_count_compressed_and_expanded_bounds_are_enforced(self):
        payload, _ = sealed()
        with patch.object(replay, "MAX_ZIP_BYTES", 1):
            with self.assertRaisesRegex(replay.ReplayInputError, "compressed byte bound"):
                verified(payload)
        with patch.object(replay, "MAX_MEMBERS", 1):
            with self.assertRaisesRegex(replay.ReplayInputError, "member count"):
                verified(payload)
        with patch.object(replay, "MAX_MEMBER_BYTES", 1):
            with self.assertRaisesRegex(replay.ReplayInputError, "member exceeds"):
                verified(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            with self.assertRaisesRegex(replay.ReplayInputError, "expanded bytes"):
                replay._safe_zip_members(archive, limit=1)

    def test_missing_and_duplicate_inventory_json_keys_are_rejected(self):
        payload = zip_bytes([("data", b"data")])
        with self.assertRaisesRegex(replay.ReplayInputError, "missing artifact inventory"):
            verified(payload)
        payload = zip_bytes([("artifact-inventory.json", b'{"files":[],"files":[]}')])
        with self.assertRaisesRegex(replay.ReplayInputError, "duplicate JSON key"):
            verified(payload)


class TestReplayBinding(unittest.TestCase):
    def test_nonfinite_json_and_duplicate_keys_fail_closed(self):
        for payload in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}', b'{"x":1,"x":2}'):
            with self.subTest(payload=payload):
                with self.assertRaises(replay.ReplayInputError):
                    replay._json(payload, "test")

    def test_coordinate_binary64_sign_and_precision_are_preserved(self):
        values = {"shape": [1, 3], "values_hex": [(-0.0).hex(), (1.25).hex(), float.fromhex("0x1.0000000000001p+0").hex()]}
        count, encoded = replay._coordinates(values)
        self.assertEqual(count, 1)
        self.assertEqual(json.loads(encoded), values)
        self.assertEqual(json.loads(encoded)["values_hex"][0], "-0x0.0p+0")

    def test_invalid_coordinate_shapes_counts_noncanonical_and_nonfinite_values_reject(self):
        baseline = {"shape": [1, 3], "values_hex": ["0x0.0p+0"] * 3}
        malformed = [dict(baseline, shape=[True, 3]), dict(baseline, shape=[0, 3]),
            dict(baseline, shape=[1, 2]), dict(baseline, values_hex=["0x0.0p+0"]),
            dict(baseline, extra="ignored")]
        for value in ("nan", "inf", "-inf", "0x0p+0", "0x1p+99999999", 1.0):
            malformed.append(dict(baseline, values_hex=[value, "0x0.0p+0", "0x0.0p+0"]))
        for payload in malformed:
            with self.subTest(payload=payload):
                with self.assertRaises(replay.ReplayInputError):
                    replay._coordinates(payload)

    def test_record_split_preserves_bytes_and_rejects_unaccounted_tail(self):
        records = [b"first\r\nbody\r\n$$$$\r\n", b"second\nbody\n$$$$\n"]
        self.assertEqual(replay.split_sdf_records(b"".join(records)), records)
        for payload in (b"", b"missing\n$$$$", b"x\n$$$$\ntrailing", b"\n$$$$\n"):
            with self.subTest(payload=payload):
                with self.assertRaises(replay.ReplayInputError):
                    replay.split_sdf_records(payload)

    def test_source_run_commit_tree_and_runner_are_all_bound(self):
        source = {"commit": replay.SOURCE_COMMIT, "tree": replay.SOURCE_TREE,
            "workflow_run_id": replay.SOURCE_RUN_ID, "workflow_run_attempt": "1",
            "entrypoint_sha256s": {"tools/run_engine_v2_public_redocking_300.py":
                "ad32d38b48764c167496e9abd4b2e4e3e41d41a42014a78649ef4e2c31e88d2a"}}
        replay._validate_source(source)
        for key in source:
            with self.subTest(key=key):
                changed = deepcopy(source)
                changed[key] = {} if key == "entrypoint_sha256s" else "other"
                with self.assertRaises(replay.ReplayInputError):
                    replay._validate_source(changed)

    def test_receipt_self_hash_rejects_changed_science(self):
        receipt = signed({"result": {"geometric_valid": [True]}}, "receipt_sha256")
        replay._self_hash(receipt, "receipt_sha256", "fixture")
        receipt["result"]["geometric_valid"][0] = False
        with self.assertRaisesRegex(replay.ReplayInputError, "self hash mismatch"):
            replay._self_hash(receipt, "receipt_sha256", "fixture")

    def test_valid_journal_and_request_receipt_bindings(self):
        files, arguments = journal_fixture()
        archive = verified(sealed(files)[0])
        try:
            events, report = replay._verify_journal(archive, "journal/", **arguments)
            self.assertEqual(len(events), 2)
            self.assertEqual(report["event_count"], 2)
            for name in ("request_sha256", "receipt_sha256", "case_id"):
                changed = {**arguments, name: "wrong"}
                with self.subTest(name=name), self.assertRaises(replay.ReplayInputError):
                    replay._verify_journal(archive, "journal/", **changed)
        finally:
            archive.close()

    def test_journal_gap_chain_checkpoint_and_recomputed_event_tampering_reject(self):
        for mutation in ("gap", "chain", "event_payload", "checkpoint_bytes", "checkpoint_tail"):
            with self.subTest(mutation=mutation):
                files, arguments = journal_fixture()
                if mutation == "gap":
                    files.pop("journal/event-000001.json")
                elif mutation.startswith("checkpoint"):
                    checkpoint = json.loads(files["journal/checkpoint.json"])
                    if mutation == "checkpoint_bytes": checkpoint["event_bytes_total"] += 1
                    else: checkpoint["last_event"] = {"stage": "invented"}
                    files["journal/checkpoint.json"] = replay._canonical(checkpoint)
                else:
                    event = json.loads(files["journal/event-000002.json"])
                    if mutation == "chain":
                        event["previous_event_sha256"] = "c" * 64
                        event.pop("event_sha256")
                        event = signed(event, "event_sha256")
                    else:
                        event["event"]["details"]["scientific_status"] = "changed"
                    files["journal/event-000002.json"] = replay._canonical(event)
                archive = verified(sealed(files)[0])
                try:
                    with self.assertRaises(replay.ReplayInputError):
                        replay._verify_journal(archive, "journal/", **arguments)
                finally:
                    archive.close()


class TestFilesystemBoundary(unittest.TestCase):
    def test_symlink_inputs_and_parent_components_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaisesRegex(replay.ReplayInputError, "symlink"):
                replay._no_symlink_path(root / "link" / "missing")

    def test_outer_artifact_and_direct_sealed_paths_work_but_ambiguity_rejects(self):
        payload, inventory = sealed()
        outer = zip_bytes([("sealed-evidence.zip", payload)])
        spec = replay.ArtifactSpec("fixture", 1, replay._sha256(outer), replay._sha256(payload), replay._sha256(inventory))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = root / "fixture.zip"
            for content in (outer, payload):
                file.write_bytes(content)
                archive, chosen = replay._load_artifact(root, spec)
                try:
                    self.assertEqual(chosen, file)
                    self.assertEqual(archive.read("inputs/seed.sdf"), b"seed\n$$$$\n")
                finally:
                    archive.close()
            (root / "fixture-sealed-evidence.zip").write_bytes(payload)
            with self.assertRaisesRegex(replay.ReplayInputError, "exactly one"):
                replay._load_artifact(root, spec)

    def test_existing_output_is_never_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts, output = root / "artifacts", root / "output"
            artifacts.mkdir(); output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep")
            with self.assertRaisesRegex(replay.ReplayInputError, "must be fresh"):
                replay.prepare_cases(artifacts, output)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_failed_admission_leaves_no_output_or_staging_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts, output = root / "artifacts", root / "output"
            artifacts.mkdir()
            with self.assertRaises(replay.ReplayInputError):
                replay.prepare_cases(artifacts, output)
            self.assertFalse(output.exists())
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["artifacts"])

    def test_import_is_standard_library_only(self):
        source_root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, "-c", "import sys; from tools import posebusters_replay_inputs; "
            "assert not any(name in sys.modules for name in ('torch','rdkit','posebusters','numpy','pandas'))"],
            cwd=source_root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

"""Pure coverage/negative tests for fixed32 integration input orchestration.

These tests use synthetic, hash-bound ZIPs and replace only _prepare_case,
whose coordinate/scientific lineage checks already belong to the frozen
helper's tests and the real sealed-data preparation job. No molecular module
is imported or executed here. The independent fixed-cohort digest below was
derived from successful-case-specs.json, audited from run 41697499611.
"""

from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from tools import posebusters_integration_inputs as integration
from tools import posebusters_replay_inputs as frozen


INDEPENDENT_FIXED_COHORT_SHA256 = "d7a17ad56d779bbf21f1d0912298bd04b2fa438a26b158ede6bd647560069fb2"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def signed(document):
    return {**document, "receipt_sha256": sha(canonical(document))}


def fixture_source():
    return {
        "commit": frozen.SOURCE_COMMIT, "tree": frozen.SOURCE_TREE,
        "workflow_run_id": frozen.SOURCE_RUN_ID, "workflow_run_attempt": "1",
        "entrypoint_sha256s": {
            "tools/run_engine_v2_public_redocking_300.py":
                "ad32d38b48764c167496e9abd4b2e4e3e41d41a42014a78649ef4e2c31e88d2a",
        },
    }


def seal(files):
    inventory = {
        "schema_id": frozen.INVENTORY_SCHEMA, "hidden_files_included": True,
        "excluded_paths": [], "payload_file_count": len(files),
        "archive_member_count": len(files) + 1,
        "bytes": sum(len(value) for value in files.values()),
        "files": [{"path": name, "sha256": sha(value), "size": len(value)}
                  for name, value in sorted(files.items())],
    }
    inventory_bytes = canonical(inventory) + b"\n"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(files.items()):
            archive.writestr(name, value)
        archive.writestr("artifact-inventory.json", inventory_bytes)
    return output.getvalue(), inventory_bytes


class SyntheticCohort:
    """Keep the fixed IDs/indexes/seeds; replace only fixture bytes/digests."""

    def __init__(self, root, *, mutate=None, mutate_signed_receipt=None):
        self.root = root
        self.root.mkdir()
        self.rows = {}
        self.success_specs = []
        self.failure_specs = []
        self.artifact_specs = []
        files_by_key = {spec.key: {} for spec in integration.ARTIFACT_SPECS}
        preflight = canonical({
            "commit": frozen.SOURCE_COMMIT,
            "evaluation_pipeline_sha256": frozen.EVALUATION_PIPELINE_SHA256,
            "environment_content_identity_sha256": frozen.ENVIRONMENT_CONTENT_IDENTITY_SHA256,
            "engine_source_sha256": "a" * 64,
        }) + b"\n"
        for files in files_by_key.values():
            files["preflight.json"] = preflight
        for prepared, specs in ((True, integration.CASE_SPECS), (False, integration.NOT_PREPARED_SPECS)):
            for case_id, key, case_root, index, seed, _ in specs:
                materialization = {
                    "case_id": case_id, "frozen_case_seed": seed,
                    "source_archive_sha256": frozen.SOURCE_ARCHIVE_SHA256,
                    "hash_verified_archive": True,
                }
                request = {
                    "case_id": case_id, "global_index": index,
                    "profile": frozen.PROFILE, "task": "engine_v2", "source": fixture_source(),
                    "job_preflight": {"sha256": sha(preflight)},
                }
                row = {
                    "case_id": case_id, "engine_id": "engine_v2",
                    "status": "success" if prepared else "failure",
                    "failure_code": "" if prepared else "engine_v2_case_failed",
                    "engine_v2_diagnostics": {
                        "preparation_status": "success" if prepared else "failure",
                        "preparation_failure_code": "" if prepared else "unsupported_large_ring_system",
                        "candidate_success_count": 64 if prepared else 0,
                        "candidate_failure_count": 0, "candidates": [],
                    },
                }
                if mutate is not None:
                    mutate(case_id, materialization, request, row)
                materialization = signed(materialization)
                receipt = signed({
                    "result": row, "materialization_receipt_sha256": materialization["receipt_sha256"],
                    "archive_sha256": frozen.SOURCE_ARCHIVE_SHA256,
                    "evaluation_pipeline_sha256": frozen.EVALUATION_PIPELINE_SHA256,
                    "implementation_sha256": "a" * 64,
                    "cache_read_allowed": False, "fresh_execution": True,
                })
                if mutate_signed_receipt is not None:
                    mutate_signed_receipt(case_id, receipt)
                receipt_bytes = canonical(receipt) + b"\n"
                self.rows[case_id] = row
                row_spec = (case_id, key, case_root, index, seed, sha(receipt_bytes))
                (self.success_specs if prepared else self.failure_specs).append(row_spec)
                files = files_by_key[key]
                files[f"{case_root}/engines/engine_v2/receipt.json"] = receipt_bytes
                files[f"{case_root}/engines/engine_v2/request.json"] = canonical(request) + b"\n"
                files[f"{case_root}/materialization/materialization.json"] = canonical(materialization) + b"\n"
        for original in integration.ARTIFACT_SPECS:
            payload, inventory = seal(files_by_key[original.key])
            (root / f"{original.key}.zip").write_bytes(payload)
            self.artifact_specs.append(frozen.ArtifactSpec(
                original.key, original.artifact_id, "0" * 64, sha(payload), sha(inventory)))
        self.success_specs = tuple(self.success_specs)
        self.failure_specs = tuple(self.failure_specs)
        self.artifact_specs = tuple(self.artifact_specs)

    def patch_scope(self, prepare):
        stack = ExitStack()
        stack.enter_context(patch.object(integration, "ARTIFACT_SPECS", self.artifact_specs))
        stack.enter_context(patch.object(integration, "CASE_SPECS", self.success_specs))
        stack.enter_context(patch.object(integration, "NOT_PREPARED_SPECS", self.failure_specs))
        stack.enter_context(patch.object(frozen, "_prepare_case", prepare))
        return stack


def prepared_descriptor(archive, *, case_id, artifact_key, case_root, global_index, staging, final_root):
    """A stub solely for the already-tested scientific preparation dependency."""
    frozen._write_file(staging, final_root, f"cases/{case_id}/delegated.json", b'{"delegated":true}\n')
    return {
        "case_id": case_id, "artifact_key": artifact_key,
        "source_case_root": case_root, "source_global_index": global_index,
        "candidate_count": 64, "top5": {"record_count": 5},
    }


class FixedCohortContractTests(unittest.TestCase):
    def test_contract_matches_independently_extracted_original_specs(self):
        projection = {
            "fixed_case_order": integration.FIXED_CASE_ORDER,
            "successful": integration.CASE_SPECS,
            "not_prepared": integration.NOT_PREPARED_SPECS,
        }
        self.assertEqual(sha(canonical(projection)), INDEPENDENT_FIXED_COHORT_SHA256)
        integration.validate_fixed_cohort()
        self.assertEqual(Counter(row[1] for row in integration.CASE_SPECS),
                         {"development-2": 7, "development-10": 7, "development-18": 7, "development-26": 8})
        self.assertEqual({row[0] for row in integration.NOT_PREPARED_SPECS},
                         {"6M73_FNR", "6YJA_2BA", "6YR2_T1C"})
        self.assertEqual(integration.PILOT_CASES, ("6T88_MWQ", "6YSP_PAL"))
        self.assertTrue(set(integration.PILOT_CASES) <= set(integration.CASE_IDS))
        self.assertTrue({"5SAK_ZRY", "5SB2_1K2"}.isdisjoint(integration.FIXED_CASE_ORDER))

    def test_artifact_set_is_exact_development_partition_without_admission(self):
        specs = integration.ARTIFACT_SPECS
        self.assertEqual(tuple(spec.key for spec in specs),
                         ("development-2", "development-10", "development-18", "development-26"))
        self.assertEqual(tuple(spec.artifact_id for spec in specs),
                         (13265279407, 13265624269, 13263599742, 13265626749))
        self.assertEqual(len({spec.sealed_sha256 for spec in specs}), 4)
        for spec in specs:
            for value in (spec.outer_sha256, spec.sealed_sha256, spec.inventory_sha256):
                self.assertRegex(value, r"^[0-9a-f]{64}$")

    def test_cohort_missing_duplicate_index_order_and_seed_changes_fail(self):
        base = integration.CASE_SPECS
        duplicate_id = list(base)
        duplicate_id[1] = (base[0][0], *base[1][1:])
        duplicate_index = list(base)
        duplicate_index[1] = (*base[1][:3], base[0][3], *base[1][4:])
        swapped_identity = list(base)
        swapped_identity[0] = (base[1][0], *base[0][1:])
        swapped_identity[1] = (base[0][0], *base[1][1:])
        wrong_seed = list(base)
        wrong_seed[0] = (*base[0][:4], base[0][4] + 1, base[0][5])
        for changed in (base[1:], tuple(duplicate_id), tuple(duplicate_index), tuple(swapped_identity), tuple(wrong_seed)):
            with self.subTest(changed=changed[:2]), patch.object(integration, "CASE_SPECS", changed):
                with self.assertRaises(frozen.ReplayInputError):
                    integration.validate_fixed_cohort()

    def test_import_has_no_molecular_or_array_dependency(self):
        source_root = Path(__file__).resolve().parents[2]
        command = [sys.executable, "-c", "import sys; from tools import posebusters_integration_inputs; "
                   "assert not any(name in sys.modules for name in ('torch','rdkit','posebusters','numpy','pandas'))"]
        result = subprocess.run(command, cwd=source_root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class IntegrationPreparationTests(unittest.TestCase):
    def _assert_no_published_or_staging_output(self, root, output):
        self.assertFalse(output.exists())
        self.assertFalse(any(path.name.startswith(f".{output.name}-preparing-") for path in root.iterdir()))

    def test_all_29_successes_are_delegated_and_three_failures_remain_in_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = SyntheticCohort(root / "artifacts")
            output = root / "prepared"
            prepared = Mock(side_effect=prepared_descriptor)
            opened = []
            original_loader = frozen._load_artifact

            def observe_loader(*args):
                archive, path = original_loader(*args)
                opened.append(archive)
                return archive, path

            with fixture.patch_scope(prepared), patch.object(frozen, "_load_artifact", side_effect=observe_loader):
                manifest = integration.prepare_cases(fixture.root, output)
            self.assertEqual(prepared.call_count, 29)
            calls = [call.kwargs for call in prepared.call_args_list]
            self.assertEqual([call["case_id"] for call in calls], list(integration.CASE_IDS))
            for actual, expected in zip(calls, fixture.success_specs):
                self.assertEqual((actual["case_id"], actual["artifact_key"], actual["case_root"], actual["global_index"]), expected[:4])
                self.assertEqual(actual["final_root"], output)
            self.assertEqual(len(opened), 4)
            self.assertTrue(all(archive.archive.fp is None for archive in opened))
            self.assertEqual(json.loads((output / "manifest.json").read_bytes()), manifest)
            self.assertEqual(manifest["fixed_case_denominator"], 32)
            self.assertEqual(manifest["successful_case_count"], 29)
            self.assertEqual(manifest["not_prepared_case_count"], 3)
            self.assertEqual(manifest["exact_saved_top5_record_count"], 145)
            self.assertEqual(manifest["expected_candidate_record_count"], 1856)
            self.assertIs(manifest["molecular_evaluation_performed"], False)
            self.assertIs(manifest["candidate_generation_performed"], False)
            self.assertEqual([row["case_id"] for row in manifest["cases"]], list(integration.CASE_IDS))
            self.assertEqual([row["source_global_index"] for row in manifest["not_prepared"]], [5, 16, 20])
            self.assertTrue(all(row["candidate_count"] == 0 and row["status"] == "not_prepared"
                                for row in manifest["not_prepared"]))
            self.assertTrue(all(row["purpose"] == "fixed_development32_successful_case" for row in manifest["cases"]))
            for row in manifest["cases"]:
                descriptor = row["source_row"]
                path = output / descriptor["relative_path"]
                payload = path.read_bytes()
                self.assertEqual(json.loads(payload), fixture.rows[row["case_id"]])
                self.assertEqual(sha(payload), descriptor["sha256"])
                self.assertEqual(len(payload), descriptor["size_bytes"])
                self.assertEqual(Path(descriptor["path"]), path)
            self.assertFalse(any(path.name.startswith(".prepared-preparing-") for path in root.iterdir()))

    def test_corrupt_artifact_digest_aborts_and_cleans_prior_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = SyntheticCohort(root / "artifacts")
            output = root / "prepared"
            corrupt = fixture.root / "development-26.zip"
            corrupt.write_bytes(corrupt.read_bytes() + b"unbound tail")
            with fixture.patch_scope(prepared_descriptor):
                with self.assertRaisesRegex(frozen.ReplayInputError, "artifact SHA256 mismatch"):
                    integration.prepare_cases(fixture.root, output)
            self._assert_no_published_or_staging_output(root, output)

    def test_success_and_unprepared_receipt_file_hashes_are_checked(self):
        for success in (True, False):
            with self.subTest(success=success), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = SyntheticCohort(root / "artifacts")
                output = root / "prepared"
                attribute = "success_specs" if success else "failure_specs"
                rows = list(getattr(fixture, attribute))
                rows[0] = (*rows[0][:-1], "0" * 64)
                setattr(fixture, attribute, tuple(rows))
                with fixture.patch_scope(prepared_descriptor):
                    with self.assertRaisesRegex(frozen.ReplayInputError, "original .* receipt changed"):
                        integration.prepare_cases(fixture.root, output)
                self._assert_no_published_or_staging_output(root, output)

    def test_success_seed_change_and_float_type_reject_after_delegation(self):
        first = integration.CASE_SPECS[0][0]
        for changed in (2026072703, 2026072702.0, "2026072702"):
            with self.subTest(seed=repr(changed)), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def mutate(case_id, materialization, request, row):
                    if case_id == first:
                        materialization["frozen_case_seed"] = changed

                fixture = SyntheticCohort(root / "artifacts", mutate=mutate)
                output = root / "prepared"
                with fixture.patch_scope(prepared_descriptor):
                    with self.assertRaisesRegex(frozen.ReplayInputError, "original seed mismatch"):
                        integration.prepare_cases(fixture.root, output)
                self._assert_no_published_or_staging_output(root, output)

    def test_unprepared_receipt_self_hash_and_row_identity_are_checked(self):
        target = integration.NOT_PREPARED_SPECS[0][0]
        changes = ({"case_id": "wrong"}, {"status": "success"}, {"engine_id": "vina"})
        for changed in changes:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def mutate(case_id, materialization, request, row):
                    if case_id == target:
                        row.update(changed)

                fixture = SyntheticCohort(root / "artifacts", mutate=mutate)
                output = root / "prepared"
                with fixture.patch_scope(prepared_descriptor):
                    with self.assertRaisesRegex(frozen.ReplayInputError, "unprepared case status changed"):
                        integration.prepare_cases(fixture.root, output)
                self._assert_no_published_or_staging_output(root, output)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def mutate_hash(case_id, receipt):
                if case_id == target:
                    receipt["receipt_sha256"] = "0" * 64

            fixture = SyntheticCohort(root / "artifacts", mutate_signed_receipt=mutate_hash)
            output = root / "prepared"
            with fixture.patch_scope(prepared_descriptor):
                with self.assertRaisesRegex(frozen.ReplayInputError, "self hash mismatch"):
                    integration.prepare_cases(fixture.root, output)
            self._assert_no_published_or_staging_output(root, output)

    def test_unprepared_request_source_case_index_and_seed_values_are_checked(self):
        target = integration.NOT_PREPARED_SPECS[0][0]
        for mutation in ("source", "case", "index", "seed"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def mutate(case_id, materialization, request, row):
                    if case_id != target:
                        return
                    if mutation == "source":
                        request["source"]["commit"] = "changed"
                    elif mutation == "case":
                        request["case_id"] = "different"
                    elif mutation == "index":
                        request["global_index"] += 1
                    else:
                        materialization["frozen_case_seed"] += 1

                fixture = SyntheticCohort(root / "artifacts", mutate=mutate)
                output = root / "prepared"
                with fixture.patch_scope(prepared_descriptor):
                    with self.assertRaises(frozen.ReplayInputError):
                        integration.prepare_cases(fixture.root, output)
                self._assert_no_published_or_staging_output(root, output)

    def test_missing_artifact_and_unmapped_case_cannot_publish_partial_cohort(self):
        for failure in ("missing_archive", "unmapped_case"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = SyntheticCohort(root / "artifacts")
                output = root / "prepared"
                if failure == "missing_archive":
                    (fixture.root / "development-26.zip").unlink()
                else:
                    rows = list(fixture.success_specs)
                    rows[-1] = (rows[-1][0], "unmapped", *rows[-1][2:])
                    fixture.success_specs = tuple(rows)
                with fixture.patch_scope(prepared_descriptor):
                    with self.assertRaises(frozen.ReplayInputError):
                        integration.prepare_cases(fixture.root, output)
                self._assert_no_published_or_staging_output(root, output)

    def test_delegate_exception_and_keyboard_interrupt_close_archive_and_remove_staging(self):
        for error in (RuntimeError("delegate failed"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = SyntheticCohort(root / "artifacts")
                output = root / "prepared"
                opened = []
                original_loader = frozen._load_artifact

                def observe_loader(*args):
                    archive, path = original_loader(*args)
                    opened.append(archive)
                    return archive, path

                def fail_after_staging(archive, **kwargs):
                    prepared_descriptor(archive, **kwargs)
                    raise error

                with fixture.patch_scope(fail_after_staging), patch.object(frozen, "_load_artifact", side_effect=observe_loader):
                    with self.assertRaises(type(error)) as caught:
                        integration.prepare_cases(fixture.root, output)
                self.assertIs(caught.exception, error)
                self.assertEqual(len(opened), 1)
                self.assertIsNone(opened[0].archive.fp)
                self._assert_no_published_or_staging_output(root, output)

    def test_existing_output_and_symlink_paths_are_not_modified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            output = root / "prepared"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep")
            with self.assertRaisesRegex(frozen.ReplayInputError, "must be fresh"):
                integration.prepare_cases(artifacts, output)
            self.assertEqual(sentinel.read_text(), "keep")
            linked = root / "linked"
            linked.symlink_to(artifacts, target_is_directory=True)
            with self.assertRaisesRegex(frozen.ReplayInputError, "symlink"):
                integration.prepare_cases(linked, root / "unused")
            broken = root / "broken"
            broken.symlink_to(root / "missing", target_is_directory=True)
            with self.assertRaisesRegex(frozen.ReplayInputError, "symlink"):
                integration.prepare_cases(artifacts, broken)

    def test_missing_roots_fail_without_loading_an_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = root / "artifacts"
            with patch.object(frozen, "_load_artifact") as loader:
                with self.assertRaisesRegex(frozen.ReplayInputError, "artifact root"):
                    integration.prepare_cases(artifacts, root / "prepared")
                artifacts.mkdir()
                with self.assertRaisesRegex(frozen.ReplayInputError, "parent directory"):
                    integration.prepare_cases(artifacts, root / "missing-parent" / "prepared")
                loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()

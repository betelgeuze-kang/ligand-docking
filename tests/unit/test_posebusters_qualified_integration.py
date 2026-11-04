"""Control-plane regressions; these tests do not execute molecular calculations."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from tools import run_posebusters_qualified_integration as qualified


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config/posebusters_qualified_profile_20261104.json"


def helper_root():
    # The published checkout contains the unchanged helper. The override is
    # solely for pure tests in a partial local checkout, never production CLI.
    return Path(os.environ.get("PB_QUALIFIED_TEST_HELPER_ROOT", str(ROOT))).resolve()


def cpu_for(profile):
    target = profile["cpu"]
    flags = " ".join(target["common_flags"])
    uname = profile["platform"]
    return {"affinity": [4, 5, 6, 7], "common_flags": list(target["common_flags"]),
        "cpus": [{**target["identity"], "processor": str(cpu), "flags": flags} for cpu in (4, 5, 6, 7)],
        "uname": [uname["system"], "different-hostname", uname["release"], uname["version"], uname["machine"], uname["processor"]],
        "hostname": "different-hostname", "machine": uname["machine"], "boot_id": "observed-new-boot",
        "cpuinfo": "observation only", "cpuinfo_sha256": "a" * 64}


def arguments():
    return SimpleNamespace(launcher_root=Path("/launcher"), execution_root=Path("/execution"),
        python=Path("/runtime/bin/python"), profile=Path("/launcher/config/profile.json"),
        input_root=Path("/inputs"), runtime_root=Path("/runtime"), output_root=Path("/output/host-1"),
        profile_sha256=qualified.PROFILE_FILE_SHA256, bundle_sha256=qualified.BUNDLE_SHA256,
        launcher_workflow_sha="a" * 40, host_slot=1)


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = qualified.load_helpers(helper_root())
        cls.profile = qualified.load_profile(PROFILE_PATH, qualified.PROFILE_FILE_SHA256, cls.helper)

    def test_real_frozen_profile_and_helper_are_bound(self):
        self.assertEqual(self.profile["execution_source"], qualified.EXECUTION_SOURCE)
        self.assertEqual(self.profile["runtime"]["torch_interop_threads"], 2)
        self.assertEqual(self.profile["runtime"]["torch_intraop_threads"], 1)
        self.assertEqual(self.helper.__name__, "_posebusters_qualified_frozen_cpu_helpers")
        self.assertNotEqual(self.helper.__name__, "tools.run_posebusters_cpu_diagnostic")

    def test_profile_tamper_is_integrity_failure_not_ineligibility(self):
        value = deepcopy(self.profile)
        value["cpu"]["identity"]["model"] = "1"
        value["profile_sha256"] = qualified.digest({k: v for k, v in value.items() if k != "profile_sha256"})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            qualified.atomic_json(path, value)
            with self.assertRaises(qualified.IntegrityError):
                qualified.load_profile(path, qualified.PROFILE_FILE_SHA256, self.helper)
            with self.assertRaises(qualified.IntegrityError):
                qualified.load_profile(path, qualified.digest_file(path), self.helper)

    def test_new_host_numbers_and_hostname_do_not_change_profile_match(self):
        qualified.validate_cpu(cpu_for(self.profile), self.profile)

    def test_every_cpu_identity_field_is_required(self):
        for key in qualified.CPU_IDENTITY_KEYS:
            with self.subTest(key=key):
                observed = cpu_for(self.profile)
                observed["cpus"][2][key] += " changed"
                with self.assertRaises(qualified.ProfileMismatch):
                    qualified.validate_cpu(observed, self.profile)

    def test_one_cpu_extra_flag_cannot_hide_in_common_intersection(self):
        observed = cpu_for(self.profile)
        observed["cpus"][0]["flags"] += " unknown_feature"
        with self.assertRaises(qualified.ProfileMismatch):
            qualified.validate_cpu(observed, self.profile)

    def test_platform_and_affinity_must_match(self):
        for field in ("platform", "affinity"):
            with self.subTest(field=field):
                observed = cpu_for(self.profile)
                if field == "platform":
                    observed["uname"][2] = "different-kernel"
                else:
                    observed["affinity"].pop()
                with self.assertRaises(qualified.ProfileMismatch):
                    qualified.validate_cpu(observed, self.profile)

    def test_malformed_boolean_affinity_is_not_host_ineligibility(self):
        observed = cpu_for(self.profile)
        observed["affinity"][0] = True
        with self.assertRaises(qualified.IntegrityError):
            qualified.validate_cpu(observed, self.profile)

    def test_native_environment_removes_only_explicit_aten_request(self):
        expected = deepcopy(self.profile["numerical_environment"]["observed"])
        native = qualified.expected_environment(self.profile, native=True)
        forced = qualified.expected_environment(self.profile)
        self.assertEqual(forced, expected)
        self.assertNotIn("ATEN_CPU_CAPABILITY", native)
        expected.pop("ATEN_CPU_CAPABILITY")
        self.assertEqual(native, expected)
        self.assertEqual(self.profile["numerical_environment"]["observed"]["ATEN_CPU_CAPABILITY"], "avx2")

    def test_unexpected_numeric_override_is_not_silently_dropped(self):
        actual = qualified.expected_environment(self.profile)
        actual["MKL_CBWR"] = "COMPATIBLE"
        with self.assertRaises(qualified.ProfileMismatch):
            qualified.matches(actual, qualified.expected_environment(self.profile), "environment mismatch")

    def test_all_library_bytes_match_and_transient_cache_can_be_unobserved(self):
        rows = deepcopy(self.profile["libraries"]["worker"]["entries"])
        qualified.validate_disk_libraries(rows, self.profile)
        observed = [row for row in rows if row["path"] != "/etc/ld.so.cache"]
        coverage = qualified.validate_libraries(observed, self.profile, kind="worker")
        self.assertEqual(coverage["unobserved_optional_paths"], ["/etc/ld.so.cache"])
        self.assertEqual(coverage["observed_count"], 198)

    def test_required_core_only_is_valid_and_reports_optional_coverage(self):
        section = self.profile["libraries"]["worker"]
        rows = [row for row in section["entries"] if row["path"] in section["required_mapped_paths"]]
        coverage = qualified.validate_libraries(rows, self.profile, kind="worker")
        self.assertEqual(coverage["observed_count"], 21)
        self.assertEqual(len(coverage["unobserved_optional_paths"]), 178)

    def test_missing_required_core_extra_mapping_and_changed_bytes_reject(self):
        section = self.profile["libraries"]["worker"]
        for change in ("missing", "extra", "bytes"):
            with self.subTest(change=change):
                rows = deepcopy(section["entries"])
                if change == "missing":
                    rows = [row for row in rows if row["path"] != section["required_mapped_paths"][0]]
                elif change == "extra":
                    rows.append({"path": "/unqualified/libextra.so", "size_bytes": 1, "sha256": "a" * 64})
                else:
                    rows[0]["sha256"] = "0" * 64
                with self.assertRaises(qualified.ProfileMismatch):
                    qualified.validate_libraries(rows, self.profile, kind="worker")

    def test_optional_mapping_when_observed_still_requires_exact_bytes(self):
        rows = deepcopy(self.profile["libraries"]["worker"]["entries"])
        next(row for row in rows if row["path"] == "/etc/ld.so.cache")["sha256"] = "0" * 64
        with self.assertRaises(qualified.ProfileMismatch):
            qualified.validate_libraries(rows, self.profile, kind="worker")
        with self.assertRaises(qualified.ProfileMismatch):
            qualified.validate_disk_libraries(rows, self.profile)

    def test_probe_mapping_set_remains_exact(self):
        rows = deepcopy(self.profile["libraries"]["probe"]["entries"])
        qualified.validate_libraries(rows, self.profile, kind="probe")
        with self.assertRaises(qualified.ProfileMismatch):
            qualified.validate_libraries(rows[:-1], self.profile, kind="probe")

    def test_duplicate_mapping_and_boolean_size_are_integrity_errors(self):
        row = deepcopy(self.profile["libraries"]["worker"]["entries"][0])
        with self.assertRaises(qualified.IntegrityError):
            qualified.library_projection([row, row])
        row["size_bytes"] = True
        with self.assertRaises(qualified.IntegrityError):
            qualified.library_projection([row])


class EvidenceAndCommandTests(unittest.TestCase):
    def test_resource_contract_keeps_three_distinct_limits(self):
        self.assertEqual((qualified.LAUNCHER_WALL_SECONDS, qualified.CASE_WALL_SECONDS,
                          qualified.WORKER_WALL_SECONDS), (3000, 2400, 1800))
        self.assertEqual(qualified.LIMITS["original_historical_worker_wall_seconds"], 900)
        self.assertEqual(qualified.RSS_BYTES, 6442450944)
        self.assertEqual(qualified.LOG_BYTES, 8388608)

    def test_original_run_case_cli_has_no_new_science_or_limit_flags(self):
        actual = qualified.case_command(arguments(), Path("/evidence/case"))
        self.assertEqual(actual, ["/runtime/bin/python", "-m", "tools.run_posebusters_integration", "run-case",
            "--input-root", "/inputs", "--bundle-sha256", qualified.BUNDLE_SHA256,
            "--runtime-root", "/runtime", "--output-root", "/evidence/case",
            "--stage", "pipeline", "--case-id", "6YSP_PAL"])
        self.assertNotIn("--mode", actual)
        self.assertNotIn("--wall-limit", actual)

    def test_actual_launcher_argv_is_fully_bound_and_duplicates_reject(self):
        args = arguments()
        command = qualified.qualification_command(args)
        command[2] = "run"
        command[command.index("--output-root") + 1] = str(args.output_root)
        qualified.validate_actual_launcher_argv(command, args)
        for extra in (["--host-slot", "2"], ["--unknown", "value"]):
            with self.assertRaises(qualified.IntegrityError):
                qualified.validate_actual_launcher_argv(command + extra, args)
        command[command.index("--bundle-sha256") + 1] = "0" * 64
        with self.assertRaises(qualified.IntegrityError):
            qualified.validate_actual_launcher_argv(command, args)

    def test_json_duplicate_keys_nan_and_self_hash_tamper_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value.json"
            for text in ('{"ok":1,"ok":2}', '{"n":NaN}', '{"n":Infinity}'):
                path.write_text(text)
                with self.assertRaises(qualified.IntegrityError):
                    qualified.read_json(path)
        value = qualified.signed({"status": "success"})
        qualified.verify_signed(value)
        value["status"] = "ineligible"
        with self.assertRaises(qualified.IntegrityError):
            qualified.verify_signed(value)

    def test_inventory_binds_raw_bytes_and_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            payload = root / "full-report.json"
            payload.write_text('{"cell":false}')
            row = qualified.inventory(root)[0]
            qualified.bound_file(root, row)
            payload.write_text('{"cell":1}')
            with self.assertRaises(qualified.IntegrityError):
                qualified.bound_file(root, row)
            (root / "linked").symlink_to("/etc/passwd")
            with self.assertRaises(qualified.IntegrityError):
                qualified.inventory(root)
            with self.assertRaises(qualified.IntegrityError):
                qualified.safe_path(root, "../outside")

    def test_claimed_science_success_must_invoke_raw_original_assessor(self):
        class OriginalController:
            called = False
            @staticmethod
            def verify_signed(value, key, label):
                qualified.equal(value[key], qualified.digest({k: v for k, v in value.items() if k != key}), label)
            def assess_case(self, *args, **kwargs):
                self.called = True
                raise qualified.IntegrityError("raw fullReport was changed")
        value = {"status": "success", "cleanup_complete": True, "assessment": {"exact_equivalence_passed": True}}
        value["summary_sha256"] = qualified.digest(value)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qualified.atomic_json(root / "case-summary.json", value)
            controller = OriginalController()
            with self.assertRaisesRegex(qualified.IntegrityError, "raw fullReport"):
                qualified.original_assessment(controller, root, bundle={}, selected={})
            self.assertTrue(controller.called)

    def test_typed_exact_comparison_does_not_treat_false_as_zero(self):
        for left, right in ((False, 0), (True, 1), (1, 1.0)):
            with self.assertRaises(qualified.IntegrityError):
                qualified.equal(left, right, "scalar type differs")


class AggregateTests(unittest.TestCase):
    @staticmethod
    def rows():
        return [{"host_slot": slot, "status": "ineligible", "eligible": False, "scientific_success": False}
                for slot in qualified.HOST_SLOTS]

    def test_all_ineligible_is_profile_unavailable_not_success(self):
        self.assertEqual(qualified.aggregate_status(self.rows()), "profile_unavailable")

    def test_one_success_with_three_authentic_ineligible_hosts_is_accepted(self):
        rows = self.rows()
        rows[1].update(status="success", eligible=True, scientific_success=True)
        self.assertEqual(qualified.aggregate_status(rows), "success")

    def test_failure_incomplete_or_invalid_host_cannot_be_dropped(self):
        for status in ("failed", "incomplete", "invalid_evidence"):
            rows = self.rows()
            rows[0].update(status="success", eligible=True, scientific_success=True)
            rows[1].update(status=status, eligible=True)
            self.assertEqual(qualified.aggregate_status(rows), "failed")

    def test_missing_duplicate_boolean_slot_and_false_success_reject(self):
        rows = self.rows()
        for variant in (rows[:-1], rows + [rows[0]], [rows[0], rows[0], rows[2], rows[3]],
                        [{**rows[0], "host_slot": True}, *rows[1:]],
                        [{**rows[0], "status": "success", "eligible": 1, "scientific_success": True}, *rows[1:]]):
            self.assertEqual(qualified.aggregate_status(variant), "failed")

    def test_run_attempt_and_exact_artifact_path_prevent_old_result_replay(self):
        expected = {"GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "1"}
        value = {"host_slot": 2, "job": {**expected, "GITHUB_JOB": "qualified_case"}}
        root = Path("/results")
        location = root / "pb-qualified-integration-6YSP_PAL-host-2-123456-1/pb-qualified-integration/host-2"
        qualified.validate_run_binding(value, location, root, expected)
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            bad = deepcopy(value)
            bad["job"][key] = "99"
            with self.assertRaises(qualified.IntegrityError):
                qualified.validate_run_binding(bad, location, root, expected)
        for bad_path in (root / "old-run/host-2", location.parent / "host-1",
                         root / "pb-qualified-integration-6YSP_PAL-host-2-123456-2/pb-qualified-integration/host-2"):
            with self.assertRaises(qualified.IntegrityError):
                qualified.validate_run_binding(value, bad_path, root, expected)
        with self.assertRaises(qualified.IntegrityError):
            qualified.validate_run_binding(value, location, root, {})


class ExternalProcessTests(unittest.TestCase):
    def test_real_nested_processes_are_bound_without_injected_observer_code(self):
        helper = qualified.load_helpers(helper_root())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            environment = helper.condition_environment(os.environ, root, "avx2")
            environment["QUALIFIED_TEST_SECRET"] = "must-not-be-serialized"
            commands = {mode: [sys.executable, "-c", "import time; time.sleep(1.0)", mode]
                        for mode in qualified.MODES}
            code = "import json,subprocess,sys,time; time.sleep(.3); [subprocess.run(cmd,check=True) for cmd in json.loads(sys.argv[1])]"
            command = [sys.executable, "-c", code, json.dumps(list(commands.values()))]
            before_parent_environment = dict(os.environ)
            monitor = qualified.NestedWorkerMonitor(helper, command, commands, environment, root)
            monitor.start()
            process = None
            try:
                process = subprocess.Popen(command, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, (stdout, stderr))
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                observed = monitor.finish()
            self.assertEqual(os.environ, before_parent_environment)
            self.assertEqual(observed["errors"], [])
            self.assertEqual(set(observed["records"]), {"case_controller", *qualified.MODES})
            parent = observed["records"]["case_controller"]
            self.assertEqual(parent["identity"]["local_pid"], process.pid)
            for mode in qualified.MODES:
                child = observed["records"][mode]
                self.assertEqual(child["identity"]["parent_pid"], parent["identity"]["pid"])
                self.assertEqual(child["argv"], commands[mode])
                self.assertEqual(child["cwd"], str(root))
                self.assertEqual(child["execution_github_sha"], qualified.EXECUTION_SOURCE["commit"])
                self.assertEqual(child["numerical_environment"]["ATEN_CPU_CAPABILITY"], "avx2")
                self.assertGreaterEqual(child["samples"], 2)
                self.assertTrue(child["mapped_shared_libraries"])
            self.assertNotIn("must-not-be-serialized", json.dumps(observed))

    def test_cleanup_error_survives_monitor_finalization_failure(self):
        helper = qualified.load_helpers(helper_root())
        class FatalCleanup(RuntimeError):
            pass
        def supervise():
            raise FatalCleanup("uncertain descendants")
        def finalize():
            raise OSError("observation write failed")
        with self.assertRaisesRegex(FatalCleanup, "uncertain descendants") as caught:
            helper.supervise_and_finalize(supervise, finalize)
        self.assertIsInstance(caught.exception.__cause__, OSError)


if __name__ == "__main__":
    unittest.main()

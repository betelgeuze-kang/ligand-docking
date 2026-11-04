"""Exercise failure propagation and retained evidence in the actual workflow.

The deliberately failing Python executable replaces only the command boundary;
the checked-in shell block and its real tee run unchanged under bash -e. These
tests never execute an installer, molecular worker, or GitHub mutation.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/posebusters_observed_integration.yml"
MARKER = "observed-workflow intentional Python failure"
CASE_STEP = "Run all original strategies and preserve the original scientific verdict"
GUARD_STEP = "Verify observed integration and workflow boundary regressions"
FALLBACK_STEP = "Preserve infrastructure failure when no observed result was written"


def workflow():
    value = yaml.safe_load(WORKFLOW.read_text())
    if not isinstance(value, dict):
        raise AssertionError("workflow must be a YAML mapping")
    return value


def step(name):
    matches = [item for job in workflow()["jobs"].values() for item in job["steps"]
               if item.get("name") == name]
    if len(matches) != 1:
        raise AssertionError("workflow step is missing or duplicated: " + name)
    return matches[0]


def environment(root):
    value = dict(os.environ)
    for key in ("SHELLOPTS", "BASH_ENV", "ENV"):
        value.pop(key, None)
    value.update(RUNNER_TEMP=str(root / "runner-temp"),
                 GITHUB_WORKSPACE=str(root / "workspace"), GITHUB_SHA="a" * 40,
                 GITHUB_RUN_ID="1234", GITHUB_RUN_ATTEMPT="1", HOST_SLOT="1",
                 OBSERVED_JOB_STATUS="failure", ATEN_CPU_CAPABILITY="avx2")
    return value


def run_block(block, root, cwd):
    script = root / "actual-workflow-block.sh"
    script.write_text(block)
    return subprocess.run(["/usr/bin/bash", "-e", str(script)], cwd=cwd,
                          env=environment(root), capture_output=True, text=True, timeout=10)


class ObservedWorkflowTests(unittest.TestCase):
    def assert_pipeline_propagates_python_failure(self, step_name, working_checkout, log_name):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            runner_temp, workspace = root / "runner-temp", root / "workspace"
            for path in (runner_temp / "p0p1-python/bin", runner_temp / "pb-observed-logs/host-1",
                         workspace / "launcher", workspace / "execution"):
                path.mkdir(parents=True)
            fake_python = runner_temp / "p0p1-python/bin/python"
            native_guard = ('if [ "${ATEN_CPU_CAPABILITY+x}" = x ]; then exit 29; fi\n'
                            if step_name == CASE_STEP else "")
            fake_python.write_text("#!/bin/sh\n" + native_guard
                                   + "printf '%s\\n' '" + MARKER + "'\nexit 17\n")
            fake_python.chmod(0o700)
            result = run_block(step(step_name)["run"], root, workspace / working_checkout)
            retained_log = runner_temp / "pb-observed-logs/host-1" / log_name
            self.assertTrue(retained_log.is_file(), (result.stdout, result.stderr))
            self.assertEqual(retained_log.read_text().strip(), MARKER,
                             "the actual tee must consume and retain Python output")
            self.assertIn(MARKER, result.stdout)
            self.assertEqual(result.returncode, 17,
                             f"{step_name}: tee masked Python exit 17: {result.stderr}")

    def test_guard_test_failure_reaches_workflow(self):
        self.assert_pipeline_propagates_python_failure(GUARD_STEP, "launcher", "tests.log")

    def test_original_case_failure_reaches_workflow(self):
        self.assert_pipeline_propagates_python_failure(CASE_STEP, "execution", "integration.log")

    def test_pre_checkout_failure_is_retained_without_python_or_a_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            runner_temp = root / "runner-temp"
            runner_temp.mkdir()
            result = run_block(step(FALLBACK_STEP)["run"], root, runner_temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            retained = json.loads((runner_temp / "pb-observed-logs/host-1/infrastructure-failure.json").read_text())
            self.assertEqual(retained["status"], "incomplete")
            self.assertFalse(retained["diagnostic_collection_complete"])
            self.assertFalse(retained["scientific_validation_passed"])
            self.assertEqual(retained["workflow_sha"], "a" * 40)
            self.assertEqual(retained["run_id"], "1234")
            self.assertEqual(retained["run_attempt"], "1")
            self.assertEqual(retained["host_slot"], 1)
            self.assertEqual(retained["job_status"], "failure")

    def test_existing_scientific_failure_is_not_replaced_by_infrastructure_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            runner_temp = root / "runner-temp"
            case = runner_temp / "pb-observed-integration/host-1"
            case.mkdir(parents=True)
            result_path = case / "observed-result.json"
            original = b'{"status":"scientific_failure","diagnostic_collection_complete":true}\n'
            result_path.write_bytes(original)
            result = run_block(step(FALLBACK_STEP)["run"], root, runner_temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result_path.read_bytes(), original)
            self.assertFalse((runner_temp / "pb-observed-logs/host-1/infrastructure-failure.json").exists())

    def test_both_fixed_hosts_run_without_selecting_an_eligible_cpu(self):
        value = workflow()
        self.assertEqual(set(value["jobs"]), {"observed_case"})
        job = value["jobs"]["observed_case"]
        self.assertEqual(job["runs-on"], "ubuntu-22.04")
        self.assertEqual(job["strategy"]["matrix"], {"host_slot": [1, 2]})
        self.assertIs(job["strategy"]["fail-fast"], False)
        self.assertEqual(job["strategy"]["max-parallel"], 2)
        self.assertEqual(job["timeout-minutes"], 60)
        self.assertEqual(job["defaults"]["run"]["shell"], "bash")
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("ATEN_CPU_CAPABILITY", value["env"])
        self.assertNotIn("ATEN_CPU_CAPABILITY", job.get("env", {}))
        self.assertNotIn("if", step(CASE_STEP), "CPU eligibility must not skip the original case")
        self.assertIn("unset ATEN_CPU_CAPABILITY\n", step(CASE_STEP)["run"])
        self.assertNotIn("--profile", step(CASE_STEP)["run"])
        for item in job["steps"]:
            self.assertNotIn("continue-on-error", item)
            if "run" in item:
                self.assertEqual(item["run"].splitlines()[0], "set -euo pipefail")
        self.assertEqual(step(FALLBACK_STEP)["if"], "always()")
        self.assertEqual(step(FALLBACK_STEP)["working-directory"], "${{ runner.temp }}")
        upload = step("Retain every host result including strict scientific failures")
        self.assertEqual(upload["if"], "always()")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")
        self.assertIn("pb-observed-integration/host-${{ matrix.host_slot }}", upload["with"]["path"])
        self.assertIn("pb-observed-logs/host-${{ matrix.host_slot }}", upload["with"]["path"])

    def test_workflow_is_bound_to_the_declared_protocol_and_frozen_runtime(self):
        value = workflow()
        protocol_path = ROOT / "config/posebusters_observed_protocol_20261104.json"
        protocol = json.loads(protocol_path.read_text())
        case = step(CASE_STEP)
        hashes = re.findall(r"--protocol-sha256\s+([0-9a-f]{64})\b", case["run"])
        self.assertEqual(hashes, [hashlib.sha256(protocol_path.read_bytes()).hexdigest()])
        self.assertIn('--protocol "$GITHUB_WORKSPACE/launcher/config/posebusters_observed_protocol_20261104.json"',
                      case["run"])
        self.assertIn("--bundle-sha256 " + protocol["input_bundle_sha256"], case["run"])
        execution_checkout = step("Checkout unchanged execution source")
        self.assertEqual(execution_checkout["with"]["ref"], protocol["execution_source"]["commit"])
        self.assertEqual(step("Download original frozen runtime")["with"]["run-id"], "41697499611")
        self.assertEqual(step("Download exact admitted original inputs")["with"]["run-id"], "41798394302")
        effective = dict(value.get("env", {}))
        effective.update(value["jobs"]["observed_case"].get("env", {}))
        effective.update(case.get("env", {}))
        self.assertIs(protocol["capability_request"], None)
        self.assertNotIn("ATEN_CPU_CAPABILITY", effective)
        for key, expected in protocol["numerical_environment"].items():
            self.assertEqual(effective.get(key), expected, key)

    def test_observed_push_is_read_only_and_uses_ephemeral_pinned_actions(self):
        value = workflow()
        self.assertEqual(value["on"], {"push": {"branches": ["codex/pb-observed-integration-20261104"]}})
        self.assertEqual(value["permissions"], {"contents": "read", "actions": "read"})
        job = value["jobs"]["observed_case"]
        self.assertEqual(job["runs-on"], "ubuntu-22.04")
        self.assertNotIn("permissions", job)
        for item in job["steps"]:
            if "uses" in item:
                self.assertRegex(item["uses"], r"^actions/[a-z-]+@[0-9a-f]{40}$")
            if item.get("uses", "").startswith("actions/checkout@"):
                self.assertIs(item["with"]["persist-credentials"], False)
                self.assertIs(item["with"]["clean"], True)


if __name__ == "__main__":
    unittest.main()

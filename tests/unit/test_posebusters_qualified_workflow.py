"""Execute the real workflow pipelines under the observed bash -e shell.

The temporary Python executable deliberately exits 17. The real tee succeeds,
so only the workflow's own failure handling can preserve that exit status.
No installer, molecular worker, or GitHub command is executed by these tests.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/posebusters_qualified_integration.yml"
MARKER = "qualified-workflow intentional Python failure"


def run_block(step_name):
    """Read the literal block of a uniquely named step in this checked-in YAML."""
    lines = WORKFLOW.read_text().splitlines()
    matches = [index for index, line in enumerate(lines) if line.strip() == "- name: " + step_name]
    if len(matches) != 1:
        raise AssertionError("workflow step is missing or duplicated: " + step_name)
    start = matches[0]
    step_indent = len(lines[start]) - len(lines[start].lstrip())
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= step_indent:
            break
        if line.strip() in ("run: |", "run: |-", "run: |+"):
            indent = len(line) - len(line.lstrip()) + 2
            block = []
            for body in lines[index + 1:]:
                if body.strip() and len(body) - len(body.lstrip()) < indent:
                    break
                block.append(body[indent:] if body.strip() else "")
            if not block:
                break
            return "\n".join(block).rstrip() + "\n"
    raise AssertionError("step has no supported literal run block: " + step_name)


class QualifiedWorkflowShellTests(unittest.TestCase):
    def assert_pipeline_propagates_python_failure(self, step_name, working_checkout, log_relative_path):
        block = run_block(step_name)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            runner_temp = root / "runner-temp"
            workspace = root / "workspace"
            for path in (runner_temp / "p0p1-python/bin", runner_temp / "pb-qualified-logs/host-1",
                         runner_temp / "pb-qualified-final", workspace / "launcher", workspace / "execution"):
                path.mkdir(parents=True)
            fake_python = runner_temp / "p0p1-python/bin/python"
            fake_python.write_text("#!/bin/sh\nprintf '%s\\n' '" + MARKER + "'\nexit 17\n")
            fake_python.chmod(0o700)
            script = root / "actual-workflow-block.sh"
            script.write_text(block)
            environment = dict(os.environ)
            for key in ("SHELLOPTS", "BASH_ENV", "ENV"):
                environment.pop(key, None)
            environment.update(RUNNER_TEMP=str(runner_temp), GITHUB_WORKSPACE=str(workspace),
                               GITHUB_SHA="a" * 40, HOST_SLOT="1")
            result = subprocess.run(["/usr/bin/bash", "-e", str(script)], cwd=workspace / working_checkout,
                                    env=environment, capture_output=True, text=True, timeout=10)
            retained_log = runner_temp / log_relative_path
            self.assertTrue(retained_log.is_file(), (result.stdout, result.stderr))
            self.assertEqual(retained_log.read_text().strip(), MARKER,
                             "the actual tee must consume and successfully retain Python output")
            self.assertIn(MARKER, result.stdout)
            self.assertEqual(result.returncode, 17,
                f"{step_name}: bash -e reported {result.returncode}; tee masked Python exit 17.\n{result.stderr}")

    def test_guard_test_failure_reaches_workflow(self):
        self.assert_pipeline_propagates_python_failure(
            "Verify qualified integration and workflow boundary regressions", "launcher",
            "pb-qualified-logs/host-1/tests.log")

    def test_case_launcher_failure_reaches_workflow(self):
        self.assert_pipeline_propagates_python_failure(
            "Run the original three-strategy case only on a qualified host", "execution",
            "pb-qualified-logs/host-1/integration.log")

    def test_aggregate_profile_unavailable_exit_reaches_workflow(self):
        self.assert_pipeline_propagates_python_failure(
            "Require every eligible host to pass the original raw comparison", "execution",
            "pb-qualified-final/aggregate.log")


if __name__ == "__main__":
    unittest.main()

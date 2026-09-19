"""Verify an installed wheel's candidate resume CLI outside the source checkout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture
from betelgeuze_product.cpu_refinement_v1_2.provenance import source_manifest


def verify(python, output):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parents[1]
    if output.is_relative_to(source):
        raise ValueError("verification must run outside checkout")
    python = str(Path(python).absolute())
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    commands = []

    def run(args, expected_returncode=0):
        command = [python, "-I", *args]
        result = subprocess.run(
            command, cwd=output, env=env, capture_output=True, text=True, timeout=180
        )
        commands.append(
            dict(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
        (output / "commands.json").write_text(json.dumps(commands, indent=2))
        if result.returncode != expected_returncode:
            raise RuntimeError("installed candidate CLI failed; see commands.json")
        return json.loads(result.stdout) if expected_returncode == 0 else None

    expected = source_manifest()
    expected_file = output / "source-manifest.json"
    expected_file.write_text(json.dumps(expected))
    probe = run(
        [
            "-c",
            "import sys,json,hashlib; from pathlib import Path; "
            "import betelgeuze_product,betelgeuze_engine_v2; "
            "root=Path(betelgeuze_product.__file__).resolve().parent.parent; "
            "assert root.is_relative_to(Path(sys.prefix)); "
            "assert Path(betelgeuze_engine_v2.__file__).resolve().is_relative_to(root); "
            f"assert not root.is_relative_to(Path({str(source)!r})); "
            "expected=json.loads(Path(sys.argv[1]).read_text()); "
            "actual={k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in expected}; "
            "assert actual==expected; "
            "print(json.dumps({'root':str(root),'python':sys.version,'source_hashes':len(actual)}))",
            str(expected_file),
        ]
    )
    observations = []
    for equal in (False, True):
        name = "equal-budget" if equal else "same-candidates"
        inputs = output / (name + "-inputs")
        inputs.mkdir()
        request = request_fixture(inputs)
        if equal:
            request["solver"]["minimization"]["max_backtracks"] = 0
            request["budget"].update(candidate_count=12, max_refinement_steps=2)
            request["comparison"].update(mode="equal_work_budget", work_units_per_arm=8)
        request_file = output / (name + "-request.json")
        request_file.write_text(json.dumps(request))
        result_dir = output / name
        prefix = [
            "-m",
            "betelgeuze_product.cpu_refinement_v1_2",
            "run-resumable",
            str(request_file),
            "--output",
            str(result_dir),
        ]
        paused = run([*prefix, "--stop-after", "2"])
        assert (
            paused["execution_complete"] is False
            and paused["committed_candidates"] == 2
        )
        assert not (result_dir / "complete.json").exists()
        resumed = run([*prefix, "--resume"])
        assert resumed["execution_complete"] is True
        saved = {
            n: (result_dir / n).read_bytes()
            for n in ("request.json", "report.json", "complete.json")
        }
        report = json.loads(saved["report.json"])
        assert report["implementation_sources"] == expected
        summary = report["summary"]
        assert [len(summary["rows"][k]) for k in ("baseline", "refined")] == (
            [8, 2] if equal else [4, 4]
        )
        assert summary["costs"]["baseline"]["reused_candidates"] == 2
        assert all(
            row["succeeded"] for rows in summary["rows"].values() for row in rows
        )
        run([*prefix, "--resume"])
        assert saved == {n: (result_dir / n).read_bytes() for n in saved}
        inputs.rename(output / (name + "-inputs-moved"))
        verification = run(
            [
                "-m",
                "betelgeuze_product.cpu_refinement_v1_2",
                "verify-resumable",
                str(result_dir),
            ]
        )
        assert verification["structural_verification_passed"] is True
        assert saved == {n: (result_dir / n).read_bytes() for n in saved}
        observations.append(
            {
                "mode": summary["mode"],
                "summary_sha256": summary["summary_sha256"],
                "report_sha256": hashlib.sha256(saved["report.json"]).hexdigest(),
                "source_hashes": len(expected),
                "portable_without_inputs": True,
            }
        )
    recoveries = []
    for equal in (False, True):
        for stage in ("report.json", "complete.json"):
            name = ("equal" if equal else "same") + "-interrupted-" + stage
            inputs = output / (name + "-inputs")
            inputs.mkdir()
            request = request_fixture(inputs)
            if equal:
                request["solver"]["minimization"]["max_backtracks"] = 0
                request["budget"].update(candidate_count=12, max_refinement_steps=2)
                request["comparison"].update(
                    mode="equal_work_budget", work_units_per_arm=8
                )
            request_file = output / (name + "-request.json")
            request_file.write_text(json.dumps(request))
            result_dir = output / name
            # Abrupt child termination releases the real process-held file lock.
            fault = """import json,os,sys
from pathlib import Path
from betelgeuze_product.cpu_refinement_v1_2 import resumable_workflow as w
original = w._publish
def interrupt(path, value):
    if path.name == sys.argv[3]:
        path.with_name(path.name + '.partial').write_bytes(b'{"interrupted":')
        os._exit(73)
    return original(path, value)
w._publish = interrupt
w.run_resumable_request(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
"""
            run(
                ["-c", fault, str(request_file), str(result_dir), stage],
                expected_returncode=73,
            )
            partial = result_dir / (stage + ".partial")
            fragment = partial.read_bytes()
            saved = {
                p.relative_to(result_dir): p.read_bytes()
                for p in (result_dir / "candidates").rglob("*.json")
            }
            run(
                [
                    "-m",
                    "betelgeuze_product.cpu_refinement_v1_2",
                    "run-resumable",
                    str(request_file),
                    "--output",
                    str(result_dir),
                    "--resume",
                ]
            )
            assert saved == {p: (result_dir / p).read_bytes() for p in saved}
            archive = result_dir / (
                "interrupted-" + stage + "-" + hashlib.sha256(fragment).hexdigest()
            )
            assert archive.read_bytes() == fragment and not partial.exists()
            report = json.loads((result_dir / "report.json").read_text())
            assert report["implementation_sources"] == expected
            if stage == "report.json":
                assert all(
                    c["new_candidates"]
                    == c["new_force_calls"]
                    == c["new_score_calls"]
                    == 0
                    for c in report["summary"]["costs"].values()
                )
            inputs.rename(output / (name + "-inputs-moved"))
            verification = run(
                [
                    "-m",
                    "betelgeuze_product.cpu_refinement_v1_2",
                    "verify-resumable",
                    str(result_dir),
                ]
            )
            assert verification["structural_verification_passed"]
            recoveries.append(
                dict(
                    mode=report["summary"]["mode"],
                    stage=stage,
                    exitcode=73,
                    candidate_files_unchanged=True,
                    archive_sha256=hashlib.sha256(fragment).hexdigest(),
                )
            )
    result = {
        "recoveries": recoveries,
        "probe": probe,
        "modes": observations,
        "isolated_python": True,
        "pythonpath_removed": True,
        "outside_checkout": True,
        "scientifically_validated": False,
    }
    (output / "verification.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.python, args.output), indent=2))

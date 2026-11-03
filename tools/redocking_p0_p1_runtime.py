"""Build and attest one frozen CPU runtime for P0/P1 development jobs."""

from __future__ import annotations

import argparse
from importlib import metadata
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from tools import redocking_evidence_support as evidence
from tools.run_redocking_development_stages import (
    digest_file,
    download_inputs,
    read_json,
    require,
    rmsd_contract_test,
    utc_now,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/redocking_p0_p1_20261104.json"
NATIVE_REQUIREMENTS = ROOT / "config/gnina_runtime_cudnn_cu12.txt"
NATIVE_LIBRARIES = (
    "libcudnn.so.9",
    "libcudart.so.12",
    "libcublas.so.12",
    "libcublasLt.so.12",
    "libcufft.so.11",
    "libcurand.so.10",
    "libcusolver.so.11",
    "libcusparse.so.12",
    "libnvToolsExt.so.1",
    "libnvJitLink.so.12",
)


def command(args, *, timeout=900):
    subprocess.run(
        [str(value) for value in args], cwd=ROOT, check=True, timeout=timeout
    )


def resolve(bundle_root):
    """Resolve once before docking; every worker then installs these wheel bytes."""
    bundle_root.mkdir(parents=True, exist_ok=True)
    wheelhouse = bundle_root / "evaluator"
    require(not wheelhouse.exists(), "refuse to overwrite a resolved wheelhouse")
    wheelhouse.mkdir()
    pins = read_json(MANIFEST)["evaluator_pins"]
    common = [
        f"{name}=={version}"
        for name, version in pins.items()
        if name not in {"posebusters", "torch"}
    ]
    base = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--only-binary=:all:",
        "--dest",
        wheelhouse,
    ]
    command(
        [
            *base,
            "--index-url",
            "https://pypi.org/simple",
            "--extra-index-url",
            "https://download.pytorch.org/whl/cpu",
            *common,
            "torch==" + pins["torch"],
        ]
    )
    # PoseBusters names its dependency `rdkit`; the frozen distribution is rdkit-pypi.
    command(
        [
            *base,
            "--index-url",
            "https://pypi.org/simple",
            "--no-deps",
            "posebusters==" + pins["posebusters"],
        ]
    )
    frozen = evidence.freeze_wheelhouse(wheelhouse, expected_versions=pins)
    write_json(wheelhouse / "wheelhouse-manifest.json", frozen)
    (wheelhouse / "requirements-hashed.txt").write_text(
        evidence.hashed_requirements(frozen)
    )
    write_json(
        bundle_root / "resolution.json",
        {
            "resolved_at": utc_now(),
            "before_molecular_execution": True,
            "python": platform.python_version(),
            "required_pins": pins,
            "wheel_set_sha256": frozen["wheel_set_sha256"],
            "policy": "one joint dependency solve including exact CPU Torch; PoseBusters separately downloaded with no dependencies; exact complete wheel set shared with every job",
        },
    )


def install_evaluator(bundle_root):
    wheelhouse = bundle_root / "evaluator"
    frozen = read_json(wheelhouse / "wheelhouse-manifest.json")
    evidence.verify_wheelhouse(wheelhouse, frozen)
    require(
        sys.prefix != sys.base_prefix, "installation requires a fresh dedicated venv"
    )
    command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-compile",
            "--no-index",
            "--find-links",
            wheelhouse,
            "--require-hashes",
            "--no-deps",
            "-r",
            wheelhouse / "requirements-hashed.txt",
        ]
    )
    actual = {
        re.sub(r"[-_.]+", "-", d.metadata["Name"]).lower(): d.version
        for d in metadata.distributions()
    }
    require(
        actual == frozen["distributions"],
        "active distribution set differs from frozen wheel set",
    )


def native_runtime(bundle_root, native_root, output_root, *, create_reference=False):
    require(not native_root.exists(), "native runtime target must be fresh")
    if not create_reference:
        require(
            all(
                (bundle_root / name).is_file()
                for name in ("native-wheelhouse-manifest.json", "native-runtime.json")
            ),
            "worker bundle is missing a bootstrap native reference",
        )
    output_root.mkdir(parents=True, exist_ok=True)
    wheels = native_root.with_name(native_root.name + "-wheels")
    require(not wheels.exists(), "native wheel target must be fresh")
    wheels.mkdir(parents=True)
    command(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--index-url",
            "https://pypi.org/simple",
            "--only-binary=:all:",
            "--require-hashes",
            "--no-deps",
            "--dest",
            wheels,
            "-r",
            NATIVE_REQUIREMENTS,
        ]
    )
    frozen = evidence.freeze_wheelhouse(wheels)
    require(
        len(frozen["files"]) == 9,
        "GNINA native wheel set must contain exactly nine wheels",
    )
    reference_path = bundle_root / "native-wheelhouse-manifest.json"
    if reference_path.exists():
        require(
            read_json(reference_path) == frozen, "native wheel set differs across jobs"
        )
    else:
        require(
            create_reference,
            "worker bundle is missing the bootstrap native wheel manifest",
        )
        write_json(reference_path, frozen)
    write_json(output_root / "native-wheelhouse-manifest.json", frozen)
    command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            wheels,
            "--only-binary=:all:",
            "--require-hashes",
            "--no-deps",
            "--no-compile",
            "--target",
            native_root,
            "-r",
            NATIVE_REQUIREMENTS,
        ]
    )
    for name in NATIVE_LIBRARIES:
        require(len(list(native_root.rglob(name))) == 1, "expected exactly one " + name)
    paths = sorted(path for path in native_root.rglob("*.so*") if path.is_file())
    rows = [
        {
            "path": str(path.relative_to(native_root)),
            "size": path.stat().st_size,
            "sha256": digest_file(path),
        }
        for path in paths
    ]
    native_report = {
        "loader_only": True,
        "distributions": frozen["distributions"],
        "wheel_set_sha256": frozen["wheel_set_sha256"],
        "libraries": rows,
    }
    reference_libraries = bundle_root / "native-runtime.json"
    if reference_libraries.exists():
        require(
            read_json(reference_libraries) == native_report,
            "native installed library bytes differ",
        )
    else:
        require(
            create_reference,
            "worker bundle is missing the bootstrap native library inventory",
        )
        write_json(reference_libraries, native_report)
    write_json(output_root / "native-runtime.json", native_report)
    library_path = ":".join(sorted({str(path.parent) for path in paths}))
    if os.environ.get("LD_LIBRARY_PATH"):
        library_path += ":" + os.environ["LD_LIBRARY_PATH"]
    with open(os.environ["GITHUB_ENV"], "a") as stream:
        stream.write("LD_LIBRARY_PATH=" + library_path + "\n")
    # Wheel bytes are reproducible from the pinned requirement and retained manifest.
    shutil.rmtree(wheels)


def source_files():
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    prefixes = (
        "betelgeuze_engine_v2/",
        "benchmarks/oracles/",
        "tools/",
        "config/",
        ".github/workflows/",
    )
    return {
        name: ROOT / name
        for name in tracked
        if name.startswith(prefixes)
        and (ROOT / name).is_file()
        and (name.endswith((".py", ".json", ".yml", ".txt")))
    }


def environment_snapshot(bundle_root):
    frozen = read_json(bundle_root / "evaluator/wheelhouse-manifest.json")
    return evidence.snapshot_environment(
        frozen["distributions"], source_files=source_files(), wheelhouse_manifest=frozen
    )


def check_environment(reference, observed, output):
    comparison = evidence.compare_environments(reference, observed)
    write_json(output, comparison)
    evidence.require_matching_environment(reference, observed)


def preflight(bundle_root, input_root, output_root, *, create_reference=False):
    manifest = read_json(MANIFEST)
    output_root.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "preparing",
        "started_at": utc_now(),
        "environment_role": "bootstrap_reference"
        if create_reference
        else "worker_comparison",
        "manifest_sha256": digest_file(MANIFEST),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    try:
        if not create_reference:
            require(
                (bundle_root / "reference-environment.json").is_file(),
                "worker bundle is missing the bootstrap environment reference",
            )
        from tools import run_engine_v2_public_redocking_300 as runner
        import rdkit
        import torch

        require(
            platform.python_version() == manifest["python_version"],
            "Python version differs",
        )
        require(
            str(torch.__version__) == "2.6.0+cpu" and torch.version.cuda is None,
            "requires frozen CPU-only Torch",
        )
        require(rdkit.__version__ == "2022.09.5", "RDKit import version differs")
        try:
            metadata.distribution("rdkit")
        except metadata.PackageNotFoundError:
            pass
        else:
            raise RuntimeError("conflicting rdkit distribution is installed")
        record.update(
            evaluator_versions=runner._evaluator_environment_versions(),
            evaluator_payload_sha256s=runner._evaluator_distribution_payload_sha256s(),
            evaluation_pipeline_sha256=runner._evaluation_pipeline_sha256(ROOT),
            engine_source_sha256=runner._engine_source_sha256(ROOT),
            torch_version=str(torch.__version__),
            python=sys.version,
            platform=platform.platform(),
            host_cpu_count=os.cpu_count(),
            runner_image={
                k: os.environ.get(k)
                for k in ("ImageOS", "ImageVersion", "RUNNER_OS", "RUNNER_ARCH")
            },
            rmsd_semantics_test=rmsd_contract_test(),
        )
        check = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        record["pip_check"] = {
            "returncode": check.returncode,
            "stdout": check.stdout,
            "stderr": check.stderr,
        }
        if check.returncode:
            require(
                [s.strip().lower() for s in check.stdout.splitlines() if s.strip()]
                == ["posebusters 0.3.1 requires rdkit, which is not installed."],
                "unexpected package dependency conflict",
            )
        snapshot = environment_snapshot(bundle_root)
        write_json(output_root / "environment-start.json", snapshot)
        reference_path = bundle_root / "reference-environment.json"
        if reference_path.exists():
            check_environment(
                read_json(reference_path),
                snapshot,
                output_root / "environment-vs-reference.json",
            )
        else:
            require(
                create_reference,
                "worker bundle is missing the bootstrap environment reference",
            )
            write_json(reference_path, snapshot)
        record["environment_content_identity_sha256"] = snapshot[
            "content_identity_sha256"
        ]
        download_inputs(input_root, manifest)
        binary = input_root / manifest["inputs"]["gnina"]["filename"]
        linkage = subprocess.run(
            ["ldd", str(binary)], capture_output=True, text=True, timeout=30
        )
        record["gnina_ldd"] = {
            "returncode": linkage.returncode,
            "stdout": linkage.stdout,
            "stderr": linkage.stderr,
        }
        require(
            linkage.returncode == 0 and "not found" not in linkage.stdout,
            "unresolved GNINA library",
        )
        linked = {}
        for line in linkage.stdout.splitlines():
            parts = line.split()
            if "=>" in parts:
                target = parts[parts.index("=>") + 1]
                if target.startswith("/") and Path(target).is_file():
                    linked[target] = digest_file(target)
        record["gnina_linked_library_sha256s"] = linked
        probe = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=30
        )
        record["gnina_version_probe"] = {
            "returncode": probe.returncode,
            "stdout": probe.stdout,
            "stderr": probe.stderr,
        }
        require(probe.returncode == 0, "GNINA version/loader probe failed")
        record.update(status="ready", input_specs=manifest["inputs"])
    except Exception as exc:
        record.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        record["finished_at"] = utc_now()
        write_json(output_root / "preflight.json", record)


def postflight(bundle_root, output_root):
    snapshot = environment_snapshot(bundle_root)
    write_json(output_root / "environment-end.json", snapshot)
    check_environment(
        read_json(output_root / "environment-start.json"),
        snapshot,
        output_root / "environment-start-vs-end.json",
    )


def run_tests(output_root):
    output_root.mkdir(parents=True, exist_ok=True)
    selected = [
        ROOT / "tests/unit" / (name + ".py")
        for name in (
            "test_engine_v2_public_redocking_runner_stage7",
            "test_engine_v2_public_redocking_benchmark_stage7",
            "test_engine_v2_scorer_v1_stage5",
            "test_engine_v2_element_contact_round8",
            "test_source_paired_torsion_rescue_activation_snapshot",
            "test_source_paired_clearance_activation",
        )
    ]
    for pattern in (
        "test_p1_redocking*.py",
        "test_redocking_evidence_support*.py",
        "test_redocking_isolation*.py",
        "test_analyze_redocking_p0_p1*.py",
        "test_redocking_p0_p1_runtime.py",
    ):
        matches = sorted((ROOT / "tests").rglob(pattern))
        require(matches, "required P0/P1 test family is absent: " + pattern)
        selected.extend(matches)
    command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *selected,
            "--junitxml=" + str(output_root / "tests.xml"),
        ],
        timeout=900,
    )
    nodes = [
        node
        for node in ET.parse(output_root / "tests.xml").iter("testcase")
        if node.attrib.get("name")
        == "test_frozen_posebusters_top5_reuse_matches_fresh_evaluation"
    ]
    require(
        len(nodes) == 1 and nodes[0].find("skipped") is None,
        "frozen PoseBusters equivalence test must execute, not skip",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "resolve",
            "install-evaluator",
            "native",
            "preflight",
            "postflight",
            "tests",
        ),
    )
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--native-root", type=Path)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--create-reference", action="store_true")
    args = parser.parse_args()
    require(
        not args.create_reference or args.operation in {"native", "preflight"},
        "bootstrap reference creation is only available for native/preflight",
    )
    if args.operation == "resolve":
        resolve(args.bundle_root)
    elif args.operation == "install-evaluator":
        install_evaluator(args.bundle_root)
    elif args.operation == "native":
        require(args.native_root and args.output_root, "native/output roots required")
        native_runtime(
            args.bundle_root,
            args.native_root,
            args.output_root,
            create_reference=args.create_reference,
        )
    elif args.operation == "preflight":
        require(args.input_root and args.output_root, "input/output roots required")
        preflight(
            args.bundle_root,
            args.input_root,
            args.output_root,
            create_reference=args.create_reference,
        )
    elif args.operation == "tests":
        require(args.output_root, "output root required")
        run_tests(args.output_root)
    else:
        require(args.output_root, "output root required")
        postflight(args.bundle_root, args.output_root)


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from tools import check_external_oracle_architecture as architecture


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "tools" / "check_external_oracle_architecture.py"


def _codes(violations: list[object]) -> set[str]:
    return {str(getattr(violation, "code")) for violation in violations}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_packaging(root: Path) -> None:
    _write(
        root / ".dockerignore",
        "\n".join(
            (
                "*",
                "benchmarks",
                "benchmarks/**",
                *sorted(architecture.LEGACY_BENCHMARK_DOCKER_EXCLUSIONS),
            )
        )
        + "\n",
    )
    _write(
        root / "Dockerfile.product",
        "FROM scratch\n"
        "RUN test ! -e /app/benchmarks && python "
        "tools/check_external_oracle_architecture.py --root /app --product-image\n",
    )
    pyproject = (
        "[build-system]\n"
        'requires = ["setuptools"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        'name = "fixture"\n'
        'version = "0.0.0"\n\n'
        "[tool.setuptools.packages.find]\n"
        'include = ["api*"]\n'
        'exclude = ["benchmarks*"]\n'
    )
    _write(root / "pyproject.toml", pyproject)
    _write(root / "packaging/engine-v2/pyproject.toml", pyproject)


def test_repository_satisfies_external_oracle_boundary() -> None:
    violations = architecture.inspect_repository(ROOT)
    assert violations == [], "\n" + "\n".join(
        violation.render() for violation in violations
    )


def test_scientific_qualification_tools_are_product_image_exclusions() -> None:
    assert {
        "tools/run_docking_search_v2_development_cohort.py",
        "tools/run_engine_v2_cpu_performance_qualification.py",
        "tools/run_engine_v2_cpu_performance_qualification_v3.py",
        "tools/benchmarking/__init__.py",
        "tools/benchmarking/build_docking_search_v2_development_evidence.py",
    }.issubset(architecture.LEGACY_BENCHMARK_DOCKER_EXCLUSIONS)


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("import openmm\n", "external_python_import_outside_oracle"),
        (
            'from importlib import import_module\nengine = import_module("gnina")\n',
            "external_dynamic_import_outside_oracle",
        ),
        (
            'import subprocess\nsubprocess.run(["gmx", "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            "from subprocess import run\n"
            'run(["/opt/oracles/gnina", "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            "import subprocess as process\n"
            'process.check_call(["/usr/local/bin/gmx", "--version"])\n',
            "external_process_outside_oracle",
        ),
        (
            "import subprocess\n"
            'binary = "/opt/oracles/gnina"\n'
            'subprocess.run([binary, "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            "from pathlib import Path\n"
            "import subprocess\n"
            'binary = Path("/opt/oracles/gnina")\n'
            'subprocess.run([str(binary), "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            "import shutil\n"
            "import subprocess\n"
            'binary = shutil.which("gnina")\n'
            'subprocess.run([binary, "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            "import subprocess\n"
            'subprocess.run(args=["gnina", "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            'from subprocess import run\nrun(["gni" "na", "--version"], check=False)\n',
            "external_process_outside_oracle",
        ),
        (
            'import importlib\nengine = importlib.import_module("open" + "mm")\n',
            "external_dynamic_import_outside_oracle",
        ),
        (
            "engine = __import__(f\"{'gni'}na\")\n",
            "external_dynamic_import_outside_oracle",
        ),
        (
            'engine = __import__("{}{}".format("vi", "na"))\n',
            "external_dynamic_import_outside_oracle",
        ),
        (
            'engine = __import__("".join(("gni", "na")))\n',
            "external_dynamic_import_outside_oracle",
        ),
        (
            "import asyncio\n"
            "async def launch():\n"
            '    await asyncio.create_subprocess_exec("gni" + "na", "--version")\n',
            "external_process_outside_oracle",
        ),
        (
            "from asyncio import create_subprocess_shell as launch\n"
            "async def run():\n"
            "    await launch(f\"{'gmx'} --version\")\n",
            "external_process_outside_oracle",
        ),
        (
            "import subprocess\n"
            'subprocess.run(["echo"], executable="/opt/gni" + "na")\n',
            "external_process_outside_oracle",
        ),
        (
            'import ctypes as ffi\nffi.CDLL("/opt/libOpen" + "MM.so")\n',
            "external_native_library_outside_oracle",
        ),
        (
            "from ctypes import PyDLL as load\n"
            'library = "lib" + "gromacs.so"\n'
            "load(library)\n",
            "external_native_library_outside_oracle",
        ),
        (
            "import subprocess\n"
            "launch = subprocess.run\n"
            'launch(["vina", "--version"])\n',
            "external_process_outside_oracle",
        ),
        (
            'import ctypes\nctypes.cdll.LoadLibrary("libOpenMM.so")\n',
            "external_native_library_outside_oracle",
        ),
        (
            'import subprocess\ngetattr(subprocess, "run")(["vina", "--version"])\n',
            "external_process_outside_oracle",
        ),
        (
            'exec("import openmm")\n',
            "external_dynamic_code_outside_oracle",
        ),
        (
            "eval(\"__import__('gnina')\")\n",
            "external_dynamic_code_outside_oracle",
        ),
        (
            'import ctypes\ngetattr(ctypes, "CDLL")("libOpenMM.so")\n',
            "external_native_library_outside_oracle",
        ),
        (
            "import builtins\nbuiltins.__import__('openmm')\n",
            "external_dynamic_import_outside_oracle",
        ),
        (
            "import builtins\ngetattr(builtins, '__import__')('gnina')\n",
            "external_dynamic_import_outside_oracle",
        ),
        (
            "import builtins\n"
            "load_module = getattr(builtins, '__import__')\n"
            "load_module('vina')\n",
            "external_dynamic_import_outside_oracle",
        ),
    ],
)
def test_python_boundary_mutations_fail_closed(
    tmp_path: Path,
    source: str,
    expected_code: str,
) -> None:
    _write(tmp_path / "tools/bad_adapter.py", source)
    violations = architecture.inspect_python_boundary(tmp_path)
    assert expected_code in _codes(violations)


def test_external_imports_are_allowed_inside_oracle_pack(tmp_path: Path) -> None:
    _write(
        tmp_path / "benchmarks/oracles/openmm/adapter.py",
        "import openmm\n",
    )
    _write(
        tmp_path / "benchmarks/oracles/gromacs/adapter.py",
        "import subprocess\nsubprocess.run(['gmx', '--version'], check=False)\n",
    )
    assert architecture.inspect_python_boundary(tmp_path) == []


@pytest.mark.parametrize(
    "source",
    [
        'import ctypes\nctypes.WinDLL("gnina.dll")\n',
        'import ctypes\nctypes.OleDLL("vina.dll")\n',
        'import ctypes\nctypes.pydll.LoadLibrary("libgromacs.so")\n',
        'import ctypes\nctypes.windll.LoadLibrary("OpenMM.dll")\n',
        'import ctypes\nctypes.oledll.LoadLibrary("vina.dll")\n',
        "from ctypes import cdll\ncdll.libgnina\n",
    ],
)
def test_ctypes_loader_family_mutations_fail_closed(
    tmp_path: Path,
    source: str,
) -> None:
    _write(tmp_path / "api/bad_loader.py", source)
    violations = architecture.inspect_python_boundary(tmp_path)
    assert "external_native_library_outside_oracle" in _codes(violations)


@pytest.mark.parametrize(
    ("function", "call"),
    [
        ("spawnl", 'os.spawnl(os.P_WAIT, "/opt/vina", "vina")'),
        ("spawnle", 'os.spawnle(os.P_WAIT, "/opt/vina", "vina", {})'),
        ("spawnlp", 'os.spawnlp(os.P_WAIT, "gmx", "gmx")'),
        ("spawnlpe", 'os.spawnlpe(os.P_WAIT, "gmx", "gmx", {})'),
        ("spawnv", 'os.spawnv(os.P_WAIT, "/opt/gnina", ["gnina"])'),
        ("spawnve", 'os.spawnve(os.P_WAIT, "/opt/gnina", ["gnina"], {})'),
        ("spawnvp", 'os.spawnvp(os.P_WAIT, "gmx_mpi", ["gmx_mpi"])'),
        ("spawnvpe", 'os.spawnvpe(os.P_WAIT, "gmx_d", ["gmx_d"], {})'),
        ("posix_spawn", 'os.posix_spawn("/opt/vina", ["vina"], {})'),
        ("posix_spawnp", 'os.posix_spawnp("gnina", ["gnina"], {})'),
    ],
)
def test_os_spawn_family_mutations_fail_closed(
    tmp_path: Path,
    function: str,
    call: str,
) -> None:
    _write(tmp_path / "tools/bad_spawn.py", f"import os\n{call}\n")
    violations = architecture.inspect_python_boundary(tmp_path)
    assert "external_process_outside_oracle" in _codes(violations), function


def test_aliased_os_spawn_mutation_fails_closed(tmp_path: Path) -> None:
    _write(
        tmp_path / "tools/bad_spawn_alias.py",
        "from os import P_WAIT, spawnvp as launch\n"
        'launch(P_WAIT, "gmx", ["gmx", "--version"])\n',
    )
    violations = architecture.inspect_python_boundary(tmp_path)
    assert "external_process_outside_oracle" in _codes(violations)


@pytest.mark.parametrize(
    "source",
    [
        "#!/bin/sh\ngnina --version\n",
        "#!/bin/sh\nexec /opt/gmx --version\n",
        '#!/bin/sh\ncommand -p gni""na --version\n',
        '#!/bin/sh\nBIN=/opt/vina; exec "$BIN" --version\n',
        "#!/bin/sh\nenv vina --version\n",
        "#!/bin/sh\nnice -n 5 env command gnina --version\n",
        "#!/bin/sh\nsh -c 'vina --version'\n",
        "#!/bin/sh\nbash -lc 'env gnina --version'\n",
        "#!/bin/sh\ndash -c 'gmx --version'\n",
        "#!/bin/sh\nzsh -c 'command vina --version'\n",
        "#!/bin/sh\nksh -c 'nice gnina --version'\n",
        '#!/bin/sh\nPAYLOAD="$1"\nsh -c "$PAYLOAD"\n',
    ],
)
def test_product_shell_external_process_mutations_fail_closed(
    tmp_path: Path,
    source: str,
) -> None:
    _write(tmp_path / "tools/bad_adapter.sh", source)
    violations = architecture.inspect_shell_boundary(tmp_path)
    assert "external_shell_process_outside_oracle" in _codes(violations)


def test_shell_queries_and_quoted_prose_are_not_execution(tmp_path: Path) -> None:
    _write(
        tmp_path / "tools/safe.sh",
        "#!/bin/sh\ncommand -v gnina\necho 'command gmx'\n",
    )
    assert architecture.inspect_shell_boundary(tmp_path) == []


def test_safe_shell_c_payload_is_allowed(tmp_path: Path) -> None:
    _write(tmp_path / "tools/safe_shell_c.sh", "#!/bin/sh\nsh -c 'echo ok'\n")
    assert architecture.inspect_shell_boundary(tmp_path) == []


def test_external_shell_process_is_allowed_inside_oracle_pack(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "benchmarks/oracles/gromacs/run.sh",
        "#!/bin/sh\nexec gmx --version\n",
    )
    assert architecture.inspect_shell_boundary(tmp_path) == []


def test_product_transitive_import_of_oracle_fails_closed(tmp_path: Path) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(tmp_path / "api/main.py", "from support import bridge\n")
    _write(
        tmp_path / "support/bridge.py",
        "from benchmarks.oracles.openmm import adapter\n",
    )
    _write(tmp_path / "benchmarks/__init__.py", "")
    _write(tmp_path / "benchmarks/oracles/__init__.py", "")
    _write(tmp_path / "benchmarks/oracles/openmm/__init__.py", "")
    _write(tmp_path / "benchmarks/oracles/openmm/adapter.py", "")

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert "product_imports_external_oracle" in _codes(violations)
    assert any("api.main -> support.bridge" in item.detail for item in violations)


@pytest.mark.parametrize(
    "source",
    [
        "import builtins\nbuiltins.__import__('benchmarks.oracles.openmm')\n",
        "import builtins\n"
        "load_module = getattr(builtins, '__import__')\n"
        "load_module('benchmarks.oracles.openmm')\n",
    ],
)
def test_builtins_import_cannot_bypass_product_closure(
    tmp_path: Path,
    source: str,
) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(tmp_path / "api/main.py", source)
    _write(tmp_path / "benchmarks/oracles/openmm/__init__.py", "")

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert "product_imports_external_oracle" in _codes(violations)


def test_product_nonliteral_dynamic_import_fails_closed(tmp_path: Path) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(
        tmp_path / "api/main.py",
        "import importlib\n"
        "import os\n"
        'name = "benchmarks." + os.environ.get("LAYER", "oracles")\n'
        "importlib.import_module(name)\n",
    )

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert "product_dynamic_import_unresolved" in _codes(violations)


def test_product_unresolved_exec_and_eval_fail_closed(tmp_path: Path) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(
        tmp_path / "api/main.py",
        "import os\n"
        'payload = os.environ.get("PRODUCT_CODE")\n'
        "exec(payload)\n"
        'eval(os.environ.get("PRODUCT_EXPRESSION"))\n',
    )

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert {
        item.line
        for item in violations
        if item.code == "product_dynamic_code_execution_unresolved"
    } == {3, 4}


def test_constant_safe_exec_does_not_trigger_product_boundary(tmp_path: Path) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(tmp_path / "api/main.py", 'exec("value = 1")\n')
    assert architecture.inspect_product_import_boundary(tmp_path) == []


def test_audited_full_pipeline_activation_loader_exception_is_narrow(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "tools/__init__.py", "")
    _write(
        tmp_path
        / "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        "def _load_source_module(code):\n"
        "    exec(code, {})\n"
        "def unreviewed_loader(payload):\n"
        "    exec(payload, {})\n",
    )

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert {
        item.line
        for item in violations
        if item.code == "product_dynamic_code_execution_unresolved"
    } == {4}


def test_new_loader_in_audited_module_does_not_inherit_exception(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "core/__init__.py", "")
    _write(
        tmp_path / "core/rust_hip_backend.py",
        "import importlib\n"
        "def unreviewed_loader(name):\n"
        "    return importlib.import_module(name)\n",
    )

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert "product_dynamic_import_unresolved" in _codes(violations)


def test_dynamic_import_with_proven_internal_prefix_is_allowed(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(
        tmp_path / "api/main.py",
        "import importlib\n"
        "import os\n"
        'name = "api.plugins." + os.environ.get("PLUGIN", "default")\n'
        "importlib.import_module(name)\n",
    )

    assert architecture.inspect_product_import_boundary(tmp_path) == []


def test_docker_included_customer_tool_cannot_import_oracle_pack(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "tools/new_customer_runner.py",
        "from benchmarks.oracles.openmm import adapter\n",
    )
    _write(tmp_path / "benchmarks/oracles/openmm/adapter.py", "")

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert "product_imports_external_oracle" in _codes(violations)
    assert any(item.path == "tools/new_customer_runner.py" for item in violations)


def test_explicit_legacy_benchmark_tool_is_not_a_product_import_root(
    tmp_path: Path,
) -> None:
    legacy = sorted(architecture.LEGACY_BENCHMARK_DOCKER_EXCLUSIONS)[0]
    _write(
        tmp_path / legacy,
        "from benchmarks.oracles.openmm import adapter\n",
    )
    _write(tmp_path / "benchmarks/oracles/openmm/adapter.py", "")

    assert architecture.inspect_product_import_boundary(tmp_path) == []


def test_customer_tool_reaching_excluded_wrapper_still_fails_closed(
    tmp_path: Path,
) -> None:
    legacy = "tools/product/generate_openmm_ca_md_references.py"
    assert legacy in architecture.LEGACY_BENCHMARK_DOCKER_EXCLUSIONS
    _write(
        tmp_path / legacy,
        "from benchmarks.oracles.openmm import adapter\n",
    )
    _write(
        tmp_path / "tools/new_customer_runner.py",
        "from tools.product import generate_openmm_ca_md_references\n",
    )
    _write(tmp_path / "benchmarks/oracles/openmm/adapter.py", "")

    violations = architecture.inspect_product_import_boundary(tmp_path)
    assert "product_imports_external_oracle" in _codes(violations)
    assert any(
        "tools.new_customer_runner -> "
        "tools.product.generate_openmm_ca_md_references" in item.detail
        for item in violations
    )


@pytest.mark.parametrize(
    ("relative", "source", "expected_code"),
    [
        (
            "requirements-package.txt",
            "openmm==8.4\n",
            "external_product_dependency",
        ),
        (
            "rust/product/Cargo.toml",
            '[package]\nname="fixture"\nversion="0.0.0"\n'
            '[dependencies]\nopenmm-sys="1"\n',
            "external_rust_dependency",
        ),
        (
            "native/CMakeLists.txt",
            "find_package(OpenMM REQUIRED)\n",
            "external_native_dependency",
        ),
        (
            "native/src/adapter.cpp",
            "#include <OpenMM.h>\n",
            "external_native_dependency",
        ),
        (
            "native/src/runtime_loader.c",
            'void *handle = dlopen("libOpenMM.so", 2);\n',
            "external_native_library_runtime_load",
        ),
        (
            "native/src/runtime_loader.cpp",
            'auto handle = LoadLibraryW(L"gromacs.dll");\n',
            "external_native_library_runtime_load",
        ),
        (
            "rust/product/src/runtime_loader.rs",
            'let library = unsafe { libloading::Library::new("libvina.so")? };\n',
            "external_native_library_runtime_load",
        ),
        (
            "native/src/multiline_loader.cpp",
            'void *handle = dlopen(\n    "libOpenMM.so",\n    2\n);\n',
            "external_native_library_runtime_load",
        ),
        (
            "rust/product/src/multiline_loader.rs",
            "let library = unsafe { libloading::Library::new(\n"
            '    "libvina.so"\n'
            ")? };\n",
            "external_native_library_runtime_load",
        ),
    ],
)
def test_product_dependency_mutations_fail_closed(
    tmp_path: Path,
    relative: str,
    source: str,
    expected_code: str,
) -> None:
    _write(tmp_path / relative, source)
    violations = architecture.inspect_dependency_boundary(tmp_path)
    assert expected_code in _codes(violations)


def test_dev_only_rust_dependency_does_not_become_product_dependency(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "rust/reference/Cargo.toml",
        '[package]\nname="fixture"\nversion="0.0.0"\n'
        '[dev-dependencies]\nopenmm-sys="1"\n',
    )
    assert architecture.inspect_dependency_boundary(tmp_path) == []


def test_packaging_mutations_detect_docker_and_wheel_leaks(tmp_path: Path) -> None:
    _minimal_packaging(tmp_path)
    assert architecture.inspect_packaging_boundary(tmp_path) == []

    dockerignore = tmp_path / ".dockerignore"
    lines = dockerignore.read_text(encoding="utf-8").splitlines()
    lines.remove("tools/run_engine_v2_public_redocking_300.py")
    dockerignore.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with_missing_rule = architecture.inspect_packaging_boundary(tmp_path)
    assert "oracle_docker_exclusion_missing" in _codes(with_missing_rule)

    _minimal_packaging(tmp_path)
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text(
        dockerignore.read_text(encoding="utf-8")
        + "!benchmarks/**\n"
        + "!tools/run_engine_v2_public_redocking_300.py\n",
        encoding="utf-8",
    )
    reintroduced = architecture.inspect_packaging_boundary(tmp_path)
    assert "oracle_docker_reincluded" in _codes(reintroduced)

    _minimal_packaging(tmp_path)
    _write(
        tmp_path / "Dockerfile.product",
        "FROM scratch\nCOPY benchmarks /app/benchmarks\n",
    )
    copied = architecture.inspect_packaging_boundary(tmp_path)
    assert "oracle_copied_into_product_image" in _codes(copied)

    _minimal_packaging(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'exclude = ["benchmarks*"]\n',
            "",
        ),
        encoding="utf-8",
    )
    wheel_leak = architecture.inspect_packaging_boundary(tmp_path)
    assert "oracle_wheel_exclusion_missing" in _codes(wheel_leak)


def test_product_image_mode_does_not_require_repository_only_files(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "api/__init__.py", "")
    _write(tmp_path / "api/main.py", "")
    _write(tmp_path / "pyproject.toml", "[project]\nname='image'\nversion='0'\n")
    assert architecture.inspect_repository(tmp_path, product_image=True) == []


def test_checker_cli_is_executable_source() -> None:
    assert CHECKER_PATH.is_file()
    assert shutil.which("python3") is not None

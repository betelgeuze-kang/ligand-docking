#!/usr/bin/env python3
"""Enforce the external-solver oracle and product dependency boundary.

OpenMM, GROMACS, Vina, and GNINA are validation oracles.  Their adapters may
live below ``benchmarks/oracles``; customer/product execution code must neither
import those adapters nor acquire the corresponding Python, native, or Rust
dependencies.

The checker deliberately parses source and dependency declarations instead of
grepping prose.  Documentation and result schemas may name an external engine
without becoming an executable dependency.
"""

from __future__ import annotations

import argparse
import ast
from collections import deque
from dataclasses import dataclass
import fnmatch
import os
from pathlib import Path
import re
import shlex
from typing import Iterator, Sequence


ORACLE_PREFIX = "benchmarks/oracles/"
ORACLE_MODULE_PREFIX = "benchmarks.oracles"

EXTERNAL_PYTHON_ROOTS = frozenset(
    {"openmm", "simtk", "gmxapi", "gromacs", "vina", "gnina"}
)
EXTERNAL_EXECUTABLES = frozenset(
    {"gmx", "gmx_d", "gmx_mpi", "gmx_mpi_d", "vina", "gnina"}
)
EXTERNAL_DEPENDENCY_ROOTS = frozenset(
    {
        "openmm",
        "simtk-openmm",
        "gmxapi",
        "gromacs",
        "vina",
        "autodock-vina",
        "gnina",
    }
)

PRODUCT_PACKAGE_ROOTS = frozenset(
    {
        "api",
        "core",
        "runtime",
        "train",
        "theory",
        "betelgeuze_engine",
        "betelgeuze_engine_v2",
        "betelgeuze_ai_md",
        "betelgeuze_product",
        "betelgeuze_cameo",
        "betelgeuze_cleanup",
    }
)
PRODUCT_ENTRYPOINTS = frozenset(
    {
        "tools/run_api_simulation_worker.py",
        "tools/run_api_docking_dispatch_worker.py",
        "tools/run_ligand_htvs_pipeline.py",
        "tools/run_ligand_backmapping_scoring.py",
        "tools/run_ligand_topk_delivery.py",
        "tools/run_tier_beta_vertical_slice.py",
    }
)

# This is the complete reverse import closure of external-oracle tooling, plus
# benchmark-only qualification loaders and historical dynamic-import
# compatibility shims.  The files remain available in source for benchmark
# reproduction but never enter the product context.
LEGACY_BENCHMARK_DOCKER_EXCLUSIONS = frozenset(
    {
        "tools/accounting/build_gpcr_drd2_full_forcefield_local_minimization_survival.py",
        "tools/accounting/build_gpcr_drd2_full_forcefield_minimization_readiness.py",
        "tools/accounting/build_gpcr_drd2_local_minimization_survival.py",
        "tools/accounting/build_gpcr_drd2_openmm_forcefield_parameterization_probe.py",
        "tools/accounting/build_gpcr_drd2_protein_amber14_parameterization_repair.py",
        "tools/accounting/build_tcruzi_pde_strict_external_manifest.py",
        "tools/accounting/build_wetlab_tcruzi_pde_atomized_parameterization_minimization_packet.py",
        "tools/build_engine_v2_solo_stage0_evidence.py",
        "tools/build_engine_v2_solo_stage0_policy.py",
        "tools/build_gpcr_drd2_full_forcefield_local_minimization_survival.py",
        "tools/build_gpcr_drd2_full_forcefield_minimization_readiness.py",
        "tools/build_gpcr_drd2_local_minimization_survival.py",
        "tools/build_gpcr_drd2_openmm_forcefield_parameterization_probe.py",
        "tools/build_gpcr_drd2_protein_amber14_parameterization_repair.py",
        "tools/build_tcruzi_pde_strict_external_manifest.py",
        "tools/build_wetlab_tcruzi_pde_atomized_parameterization_minimization_packet.py",
        "tools/benchmarking/__init__.py",
        "tools/benchmarking/build_docking_search_v2_development_evidence.py",
        "tools/cleanup/maintain_live_unseen_archives.py",
        "tools/generate_openmm_ca_md_references.py",
        "tools/gpcr_replay/build_gpcr_drd2_full_forcefield_local_minimization_survival.py",
        "tools/gpcr_replay/build_gpcr_drd2_local_minimization_survival.py",
        "tools/maintain_live_unseen_archives.py",
        "tools/product/generate_openmm_ca_md_references.py",
        "tools/product/run_live_unseen_protein_learning_loop.py",
        "tools/product/run_openmm_2bead_rebench.py",
        "tools/product/run_openmm_2bead_strict_release.py",
        "tools/product/run_strict_release_with_regression_gate.py",
        "tools/run_engine_v2_cpu_performance_qualification.py",
        "tools/run_engine_v2_cpu_performance_qualification_v3.py",
        "tools/run_engine_v2_public_redocking_300.py",
        "tools/run_docking_search_v2_development_cohort.py",
        "tools/run_live_unseen_protein_learning_loop.py",
        "tools/run_openmm_2bead_rebench.py",
        "tools/run_openmm_2bead_strict_release.py",
        "tools/run_strict_release_with_regression_gate.py",
        "tools/wetlab/build_tcruzi_pde_strict_external_manifest.py",
        "tools/wetlab/build_wetlab_tcruzi_pde_atomized_parameterization_minimization_packet.py",
    }
)

_SKIP_TOP_LEVEL = frozenset(
    {
        ".agents",
        ".betelgeuze",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "data",
        "dist",
        "final_result_summaries_2026-03-10",
        "logs",
        "models",
        "node_modules",
        "output",
        "results",
        "runs",
        "target",
        "tmp",
        "venv",
    }
)
_DYNAMIC_IMPORT_NAMES = frozenset(
    {"__import__", "builtins.__import__", "importlib.import_module", "import_module"}
)
_DYNAMIC_CODE_NAMES = frozenset({"builtins.eval", "builtins.exec", "eval", "exec"})
_PROCESS_CALL_NAMES = frozenset(
    {
        "asyncio.create_subprocess_exec",
        "asyncio.create_subprocess_shell",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.run",
        "os.execl",
        "os.execle",
        "os.execlp",
        "os.execlpe",
        "os.execv",
        "os.execve",
        "os.execvp",
        "os.execvpe",
        "os.posix_spawn",
        "os.posix_spawnp",
        "os.spawnl",
        "os.spawnle",
        "os.spawnlp",
        "os.spawnlpe",
        "os.spawnv",
        "os.spawnve",
        "os.spawnvp",
        "os.spawnvpe",
        "os.system",
    }
)
_SPAWN_MODE_FIRST_NAMES = frozenset(
    {
        "os.spawnl",
        "os.spawnle",
        "os.spawnlp",
        "os.spawnlpe",
        "os.spawnv",
        "os.spawnve",
        "os.spawnvp",
        "os.spawnvpe",
    }
)
_SUBPROCESS_CALL_NAMES = frozenset(
    {
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.run",
    }
)
_SHELL_COMMAND_WRAPPERS = frozenset(
    {
        "chrt",
        "command",
        "env",
        "exec",
        "ionice",
        "nice",
        "nohup",
        "setsid",
        "stdbuf",
        "sudo",
        "taskset",
        "time",
    }
)
_SHELL_INTERPRETERS = frozenset({"ash", "bash", "dash", "ksh", "mksh", "sh", "zsh"})
_CTYPES_LOADER_OBJECTS = frozenset(
    {"ctypes.cdll", "ctypes.oledll", "ctypes.pydll", "ctypes.windll"}
)
_CTYPES_LOADERS = frozenset(
    {
        "ctypes.CDLL",
        "ctypes.OleDLL",
        "ctypes.PyDLL",
        "ctypes.WinDLL",
        *(f"{loader}.LoadLibrary" for loader in _CTYPES_LOADER_OBJECTS),
    }
)
_EXTERNAL_LIBRARY_RE = re.compile(
    r"(?i)(?:^|lib)(openmm|gromacs|gmxapi|vina|gnina)(?:$|[._-])"
)
_NATIVE_DYNAMIC_LOADER_CALL_RE = re.compile(
    r"\b(?:dlm?open|LoadLibrary(?:Ex)?[AW]?)\s*\("
    r"(?P<arguments>[\s\S]{0,4096}?)\)"
)
_RUST_DYNAMIC_LOADER_CALL_RE = re.compile(
    r"\b(?:libloading(?:::[A-Za-z_][A-Za-z0-9_]*)*::)?"
    r"Library::(?:load|new|open)\s*\("
    r"(?P<arguments>[\s\S]{0,4096}?)\)"
)
# Pre-existing internal extension/compatibility probes whose dynamic target is
# intentionally a runtime parameter.  Unresolved imports are denied everywhere
# else; keep this audit surface keyed by module, enclosing function, and exact
# argument name so a new loader in the same file does not inherit an exception.
_AUDITED_UNRESOLVED_DYNAMIC_IMPORTS = frozenset(
    {
        ("core.rust_hip_backend", "probe_rust_hip_backend", "module_name"),
        ("core.rust_hip_backend", "__init__", "module_name"),
        ("tools.check_rust_hip_engine", "_smoke_hip_add", "module_name"),
        (
            "tools.product.build_ai_md_engine_kpi_report",
            "_core_compatibility_layer_kpi",
            "legacy_module_name",
        ),
        (
            "tools.product.build_ai_md_engine_kpi_report",
            "_core_compatibility_layer_kpi",
            "canonical_module_name",
        ),
        (
            "tools.product.build_ai_md_engine_kpi_report",
            "_allowlisted_runner_shim_contract_kpi",
            "legacy_import",
        ),
        (
            "tools.product.build_ai_md_engine_kpi_report",
            "_allowlisted_runner_shim_contract_kpi",
            "adapter_import",
        ),
        (
            "tools.product.build_engine_refinement_tier_readiness",
            "_module_importable",
            "module_name",
        ),
    }
)
_AUDITED_UNRESOLVED_DYNAMIC_CODE = frozenset(
    {
        (
            "betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap",
            "exec_module",
            "code",
        ),
    }
)
_CMAKE_EXTERNAL_RE = re.compile(
    r"(?i)(?:\bopenmm\b|\bgromacs\b|\bgmxapi\b|\bgnina\b|\bautodock[-_]?vina\b|\blibvina\b)"
)
_FILE_CACHE: dict[Path, tuple[Path, ...]] = {}
_PYTHON_CACHE: dict[
    tuple[Path, Path], tuple[ast.Module | None, tuple[Violation, ...]]
] = {}
_UNKNOWN_CONSTANT = object()


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    line: int
    code: str
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.detail}"


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    if not parts:
        return False
    first = parts[0]
    return (
        first in _SKIP_TOP_LEVEL
        or first.startswith("build")
        or parts[:2] == ("tools", "bin")
        or "site-packages" in parts
        or "__pycache__" in parts
        or any(part.startswith(".") and part != ".github" for part in parts)
    )


def _iter_files(root: Path, pattern: str) -> Iterator[Path]:
    root = root.resolve()
    cached = _FILE_CACHE.get(root)
    if cached is None:
        discovered: list[Path] = []
        for directory, names, files in os.walk(root, topdown=True):
            directory_path = Path(directory)
            retained: list[str] = []
            for name in names:
                candidate = directory_path / name
                if not _is_skipped(candidate, root):
                    retained.append(name)
            names[:] = retained
            for name in files:
                path = directory_path / name
                if not _is_skipped(path, root):
                    discovered.append(path)
        cached = tuple(sorted(discovered))
        _FILE_CACHE[root] = cached
    for path in cached:
        if path.match(pattern):
            yield path


def _parse_python(path: Path, root: Path) -> tuple[ast.Module | None, list[Violation]]:
    key = (path.resolve(), root.resolve())
    cached = _PYTHON_CACHE.get(key)
    if cached is not None:
        return cached[0], list(cached[1])
    relative = _relative(path, root)
    try:
        source = path.read_text(encoding="utf-8")
        result: tuple[ast.Module | None, tuple[Violation, ...]] = (
            ast.parse(source, filename=relative),
            (),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        line = int(getattr(exc, "lineno", 0) or 0)
        result = (
            None,
            (Violation(relative, line, "python_parse_error", str(exc)),),
        )
    _PYTHON_CACHE[key] = result
    return result[0], list(result[1])


def _dotted_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value, aliases)
        name = f"{prefix}.{node.attr}" if prefix else node.attr
    else:
        return ""
    first, separator, remainder = name.partition(".")
    target = aliases.get(first, first)
    return f"{target}.{remainder}" if separator else target


def _aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".", 1)[0]] = item.name
        elif isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            for item in node.names:
                aliases[item.asname or item.name] = (
                    f"{module}.{item.name}" if module else item.name
                )
    callable_targets = {
        *_DYNAMIC_IMPORT_NAMES,
        *_DYNAMIC_CODE_NAMES,
        *_PROCESS_CALL_NAMES,
        *_CTYPES_LOADERS,
    }
    constants = _constant_bindings(tree)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            dotted = _callable_name(value, aliases, constants)
            if dotted not in callable_targets:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases[target.id] = dotted
                    changed = True
    return aliases


def _constant_value(
    node: ast.AST,
    constants: dict[str, object] | None = None,
) -> object:
    """Fold a deliberately small, side-effect-free Python constant subset."""

    bindings = constants or {}
    if isinstance(node, ast.Constant) and isinstance(
        node.value, (str, int, float, bool, type(None))
    ):
        return node.value
    if isinstance(node, ast.Name):
        return bindings.get(node.id, _UNKNOWN_CONSTANT)
    if isinstance(node, (ast.List, ast.Tuple)):
        values = tuple(_constant_value(item, bindings) for item in node.elts)
        if any(value is _UNKNOWN_CONSTANT for value in values):
            return _UNKNOWN_CONSTANT
        return values
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_value(node.left, bindings)
        right = _constant_value(node.right, bindings)
        if isinstance(left, str) and isinstance(right, str):
            result = left + right
            return result if len(result) <= 8192 else _UNKNOWN_CONSTANT
        return _UNKNOWN_CONSTANT
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value_node in node.values:
            if isinstance(value_node, ast.Constant) and isinstance(
                value_node.value, str
            ):
                parts.append(value_node.value)
                continue
            if not isinstance(value_node, ast.FormattedValue):
                return _UNKNOWN_CONSTANT
            value = _constant_value(value_node.value, bindings)
            if value is _UNKNOWN_CONSTANT:
                return _UNKNOWN_CONSTANT
            if value_node.conversion == ord("r"):
                rendered = repr(value)
            elif value_node.conversion == ord("a"):
                rendered = ascii(value)
            else:
                rendered = str(value)
            if value_node.format_spec is not None:
                spec = _constant_value(value_node.format_spec, bindings)
                if not isinstance(spec, str):
                    return _UNKNOWN_CONSTANT
                try:
                    rendered = format(value, spec)
                except (TypeError, ValueError):
                    return _UNKNOWN_CONSTANT
            parts.append(rendered)
        result = "".join(parts)
        return result if len(result) <= 8192 else _UNKNOWN_CONSTANT
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return _UNKNOWN_CONSTANT

    receiver = _constant_value(node.func.value, bindings)
    if node.func.attr == "join" and isinstance(receiver, str):
        if len(node.args) != 1 or node.keywords:
            return _UNKNOWN_CONSTANT
        values = _constant_value(node.args[0], bindings)
        if not isinstance(values, tuple) or not all(
            isinstance(value, str) for value in values
        ):
            return _UNKNOWN_CONSTANT
        result = receiver.join(values)
        return result if len(result) <= 8192 else _UNKNOWN_CONSTANT
    if node.func.attr == "format" and isinstance(receiver, str):
        arguments = tuple(_constant_value(item, bindings) for item in node.args)
        if any(value is _UNKNOWN_CONSTANT for value in arguments):
            return _UNKNOWN_CONSTANT
        keywords: dict[str, object] = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                return _UNKNOWN_CONSTANT
            value = _constant_value(keyword.value, bindings)
            if value is _UNKNOWN_CONSTANT:
                return _UNKNOWN_CONSTANT
            keywords[keyword.arg] = value
        try:
            result = receiver.format(*arguments, **keywords)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return _UNKNOWN_CONSTANT
        return result if len(result) <= 8192 else _UNKNOWN_CONSTANT
    return _UNKNOWN_CONSTANT


def _constant_string(
    node: ast.AST,
    constants: dict[str, object] | None = None,
) -> str:
    value = _constant_value(node, constants)
    return value if isinstance(value, str) else ""


def _callable_name(
    node: ast.AST,
    aliases: dict[str, str],
    constants: dict[str, object] | None = None,
) -> str:
    if isinstance(node, ast.Call):
        constructor = _dotted_name(node.func, aliases)
        if constructor in {"builtins.getattr", "getattr"} and len(node.args) >= 2:
            owner = _callable_name(node.args[0], aliases, constants)
            attribute = _constant_string(node.args[1], constants)
            if owner and attribute.isidentifier():
                return f"{owner}.{attribute}"
        return ""
    return _dotted_name(node, aliases)


def _scope_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    stack = list(reversed(list(ast.iter_child_nodes(scope))))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _constant_bindings(
    scope: ast.AST,
    inherited: dict[str, object] | None = None,
) -> dict[str, object]:
    bindings = dict(inherited or {})
    changed = True
    while changed:
        changed = False
        for node in _scope_nodes(scope):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value_node = node.value
            if value_node is None:
                continue
            value = _constant_value(value_node, bindings)
            if value is _UNKNOWN_CONSTANT:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in bindings:
                    bindings[target.id] = value
                    changed = True
    return bindings


def _literal_module(
    node: ast.AST,
    constants: dict[str, object] | None = None,
) -> str:
    return _constant_string(node, constants).strip()


def _external_python_root(module: str) -> str:
    root = module.lstrip(".").split(".", 1)[0].lower()
    return root if root in EXTERNAL_PYTHON_ROOTS else ""


def _is_oracle_path(relative: str) -> bool:
    return relative.startswith(ORACLE_PREFIX)


def _command_tokens(
    node: ast.AST,
    constants: dict[str, object] | None = None,
) -> tuple[str, ...]:
    value = _constant_value(node, constants)
    if isinstance(value, str):
        try:
            return tuple(shlex.split(value))
        except ValueError:
            return (value,)
    if isinstance(value, tuple):
        return tuple(item if isinstance(item, str) else "" for item in value)
    return ()


def _external_executable(tokens: Sequence[str]) -> str:
    for token in tokens:
        if not token:
            continue
        basename = Path(token).name.lower()
        if basename in EXTERNAL_EXECUTABLES:
            return basename
    return ""


def _function_external_markers(
    node: ast.AST,
    constants: dict[str, object],
) -> set[str]:
    markers: set[str] = set()
    name = str(getattr(node, "name", "")).lower()
    for engine in EXTERNAL_EXECUTABLES:
        if engine in name:
            markers.add(engine)
    for child in ast.walk(node):
        value = _constant_string(child, constants).strip().lower()
        executable = _external_executable((value,)) if value else ""
        if executable:
            markers.add(executable)
    return markers


def _external_command_builders(tree: ast.Module) -> set[str]:
    builders: set[str] = set()
    module_constants = _constant_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        constants = _constant_bindings(node, module_constants)
        if not _function_external_markers(node, constants):
            continue
        if any(isinstance(child, ast.Return) for child in ast.walk(node)):
            builders.add(node.name)
    return builders


def _expression_is_external_command(
    node: ast.AST,
    *,
    tainted: set[str],
    builders: set[str],
    aliases: dict[str, str],
    constants: dict[str, object],
) -> bool:
    if _external_executable(_command_tokens(node, constants)):
        return True
    if isinstance(node, ast.Name):
        return node.id in tainted
    if isinstance(node, (ast.List, ast.Tuple)):
        return any(
            _expression_is_external_command(
                item,
                tainted=tainted,
                builders=builders,
                aliases=aliases,
                constants=constants,
            )
            for item in node.elts
        )
    if not isinstance(node, ast.Call):
        return False
    dotted = _callable_name(node.func, aliases, constants)
    if dotted.rsplit(".", 1)[-1] in builders:
        return True
    propagating_calls = {
        "Path",
        "os.fspath",
        "pathlib.Path",
        "shutil.which",
        "str",
    }
    return dotted in propagating_calls and any(
        _expression_is_external_command(
            argument,
            tainted=tainted,
            builders=builders,
            aliases=aliases,
            constants=constants,
        )
        for argument in node.args
    )


def _tainted_command_names(
    scope: ast.AST,
    *,
    builders: set[str],
    aliases: dict[str, str],
    constants: dict[str, object],
) -> set[str]:
    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(scope):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            is_external = _expression_is_external_command(
                value,
                tainted=tainted,
                builders=builders,
                aliases=aliases,
                constants=constants,
            )
            if not is_external:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in tainted:
                    tainted.add(target.id)
                    changed = True
    return tainted


def _external_library_name(value: str) -> str:
    basename = value.replace("\\", "/").rsplit("/", 1)[-1]
    match = _EXTERNAL_LIBRARY_RE.search(basename)
    return match.group(1).lower() if match else ""


def _external_native_library(
    node: ast.AST,
    constants: dict[str, object],
) -> str:
    return _external_library_name(_constant_string(node, constants).strip())


def _process_command_node(node: ast.Call, dotted: str) -> ast.AST | None:
    positional_index = 1 if dotted in _SPAWN_MODE_FIRST_NAMES else 0
    if len(node.args) > positional_index:
        return node.args[positional_index]
    keyword_names = {"args", "cmd", "command", "path", "file", "program"}
    for keyword in node.keywords:
        if keyword.arg in keyword_names:
            return keyword.value
    return None


def _embedded_python_external_marker(source: str, *, depth: int = 0) -> str:
    if depth >= 8:
        return "nested dynamic code exceeds analysis depth"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    aliases = _aliases(tree)
    constants = _constant_bindings(tree)
    builders = _external_command_builders(tree)
    tainted = _tainted_command_names(
        tree,
        builders=builders,
        aliases=aliases,
        constants=constants,
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if _external_python_root(item.name):
                    return item.name
        elif isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            if _external_python_root(module):
                return module
        elif isinstance(node, ast.Call):
            dotted = _callable_name(node.func, aliases, constants)
            if dotted in _DYNAMIC_IMPORT_NAMES and node.args:
                module = _literal_module(node.args[0], constants)
                if not module:
                    return "unresolved dynamic import in executed code"
                if _external_python_root(module):
                    return module
            if dotted in _DYNAMIC_CODE_NAMES and node.args:
                nested = _constant_string(node.args[0], constants)
                if not nested:
                    return "unresolved nested dynamic code"
                marker = _embedded_python_external_marker(nested, depth=depth + 1)
                if marker:
                    return marker
            if dotted in _CTYPES_LOADERS:
                library_node = node.args[0] if node.args else None
                if library_node is not None:
                    library = _external_native_library(library_node, constants)
                    if library:
                        return library
            if dotted in _PROCESS_CALL_NAMES:
                candidates: list[ast.AST] = []
                command = _process_command_node(node, dotted)
                if command is not None:
                    candidates.append(command)
                if dotted in _SUBPROCESS_CALL_NAMES:
                    candidates.extend(
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg == "executable"
                    )
                for candidate in candidates:
                    executable = _external_executable(
                        _command_tokens(candidate, constants)
                    )
                    if executable:
                        return executable
                    if _expression_is_external_command(
                        candidate,
                        tainted=tainted,
                        builders=builders,
                        aliases=aliases,
                        constants=constants,
                    ):
                        return "external command in executed code"
    return ""


def inspect_python_boundary(root: Path) -> list[Violation]:
    """Check direct imports and direct process execution ownership."""

    root = root.resolve()
    violations: list[Violation] = []
    for path in _iter_files(root, "*.py"):
        relative = _relative(path, root)
        if Path(relative).parts[0] == "tests":
            continue
        # Parse every Python source.  A textual prefilter is unsafe here:
        # Python folds adjacent literals (``"gni" "na"``) in the AST, and a
        # product dispatch boundary must recognize the resulting executable.
        tree, parse_violations = _parse_python(path, root)
        violations.extend(parse_violations)
        if tree is None or _is_oracle_path(relative):
            continue
        aliases = _aliases(tree)
        parent: dict[ast.AST, ast.AST] = {}
        for candidate in ast.walk(tree):
            for child in ast.iter_child_nodes(candidate):
                parent[child] = candidate
        module_constants = _constant_bindings(tree)
        scope_constants: dict[int, dict[str, object]] = {id(tree): module_constants}

        def enclosing_scope(node: ast.AST) -> ast.AST:
            cursor = node
            while cursor in parent:
                cursor = parent[cursor]
                if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return cursor
            return tree

        def constants_for(node: ast.AST) -> dict[str, object]:
            scope = enclosing_scope(node)
            key = id(scope)
            if key not in scope_constants:
                scope_constants[key] = _constant_bindings(
                    scope,
                    module_constants,
                )
            return scope_constants[key]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    external = _external_python_root(item.name)
                    if external:
                        violations.append(
                            Violation(
                                relative,
                                node.lineno,
                                "external_python_import_outside_oracle",
                                item.name,
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                external = _external_python_root(str(node.module or ""))
                if external:
                    violations.append(
                        Violation(
                            relative,
                            node.lineno,
                            "external_python_import_outside_oracle",
                            str(node.module or ""),
                        )
                    )
            elif isinstance(node, ast.Call):
                dotted = _callable_name(node.func, aliases, constants_for(node))
                if dotted in _DYNAMIC_IMPORT_NAMES and node.args:
                    module = _literal_module(node.args[0], constants_for(node))
                    external = _external_python_root(module)
                    if external:
                        violations.append(
                            Violation(
                                relative,
                                node.lineno,
                                "external_dynamic_import_outside_oracle",
                                module,
                            )
                        )
                if dotted in _DYNAMIC_CODE_NAMES and node.args:
                    embedded = _constant_string(node.args[0], constants_for(node))
                    if embedded:
                        marker = _embedded_python_external_marker(embedded)
                        if marker:
                            violations.append(
                                Violation(
                                    relative,
                                    node.lineno,
                                    "external_dynamic_code_outside_oracle",
                                    marker,
                                )
                            )
                if dotted in _CTYPES_LOADERS:
                    library_node = node.args[0] if node.args else None
                    if library_node is None:
                        for keyword in node.keywords:
                            if keyword.arg in {"name", "library"}:
                                library_node = keyword.value
                                break
                    if library_node is not None:
                        library = _external_native_library(
                            library_node,
                            constants_for(node),
                        )
                        if library:
                            violations.append(
                                Violation(
                                    relative,
                                    node.lineno,
                                    "external_native_library_outside_oracle",
                                    library,
                                )
                            )
            elif isinstance(node, ast.Attribute):
                dotted = _dotted_name(node, aliases)
                for loader in _CTYPES_LOADER_OBJECTS:
                    prefix = f"{loader}."
                    if not dotted.startswith(prefix):
                        continue
                    library = _external_library_name(dotted.removeprefix(prefix))
                    if library:
                        violations.append(
                            Violation(
                                relative,
                                node.lineno,
                                "external_native_library_outside_oracle",
                                library,
                            )
                        )
                    break

        # Direct literal commands are always detectable.  A small taint pass
        # additionally follows local command builders such as the historical
        # Vina/GNINA runner's ``_external_command`` helper.
        builders = _external_command_builders(tree)
        scope_cache: dict[int, set[str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _callable_name(node.func, aliases, constants_for(node))
            if dotted not in _PROCESS_CALL_NAMES:
                continue
            command = _process_command_node(node, dotted)
            scope = enclosing_scope(node)
            key = id(scope)
            if key not in scope_cache:
                scope_cache[key] = _tainted_command_names(
                    scope,
                    builders=builders,
                    aliases=aliases,
                    constants=constants_for(node),
                )
            candidates: list[ast.AST] = []
            if command is not None:
                candidates.append(command)
            if dotted in _SUBPROCESS_CALL_NAMES:
                candidates.extend(
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "executable"
                )
            executable = ""
            for candidate in candidates:
                executable = _external_executable(
                    _command_tokens(candidate, constants_for(node))
                )
                if not executable and _expression_is_external_command(
                    candidate,
                    tainted=scope_cache[key],
                    builders=builders,
                    aliases=aliases,
                    constants=constants_for(node),
                ):
                    executable = "external command built in this module"
                if executable:
                    break
            if executable:
                violations.append(
                    Violation(
                        relative,
                        node.lineno,
                        "external_process_outside_oracle",
                        executable,
                    )
                )
    return sorted(set(violations))


def _shell_logical_lines(text: str) -> Iterator[tuple[int, str]]:
    start = 1
    buffer = ""
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not buffer:
            start = line_number
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        yield start, buffer + line
        buffer = ""
    if buffer:
        yield start, buffer


def _shell_tokens(line: str) -> tuple[str, ...]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
    lexer.commenters = "#"
    lexer.whitespace_split = True
    try:
        return tuple(lexer)
    except ValueError:
        return ()


def _shell_command_position(tokens: Sequence[str], index: int) -> bool:
    if index == 0:
        return True
    cursor = index - 1
    assignment = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
    while cursor >= 0 and assignment.fullmatch(tokens[cursor]):
        cursor -= 1
    if cursor < 0:
        return True
    return tokens[cursor] in {
        "(",
        ")",
        ";",
        "&",
        "&&",
        "|",
        "||",
        "do",
        "elif",
        "else",
        "if",
        "then",
    }


def _shell_wrapper_operand_index(
    tokens: Sequence[str],
    index: int,
    wrapper: str,
) -> int | None:
    cursor = index + 1
    options_with_values = {
        "chrt": {"-p", "--pid"},
        "env": {"-C", "-S", "-u", "--chdir", "--split-string", "--unset"},
        "exec": {"-a"},
        "ionice": {"-c", "-n", "-p", "-P", "-u"},
        "nice": {"-n", "--adjustment"},
        "stdbuf": {"-e", "-i", "-o"},
        "sudo": {
            "-C",
            "-D",
            "-g",
            "-h",
            "-p",
            "-R",
            "-r",
            "-T",
            "-t",
            "-u",
        },
        "taskset": {"-p", "--pid"},
        "time": {"-f", "-o", "--format", "--output"},
    }
    assignment = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.DOTALL)
    while cursor < len(tokens):
        token = tokens[cursor]
        if token == "--":
            cursor += 1
            break
        if not token.startswith("-") or token == "-":
            if wrapper == "env" and assignment.fullmatch(token):
                cursor += 1
                continue
            break
        if wrapper == "command" and token in {"-v", "-V"}:
            return None
        option = token.split("=", 1)[0]
        if option in options_with_values.get(wrapper, set()) and "=" not in token:
            cursor += 2
        else:
            cursor += 1
    return cursor if cursor < len(tokens) else None


def _shell_constant_operand(
    token: str,
    constants: dict[str, str],
    variable: re.Pattern[str],
) -> str:
    match = variable.fullmatch(token)
    return constants.get(match.group(1) or match.group(2), "") if match else token


def _shell_interpreter_payload_index(
    tokens: Sequence[str],
    index: int,
) -> int | None:
    cursor = index + 1
    while cursor < len(tokens):
        option = tokens[cursor]
        if option == "--":
            return None
        if option in {"--command"} or (
            option.startswith("-") and not option.startswith("--") and "c" in option[1:]
        ):
            return cursor + 1 if cursor + 1 < len(tokens) else None
        if option in {"-o", "-O"}:
            cursor += 2
            continue
        if option.startswith("-"):
            cursor += 1
            continue
        return None
    return None


def _external_shell_command(
    tokens: Sequence[str],
    index: int,
    constants: dict[str, str],
    variable: re.Pattern[str],
    depth: int = 0,
) -> str:
    if depth >= 8:
        return "unresolved nested shell command"
    seen: set[int] = set()
    while index < len(tokens) and index not in seen:
        seen.add(index)
        operand = _shell_constant_operand(tokens[index], constants, variable)
        executable = _external_executable((operand,))
        if executable:
            return executable
        wrapper = Path(operand).name
        if wrapper in _SHELL_INTERPRETERS:
            payload_index = _shell_interpreter_payload_index(tokens, index)
            if payload_index is None:
                return ""
            payload_token = tokens[payload_index]
            match = variable.fullmatch(payload_token)
            if match:
                name = match.group(1) or match.group(2)
                if name not in constants:
                    return "unresolved shell -c payload"
                payload = constants[name]
            else:
                payload = payload_token
            payload_tokens = _shell_tokens(payload)
            if not payload_tokens and payload.strip():
                return "unresolved shell -c payload"
            nested_constants: dict[str, str] = {}
            assignment = re.compile(
                r"([A-Za-z_][A-Za-z0-9_]*)=(.*)",
                re.DOTALL,
            )
            for token in payload_tokens:
                assignment_match = assignment.fullmatch(token)
                if assignment_match and "$" not in assignment_match.group(2):
                    nested_constants.setdefault(
                        assignment_match.group(1),
                        assignment_match.group(2),
                    )
            for payload_command_index, _ in enumerate(payload_tokens):
                if not _shell_command_position(payload_tokens, payload_command_index):
                    continue
                marker = _external_shell_command(
                    payload_tokens,
                    payload_command_index,
                    nested_constants,
                    variable,
                    depth + 1,
                )
                if marker:
                    return marker
            return ""
        if wrapper not in _SHELL_COMMAND_WRAPPERS:
            return ""
        next_index = _shell_wrapper_operand_index(tokens, index, wrapper)
        if next_index is None:
            return ""
        index = next_index
    return ""


def inspect_shell_boundary(root: Path) -> list[Violation]:
    """Reject external-engine execution from customer-visible shell scripts."""

    root = root.resolve()
    violations: list[Violation] = []
    assignment = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.DOTALL)
    variable = re.compile(
        r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))"
    )
    for path in _iter_files(root, "*.sh"):
        relative = _relative(path, root)
        if _is_oracle_path(relative) or Path(relative).parts[0] == "tests":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        constants: dict[str, str] = {}
        for line_number, line in _shell_logical_lines(text):
            tokens = _shell_tokens(line)
            for token in tokens:
                match = assignment.fullmatch(token)
                if match and "$" not in match.group(2):
                    constants.setdefault(match.group(1), match.group(2))
            for index, token in enumerate(tokens):
                if not _shell_command_position(tokens, index):
                    continue
                executable = _external_shell_command(
                    tokens,
                    index,
                    constants,
                    variable,
                )
                if executable:
                    violations.append(
                        Violation(
                            relative,
                            line_number,
                            "external_shell_process_outside_oracle",
                            executable,
                        )
                    )
    return sorted(set(violations))


def _module_name(relative: str) -> tuple[str, bool]:
    path = Path(relative)
    if path.suffix != ".py":
        return "", False
    parts = list(path.with_suffix("").parts)
    is_package = bool(parts and parts[-1] == "__init__")
    if is_package:
        parts.pop()
    if not parts or not all(part.isidentifier() for part in parts):
        return "", is_package
    return ".".join(parts), is_package


def _simple_name_assignments(tree: ast.Module) -> dict[str, ast.AST]:
    assignments: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, node.value)
    return assignments


def _guaranteed_string_prefix(
    node: ast.AST,
    assignments: dict[str, ast.AST],
    seen: set[str] | None = None,
) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        visited = set(seen or ())
        if node.id in visited or node.id not in assignments:
            return ""
        visited.add(node.id)
        return _guaranteed_string_prefix(assignments[node.id], assignments, visited)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left_value = _constant_string(node.left)
        if left_value:
            return left_value + _guaranteed_string_prefix(
                node.right,
                assignments,
                seen,
            )
        return _guaranteed_string_prefix(node.left, assignments, seen)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if isinstance(value, ast.FormattedValue):
                rendered = _constant_string(value.value)
                if rendered:
                    parts.append(rendered)
                    continue
            break
        return "".join(parts)
    return ""


def _internal_dynamic_import_prefix(prefix: str) -> bool:
    if not prefix.endswith("."):
        return False
    root = prefix.split(".", 1)[0]
    return root in PRODUCT_PACKAGE_ROOTS or root == "tools"


def _enclosing_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> str:
    cursor = node
    while cursor in parents:
        cursor = parents[cursor]
        if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cursor.name
    return ""


def _unresolved_dynamic_code_lines(
    tree: ast.Module,
    module: str,
) -> tuple[int, ...]:
    aliases = _aliases(tree)
    constants = _constant_bindings(tree)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    unresolved: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        dotted = _callable_name(node.func, aliases, constants)
        if dotted not in _DYNAMIC_CODE_NAMES:
            continue
        if _constant_string(node.args[0], constants):
            continue
        argument = node.args[0]
        audited = (
            module,
            _enclosing_function(node, parents),
            argument.id if isinstance(argument, ast.Name) else "",
        ) in _AUDITED_UNRESOLVED_DYNAMIC_CODE
        if not audited:
            unresolved.append(node.lineno)
    return tuple(sorted(set(unresolved)))


def _import_edges(
    tree: ast.Module,
    *,
    module: str,
    is_package: bool,
) -> list[tuple[str | None, int]]:
    aliases = _aliases(tree)
    constants = _constant_bindings(tree)
    assignments = _simple_name_assignments(tree)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    edges: list[tuple[str | None, int]] = []
    package = module if is_package else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.extend((item.name, node.lineno) for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported = str(node.module or "")
            if node.level:
                parts = package.split(".") if package else []
                ascend = max(0, node.level - 1)
                base_parts = (
                    parts[: len(parts) - ascend] if ascend <= len(parts) else []
                )
                if imported:
                    base_parts.extend(imported.split("."))
                imported = ".".join(part for part in base_parts if part)
            if imported:
                edges.append((imported, node.lineno))
            for item in node.names:
                if item.name == "*":
                    continue
                candidate = f"{imported}.{item.name}" if imported else item.name
                edges.append((candidate, node.lineno))
        elif isinstance(node, ast.Call):
            dotted = _callable_name(node.func, aliases, constants)
            if dotted in _DYNAMIC_IMPORT_NAMES and node.args:
                target = _literal_module(node.args[0], constants)
                if not target:
                    prefix = _guaranteed_string_prefix(node.args[0], assignments)
                    argument = node.args[0]
                    audited = (
                        module,
                        _enclosing_function(node, parents),
                        argument.id if isinstance(argument, ast.Name) else "",
                    ) in _AUDITED_UNRESOLVED_DYNAMIC_IMPORTS
                    if _internal_dynamic_import_prefix(prefix) or audited:
                        continue
                edges.append((target or None, node.lineno))
    return edges


def inspect_product_import_boundary(root: Path) -> list[Violation]:
    """Prove every product module/entrypoint is disconnected from oracles."""

    root = root.resolve()
    module_paths: dict[str, tuple[Path, bool]] = {}
    for path in _iter_files(root, "*.py"):
        relative = _relative(path, root)
        if Path(relative).parts[0] == "tests":
            continue
        module, is_package = _module_name(relative)
        if not module:
            continue
        module_paths[module] = (path, is_package)

    roots: set[str] = set()
    for module, (path, _) in module_paths.items():
        relative = _relative(path, root)
        first = Path(relative).parts[0]
        docker_product_tool = (
            first == "tools" and relative not in LEGACY_BENCHMARK_DOCKER_EXCLUSIONS
        )
        if (
            relative in PRODUCT_ENTRYPOINTS
            or first in PRODUCT_PACKAGE_ROOTS
            or docker_product_tool
        ):
            roots.add(module)

    violations: list[Violation] = []
    queue: deque[tuple[str, tuple[str, ...]]] = deque(
        (module, (module,)) for module in sorted(roots)
    )
    visited: set[str] = set()
    while queue:
        module, chain = queue.popleft()
        if module in visited:
            continue
        visited.add(module)
        record = module_paths.get(module)
        if record is None:
            continue
        path, is_package = record
        tree, errors = _parse_python(path, root)
        violations.extend(errors)
        if tree is None:
            continue
        relative = _relative(path, root)
        for line in _unresolved_dynamic_code_lines(tree, module):
            violations.append(
                Violation(
                    relative,
                    line,
                    "product_dynamic_code_execution_unresolved",
                    "exec/eval target is not statically provable",
                )
            )
        for target, line in _import_edges(
            tree,
            module=module,
            is_package=is_package,
        ):
            if target is None:
                violations.append(
                    Violation(
                        relative,
                        line,
                        "product_dynamic_import_unresolved",
                        "dynamic import target is not statically provable",
                    )
                )
                continue
            if (
                target == "benchmarks"
                or target.startswith(f"{ORACLE_MODULE_PREFIX}.")
                or target == ORACLE_MODULE_PREFIX
            ):
                violations.append(
                    Violation(
                        relative,
                        line,
                        "product_imports_external_oracle",
                        " -> ".join((*chain, target)),
                    )
                )
                continue
            candidate = target
            while candidate and candidate not in module_paths:
                candidate = candidate.rpartition(".")[0]
            if candidate and candidate not in visited:
                queue.append((candidate, (*chain, candidate)))
    return sorted(set(violations))


def _normalize_dependency(value: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", value)
    if match is None:
        return ""
    return re.sub(r"[-_.]+", "-", match.group(1).lower())


def _forbidden_dependency(value: str) -> str:
    normalized = _normalize_dependency(value)
    for root in EXTERNAL_DEPENDENCY_ROOTS:
        if normalized == root or normalized.startswith(f"{root}-"):
            return normalized
    return ""


def _external_library_literal(line: str) -> str:
    for value in re.findall(r'["\']([^"\']+)["\']', line):
        library = _external_library_name(value)
        if library:
            return library
    return ""


def _root_requirement_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.glob("requirements*.txt")):
        if path.is_file():
            yield path


def _toml_sections(text: str) -> Iterator[tuple[str, int, str]]:
    section = ""
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[]").strip().lower()
        yield section, line_number, line


def inspect_dependency_boundary(root: Path) -> list[Violation]:
    root = root.resolve()
    violations: list[Violation] = []

    for path in _root_requirement_files(root):
        relative = _relative(path, root)
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "-")):
                continue
            dependency = _forbidden_dependency(stripped)
            if dependency:
                violations.append(
                    Violation(
                        relative, line_number, "external_product_dependency", dependency
                    )
                )

    pyprojects = (root / "pyproject.toml", root / "packaging/engine-v2/pyproject.toml")
    for path in pyprojects:
        if not path.is_file():
            continue
        relative = _relative(path, root)
        for section, line_number, line in _toml_sections(
            path.read_text(encoding="utf-8")
        ):
            if not (
                section == "project"
                or section.startswith("project.optional-dependencies")
            ):
                continue
            for quoted in re.findall(r'["\']([^"\']+)["\']', line):
                dependency = _forbidden_dependency(quoted)
                if dependency:
                    violations.append(
                        Violation(
                            relative,
                            line_number,
                            "external_product_dependency",
                            dependency,
                        )
                    )

    for path in _iter_files(root, "Cargo.toml"):
        relative = _relative(path, root)
        if _is_oracle_path(relative):
            continue
        for section, line_number, line in _toml_sections(
            path.read_text(encoding="utf-8")
        ):
            if "dependencies" not in section or "dev-dependencies" in section:
                continue
            stripped = line.split("#", 1)[0].strip()
            if not stripped or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            candidates = [
                key.strip().strip("\"'"),
                *re.findall(r'["\']([^"\']+)["\']', value),
            ]
            for candidate in candidates:
                dependency = _forbidden_dependency(candidate)
                if dependency:
                    violations.append(
                        Violation(
                            relative,
                            line_number,
                            "external_rust_dependency",
                            dependency,
                        )
                    )

    cmake_paths = list(_iter_files(root, "CMakeLists.txt")) + list(
        _iter_files(root, "*.cmake")
    )
    for path in cmake_paths:
        relative = _relative(path, root)
        if _is_oracle_path(relative):
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if _CMAKE_EXTERNAL_RE.search(line) and re.search(
                r"(?i)(find_package|pkg_check_modules|target_link_libraries|link_libraries)",
                line,
            ):
                violations.append(
                    Violation(
                        relative,
                        line_number,
                        "external_native_dependency",
                        line.strip(),
                    )
                )

    native_suffixes = ("*.c", "*.cc", "*.cpp", "*.cxx", "*.h", "*.hh", "*.hpp", "*.rs")
    for pattern in native_suffixes:
        for path in _iter_files(root, pattern):
            relative = _relative(path, root)
            if _is_oracle_path(relative) or Path(relative).parts[0] == "tests":
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            loader_calls = (
                _RUST_DYNAMIC_LOADER_CALL_RE
                if path.suffix == ".rs"
                else _NATIVE_DYNAMIC_LOADER_CALL_RE
            )
            for match in loader_calls.finditer(source):
                library = _external_library_literal(match.group("arguments"))
                if library:
                    violations.append(
                        Violation(
                            relative,
                            source.count("\n", 0, match.start()) + 1,
                            "external_native_library_runtime_load",
                            library,
                        )
                    )
            for line_number, line in enumerate(source.splitlines(), 1):
                relevant = (
                    line.lstrip().startswith("#include")
                    or "cargo:rustc-link-lib" in line
                    or "#[link(" in line
                )
                if relevant and _CMAKE_EXTERNAL_RE.search(line):
                    violations.append(
                        Violation(
                            relative,
                            line_number,
                            "external_native_dependency",
                            line.strip(),
                        )
                    )
    return sorted(set(violations))


def _dockerignore_rules(path: Path) -> tuple[tuple[bool, str], ...]:
    rules: list[tuple[bool, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        negated = stripped.startswith("!")
        pattern = stripped[1:] if negated else stripped
        rules.append((negated, pattern.removeprefix("./").lstrip("/")))
    return tuple(rules)


def _dockerignore_matches(pattern: str, relative: str) -> bool:
    if pattern.endswith("/**"):
        directory = pattern[:-3].rstrip("/")
        return relative == directory or relative.startswith(f"{directory}/")
    if pattern.endswith("/"):
        directory = pattern.rstrip("/")
        return relative == directory or relative.startswith(f"{directory}/")
    return fnmatch.fnmatchcase(relative, pattern)


def _dockerignore_excludes(rules: Sequence[tuple[bool, str]], relative: str) -> bool:
    excluded = False
    for negated, pattern in rules:
        if _dockerignore_matches(pattern, relative):
            excluded = not negated
    return excluded


def _pyproject_excludes_benchmarks(path: Path) -> bool:
    section = ""
    for current, _, line in _toml_sections(path.read_text(encoding="utf-8")):
        section = current
        if section == "tool.setuptools.packages.find" and re.search(
            r'["\']benchmarks\*["\']', line
        ):
            return True
    return False


def inspect_packaging_boundary(
    root: Path, *, product_image: bool = False
) -> list[Violation]:
    root = root.resolve()
    violations: list[Violation] = []
    dockerfile = root / "Dockerfile.product"
    if dockerfile.is_file():
        text = dockerfile.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if re.match(r"\s*(?:COPY|ADD)\s+.*\bbenchmarks(?:/|\b)", line, re.I):
                violations.append(
                    Violation(
                        "Dockerfile.product",
                        line_number,
                        "oracle_copied_into_product_image",
                        line.strip(),
                    )
                )
        if not product_image:
            required_fragments = (
                "test ! -e /app/benchmarks",
                "check_external_oracle_architecture.py --root /app --product-image",
            )
            for fragment in required_fragments:
                if fragment not in text:
                    violations.append(
                        Violation(
                            "Dockerfile.product",
                            0,
                            "product_image_boundary_check_missing",
                            fragment,
                        )
                    )

    if not product_image:
        dockerignore = root / ".dockerignore"
        if not dockerignore.is_file():
            violations.append(
                Violation(".dockerignore", 0, "dockerignore_missing", "file missing")
            )
        else:
            ordered_rules = _dockerignore_rules(dockerignore)
            positive_rules = {
                pattern for negated, pattern in ordered_rules if not negated
            }
            required = {
                "benchmarks",
                "benchmarks/**",
                *LEGACY_BENCHMARK_DOCKER_EXCLUSIONS,
            }
            for missing in sorted(required - positive_rules):
                violations.append(
                    Violation(
                        ".dockerignore", 0, "oracle_docker_exclusion_missing", missing
                    )
                )
            effective_targets = {
                "benchmarks",
                "benchmarks/oracles/architecture-probe.py",
                *LEGACY_BENCHMARK_DOCKER_EXCLUSIONS,
            }
            for leaked in sorted(
                target
                for target in effective_targets
                if not _dockerignore_excludes(ordered_rules, target)
            ):
                violations.append(
                    Violation(
                        ".dockerignore",
                        0,
                        "oracle_docker_reincluded",
                        leaked,
                    )
                )

        for relative in ("pyproject.toml", "packaging/engine-v2/pyproject.toml"):
            path = root / relative
            if path.is_file() and not _pyproject_excludes_benchmarks(path):
                violations.append(
                    Violation(
                        relative,
                        0,
                        "oracle_wheel_exclusion_missing",
                        'exclude = ["benchmarks*"]',
                    )
                )
    return sorted(set(violations))


def inspect_repository(root: Path, *, product_image: bool = False) -> list[Violation]:
    violations = [
        *inspect_python_boundary(root),
        *inspect_shell_boundary(root),
        *inspect_product_import_boundary(root),
        *inspect_dependency_boundary(root),
        *inspect_packaging_boundary(root, product_image=product_image),
    ]
    return sorted(set(violations))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--product-image", action="store_true")
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    if not root.is_dir():
        parser.error(f"repository root is not a directory: {root}")
    violations = inspect_repository(root, product_image=arguments.product_image)
    if violations:
        for violation in violations:
            print(violation.render())
        return 1
    print(
        "External oracle architecture guard passed: adapters are benchmark-only; "
        "product imports, dependencies, image, and wheels remain independent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

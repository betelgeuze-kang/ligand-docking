#!/usr/bin/env python3
"""Enforce Engine v2 ownership and prohibited dense-operation boundaries."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


PROHIBITED_IMPORT_ROOTS = {
    "api",
    "benchmark",
    "betelgeuze_ai_md",
    "betelgeuze_engine",
    "betelgeuze_product",
    "core",
    "theory",
    "train",
}
LEGACY_IMPORT_ALLOWLIST = {
    "betelgeuze_engine_v2/molecular/legacy.py",
}
PROHIBITED_CALLS = {
    "torch.cdist",
    "torch.pdist",
    "torch.nn.MultiheadAttention",
    "torch.nn.Transformer",
    "torch.nn.TransformerEncoder",
    "torch.nn.TransformerEncoderLayer",
    "torch.nn.TransformerDecoder",
    "torch.nn.TransformerDecoderLayer",
}
PROHIBITED_CALL_BASENAMES = {
    "cdist",
    "pdist",
    "MultiheadAttention",
    "Transformer",
    "TransformerEncoder",
    "TransformerEncoderLayer",
    "TransformerDecoder",
    "TransformerDecoderLayer",
}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    code: str
    detail: str


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _import_root(module: str) -> str:
    return str(module or "").split(".", 1)[0]


def inspect_file(path: Path, package_root: Path) -> list[Violation]:
    relative = path.relative_to(package_root.parent).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    violations: list[Violation] = []
    aliases: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                root = _import_root(item.name)
                local = item.asname or root
                aliases[local] = item.name
                if root in PROHIBITED_IMPORT_ROOTS and relative not in LEGACY_IMPORT_ALLOWLIST:
                    violations.append(
                        Violation(relative, node.lineno, "prohibited_import", item.name)
                    )
        elif isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            root = _import_root(module)
            if root in PROHIBITED_IMPORT_ROOTS and relative not in LEGACY_IMPORT_ALLOWLIST:
                violations.append(
                    Violation(relative, node.lineno, "prohibited_import", module)
                )
            for item in node.names:
                local = item.asname or item.name
                aliases[local] = f"{module}.{item.name}" if module else item.name

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        if dotted:
            first, *rest = dotted.split(".")
            if first in aliases:
                dotted = ".".join((aliases[first], *rest))
        basename = dotted.rsplit(".", 1)[-1]
        if dotted in PROHIBITED_CALLS or basename in PROHIBITED_CALL_BASENAMES:
            violations.append(
                Violation(relative, node.lineno, "prohibited_dense_operation", dotted)
            )

    return violations


def inspect_package(package_root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(package_root.rglob("*.py")):
        violations.extend(inspect_file(path, package_root))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", default="betelgeuze_engine_v2")
    args = parser.parse_args()
    package_root = Path(args.package_root).resolve()
    if not package_root.is_dir():
        raise SystemExit(f"package root not found: {package_root}")
    violations = inspect_package(package_root)
    if violations:
        for violation in violations:
            print(
                f"{violation.path}:{violation.line}: "
                f"{violation.code}: {violation.detail}"
            )
        return 1
    print(
        "Engine v2 architecture guard passed: no prohibited legacy imports, "
        "attention modules, or dense distance constructors."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

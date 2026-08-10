#!/usr/bin/env python3
"""Materialize and verify the product Docker context without building its image."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
from typing import Iterable

try:
    from tools.check_external_oracle_architecture import (
        LEGACY_BENCHMARK_DOCKER_EXCLUSIONS,
    )
except ModuleNotFoundError:  # Direct ``python tools/...`` execution.
    from check_external_oracle_architecture import (  # type: ignore[no-redef]
        LEGACY_BENCHMARK_DOCKER_EXCLUSIONS,
    )


MANDATORY_ORACLE_EXCLUSIONS = frozenset(
    {"benchmarks", "benchmarks/**", *LEGACY_BENCHMARK_DOCKER_EXCLUSIONS}
)


@dataclass(frozen=True)
class DockerIgnoreRule:
    negated: bool
    pattern: str
    expression: re.Pattern[str] | None

    def matches(self, relative: str) -> bool:
        candidates = _path_and_parents(relative)
        if "/" not in self.pattern:
            return any(
                fnmatch.fnmatchcase(PurePosixPath(candidate).name, self.pattern)
                for candidate in candidates
            )
        assert self.expression is not None
        return any(self.expression.fullmatch(candidate) for candidate in candidates)


def _path_and_parents(relative: str) -> tuple[str, ...]:
    parts = PurePosixPath(relative).parts
    return tuple("/".join(parts[:length]) for length in range(len(parts), 0, -1))


def _docker_glob_expression(pattern: str) -> re.Pattern[str]:
    rendered: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    rendered.append("(?:[^/]+/)*")
                    index += 1
                else:
                    rendered.append(".*")
                continue
            rendered.append("[^/]*")
        elif character == "?":
            rendered.append("[^/]")
        elif character == "[":
            end = pattern.find("]", index + 1)
            if end == -1:
                rendered.append(r"\[")
            else:
                character_class = pattern[index + 1 : end]
                if character_class.startswith("!"):
                    character_class = "^" + character_class[1:]
                elif character_class.startswith("^"):
                    character_class = "\\" + character_class
                rendered.append("[" + character_class.replace("\\", r"\\") + "]")
                index = end
        else:
            rendered.append(re.escape(character))
        index += 1
    return re.compile("".join(rendered))


def read_dockerignore(path: Path) -> tuple[DockerIgnoreRule, ...]:
    rules: list[DockerIgnoreRule] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        pattern = line.removeprefix("./").strip("/")
        if not pattern or pattern == ".":
            continue
        rules.append(
            DockerIgnoreRule(
                negated=negated,
                pattern=pattern,
                expression=(
                    _docker_glob_expression(pattern) if "/" in pattern else None
                ),
            )
        )
    return tuple(rules)


def is_excluded(rules: Iterable[DockerIgnoreRule], relative: str) -> bool:
    excluded = False
    for rule in rules:
        if rule.matches(relative):
            excluded = not rule.negated
    return excluded


def _last_matching_rule(
    rules: tuple[DockerIgnoreRule, ...], relative: str
) -> tuple[int, DockerIgnoreRule] | None:
    matched = [
        (index, rule) for index, rule in enumerate(rules) if rule.matches(relative)
    ]
    return matched[-1] if matched else None


def _could_reinclude_descendant(
    rules: tuple[DockerIgnoreRule, ...],
    relative: str,
) -> bool:
    last = _last_matching_rule(rules, relative)
    start = 0 if last is None else last[0] + 1
    for rule in rules[start:]:
        if not rule.negated or "/" not in rule.pattern:
            continue
        wildcard_offsets = [
            offset
            for character in "*?["
            if (offset := rule.pattern.find(character)) >= 0
        ]
        static_prefix = rule.pattern[
            : min(wildcard_offsets, default=len(rule.pattern))
        ].rstrip("/")
        if (
            static_prefix == relative
            or static_prefix.startswith(f"{relative}/")
            or relative.startswith(f"{static_prefix}/")
        ):
            return True
    return False


def _normalized_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _context_entries(
    root: Path,
    rules: tuple[DockerIgnoreRule, ...],
) -> tuple[Path, ...]:
    entries: list[Path] = []
    for directory, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current = Path(directory)
        directory_names.sort()
        file_names.sort()
        for name in tuple(directory_names):
            candidate = current / name
            relative = _normalized_relative(candidate, root)
            excluded = is_excluded(rules, relative)
            if not excluded:
                entries.append(candidate)
            elif not _could_reinclude_descendant(rules, relative):
                directory_names.remove(name)
        for name in file_names:
            candidate = current / name
            relative = _normalized_relative(candidate, root)
            if not is_excluded(rules, relative):
                entries.append(candidate)
    return tuple(entries)


def _copy_sources(dockerfile: Path) -> tuple[str, ...]:
    sources: list[str] = []
    for line_number, raw_line in enumerate(
        dockerfile.read_text(encoding="utf-8").splitlines(), 1
    ):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        instruction, _, arguments = stripped.partition(" ")
        if instruction.upper() != "COPY":
            continue
        if not arguments or arguments.lstrip().startswith("["):
            raise RuntimeError(
                f"unsupported product COPY syntax at Dockerfile.product:{line_number}"
            )
        try:
            fields = shlex.split(arguments, posix=True)
        except ValueError as exc:
            raise RuntimeError(
                f"invalid product COPY syntax at Dockerfile.product:{line_number}"
            ) from exc
        while fields and fields[0].startswith("--"):
            fields.pop(0)
        if len(fields) < 2:
            raise RuntimeError(
                f"invalid product COPY syntax at Dockerfile.product:{line_number}"
            )
        for source in fields[:-1]:
            normalized = PurePosixPath(source).as_posix().removeprefix("./")
            if (
                not normalized
                or normalized.startswith("/")
                or ".." in PurePosixPath(normalized).parts
                or any(character in normalized for character in "*?[")
            ):
                raise RuntimeError(
                    f"non-literal product COPY source at Dockerfile.product:{line_number}"
                )
            sources.append(normalized.rstrip("/"))
    return tuple(sorted(set(sources)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(entries: Iterable[Path], root: Path) -> tuple[str, int]:
    rows: list[dict[str, object]] = []
    file_count = 0
    for path in sorted(entries, key=lambda value: _normalized_relative(value, root)):
        status = path.lstat()
        relative = _normalized_relative(path, root)
        if stat.S_ISLNK(status.st_mode):
            raise RuntimeError(f"product Docker context contains symlink: {relative}")
        if stat.S_ISDIR(status.st_mode):
            rows.append({"path": relative, "type": "directory"})
            continue
        if not stat.S_ISREG(status.st_mode):
            raise RuntimeError(
                f"product Docker context contains special file: {relative}"
            )
        rows.append(
            {
                "path": relative,
                "type": "file",
                "size": status.st_size,
                "sha256": _sha256(path),
            }
        )
        file_count += 1
    encoded = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), file_count


def materialize_product_context(root: Path, output: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    dockerignore = root / ".dockerignore"
    dockerfile = root / "Dockerfile.product"
    if not dockerignore.is_file() or not dockerfile.is_file():
        raise RuntimeError(
            "product Docker context requires .dockerignore and Dockerfile.product"
        )
    rules = read_dockerignore(dockerignore)
    positive_patterns = {rule.pattern for rule in rules if not rule.negated}
    missing = sorted(MANDATORY_ORACLE_EXCLUSIONS - positive_patterns)
    if missing:
        raise RuntimeError(
            "mandatory oracle Docker exclusions missing: " + ", ".join(missing)
        )

    entries = _context_entries(root, rules)
    included = {_normalized_relative(path, root) for path in entries}
    leaked = sorted(
        relative
        for relative in included
        if relative == "benchmarks"
        or relative.startswith("benchmarks/")
        or relative in LEGACY_BENCHMARK_DOCKER_EXCLUSIONS
    )
    if leaked:
        raise RuntimeError(
            "oracle file entered product Docker context: " + ", ".join(leaked)
        )

    required = {"Dockerfile.product", *_copy_sources(dockerfile)}
    absent = sorted(
        relative
        for relative in required
        if not (root / relative).exists() or relative not in included
    )
    if absent:
        raise RuntimeError(
            "product Docker COPY source excluded from context: " + ", ".join(absent)
        )
    source_sha256, source_file_count = _manifest(entries, root)

    output = output.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise RuntimeError(
            "materialized Docker context must be outside repository root"
        )
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise RuntimeError(
                f"materialized Docker context output is not empty: {output}"
            )
    else:
        output.mkdir(parents=True)

    for source in entries:
        destination = output / source.relative_to(root)
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)

    output_entries = tuple(
        sorted(
            (path for path in output.rglob("*") if path != output),
            key=lambda path: path.relative_to(output).as_posix(),
        )
    )
    output_sha256, output_file_count = _manifest(output_entries, output)
    if (output_sha256, output_file_count) != (source_sha256, source_file_count):
        raise RuntimeError("materialized product Docker context verification failed")
    return {
        "file_count": source_file_count,
        "manifest_sha256": source_sha256,
        "oracle_free": True,
        "output": os.fspath(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = materialize_product_context(Path(args.root), Path(args.output))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

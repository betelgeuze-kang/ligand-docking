#!/usr/bin/python3.10
"""Fail closed unless v6 qualification crates receive the frozen rustc flags."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import NoReturn


QUALIFICATION_BUILD_ENV = "BETELGEUZE_V6_QUALIFICATION_BUILD"
VERIFIED_CFG = "betelgeuze_v6_effective_rust_flags_verified"
CONTROLLED_LIBRARY_CRATES = {
    "betelgeuze_cpu_kernel",
    "betelgeuze_docking_search",
    "betelgeuze_runtime",
    "betelgeuze_sys",
}
CONTROLLED_BINARY_CRATE = "betelgeuze_fixed64_cpu_qualify_v6"
CONTROLLED_CFG_VALUES = {
    "betelgeuze_cpu_kernel": [],
    "betelgeuze_docking_search": [],
    "betelgeuze_runtime": [
        "betelgeuze_v6_qualification_build",
        'feature="default"',
    ],
    "betelgeuze_sys": ['feature="default"'],
    CONTROLLED_BINARY_CRATE: [
        "betelgeuze_v6_qualification_build",
        'feature="default"',
    ],
}
_RUSTC_METADATA = re.compile(r"[0-9a-f]{16}")
_RUSTC_EXTRA_FILENAME = re.compile(r"-[0-9a-f]{16}")
ALLOWED_QUERY_ARGUMENTS = {("-vV",), ("--version",)}


def _fail(message: str) -> NoReturn:
    print(
        f"native fixed64 CPU v6 rustc wrapper rejected build: {message}",
        file=sys.stderr,
    )
    raise SystemExit(86)


def _single_option(arguments: list[str], name: str) -> str:
    values: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == name:
            if index + 1 >= len(arguments):
                _fail(f"{name} is missing its value")
            values.append(arguments[index + 1])
            index += 2
            continue
        prefix = f"{name}="
        if argument.startswith(prefix):
            values.append(argument[len(prefix) :])
        index += 1
    if len(values) != 1:
        _fail(f"{name} must occur exactly once")
    return values[0]


def _codegen_options(arguments: list[str]) -> dict[str, list[str | None]]:
    options: dict[str, list[str | None]] = {}
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-C":
            if index + 1 >= len(arguments):
                _fail("-C is missing its value")
            encoded = arguments[index + 1]
            index += 2
        elif argument.startswith("-C") and len(argument) > 2:
            encoded = argument[2:]
            index += 1
        else:
            index += 1
            continue
        key, separator, value = encoded.partition("=")
        if not key:
            _fail("empty -C option")
        options.setdefault(key, []).append(value if separator else None)
    return options


def _require_frozen_codegen(arguments: list[str], *, binary: bool) -> None:
    options = _codegen_options(arguments)
    library_lto = None if binary else options.pop("linker-plugin-lto", None)
    expected: dict[str, str | None] = {
        "opt-level": "3",
        "panic": "abort",
        "codegen-units": "1",
        "overflow-checks": "on",
        "metadata": None,
        "extra-filename": None,
    }
    if binary:
        expected["lto"] = "fat"
    if set(options) != set(expected):
        _fail("effective -C option names differ from the frozen profile")
    for key, value in expected.items():
        observed = options[key]
        if len(observed) != 1:
            _fail(f"-C {key} must occur exactly once")
        if value is not None and observed[0] != value:
            _fail(f"-C {key} differs from the frozen profile")
    metadata = options["metadata"][0]
    extra_filename = options["extra-filename"][0]
    if (
        not isinstance(metadata, str)
        or _RUSTC_METADATA.fullmatch(metadata) is None
        or not isinstance(extra_filename, str)
        or _RUSTC_EXTRA_FILENAME.fullmatch(extra_filename) is None
    ):
        _fail("Cargo identity codegen flags are not canonical")
    if not binary:
        if library_lto is None:
            # Cargo 1.93 can omit this option from dependency invocations.
            # Inject it only after rejecting every caller-supplied extra -C
            # option, so the effective invocation still has exactly one LTO
            # mode.
            arguments.extend(["-C", "linker-plugin-lto"])
        elif library_lto != [None]:
            _fail("-C linker-plugin-lto must occur exactly once without a value")


def _require_frozen_cfg(arguments: list[str], *, crate_name: str) -> None:
    cfg_values: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--cfg":
            if index + 1 >= len(arguments):
                _fail("--cfg is missing its value")
            cfg_values.append(arguments[index + 1])
            index += 2
            continue
        if argument.startswith("--cfg="):
            cfg_values.append(argument.removeprefix("--cfg="))
        index += 1
    if sorted(cfg_values) != sorted(CONTROLLED_CFG_VALUES[crate_name]):
        _fail(f"{crate_name} cfg values differ from the frozen profile")
    if VERIFIED_CFG in cfg_values:
        _fail("verified cfg was supplied before wrapper validation")


def main() -> NoReturn:
    if len(sys.argv) < 2:
        _fail("rustc executable is missing")
    rustc = Path(sys.argv[1])
    arguments = sys.argv[2:]
    requested = os.environ.get(QUALIFICATION_BUILD_ENV)
    if requested is not None and requested != "1":
        _fail(f"{QUALIFICATION_BUILD_ENV} must equal 1 when present")
    if requested == "1":
        if any(argument == "-Z" or argument.startswith("-Z") for argument in arguments):
            _fail("unstable rustc options are forbidden")
        if tuple(arguments) not in ALLOWED_QUERY_ARGUMENTS:
            crate_name = _single_option(arguments, "--crate-name")
            if crate_name in CONTROLLED_LIBRARY_CRATES:
                _require_frozen_codegen(arguments, binary=False)
            elif crate_name == CONTROLLED_BINARY_CRATE:
                _require_frozen_codegen(arguments, binary=True)
            if crate_name in CONTROLLED_CFG_VALUES:
                _require_frozen_cfg(arguments, crate_name=crate_name)
            if crate_name in {"betelgeuze_runtime", CONTROLLED_BINARY_CRATE}:
                arguments.extend(
                    [
                        "--cfg",
                        VERIFIED_CFG,
                        "--check-cfg",
                        f"cfg({VERIFIED_CFG})",
                    ]
                )
    try:
        os.execv(rustc, [str(rustc), *arguments])
    except OSError as exc:
        _fail(f"rustc execution failed: {exc.strerror or type(exc).__name__}")


if __name__ == "__main__":
    main()

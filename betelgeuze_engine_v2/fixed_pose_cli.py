"""Fixed-coordinate development evaluation through the existing CPU force field.

This adapter reads explicit canonical state and parameters. It performs no
preparation, parameter assignment, search, minimization, or dynamics.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Sequence

from . import cli as _cli
from .molecular.serialization import (
    all_atom_system_from_canonical_json, canonical_system_document, canonical_json_value,
)
from .physics.reference_parameters import (
    AtomNonbondedParameter, HarmonicAngleParameter, HarmonicBondParameter,
    PairScalingParameter, PeriodicTorsionParameter, ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)

COMMAND_ID = "betelgeuze-engine-v2/evaluate-fixed-pose/1.0.0"
MAX_INPUT_BYTES = 4 * 1024 * 1024


class FixedPoseInputError(ValueError):
    """An explicit input is incomplete, ambiguous, or unsupported."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise FixedPoseInputError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FixedPoseInputError("duplicate JSON object key")
        result[key] = value
    return result


def _nonfinite_constant(value):
    raise FixedPoseInputError("non-finite JSON number")


def _load_object(raw: bytes) -> dict:
    document = json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=_nonfinite_constant)
    # JSON exponent overflow (1e999) does not invoke parse_constant.
    json.dumps(document, allow_nan=False)
    if not isinstance(document, dict):
        raise FixedPoseInputError("input must be a JSON object")
    return document


def _exact_keys(document, keys, name):
    if not isinstance(document, dict) or set(document) != set(keys):
        raise FixedPoseInputError(f"{name} requires exactly: {', '.join(sorted(keys))}")


def _record(cls, document):
    _exact_keys(document, {f.name for f in fields(cls) if f.init}, cls.__name__)
    return cls(**document)


def parameters_from_document(document: dict) -> ReferenceForceFieldParameters:
    """Read exactly the existing parameter to_dict contract, without defaults."""
    _exact_keys(document, {f.name for f in fields(ReferenceForceFieldParameters)},
                "reference parameters")
    values = dict(document)
    for name, cls in (
        ("atom_parameters", AtomNonbondedParameter),
        ("bonds", HarmonicBondParameter),
        ("angles", HarmonicAngleParameter),
        ("torsions", PeriodicTorsionParameter),
        ("scaled_pairs", PairScalingParameter),
    ):
        if not isinstance(values[name], list):
            raise FixedPoseInputError(f"{name} must be an explicit list")
        values[name] = tuple(_record(cls, row) for row in values[name])
    if not isinstance(values["excluded_pairs"], list):
        raise FixedPoseInputError("excluded_pairs must be an explicit list")
    if any(not isinstance(pair, list) or len(pair) != 2
           for pair in values["excluded_pairs"]):
        raise FixedPoseInputError("excluded_pairs must contain index pairs")
    values["excluded_pairs"] = tuple(tuple(pair) for pair in values["excluded_pairs"])
    values["applicability_domain"] = _record(
        ReferenceApplicabilityDomain, values["applicability_domain"])
    return ReferenceForceFieldParameters(**values)


def evaluate_documents(*, system_raw: bytes, parameters_raw: bytes,
                       pocket_raw: bytes, partition_raw: bytes) -> dict:
    """The console consumer: verify inputs, run the existing evaluator, bind output."""
    from .docking.fixed_pose import evaluate_fixed_pose

    raw_inputs = {"system": system_raw, "parameters": parameters_raw,
                  "pocket": pocket_raw, "partition": partition_raw}
    if any(len(raw) > MAX_INPUT_BYTES for raw in raw_inputs.values()):
        raise FixedPoseInputError("fixed-pose input exceeds byte limit")
    documents = {name: _load_object(raw) for name, raw in raw_inputs.items()}
    system = all_atom_system_from_canonical_json(system_raw, device="cpu")
    parameters = parameters_from_document(documents["parameters"])
    pocket = _cli._pocket_from_document(documents["pocket"])
    partition = documents["partition"]
    _exact_keys(partition, {"receptor_atom_indices", "ligand_atom_indices",
                            "state_declarations"}, "partition")
    result = evaluate_fixed_pose(system, parameters, pocket=pocket, **partition)
    result.update({
        "command_id": COMMAND_ID,
        "input_bytes_sha256": {name: hashlib.sha256(raw).hexdigest()
                               for name, raw in raw_inputs.items()},
        "evaluated_system": canonical_json_value(canonical_system_document(system)),
        "evaluated_parameters": parameters.to_dict(),
        "pocket_input": documents["pocket"],
    })
    json.dumps(result, allow_nan=False)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(
        prog="betelgeuze-engine-v2 evaluate-fixed-pose",
        description="Single-pose CPU development evaluation; explicit state and parameters only.")
    for name in ("system", "parameters", "pocket", "partition"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    result = None
    try:
        args = parser.parse_args(argv)
        result = evaluate_documents(**{
            name + "_raw": _cli._read_bounded(getattr(args, name),
                maximum=MAX_INPUT_BYTES, name="fixed-pose " + name)
            for name in ("system", "parameters", "pocket", "partition")
        })
        result.update({"requested_count": 1, "evaluated_count": 1, "failure_count": 0})
        result["consumer_cost"] = {
            "wall_seconds": time.perf_counter() - started_wall,
            "cpu_seconds": time.process_time() - started_cpu,
            "scope": "input_read_decode_validation_and_evaluation_excludes_import_and_output_write",
            "peak_rss_bytes": None, "peak_vram_bytes": None,
        }
        if args.output is None:
            sys.stdout.buffer.write(_cli._canonical_bytes(result) + b"\n")
            sys.stdout.buffer.flush()
        else:
            _cli._write_output(result, args.output, overwrite=args.overwrite)
        return 0
    except Exception as exc:
        failure = {
            "command_id": COMMAND_ID, "status": "failure", "requested_count": 1,
            "evaluated_count": int(result is not None), "failure_count": 1,
            "failure_stage": "output" if result is not None else "input_or_evaluation",
            "error_code": type(exc).__name__, "reason": str(exc),
            "scientifically_validated": False, "product_qualified": False,
            "wall_seconds": time.perf_counter() - started_wall,
            "cpu_seconds": time.process_time() - started_cpu,
        }
        sys.stderr.buffer.write(_cli._canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

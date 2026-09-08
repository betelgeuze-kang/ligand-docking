"""Console adapter from separate explicit components to fixed-pose evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Sequence

from . import cli as _cli
from .fixed_pose_cli import (
    MAX_INPUT_BYTES, _Parser, _exact_keys, _load_object,
    parameters_from_document, require_distinct_output,
)
from .molecular.serialization import all_atom_system_from_canonical_json

COMMAND_ID = "betelgeuze-engine-v2/evaluate-fixed-components/1.0.0"
_COMPONENT_FIELDS = {
    "receptor_system", "receptor_parameters", "ligand_system", "ligand_parameters",
    "frame_declaration", "state_declarations",
}


def evaluate_component_documents(*, components_raw: bytes, pocket_raw: bytes) -> dict:
    """Preserve both parent identities while joining their explicit same-frame inputs."""
    from .docking.fixed_pose_assembly import evaluate_fixed_components

    if max(len(components_raw), len(pocket_raw)) > MAX_INPUT_BYTES:
        raise ValueError("fixed component input exceeds byte limit")
    document = _load_object(components_raw)
    _exact_keys(document, _COMPONENT_FIELDS, "components")
    systems, parameters = {}, {}
    for side in ("receptor", "ligand"):
        source = document[side + "_system"]
        _exact_keys(source, {"schema_id", "system_sha256", "system"}, side + " canonical system")
        systems[side] = all_atom_system_from_canonical_json(
            _cli._canonical_bytes(source), device="cpu")
        parameters[side] = parameters_from_document(document[side + "_parameters"])
    pocket_document = _load_object(pocket_raw)
    result = evaluate_fixed_components(
        systems["receptor"], parameters["receptor"], systems["ligand"], parameters["ligand"],
        pocket=_cli._pocket_from_document(pocket_document),
        frame_declaration=document["frame_declaration"],
        state_declarations=document["state_declarations"],
    )
    result.update({
        "command_id": COMMAND_ID,
        "input_bytes_sha256": {"components": hashlib.sha256(components_raw).hexdigest(),
                               "pocket": hashlib.sha256(pocket_raw).hexdigest()},
        "pocket_input": pocket_document,
    })
    json.dumps(result, allow_nan=False)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(prog="betelgeuze-engine-v2 evaluate-fixed-components",
                     description="Join explicit same-frame components and evaluate one fixed pose on CPU.")
    parser.add_argument("--components", type=Path, required=True)
    parser.add_argument("--pocket", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    result = None
    try:
        args = parser.parse_args(argv)
        require_distinct_output(args.output, [args.components, args.pocket])
        result = evaluate_component_documents(
            components_raw=_cli._read_bounded(args.components, maximum=MAX_INPUT_BYTES, name="components"),
            pocket_raw=_cli._read_bounded(args.pocket, maximum=MAX_INPUT_BYTES, name="pocket"),
        )
        result.update({"requested_count": 1, "evaluated_count": 1, "failure_count": 0})
        result["consumer_cost"] = {
            "wall_seconds": time.perf_counter() - wall_start,
            "cpu_seconds": time.process_time() - cpu_start,
            "scope": "input_read_decode_assembly_validation_and_evaluation_excludes_import_and_output_write",
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
            "failure_stage": "output" if result is not None else "input_assembly_or_evaluation",
            "error_code": type(exc).__name__, "reason": str(exc),
            "scientifically_validated": False, "product_qualified": False,
            "wall_seconds": time.perf_counter() - wall_start,
            "cpu_seconds": time.process_time() - cpu_start,
        }
        sys.stderr.buffer.write(_cli._canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only installed FIT-only verification of a bound receptor v4 intake.

The verifier rederives every cached row from its raw sources and the supplied
identity universe. It does not fit a model, open evaluation outcomes, prepare
physical states, or authorize training/product use. The receipt is a local
integrity observation, not source authentication.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

from rdkit import rdBase

from . import native_v4_bound as bound
from . import native_v4_chemical_identity as chemical
from . import native_v4_measurement as measurement
from . import native_v4_primary as primary
from . import native_v4_receptor as receptor
from . import public_assay_components as components
from . import residual_evidence

REFERENCE_SCHEMA = "installed_native_v4_fit_source_reference_v1"
RESULT_SCHEMA = "installed_native_v4_fit_source_verification_v1"


def _source_reference(value: dict) -> dict:
    if (type(value) is not dict or set(value) != {
        "schema_version", "input_dir", "summary_sha256", "phase"
    } or value["schema_version"] != REFERENCE_SCHEMA or value["phase"] != "fit"
            or type(value["input_dir"]) is not str
            or type(value["summary_sha256"]) is not str):
        raise ValueError("unsupported_installed_native_v4_source_reference")
    directory = Path(value["input_dir"])
    if (not directory.is_absolute() or directory.resolve(strict=True) != directory
            or not directory.is_dir()):
        raise ValueError("noncanonical_or_missing_native_intake_dir")
    chemical.require_sha(value["summary_sha256"], value["summary_sha256"])
    return value


def _implementation_binding() -> dict:
    try:
        distribution_version = importlib.metadata.version("betelgeuze-md-product")
    except importlib.metadata.PackageNotFoundError:
        distribution_version = None
    modules = {
        "installed_native_v4_source": sys.modules[__name__],
        "native_v4_bound": bound,
        "native_v4_chemical_identity": chemical,
        "native_v4_measurement": measurement,
        "native_v4_primary": primary,
        "native_v4_receptor": receptor,
        "public_assay_components": components,
        "residual_evidence": residual_evidence,
    }
    return {
        "modules_sha256": {
            name: chemical.file_sha(Path(module.__file__))
            for name, module in sorted(modules.items())
        },
        "rdkit_version": rdBase.rdkitVersion,
        "distribution_version": distribution_version,
        "implementation_root": str(Path(__file__).resolve().parent),
        "python_version": list(sys.version_info[:3]),
    }


def _verified_intake(reference: dict) -> tuple[dict, dict, list[dict]]:
    """Return the receipt and source-derived scope/rows from one verification."""
    reference = _source_reference(reference)
    directory = Path(reference["input_dir"])
    summary = bound.bound_json({
        "path": str(directory / "summary.json"),
        "sha256": reference["summary_sha256"],
    })
    summary_fields = {
        "schema_version", "phase", "manifest_path", "manifest_sha256",
        "records_sha256", "split_plan_sha256", "intake_scope_sha256",
        "identity_context_sha256", "requested_metadata_rows",
        "assigned_role_counts", "point_eligible", "exclusions",
    }
    if (type(summary) is not dict
            or set(summary) != summary_fields
            or summary.get("schema_version") != bound.SCHEMA_V4
            or summary.get("phase") != "fit"
            or type(summary.get("manifest_path")) is not str
            or type(summary.get("manifest_sha256")) is not str):
        raise ValueError("unsupported_installed_native_v4_summary")
    manifest = bound.bound_json({
        "path": summary["manifest_path"],
        "sha256": summary["manifest_sha256"],
    })
    receptor.validate_manifest(manifest)
    scope = bound.bound_json(manifest["scope"])
    receptor.validate_scope(scope)
    if scope.get("target_annotation") != primary.TARGET:
        raise ValueError("unsupported_installed_native_v4_target")
    # This rederives the entire supplied graph and every cached row from bound
    # raw source bytes. The checkout's old v4 checkpoint is never accepted.
    checked_summary, plan, scope, rows = receptor.load_intake(
        directory, reference["summary_sha256"], "fit"
    )
    component_roles = {}
    for row in rows:
        role = row["assigned_role"]
        if role not in bound.ROLES:
            raise ValueError("unsupported_installed_native_v4_role")
        component = row["component_id"]
        if component in component_roles and component_roles[component] != role:
            raise ValueError("cross_role_component_leakage")
        component_roles[component] = role
        if (role != "fit" and (row["native_activity"] is not None
                               or row["observation"] is not None
                               or row["eligible_for_point_model"])):
            raise ValueError("nonfit_observation_in_installed_v4_source")
        if role == "fit" and row["assignment"]["role"] != "fit":
            raise ValueError("invalid_installed_native_fit_assignment")
    result = {
        "schema_version": RESULT_SCHEMA,
        "source_reference": reference.copy(),
        "source_reference_sha256": components.digest(components.canonical(reference)),
        "source_manifest": {
            "path": checked_summary["manifest_path"],
            "sha256": checked_summary["manifest_sha256"],
        },
        "records_sha256": checked_summary["records_sha256"],
        "identity_context_sha256": checked_summary["identity_context_sha256"],
        "requested_metadata_rows": len(rows),
        "assigned_role_counts": plan["counts"],
        "point_eligible": sum(row["eligible_for_point_model"] for row in rows),
        "component_count_in_supplied_rows": len(component_roles),
        "implementation_runtime": _implementation_binding(),
        "evaluation_labels_read": 0,
        "model_fit_performed": False,
        "engine_calls": 0,
        "source_authenticated": False,
        "scientifically_validated": False,
        "same_prepared_assay_state_verified": False,
        "product_ranking_enabled": False,
    }
    return result, scope, rows


def verify_source(reference: dict) -> dict:
    """Recheck source bytes, roles, graph, measurements and cached v4 records."""
    result, _, _ = _verified_intake(reference)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify-source", "verify-receipt"))
    parser.add_argument("path", type=Path, help="Bound reference or prior receipt JSON")
    args = parser.parse_args(argv)
    supplied = components.loads(args.path.read_text())
    if args.action == "verify-source":
        result = verify_source(supplied)
    else:
        if (type(supplied) is not dict
                or supplied.get("schema_version") != RESULT_SCHEMA):
            raise ValueError("unsupported_installed_native_v4_receipt")
        result = verify_source(supplied["source_reference"])
        if result != supplied:
            raise ValueError("installed_native_v4_receipt_does_not_match_source")
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

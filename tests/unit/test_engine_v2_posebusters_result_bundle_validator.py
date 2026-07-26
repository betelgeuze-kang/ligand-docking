from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_result_bundle_validator as validator,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_result_bundle_validator import (  # noqa: E402
    POSEBUSTERS_RESULT_BUNDLE_BLOCKERS,
    POSEBUSTERS_RESULT_BUNDLE_MANIFEST_SCHEMA_ID,
    POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES,
    POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES,
    PoseBustersResultBundleValidationError,
    validate_posebusters_result_bundle,
    verify_posebusters_result_bundle_validation_receipt,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _write_canonical(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(payload) + b"\n")
    path.chmod(0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_receipt(path: Path, payload: dict[str, object]) -> str:
    receipt_sha = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    _write_canonical(path, {**payload, "receipt_sha256": receipt_sha})
    return receipt_sha


def _claim_closed(schema_id: str, **extra: object) -> dict[str, object]:
    return {
        "schema_id": schema_id,
        "benchmark_executed": False,
        "scientifically_validated": False,
        "claim_safe": False,
        **extra,
    }


def _bundle(
    tmp_path: Path,
    *,
    omit_roles: tuple[str, ...] = (),
    crosswire: str | None = None,
    unknown_role: bool = False,
) -> dict[str, object]:
    root = tmp_path / "bundle"
    root.mkdir(parents=True, exist_ok=True)
    schemas = validator._ROLE_SCHEMA_IDS
    digests: dict[str, str] = {}

    digests["archive_intake"] = _write_receipt(
        root / "archive-intake.json",
        _claim_closed(schemas["archive_intake"]),
    )
    digests["corpus_audit"] = _write_receipt(
        root / "corpus-audit.json",
        _claim_closed(
            schemas["corpus_audit"],
            archive_intake_receipt_sha256=digests["archive_intake"],
        ),
    )
    digests["internal_preparation"] = _write_receipt(
        root / "preparation.json",
        _claim_closed(
            schemas["internal_preparation"],
            archive_intake_receipt_sha256=digests["archive_intake"],
            corpus_audit_receipt_sha256=digests["corpus_audit"],
        ),
    )
    digests["internal_execution"] = _write_receipt(
        root / "execution.json",
        _claim_closed(
            schemas["internal_execution"],
            preparation_receipt_sha256=digests["internal_preparation"],
        ),
    )
    digests["internal_rmsd_evaluation"] = _write_receipt(
        root / "rmsd.json",
        _claim_closed(
            schemas["internal_rmsd_evaluation"],
            archive_intake_receipt_sha256=digests["archive_intake"],
            execution_receipt_sha256=digests["internal_execution"],
        ),
    )
    oracle_execution = (
        digests["internal_preparation"]
        if crosswire == "oracle_execution"
        else digests["internal_execution"]
    )
    digests["internal_oracle_evaluation"] = _write_receipt(
        root / "oracle.json",
        _claim_closed(
            schemas["internal_oracle_evaluation"],
            archive_intake_receipt_sha256=digests["archive_intake"],
            internal_rmsd_receipt_sha256=digests["internal_rmsd_evaluation"],
            internal_execution_receipt_sha256=oracle_execution,
        ),
    )
    digests["internal_oracle_runtime_observation"] = _write_receipt(
        root / "runtime.json",
        _claim_closed(
            schemas["internal_oracle_runtime_observation"],
            oracle_receipt_sha256=digests["internal_oracle_evaluation"],
        ),
    )
    digests["internal_oracle_stratification"] = _write_receipt(
        root / "strata.json",
        _claim_closed(
            schemas["internal_oracle_stratification"],
            archive_intake_receipt_sha256=digests["archive_intake"],
            corpus_audit_receipt_sha256=digests["corpus_audit"],
            preparation_receipt_sha256=digests["internal_preparation"],
            oracle_receipt_sha256=digests["internal_oracle_evaluation"],
            runtime_observation_receipt_sha256=digests[
                "internal_oracle_runtime_observation"
            ],
        ),
    )
    digests["same_input_engine_comparison"] = _write_receipt(
        root / "comparison.json",
        _claim_closed(
            schemas["same_input_engine_comparison"],
            archive_intake_receipt_sha256=digests["archive_intake"],
        ),
    )

    paths = {
        "archive_intake": "archive-intake.json",
        "corpus_audit": "corpus-audit.json",
        "internal_preparation": "preparation.json",
        "internal_execution": "execution.json",
        "internal_rmsd_evaluation": "rmsd.json",
        "internal_oracle_evaluation": "oracle.json",
        "internal_oracle_runtime_observation": "runtime.json",
        "internal_oracle_stratification": "strata.json",
        "same_input_engine_comparison": "comparison.json",
    }
    receipts = [
        {
            "role": role,
            "relative_path": relative_path,
            "receipt_sha256": digests[role],
        }
        for role, relative_path in paths.items()
        if role not in omit_roles
    ]
    if unknown_role:
        receipts.append(
            {
                "role": "unregistered_role",
                "relative_path": "archive-intake.json",
                "receipt_sha256": digests["archive_intake"],
            }
        )
    manifest_path = tmp_path / "manifest.json"
    manifest_sha = _write_canonical(
        manifest_path,
        {
            "schema_id": POSEBUSTERS_RESULT_BUNDLE_MANIFEST_SCHEMA_ID,
            "receipts": receipts,
        },
    )
    return {
        "root": root,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_sha,
        "digests": digests,
    }


def test_complete_bundle_validates_and_stays_claim_closed(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = validate_posebusters_result_bundle(
        bundle["root"],
        bundle["manifest_path"],
        expected_manifest_sha256=str(bundle["manifest_sha256"]),
    )
    payload = receipt.to_dict()

    assert payload["status"] == "bundle_structurally_valid"
    assert payload["bundle_manifest_receipt_count"] == 9
    assert payload["missing_optional_roles"] == []
    assert set(payload["present_roles"]) == set(
        (*POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES, *POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES)
    )
    assert payload["bundle_structurally_complete"] is True
    assert payload["every_declared_link_resolved_within_the_bundle"] is True
    assert payload["every_receipt_claim_closed"] is True
    assert payload["physics_reexecuted"] is False
    assert payload["metrics_recomputed"] is False
    assert payload["bundle_manifest_signature_verified"] is False
    assert payload["benchmark_executed"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        POSEBUSTERS_RESULT_BUNDLE_BLOCKERS
    )
    assert payload["resolved_link_count"] == len(validator._ROLE_LINKS)
    assert all(row["resolved_within_bundle"] for row in payload["resolved_link_rows"])
    assert all(row["claim_closed"] for row in payload["role_rows"])


def test_optional_roles_may_be_absent(tmp_path: Path) -> None:
    bundle = _bundle(
        tmp_path,
        omit_roles=(
            "internal_oracle_runtime_observation",
            "internal_oracle_stratification",
            "same_input_engine_comparison",
        ),
    )
    payload = validate_posebusters_result_bundle(
        bundle["root"],
        bundle["manifest_path"],
        expected_manifest_sha256=str(bundle["manifest_sha256"]),
    ).to_dict()
    assert payload["present_roles"] == sorted(
        POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES
    )
    assert payload["missing_optional_roles"] == list(
        POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES
    )
    assert payload["resolved_link_count"] < len(validator._ROLE_LINKS)


@pytest.mark.parametrize("omitted", POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES)
def test_missing_required_role_fails_closed(tmp_path: Path, omitted: str) -> None:
    bundle = _bundle(tmp_path, omit_roles=(omitted,))
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="omits required role",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=str(bundle["manifest_sha256"]),
        )


def test_stratification_requires_its_runtime_observation(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, omit_roles=("internal_oracle_runtime_observation",))
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="requires internal_oracle_runtime_observation",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=str(bundle["manifest_sha256"]),
        )


def test_crosswired_upstream_link_fails_closed(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, crosswire="oracle_execution")
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="does not reference the bundled internal_execution",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=str(bundle["manifest_sha256"]),
        )


def test_unknown_role_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, unknown_role=True)
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="unknown role unregistered_role",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=str(bundle["manifest_sha256"]),
        )


def test_manifest_digest_pin_and_receipt_tamper_fail_closed(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="differs from its expected identity",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256="0" * 64,
        )

    tampered = Path(str(bundle["root"])) / "oracle.json"
    tampered.write_bytes(tampered.read_bytes() + b" ")
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="bytes are not canonical",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=str(bundle["manifest_sha256"]),
        )


def test_claim_open_bundled_receipt_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    path = Path(str(bundle["root"])) / "comparison.json"
    payload = _claim_closed(
        validator._ROLE_SCHEMA_IDS["same_input_engine_comparison"],
        archive_intake_receipt_sha256=str(
            dict(bundle["digests"])["archive_intake"]  # type: ignore[arg-type]
        ),
    )
    payload["claim_safe"] = True
    digest = _write_receipt(path, payload)
    manifest = json.loads(
        Path(str(bundle["manifest_path"])).read_text(encoding="ascii")
    )
    for entry in manifest["receipts"]:
        if entry["role"] == "same_input_engine_comparison":
            entry["receipt_sha256"] = digest
    manifest_sha = _write_canonical(Path(str(bundle["manifest_path"])), manifest)
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="must keep claim_safe=false",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=manifest_sha,
        )


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    manifest = json.loads(
        Path(str(bundle["manifest_path"])).read_text(encoding="ascii")
    )
    for entry in manifest["receipts"]:
        if entry["role"] == "archive_intake":
            entry["relative_path"] = "../manifest.json"
    manifest_sha = _write_canonical(Path(str(bundle["manifest_path"])), manifest)
    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="escapes the bundle root",
    ):
        validate_posebusters_result_bundle(
            bundle["root"],
            bundle["manifest_path"],
            expected_manifest_sha256=manifest_sha,
        )


def test_validation_receipt_reconstructs_exactly(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = validate_posebusters_result_bundle(
        bundle["root"],
        bundle["manifest_path"],
        expected_manifest_sha256=str(bundle["manifest_sha256"]),
    )
    output = tmp_path / "receipts" / "bundle-validation.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    verified = verify_posebusters_result_bundle_validation_receipt(
        validation_receipt_path=output,
        bundle_root=bundle["root"],
        manifest_path=bundle["manifest_path"],
        expected_validation_receipt_sha256=receipt.fingerprint_sha256,
        expected_manifest_sha256=str(bundle["manifest_sha256"]),
    )
    assert verified.canonical_bytes() == receipt.canonical_bytes()

    with pytest.raises(
        PoseBustersResultBundleValidationError,
        match="already exists",
    ):
        receipt.write_json(output)


def test_cli_validate_and_verify_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _bundle(tmp_path)
    flags = [
        "--bundle-root",
        str(bundle["root"]),
        "--manifest",
        str(bundle["manifest_path"]),
        "--expected-manifest-sha256",
        str(bundle["manifest_sha256"]),
    ]
    output = tmp_path / "cli-bundle-validation.json"
    assert validator.main(["validate", *flags, "--output", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "bundle_structurally_valid"
    assert summary["present_role_count"] == 9
    assert summary["claim_safe"] is False

    document = json.loads(output.read_text(encoding="ascii"))
    assert (
        validator.main(
            [
                "verify",
                *flags,
                "--receipt",
                str(output),
                "--expected-validation-receipt-sha256",
                document["receipt_sha256"],
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["bundle_structurally_complete"] is True


def test_cli_help_states_the_structural_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        validator.main(["--help"])
    output = capsys.readouterr().out
    assert "result bundle" in output
    assert "claim" in output

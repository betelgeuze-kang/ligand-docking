from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    public_pose_ranking_fit_validation_custody as custody,
)
from betelgeuze_engine_v2.benchmark import (
    public_pose_ranking_fit_validation_selection as selection,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
from tests.unit.test_engine_v2_public_pose_ranking_calibration_partition_intake import (
    _fit_validation_fixture,
    _sha,
)


_REGISTERED_AT = "2026-07-24T10:00:00Z"
_RELEASED_AT = "2026-07-24T11:00:00Z"
_CHECKED_AT = "2026-07-24T12:00:00Z"
_EXPIRES_AT = "2026-08-01T10:00:00Z"
_REGISTRAR_KEY = bytes(range(32))
_CUSTODIAN_KEY = bytes(range(1, 33))


def _sign_registration_for_test(
    *,
    signing_key: bytes,
    **payload_arguments: object,
) -> dict[str, object]:
    request = (
        custody.build_public_pose_ranking_preregistration_signing_request(
            **payload_arguments
        )
    )
    return custody.attach_public_pose_ranking_preregistration_signature(
        request,
        signature_hex=sign_ed25519(
            custody.public_pose_ranking_preregistration_signing_bytes(
                request
            ),
            signing_key,
        ),
        verification_key=ed25519_public_key_bytes(signing_key),
    )


def _sign_release_for_test(
    request: object,
    *,
    signing_key: bytes,
) -> dict[str, object]:
    return custody.attach_public_pose_ranking_validation_release_signature(
        request,
        signature_hex=sign_ed25519(
            custody.public_pose_ranking_validation_release_signing_bytes(
                request
            ),
            signing_key,
        ),
        verification_key=ed25519_public_key_bytes(signing_key),
    )


def _empty_state_json() -> str:
    return json.dumps(
        {
            "revoked_registrar_key_ids": [],
            "revoked_registration_receipt_sha256s": [],
            "superseded_registration_receipt_sha256s": [],
            "revoked_custodian_key_ids": [],
            "revoked_release_receipt_sha256s": [],
            "superseded_release_receipt_sha256s": [],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _fixture() -> dict[str, object]:
    training_view, validation_partition, manifest, _ = (
        _fit_validation_fixture()
    )
    bound = {
        "training_view_receipt": training_view,
        "training_view_receipt_source_file_sha256": _sha(
            "training-view-receipt:file"
        ),
        "training_view_receipt_source_file_size_bytes": 32768,
        "validation_partition": validation_partition,
        "manifest": manifest,
        "manifest_source_file_sha256": _sha("candidate-manifest:file"),
        "manifest_source_file_size_bytes": 4096,
    }
    registrar_identity = _sha("independent-registrar")
    training_operator_identity = _sha("training-operator")
    custodian_identity = _sha("validation-custodian")
    evaluation_operator_identity = _sha("evaluation-operator")
    registration_arguments = {
        **bound,
        "registrar_identity_sha256": registrar_identity,
        "registrar_key_id": "registrar-v1",
        "training_operator_identity_sha256": training_operator_identity,
        "validation_custodian_identity_sha256": custodian_identity,
        "validation_custodian_key_id": "custodian-v1",
        "evaluation_operator_identity_sha256": evaluation_operator_identity,
        "registered_at_utc": _REGISTERED_AT,
        "expires_at_utc": _EXPIRES_AT,
        "registration_nonce_sha256": _sha("registration-nonce"),
    }
    request = (
        custody.build_public_pose_ranking_preregistration_signing_request(
            **registration_arguments
        )
    )
    signed_registration = (
        _sign_registration_for_test(
            signing_key=_REGISTRAR_KEY,
            **registration_arguments,
        )
    )
    registrar_trust = {
        "registrar-v1": custody.PublicPoseRankingCustodyTrustAnchor(
            identity_sha256=registrar_identity,
            verification_key=ed25519_public_key_bytes(_REGISTRAR_KEY),
        )
    }
    release_arguments = {
        **bound,
        "trusted_registrar_keys": registrar_trust,
        "revoked_registrar_key_ids": (),
        "revoked_registration_receipt_sha256s": (),
        "superseded_registration_receipt_sha256s": (),
        "custodian_identity_sha256": custodian_identity,
        "custodian_key_id": "custodian-v1",
        "released_at_utc": _RELEASED_AT,
        "release_nonce_sha256": _sha("release-nonce"),
    }
    release_request = (
        custody.build_public_pose_ranking_validation_release_signing_request(
            signed_registration,
            **release_arguments,
        )
    )
    signed_release = (
        _sign_release_for_test(
            release_request,
            signing_key=_CUSTODIAN_KEY,
        )
    )
    custodian_trust = {
        "custodian-v1": custody.PublicPoseRankingCustodyTrustAnchor(
            identity_sha256=custodian_identity,
            verification_key=ed25519_public_key_bytes(_CUSTODIAN_KEY),
        )
    }
    materialization_arguments = {
        "signed_registration": signed_registration,
        "signed_release": signed_release,
        **bound,
        "trusted_registrar_keys": registrar_trust,
        "trusted_custodian_keys": custodian_trust,
        "checked_at_utc": _CHECKED_AT,
        "revoked_registrar_key_ids": (),
        "revoked_registration_receipt_sha256s": (),
        "superseded_registration_receipt_sha256s": (),
        "revoked_custodian_key_ids": (),
        "revoked_release_receipt_sha256s": (),
        "superseded_release_receipt_sha256s": (),
    }
    admission = (
        custody.materialize_public_pose_ranking_fit_validation_custody_admission(
            **materialization_arguments
        )
    )
    return {
        "training_view": training_view,
        "validation_partition": validation_partition,
        "manifest": manifest,
        "bound": bound,
        "registration_arguments": registration_arguments,
        "request": request,
        "signed_registration": signed_registration,
        "registrar_trust": registrar_trust,
        "release_arguments": release_arguments,
        "release_request": release_request,
        "signed_release": signed_release,
        "custodian_trust": custodian_trust,
        "materialization_arguments": materialization_arguments,
        "admission": admission,
    }


def test_registration_is_label_blind_secret_free_and_signed() -> None:
    values = _fixture()
    request = values["request"]
    payload = request["registration_payload"]
    validation = values["validation_partition"]
    serialized = json.dumps(
        request,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )

    for row in validation.rows:
        assert row.pose_id not in serialized
        assert row.case_id not in serialized
    assert '"native_like"' not in serialized
    assert '"term_values"' not in serialized
    assert "private_key" not in serialized
    assert "signing_key" not in serialized
    assert payload["validation_rows_disclosed"] is False
    assert payload["validation_labels_disclosed"] is False
    assert payload["validation_class_counts_disclosed"] is False
    assert payload["validation_metrics_disclosed"] is False
    assert request["signing_bytes_sha256"] == hashlib.sha256(
        custody.public_pose_ranking_preregistration_signing_bytes(request)
    ).hexdigest()

    verified = custody.verify_signed_public_pose_ranking_preregistration(
        values["signed_registration"],
        **values["bound"],
        trusted_registrar_keys=values["registrar_trust"],
        checked_at_utc=_CHECKED_AT,
        revoked_registrar_key_ids=(),
        revoked_registration_receipt_sha256s=(),
        superseded_registration_receipt_sha256s=(),
    )
    assert verified == payload


def test_release_requires_later_time_distinct_role_and_fresh_nonce() -> None:
    values = _fixture()
    request = values["release_request"]
    payload = request["release_payload"]

    assert payload["registered_at_utc"] == _REGISTERED_AT
    assert payload["released_at_utc"] == _RELEASED_AT
    assert payload["validation_labels_released_after_registration"] is True
    assert request["signing_bytes_sha256"] == hashlib.sha256(
        custody.public_pose_ranking_validation_release_signing_bytes(request)
    ).hexdigest()

    bad = dict(values["release_arguments"])
    bad["released_at_utc"] = _REGISTERED_AT
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="must follow registration",
    ):
        custody.build_public_pose_ranking_validation_release_signing_request(
            values["signed_registration"],
            **bad,
        )

    bad = dict(values["release_arguments"])
    bad["release_nonce_sha256"] = _sha("registration-nonce")
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="nonce reuses",
    ):
        custody.build_public_pose_ranking_validation_release_signing_request(
            values["signed_registration"],
            **bad,
        )

    bad = dict(values["registration_arguments"])
    bad["evaluation_operator_identity_sha256"] = bad[
        "training_operator_identity_sha256"
    ]
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="distinct identities",
    ):
        custody.build_public_pose_ranking_preregistration_signing_request(
            **bad
        )


def test_trust_signature_revocation_supersession_and_expiry_fail_closed() -> None:
    values = _fixture()
    verify_arguments = {
        **values["bound"],
        "trusted_registrar_keys": values["registrar_trust"],
        "checked_at_utc": _CHECKED_AT,
        "revoked_registrar_key_ids": (),
        "revoked_registration_receipt_sha256s": (),
        "superseded_registration_receipt_sha256s": (),
    }

    tampered = deepcopy(values["signed_registration"])
    tampered["signature"]["value"] = "0" * 128
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="signature verification failed",
    ):
        custody.verify_signed_public_pose_ranking_preregistration(
            tampered,
            **verify_arguments,
        )

    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="key is revoked",
    ):
        custody.verify_signed_public_pose_ranking_preregistration(
            values["signed_registration"],
            **{
                **verify_arguments,
                "revoked_registrar_key_ids": ("registrar-v1",),
            },
        )

    registration_sha = values["signed_registration"][
        "registration_receipt_sha256"
    ]
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="receipt is superseded",
    ):
        custody.verify_signed_public_pose_ranking_preregistration(
            values["signed_registration"],
            **{
                **verify_arguments,
                "superseded_registration_receipt_sha256s": (
                    registration_sha,
                ),
            },
        )

    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="not currently valid",
    ):
        custody.verify_signed_public_pose_ranking_preregistration(
            values["signed_registration"],
            **{
                **verify_arguments,
                "checked_at_utc": "2026-08-02T10:00:00Z",
            },
        )

    release_sha = values["signed_release"]["release_receipt_sha256"]
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="receipt is revoked",
    ):
        custody.verify_signed_public_pose_ranking_validation_release(
            values["signed_release"],
            signed_registration_value=values["signed_registration"],
            **values["bound"],
            trusted_registrar_keys=values["registrar_trust"],
            trusted_custodian_keys=values["custodian_trust"],
            checked_at_utc=_CHECKED_AT,
            revoked_registrar_key_ids=(),
            revoked_registration_receipt_sha256s=(),
            superseded_registration_receipt_sha256s=(),
            revoked_custodian_key_ids=(),
            revoked_release_receipt_sha256s=(release_sha,),
            superseded_release_receipt_sha256s=(),
        )


def test_private_material_malformed_signature_and_crosswire_are_rejected() -> None:
    values = _fixture()
    request = deepcopy(values["request"])
    request["registration_payload"]["private_key_hex"] = "00" * 32
    request["registration_payload"]["registration_receipt_sha256"] = (
        _canonical_sha256(
            {
                key: value
                for key, value in request["registration_payload"].items()
                if key != "registration_receipt_sha256"
            }
        )
    )
    request["signing_bytes_sha256"] = hashlib.sha256(
        json.dumps(
            request["registration_payload"],
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    request["request_sha256"] = _canonical_sha256(
        {
            key: value
            for key, value in request.items()
            if key != "request_sha256"
        }
    )
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="private signing material",
    ):
        custody.require_public_pose_ranking_preregistration_signing_request(
            request
        )

    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="64-byte Ed25519 signature",
    ):
        custody.attach_public_pose_ranking_preregistration_signature(
            values["request"],
            signature_hex="00",
            verification_key=ed25519_public_key_bytes(_REGISTRAR_KEY),
        )

    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="detached preregistration signature verification failed",
    ):
        custody.attach_public_pose_ranking_preregistration_signature(
            values["request"],
            signature_hex=values["signed_registration"]["signature"][
                "value"
            ],
            verification_key=ed25519_public_key_bytes(_CUSTODIAN_KEY),
        )


def test_admission_is_exact_claim_closed_and_manifest_tamper_evident() -> None:
    values = _fixture()
    admission = values["admission"]

    assert admission["admitted_for_fit_validation_execution"] is True
    assert admission["registration_signature_verified"] is True
    assert admission["release_signature_verified"] is True
    assert admission["scientifically_validated"] is False
    assert admission["production_eligible"] is False
    assert admission["claim_safe"] is False
    assert admission["scientific_blockers"] == list(
        custody.PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS
    )
    assert (
        custody.require_public_pose_ranking_fit_validation_custody_admission(
            admission,
            **values["materialization_arguments"],
        )
        == admission
    )

    tampered = deepcopy(admission)
    tampered["candidate_manifest_sha256"] = _sha("different-manifest")
    projection = {
        key: value
        for key, value in tampered.items()
        if key != "custody_admission_sha256"
    }
    tampered["custody_admission_sha256"] = _canonical_sha256(projection)
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="evidence or claim boundary",
    ):
        custody.validate_public_pose_ranking_fit_validation_custody_admission_structure(
            tampered
        )

    crosswired = deepcopy(admission)
    release = crosswired["signed_release"]
    release["training_partition_sha256"] = _sha(
        "crosswired-training-partition"
    )
    release_projection = {
        key: value
        for key, value in release.items()
        if key not in {"release_receipt_sha256", "signature"}
    }
    release["release_receipt_sha256"] = _canonical_sha256(
        release_projection
    )
    crosswired["release_receipt_sha256"] = release[
        "release_receipt_sha256"
    ]
    crosswired["custody_admission_sha256"] = _canonical_sha256(
        {
            key: value
            for key, value in crosswired.items()
            if key != "custody_admission_sha256"
        }
    )
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="evidence or claim boundary",
    ):
        custody.validate_public_pose_ranking_fit_validation_custody_admission_structure(
            crosswired
        )


def test_artifacts_are_canonical_private_no_overwrite_and_mode_checked(
    tmp_path: Path,
) -> None:
    values = _fixture()
    request_path = tmp_path / "registration-request.json"
    signed_registration_path = tmp_path / "signed-registration.json"
    release_request_path = tmp_path / "release-request.json"
    signed_release_path = tmp_path / "signed-release.json"
    admission_path = tmp_path / "custody-admission.json"

    custody.write_public_pose_ranking_custody_artifact(
        request_path,
        values["request"],
    )
    custody.write_public_pose_ranking_custody_artifact(
        signed_registration_path,
        values["signed_registration"],
    )
    custody.write_public_pose_ranking_custody_artifact(
        release_request_path,
        values["release_request"],
    )
    custody.write_public_pose_ranking_custody_artifact(
        signed_release_path,
        values["signed_release"],
    )
    custody.write_public_pose_ranking_custody_artifact(
        admission_path,
        values["admission"],
    )
    assert os.stat(request_path, follow_symlinks=False).st_mode & 0o777 == 0o600
    assert (
        os.stat(admission_path, follow_symlinks=False).st_mode & 0o777
        == 0o600
    )
    admission_data = admission_path.read_bytes()
    assert admission_data == json.dumps(
        values["admission"],
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"
    assert custody.read_public_pose_ranking_custody_admission(
        admission_path,
        expected_file_sha256=hashlib.sha256(admission_data).hexdigest(),
        expected_admission_sha256=values["admission"][
            "custody_admission_sha256"
        ],
    ) == values["admission"]
    request_data = request_path.read_bytes()
    assert custody.read_public_pose_ranking_preregistration_signing_request(
        request_path,
        expected_file_sha256=hashlib.sha256(request_data).hexdigest(),
        expected_request_sha256=values["request"]["request_sha256"],
    ) == values["request"]
    signed_registration_data = signed_registration_path.read_bytes()
    assert custody.read_signed_public_pose_ranking_preregistration(
        signed_registration_path,
        expected_file_sha256=hashlib.sha256(
            signed_registration_data
        ).hexdigest(),
        expected_registration_receipt_sha256=values[
            "signed_registration"
        ]["registration_receipt_sha256"],
    ) == values["signed_registration"]
    release_request_data = release_request_path.read_bytes()
    assert (
        custody.read_public_pose_ranking_validation_release_signing_request(
            release_request_path,
            expected_file_sha256=hashlib.sha256(
                release_request_data
            ).hexdigest(),
            expected_request_sha256=values["release_request"][
                "request_sha256"
            ],
        )
        == values["release_request"]
    )
    signed_release_data = signed_release_path.read_bytes()
    assert custody.read_signed_public_pose_ranking_validation_release(
        signed_release_path,
        expected_file_sha256=hashlib.sha256(
            signed_release_data
        ).hexdigest(),
        expected_release_receipt_sha256=values["signed_release"][
            "release_receipt_sha256"
        ],
    ) == values["signed_release"]

    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="already exists",
    ):
        custody.write_public_pose_ranking_custody_artifact(
            admission_path,
            values["admission"],
        )

    os.chmod(admission_path, 0o640)
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="mode must be 0600",
    ):
        custody.read_public_pose_ranking_custody_admission(
            admission_path,
            expected_file_sha256=hashlib.sha256(admission_data).hexdigest(),
            expected_admission_sha256=values["admission"][
                "custody_admission_sha256"
            ],
        )


def test_public_key_context_requires_explicit_exact_state_and_distinct_anchors() -> None:
    context = custody.public_pose_ranking_custody_verification_context(
        registrar_key_id="registrar-v1",
        registrar_identity_sha256=_sha("independent-registrar"),
        registrar_public_key_hex=ed25519_public_key_bytes(
            _REGISTRAR_KEY
        ).hex(),
        custodian_key_id="custodian-v1",
        custodian_identity_sha256=_sha("validation-custodian"),
        custodian_public_key_hex=ed25519_public_key_bytes(
            _CUSTODIAN_KEY
        ).hex(),
        custody_state_json=_empty_state_json(),
    )
    assert context["revoked_registrar_key_ids"] == ()
    assert context["superseded_release_receipt_sha256s"] == ()

    incomplete = json.loads(_empty_state_json())
    incomplete.pop("revoked_release_receipt_sha256s")
    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="custody state fields differ",
    ):
        custody.parse_public_pose_ranking_custody_state_json(
            json.dumps(incomplete)
        )

    with pytest.raises(
        custody.PublicPoseRankingFitValidationCustodyError,
        match="trust anchors must be distinct",
    ):
        custody.public_pose_ranking_custody_verification_context(
            registrar_key_id="shared-v1",
            registrar_identity_sha256=_sha("shared"),
            registrar_public_key_hex=ed25519_public_key_bytes(
                _REGISTRAR_KEY
            ).hex(),
            custodian_key_id="shared-v1",
            custodian_identity_sha256=_sha("shared"),
            custodian_public_key_hex=ed25519_public_key_bytes(
                _REGISTRAR_KEY
            ).hex(),
            custody_state_json=_empty_state_json(),
        )


def test_selection_file_path_requires_current_mode_0600_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = _fixture()
    admission_path = tmp_path / "custody-admission.json"
    custody.write_public_pose_ranking_custody_artifact(
        admission_path,
        values["admission"],
    )
    admission_data = admission_path.read_bytes()
    monkeypatch.setattr(
        selection,
        "load_public_pose_ranking_fit_validation_bound_inputs_from_files",
        lambda **_arguments: values["bound"],
    )
    common = {
        "training_view_receipt_path": "bound-by-test",
        "expected_training_view_receipt_file_sha256": _sha(
            "bound-by-test"
        ),
        "expected_training_view_receipt_sha256": _sha("bound-by-test"),
        "ancestry_arguments_path": "bound-by-test",
        "candidate_manifest_path": "bound-by-test",
        "expected_candidate_manifest_file_sha256": _sha("bound-by-test"),
        "expected_candidate_manifest_sha256": _sha("bound-by-test"),
        "custody_admission_path": admission_path,
        "expected_custody_admission_file_sha256": hashlib.sha256(
            admission_data
        ).hexdigest(),
        "expected_custody_admission_sha256": values["admission"][
            "custody_admission_sha256"
        ],
        "trusted_registrar_keys": values["registrar_trust"],
        "trusted_custodian_keys": values["custodian_trust"],
        "custody_checked_at_utc": _CHECKED_AT,
        "revoked_registrar_key_ids": (),
        "revoked_registration_receipt_sha256s": (),
        "superseded_registration_receipt_sha256s": (),
        "revoked_custodian_key_ids": (),
        "revoked_release_receipt_sha256s": (),
        "superseded_release_receipt_sha256s": (),
    }
    receipt = (
        selection.materialize_public_pose_ranking_fit_validation_selection_from_files(
            **common
        )
    )
    assert receipt["independent_preregistration_custody_verified"] is True

    with pytest.raises(
        selection.PublicPoseRankingFitValidationSelectionError,
        match="custody admission is required",
    ):
        selection.materialize_public_pose_ranking_fit_validation_selection_from_files(
            **{
                **common,
                "revoked_registrar_key_ids": ("registrar-v1",),
            }
        )


def test_installed_cli_surfaces_are_public_key_only_and_custody_required() -> None:
    custody_parser = custody._parser()
    selection_parser = selection._parser()
    help_texts = [
        custody_parser.format_help(),
        selection_parser.format_help(),
    ]
    for parser in (custody_parser, selection_parser):
        subparsers = [
            action
            for action in parser._actions
            if hasattr(action, "choices") and action.choices
        ]
        for action in subparsers:
            help_texts.extend(
                child.format_help()
                for child in action.choices.values()
            )
    combined = "\n".join(help_texts).lower()
    assert "private-key" not in combined
    assert "private_key" not in combined
    assert "signing-key" not in combined
    assert "signing_key" not in combined
    assert "--registrar-public-key-hex" in combined
    assert "--custodian-public-key-hex" in combined
    assert "--custody-admission" in combined
    assert "--custody-state-json" in combined


def test_detached_signature_attachment_cli_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    values = _fixture()
    request_path = tmp_path / "registration-request.json"
    signed_registration_path = tmp_path / "signed-registration.json"
    release_request_path = tmp_path / "release-request.json"
    signed_release_path = tmp_path / "signed-release.json"
    custody.write_public_pose_ranking_custody_artifact(
        request_path,
        values["request"],
    )
    request_data = request_path.read_bytes()
    assert custody.main(
        [
            "attach-registration",
            "--registration-request",
            str(request_path),
            "--expected-registration-request-file-sha256",
            hashlib.sha256(request_data).hexdigest(),
            "--expected-registration-request-sha256",
            values["request"]["request_sha256"],
            "--signature-hex",
            values["signed_registration"]["signature"]["value"],
            "--verification-public-key-hex",
            ed25519_public_key_bytes(_REGISTRAR_KEY).hex(),
            "--output",
            str(signed_registration_path),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)[
        "registration_receipt_sha256"
    ] == values["signed_registration"]["registration_receipt_sha256"]
    assert signed_registration_path.read_bytes() == json.dumps(
        values["signed_registration"],
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"

    custody.write_public_pose_ranking_custody_artifact(
        release_request_path,
        values["release_request"],
    )
    release_request_data = release_request_path.read_bytes()
    assert custody.main(
        [
            "attach-release",
            "--release-request",
            str(release_request_path),
            "--expected-release-request-file-sha256",
            hashlib.sha256(release_request_data).hexdigest(),
            "--expected-release-request-sha256",
            values["release_request"]["request_sha256"],
            "--signature-hex",
            values["signed_release"]["signature"]["value"],
            "--verification-public-key-hex",
            ed25519_public_key_bytes(_CUSTODIAN_KEY).hex(),
            "--output",
            str(signed_release_path),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)[
        "release_receipt_sha256"
    ] == values["signed_release"]["release_receipt_sha256"]
    assert signed_release_path.read_bytes() == json.dumps(
        values["signed_release"],
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"

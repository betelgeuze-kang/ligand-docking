import json
from pathlib import Path

from tools import validate_local_delivery_bundle as v


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _pass_fingerprint_check() -> dict:
    return {
        "status": "pass",
        "ok": True,
        "comparison_performed": True,
        "mismatch_count": 0,
    }


def _failed_fingerprint_check() -> dict:
    return {
        "status": "mismatch",
        "ok": False,
        "comparison_performed": True,
        "mismatch_count": 1,
        "mismatches": [{"label": "preflight_json", "field": "sha256"}],
    }


def _family_scorecard_row(
    *,
    bundle_path: str = "artifacts/family_scorecards/kinase_scorecard.json",
    status: str = "pass",
    acceptance_pass: bool = True,
) -> dict:
    return {
        "source_path": "/tmp/kinase_scorecard.json",
        "bundle_path": bundle_path,
        "present": True,
        "sha256": "0" * 64,
        "summary": {
            "family": "kinase",
            "scorecard_level_status": status,
            "acceptance_overall_pass": acceptance_pass,
        },
    }


def _write_signed_manifest(path: Path, payload: dict) -> None:
    payload = dict(payload)
    payload.pop("manifest_signature_sha256", None)
    payload["manifest_signature_sha256"] = v._manifest_signature(payload)
    _write_json(path, payload)


def _write_checksums(bundle_dir: Path) -> None:
    rows = []
    for path in sorted(bundle_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            rows.append(f"{v._sha256_file(path)}  {path.relative_to(bundle_dir).as_posix()}")
    _write_text(bundle_dir / "checksums.sha256", "\n".join(rows) + "\n")


def _make_bundle(
    tmp_path: Path,
    *,
    verdict: str = "Delivery-ready only for the attached restricted local-delivery scope.",
    fingerprint_check: dict | None = None,
    missing_files: list[dict] | None = None,
    included_files: list[dict] | None = None,
    source_artifacts: list[dict] | None = None,
    family_scorecards: list[dict] | None = None,
) -> Path:
    bundle_dir = tmp_path / "bundle"
    _write_text(bundle_dir / "manifest.md", "# Local Delivery Bundle\n")
    _write_text(bundle_dir / "runs" / "local_delivery_preflight_current.json", '{"summary":{"overall_ok":true}}\n')
    for row in included_files or []:
        bundle_path = str(row.get("bundle_path", "")).strip()
        if bundle_path and not bundle_path.startswith("../") and not bundle_path.startswith("/"):
            _write_text(bundle_dir / bundle_path, "{}\n")
    for row in family_scorecards or []:
        bundle_path = str(row.get("bundle_path", "")).strip()
        if bundle_path and not bundle_path.startswith("../") and not bundle_path.startswith("/"):
            _write_json(bundle_dir / bundle_path, {"summary": row.get("summary", {})})
    manifest_included_files = [
        {
            "spec_key": "preflight_json",
            "bundle_path": "runs/local_delivery_preflight_current.json",
            "required": True,
        },
        *(included_files or []),
    ]
    manifest = {
        "verdict": verdict,
        "local_delivery_verdict_gate": {
            "summary": {"delivery_ready": True},
            "source_artifacts": source_artifacts or [],
        },
        "included_files": manifest_included_files,
        "missing_files": missing_files or [],
        "verdict_gate_fingerprint_check": fingerprint_check or _pass_fingerprint_check(),
        "family_scorecards": family_scorecards or [],
    }
    _write_signed_manifest(bundle_dir / "manifest.json", manifest)
    _write_checksums(bundle_dir)
    return bundle_dir


def test_green_bundle_validation_success(tmp_path):
    bundle_dir = _make_bundle(tmp_path)

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is True
    assert summary["blocker_count"] == 0
    assert summary["checksum_mismatch_count"] == 0
    assert summary["missing_file_count"] == 0
    assert summary["delivery_ready_policy_ok"] is True
    assert summary["verdict_gate_fingerprint_check_ok"] is True
    assert (bundle_dir / "validation.json").exists()
    assert "- overall_ok: `True`" in (bundle_dir / "validation.md").read_text(encoding="utf-8")


def test_checksum_mismatch_failure(tmp_path):
    bundle_dir = _make_bundle(tmp_path)
    _write_text(bundle_dir / "runs" / "local_delivery_preflight_current.json", '{"summary":{"overall_ok":false}}\n')

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["checksum_mismatch_count"] == 1
    assert any(blocker["code"] == "checksum_mismatch" for blocker in summary["blockers"])


def test_missing_required_file_failure(tmp_path):
    bundle_dir = _make_bundle(
        tmp_path,
        missing_files=[
            {
                "spec_key": "environment_json",
                "bundle_path": "environment/environment_manifest.json",
                "required": True,
                "reason": "source_missing",
            }
        ],
    )

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["missing_file_count"] == 1
    assert any(blocker["code"] == "required_manifest_file_missing" for blocker in summary["blockers"])


def test_verdict_gate_current_results_index_source_artifact_missing_from_manifest_files_is_required(tmp_path):
    bundle_dir = _make_bundle(
        tmp_path,
        source_artifacts=[
            {"label": "preflight", "path": "runs/local_delivery_preflight_current.json", "required": True},
            {
                "label": "current_results_index",
                "path": "runs/wetlab_current_results_index_current.json",
                "required": True,
            },
            {
                "label": "partnering_stack",
                "path": "runs/wetlab_partnering_stack_current.json",
                "required": True,
            },
        ],
        included_files=[
            {
                "spec_key": "verdict_gate_source_artifact_partnering_stack",
                "bundle_path": "runs/wetlab_partnering_stack_current.json",
                "required": True,
            },
        ],
    )

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["missing_file_count"] == 1
    assert summary["manifest"]["required_missing_files"] == [
        {
            "source": "manifest.local_delivery_verdict_gate.source_artifacts",
            "path": "runs/wetlab_current_results_index_current.json",
            "spec_key": "current_results_index",
            "reason": "required_source_artifact_not_represented_in_manifest_files",
        }
    ]
    assert any(blocker["code"] == "required_manifest_file_missing" for blocker in summary["blockers"])


def test_verdict_gate_partnering_stack_source_artifact_included_but_absent_is_required_missing(tmp_path):
    bundle_dir = _make_bundle(
        tmp_path,
        source_artifacts=[
            {
                "label": "partnering_stack",
                "path": "runs/wetlab_partnering_stack_current.json",
                "required": True,
            },
        ],
        included_files=[
            {
                "spec_key": "verdict_gate_source_artifact_partnering_stack",
                "bundle_path": "runs/wetlab_partnering_stack_current.json",
                "required": True,
            },
        ],
    )
    (bundle_dir / "runs" / "wetlab_partnering_stack_current.json").unlink()
    _write_signed_manifest(
        bundle_dir / "manifest.json",
        json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8")),
    )
    _write_checksums(bundle_dir)

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["missing_file_count"] == 1
    assert summary["manifest"]["required_missing_files"] == [
        {
            "source": "manifest.included_files",
            "path": "runs/wetlab_partnering_stack_current.json",
            "spec_key": "verdict_gate_source_artifact_partnering_stack",
            "reason": "required_included_file_absent_from_bundle",
        },
    ]


def test_delivery_ready_verdict_with_failed_fingerprint_check_failure(tmp_path):
    bundle_dir = _make_bundle(tmp_path, fingerprint_check=_failed_fingerprint_check())

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["delivery_ready_policy_ok"] is False
    assert summary["verdict_gate_fingerprint_check_ok"] is False
    assert any(blocker["code"] == "delivery_ready_fingerprint_check_failed" for blocker in summary["blockers"])


def test_delivery_ready_verdict_with_gate_not_ready_failure(tmp_path):
    bundle_dir = _make_bundle(tmp_path)
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] = False
    manifest.pop("manifest_signature_sha256")
    _write_signed_manifest(bundle_dir / "manifest.json", manifest)
    _write_checksums(bundle_dir)

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["delivery_ready_policy_ok"] is False
    assert summary["verdict_gate_delivery_ready_ok"] is False
    assert any(blocker["code"] == "delivery_ready_verdict_gate_not_ready" for blocker in summary["blockers"])


def test_internal_review_with_failed_fingerprint_check_allowed_but_recorded(tmp_path):
    bundle_dir = _make_bundle(
        tmp_path,
        verdict="Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
        fingerprint_check=_failed_fingerprint_check(),
    )

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is True
    assert summary["delivery_ready_policy_ok"] is True
    assert summary["verdict_gate_fingerprint_check_ok"] is False
    assert summary["manifest"]["verdict_gate_fingerprint_check"]["status"] == "mismatch"


def test_delivery_ready_manifest_with_blocked_family_scorecard_policy_failure(tmp_path):
    bundle_dir = _make_bundle(
        tmp_path,
        family_scorecards=[
            _family_scorecard_row(status="blocked", acceptance_pass=False),
        ],
    )

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["delivery_ready_policy_ok"] is False
    assert summary["manifest"]["family_scorecards"][0]["summary_pass"] is False
    assert any(blocker["code"] == "delivery_ready_family_scorecard_blocked" for blocker in summary["blockers"])


def test_internal_review_manifest_with_blocked_family_scorecard_allowed_but_recorded(
    tmp_path,
):
    bundle_dir = _make_bundle(
        tmp_path,
        verdict="Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
        family_scorecards=[
            _family_scorecard_row(status="blocked", acceptance_pass=False),
        ],
    )

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is True
    assert summary["delivery_ready_policy_ok"] is True
    assert summary["manifest"]["family_scorecards"][0]["summary_pass"] is False
    assert summary["manifest"]["family_scorecards"][0]["reason"] == "family_scorecard_summary_blocked"
    assert "delivery_ready_family_scorecard_blocked" not in {
        blocker["code"] for blocker in summary["blockers"]
    }
    validation_md = (bundle_dir / "validation.md").read_text(encoding="utf-8")
    assert "summary_pass=`False` reason=`family_scorecard_summary_blocked`" in validation_md


def test_family_scorecard_unsafe_bundle_path_is_overall_blocker(tmp_path):
    bundle_dir = _make_bundle(
        tmp_path,
        verdict="Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
        family_scorecards=[
            _family_scorecard_row(bundle_path="../outside.json"),
        ],
    )

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["delivery_ready_policy_ok"] is True
    assert any(blocker["code"] == "family_scorecard_artifact_unsafe" for blocker in summary["blockers"])


def test_family_scorecard_missing_bundle_path_is_overall_blocker(tmp_path):
    row = _family_scorecard_row(bundle_path="artifacts/family_scorecards/missing_scorecard.json")
    bundle_dir = _make_bundle(
        tmp_path,
        verdict="Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
        family_scorecards=[row],
    )
    (bundle_dir / row["bundle_path"]).unlink()
    _write_checksums(bundle_dir)

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["missing_file_count"] == 1
    assert summary["delivery_ready_policy_ok"] is True
    assert any(blocker["code"] == "family_scorecard_artifact_missing" for blocker in summary["blockers"])


def test_manifest_signature_mismatch_failure(tmp_path):
    bundle_dir = _make_bundle(tmp_path)
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["request_summary"] = "tampered without resigning"
    _write_json(bundle_dir / "manifest.json", manifest)
    _write_checksums(bundle_dir)

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert summary["manifest_signature_ok"] is False
    assert any(blocker["code"] == "manifest_signature_invalid" for blocker in summary["blockers"])


def test_unlisted_bundle_file_failure(tmp_path):
    bundle_dir = _make_bundle(tmp_path)
    _write_text(bundle_dir / "artifacts" / "late_result.json", "{}\n")

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert any(blocker["code"] == "checksum_file_unlisted" for blocker in summary["blockers"])
    assert summary["checksum"]["unlisted_files"] == [
        {"path": "artifacts/late_result.json", "reason": "bundle_file_missing_from_checksums"}
    ]


def test_checksum_duplicate_and_unsafe_path_failure(tmp_path):
    bundle_dir = _make_bundle(tmp_path)
    existing = bundle_dir / "manifest.md"
    checksum = v._sha256_file(existing)
    with (bundle_dir / "checksums.sha256").open("a", encoding="utf-8") as handle:
        handle.write(f"{checksum}  manifest.md\n")
        handle.write(f"{checksum}  ../outside.txt\n")

    summary = v.validate_bundle(bundle_dir)

    assert summary["overall_ok"] is False
    assert any(blocker["code"] == "checksum_duplicate_entry" for blocker in summary["blockers"])
    assert any(blocker["code"] == "checksum_row_invalid" for blocker in summary["blockers"])

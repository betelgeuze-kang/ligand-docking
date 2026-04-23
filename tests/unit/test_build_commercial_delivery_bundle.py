import json
import zipfile

from tools import build_commercial_delivery_bundle as b


def _write_base_bundle_fixture(tmp_path, *, nightly_extra_paths=None):
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    nightly_json = runs / "nightly.json"
    nightly_md = runs / "nightly.md"
    external_packet_json = runs / "packet.json"
    dashboard_html = runs / "dashboard.html"
    commercial_json = runs / "commercial.json"
    commercial_csv = runs / "commercial.csv"
    commercial_md = runs / "commercial.md"

    nightly_md.write_text("# nightly\n", encoding="utf-8")
    external_packet_json.write_text("{}", encoding="utf-8")
    dashboard_html.write_text("<html></html>\n", encoding="utf-8")
    commercial_json.write_text(
        json.dumps({"summary": {"readiness_tier": "pilot_ready"}}),
        encoding="utf-8",
    )
    commercial_csv.write_text("a,b\n1,2\n", encoding="utf-8")
    commercial_md.write_text("# commercial\n", encoding="utf-8")

    paths = {
        "batch_summary_md": str(nightly_md),
        "external_packet_json": str(external_packet_json),
        "dashboard_html": str(dashboard_html),
        "commercial_readiness_json": str(commercial_json),
        "commercial_readiness_csv": str(commercial_csv),
        "commercial_readiness_md": str(commercial_md),
    }
    if nightly_extra_paths:
        paths.update(nightly_extra_paths)

    nightly_json.write_text(
        json.dumps(
            {
                "date_tag": "2026-02-19-x",
                "pass": True,
                "commercial_readiness_status": {"readiness_tier": "pilot_ready"},
                "paths": paths,
            }
        ),
        encoding="utf-8",
    )
    return {
        "runs": runs,
        "nightly_json": nightly_json,
    }


def _build_bundle_and_read_outputs(tmp_path, nightly_json, extra_args=None):
    args = b.build_parser().parse_args(
        [
            "--nightly-summary-json",
            str(nightly_json),
            "--out-dir",
            str(tmp_path / "delivery"),
            *(extra_args or []),
        ]
    )
    payload = b.build_bundle(args)
    manifest_path = tmp_path / "delivery" / "bundle_2026-02-19-x" / "manifest.json"
    manifest_md_path = tmp_path / "delivery" / "bundle_2026-02-19-x" / "manifest.md"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_md = manifest_md_path.read_text(encoding="utf-8")
    return payload, manifest, manifest_md


def _write_wetlab_artifacts(base_dir, stem):
    wetlab_json = base_dir / f"{stem}.json"
    wetlab_csv = base_dir / f"{stem}.csv"
    wetlab_md = base_dir / f"{stem}.md"
    wetlab_json.write_text(json.dumps({"summary": {"queue_ready": True, "source": stem}}), encoding="utf-8")
    wetlab_csv.write_text("queue_rank,lane_id,status\n1,primary_dispatch_lane,blocked\n", encoding="utf-8")
    wetlab_md.write_text(f"# {stem}\n", encoding="utf-8")
    return wetlab_json, wetlab_csv, wetlab_md


def test_build_commercial_delivery_bundle_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fixture = _write_base_bundle_fixture(tmp_path)

    payload, manifest, manifest_md = _build_bundle_and_read_outputs(tmp_path, fixture["nightly_json"])

    assert payload["included_count"] == 7
    assert payload["missing_count"] == 0
    assert payload["archive_sha256"]
    assert payload["manifest_signature_sha256"]

    z = payload["archive_zip"]
    assert z.endswith(".zip")
    assert zipfile.is_zipfile(z)

    assert manifest["manifest_signature_sha256"]
    assert manifest["archive"]["sha256"]
    included_names = {row["name"] for row in manifest["included_files"]}
    assert "wetlab_execution_readiness_queue_json" not in included_names
    assert "wetlab_execution_readiness_queue_csv" not in included_names
    assert "wetlab_execution_readiness_queue_md" not in included_names
    assert manifest["wetlab_execution_readiness_status"]["artifact"] == ""
    assert "- queue_ready: `False`" in manifest_md


def test_build_commercial_delivery_bundle_uses_wetlab_defaults_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fixture = _write_base_bundle_fixture(tmp_path)
    _write_wetlab_artifacts(fixture["runs"], "wetlab_execution_readiness_queue_current")

    payload, manifest, manifest_md = _build_bundle_and_read_outputs(tmp_path, fixture["nightly_json"])

    assert payload["included_count"] == 10
    assert payload["missing_count"] == 0
    included_by_name = {row["name"]: row for row in manifest["included_files"]}
    assert included_by_name["wetlab_execution_readiness_queue_json"]["src"] == (
        b.DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_JSON
    )
    assert included_by_name["wetlab_execution_readiness_queue_csv"]["src"] == (
        b.DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_CSV
    )
    assert included_by_name["wetlab_execution_readiness_queue_md"]["src"] == (
        b.DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD
    )
    assert manifest["wetlab_execution_readiness_status"]["artifact"] == (
        b.DEFAULT_WETLAB_EXECUTION_READINESS_QUEUE_MD
    )
    assert "- wetlab_execution_readiness_queue_json:" in manifest_md
    assert "- wetlab_execution_readiness_queue_csv:" in manifest_md
    assert "- wetlab_execution_readiness_queue_md:" in manifest_md


def test_build_commercial_delivery_bundle_prefers_nightly_wetlab_paths_over_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fixture = _write_base_bundle_fixture(tmp_path)
    _write_wetlab_artifacts(fixture["runs"], "wetlab_execution_readiness_queue_current")
    nightly_wetlab_json, nightly_wetlab_csv, nightly_wetlab_md = _write_wetlab_artifacts(
        fixture["runs"],
        "nightly_wetlab_queue",
    )
    fixture = _write_base_bundle_fixture(
        tmp_path,
        nightly_extra_paths={
            "wetlab_execution_readiness_queue_json": str(nightly_wetlab_json),
            "wetlab_execution_readiness_queue_csv": str(nightly_wetlab_csv),
            "wetlab_execution_readiness_queue_artifact": str(nightly_wetlab_md),
        },
    )

    payload, manifest, _ = _build_bundle_and_read_outputs(tmp_path, fixture["nightly_json"])

    assert payload["included_count"] == 10
    assert payload["missing_count"] == 0
    included_by_name = {row["name"]: row for row in manifest["included_files"]}
    assert included_by_name["wetlab_execution_readiness_queue_json"]["src"] == str(nightly_wetlab_json)
    assert included_by_name["wetlab_execution_readiness_queue_csv"]["src"] == str(nightly_wetlab_csv)
    assert included_by_name["wetlab_execution_readiness_queue_md"]["src"] == str(nightly_wetlab_md)
    assert manifest["wetlab_execution_readiness_status"]["artifact"] == str(nightly_wetlab_md)


def test_build_commercial_delivery_bundle_prefers_explicit_wetlab_paths_over_nightly_and_defaults(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    fixture = _write_base_bundle_fixture(tmp_path)
    _write_wetlab_artifacts(fixture["runs"], "wetlab_execution_readiness_queue_current")
    nightly_wetlab_json, nightly_wetlab_csv, nightly_wetlab_md = _write_wetlab_artifacts(
        fixture["runs"],
        "nightly_wetlab_queue",
    )
    explicit_dir = tmp_path / "explicit"
    explicit_dir.mkdir(parents=True, exist_ok=True)
    explicit_wetlab_json, explicit_wetlab_csv, explicit_wetlab_md = _write_wetlab_artifacts(
        explicit_dir,
        "explicit_wetlab_queue",
    )
    fixture = _write_base_bundle_fixture(
        tmp_path,
        nightly_extra_paths={
            "wetlab_execution_readiness_queue_json": str(nightly_wetlab_json),
            "wetlab_execution_readiness_queue_csv": str(nightly_wetlab_csv),
            "wetlab_execution_readiness_queue_artifact": str(nightly_wetlab_md),
        },
    )

    payload, manifest, _ = _build_bundle_and_read_outputs(
        tmp_path,
        fixture["nightly_json"],
        extra_args=[
            "--wetlab-execution-readiness-queue-json",
            str(explicit_wetlab_json),
            "--wetlab-execution-readiness-queue-csv",
            str(explicit_wetlab_csv),
            "--wetlab-execution-readiness-queue-artifact",
            str(explicit_wetlab_md),
        ],
    )

    assert payload["included_count"] == 10
    assert payload["missing_count"] == 0
    included_by_name = {row["name"]: row for row in manifest["included_files"]}
    assert included_by_name["wetlab_execution_readiness_queue_json"]["src"] == str(explicit_wetlab_json)
    assert included_by_name["wetlab_execution_readiness_queue_csv"]["src"] == str(explicit_wetlab_csv)
    assert included_by_name["wetlab_execution_readiness_queue_md"]["src"] == str(explicit_wetlab_md)
    assert manifest["wetlab_execution_readiness_status"]["artifact"] == str(explicit_wetlab_md)

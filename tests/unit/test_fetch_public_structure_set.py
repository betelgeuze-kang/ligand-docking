from pathlib import Path

import pytest

from tools import fetch_public_structure_set as fetcher


def test_fetch_public_structure_set_dry_run_writes_manifest(tmp_path):
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text(
        "target,pdb_id,uniprot_id\n"
        "Chignolin,1UAO,\n"
        "Ubiquitin_Mini,1UBQ,P0CG47\n",
        encoding="utf-8",
    )
    out_manifest = tmp_path / "manifest.csv"
    out_summary = tmp_path / "summary.json"
    out_dir = tmp_path / "downloads"

    payload = fetcher.fetch_public_structure_set(
        sources_csv=str(sources_csv),
        targets_spec="Chignolin,Ubiquitin_Mini",
        out_dir=str(out_dir),
        out_manifest_csv=str(out_manifest),
        out_summary_json=str(out_summary),
        download_pdb=True,
        download_afdb=True,
        dry_run=True,
    )

    assert out_manifest.exists()
    assert out_summary.exists()
    summary = payload["summary"]
    assert summary["requested_sources"] == 3
    assert summary["rows_emitted"] == 3
    assert summary["dry_run_count"] == 3
    assert summary["failed_count"] == 0


def test_fetch_public_structure_set_strict_raises_on_download_failure(tmp_path, monkeypatch):
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text("target,pdb_id,uniprot_id\nChignolin,1UAO,\n", encoding="utf-8")

    def _boom(url: str, out_path: str, timeout_sec: float):
        raise RuntimeError("forced-download-failure")

    monkeypatch.setattr(fetcher, "_download_binary", _boom)

    with pytest.raises(RuntimeError):
        fetcher.fetch_public_structure_set(
            sources_csv=str(sources_csv),
            targets_spec="Chignolin",
            out_dir=str(tmp_path / "downloads"),
            out_manifest_csv=str(tmp_path / "manifest.csv"),
            out_summary_json=str(tmp_path / "summary.json"),
            download_pdb=True,
            download_afdb=False,
            strict=True,
            dry_run=False,
        )


def test_fetch_public_structure_set_afdb_fallback_versions(tmp_path, monkeypatch):
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text("target,pdb_id,uniprot_id\nUbiquitin_Mini,,P0CG48\n", encoding="utf-8")
    calls = []

    def _fake_download(url: str, out_path: str, timeout_sec: float):
        calls.append(url)
        if "model_v6" in url:
            raise RuntimeError("v6-missing")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("FAKE_PDB", encoding="utf-8")
        return 8, out_path

    monkeypatch.setattr(fetcher, "_download_binary", _fake_download)

    payload = fetcher.fetch_public_structure_set(
        sources_csv=str(sources_csv),
        targets_spec="Ubiquitin_Mini",
        out_dir=str(tmp_path / "downloads"),
        out_manifest_csv=str(tmp_path / "manifest.csv"),
        out_summary_json=str(tmp_path / "summary.json"),
        download_pdb=False,
        download_afdb=True,
        afdb_model_versions="v6,v5",
        strict=False,
        dry_run=False,
    )

    assert payload["summary"]["downloaded_count"] == 1
    assert any("model_v6" in u for u in calls)
    assert any("model_v5" in u for u in calls)
    row = payload["rows"][0]
    assert row["status"] == "downloaded"
    assert row["fallback_attempts"] == 2

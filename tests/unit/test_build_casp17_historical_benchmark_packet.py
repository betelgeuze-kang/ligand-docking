from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _ca(serial: int, chain: str, resseq: int, x: float, y: float, z: float, *, resname: str = "ALA") -> str:
    return (
        f"ATOM  {serial:5d} CA   {resname:>3s} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{70.0 + serial:6.2f}           C  "
    )


def _write_ca_pdb(
    path: Path,
    *,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    chain: str = "A",
    resnames: list[str] | None = None,
    count: int = 6,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox, oy, oz = offset
    lines = ["PFRMAT TS", "TARGET T9999", "AUTHOR REDACTED", "METHOD fixture", "MODEL 1", "PARENT N/A"]
    for index in range(1, count + 1):
        resname = (resnames or ["ALA"] * 6)[index - 1]
        lines.append(_ca(index, chain, index, index * 3.8 + ox, (index % 2) * 0.6 + oy, index * 0.2 + oz, resname=resname))
    lines.extend(["TER", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_complex_ca_pdb(path: Path, *, offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox, oy, oz = offset
    lines = ["PFRMAT TS", "TARGET H9999", "AUTHOR REDACTED", "METHOD fixture", "MODEL 1", "PARENT N/A"]
    serial = 1
    for chain, y in [("A", 0.0), ("B", 6.0)]:
        for index in range(1, 5):
            lines.append(_ca(serial, chain, index, index * 3.8 + ox, y + oy, index * 0.2 + oz))
            serial += 1
        lines.append("TER")
    lines.extend(["END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_build_casp17_historical_benchmark_packet_scores_no_leak_fixture(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_ca_pdb(native)
    _write_ca_pdb(prediction, offset=(12.0, -3.0, 7.0))
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9999",
                "target_id": "T9999",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "3",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["historical_benchmark_status"] == "pass"
    assert payload["summary"]["monomer_win_tier_status"] == "pass"
    assert row["benchmark_status"] == "pass"
    assert row["matched_ca_count"] == 6
    assert row["sequence_exact_match"] is True
    assert row["chain_exact_match"] is True
    assert row["sequence_identity_match_fraction"] == 1.0
    assert row["coordinate_pairing_mode"] == "chain_residue_key_intersection"
    assert row["ca_rmsd_A"] < 1e-6
    assert row["tm_score_proxy"] == 1.0
    assert row["gdt_ts_proxy"] == 1.0
    assert row["ca_lddt_proxy"] == 1.0


def test_build_casp17_historical_benchmark_packet_scores_complex_interface_proxies(tmp_path: Path) -> None:
    native = tmp_path / "native_complex.pdb"
    prediction = tmp_path / "prediction_complex.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_complex_ca_pdb(native)
    _write_complex_ca_pdb(prediction, offset=(8.0, -2.0, 4.0))
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_H9999",
                "target_id": "H9999",
                "scope": "complex",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "6",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["historical_benchmark_status"] == "pass"
    assert payload["summary"]["complex_win_tier_status"] == "pass"
    assert payload["summary"]["mean_complex_dockq_proxy"] == 1.0
    assert payload["summary"]["mean_complex_qsbest_proxy"] == 1.0
    assert row["benchmark_status"] == "pass"
    assert row["native_interface_contact_count"] > 0
    assert row["prediction_interface_contact_count"] == row["native_interface_contact_count"]
    assert row["interface_contact_precision_proxy"] == 1.0
    assert row["interface_contact_recall_proxy"] == 1.0
    assert row["interface_contact_f1_proxy"] == 1.0
    assert row["interface_patch_jaccard_proxy"] == 1.0
    assert row["interface_qsbest_proxy"] == 1.0
    assert row["dockq_proxy"] == 1.0


def test_build_casp17_historical_benchmark_packet_blocks_sequence_mismatch(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_ca_pdb(native, resnames=["ALA", "ALA", "GLY", "ALA", "ALA", "ALA"])
    _write_ca_pdb(prediction)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9999",
                "target_id": "T9999",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "3",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["historical_benchmark_status"] == "blocked"
    assert payload["summary"]["sequence_exact_match_count"] == 0
    assert row["benchmark_status"] == "blocked"
    assert row["sequence_exact_match"] is False
    assert row["sequence_identity_match_fraction"] < 1.0
    assert "prediction_native_residue_identity_mismatch" in row["blockers"]


def test_build_casp17_historical_benchmark_packet_blocks_chain_mismatch(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_ca_pdb(native, chain="B")
    _write_ca_pdb(prediction, chain="A")
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9999",
                "target_id": "T9999",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "3",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["historical_benchmark_status"] == "blocked"
    assert row["coordinate_pairing_mode"] == "order_fallback"
    assert row["chain_exact_match"] is False
    assert "prediction_native_chain_ids_mismatch" in row["blockers"]
    assert "residue_key_overlap_missing" in row["blockers"]


def test_build_casp17_historical_benchmark_packet_blocks_partial_ca_coverage(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_ca_pdb(native, count=6)
    _write_ca_pdb(prediction, count=5)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["benchmark_id", "target_id", "scope", "split", "prediction_pdb", "native_pdb", "leakage_clearance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9999",
                "target_id": "T9999",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
            }
        )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "3",
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["historical_benchmark_status"] == "blocked"
    assert row["prediction_ca_coverage"] == 1.0
    assert row["native_ca_coverage"] < 1.0
    assert "native_ca_coverage_below_threshold" in row["blockers"]


def test_build_casp17_historical_benchmark_packet_blocks_missing_manifest(tmp_path: Path) -> None:
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_benchmark_packet.py"),
            "--manifest-csv",
            str(tmp_path / "missing.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["historical_benchmark_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["manifest_blockers"] == "manifest_missing"

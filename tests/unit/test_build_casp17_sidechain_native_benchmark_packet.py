from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom_name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = atom_name.strip()[0]
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{70.0 + serial:6.2f}           {element:>2}  "
    )


def _write_sidechain_pdb(
    path: Path,
    *,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    sidechains: bool = True,
    residue_count: int = 3,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ox, oy, oz = offset
    atoms = [
        ("CA", "SER", 1, 0.0, 0.0, 0.0),
        ("CB", "SER", 1, 0.0, 1.5, 0.2),
        ("OG", "SER", 1, 0.0, 2.4, 0.6),
        ("CA", "ASP", 2, 3.8, 0.4, 0.3),
        ("CB", "ASP", 2, 3.8, 1.8, 0.5),
        ("CG", "ASP", 2, 3.8, 2.9, 1.0),
        ("OD1", "ASP", 2, 3.2, 3.5, 1.5),
        ("OD2", "ASP", 2, 4.4, 3.5, 0.8),
        ("CA", "LYS", 3, 7.6, -0.2, 0.7),
        ("CB", "LYS", 3, 7.6, 1.1, 1.1),
        ("CG", "LYS", 3, 8.1, 2.3, 1.7),
        ("NZ", "LYS", 3, 8.6, 3.4, 2.4),
    ]
    lines = ["PFRMAT TS", "TARGET T9999", "AUTHOR REDACTED", "METHOD fixture", "MODEL 1", "PARENT N/A"]
    serial = 1
    for atom_name, resname, resseq, x, y, z in atoms:
        if resseq > residue_count:
            continue
        if not sidechains and atom_name != "CA":
            continue
        lines.append(_atom(serial, atom_name, resname, "A", resseq, x + ox, y + oy, z + oz))
        serial += 1
    lines.extend(["TER", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(manifest: Path, prediction: Path, native: Path) -> None:
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


def test_build_casp17_sidechain_native_benchmark_packet_scores_no_leak_fixture(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_sidechain_pdb(native)
    _write_sidechain_pdb(prediction, offset=(9.0, -4.0, 2.5))
    _write_manifest(manifest, prediction, native)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_native_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "3",
            "--min-sidechain-atom-count",
            "4",
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

    assert payload["summary"]["sidechain_native_benchmark_status"] == "pass"
    assert row["sidechain_native_status"] == "pass"
    assert row["matched_ca_count"] == 3
    assert row["matched_sidechain_atom_count"] == 9
    assert row["native_sidechain_atom_coverage"] == 1.0
    assert row["sidechain_rmsd_A"] < 1e-6
    assert row["sidechain_lddt_proxy"] == 1.0
    assert "Sidechain Native Benchmark" in (tmp_path / "packet.md").read_text(encoding="utf-8")


def test_build_casp17_sidechain_native_benchmark_packet_blocks_missing_sidechains(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_sidechain_pdb(native)
    _write_sidechain_pdb(prediction, sidechains=False)
    _write_manifest(manifest, prediction, native)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_native_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "3",
            "--min-sidechain-atom-count",
            "4",
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

    assert payload["summary"]["sidechain_native_benchmark_status"] == "blocked"
    assert row["sidechain_native_status"] == "blocked"
    assert "matched_sidechain_atom_count_below_threshold" in row["blockers"]
    assert "native_sidechain_coverage_below_threshold" in row["blockers"]


def test_build_casp17_sidechain_native_benchmark_packet_blocks_partial_ca_coverage(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    prediction = tmp_path / "prediction.pdb"
    manifest = tmp_path / "manifest.csv"
    _write_sidechain_pdb(native)
    _write_sidechain_pdb(prediction, residue_count=2)
    _write_manifest(manifest, prediction, native)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_native_benchmark_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--min-ca-count",
            "2",
            "--min-sidechain-atom-count",
            "4",
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

    assert payload["summary"]["sidechain_native_benchmark_status"] == "blocked"
    assert row["prediction_ca_coverage"] == 1.0
    assert row["native_ca_coverage"] < 1.0
    assert "native_ca_coverage_below_threshold" in row["blockers"]


def test_build_casp17_sidechain_native_benchmark_packet_blocks_missing_manifest(tmp_path: Path) -> None:
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_native_benchmark_packet.py"),
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
    assert payload["summary"]["sidechain_native_benchmark_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["manifest_blockers"] == "manifest_missing"

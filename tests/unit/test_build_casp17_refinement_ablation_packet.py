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


def _write_ca_pdb(path: Path, coords: list[tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["PFRMAT TS", "TARGET T9999", "AUTHOR REDACTED", "METHOD fixture", "MODEL 1", "PARENT N/A"]
    for index, (x, y, z) in enumerate(coords, start=1):
        lines.append(_ca(index, "A", index, x, y, z))
    lines.extend(["TER", "END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _native_coords(count: int = 8) -> list[tuple[float, float, float]]:
    return [(index * 3.8, (index % 2) * 0.6, index * 0.2) for index in range(1, count + 1)]


def _distorted_coords(count: int = 8) -> list[tuple[float, float, float]]:
    return [(index * 3.8, (index % 2) * 2.8, index * 0.2 + (index % 3) * 1.4) for index in range(1, count + 1)]


def _translated_coords(coords: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    return [(x + 11.0, y - 7.0, z + 3.0) for x, y, z in coords]


def _write_manifest(path: Path, *, native: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["benchmark_id", "target_id", "scope", "split", "native_pdb", "leakage_clearance"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_id": "hist_T9999",
                "target_id": "T9999",
                "scope": "monomer",
                "split": "historical",
                "native_pdb": str(native),
                "leakage_clearance": "no_leak",
            }
        )


def test_build_casp17_refinement_ablation_packet_passes_when_final_improves_no_leak_fixture(tmp_path: Path) -> None:
    native = tmp_path / "native/T9999.pdb"
    recursive_dir = tmp_path / "layers/recursive"
    final_dir = tmp_path / "layers/statistical_rotamer"
    manifest = tmp_path / "manifest.csv"
    coords = _native_coords()
    _write_ca_pdb(native, coords)
    _write_ca_pdb(recursive_dir / "T9999TS.pdb", _distorted_coords())
    _write_ca_pdb(final_dir / "T9999TS.pdb", _translated_coords(coords))
    _write_manifest(manifest, native=native)

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_refinement_ablation_packet.py"),
            "--manifest-csv",
            str(manifest),
            "--layer",
            f"recursive={recursive_dir}",
            "--layer",
            f"statistical_rotamer={final_dir}",
            "--baseline-layer",
            "recursive",
            "--final-layer",
            "statistical_rotamer",
            "--min-ca-count",
            "3",
            "--min-improved-fraction",
            "1.0",
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
    summary = payload["summary"]
    group = payload["group_rows"][0]

    assert summary["refinement_ablation_status"] == "pass"
    assert summary["benchmark_count"] == 1
    assert summary["layer_row_count"] == 2
    assert summary["usable_layer_count"] == 2
    assert summary["final_not_worse_count"] == 1
    assert summary["final_improved_count"] == 1
    assert group["ablation_group_status"] == "pass"
    assert group["delta_tm_score_proxy"] > 0
    assert group["delta_gdt_ts_proxy"] > 0
    assert group["delta_ca_lddt_proxy"] >= 0
    assert group["rmsd_improvement_A"] > 0
    assert "statistical_rotamer" in (tmp_path / "packet.md").read_text(encoding="utf-8")


def test_build_casp17_refinement_ablation_packet_fails_closed_without_manifest(tmp_path: Path) -> None:
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_refinement_ablation_packet.py"),
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

    assert payload["summary"]["refinement_ablation_status"] == "blocked"
    assert payload["summary"]["manifest_blockers"] == "manifest_missing"
    assert payload["summary"]["layer_row_count"] == 0
    assert payload["rows"] == []

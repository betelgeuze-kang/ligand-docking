from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tools.build_bm5_complex_proxy_results import build_results


def _atom(serial: int, atom: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4} GLY {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 10.00           C\n"
    )


def _pdb(chain: str, offset: float = 0.0) -> str:
    return "".join(
        [
            _atom(1, "CA", chain, 1, 0.0 + offset, 0.0, 0.0),
            _atom(2, "CA", chain, 2, 1.0 + offset, 0.0, 0.0),
            _atom(3, "CA", chain, 3, 0.0 + offset, 1.0, 0.0),
        ]
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_bm5_complex_proxy_results_passes_aligned_triplet(tmp_path: Path) -> None:
    case = tmp_path / "bm5" / "HADDOCK-ready" / "1ABC"
    case.mkdir(parents=True)
    (case / "1ABC_r_u.pdb").write_text(_pdb("A"), encoding="utf-8")
    (case / "1ABC_l_u.pdb").write_text(_pdb("B", offset=5.0), encoding="utf-8")
    (case / "1ABC_target.pdb").write_text(_pdb("A") + _pdb("B", offset=5.0), encoding="utf-8")
    out_csv = tmp_path / "results.csv"

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "bm5"),
            max_complexes=0,
            threshold=0.2,
            acceptable_ligand_rmsd_a=10.0,
            receptor_chain="A",
            ligand_chain="B",
            out_csv=str(out_csv),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
        )
    )

    assert payload["summary"]["status"] == "bm5_complex_proxy_results_ready"
    assert payload["summary"]["dockq_acceptable_rate"] == 1.0
    assert _rows(out_csv)[0]["complex_id"] == "1ABC"


def test_build_bm5_complex_proxy_results_blocks_missing_triplets(tmp_path: Path) -> None:
    (tmp_path / "bm5" / "HADDOCK-ready").mkdir(parents=True)

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "bm5"),
            max_complexes=0,
            threshold=0.2,
            acceptable_ligand_rmsd_a=10.0,
            receptor_chain="A",
            ligand_chain="B",
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
        )
    )

    assert payload["summary"]["status"] == "blocked_bm5_complex_proxy_results"
    assert "complex_triplets_missing" in payload["summary"]["blockers"]

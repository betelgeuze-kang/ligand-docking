from pathlib import Path

import torch

from tools import pdb_loader


def _write_pdb(path: Path) -> None:
    lines = []
    atom_id = 1
    for chain, count in {"A": 2, "B": 3}.items():
        for idx in range(1, count + 1):
            lines.append(
                f"ATOM  {atom_id:5d}  CA  GLY {chain}{idx:4d}    "
                f"{idx:8.3f}{float(ord(chain)):8.3f}{0.0:8.3f}  1.00 20.00           C"
            )
            atom_id += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_native_structure_uses_research_constants_native_path_and_chain(tmp_path, monkeypatch):
    pdb_path = tmp_path / "native.pdb"
    _write_pdb(pdb_path)
    monkeypatch.setitem(
        pdb_loader.ResearchConstants.CHALLENGES,
        "Custom Target",
        {
            "n_res": 3,
            "type": "protein",
            "box": [100.0, 100.0, 100.0],
            "native_pdb_path": str(pdb_path),
            "canonical_chain": "B",
        },
    )

    coords, seq = pdb_loader.load_native_structure("Custom Target")

    assert isinstance(coords, torch.Tensor)
    assert coords.shape == (3, 3)
    assert seq == ""
    assert torch.all(coords[:, 1] == float(ord("B")))

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from tools.wetlab import build_tcruzi_pde_strict_external_manifest as mod


def _write_pdb(path: Path) -> None:
    lines = []
    atom_id = 1
    for chain, count in {"A": 2, "B": 3}.items():
        for idx in range(1, count + 1):
            lines.append(
                f"ATOM  {atom_id:5d}  CA  GLY {chain}{idx:4d}    "
                f"{idx:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C"
            )
            atom_id += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_registration(path: Path, *, chain: str = "B", ca_count: int = 3) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {"registration_ready": True},
                "strict_release_registry": {
                    "canonical_chain": chain,
                    "selected_chain_ca_count": ca_count,
                },
            }
        ),
        encoding="utf-8",
    )


def _args(tmp_path: Path):
    return mod.build_parser().parse_args(
        [
            "--native-pdb",
            str(tmp_path / "native.pdb"),
            "--registration-json",
            str(tmp_path / "registration.json"),
            "--out-dir",
            str(tmp_path / "out"),
            "--out-manifest",
            str(tmp_path / "manifest.csv"),
            "--out-json",
            str(tmp_path / "summary.json"),
            "--steps",
            "2",
            "--save-stride",
            "1",
        ]
    )


def test_builds_manifest_from_registered_canonical_chain(tmp_path, monkeypatch):
    _write_pdb(tmp_path / "native.pdb")
    _write_registration(tmp_path / "registration.json")

    def fake_simulate(**kwargs):
        chain_pdb = Path(kwargs["pdb_path"])
        chain_text = chain_pdb.read_text(encoding="utf-8")
        assert " GLY B" in chain_text
        assert " GLY A" not in chain_text
        assert chain_text.count(" CA ") == 3
        out_npy = Path(kwargs["out_npy"])
        np.save(out_npy, np.zeros((2, 3, 3), dtype=np.float32))
        return {
            "target": kwargs["target"],
            "path": str(out_npy),
            "engine": "openmm",
            "label": "T. cruzi PDE_openmm_ca_md",
            "frame": -1,
            "key": "",
            "source_engine": "openmm",
            "source_path": str(out_npy),
            "source_label": "T. cruzi PDE_openmm_ca_md",
            "notes": "REAL_MD_OPENMM_CA_BEAD",
            "representation": "ca",
            "bead_order": "ca_only",
            "n_res": 3,
            "n_atoms": 3,
            "beads_per_residue": 1.0,
            "temperature_k": 300.0,
            "friction_ps": 1.0,
            "dt_ps": 0.004,
            "steps": 2,
            "save_stride": 1,
            "platform": "Reference",
            "seed": 1234,
        }

    monkeypatch.setattr(mod, "_simulate_target", fake_simulate)

    payload = mod.run_build(_args(tmp_path))

    assert payload["summary"]["manifest_ready"] is True
    assert payload["summary"]["canonical_chain"] == "B"
    assert payload["summary"]["expected_ca_count"] == 3
    rows = list(csv.DictReader((tmp_path / "manifest.csv").open()))
    assert rows[0]["target"] == "T. cruzi PDE"
    assert rows[0]["engine"] == "openmm"
    assert rows[0]["representation"] == "ca"
    assert rows[0]["canonical_chain"] == "B"
    assert rows[0]["n_res"] == "3"


def test_blocks_when_registered_ca_count_does_not_match_chain(tmp_path, monkeypatch):
    _write_pdb(tmp_path / "native.pdb")
    _write_registration(tmp_path / "registration.json", ca_count=4)
    monkeypatch.setattr(mod, "_simulate_target", lambda **_: pytest.fail("should not simulate"))

    with pytest.raises(ValueError, match="canonical_chain_ca_count_mismatch"):
        mod.run_build(_args(tmp_path))

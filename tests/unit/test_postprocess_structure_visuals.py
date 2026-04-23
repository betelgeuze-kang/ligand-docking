from pathlib import Path

import numpy as np

from tools import postprocess_structure_visuals as pp


def _write_simple_pdb(path: Path, coords: np.ndarray, target: str, step: int) -> None:
    lines = [
        "REMARK GENERATED_FOR_TEST",
        f"REMARK TARGET {target}",
        "REMARK SAMPLE_IDX 0",
        f"REMARK STEP {step}",
    ]
    for i, xyz in enumerate(coords, start=1):
        x, y, z = [float(v) for v in xyz]
        lines.append(
            f"ATOM  {i:5d}  CA  GLY A{i:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}"
            "  1.00  0.00           C"
        )
    for i in range(1, len(coords)):
        lines.append(f"CONECT{i:5d}{(i + 1):5d}")
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_postprocess_structure_visuals_generates_refined_pdb(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    c0 = np.array([[i * 3.8, 0.0, 0.0] for i in range(1, 9)], dtype=np.float32)
    c1 = c0.copy()
    c1[:, 1] = np.linspace(-1.2, 1.8, c1.shape[0], dtype=np.float32)
    c1[:, 2] = np.sin(np.linspace(0.0, 2.0, c1.shape[0], dtype=np.float32))

    p0 = in_dir / "internal_post_toy_sample000_step00010.pdb"
    p1 = in_dir / "internal_post_toy_sample000_step00020.pdb"
    _write_simple_pdb(p0, c0, target="Toy", step=10)
    _write_simple_pdb(p1, c1, target="Toy", step=20)

    args = pp.build_parser().parse_args(
        [
            "--in-glob",
            str(in_dir / "*.pdb"),
            "--out-dir",
            str(out_dir),
            "--out-csv",
            str(tmp_path / "refined.csv"),
            "--out-json",
            str(tmp_path / "refined.json"),
            "--smooth-window",
            "3",
            "--align",
        ]
    )
    summary = pp.run(args)
    assert summary["ok"] is True
    assert int(summary["processed_frames"]) == 2

    out_pdbs = sorted(out_dir.glob("*.pdb"))
    assert len(out_pdbs) == 2
    txt = out_pdbs[0].read_text(encoding="utf-8")
    assert "REMARK SOURCE internal_visual_refined" in txt
    assert "REMARK FLEXIBILITY_METHOD" in txt
    assert "REMARK VISUAL_MODEL pseudo_backbone_v1" in txt
    bvals = []
    atom_names = []
    for ln in txt.splitlines():
        if ln.startswith("ATOM"):
            bvals.append(float(ln[60:66]))
            atom_names.append(ln[12:16].strip())
    assert len(bvals) == 32
    assert atom_names.count("N") == 8
    assert atom_names.count("CA") == 8
    assert atom_names.count("C") == 8
    assert atom_names.count("O") == 8
    assert max(bvals) >= min(bvals)


def test_secondary_structure_dssp_path_prefers_pydssp(monkeypatch):
    atoms = []
    coords = []
    serial = 1
    for i in range(10):
        x = float(i) * 3.8
        for atom_name, elem, off in [
            ("N", "N", (-1.20, 0.25, 0.00)),
            ("CA", "C", (0.00, 0.00, 0.00)),
            ("C", "C", (1.25, -0.15, 0.00)),
            ("O", "O", (1.65, 0.80, 0.00)),
        ]:
            atoms.append(
                pp.AtomRecord(
                    record_name="ATOM",
                    serial=serial,
                    atom_name=atom_name,
                    alt_loc="",
                    res_name="GLY",
                    chain_id="A",
                    res_seq=i + 1,
                    i_code="",
                    occupancy=1.0,
                    element=elem,
                    charge="",
                )
            )
            coords.append(np.asarray([x + off[0], off[1], off[2]], dtype=np.float32))
            serial += 1
    xyz = np.stack(coords, axis=0).astype(np.float32, copy=False)

    class _DummyDSSP:
        @staticmethod
        def assign(coord, donor_mask=None, out_type="c3"):
            assert out_type == "c3"
            n = int(coord.shape[0])
            out = np.asarray(["-"] * n, dtype=object)
            out[1:7] = "H"
            out[7:10] = "E"
            return out

    monkeypatch.setattr(pp, "_pydssp", _DummyDSSP, raising=False)
    labels, helices, sheets, method = pp._assign_secondary_structure_for_render(
        atoms,
        xyz,
        mode="dssp",
    )
    assert method == "dssp_pydssp_v1"
    assert len(labels) == 10
    assert helices == [(2, 7)]
    assert sheets == [(8, 10)]


def test_temporal_vote_secondary_labels_majority():
    labels_stack = [
        list("CCCHHHHCCCC"),
        list("CCCHHHHCCCC"),
        list("CCCEEEECCCC"),
        list("CCCHHHHCCCC"),
    ]
    voted = pp._temporal_vote_secondary_labels(labels_stack, min_fraction=0.60)
    assert voted is not None
    labels, helices, sheets = voted
    assert len(labels) == 11
    assert helices == [(4, 7)]
    assert sheets == []

import csv
import json
from pathlib import Path

from tools import build_strict_release_target_registration_packet as mod


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_pdb(
    path: Path,
    *,
    chains: dict[str, int],
    seqres_lengths: dict[str, int] | None = None,
    dbref_ranges: dict[str, tuple[int, int]] | None = None,
    missing_counts: dict[str, int] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atom_id = 1
    lines: list[str] = []
    if dbref_ranges:
        for chain, (start, end) in dbref_ranges.items():
            lines.append(f"DBREF  TEST {chain} {start:4d} {end:5d}  UNP    TEST_{chain}")
    if missing_counts:
        lines.append("REMARK 465   M RES C SSSEQI")
        for chain, count in missing_counts.items():
            for idx in range(1, count + 1):
                lines.append(f"REMARK 465     GLY {chain}  {idx:4d}")
    if seqres_lengths:
        for chain, length in seqres_lengths.items():
            lines.append(f"SEQRES   1 {chain} {length:4d}  GLY")
    for chain, count in chains.items():
        for idx in range(1, count + 1):
            lines.append(
                f"ATOM  {atom_id:5d}  CA  GLY {chain}{idx:4d}    "
                f"{idx:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C"
            )
            atom_id += 1
        lines.append(
            f"HETATM{atom_id:5d}  O   HOH {chain}{900 + atom_id:4d}    "
            f"{0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           O"
        )
        atom_id += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _args(tmp_path: Path, *extra: str):
    return mod.build_parser().parse_args(
        [
            "--target",
            "T. cruzi PDE",
            "--native-csv",
            str(tmp_path / "native.csv"),
            "--profile-json",
            str(tmp_path / "profile.json"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-md",
            str(tmp_path / "packet.md"),
            *extra,
        ]
    )


def test_tcruzi_native_ready_but_canonical_chain_selection_still_fail_closes(tmp_path):
    pdb = tmp_path / "tcruzi.pdb"
    _write_pdb(
        pdb,
        chains={"A": 332, "B": 334, "F": 334, "G": 334},
        seqres_lengths={"A": 345, "B": 345, "F": 345, "G": 345},
        dbref_ranges={"A": (270, 614), "B": (270, 614), "F": (270, 614), "G": (270, 614)},
        missing_counts={"A": 13, "B": 11, "F": 11, "G": 11},
    )
    _write_csv(
        tmp_path / "native.csv",
        [
            {
                "target": "T. cruzi PDE",
                "native_pdb_path": str(pdb),
                "pdb_id": "3V94",
                "target_aliases": "t_cruzi_pde;TcrPDEC1",
                "notes": "native ready",
            }
        ],
    )
    (tmp_path / "profile.json").write_text(
        json.dumps({"targets": {"T. cruzi PDE": {"dt": 1e-6}}}),
        encoding="utf-8",
    )

    payload = mod.run_build(_args(tmp_path))

    summary = payload["summary"]
    assert summary["registration_ready"] is False
    assert summary["native_registry_ready"] is True
    assert summary["native_pdb_ready"] is True
    assert "canonical_chain_not_selected" in summary["blockers"]
    assert "research_constants_target_missing" not in summary["blockers"]
    assert "long_stability_profile_target_missing" not in summary["blockers"]
    assert summary["research_constants_ready"] is True
    assert summary["profile_ready"] is True
    assert payload["native_pdb"]["chain_count"] == 4
    assert payload["native_pdb"]["ca_count"] == 1334
    assert payload["native_pdb"]["hetero_residue_count"] == 4
    assert payload["native_pdb"]["chains"][0]["residue_count"] == 332
    assert payload["native_pdb"]["chains"][0]["hetero_residue_count"] == 1
    assert payload["summary"]["canonical_chain_recommendation_ready"] is True
    assert payload["strict_release_registry"]["recommended_canonical_chain"] == "B"
    assert payload["strict_release_registry"]["recommended_seqres_n_res"] == 345
    assert payload["strict_release_registry"]["recommended_observed_ca_count"] == 334
    assert payload["strict_release_registry"]["recommended_missing_residue_count"] == 11
    assert payload["strict_release_registry"]["canonical_chain_recommendation_reason"] == (
        "max_observed_ca_count_with_seqres_345_and_missing_residue_count_11"
    )
    assert Path(payload["native_registry"]["native_pdb_path"]) == pdb
    assert (tmp_path / "packet.json").exists()
    assert (tmp_path / "packet.md").exists()


def test_explicit_tcruzi_canonical_chain_is_registration_ready(tmp_path):
    pdb = tmp_path / "tcruzi.pdb"
    _write_pdb(
        pdb,
        chains={"A": 332, "B": 334},
        seqres_lengths={"A": 345, "B": 345},
        missing_counts={"A": 13, "B": 11},
    )
    _write_csv(
        tmp_path / "native.csv",
        [
            {
                "target": "T. cruzi PDE",
                "native_pdb_path": str(pdb),
                "pdb_id": "3V94",
                "target_aliases": "t_cruzi_pde;TcrPDEC1",
                "notes": "native ready",
            }
        ],
    )
    (tmp_path / "profile.json").write_text(
        json.dumps({"targets": {"T. cruzi PDE": {"dt": 1e-6}}}),
        encoding="utf-8",
    )

    payload = mod.run_build(_args(tmp_path, "--canonical-chain", "B"))

    summary = payload["summary"]
    assert summary["registration_ready"] is True
    assert summary["canonical_chain_ready"] is True
    assert summary["research_constants_ready"] is True
    assert summary["profile_ready"] is True
    assert summary["n_res_match"] is True
    assert summary["blockers"] == []
    assert "canonical_chain_not_selected" not in summary["blockers"]
    assert summary["next_required_step"] == "Target registration is ready for strict-release use."
    assert payload["strict_release_registry"]["research_constants_target"] == "T. cruzi PDE"
    assert payload["strict_release_registry"]["research_constants_n_res"] == 334
    assert payload["strict_release_registry"]["profile_target"] == "T. cruzi PDE"
    assert payload["strict_release_registry"]["selected_chain_seqres_count"] == 345
    assert payload["strict_release_registry"]["selected_chain_missing_residue_count"] == 11


def test_registered_supported_target_with_matching_profile_and_chain_is_ready(tmp_path, monkeypatch):
    pdb = tmp_path / "custom.pdb"
    _write_pdb(pdb, chains={"A": 4})
    _write_csv(
        tmp_path / "native.csv",
        [
            {
                "target": "Custom_Target",
                "native_pdb_path": str(pdb),
                "pdb_id": "CUST",
                "target_aliases": "",
                "notes": "custom ready",
            }
        ],
    )
    (tmp_path / "profile.json").write_text(
        json.dumps({"targets": {"Custom_Target": {"dt": 1e-6, "restraint_k": 1.0}}}),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        mod.ResearchConstants.CHALLENGES,
        "Custom_Target",
        {"n_res": 4, "type": "protein", "box": [100.0, 100.0, 100.0]},
    )

    payload = mod.run_build(
        mod.build_parser().parse_args(
            [
                "--target",
                "Custom_Target",
                "--native-csv",
                str(tmp_path / "native.csv"),
                "--profile-json",
                str(tmp_path / "profile.json"),
                "--canonical-chain",
                "A",
                "--out-json",
                str(tmp_path / "packet.json"),
                "--out-md",
                str(tmp_path / "packet.md"),
            ]
        )
    )

    summary = payload["summary"]
    assert summary["registration_ready"] is True
    assert summary["blockers"] == []
    assert summary["research_constants_ready"] is True
    assert summary["profile_ready"] is True
    assert summary["canonical_chain_ready"] is True
    assert summary["n_res_match"] is True
    assert payload["strict_release_registry"]["research_constants_n_res"] == 4


def test_registered_target_with_chain_n_res_mismatch_is_blocked(tmp_path, monkeypatch):
    pdb = tmp_path / "custom.pdb"
    _write_pdb(pdb, chains={"A": 5})
    _write_csv(
        tmp_path / "native.csv",
        [
            {
                "target": "Custom_Target",
                "native_pdb_path": str(pdb),
                "pdb_id": "CUST",
                "target_aliases": "",
                "notes": "custom ready",
            }
        ],
    )
    (tmp_path / "profile.json").write_text(
        json.dumps({"targets": {"Custom_Target": {"dt": 1e-6}}}),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        mod.ResearchConstants.CHALLENGES,
        "Custom_Target",
        {"n_res": 4, "type": "protein", "box": [100.0, 100.0, 100.0]},
    )

    payload = mod.run_build(
        mod.build_parser().parse_args(
            [
                "--target",
                "Custom_Target",
                "--native-csv",
                str(tmp_path / "native.csv"),
                "--profile-json",
                str(tmp_path / "profile.json"),
                "--canonical-chain",
                "A",
                "--out-json",
                str(tmp_path / "packet.json"),
                "--out-md",
                str(tmp_path / "packet.md"),
            ]
        )
    )

    assert payload["summary"]["registration_ready"] is False
    assert "research_constants_n_res_mismatch" in payload["summary"]["blockers"]
    assert payload["strict_release_registry"]["n_res_reason"] == (
        "n_res_mismatch:challenge=4,canonical_chain_ca=5"
    )

from __future__ import annotations

import argparse
import csv
import pickle
from pathlib import Path
from typing import Any

import pytest

from tools.build_pdbbind_casf_pose_affinity_results import build_results


def _rdkit() -> tuple[Any, Any]:
    chem = pytest.importorskip("rdkit.Chem")
    geometry = pytest.importorskip("rdkit.Geometry")
    return chem, geometry.Point3D


def _mol(offset: float = 0.0) -> Any:
    Chem, Point3D = _rdkit()
    mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    conformer = Chem.Conformer(mol.GetNumAtoms())
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        conformer.SetAtomPosition(idx, Point3D(float(idx) + offset, 0.0, 0.0))
    mol.AddConformer(conformer)
    return mol


def _ethane_with_heavy_positions(positions: list[tuple[float, float, float]]) -> Any:
    Chem, Point3D = _rdkit()
    mol = Chem.AddHs(Chem.MolFromSmiles("CC"))
    conformer = Chem.Conformer(mol.GetNumAtoms())
    heavy_idx = 0
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        if atom.GetAtomicNum() == 1:
            conformer.SetAtomPosition(idx, Point3D(float(idx), 2.0, 0.0))
            continue
        x, y, z = positions[heavy_idx]
        conformer.SetAtomPosition(idx, Point3D(x, y, z))
        heavy_idx += 1
    mol.AddConformer(conformer)
    return mol


def _dump(path: Path, mol: Any) -> None:
    Chem, _Point3D = _rdkit()
    path.write_bytes(pickle.dumps((mol, Chem.MolFromSmiles("CC"))))


class _FakePoint:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


class _FakeConformer:
    def __init__(self, points: list[_FakePoint]) -> None:
        self._points = points

    def GetAtomPosition(self, idx: int) -> _FakePoint:
        return self._points[idx]


class _FakeAtom:
    def __init__(self, idx: int, atomic_num: int, symbol: str) -> None:
        self._idx = idx
        self._atomic_num = atomic_num
        self._symbol = symbol

    def GetIdx(self) -> int:
        return self._idx

    def GetAtomicNum(self) -> int:
        return self._atomic_num

    def GetSymbol(self) -> str:
        return self._symbol


class _FakeMol:
    def __init__(self, offset: float = 0.0) -> None:
        self._atoms = [_FakeAtom(0, 6, "C"), _FakeAtom(1, 6, "C"), _FakeAtom(2, 8, "O")]
        self._conformer = _FakeConformer(
            [
                _FakePoint(0.0 + offset, 0.0, 0.0),
                _FakePoint(1.0 + offset, 0.0, 0.0),
                _FakePoint(2.0 + offset, 0.0, 0.0),
            ]
        )

    def GetAtoms(self) -> list[_FakeAtom]:
        return self._atoms

    def GetConformer(self) -> _FakeConformer:
        return self._conformer


def _dump_fake(path: Path, mol: _FakeMol) -> None:
    path.write_bytes(pickle.dumps((mol, mol)))


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _metadata(path: Path, rows: list[dict[str, object]]) -> Path:
    fields = [
        "pose_id",
        "complex_id",
        "active_label",
        "affinity_label",
        "score",
        "baseline_score",
        "split_id",
        "abstained",
        "abstention_reasons",
        "chirality_failure",
        "tautomer_failure",
        "protonation_failure",
        "runtime_ms",
        "peak_memory_mb",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return path


def test_build_pdbbind_casf_pose_affinity_results_scores_pose_success(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump_fake(data / "1abc", _FakeMol())
    _dump_fake(data / "1abc_1", _FakeMol(offset=0.5))
    _dump(data / "1abc_2", _mol(offset=5.0))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "split_id": "heldout",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "10",
                "peak_memory_mb": "100",
            },
            {
                "pose_id": "1abc_2",
                "complex_id": "1abc",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "split_id": "heldout",
                "abstained": "1",
                "abstention_reasons": "decoy_rejected",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "12",
                "peak_memory_mb": "120",
            },
        ],
    )
    out_csv = tmp_path / "results.csv"

    args = argparse.Namespace(
        dataset_artifact=str(tmp_path / "casf"),
        max_poses=0,
        threshold=0.35,
        pose_success_rmsd_a=2.0,
        out_csv=str(out_csv),
        out_json=str(tmp_path / "results.json"),
        out_md=str(tmp_path / "results.md"),
        gold_metadata_csv=str(metadata),
    )
    payload = build_results(args)

    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["pose_success_rate"] == 1.0
    assert payload["summary"]["pose_row_success_rate"] == 0.5
    assert payload["summary"]["complex_pose_success_rate"] == 1.0
    assert payload["summary"]["top1_mean_rmsd_A"] == 0.5
    assert payload["summary"]["top5_best_mean_rmsd_A"] == 0.5
    assert payload["summary"]["top1_pose_success_rate"] == 1.0
    assert payload["summary"]["top5_pose_success_rate"] == 1.0
    assert payload["summary"]["ranking_spearman"] == pytest.approx(1.0)
    assert payload["summary"]["baseline_ranking_spearman"] == pytest.approx(-1.0)
    assert payload["summary"]["refine_ranking_spearman_delta"] == pytest.approx(2.0)
    assert payload["summary"]["decoy_rejection_rate"] == 1.0
    assert payload["summary"]["abstention_precision"] == 1.0
    assert payload["summary"]["chemistry_evidence_coverage"] == 1.0
    assert payload["summary"]["mean_runtime_ms"] > 0.0
    assert payload["summary"]["peak_memory_mb"] > 0.0
    assert payload["summary"]["subset_identity_schema_version"] == "pdbbind_casf_subset_identity_v1"
    assert payload["summary"]["subset_pose_file_names"] == ["1abc_1", "1abc_2"]
    assert payload["summary"]["subset_reference_file_names"] == ["1abc"]
    assert payload["summary"]["subset_gold_metadata_sha256"]
    assert payload["summary"]["subset_identity_sha256"]
    repeat_payload = build_results(args)
    assert repeat_payload["summary"]["subset_identity_sha256"] == payload["summary"]["subset_identity_sha256"]
    limited_args = argparse.Namespace(**{**vars(args), "max_poses": 1})
    limited_payload = build_results(limited_args)
    assert limited_payload["summary"]["subset_pose_file_names"] == ["1abc_1"]
    assert limited_payload["summary"]["subset_identity_sha256"] != payload["summary"]["subset_identity_sha256"]
    allowlist = tmp_path / "allowlist.csv"
    allowlist.write_text("pose_id\n1abc_2\n", encoding="utf-8")
    allowlisted_args = argparse.Namespace(**{**vars(args), "pose_id_allowlist_csv": str(allowlist)})
    allowlisted_payload = build_results(allowlisted_args)
    assert allowlisted_payload["summary"]["pose_count"] == 1
    assert allowlisted_payload["summary"]["pose_id_allowlist_count"] == 1
    assert allowlisted_payload["summary"]["subset_pose_file_names"] == ["1abc_2"]
    first_row = _rows(out_csv)[0]
    assert first_row["complex_id"] == "1abc"
    assert first_row["pose_rmsd_method"] == "rdkit_self_substructure_automorphism_no_ligand_alignment"
    assert first_row["runtime_metric_source"] == "builder_wall_clock_perf_counter"
    assert first_row["peak_memory_metric_source"] == "builder_tracemalloc_peak"


def test_build_pdbbind_casf_pose_affinity_results_uses_best_pose_per_complex(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=5.0))
    _dump(data / "1abc_2", _mol(offset=0.5))
    _dump(data / "1abc_3", _mol(offset=6.0))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "10",
                "peak_memory_mb": "100",
            },
            {
                "pose_id": "1abc_2",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "8.0",
                "score": "-8.0",
                "baseline_score": "-2.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "11",
                "peak_memory_mb": "101",
            },
            {
                "pose_id": "1abc_3",
                "complex_id": "1abc",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "abstained": "1",
                "abstention_reasons": "decoy_rejected",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "12",
                "peak_memory_mb": "102",
            },
        ],
    )

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["pose_row_success_rate"] == 1 / 3
    assert payload["summary"]["complex_pose_success_rate"] == 1.0
    assert payload["summary"]["top1_mean_rmsd_A"] == 5.0
    assert payload["summary"]["top5_best_mean_rmsd_A"] == 0.5
    assert payload["summary"]["top1_pose_success_rate"] == 0.0
    assert payload["summary"]["top5_pose_success_rate"] == 1.0


def test_build_pdbbind_casf_pose_affinity_results_uses_symmetry_aware_rmsd(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _ethane_with_heavy_positions([(0.0, 0.0, 0.0), (1.5, 0.0, 0.0)]))
    _dump(data / "1abc_1", _ethane_with_heavy_positions([(1.5, 0.0, 0.0), (0.0, 0.0, 0.0)]))
    _dump(data / "1abc_2", _ethane_with_heavy_positions([(5.0, 0.0, 0.0), (6.5, 0.0, 0.0)]))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
            {
                "pose_id": "1abc_2",
                "complex_id": "1abc",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "abstained": "1",
                "abstention_reasons": "symmetry_decoy",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
        ],
    )
    out_csv = tmp_path / "results.csv"

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(out_csv),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    first_row = _rows(out_csv)[0]
    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["top1_mean_rmsd_A"] == pytest.approx(0.0)
    assert float(first_row["pose_rmsd_A"]) == pytest.approx(0.0)
    assert first_row["pose_rmsd_method"] == "rdkit_self_substructure_automorphism_no_ligand_alignment"
    assert '"symmetry_mapping_count": 2' in first_row["pose_rmsd_diagnostics"]


def test_build_pdbbind_casf_pose_affinity_results_blocks_without_abstention_evidence(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    _dump(data / "1abc_2", _mol(offset=5.0))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
            {
                "pose_id": "1abc_2",
                "complex_id": "1abc",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
        ],
    )

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "gold_metrics_blocked" in payload["summary"]["blockers"]
    assert "abstention_precision_not_computable" in payload["summary"]["gold_metric_blockers"]


def test_build_pdbbind_casf_pose_affinity_results_blocks_without_poses(tmp_path: Path) -> None:
    (tmp_path / "casf" / "data_5_sdf").mkdir(parents=True)

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv="",
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "pose_files_missing" in payload["summary"]["blockers"]


def test_build_pdbbind_casf_pose_affinity_results_blocks_without_gold_metadata(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv="",
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "gold_metrics_blocked" in payload["summary"]["blockers"]
    assert "affinity_labels_missing" in payload["summary"]["gold_metric_blockers"]


def test_build_pdbbind_casf_pose_affinity_results_blocks_partial_references(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    _dump(data / "2def_1", _mol(offset=0.5))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "10",
                "peak_memory_mb": "100",
            },
            {
                "pose_id": "2def_1",
                "complex_id": "2def",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "abstained": "1",
                "abstention_reasons": "missing_reference_decoy",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
                "runtime_ms": "11",
                "peak_memory_mb": "101",
            },
        ],
    )

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "row_level_benchmark_blockers_present" in payload["summary"]["blockers"]
    assert "gold_metrics_blocked" in payload["summary"]["blockers"]


def test_build_pdbbind_casf_pose_affinity_results_replay_mode_keeps_prediction_generation_disabled(
    tmp_path: Path,
) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
        ],
    )

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["prediction_generation_enabled"] is False
    assert payload["summary"]["generated_pose_smoke_row_count"] == 0
    assert payload["summary"]["replay_pose_count"] == 1
    assert all(row["row_source"] == "replay" for row in _rows(tmp_path / "results.csv"))


def test_build_pdbbind_casf_pose_affinity_results_generate_poses_smoke_mode(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    _dump(data / "2def", _mol())
    _dump(data / "2def_1", _mol(offset=0.5))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
            {
                "pose_id": "2def_1",
                "complex_id": "2def",
                "active_label": "1",
                "affinity_label": "8.0",
                "score": "-8.0",
                "baseline_score": "-2.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
        ],
    )
    out_csv = tmp_path / "results.csv"

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(out_csv),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
            generate_poses=True,
            generate_poses_seed=42,
            generate_poses_count=1,
            generate_poses_max_complexes=2,
        )
    )

    csv_rows = _rows(out_csv)
    replay_rows = [row for row in csv_rows if row["row_source"] == "replay"]
    generated_rows = [row for row in csv_rows if row["row_source"] == "generated_pose_smoke"]

    assert payload["summary"]["prediction_generation_enabled"] is True
    assert payload["summary"]["generated_pose_smoke_enabled"] is True
    assert payload["summary"]["generated_pose_generation_seed"] == 42
    assert payload["summary"]["generated_pose_smoke_row_count"] == 2
    assert payload["summary"]["replay_pose_count"] == 2
    assert len(replay_rows) == 2
    assert len(generated_rows) == 2
    assert "restricted local generated-pose smoke" in payload["summary"]["claim_boundary"].lower()
    assert "claim official casf/pdbbind parity" in payload["summary"]["claim_boundary"].lower()
    assert generated_rows[0]["pose_generation_source"] == "rdkit_etkdgv3_local"
    assert generated_rows[0]["pose_generation_seed"] == "42"
    assert generated_rows[0]["generated_pose_count"] == "1"
    assert generated_rows[0]["generated_pose_reference_comparison_status"]
    assert "restricted local generated-pose smoke" in generated_rows[0]["generated_pose_claim_boundary"].lower()
    assert generated_rows[0]["pose_id"].endswith("_generated_smoke_0")
    assert payload["summary"]["pose_success_rate"] == 1.0


def test_build_pdbbind_casf_pose_affinity_results_generate_poses_smoke_without_rdkit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tools.accounting.build_pdbbind_casf_pose_affinity_results as builder_module

    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "abstained": "0",
                "chirality_failure": "0",
                "tautomer_failure": "0",
                "protonation_failure": "0",
            },
        ],
    )
    out_csv = tmp_path / "results.csv"

    monkeypatch.setattr(builder_module, "Chem", None)
    monkeypatch.setattr(builder_module, "generate_conformers", lambda *_args, **_kwargs: None)

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(out_csv),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
            generate_poses=True,
            generate_poses_seed=42,
            generate_poses_count=1,
            generate_poses_max_complexes=1,
        )
    )

    generated_rows = [row for row in _rows(out_csv) if row["row_source"] == "generated_pose_smoke"]

    assert payload["summary"]["prediction_generation_enabled"] is True
    assert payload["summary"]["generated_pose_smoke_enabled"] is True
    assert payload["summary"]["external_state_mutated"] is False
    assert payload["summary"]["download_executed"] is False
    assert len(generated_rows) == 1
    assert "rdkit_unavailable" in generated_rows[0]["blockers"]
    assert generated_rows[0]["generated_pose_reference_comparison_status"] == "rdkit_unavailable"
    assert '"status": "rdkit_unavailable"' in generated_rows[0]["pose_rmsd_diagnostics"]

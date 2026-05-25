from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from tools import run_casp17_internal_physics_baseline_predictor as predictor
from tools import validate_casp17_backend_contract as contract
from tools import validate_casp17_confidence_calibration as confidence
from tools import validate_casp17_geometry_sanity as geometry


ROOT = Path(__file__).resolve().parents[2]


def _run_predictor(tmp_path: Path, fasta_text: str, *, target_id: str = "T9100") -> tuple[Path, Path, Path, Path]:
    fasta = tmp_path / f"{target_id}.fasta"
    out_dir = tmp_path / "job"
    raw_pdb = out_dir / f"{target_id}_model_1.pdb"
    runtime_json = out_dir / "backend_runtime.json"
    metrics_json = out_dir / "metrics.json"
    fasta.write_text(fasta_text, encoding="utf-8")
    command = [
        "python3",
        str(ROOT / "tools/run_casp17_internal_physics_baseline_predictor.py"),
        "--target-id",
        target_id,
        "--fasta",
        str(fasta),
        "--out-dir",
        str(out_dir),
        "--raw-pdb",
        str(raw_pdb),
        "--runtime-json",
        str(runtime_json),
        "--metrics-json",
        str(metrics_json),
        "--quality-preset",
        "smoke",
        "--device",
        "cpu",
        "--allow-cpu",
        "--out-json",
        str(out_dir / "predictor.json"),
        "--out-csv",
        str(out_dir / "predictor.csv"),
        "--out-md",
        str(out_dir / "predictor.md"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    return fasta, raw_pdb, runtime_json, metrics_json


def test_casp17_current_fasta_parser_counts_all_protein_targets() -> None:
    expected = {
        "T1331": (1, 281),
        "H1335": (5, 1820),
        "H2312": (3, 1409),
        "T2313": (1, 618),
        "H2338": (4, 1050),
        "H2339": (4, 1044),
        "H1340": (3, 686),
        "H1343": (3, 773),
        "H2319": (3, 497),
        "T1342": (1, 1455),
        "H1344": (3, 734),
        "H2321": (3, 502),
        "H1346": (4, 885),
        "H1347": (4, 876),
    }
    for target_id, (entry_count, residue_count) in expected.items():
        chains = predictor.parse_fasta(ROOT / f"runs/casp17_sequences_current/{target_id}.fasta")
        assert len(chains) == entry_count
        assert sum(len(chain.sequence) for chain in chains) == residue_count


def test_sequence_compaction_scale_uses_target_leak_free_composition() -> None:
    hydrophobic = predictor.sequence_compaction_scale("AVILMFWY" * 4)
    charged = predictor.sequence_compaction_scale("DEKR" * 8)
    breaker_rich = predictor.sequence_compaction_scale("PG" * 16)

    assert hydrophobic < charged
    assert hydrophobic < 1.0
    assert breaker_rich > 1.0


def test_finalize_coords_reduces_nonlocal_ca_close_contacts() -> None:
    coords = predictor._random_walk_coords(72, seed=42, compact=True)
    before = _nonlocal_ca_close_contacts(coords, threshold=2.0)
    finalized = predictor._finalize_coords(coords)
    after = _nonlocal_ca_close_contacts(finalized, threshold=2.0)
    ca_dist = (finalized[1:] - finalized[:-1]).norm(dim=-1)

    assert after <= before
    assert after <= 2
    assert float(ca_dist.min().item()) >= 3.0
    assert float(ca_dist.max().item()) <= 4.8


def test_repair_ca_bond_window_clamps_local_continuity() -> None:
    coords = predictor._random_walk_coords(20, seed=10, compact=False)
    coords[7] = coords[6] + 5.25 * (coords[7] - coords[6]) / (coords[7] - coords[6]).norm()
    repaired = predictor._repair_ca_bond_window(coords, min_dist=3.05, max_dist=4.75, target=3.80, iterations=4)
    ca_dist = (repaired[1:] - repaired[:-1]).norm(dim=-1)

    assert float(ca_dist.min().item()) >= 3.0
    assert float(ca_dist.max().item()) <= 4.8


def test_ranked_candidate_quality_prefers_gate_clean_geometry() -> None:
    clashy = predictor.torch.tensor(
        [[0.0, 0.0, 0.0], [3.8, 0.0, 0.0], [0.2, 0.0, 0.0], [4.0, 0.0, 0.0]],
        dtype=predictor.torch.float32,
    )
    clean = predictor.torch.tensor(
        [[0.0, 0.0, 0.0], [3.8, 0.0, 0.0], [7.6, 0.0, 0.0], [11.4, 0.0, 0.0]],
        dtype=predictor.torch.float32,
    )

    assert predictor._ranked_candidate_quality_score(clean, "AAAA", 1000.0) < predictor._ranked_candidate_quality_score(clashy, "AAAA", 0.0)


def _nonlocal_ca_close_contacts(coords, *, threshold: float) -> int:
    count = 0
    for left in range(int(coords.shape[0])):
        for right in range(left + 2, int(coords.shape[0])):
            if float((coords[left] - coords[right]).norm().item()) < threshold:
                count += 1
    return count


def test_internal_physics_predictor_writes_exact_sequence_raw_pdb(tmp_path: Path) -> None:
    fasta, raw_pdb, runtime_json, _metrics_json = _run_predictor(tmp_path, ">T9100\nACDEFGHIKLMNPQRSTVWY\n")

    chains = contract._pdb_ca_sequences(raw_pdb)
    assert [chain["chain_id"] for chain in chains] == ["A"]
    assert chains[0]["sequence"] == "ACDEFGHIKLMNPQRSTVWY"

    runtime = json.loads(runtime_json.read_text(encoding="utf-8"))
    assert runtime["summary"]["backend_kind"] == "internal_physics"
    assert runtime["summary"]["raw_pdb_exists"] is True

    contract_payload = contract.validate_contract(
        type(
            "Args",
            (),
            {
                "target_id": "T9100",
                "sequence_path": str(fasta),
                "raw_pdb": str(raw_pdb),
                "runtime_json": str(runtime_json),
                "backend_kind": "internal_physics",
                "require_gpu": False,
            },
        )()
    )
    assert contract_payload["summary"]["contract_status"] == "pass"


def test_internal_physics_predictor_multichain_geometry_and_confidence(tmp_path: Path) -> None:
    fasta, raw_pdb, _runtime_json, metrics_json = _run_predictor(
        tmp_path,
        ">H9101_A\nACDEFGHIK\n>H9101_B\nLMNPQRSTV\n",
        target_id="H9101",
    )

    chains = contract._pdb_ca_sequences(raw_pdb)
    assert [chain["sequence"] for chain in chains] == ["ACDEFGHIK", "LMNPQRSTV"]

    geometry_payload = geometry.validate_geometry(target_id="H9101", prediction_file=raw_pdb)
    assert geometry_payload["summary"]["geometry_sanity_status"] == "pass"

    confidence_payload = confidence.validate_confidence(target_id="H9101", prediction_file=raw_pdb, sequence_path=fasta)
    assert confidence_payload["summary"]["confidence_calibration_status"] == "pass"
    assert confidence_payload["summary"]["confidence_stddev"] >= 1.0

    metrics = json.loads(metrics_json.read_text(encoding="utf-8"))
    assert metrics["assembly"]["chain_count"] == 2
    assert metrics["assembly"]["interchain_ca_clash_count_3A"] == 0
    assert metrics["assembly"]["min_interchain_ca_distance_A"] >= 3.0
    assert metrics["assembly"]["interchain_ca_contact_count_12A"] >= 1


def test_internal_physics_metrics_are_finite(tmp_path: Path) -> None:
    _fasta, _raw_pdb, runtime_json, _metrics_json = _run_predictor(tmp_path, ">T9102\nACDEFGHIKLMNPQ\n", target_id="T9102")
    runtime = json.loads(runtime_json.read_text(encoding="utf-8"))
    metrics_path = ROOT / runtime["summary"]["metrics_json"]
    if not metrics_path.exists():
        metrics_path = tmp_path / "job/metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    chain = metrics["chains"][0]
    assert math.isfinite(float(chain["energy"]))
    assert 0.78 <= float(chain["sequence_compaction_scale"]) <= 1.34
    assert float(chain["target_rg_A"]) > 0.0
    assert float(chain["rg_ratio"]) > 0.0
    assert 2.0 <= float(chain["ca_distance_min_A"]) <= 4.2
    assert 3.0 <= float(chain["ca_distance_mean_A"]) <= 4.2


def test_internal_physics_predictor_can_emit_ranked_raw_models(tmp_path: Path) -> None:
    fasta = tmp_path / "T9200.fasta"
    out_dir = tmp_path / "job"
    ranked_dir = out_dir / "ranked"
    fasta.write_text(">T9200\nACDEFGHIKLMNPQ\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_internal_physics_baseline_predictor.py"),
            "--target-id",
            "T9200",
            "--fasta",
            str(fasta),
            "--out-dir",
            str(out_dir),
            "--raw-pdb",
            str(out_dir / "T9200_model_1.pdb"),
            "--runtime-json",
            str(out_dir / "runtime.json"),
            "--metrics-json",
            str(out_dir / "metrics.json"),
            "--quality-preset",
            "smoke",
            "--ensemble-size",
            "4",
            "--device",
            "cpu",
            "--allow-cpu",
            "--emit-backbone-atoms",
            "--ranked-raw-dir",
            str(ranked_dir),
            "--ranked-raw-count",
            "3",
            "--out-json",
            str(out_dir / "predictor.json"),
            "--out-csv",
            str(out_dir / "predictor.csv"),
            "--out-md",
            str(out_dir / "predictor.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((out_dir / "predictor.json").read_text(encoding="utf-8"))
    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert payload["summary"]["ranked_raw_count"] == 3
    assert metrics["summary"]["ranked_raw_count"] == 3
    assert len(metrics["ranked_raw_models"]) == 3
    for rank in range(1, 4):
        raw_pdb = ranked_dir / f"T9200_model_{rank}.pdb"
        assert raw_pdb.exists()
        assert "ATOM" in raw_pdb.read_text(encoding="utf-8")

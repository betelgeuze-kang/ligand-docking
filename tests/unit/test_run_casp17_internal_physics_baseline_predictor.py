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
        "H1319": (3, 497),
        "H1321": (3, 502),
        "H2324": (5, 856),
        "T1331": (1, 281),
        "H1335": (5, 1820),
        "H2312": (3, 1409),
        "T2313": (1, 618),
        "H2338": (4, 1050),
        "H2339": (4, 1044),
        "H1340": (3, 686),
        "H1343": (3, 773),
    }
    for target_id, (entry_count, residue_count) in expected.items():
        chains = predictor.parse_fasta(ROOT / f"runs/casp17_sequences_current/{target_id}.fasta")
        assert len(chains) == entry_count
        assert sum(len(chain.sequence) for chain in chains) == residue_count


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
    assert 2.0 <= float(chain["ca_distance_min_A"]) <= 4.2
    assert 3.0 <= float(chain["ca_distance_mean_A"]) <= 4.2

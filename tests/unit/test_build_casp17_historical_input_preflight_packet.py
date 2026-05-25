from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = {
    "prediction_method": "internal_physics_fixture",
    "prediction_created_at": "2024-01-01",
    "native_release_date": "2024-06-01",
    "prediction_generated_before_native_release": "true",
    "public_template_or_native_used_for_prediction": "false",
    "other_team_model_used": "false",
    "post_release_information_used": "false",
    "current_casp17_target": "false",
    "operator_clearance": "no_leak",
}
LAYERS = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "MODEL 1",
                "ATOM      1 CA   ALA A   1       1.000   2.000   3.000  1.00 70.00           C  ",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_watchlist(path: Path, current_targets: list[str] | None = None) -> None:
    path.write_text(
        json.dumps({"rows": [{"target_id": target_id, "human_open": True} for target_id in current_targets or []]}),
        encoding="utf-8",
    )


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "benchmark_id",
        "target_id",
        "scope",
        "split",
        "prediction_pdb",
        "native_pdb",
        "leakage_clearance",
        *PROVENANCE,
    ]
    for layer in LAYERS:
        fieldnames.append(f"{layer}_prediction_pdb")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _ready_row(tmp_path: Path, target_id: str, scope: str, *, with_layers: bool) -> dict[str, str]:
    prediction = tmp_path / "predictions" / f"{target_id}_prediction.pdb"
    native = tmp_path / "natives" / f"{target_id}_native.pdb"
    _write_pdb(prediction)
    _write_pdb(native)
    row = {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": scope,
        "split": "historical",
        "prediction_pdb": str(prediction),
        "native_pdb": str(native),
        "leakage_clearance": "no_leak",
        **PROVENANCE,
    }
    if with_layers:
        for layer in LAYERS:
            layer_path = tmp_path / "layers" / layer / f"{target_id}TS.pdb"
            _write_pdb(layer_path)
            row[f"{layer}_prediction_pdb"] = str(layer_path)
    return row


def test_historical_input_preflight_blocks_placeholder_scaffold_rows(tmp_path: Path) -> None:
    scaffold = tmp_path / "scaffold.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist)
    _write_manifest(
        scaffold,
        [
            {
                "benchmark_id": "hist_REQUIRED_MONOMER",
                "target_id": "REQUIRED_MONOMER",
                "scope": "monomer",
                "split": "historical",
                "prediction_pdb": "",
                "native_pdb": "",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_input_preflight_packet.py"),
            "--scaffold-csv",
            str(scaffold),
            "--ready-manifest-csv",
            str(tmp_path / "missing_ready.csv"),
            "--active-manifest-csv",
            str(tmp_path / "missing_active.csv"),
            "--target-watchlist-json",
            str(watchlist),
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

    assert payload["summary"]["source_mode"] == "scaffold"
    assert payload["summary"]["preflight_status"] == "blocked"
    assert payload["summary"]["historical_ready_count"] == 0
    assert row["row_status"] == "blocked"
    assert "placeholder_target_id" in row["blockers"]
    assert "prediction_pdb_missing" in row["blockers"]


def test_historical_input_preflight_marks_ready_manifest_ready_to_activate_with_layers(tmp_path: Path) -> None:
    ready = tmp_path / "ready.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist, ["T1331"])
    _write_manifest(ready, [_ready_row(tmp_path, "T9001", "monomer", with_layers=True)])

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_input_preflight_packet.py"),
            "--scaffold-csv",
            str(tmp_path / "missing_scaffold.csv"),
            "--ready-manifest-csv",
            str(ready),
            "--active-manifest-csv",
            str(tmp_path / "missing_active.csv"),
            "--target-watchlist-json",
            str(watchlist),
            "--min-ready-total",
            "1",
            "--min-ready-complex",
            "0",
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

    assert payload["summary"]["source_mode"] == "ready_manifest"
    assert payload["summary"]["historical_input_preflight_status"] == "ready_to_activate"
    assert payload["summary"]["ablation_input_preflight_status"] == "ready_to_activate"
    assert row["row_status"] == "historical_and_ablation_ready"
    assert row["ablation_layer_present_count"] == 10
    assert row["missing_ablation_layers"] == ""


def test_historical_input_preflight_passes_active_manifest_but_blocks_missing_layers(tmp_path: Path) -> None:
    active = tmp_path / "active.csv"
    watchlist = tmp_path / "watchlist.json"
    _write_watchlist(watchlist)
    _write_manifest(active, [_ready_row(tmp_path, "T9001", "monomer", with_layers=False)])

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_input_preflight_packet.py"),
            "--scaffold-csv",
            str(tmp_path / "missing_scaffold.csv"),
            "--ready-manifest-csv",
            str(tmp_path / "missing_ready.csv"),
            "--active-manifest-csv",
            str(active),
            "--target-watchlist-json",
            str(watchlist),
            "--min-ready-total",
            "1",
            "--min-ready-complex",
            "0",
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

    assert payload["summary"]["source_mode"] == "active_manifest"
    assert payload["summary"]["historical_input_preflight_status"] == "pass"
    assert payload["summary"]["ablation_input_preflight_status"] == "blocked"
    assert payload["summary"]["preflight_status"] == "blocked"
    assert row["row_status"] == "historical_ready_ablation_incomplete"
    assert row["ablation_layer_present_count"] == 0
    assert "recursive" in row["missing_ablation_layers"]

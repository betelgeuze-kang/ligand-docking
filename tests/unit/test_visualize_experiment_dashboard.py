import json

import pandas as pd
import pytest

from tools import visualize_experiment_dashboard as viz


def test_visualize_experiment_dashboard_smoke(tmp_path):
    csv_a = tmp_path / "run_a.csv"
    csv_b = tmp_path / "run_b.csv"
    gate_json = tmp_path / "gate.json"
    movie_json = tmp_path / "movie.json"
    pdb = tmp_path / "toy.pdb"
    out_html = tmp_path / "dashboard.html"
    out_json = tmp_path / "dashboard.json"

    pd.DataFrame(
        [
            {"target": "Chignolin", "step": 0, "energy": -10.0, "Rg": 5.2},
            {"target": "Chignolin", "step": 1, "energy": -9.5, "Rg": 5.1},
            {"target": "Other", "step": 2, "energy": -1.0, "Rg": 8.0},
        ]
    ).to_csv(csv_a, index=False)
    pd.DataFrame(
        [
            {"target": "Chignolin", "step": 0, "energy": -10.2, "Rg": 5.3},
            {"target": "Chignolin", "step": 1, "energy": -9.7, "Rg": 5.2},
            {"target": "Other", "step": 2, "energy": -1.3, "Rg": 8.1},
        ]
    ).to_csv(csv_b, index=False)
    gate_json.write_text(
        json.dumps({"summary": {"thresholds": {"energy": -8.0}}}),
        encoding="utf-8",
    )
    pdb.write_text(
        "ATOM      1  N   GLY A   1      11.104   9.104  10.104  1.00 20.00           N\nEND\n",
        encoding="utf-8",
    )
    movie_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "pdb_path": str(pdb),
                        "mp4_path": str(tmp_path / "toy.mp4"),
                        "script_path": str(tmp_path / "toy.cxc"),
                        "ok": True,
                        "executed": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    args = viz.build_parser().parse_args(
        [
            "--csv",
            str(csv_a),
            "--compare-csv",
            str(csv_b),
            "--labels",
            "run_a",
            "--labels",
            "run_b",
            "--target",
            "Chignolin",
            "--gate-json",
            str(gate_json),
            "--threshold",
            "Rg=6.0",
            "--pdb",
            str(pdb),
            "--movie-json",
            str(movie_json),
            "--out-html",
            str(out_html),
            "--out-json",
            str(out_json),
        ]
    )
    payload = viz.build_dashboard(args)

    assert out_html.exists()
    assert out_json.exists()
    assert payload["runs"] == 2
    assert payload["pdb_entries"] == 1
    assert payload["movie_entries"] == 1
    assert float(payload["thresholds"]["energy"]) == -8.0
    assert float(payload["thresholds"]["Rg"]) == 6.0
    assert int(payload["summary"]["run_count"]) == 2
    assert int(payload["summary"]["metric_count"]) >= 1

    saved = json.loads(out_json.read_text(encoding="utf-8"))
    assert saved["target_filters"] == ["Chignolin"]
    assert len(saved["runs"]) == 2
    assert "summary" in saved
    assert "metric_cards" in saved["summary"]
    assert int(saved["summary"]["movie_count"]) == 1
    assert "decision_board" in saved["summary"]
    assert saved["summary"]["decision_board"]["available"] is True
    assert isinstance(saved.get("movie_entries"), list)
    assert len(saved["movie_entries"]) == 1
    energy_series = saved["runs"][0]["metrics"]["energy"]
    assert len(energy_series["x"]) == len(energy_series["y"]) == 2
    assert all(v <= 1.0 for v in energy_series["x"])


def test_visualize_experiment_dashboard_target_filter_requires_column(tmp_path):
    csv_a = tmp_path / "run_a.csv"
    pd.DataFrame(
        [
            {"step": 0, "energy": -10.0},
            {"step": 1, "energy": -9.8},
        ]
    ).to_csv(csv_a, index=False)

    args = viz.build_parser().parse_args(
        [
            "--csv",
            str(csv_a),
            "--target",
            "Chignolin",
            "--out-html",
            str(tmp_path / "x.html"),
            "--out-json",
            str(tmp_path / "x.json"),
        ]
    )
    with pytest.raises(ValueError, match="target filter requested but column not found"):
        viz.build_dashboard(args)


def test_visualize_experiment_dashboard_from_json_rebuild(tmp_path):
    src_json = tmp_path / "src_dashboard.json"
    out_html = tmp_path / "rebuilt_dashboard.html"
    payload = {
        "generated_at_local": "2026-02-20T00:00:00",
        "title": "Dashboard Rebuild",
        "metrics": ["energy"],
        "thresholds": {},
        "target_filters": [],
        "runs": [
            {
                "label": "run_1",
                "csv_path": "runs/sample.csv",
                "rows": 2,
                "color": "#0b84f3",
                "metrics": {"energy": {"x": [0, 1], "y": [-1.0, -0.5]}},
            }
        ],
        "pdb_entries": [
            {
                "name": "toy.pdb",
                "path": "runs/toy.pdb",
                "content": "ATOM      1  N   GLY A   1      11.104   9.104  10.104  1.00 20.00           N\nEND\n",
            }
        ],
        "summary": {"run_count": 1, "metric_count": 1, "pdb_count": 1, "metric_cards": []},
    }
    src_json.write_text(json.dumps(payload), encoding="utf-8")

    args = viz.build_parser().parse_args(
        [
            "--from-json",
            str(src_json),
            "--out-html",
            str(out_html),
        ]
    )
    ret = viz.build_dashboard(args)
    assert ret["from_json"] == str(src_json)
    assert out_html.exists()
    html = out_html.read_text(encoding="utf-8")
    assert "viewerModal" in html
    assert "openViewerModalBtn" in html
    assert "pdbSelectModal" in html
    assert "openMovieBtn" in html


def test_collect_pdb_entries_keeps_external_and_internal_sources(tmp_path):
    pub_dir = tmp_path / "data" / "public_structures" / "nightly" / "d1"
    int_dir = tmp_path / "data" / "internal_structures" / "nightly" / "d1"
    pub_dir.mkdir(parents=True, exist_ok=True)
    int_dir.mkdir(parents=True, exist_ok=True)

    for i in range(2):
        (pub_dir / f"target_{i}_pdb_1AAA.pdb").write_text(
            "ATOM      1  CA  GLY A   1      11.000   9.000  10.000  1.00 20.00           C\nEND\n",
            encoding="utf-8",
        )
    for i in range(2):
        (int_dir / f"internal_post_target_{i}.pdb").write_text(
            "ATOM      1  CA  GLY A   1      12.000   8.000  11.000  1.00 20.00           C\nEND\n",
            encoding="utf-8",
        )

    out = viz._collect_pdb_entries(
        pdb_files=[],
        pdb_glob=[str(pub_dir / "*.pdb"), str(int_dir / "*.pdb")],
        max_pdb=2,
    )
    assert len(out) == 2
    sources = {str(x.get("source", "")) for x in out}
    assert "external_public" in sources
    assert "internal_postprocessed" in sources

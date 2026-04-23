from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import run_ood_first_validation_batch as ood


def _write_ca_pdb(path: Path, n_ca: int, offset: float = 0.0) -> None:
    lines = []
    for i in range(1, n_ca + 1):
        x = float(i) + float(offset)
        y = float(i % 3) * 0.5 + float(offset)
        z = float(i % 5) * 0.25 + float(offset)
        lines.append(
            f"ATOM  {i:5d}  CA  ALA A{i:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 80.00           C"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_ood_policy_enforces_proxy_and_real_afdb_gate(tmp_path: Path):
    pdb_path = tmp_path / "t1_pdb.pdb"
    afdb_proxy_path = tmp_path / "t1_afdb_proxy.pdb"
    _write_ca_pdb(pdb_path, n_ca=12, offset=0.0)
    _write_ca_pdb(afdb_proxy_path, n_ca=12, offset=0.1)

    sources_csv = tmp_path / "sources.csv"
    pd.DataFrame([{"target": "T1", "pdb_id": "1ABC", "uniprot_id": "", "notes": "test"}]).to_csv(
        sources_csv, index=False
    )
    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "T1",
                "source_kind": "pdb_or_other",
                "source_file": str(pdb_path),
                "path": str(pdb_path),
                "pdb_id": "1ABC",
            }
        ]
    ).to_csv(manifest_csv, index=False)
    curated_csv = tmp_path / "curated.csv"
    pd.DataFrame(
        [
            {
                "target": "T1",
                "source_kind": "pdb_or_other",
                "source_file": str(pdb_path),
                "include": 1,
                "sample_weight": 1.0,
                "plddt_mean": 90.0,
            },
            {
                "target": "T1",
                "source_kind": "afdb_proxy",
                "source_file": str(afdb_proxy_path),
                "include": 1,
                "sample_weight": 1.0,
                "plddt_mean": 90.0,
            },
        ]
    ).to_csv(curated_csv, index=False)

    args = ood.build_parser().parse_args(
        [
            "--targets",
            "T1",
            "--sources-csv",
            str(sources_csv),
            "--manifest-csv",
            str(manifest_csv),
            "--skip-fetch",
            "--skip-curation",
            "--curated-csv",
            str(curated_csv),
            "--out-prefix",
            str(tmp_path / "ood"),
            "--min-pairs",
            "1",
            "--max-mean-pair-rmsd",
            "10.0",
            "--max-proxy-rows",
            "0",
            "--require-real-afdb",
        ]
    )
    summary = ood.run_ood_batch(args)
    assert summary["pass"] is False
    assert summary["gates"]["max_proxy_rows"]["pass"] is False
    assert summary["gates"]["require_real_afdb"]["pass"] is False
    assert int(summary["proxy_summary"]["proxy_rows_added"]) >= 1


def test_ood_policy_domain_coverage_gate(tmp_path: Path):
    p1 = tmp_path / "t1.pdb"
    a1 = tmp_path / "t1_afdb.pdb"
    p2 = tmp_path / "t2.pdb"
    a2 = tmp_path / "t2_afdb.pdb"
    _write_ca_pdb(p1, n_ca=12, offset=0.0)
    _write_ca_pdb(a1, n_ca=12, offset=0.1)
    _write_ca_pdb(p2, n_ca=12, offset=0.0)
    _write_ca_pdb(a2, n_ca=12, offset=0.2)

    sources_csv = tmp_path / "sources.csv"
    pd.DataFrame(
        [
            {"target": "T1", "pdb_id": "1AAA", "uniprot_id": "", "notes": "test"},
            {"target": "T2", "pdb_id": "1BBB", "uniprot_id": "", "notes": "test"},
        ]
    ).to_csv(sources_csv, index=False)
    tags_csv = tmp_path / "tags.csv"
    pd.DataFrame(
        [
            {"target": "T1", "domain": "globular"},
            {"target": "T2", "domain": "metal"},
        ]
    ).to_csv(tags_csv, index=False)
    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {"target": "T1", "source_kind": "pdb_or_other", "source_file": str(p1), "path": str(p1), "pdb_id": "1AAA"},
            {"target": "T1", "source_kind": "afdb", "source_file": str(a1), "path": str(a1), "pdb_id": "1AAA"},
            {"target": "T2", "source_kind": "pdb_or_other", "source_file": str(p2), "path": str(p2), "pdb_id": "1BBB"},
            {"target": "T2", "source_kind": "afdb", "source_file": str(a2), "path": str(a2), "pdb_id": "1BBB"},
        ]
    ).to_csv(manifest_csv, index=False)
    curated_csv = tmp_path / "curated.csv"
    pd.DataFrame(
        [
            {"target": "T1", "source_kind": "pdb_or_other", "source_file": str(p1), "include": 1, "sample_weight": 1.0, "plddt_mean": 90.0},
            {"target": "T1", "source_kind": "afdb", "source_file": str(a1), "include": 1, "sample_weight": 1.0, "plddt_mean": 90.0},
            {"target": "T2", "source_kind": "pdb_or_other", "source_file": str(p2), "include": 1, "sample_weight": 1.0, "plddt_mean": 90.0},
            {"target": "T2", "source_kind": "afdb", "source_file": str(a2), "include": 1, "sample_weight": 1.0, "plddt_mean": 90.0},
        ]
    ).to_csv(curated_csv, index=False)

    args = ood.build_parser().parse_args(
        [
            "--targets",
            "T1,T2",
            "--sources-csv",
            str(sources_csv),
            "--domain-tags-csv",
            str(tags_csv),
            "--manifest-csv",
            str(manifest_csv),
            "--skip-fetch",
            "--skip-curation",
            "--curated-csv",
            str(curated_csv),
            "--out-prefix",
            str(tmp_path / "ood"),
            "--min-pairs",
            "2",
            "--max-mean-pair-rmsd",
            "10.0",
            "--min-domain-coverage",
            "3",
        ]
    )
    summary = ood.run_ood_batch(args)
    assert summary["pass"] is False
    assert summary["gates"]["min_pairs"]["pass"] is True
    assert summary["gates"]["min_domain_coverage"]["pass"] is False
    assert int(summary["pair_metrics"]["domain_coverage"]) == 2


def test_ood_curation_preserves_afdb_proxy_source_kind(tmp_path: Path):
    pdb_path = tmp_path / "t1_pdb.pdb"
    afdb_proxy_path = tmp_path / "t1_afdb_proxy.pdb"
    _write_ca_pdb(pdb_path, n_ca=12, offset=0.0)
    _write_ca_pdb(afdb_proxy_path, n_ca=12, offset=0.2)

    sources_csv = tmp_path / "sources.csv"
    pd.DataFrame([{"target": "T1", "pdb_id": "1ABC", "uniprot_id": "", "notes": "test"}]).to_csv(
        sources_csv, index=False
    )
    manifest_csv = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "T1",
                "source_kind": "pdb_or_other",
                "source_file": str(pdb_path),
                "path": str(pdb_path),
                "pdb_id": "1ABC",
            },
            {
                "target": "T1",
                "source_kind": "afdb_proxy",
                "source_file": str(afdb_proxy_path),
                "path": str(afdb_proxy_path),
                "pdb_id": "1ABC",
            },
        ]
    ).to_csv(manifest_csv, index=False)

    args = ood.build_parser().parse_args(
        [
            "--targets",
            "T1",
            "--sources-csv",
            str(sources_csv),
            "--manifest-csv",
            str(manifest_csv),
            "--skip-fetch",
            "--out-prefix",
            str(tmp_path / "ood"),
            "--min-pairs",
            "1",
            "--max-mean-pair-rmsd",
            "10.0",
            "--max-proxy-rows",
            "0",
            "--require-real-afdb",
        ]
    )
    summary = ood.run_ood_batch(args)

    pair_df = pd.read_csv(summary["artifacts"]["pair_csv"])
    assert int(pair_df.shape[0]) == 1
    assert str(pair_df.iloc[0]["afdb_source_kind"]) == "afdb_proxy"
    assert int(pair_df.iloc[0]["afdb_is_proxy"]) == 1
    assert str(pair_df.iloc[0]["reason"]) == "afdb_proxy_not_allowed"


def test_parse_targets_sources_all_uses_sources_csv(tmp_path: Path):
    sources_csv = tmp_path / "sources.csv"
    pd.DataFrame(
        [
            {"target": "M20_A", "pdb_id": "1AAA"},
            {"target": "M20_B", "pdb_id": "1BBB"},
            {"target": "M20_A", "pdb_id": "1AAA"},  # duplicate
        ]
    ).to_csv(sources_csv, index=False)
    targets = ood._parse_targets("sources_all", str(sources_csv))
    assert targets == ["M20_A", "M20_B"]

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools import build_claim_inputs_from_openmm_manifest as mod


def test_build_claim_inputs_from_manifest_smoke(tmp_path):
    t = 30
    n = 12
    rng = np.random.default_rng(123)
    base = rng.normal(size=(n, 3)).astype(np.float64)
    traj = []
    for i in range(t):
        noise = rng.normal(scale=0.02 + 0.0005 * i, size=(n, 3))
        traj.append(base + noise)
    traj = np.asarray(traj, dtype=np.float64)

    traj_path = tmp_path / "traj.npy"
    np.save(traj_path, traj)

    manifest = pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "path": str(traj_path),
                "beads_per_residue": 1.0,
                "bead_order": "ca_then_sc",
            }
        ]
    )
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    out_k = tmp_path / "k.csv"
    out_t = tmp_path / "t.csv"
    out_e = tmp_path / "e.csv"
    out_d_csv = tmp_path / "diag.csv"
    out_d_json = tmp_path / "diag.json"
    out_j = tmp_path / "s.json"

    args = mod.build_parser().parse_args(
        [
            "--manifest-csv",
            str(manifest_path),
            "--targets",
            "Chignolin",
            "--out-kinetics-csv",
            str(out_k),
            "--out-thermo-csv",
            str(out_t),
            "--out-experiment-csv",
            str(out_e),
            "--out-diagnostics-csv",
            str(out_d_csv),
            "--out-diagnostics-json",
            str(out_d_json),
            "--out-json",
            str(out_j),
        ]
    )
    payload = mod.run_build(args)

    assert payload["summary"]["targets_requested"] == 1
    assert payload["summary"]["targets_built"] == 1
    assert out_k.exists()
    assert out_t.exists()
    assert out_e.exists()
    assert out_d_csv.exists()
    assert out_d_json.exists()
    assert out_j.exists()

    kdf = pd.read_csv(out_k)
    tdf = pd.read_csv(out_t)
    edf = pd.read_csv(out_e)
    ddf = pd.read_csv(out_d_csv)
    assert {"target", "mfpt_pred", "mfpt_ref", "its_pred", "its_ref"}.issubset(kdf.columns)
    assert {"target", "deltaG_rmse_kcal_mol", "state_population_jsd", "pmf_1d_emd"}.issubset(tdf.columns)
    assert {"target", "nmr_noe_violation_rate", "cryoem_map_cc", "saxs_chi2"}.issubset(edf.columns)
    assert {"target", "split_mode", "split_replicas_used", "effective_ref_frames_min"}.issubset(ddf.columns)

    saved = json.loads(Path(out_j).read_text(encoding="utf-8"))
    assert saved["summary"]["targets_built"] == 1
    assert "diagnostics_json" in saved["artifacts"]

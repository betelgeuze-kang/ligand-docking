#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CALIBRATION_PACKET_JSON = "runs/tau_k18_full_fold_corrected_calibration_packet_current.json"
DEFAULT_FROZEN_LABELS_CSV = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_eval_corrected_targets.csv"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phsplithelix_frozen_r1"
DEFAULT_OUT_JSON = "runs/tau_k18_frozen_label_parity_packet_current.json"
DEFAULT_OUT_MD = "runs/tau_k18_frozen_label_parity_packet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(packet_payload: dict[str, Any], *, frozen_labels_csv: str, out_prefix: str) -> dict[str, Any]:
    packet_s = dict(packet_payload.get("summary", {}) or {})
    summary = {
        "status": "operator_parity_packet_ready",
        "packet_scope": "tau_k18_frozen_label_parity_rerun",
        "operator_scope_now": str(packet_s.get("operator_scope_now") or "").strip(),
        "blocking_target": str(packet_s.get("blocking_target") or "tau_k18").strip(),
        "candidate_rule_name": str(packet_s.get("candidate_rule_name") or "").strip(),
        "frozen_labels_csv": str(_resolve(frozen_labels_csv)),
        "out_prefix": str(_resolve(out_prefix)),
        "exact_command": " ".join(
            [
                "python3",
                "tools/run_idp_tau_k18_stabilization_trial.py",
                "--eval-config-json",
                str(_resolve("runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold_inputs/fold6_tau_k18_eval.json")),
                "--baseline-gate-json",
                str(_resolve("runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_gate_baseline_summary.json")),
                "--frozen-labels-csv",
                str(_resolve(frozen_labels_csv)),
                "--out-prefix",
                str(_resolve(out_prefix)),
                "--seed",
                "123",
                "--epochs",
                "120",
                "--patience",
                "24",
                "--lr",
                "0.00075",
                "--weight-decay",
                "1e-05",
                "--kalman-shadow-feature-mask",
                "rg_sasa_only",
                "--idp-r16-ml-patch",
                "1",
                "--idp-r17-tau-ph-split-patch",
                "1",
            ]
        ),
        "decision_reason": (
            "Re-run the same tau_k18 full-fold calibration slice with frozen labels so the local trial uses the same truth basis as the bounded commercial-pretest failure slice."
        ),
        "next_required_step": (
            "Run the parity rerun first. Only interpret calibration quality after label_basis_drift_count returns to zero."
        ),
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Frozen-Label Parity Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- candidate_rule_name: `{s['candidate_rule_name']}`",
        f"- frozen_labels_csv: `{s['frozen_labels_csv']}`",
        "",
        "## Exact Command",
        "",
        "```bash",
        s["exact_command"],
        "```",
        "",
        "## Why This Slice",
        "",
        f"- {s['decision_reason']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tau_k18 frozen-label parity rerun packet.")
    parser.add_argument("--calibration-packet-json", default=DEFAULT_CALIBRATION_PACKET_JSON)
    parser.add_argument("--frozen-labels-csv", default=DEFAULT_FROZEN_LABELS_CSV)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.calibration_packet_json),
        frozen_labels_csv=args.frozen_labels_csv,
        out_prefix=args.out_prefix,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()

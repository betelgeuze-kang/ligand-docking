#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import torch

from core.rust_hip_backend import RustHipBackend
from theory.branches.idp_logic import IDPLogic


class _Top:
    def __init__(self, residue_types: torch.Tensor, box_size: torch.Tensor | None = None):
        self.residue_types = residue_types
        self.box_size = box_size if box_size is not None else torch.tensor([160.0], dtype=torch.float32, device=residue_types.device)


def _tensor_to_device(x: Any, device: torch.device):
    if torch.is_tensor(x):
        return x.to(device=device)
    if isinstance(x, dict):
        return {k: _tensor_to_device(v, device) for k, v in x.items()}
    if isinstance(x, list):
        return [_tensor_to_device(v, device) for v in x]
    return x


def _scalar_from_info(info: Dict[str, Any], key: str) -> float:
    value = info.get(key, 0.0)
    if torch.is_tensor(value):
        return float(value.detach().float().mean().item())
    return float(value)


def _first_tensor(*values: Any) -> torch.Tensor | None:
    for value in values:
        if torch.is_tensor(value):
            return value
    return None


def _bool_like(x: torch.Tensor, device: torch.device) -> torch.Tensor:
    out = x.to(device=device)
    if out.dtype != torch.bool:
        out = out > 0.5
    if not out.is_contiguous():
        out = out.contiguous()
    return out


def _uint8_like(x: torch.Tensor, device: torch.device) -> torch.Tensor:
    out = x.to(device=device)
    if out.dtype != torch.uint8:
        out = (out > 0.5).to(dtype=torch.uint8)
    if not out.is_contiguous():
        out = out.contiguous()
    return out


def _flat_float_like(x: torch.Tensor, device: torch.device) -> torch.Tensor:
    out = x.to(device=device, dtype=torch.float32)
    if out.ndim != 1:
        out = out.reshape(-1)
    if not out.is_contiguous():
        out = out.contiguous()
    return out


def _tensor_like(x: torch.Tensor, device: torch.device, *, dtype: torch.dtype | None = None) -> torch.Tensor:
    out = x.to(device=device, dtype=dtype or x.dtype)
    if not out.is_contiguous():
        out = out.contiguous()
    return out


def _derive_prepared_inputs(packet: Dict[str, Any], device: torch.device) -> Dict[str, torch.Tensor]:
    derived = dict(packet.get("derived", {}) or {})
    raw = dict(packet.get("raw", {}) or {})
    backend_inputs = dict(derived.get("backend_inputs", {}) or {})
    pair_ctx = dict(derived.get("pair_ctx", {}) or {})
    cond = dict(derived.get("cond", {}) or {})

    mod = IDPLogic(device).to(device)
    env_scale = _first_tensor(backend_inputs.get("env_scale"), derived.get("env_scale"))
    nb_idx = _first_tensor(backend_inputs.get("nb_idx"), raw.get("nb_idx"))
    nb_dist = _first_tensor(backend_inputs.get("nb_dist"), raw.get("nb_dist"))
    nb_mask = _first_tensor(backend_inputs.get("nb_mask"), raw.get("nb_mask"))
    donor = _first_tensor(backend_inputs.get("donor"))
    acceptor = _first_tensor(backend_inputs.get("acceptor"))
    ca = _first_tensor(backend_inputs.get("ca"))
    sc = _first_tensor(backend_inputs.get("sc"))
    disorder = _first_tensor(backend_inputs.get("disorder"))
    aromatic_mask = _first_tensor(backend_inputs.get("aromatic_mask"))
    cationic_mask = _first_tensor(backend_inputs.get("cationic_mask"))
    sticker_mask = _first_tensor(backend_inputs.get("sticker_mask"))
    vh_scale = _first_tensor(backend_inputs.get("virtual_hbond_scale"), cond.get("virtual_hbond_scale"))
    contact_gain_scale = _first_tensor(backend_inputs.get("contact_gain_scale"), cond.get("contact_gain_scale"))
    exposure_sensitivity = _first_tensor(backend_inputs.get("exposure_sensitivity"), cond.get("exposure_sensitivity"))
    center = _first_tensor(backend_inputs.get("virtual_hbond_center_A"), cond.get("virtual_hbond_center_A"))
    width = _first_tensor(backend_inputs.get("virtual_hbond_width_A"), cond.get("virtual_hbond_width_A"))
    exposure_gain_scale = _first_tensor(backend_inputs.get("exposure_gain_scale"))
    llps_branch = _first_tensor(backend_inputs.get("llps_branch"), cond.get("llps_branch"))
    is_llps_target = _first_tensor(backend_inputs.get("is_llps_target"), cond.get("is_llps_target"))
    is_hnrn_target = _first_tensor(backend_inputs.get("is_hnrn_target"), cond.get("is_hnrn_target"))
    is_fus_target = _first_tensor(backend_inputs.get("is_fus_target"), cond.get("is_fus_target"))
    vh_strength = _first_tensor(backend_inputs.get("virtual_hbond_strength"))
    unsat_penalty = _first_tensor(backend_inputs.get("unsat_penalty_strength"))

    if not torch.is_tensor(exposure_gain_scale):
        coords = raw.get("coords")
        raw_top = dict(raw.get("top", {}) or {})
        residue_types = raw_top.get("residue_types")
        nb_dist = raw.get("nb_dist")
        if (
            torch.is_tensor(coords)
            and torch.is_tensor(nb_idx)
            and torch.is_tensor(nb_mask)
            and torch.is_tensor(nb_dist)
            and torch.is_tensor(residue_types)
        ):
            box_size = raw_top.get("box_size")
            if torch.is_tensor(box_size):
                box_size = box_size.to(device=device)
            top = _Top(residue_types=residue_types.to(device=device), box_size=box_size)
            sim_params = _tensor_to_device(raw.get("sim_params"), device)
            current_packet = mod.build_virtual_hbond_parity_packet(
                coords.to(device=device),
                top=top,
                nb_data=(nb_idx.to(device=device), nb_dist.to(device=device), nb_mask.to(device=device)),
                sim_params=sim_params,
            )
            refreshed_inputs = dict(current_packet.get("derived", {}).get("backend_inputs", {}) or {})
            exposure_gain_scale = _first_tensor(refreshed_inputs.get("exposure_gain_scale"))

    required = {
        "donor": donor,
        "acceptor": acceptor,
        "ca": ca,
        "sc": sc,
        "disorder": disorder,
        "aromatic_mask": aromatic_mask,
        "cationic_mask": cationic_mask,
        "sticker_mask": sticker_mask,
        "nb_idx": nb_idx,
        "nb_dist": nb_dist,
        "nb_mask": nb_mask,
        "virtual_hbond_scale": vh_scale,
        "contact_gain_scale": contact_gain_scale,
        "exposure_sensitivity": exposure_sensitivity,
        "exposure_gain_scale": exposure_gain_scale,
        "virtual_hbond_center_A": center,
        "virtual_hbond_width_A": width,
        "llps_branch": llps_branch,
        "is_llps_target": is_llps_target,
        "is_hnrn_target": is_hnrn_target,
        "is_fus_target": is_fus_target,
        "env_scale": env_scale,
    }
    missing = [name for name, value in required.items() if not torch.is_tensor(value)]
    if missing:
        raise TypeError(f"backend_inputs must include all virtual_hbond tensors; missing: {', '.join(missing)}")

    if not torch.is_tensor(vh_strength):
        vh_strength = torch.relu(mod.virtual_hbond_strength.detach())
    if not torch.is_tensor(unsat_penalty):
        unsat_penalty = torch.relu(mod.unsat_penalty_strength.detach())

    return {
        "donor": _tensor_like(donor, device, dtype=torch.float32),
        "acceptor": _tensor_like(acceptor, device, dtype=torch.float32),
        "ca": _tensor_like(ca, device, dtype=torch.float32),
        "sc": _tensor_like(sc, device, dtype=torch.float32),
        "disorder": _tensor_like(disorder, device, dtype=torch.float32),
        "aromatic_mask": _bool_like(aromatic_mask, device),
        "cationic_mask": _bool_like(cationic_mask, device),
        "sticker_mask": _bool_like(sticker_mask, device),
        "nb_idx": _tensor_like(nb_idx, device, dtype=torch.int64),
        "nb_dist": _tensor_like(nb_dist, device, dtype=torch.float32),
        "nb_mask": _uint8_like(nb_mask, device),
        "virtual_hbond_scale": _flat_float_like(vh_scale, device),
        "contact_gain_scale": _flat_float_like(contact_gain_scale, device),
        "exposure_sensitivity": _flat_float_like(exposure_sensitivity, device),
        "exposure_gain_scale": _flat_float_like(exposure_gain_scale, device),
        "virtual_hbond_center_A": _flat_float_like(center, device),
        "virtual_hbond_width_A": _flat_float_like(width, device),
        "llps_branch": _flat_float_like(llps_branch, device),
        "is_llps_target": _flat_float_like(is_llps_target, device),
        "is_hnrn_target": _flat_float_like(is_hnrn_target, device),
        "is_fus_target": _flat_float_like(is_fus_target, device),
        "env_scale": _tensor_like(env_scale, device, dtype=torch.float32),
        "virtual_hbond_strength": _tensor_like(vh_strength, device, dtype=torch.float32),
        "unsat_penalty_strength": _tensor_like(unsat_penalty, device, dtype=torch.float32),
    }


def check_packet(packet: Dict[str, Any], device: str, backend: str) -> Dict[str, Any]:
    dev = torch.device(str(device))
    ref = packet["reference"]
    info_ref = dict(ref.get("info", {}) or {})
    result: Dict[str, Any] = {
        "target_name": str(packet.get("meta", {}).get("target_name", "")),
        "capture_step": int(packet.get("meta", {}).get("capture_step", 0) or 0),
        "backend": str(backend),
        "status": "ok",
        "force_max_abs_err": 0.0,
        "force_mean_abs_err": 0.0,
        "contacts_abs_err": 0.0,
        "distance_abs_err": 0.0,
        "backend_reported": str(backend),
    }

    if str(backend).strip().lower() == "python":
        os.environ["IDP_VIRTUAL_HBOND_BACKEND"] = "python"
        raw = dict(packet.get("raw", {}) or {})
        raw_top = dict(raw.get("top", {}) or {})
        coords = raw["coords"].to(device=dev)
        nb_idx = raw["nb_idx"].to(device=dev)
        nb_dist = raw["nb_dist"].to(device=dev)
        nb_mask = raw["nb_mask"].to(device=dev)
        residue_types = raw_top["residue_types"].to(device=dev)
        box_size = raw_top.get("box_size")
        if torch.is_tensor(box_size):
            box_size = box_size.to(device=dev)
        top = _Top(residue_types=residue_types, box_size=box_size)
        sim_params = _tensor_to_device(raw.get("sim_params"), dev)

        mod = IDPLogic(dev).to(dev)
        out = mod.build_virtual_hbond_parity_packet(coords, top=top, nb_data=(nb_idx, nb_dist, nb_mask), sim_params=sim_params)
        force_ref = ref["force"].to(device=dev)
        force_new = out["reference"]["force"].to(device=dev)
        force_abs = torch.abs(force_new - force_ref)
        info_new = dict(out["reference"].get("info", {}) or {})
        result.update(
            {
                "force_max_abs_err": float(force_abs.max().item()) if force_abs.numel() else 0.0,
                "force_mean_abs_err": float(force_abs.mean().item()) if force_abs.numel() else 0.0,
                "contacts_abs_err": abs(_scalar_from_info(info_new, "virtual_hbond_contacts") - _scalar_from_info(info_ref, "virtual_hbond_contacts")),
                "distance_abs_err": abs(_scalar_from_info(info_new, "virtual_hbond_mean_distance_A") - _scalar_from_info(info_ref, "virtual_hbond_mean_distance_A")),
                "backend_reported": str(out.get("meta", {}).get("virtual_hbond_backend", "python")),
            }
        )
        return result

    if str(backend).strip().lower() in {"rust_hip", "rust", "hip"}:
        rust = RustHipBackend(device=dev)
        if not rust.supports_idp_virtual_hbond():
            result["status"] = "unsupported"
            result["message"] = "Rust HIP virtual_hbond symbol unavailable"
            return result
        try:
            prepared = _derive_prepared_inputs(packet, dev)
            force_new, contacts_new, mean_distance_new = rust.compute_idp_virtual_hbond_prepared(
                donor=prepared["donor"],
                acceptor=prepared["acceptor"],
                ca=prepared["ca"],
                sc=prepared["sc"],
                disorder=prepared["disorder"],
                aromatic_mask=prepared["aromatic_mask"],
                cationic_mask=prepared["cationic_mask"],
                sticker_mask=prepared["sticker_mask"],
                nb_idx=prepared["nb_idx"],
                nb_dist=prepared["nb_dist"],
                nb_mask=prepared["nb_mask"],
                virtual_hbond_scale=prepared["virtual_hbond_scale"],
                contact_gain_scale=prepared["contact_gain_scale"],
                exposure_sensitivity=prepared["exposure_sensitivity"],
                exposure_gain_scale=prepared["exposure_gain_scale"],
                virtual_hbond_center_A=prepared["virtual_hbond_center_A"],
                virtual_hbond_width_A=prepared["virtual_hbond_width_A"],
                llps_branch=prepared["llps_branch"],
                is_llps_target=prepared["is_llps_target"],
                is_hnrn_target=prepared["is_hnrn_target"],
                is_fus_target=prepared["is_fus_target"],
                env_scale=prepared["env_scale"],
                virtual_hbond_strength=prepared["virtual_hbond_strength"],
                unsat_penalty_strength=prepared["unsat_penalty_strength"],
            )
            force_ref = ref["force"].to(device=dev)
            force_abs = torch.abs(force_new - force_ref)
            info_new = {
                "virtual_hbond_contacts": contacts_new,
                "virtual_hbond_mean_distance_A": mean_distance_new,
            }
            result.update(
                {
                    "force_max_abs_err": float(force_abs.max().item()) if force_abs.numel() else 0.0,
                    "force_mean_abs_err": float(force_abs.mean().item()) if force_abs.numel() else 0.0,
                    "contacts_abs_err": abs(_scalar_from_info(info_new, "virtual_hbond_contacts") - _scalar_from_info(info_ref, "virtual_hbond_contacts")),
                    "distance_abs_err": abs(_scalar_from_info(info_new, "virtual_hbond_mean_distance_A") - _scalar_from_info(info_ref, "virtual_hbond_mean_distance_A")),
                    "backend_reported": "rust_hip",
                }
            )
        except Exception as exc:
            result["status"] = "error"
            result["message"] = f"{type(exc).__name__}: {exc}"
        return result

    result["status"] = "unsupported"
    result["message"] = f"unknown backend: {backend}"
    return result


def _to_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# IDP Virtual HBond Parity Check",
        "",
        f"- generated_at_local: `{report['generated_at_local']}`",
        f"- packet_path: `{report['packet_path']}`",
        f"- backend: `{report['backend']}`",
        f"- device: `{report['device']}`",
        f"- pass: `{report['pass']}`",
        f"- all_supported: `{report['all_supported']}`",
        f"- max_force_abs_err: `{report['max_force_abs_err']:.8f}`",
        f"- max_contacts_abs_err: `{report['max_contacts_abs_err']:.8f}`",
        f"- max_distance_abs_err: `{report['max_distance_abs_err']:.8f}`",
        "",
        "## Packets",
        "",
    ]
    for item in report.get("results", []):
        lines.append(
            f"- `{item['target_name']}` step `{item['capture_step']}`: "
            f"status `{item.get('status', 'ok')}`, force_max `{item['force_max_abs_err']:.8f}`, contacts `{item['contacts_abs_err']:.8f}`, distance `{item['distance_abs_err']:.8f}`"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Check parity packets against the current virtual_hbond backend implementation.")
    p.add_argument("--packet-pt", required=True)
    p.add_argument("--backend", type=str, default="python")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--force-tol", type=float, default=1e-6)
    p.add_argument("--scalar-tol", type=float, default=1e-6)
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    args = p.parse_args()

    payload = torch.load(str(args.packet_pt), map_location="cpu")
    results = [check_packet(packet, device=str(args.device), backend=str(args.backend)) for packet in payload.get("packets", [])]
    all_supported = all(str(r.get("status", "ok")) == "ok" for r in results)
    max_force = max((float(r["force_max_abs_err"]) for r in results), default=0.0)
    max_contacts = max((float(r["contacts_abs_err"]) for r in results), default=0.0)
    max_distance = max((float(r["distance_abs_err"]) for r in results), default=0.0)
    report = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "packet_path": str(args.packet_pt),
        "backend": str(args.backend),
        "device": str(args.device),
        "force_tol": float(args.force_tol),
        "scalar_tol": float(args.scalar_tol),
        "all_supported": bool(all_supported),
        "max_force_abs_err": float(max_force),
        "max_contacts_abs_err": float(max_contacts),
        "max_distance_abs_err": float(max_distance),
        "pass": bool(all_supported and max_force <= float(args.force_tol) and max_contacts <= float(args.scalar_tol) and max_distance <= float(args.scalar_tol)),
        "results": results,
    }
    out_json = str(args.out_json).strip() or f"runs/idp_virtual_hbond_parity_check_{dt.date.today().isoformat()}.json"
    out_md = str(args.out_md).strip() or f"runs/idp_virtual_hbond_parity_check_{dt.date.today().isoformat()}.md"
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(out_md).write_text(_to_markdown(report), encoding="utf-8")
    print(out_json)
    print(out_md)


if __name__ == "__main__":
    main()

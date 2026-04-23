#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _to_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_bool(value: Any) -> bool:
    return bool(value)


def _sample_list(value: Any, limit: int = 3) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value[:limit]]


def summarize_geometry_probe(detail: dict[str, Any] | None) -> dict[str, Any]:
    detail = detail or {}
    canvas = detail.get("canvas3d") if isinstance(detail.get("canvas3d"), dict) else detail
    state_cells = detail.get("stateCells") if isinstance(detail.get("stateCells"), dict) else {}
    pocket = detail.get("pocket") if isinstance(detail.get("pocket"), dict) else {}

    canvas_ready = _to_bool(canvas.get("canvasReady"))
    scene_ready = _to_bool(canvas.get("sceneReady"))
    renderable_count = _to_int(canvas.get("renderableCount"))
    primitive_estimate = _to_int(canvas.get("primitiveEstimate"))
    scene_object_count = _to_int(canvas.get("sceneObjectCount"))
    state_rep_count = _to_int(state_cells.get("stateRepCount") or pocket.get("stateRepCount"))
    state_3d_rep_count = _to_int(state_cells.get("state3DRepCount") or pocket.get("state3DRepCount"))
    state_surface_rep_count = _to_int(state_cells.get("stateSurfaceRepCount") or pocket.get("stateSurfaceRepCount"))
    state_molecular_surface_rep_count = _to_int(
        state_cells.get("stateMolecularSurfaceRepCount") or pocket.get("stateMolecularSurfaceRepCount")
    )
    tracked_ref_count = _to_int(pocket.get("trackedRefCount"))
    scene_structure_count = _to_int(pocket.get("sceneStructureCount"))
    state_cell_representation_present = state_rep_count > 0 or state_3d_rep_count > 0
    surface_representation_present = state_surface_rep_count > 0 or state_molecular_surface_rep_count > 0

    status_bits = [
        "canvas ready" if canvas_ready else "canvas missing",
        f"renderables {renderable_count}",
        f"tris~{primitive_estimate}",
        f"state reps {state_rep_count}/{state_3d_rep_count}",
    ]
    if tracked_ref_count or scene_structure_count:
        status_bits.append(f"refs {tracked_ref_count}/{scene_structure_count}")
    if surface_representation_present:
        status_bits.append("surface yes")

    return {
        "canvas_ready": canvas_ready,
        "scene_ready": scene_ready,
        "renderable_count": renderable_count,
        "primitive_estimate": primitive_estimate,
        "scene_object_count": scene_object_count,
        "tracked_ref_count": tracked_ref_count,
        "scene_structure_count": scene_structure_count,
        "state_rep_count": state_rep_count,
        "state_3d_rep_count": state_3d_rep_count,
        "state_surface_rep_count": state_surface_rep_count,
        "state_molecular_surface_rep_count": state_molecular_surface_rep_count,
        "state_cell_representation_present": state_cell_representation_present,
        "surface_representation_present": surface_representation_present,
        "scene_key_sample": _sample_list(canvas.get("sceneKeySample")),
        "render_object_key_sample": _sample_list(canvas.get("renderObjectKeySample")),
        "status_line": " · ".join(status_bits),
    }


def summarize_geometry_probe_slots(detail_by_slot: dict[str, Any] | None) -> dict[str, Any]:
    detail_by_slot = detail_by_slot or {}
    return {
        str(slot): summarize_geometry_probe(detail)
        for slot, detail in detail_by_slot.items()
    }

#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _safe_int(*values: Any, default: int = 0) -> int:
    for value in values:
        try:
            if value in {"", None}:
                continue
            return int(value)
        except Exception:
            continue
    return default


def _summary_sources(summary_sources: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    return [dict(source or {}) for source in (summary_sources or []) if isinstance(source, dict)]


def _pick_summary_value(summary: dict[str, Any], summary_sources: list[dict[str, Any]], *keys: str) -> Any:
    for key in keys:
        if key in summary and summary.get(key) not in {"", None}:
            return summary.get(key)
    for source in summary_sources:
        for key in keys:
            if key in source and source.get(key) not in {"", None}:
                return source.get(key)
    return None


def _coerce_rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (payload or {}).get("rows", [])
    if not isinstance(rows, list):
        return []
    return [dict(row or {}) for row in rows if isinstance(row, dict)]


def _count_distinct_paths(*paths: Any) -> int:
    return len({str(path or "").strip() for path in paths if str(path or "").strip()})


def _path_reported(path_like: Any) -> bool:
    return bool(str(path_like or "").strip())


def resolve_selected_allatom_visual_bundle(
    payload: dict[str, Any] | None,
    *,
    summary_sources: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    summary = dict((payload or {}).get("summary", {}) or {})
    rows = _coerce_rows(payload)
    sources = _summary_sources(summary_sources)
    status = _text(_pick_summary_value(summary, sources, "status"))
    ready = status in {
        "selected_allatom_visual_bundle_ready",
        "wetlab_selected_allatom_visual_bundle_ready",
    } or bool(_pick_summary_value(summary, sources, "selected_allatom_visual_bundle_ready"))
    target_id = _text(
        _pick_summary_value(summary, sources, "target_id", "selected_allatom_visual_target_id")
    )
    assets_dir = _text(
        _pick_summary_value(
            summary,
            sources,
            "assets_dir",
            "bundle_dir",
            "selected_allatom_visual_assets_dir",
        )
    )
    primary_figure_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_figure_path",
            "metric_panel_png",
            "scatter_png",
            "selected_allatom_visual_primary_figure_path",
        )
    )
    primary_movie_script_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_movie_script_path",
            "primary_turntable_script_path",
            "hero_turntable_script_path",
            "selected_allatom_visual_primary_movie_script_path",
        )
    )
    primary_movie_mp4_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_movie_mp4_path",
            "primary_turntable_mp4_path",
            "hero_turntable_mp4_path",
            "selected_allatom_visual_primary_movie_mp4_path",
        )
    )
    dashboard_html = _text(
        _pick_summary_value(
            summary,
            sources,
            "dashboard_html",
            "selected_allatom_visual_dashboard_html",
        )
    )
    dashboard_json = _text(
        _pick_summary_value(
            summary,
            sources,
            "dashboard_json",
            "selected_allatom_visual_dashboard_json",
        )
    )
    turntable_asset_manifest_json = _text(
        _pick_summary_value(
            summary,
            sources,
            "turntable_asset_manifest_json",
            "selected_allatom_visual_turntable_asset_manifest_json",
        )
    )
    binding_event_asset_manifest_json = _text(
        _pick_summary_value(
            summary,
            sources,
            "binding_event_asset_manifest_json",
            "selected_allatom_visual_binding_event_asset_manifest_json",
        )
    )
    manifest_version = _text(
        _pick_summary_value(
            summary,
            sources,
            "visual_bundle_manifest_version",
            "selected_allatom_visual_manifest_version",
        )
    )
    topk_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "topk_count",
            "top_k",
            "candidate_count",
            "selected_allatom_visual_topk_count",
        ),
        len(rows),
        default=len(rows),
    )
    topk_requested = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "topk_requested",
            "selected_allatom_visual_topk_requested",
        ),
        topk_count,
        default=topk_count,
    )
    figure_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "figure_count",
            "selected_allatom_visual_figure_count",
        ),
        default=_count_distinct_paths(
            primary_figure_path,
            _text(summary.get("metric_panel_png")),
            _text(summary.get("scatter_png")),
        ),
    )
    movie_plan_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "movie_plan_count",
            "selected_allatom_visual_movie_plan_count",
        ),
        summary.get("candidate_count"),
        summary.get("top_k"),
        topk_count,
        default=topk_count,
    )
    binding_event_candidate_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "binding_event_candidate_count",
            "trajectory_clip_ready_count",
            "selected_allatom_visual_binding_event_candidate_count",
        ),
        default=0,
    )
    movie_script_ready_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "turntable_script_ready_count",
            "selected_allatom_visual_movie_script_ready_count",
        ),
        default=sum(1 for row in rows if bool(row.get("turntable_script_ready"))),
    )
    movie_mp4_ready_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "turntable_mp4_ready_count",
            "selected_allatom_visual_movie_mp4_ready_count",
        ),
        default=sum(1 for row in rows if bool(row.get("turntable_mp4_ready"))),
    )
    trajectory_clip_ready_count = _safe_int(
        _pick_summary_value(
            summary,
            sources,
            "trajectory_clip_ready_count",
            "selected_allatom_visual_trajectory_clip_ready_count",
        ),
        default=sum(
            1
            for row in rows
            if _text(row.get("binding_event_clip_status")) in {"trajectory_npz_available", "trajectory_available"}
        ),
    )
    hero_ligand_id = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_ligand_id",
            "selected_allatom_visual_hero_ligand_id",
        )
    )
    hero_compound_name = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_compound_name",
            "selected_allatom_visual_hero_compound_name",
        )
    )
    visual_pipeline_status = _text(
        _pick_summary_value(
            summary,
            sources,
            "visual_pipeline_status",
            "selected_allatom_visual_pipeline_status",
        )
    )
    visual_pipeline_ok = bool(
        _pick_summary_value(
            summary,
            sources,
            "visual_pipeline_ok",
            "selected_allatom_visual_pipeline_ok",
        )
    )
    primary_binding_event_clip_status = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_binding_event_clip_status",
            "selected_allatom_visual_primary_binding_event_clip_status",
        )
    )
    primary_binding_event_clip_recipe = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_binding_event_clip_recipe",
            "selected_allatom_visual_primary_binding_event_clip_recipe",
            "hero_binding_event_clip_recipe",
        )
    )
    primary_turntable_asset_status = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_turntable_asset_status",
            "selected_allatom_visual_primary_turntable_asset_status",
        )
    )
    primary_turntable_asset_recommendation = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_turntable_asset_recommendation",
            "selected_allatom_visual_primary_turntable_asset_recommendation",
        )
    )
    primary_binding_event_expected_script_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_binding_event_expected_script_path",
            "selected_allatom_visual_primary_binding_event_expected_script_path",
        )
    )
    primary_binding_event_expected_mp4_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_binding_event_expected_mp4_path",
            "selected_allatom_visual_primary_binding_event_expected_mp4_path",
        )
    )
    primary_binding_event_asset_status = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_binding_event_asset_status",
            "selected_allatom_visual_primary_binding_event_asset_status",
        )
    )
    primary_binding_event_asset_recommendation = _text(
        _pick_summary_value(
            summary,
            sources,
            "hero_binding_event_asset_recommendation",
            "selected_allatom_visual_primary_binding_event_asset_recommendation",
        )
    )
    primary_visual_polish_processed_pdb = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_visual_polish_processed_pdb",
            "selected_allatom_visual_primary_visual_polish_processed_pdb",
        )
    )
    primary_visual_polish_movie_script_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_visual_polish_movie_script_path",
            "selected_allatom_visual_primary_visual_polish_movie_script_path",
        )
    )
    primary_visual_polish_movie_mp4_path = _text(
        _pick_summary_value(
            summary,
            sources,
            "primary_visual_polish_movie_mp4_path",
            "selected_allatom_visual_primary_visual_polish_movie_mp4_path",
        )
    )
    dashboard_ready = bool(dashboard_html or dashboard_json)
    primary_figure_ready = _path_reported(primary_figure_path)
    primary_movie_script_ready = _path_reported(primary_movie_script_path)
    primary_movie_mp4_ready = _path_reported(primary_movie_mp4_path)
    availability_rollup = _joined(
        f"top-k {topk_count}" if topk_count else "top-k 0",
        f"figures {figure_count}" if figure_count else "figures 0",
        f"movie plans {movie_plan_count}" if movie_plan_count else "movie plans 0",
        (
            f"binding-event candidates {binding_event_candidate_count}"
            if binding_event_candidate_count
            else "binding-event candidates 0"
        ),
    )
    media_ready_rollup = _joined(
        f"dashboard {'ready' if dashboard_ready else 'missing'}",
        f"figure {'ready' if primary_figure_ready else 'missing'}",
        f"movie scripts {movie_script_ready_count}/{movie_plan_count or topk_count or 0}",
        f"movie mp4 {movie_mp4_ready_count}/{movie_plan_count or topk_count or 0}",
        f"binding-event clips {trajectory_clip_ready_count}/{binding_event_candidate_count or topk_count or 0}",
    )
    human_summary = _text(
        _pick_summary_value(summary, sources, "human_summary", "selected_allatom_visual_human_summary"),
        _joined(
            f"Visual bundle for {target_id}" if target_id else "",
            availability_rollup,
            media_ready_rollup,
        ),
    )
    return {
        "ready": ready,
        "status": status,
        "target_id": target_id,
        "assets_dir": assets_dir,
        "dashboard_html": dashboard_html,
        "dashboard_json": dashboard_json,
        "turntable_asset_manifest_json": turntable_asset_manifest_json,
        "binding_event_asset_manifest_json": binding_event_asset_manifest_json,
        "manifest_version": manifest_version,
        "primary_figure_path": primary_figure_path,
        "primary_movie_script_path": primary_movie_script_path,
        "primary_movie_mp4_path": primary_movie_mp4_path,
        "primary_binding_event_clip_status": primary_binding_event_clip_status,
        "primary_binding_event_clip_recipe": primary_binding_event_clip_recipe,
        "primary_turntable_asset_status": primary_turntable_asset_status,
        "primary_turntable_asset_recommendation": primary_turntable_asset_recommendation,
        "primary_binding_event_expected_script_path": primary_binding_event_expected_script_path,
        "primary_binding_event_expected_mp4_path": primary_binding_event_expected_mp4_path,
        "primary_binding_event_asset_status": primary_binding_event_asset_status,
        "primary_binding_event_asset_recommendation": primary_binding_event_asset_recommendation,
        "primary_visual_polish_processed_pdb": primary_visual_polish_processed_pdb,
        "primary_visual_polish_movie_script_path": primary_visual_polish_movie_script_path,
        "primary_visual_polish_movie_mp4_path": primary_visual_polish_movie_mp4_path,
        "figure_count": figure_count,
        "movie_plan_count": movie_plan_count,
        "binding_event_candidate_count": binding_event_candidate_count,
        "topk_count": topk_count,
        "topk_requested": topk_requested,
        "hero_ligand_id": hero_ligand_id,
        "hero_compound_name": hero_compound_name,
        "visual_pipeline_status": visual_pipeline_status,
        "visual_pipeline_ok": visual_pipeline_ok,
        "dashboard_ready": dashboard_ready,
        "primary_figure_ready": primary_figure_ready,
        "primary_movie_script_ready": primary_movie_script_ready,
        "primary_movie_mp4_ready": primary_movie_mp4_ready,
        "movie_script_ready_count": movie_script_ready_count,
        "movie_mp4_ready_count": movie_mp4_ready_count,
        "trajectory_clip_ready_count": trajectory_clip_ready_count,
        "availability_rollup": availability_rollup,
        "media_ready_rollup": media_ready_rollup,
        "human_summary": human_summary,
        "rows": rows,
    }


def selected_allatom_visual_surface_fields(visual: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_allatom_visual_bundle_ready": bool(visual.get("ready", False)),
        "selected_allatom_visual_target_id": _text(visual.get("target_id")),
        "selected_allatom_visual_assets_dir": _text(visual.get("assets_dir")),
        "selected_allatom_visual_dashboard_html": _text(visual.get("dashboard_html")),
        "selected_allatom_visual_dashboard_json": _text(visual.get("dashboard_json")),
        "selected_allatom_visual_turntable_asset_manifest_json": _text(
            visual.get("turntable_asset_manifest_json")
        ),
        "selected_allatom_visual_binding_event_asset_manifest_json": _text(
            visual.get("binding_event_asset_manifest_json")
        ),
        "selected_allatom_visual_manifest_version": _text(visual.get("manifest_version")),
        "selected_allatom_visual_primary_figure_path": _text(visual.get("primary_figure_path")),
        "selected_allatom_visual_primary_movie_script_path": _text(visual.get("primary_movie_script_path")),
        "selected_allatom_visual_primary_movie_mp4_path": _text(visual.get("primary_movie_mp4_path")),
        "selected_allatom_visual_primary_turntable_asset_status": _text(
            visual.get("primary_turntable_asset_status")
        ),
        "selected_allatom_visual_primary_turntable_asset_recommendation": _text(
            visual.get("primary_turntable_asset_recommendation")
        ),
        "selected_allatom_visual_primary_binding_event_clip_status": _text(
            visual.get("primary_binding_event_clip_status")
        ),
        "selected_allatom_visual_primary_binding_event_clip_recipe": _text(
            visual.get("primary_binding_event_clip_recipe")
        ),
        "selected_allatom_visual_primary_binding_event_expected_script_path": _text(
            visual.get("primary_binding_event_expected_script_path")
        ),
        "selected_allatom_visual_primary_binding_event_expected_mp4_path": _text(
            visual.get("primary_binding_event_expected_mp4_path")
        ),
        "selected_allatom_visual_primary_binding_event_asset_status": _text(
            visual.get("primary_binding_event_asset_status")
        ),
        "selected_allatom_visual_primary_binding_event_asset_recommendation": _text(
            visual.get("primary_binding_event_asset_recommendation")
        ),
        "selected_allatom_visual_primary_visual_polish_processed_pdb": _text(
            visual.get("primary_visual_polish_processed_pdb")
        ),
        "selected_allatom_visual_primary_visual_polish_movie_script_path": _text(
            visual.get("primary_visual_polish_movie_script_path")
        ),
        "selected_allatom_visual_primary_visual_polish_movie_mp4_path": _text(
            visual.get("primary_visual_polish_movie_mp4_path")
        ),
        "selected_allatom_visual_topk_requested": _safe_int(visual.get("topk_requested"), default=0),
        "selected_allatom_visual_topk_count": _safe_int(visual.get("topk_count"), default=0),
        "selected_allatom_visual_figure_count": _safe_int(visual.get("figure_count"), default=0),
        "selected_allatom_visual_movie_plan_count": _safe_int(visual.get("movie_plan_count"), default=0),
        "selected_allatom_visual_binding_event_candidate_count": _safe_int(
            visual.get("binding_event_candidate_count"),
            default=0,
        ),
        "selected_allatom_visual_hero_ligand_id": _text(visual.get("hero_ligand_id")),
        "selected_allatom_visual_hero_compound_name": _text(visual.get("hero_compound_name")),
        "selected_allatom_visual_pipeline_status": _text(visual.get("visual_pipeline_status")),
        "selected_allatom_visual_pipeline_ok": bool(visual.get("visual_pipeline_ok", False)),
        "selected_allatom_visual_dashboard_ready": bool(visual.get("dashboard_ready", False)),
        "selected_allatom_visual_primary_figure_ready": bool(visual.get("primary_figure_ready", False)),
        "selected_allatom_visual_primary_movie_script_ready": bool(
            visual.get("primary_movie_script_ready", False)
        ),
        "selected_allatom_visual_primary_movie_mp4_ready": bool(
            visual.get("primary_movie_mp4_ready", False)
        ),
        "selected_allatom_visual_movie_script_ready_count": _safe_int(
            visual.get("movie_script_ready_count"),
            default=0,
        ),
        "selected_allatom_visual_movie_mp4_ready_count": _safe_int(
            visual.get("movie_mp4_ready_count"),
            default=0,
        ),
        "selected_allatom_visual_trajectory_clip_ready_count": _safe_int(
            visual.get("trajectory_clip_ready_count"),
            default=0,
        ),
        "selected_allatom_visual_availability_rollup": _text(visual.get("availability_rollup")),
        "selected_allatom_visual_media_ready_rollup": _text(visual.get("media_ready_rollup")),
        "selected_allatom_visual_human_summary": _text(visual.get("human_summary")),
    }

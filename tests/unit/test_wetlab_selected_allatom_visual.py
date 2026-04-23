from __future__ import annotations

from tools.wetlab_selected_allatom_visual import (
    resolve_selected_allatom_visual_bundle,
    selected_allatom_visual_surface_fields,
)


def test_resolve_selected_allatom_visual_bundle_supports_current_bundle_contract() -> None:
    payload = {
        "summary": {
            "status": "selected_allatom_visual_bundle_ready",
            "target_id": "T. cruzi PDE",
            "assets_dir": "/tmp/visuals",
            "dashboard_html": "/tmp/visuals/dashboard.html",
            "primary_figure_path": "/tmp/visuals/hero.png",
            "primary_movie_script_path": "/tmp/visuals/hero.cxc",
            "primary_movie_mp4_path": "/tmp/visuals/hero.mp4",
            "topk_count": 4,
            "figure_count": 2,
            "movie_plan_count": 4,
            "binding_event_candidate_count": 3,
            "human_summary": "Selected all-atom visual bundle for T. cruzi PDE.",
        }
    }

    visual = resolve_selected_allatom_visual_bundle(payload)
    fields = selected_allatom_visual_surface_fields(visual)

    assert visual["ready"] is True
    assert visual["availability_rollup"] == "top-k 4 | figures 2 | movie plans 4 | binding-event candidates 3"
    assert visual["media_ready_rollup"] == (
        "dashboard ready | figure ready | movie scripts 0/4 | movie mp4 0/4 | binding-event clips 0/3"
    )
    assert fields["selected_allatom_visual_primary_movie_mp4_ready"] is True
    assert fields["selected_allatom_visual_human_summary"] == "Selected all-atom visual bundle for T. cruzi PDE."


def test_resolve_selected_allatom_visual_bundle_falls_back_to_downstream_summary_sources() -> None:
    visual = resolve_selected_allatom_visual_bundle(
        None,
        summary_sources=[
            {
                "selected_allatom_visual_bundle_ready": True,
                "selected_allatom_visual_target_id": "Cathepsin K",
                "selected_allatom_visual_topk_count": 2,
                "selected_allatom_visual_figure_count": 1,
                "selected_allatom_visual_movie_plan_count": 2,
                "selected_allatom_visual_binding_event_candidate_count": 1,
                "selected_allatom_visual_dashboard_html": "/tmp/cathepsin/dashboard.html",
                "selected_allatom_visual_primary_figure_path": "/tmp/cathepsin/hero.png",
                "selected_allatom_visual_human_summary": "Cathepsin K visual rollup.",
            }
        ],
    )

    fields = selected_allatom_visual_surface_fields(visual)

    assert visual["ready"] is True
    assert visual["target_id"] == "Cathepsin K"
    assert visual["availability_rollup"] == "top-k 2 | figures 1 | movie plans 2 | binding-event candidates 1"
    assert fields["selected_allatom_visual_dashboard_ready"] is True
    assert fields["selected_allatom_visual_primary_figure_ready"] is True
    assert fields["selected_allatom_visual_human_summary"] == "Cathepsin K visual rollup."

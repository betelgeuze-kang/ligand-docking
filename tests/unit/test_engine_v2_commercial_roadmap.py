from pathlib import Path


def test_current_main_commercial_roadmap_tracks_v2_1_without_promotion() -> None:
    roadmap = Path("docs/independent_engine_v2_commercial_roadmap.ko.md").read_text(
        encoding="utf-8"
    )

    assert "current-main canonical planning reference" in roadmap
    assert "v2_bounded_mmcif_nonpoly_component_declarations" in roadmap
    assert "v2_bounded_mmcif_struct_conn_declarations" in roadmap
    assert "v2_bounded_mmcif_nonpoly_atom_site_observations" in roadmap
    assert "v2_bounded_mmcif_nonpoly_coordinate_values" in roadmap
    assert "finite binary64" in roadmap
    assert "exact bit pattern" in roadmap
    assert "atom_site_identity_joined" in roadmap
    assert "connection type·symmetry·order·covalence·coordination·topology" in roadmap
    assert "scientifically_validated" in roadmap
    assert "commercial_readiness" in roadmap
    assert "현재 상태는 위 종료 기준을 충족하지 않는다" in roadmap

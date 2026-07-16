from pathlib import Path


def test_current_main_commercial_roadmap_tracks_v2_1_without_promotion() -> None:
    roadmap = Path("docs/independent_engine_v2_commercial_roadmap.ko.md").read_text(
        encoding="utf-8"
    )

    assert "current-main canonical planning reference" in roadmap
    assert "v2_bounded_mmcif_nonpoly_component_declarations" in roadmap
    assert "v2_bounded_mmcif_nonpoly_component_roles" in roadmap
    assert "v2_bounded_mmcif_atom_site_model_policy" in roadmap
    assert "v2_bounded_mmcif_biological_assembly_policy" in roadmap
    assert "v2_bounded_mmcif_missing_atom_residue_policy" in roadmap
    assert "v2_bounded_mmcif_modified_residue_declarations" in roadmap
    assert "v2_bounded_mmcif_struct_conn_declarations" in roadmap
    assert "v2_bounded_mmcif_nonpoly_atom_site_observations" in roadmap
    assert "v2_bounded_mmcif_nonpoly_coordinate_values" in roadmap
    assert "v2_bounded_mmcif_nonpoly_atom_site_scalar_values" in roadmap
    assert "v2_bounded_mmcif_nonpoly_canonical_topology" in roadmap
    assert "v2_bounded_mmcif_nonpoly_neutral_coh_preparation" in roadmap
    assert "v2_bounded_mmcif_nonpoly_preparation_corpus" in roadmap
    assert "finite binary64" in roadmap
    assert "exact bit pattern" in roadmap
    assert "known/unknown/not-applicable" in roadmap
    assert "coordination edge" in roadmap
    assert "neutral acyclic C/O/H" in roadmap
    assert "parameterable=false" in roadmap
    assert "exact ASCII 30-case" in roadmap
    assert "51-axis coverage ledger" in roadmap
    assert "7개 `not_implemented`" in roadmap
    assert (
        "일반 nonpoly component를\nligand·cofactor·modified residue로 추정하지 않는다"
        in roadmap
    )
    assert "preparation과 parameterization은 명시적으로 미지원" in roadmap
    assert "`_pdbx_struct_mod_residue` category" in roadmap
    assert "atom-site\nobservation, parent chemistry" in roadmap
    assert "model set이 정확히 `{1}`" in roadmap
    assert "첫 model로 자동 선택하지 않고 명시적으로" in roadmap
    assert "deposited asymmetric unit이\nbiologically relevant assembly라는 증거" in roadmap
    assert "matrix/vector 값과 composition order를 해석하거나 좌표를 확장하지" in roadmap
    assert "0=`zero_occupancy`, 1=`unobserved`" in roadmap
    assert "그 부재가 구조가 완전하거나 missing atom/residue가 없다는 증거는" in roadmap
    assert "source-declared zero-occupancy 또는 unobserved atom/residue" in roadmap
    assert "explicit `label_alt_id` 입력" in roadmap
    assert "chemistry preparation 전에 fail-closed" in roadmap
    assert "known insertion code의 scheme·atom-site·connection exact identity" in roadmap
    assert "polymer insertion/deletion" in roadmap
    assert "cofactor 역할을 추정하지 않는 명시적 미지원 경계" in roadmap
    assert "cofactor가 아니라고 판정하는 것이 아니다" in roadmap
    assert "parameter_fitting_allowed=false" in roadmap
    assert "v2_1_exit_ready=false" in roadmap
    assert "atom_site_identity_joined" in roadmap
    assert "connection type·symmetry·order·covalence·coordination·topology" in roadmap
    assert "scientifically_validated" in roadmap
    assert "commercial_readiness" in roadmap
    assert "현재 상태는 위 종료 기준을 충족하지 않는다" in roadmap

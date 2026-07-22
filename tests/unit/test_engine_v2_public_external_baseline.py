from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.external_baseline import ExternalBaselineEngine
from betelgeuze_engine_v2.benchmark.public_external_baseline import (
    PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM,
    PublicExternalBaselineError,
    PublicExternalPreparationTool,
    PublicExternalPreparedArtifact,
    PublicExternalPreparedCase,
    build_public_external_baseline_work_order_bundle,
    public_external_baseline_pocket_definition,
)
from betelgeuze_engine_v2.benchmark.public_protocol import (
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkArtifact,
    PublicBenchmarkCaseDefinition,
)
from betelgeuze_engine_v2.benchmark.public_suite_materialization import (
    materialize_public_benchmark_input_suite,
)


_VALID_SDF = b"""one-carbon
unit-test

  1  0  0  0  0  0            999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
M  END
$$$$
"""


def _artifact(
    pdb_id: str,
    role: str,
    filename: str,
    source: bytes,
) -> PublicBenchmarkArtifact:
    relative_path = f"posebusters/datasets/pdb/{pdb_id}/{pdb_id}_{filename}"
    return PublicBenchmarkArtifact(
        role=role,
        relative_path=relative_path,
        immutable_url=(
            "https://raw.githubusercontent.com/maabuu/posebusters/"
            f"{POSEBUSTERS_SOURCE_COMMIT_SHA}/{relative_path}"
        ),
        sha256=hashlib.sha256(source).hexdigest(),
        size_bytes=len(source),
        media_type=(
            "chemical/x-pdb" if role == "receptor" else "chemical/x-mdl-sdfile"
        ),
    )


def _protocol_and_sources() -> tuple[
    FrozenPublicBenchmarkProtocol,
    dict[str, bytes],
]:
    cases: list[PublicBenchmarkCaseDefinition] = []
    sources: dict[str, bytes] = {}
    for pdb_id in ("1abc", "2abc", "3abc", "4abc"):
        receptor = f"HEADER {pdb_id}\n".encode("ascii")
        artifacts = (
            _artifact(pdb_id, "receptor", "protein_one_lig_removed.pdb", receptor),
            _artifact(pdb_id, "reference_ligands", "ligands.sdf", _VALID_SDF),
            _artifact(pdb_id, "ligand_identity_seed", "ligand.sdf", _VALID_SDF),
        )
        cases.append(
            PublicBenchmarkCaseDefinition(
                case_id=f"posebusters-packaged-{pdb_id}",
                pdb_id=pdb_id,
                receptor=artifacts[0],
                reference_ligands=artifacts[1],
                ligand_identity_seed=artifacts[2],
            )
        )
        for artifact, source in zip(
            artifacts,
            (receptor, _VALID_SDF, _VALID_SDF),
            strict=True,
        ):
            sources[artifact.relative_path] = source
    return FrozenPublicBenchmarkProtocol(cases=tuple(cases), scorer_identities=()), sources


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _engines() -> tuple[ExternalBaselineEngine, ...]:
    return tuple(
        ExternalBaselineEngine(
            engine_id=engine_id,
            engine_version=version,
            executable_sha256=_sha(f"{engine_id}-executable"),
            container_image_digest=f"sha256:{_sha(f'{engine_id}-container')}",
        )
        for engine_id, version in (
            ("vina", "1.2.7"),
            ("gnina", "1.3.2"),
            ("smina", "2020.12.10"),
        )
    )


def _prepared_cases(
    protocol: FrozenPublicBenchmarkProtocol,
    suite,
    root: Path,
) -> tuple[PublicExternalPreparedCase, ...]:
    tool = PublicExternalPreparationTool(
        tool_id="reviewed-pdbqt-preparer",
        tool_version="1.0.0",
        executable_sha256=_sha("preparer-executable"),
        configuration_sha256=_sha("preparer-config"),
        container_image_digest=f"sha256:{_sha('preparer-container')}",
    )
    suite_rows = {row.case_id: row for row in suite.case_rows}
    prepared: list[PublicExternalPreparedCase] = []
    for case in protocol.cases:
        receptor_source = f"REMARK receptor {case.pdb_id}\n".encode("ascii")
        ligand_source = f"REMARK ligand {case.pdb_id}\n".encode("ascii")
        receptor_path = f"prepared/{case.pdb_id}/receptor.pdbqt"
        ligand_path = f"prepared/{case.pdb_id}/ligand.pdbqt"
        for relative_path, source in (
            (receptor_path, receptor_source),
            (ligand_path, ligand_source),
        ):
            output = root / relative_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(source)
        center, pocket_sha256 = public_external_baseline_pocket_definition(
            case,
            suite_rows[case.case_id],
        )
        prepared.append(
            PublicExternalPreparedCase(
                case_id=case.case_id,
                target_id=case.pdb_id,
                receptor=PublicExternalPreparedArtifact(
                    role="prepared_receptor_pdbqt",
                    relative_path=receptor_path,
                    sha256=hashlib.sha256(receptor_source).hexdigest(),
                    size_bytes=len(receptor_source),
                    source_artifact_sha256=case.receptor.sha256,
                    preparation_tool=tool,
                ),
                ligand=PublicExternalPreparedArtifact(
                    role="prepared_ligand_pdbqt",
                    relative_path=ligand_path,
                    sha256=hashlib.sha256(ligand_source).hexdigest(),
                    size_bytes=len(ligand_source),
                    source_artifact_sha256=case.ligand_identity_seed.sha256,
                    preparation_tool=tool,
                ),
                pocket_center_receptor_frame_angstrom=center,
                pocket_definition_sha256=pocket_sha256,
            )
        )
    return tuple(prepared)


def _inputs(tmp_path: Path):
    protocol, sources = _protocol_and_sources()
    suite = materialize_public_benchmark_input_suite(protocol, sources)
    prepared = _prepared_cases(protocol, suite, tmp_path)
    return protocol, suite, prepared


def test_same_prepared_inputs_create_three_nonexecuting_work_orders(
    tmp_path: Path,
) -> None:
    protocol, suite, prepared = _inputs(tmp_path)

    bundle = build_public_external_baseline_work_order_bundle(
        protocol,
        suite,
        prepared,
        _engines(),
        artifact_root=tmp_path,
    )

    payload = bundle.to_dict()
    assert bundle.prepared_input_ready
    assert payload["status"] == "ready_for_offline_operator_execution"
    assert payload["prepared_input_verified_case_count"] == 4
    assert payload["case_count"] == 4
    assert payload["engine_count"] == 3
    assert payload["work_order_count"] == 3
    assert payload["same_prepared_input_identity_across_engines"] is True
    assert payload["all_case_denominator_retained"] is True
    assert payload["external_engine_launched"] is False
    assert payload["results_present"] is False
    assert payload["claim_safe"] is False
    receptor_vectors = [
        tuple(case.receptor_sha256 for case in order.cases)
        for order in bundle.work_orders
    ]
    ligand_vectors = [
        tuple(case.ligand_sha256 for case in order.cases)
        for order in bundle.work_orders
    ]
    assert len(set(receptor_vectors)) == 1
    assert len(set(ligand_vectors)) == 1
    assert {order.engine.engine_id for order in bundle.work_orders} == {
        "vina",
        "gnina",
        "smina",
    }
    for order in bundle.work_orders:
        command = set(order.command_template)
        assert {
            "{receptor_path}",
            "{ligand_path}",
            "{center_x}",
            "{center_y}",
            "{center_z}",
            "{size_x}",
            "{size_y}",
            "{size_z}",
            "{seed}",
            "{exhaustiveness}",
            "{num_modes}",
            "{cpu_count}",
            "{output_path}",
        } <= command
        assert all(
            case.metadata["box_size_angstrom"]
            == PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM
            and case.metadata["ligand_identity_seed_coordinates_used"] is False
            for case in order.cases
        )
    gnina = next(
        order for order in bundle.work_orders if order.engine.engine_id == "gnina"
    )
    assert gnina.score_semantics == "gnina_default_cnnscore"
    assert gnina.score_direction == "maximize"
    assert "--no_gpu" in gnina.command_template


def test_missing_prepared_artifact_retains_all_four_rows_and_blocks_orders(
    tmp_path: Path,
) -> None:
    protocol, suite, prepared = _inputs(tmp_path)
    (tmp_path / prepared[1].ligand.relative_path).unlink()

    bundle = build_public_external_baseline_work_order_bundle(
        protocol,
        suite,
        prepared,
        _engines(),
        artifact_root=tmp_path,
    )

    assert not bundle.prepared_input_ready
    assert len(bundle.case_rows) == 4
    assert bundle.work_orders == ()
    assert bundle.to_dict()["status"] == "blocked_prepared_input_verification"
    assert bundle.case_rows[1].error_codes == (
        "prepared_ligand_artifact_verification_failed",
    )
    assert sum(row.ready for row in bundle.case_rows) == 3


def test_source_pocket_and_native_pose_leak_crosswires_fail_closed(
    tmp_path: Path,
) -> None:
    protocol, suite, prepared = _inputs(tmp_path)

    with pytest.raises(PublicExternalBaselineError, match="source or pocket"):
        build_public_external_baseline_work_order_bundle(
            protocol,
            suite,
            (replace(prepared[0], pocket_definition_sha256="0" * 64), *prepared[1:]),
            _engines(),
            artifact_root=tmp_path,
        )
    with pytest.raises(PublicExternalBaselineError, match="source or pocket"):
        build_public_external_baseline_work_order_bundle(
            protocol,
            suite,
            (replace(prepared[0], target_id="cross-wired"), *prepared[1:]),
            _engines(),
            artifact_root=tmp_path,
        )
    with pytest.raises(PublicExternalBaselineError, match="no-native-pose-leak"):
        replace(prepared[0], ligand_identity_seed_coordinates_used=True)
    with pytest.raises(PublicExternalBaselineError, match="22.5-A cube"):
        replace(prepared[0], box_size_angstrom=(30.0, 30.0, 30.0))


def test_bundle_rejects_work_order_input_and_score_crosswires(tmp_path: Path) -> None:
    protocol, suite, prepared = _inputs(tmp_path)
    bundle = build_public_external_baseline_work_order_bundle(
        protocol,
        suite,
        prepared,
        _engines(),
        artifact_root=tmp_path,
    )
    first_order = bundle.work_orders[0]
    cross_wired_case = replace(
        first_order.cases[0],
        receptor_sha256=_sha("cross-wired-receptor"),
    )
    cross_wired_order = replace(
        first_order,
        cases=(cross_wired_case, *first_order.cases[1:]),
    )

    with pytest.raises(PublicExternalBaselineError, match="disagree"):
        replace(
            bundle,
            work_orders=(cross_wired_order, *bundle.work_orders[1:]),
        )
    with pytest.raises(PublicExternalBaselineError, match="disagree"):
        replace(
            bundle,
            work_orders=(
                replace(first_order, score_direction="minimize"),
                *bundle.work_orders[1:],
            ),
        )


def test_bundle_writer_is_mode_0600_and_refuses_overwrite(tmp_path: Path) -> None:
    protocol, suite, prepared = _inputs(tmp_path)
    bundle = build_public_external_baseline_work_order_bundle(
        protocol,
        suite,
        prepared,
        _engines(),
        artifact_root=tmp_path,
    )
    output = bundle.write_json(tmp_path / "work-orders.json")

    assert os.stat(output).st_mode & 0o777 == 0o600
    assert output.read_bytes().endswith(b"\n")
    with pytest.raises(PublicExternalBaselineError, match="already exists"):
        bundle.write_json(output)

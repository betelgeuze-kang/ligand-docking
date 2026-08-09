from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    canonical_system_json_bytes,
    canonical_system_sha256,
)
from betelgeuze_engine_v2.cli import (  # noqa: E402
    EngineV2CliError,
    _sha256_document,
)
from betelgeuze_engine_v2.standalone_cli import (  # noqa: E402
    LIGAND_MANIFEST_SCHEMA_ID,
    StandaloneDockCliError,
    define_explicit_pocket,
    dock,
    main,
    prepare_ligands,
    prepare_receptor,
    report_pipeline_result,
    verify_pipeline_result,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-cli-fixture",
        parser_version="1.0.0",
    )


def _system(*, receptor: bool) -> AllAtomSystem:
    elements = ("O", "N", "H", "C", "H") if receptor else ("C", "N", "H", "O", "H")
    charges = (-0.4, -0.2, 0.2, 0.0, 0.4) if receptor else (0.0, -0.2, 0.2, -0.4, 0.4)
    coordinates = (
        ([2.0, 0.0, 0.0], [3.0, 3.0, 0.0], [2.5, 2.5, 0.0], [-2.0, 3.0, 0.0], [6.0, 6.0, 0.0])
        if receptor
        else ([-2.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [-2.0, 0.0, 0.0], [-3.0, 0.0, 0.0])
    )
    role = "receptor" if receptor else "ligand"
    return AllAtomSystem(
        system_id=f"standalone-cli-{role}",
        atoms=tuple(
            Atom(
                index=index,
                name=f"{role[0].upper()}{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(Bond(index=0, atom_i=1, atom_j=2),)
        if receptor
        else (
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=1, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
            Bond(index=3, atom_i=3, atom_j=4),
        ),
        residues=(
            Residue(
                index=0,
                name="REC" if receptor else "LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
                entity_type="polymer" if receptor else "non-polymer",
                hetero=not receptor,
            ),
        ),
        chains=(Chain(index=0, chain_id="A" if receptor else "L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(role, ("b" if receptor else "a") * 64),
    )


def _write_system(path: Path, system: AllAtomSystem) -> None:
    path.write_bytes(canonical_system_json_bytes(system) + b"\n")


def _write_document(path: Path, document: dict[str, object]) -> None:
    path.write_text(
        json.dumps(document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="ascii",
    )


def _rehash_result(document: dict[str, object]) -> None:
    projection = dict(document)
    projection.pop("request")
    projection.pop("profile")
    projection.pop("receipt_sha256")
    document["receipt_sha256"] = _sha256_document(projection)


def _synthetic_result(
    tmp_path: Path,
    *,
    candidate_count: int = 8,
    top_k: int = 5,
) -> dict[str, object]:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)
    return dock(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        seed=4301,
        synthetic_candidate_count=candidate_count,
        synthetic_top_k=top_k,
        synthetic_acknowledged=True,
    )


def test_prepare_commands_only_admit_canonical_prepared_systems(tmp_path: Path) -> None:
    receptor = _system(receptor=True)
    ligand = _system(receptor=False)
    receptor_input = tmp_path / "receptor.json"
    ligand_input = tmp_path / "ligand.json"
    _write_system(receptor_input, receptor)
    _write_system(ligand_input, ligand)

    receipt = prepare_receptor(receptor_input, tmp_path / "prepared-receptor.json")
    manifest = prepare_ligands(
        [ligand_input],
        tmp_path / "ligands",
    )

    assert receipt["system_sha256"] == canonical_system_sha256(receptor)
    assert manifest["schema_id"] == LIGAND_MANIFEST_SCHEMA_ID
    assert manifest["system_count"] == 1
    assert manifest["manifest_filename"] == "manifest.json"
    assert manifest["bundle_absent_only"] is True
    assert manifest["chemistry_inference_performed"] is False
    bundle = tmp_path / "ligands"
    ligand_file = bundle / f"{canonical_system_sha256(ligand)}.json"
    assert ligand_file.is_file()
    assert (bundle / "manifest.json").is_file()
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o700
    assert stat.S_IMODE(ligand_file.stat().st_mode) == 0o600
    assert stat.S_IMODE((bundle / "manifest.json").stat().st_mode) == 0o600


def test_synthetic_cli_flow_is_verifiable_reportable_and_claim_blocked(tmp_path: Path) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)

    result = dock(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        seed=4301,
        synthetic_candidate_count=2,
        synthetic_top_k=1,
        synthetic_acknowledged=True,
    )
    verification = verify_pipeline_result(result)
    repeated_verification = verify_pipeline_result(result)
    report = report_pipeline_result(result)
    repeated_report = report_pipeline_result(result)

    assert "valid" not in verification
    assert verification["structural_consistency_valid"] is True
    assert verification == repeated_verification
    assert report == repeated_report
    assert verification["status"] == "verified_structural_consistency_only"
    assert verification["structural_consistency_verified"] is True
    assert verification["content_authenticity_verified"] is False
    assert verification["cryptographic_signature_verified"] is False
    assert verification["external_authority_verified"] is False
    assert verification["execution_authority_granted"] is False
    assert verification["claim_safe"] is False
    assert result["candidate_count"] == 2
    assert result["external_reservation_requested"] is False
    assert result["product_execution_authorized"] is False
    assert report["customer_pose_emission_authorized"] is False
    assert report["public_or_scientific_claim_authorized"] is False
    assert report["status"] == "structural_report_only"
    assert report["content_authenticity_verified"] is False


def test_small_denominator_requires_explicit_synthetic_acknowledgement(tmp_path: Path) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)

    with pytest.raises(StandaloneDockCliError, match="--test-only-synthetic"):
        dock(
            receptor_path=receptor_path,
            ligand_path=ligand_path,
            pocket_path=pocket_path,
            seed=4301,
            synthetic_candidate_count=2,
        )
    with pytest.raises(
        StandaloneDockCliError,
        match="synthetic test flags require --synthetic-test-candidates",
    ):
        dock(
            receptor_path=receptor_path,
            ligand_path=ligand_path,
            pocket_path=pocket_path,
            seed=4301,
            synthetic_top_k=1,
        )
    with pytest.raises(
        StandaloneDockCliError,
        match="synthetic test flags require --synthetic-test-candidates",
    ):
        dock(
            receptor_path=receptor_path,
            ligand_path=ligand_path,
            pocket_path=pocket_path,
            seed=4301,
            synthetic_acknowledged=True,
        )


def test_verifier_rejects_authority_escalation(tmp_path: Path) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)
    result = dock(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        seed=7,
        synthetic_candidate_count=1,
        synthetic_top_k=1,
        synthetic_acknowledged=True,
    )
    result["product_execution_authorized"] = True

    with pytest.raises(StandaloneDockCliError, match="receipt_sha256 mismatch"):
        verify_pipeline_result(result)


def test_ligand_bundle_is_absent_only_and_failure_atomic(tmp_path: Path) -> None:
    ligand_input = tmp_path / "ligand.json"
    invalid_input = tmp_path / "invalid.json"
    _write_system(ligand_input, _system(receptor=False))
    invalid_input.write_bytes(b"{}\n")
    bundle = tmp_path / "bundle"

    with pytest.raises(StandaloneDockCliError, match="canonical system is invalid"):
        prepare_ligands([ligand_input, invalid_input], bundle)

    assert not bundle.exists()
    assert list(tmp_path.glob(".bundle.staging-*")) == []

    prepare_ligands([ligand_input], bundle)
    with pytest.raises(EngineV2CliError, match="must be absent"):
        prepare_ligands([ligand_input], bundle)
    assert list(tmp_path.glob(".bundle.staging-*")) == []


def test_hardened_writer_rejects_parent_symlinks_special_files_and_aliases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "receptor.json"
    original = canonical_system_json_bytes(_system(receptor=True)) + b"\n"
    source.write_bytes(original)

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    symlink_parent = tmp_path / "symlink-parent"
    symlink_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(EngineV2CliError, match="parent traversal"):
        prepare_receptor(source, symlink_parent / "output.json")
    assert not (real_parent / "output.json").exists()

    for kind in ("symlink", "hardlink", "fifo"):
        output = tmp_path / f"{kind}-output"
        if kind == "symlink":
            target = tmp_path / "symlink-target"
            target.write_bytes(b"target\n")
            output.symlink_to(target)
        elif kind == "hardlink":
            target = tmp_path / "hardlink-target"
            target.write_bytes(b"target\n")
            os.link(target, output)
        else:
            os.mkfifo(output)
        with pytest.raises(EngineV2CliError, match="single-link regular file"):
            prepare_receptor(source, output, overwrite=True)

    with pytest.raises(EngineV2CliError, match="must not alias"):
        prepare_receptor(source, source, overwrite=True)
    assert source.read_bytes() == original


def test_hardened_writer_detects_overwrite_toctou_without_clobbering_racer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.cli as cli_module

    source = tmp_path / "receptor.json"
    output = tmp_path / "output.json"
    _write_system(source, _system(receptor=True))
    output.write_bytes(b"original\n")
    original_rename = cli_module._renameat2
    raced = False

    def racing_rename(
        source_directory: int,
        source_name: str,
        destination_directory: int,
        destination_name: str,
        *,
        flags: int,
    ) -> None:
        nonlocal raced
        if not raced:
            raced = True
            os.unlink(destination_name, dir_fd=destination_directory)
            descriptor = os.open(
                destination_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=destination_directory,
            )
            try:
                os.write(descriptor, b"racer\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original_rename(
            source_directory,
            source_name,
            destination_directory,
            destination_name,
            flags=flags,
        )

    monkeypatch.setattr(cli_module, "_renameat2", racing_rename)
    with pytest.raises(EngineV2CliError, match="identity changed"):
        prepare_receptor(source, output, overwrite=True)

    assert output.read_bytes() == b"racer\n"
    assert list(tmp_path.glob(".output.json.tmp-*")) == []


def test_hardened_writer_rolls_back_temporary_source_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.cli as cli_module

    source = tmp_path / "receptor.json"
    output = tmp_path / "output.json"
    _write_system(source, _system(receptor=True))
    output.write_bytes(b"original\n")
    original_rename = cli_module._renameat2
    raced = False

    def racing_rename(
        source_directory: int,
        source_name: str,
        destination_directory: int,
        destination_name: str,
        *,
        flags: int,
    ) -> None:
        nonlocal raced
        if not raced:
            raced = True
            os.unlink(source_name, dir_fd=source_directory)
            descriptor = os.open(
                source_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=source_directory,
            )
            try:
                os.write(descriptor, b"attacker-source\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        original_rename(
            source_directory,
            source_name,
            destination_directory,
            destination_name,
            flags=flags,
        )

    monkeypatch.setattr(cli_module, "_renameat2", racing_rename)
    with pytest.raises(EngineV2CliError, match="identity changed"):
        prepare_receptor(source, output, overwrite=True)

    assert output.read_bytes() == b"original\n"
    leftovers = list(tmp_path.glob(".output.json.tmp-*"))
    assert len(leftovers) == 1
    assert leftovers[0].read_bytes() == b"attacker-source\n"


def test_hardened_writer_removes_absent_publish_that_fails_postcheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.cli as cli_module

    source = tmp_path / "receptor.json"
    output = tmp_path / "output.json"
    _write_system(source, _system(receptor=True))
    original_contains = cli_module._descriptor_contains
    calls = 0

    def fail_second_check(descriptor: int, expected: bytes) -> bool:
        nonlocal calls
        calls += 1
        if calls == 2:
            return False
        return original_contains(descriptor, expected)

    monkeypatch.setattr(cli_module, "_descriptor_contains", fail_second_check)
    with pytest.raises(EngineV2CliError, match="published output identity"):
        prepare_receptor(source, output)

    assert not output.exists()
    assert list(tmp_path.glob(".output.json.tmp-*")) == []


def test_ligand_bundle_rejects_staging_source_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.cli as cli_module

    ligand = tmp_path / "ligand.json"
    bundle = tmp_path / "bundle"
    _write_system(ligand, _system(receptor=False))
    original_rename = cli_module._renameat2
    raced = False

    def racing_rename(
        source_directory: int,
        source_name: str,
        destination_directory: int,
        destination_name: str,
        *,
        flags: int,
    ) -> None:
        nonlocal raced
        if not raced:
            raced = True
            os.rename(
                source_name,
                ".bundle-original-hidden",
                src_dir_fd=source_directory,
                dst_dir_fd=source_directory,
            )
            os.mkdir(source_name, 0o700, dir_fd=source_directory)
            attacker_directory = os.open(
                source_name,
                os.O_RDONLY | os.O_DIRECTORY,
                dir_fd=source_directory,
            )
            try:
                descriptor = os.open(
                    "attacker.json",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=attacker_directory,
                )
                try:
                    os.write(descriptor, b"attacker\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            finally:
                os.close(attacker_directory)
        original_rename(
            source_directory,
            source_name,
            destination_directory,
            destination_name,
            flags=flags,
        )

    monkeypatch.setattr(cli_module, "_renameat2", racing_rename)
    with pytest.raises(EngineV2CliError, match="published bundle identity"):
        prepare_ligands([ligand], bundle)

    assert not bundle.exists()


def test_argument_errors_are_one_canonical_failure_document(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    ligand = tmp_path / "ligand.json"
    _write_system(ligand, _system(receptor=False))

    status = main(
        [
            "prepare-ligands",
            "--input",
            str(ligand),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--manifest",
            str(tmp_path / "legacy-manifest.json"),
        ]
    )

    captured = capfd.readouterr()
    assert status == 2
    assert captured.out == ""
    assert "usage:" not in captured.err
    lines = captured.err.splitlines()
    assert len(lines) == 1
    failure = json.loads(lines[0])
    assert failure["status"] == "failure"
    assert failure["error_code"] == "engine_v2_cli_failed"
    assert failure["claim_safe"] is False
    assert lines[0] == json.dumps(
        failure,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert not (tmp_path / "bundle").exists()


def test_verifier_rejects_exact_schema_derived_rank_and_term_cross_wires(
    tmp_path: Path,
) -> None:
    result = _synthetic_result(tmp_path)

    extra_key = copy.deepcopy(result)
    extra_key["unexpected"] = False
    with pytest.raises(StandaloneDockCliError, match="exact schema"):
        verify_pipeline_result(extra_key)

    bad_count = copy.deepcopy(result)
    bad_count["success_count"] = int(bad_count["success_count"]) - 1
    _rehash_result(bad_count)
    with pytest.raises(StandaloneDockCliError, match="success/failure counts"):
        verify_pipeline_result(bad_count)
    with pytest.raises(StandaloneDockCliError, match="success/failure counts"):
        report_pipeline_result(bad_count)

    bad_rank = copy.deepcopy(result)
    bad_rank["top_proposal_indices"] = list(bad_rank["top_proposal_indices"])[1:]
    bad_rank["abstained"] = True
    _rehash_result(bad_rank)
    with pytest.raises(StandaloneDockCliError, match="complete stable rank"):
        verify_pipeline_result(bad_rank)

    bad_terms = copy.deepcopy(result)
    candidate = next(
        row
        for row in bad_terms["candidate_evidence"]
        if row["status"] == "success"
    )
    terms = candidate["scorer_terms"]
    terms["proposal_fingerprint_sha256"] = "0" * 64
    terms_projection = dict(terms)
    terms_projection.pop("receipt_sha256")
    terms["receipt_sha256"] = _sha256_document(terms_projection)
    _rehash_result(bad_terms)
    with pytest.raises(StandaloneDockCliError, match="proposal cross-binding"):
        verify_pipeline_result(bad_terms)


def test_verifier_rejects_rehashed_authority_escalation(tmp_path: Path) -> None:
    result = _synthetic_result(tmp_path, candidate_count=2, top_k=1)
    result["product_execution_authorized"] = True
    _rehash_result(result)

    with pytest.raises(StandaloneDockCliError, match="forbidden authority"):
        verify_pipeline_result(result)


def test_verifier_admits_failure_rows_without_dropping_the_denominator(
    tmp_path: Path,
) -> None:
    result = _synthetic_result(tmp_path)
    candidate = result["candidate_evidence"][0]
    assert candidate["selection_eligible"] is False
    candidate["status"] = "failure"
    candidate["result_proposal_fingerprint_sha256"] = ""
    candidate["score_binary64_hex"] = None
    candidate["pose_validity"] = None
    candidate["scorer_terms"] = None
    candidate["error_code"] = "synthetic_failure_row"
    result["success_count"] = int(result["success_count"]) - 1
    result["failure_count"] = int(result["failure_count"]) + 1
    _rehash_result(result)

    verification = verify_pipeline_result(result)

    assert verification["candidate_count"] == 8
    assert verification["success_count"] == 7
    assert verification["failure_count"] == 1


def test_verifier_rejects_boolean_counts_indices_and_component_rebinding(
    tmp_path: Path,
) -> None:
    result = _synthetic_result(tmp_path, candidate_count=2, top_k=1)

    boolean_count = copy.deepcopy(result)
    boolean_count["success_count"] = True
    _rehash_result(boolean_count)
    with pytest.raises(StandaloneDockCliError, match="success_count"):
        verify_pipeline_result(boolean_count)

    boolean_index = copy.deepcopy(result)
    boolean_index["candidate_evidence"][0]["proposal_index"] = False
    _rehash_result(boolean_index)
    with pytest.raises(StandaloneDockCliError, match="proposal_index"):
        verify_pipeline_result(boolean_index)

    rebound_component = copy.deepcopy(result)
    rebound_component["component_ids"]["ranker"] = "attacker-ranker/1.0.0"
    _rehash_result(rebound_component)
    with pytest.raises(StandaloneDockCliError, match="not canonical"):
        verify_pipeline_result(rebound_component)

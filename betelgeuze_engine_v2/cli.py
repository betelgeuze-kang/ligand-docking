"""Canonical-input command line entry point for the Engine v2 research surface.

The CLI deliberately accepts only canonical Engine v2 molecular documents and a
canonical typed pocket document. It performs no PDB/SDF parsing, protonation,
tautomer selection, atom typing, charge generation, parameter assignment, or
pocket prediction.

The ``dock-canonical`` command connects the existing contracts:

canonical receptor/ligand bytes
    -> typed pocket
    -> element-aware authenticated docking authority
    -> deterministic Haar pocket placement
    -> uncalibrated interpretable scorer
    -> failure-complete retained score-term evidence

The scorer source digest is observed from the installed package resource after
module import. It is recorded explicitly as non-attested execution provenance;
it is not equivalent to the hardened pre-import source-snapshot lane.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Mapping, Sequence

import torch

from .contracts import DISTRIBUTION_VERSION, ENGINE_API_VERSION
from .docking import (
    AuthenticatedDockingSearchResult,
    DockingBudget,
    DockingProposal,
    DockingScope,
    InterpretablePoseScorerV0,
    PocketDefinition,
    PocketPlacementReceipt,
    PocketPlacementSearchResult,
    RefinedDockingCandidates,
    ScoredDockingCandidates,
    ValidatedDockingCandidates,
    build_element_aware_authenticated_known_pocket_docking_problem,
    build_interpretable_scored_search_result,
    evaluate_scored_docking_candidates,
    generate_pocket_centered_docking_proposals,
    prepare_bounded_docking_search,
    rank_validated_docking_candidates,
    refine_bounded_docking_candidates,
    score_refined_docking_candidates,
)
from .molecular import all_atom_system_from_canonical_json
from .pipeline import (
    DockingPipeline,
    DockingPipelineExecution,
    DockingPipelineStagePayload,
    VerifiedDockingPipelineStageOutput,
    VerifiedDockingPipelineExecution,
    docking_pipeline_stage_payload,
    require_pipeline_stage,
)


CLI_POCKET_INPUT_SCHEMA_ID = "betelgeuze.engine_v2_cli_pocket_input/1.0.0"
CLI_DOCKING_RESULT_LEGACY_SCHEMA_ID = "betelgeuze.engine_v2_cli_docking_result/1.0.0"
CLI_DOCKING_RESULT_SCHEMA_ID = "betelgeuze.engine_v2_cli_docking_result/1.1.0"
CLI_FAILURE_SCHEMA_ID = "betelgeuze.engine_v2_cli_failure/1.0.0"
CLI_COMMAND_ID = "betelgeuze-engine-v2/dock-canonical/1.0.0"
SCORER_SOURCE_BINDING_MODE = (
    "observed_installed_package_resource_after_import_not_preimport_attested"
)
CANONICAL_DOCKING_PIPELINE_PROFILE_ID = (
    "betelgeuze.engine_v2_standalone_canonical_cpu_pipeline/1.0.0"
)
MAX_CLI_INPUT_BYTES = 128 * 1024 * 1024
MAX_CLI_POCKET_BYTES = 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024


class EngineV2CliError(RuntimeError):
    """The canonical CLI contract failed closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("CLI output is not canonical JSON") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_document(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _read_bounded(path: Path, *, maximum: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise EngineV2CliError(f"{name} must be a single-link regular file")
        if not 0 < before.st_size <= maximum:
            raise EngineV2CliError(f"{name} exceeds its byte bound")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise EngineV2CliError(f"{name} exceeds its byte bound")
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or total != after.st_size:
            raise EngineV2CliError(f"{name} changed while it was being read")
        return b"".join(chunks)
    except EngineV2CliError:
        raise
    except OSError as exc:
        raise EngineV2CliError(f"{name} could not be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _reject_duplicate_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EngineV2CliError(f"pocket document contains duplicate key {key!r}")
        result[key] = value
    return result


def _load_canonical_pocket_document(raw: bytes) -> Mapping[str, object]:
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise EngineV2CliError("pocket document has non-canonical line endings")
    try:
        text = canonical.decode("ascii")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineV2CliError("pocket document is invalid JSON") from exc
    if not isinstance(document, dict):
        raise EngineV2CliError("pocket document must be a JSON object")
    if _canonical_bytes(document) != canonical:
        raise EngineV2CliError("pocket document bytes are not canonical")
    return document


def _exact_keys(
    document: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str],
) -> None:
    keys = set(document)
    missing = required - keys
    unexpected = keys - required - optional
    if missing:
        raise EngineV2CliError(
            "pocket document is missing fields: " + ", ".join(sorted(missing))
        )
    if unexpected:
        raise EngineV2CliError(
            "pocket document has unexpected fields: " + ", ".join(sorted(unexpected))
        )


def _pocket_from_document(document: Mapping[str, object]) -> PocketDefinition:
    _exact_keys(
        document,
        required={
            "schema_id",
            "scope",
            "method_id",
            "method_version",
            "coordinate_frame_id",
            "center_angstrom",
            "radius_angstrom",
            "source_artifact_sha256",
            "implementation_source_sha256",
        },
        optional={"metadata"},
    )
    if document["schema_id"] != CLI_POCKET_INPUT_SCHEMA_ID:
        raise EngineV2CliError("pocket document schema is unsupported")
    center = document["center_angstrom"]
    if (
        not isinstance(center, list)
        or len(center) != 3
        or any(isinstance(value, bool) for value in center)
    ):
        raise EngineV2CliError(
            "pocket center_angstrom must contain exactly three numbers"
        )
    try:
        center_tensor = torch.tensor(center, dtype=torch.float64)
        radius_value = document["radius_angstrom"]
        if isinstance(radius_value, bool) or not isinstance(radius_value, (int, float)):
            raise TypeError("pocket radius must be a JSON number")
        radius = float(radius_value)
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("pocket geometry is invalid") from exc
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        raise EngineV2CliError("pocket metadata must be a JSON object")
    try:
        return PocketDefinition(
            scope=DockingScope(str(document["scope"])),
            method_id=str(document["method_id"]),
            method_version=str(document["method_version"]),
            coordinate_frame_id=str(document["coordinate_frame_id"]),
            center=center_tensor,
            radius_angstrom=radius,
            source_artifact_sha256=str(document["source_artifact_sha256"]),
            implementation_source_sha256=str(document["implementation_source_sha256"]),
            metadata=metadata,
        )
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("pocket contract is invalid") from exc


def _installed_scorer_source_sha256() -> str:
    try:
        resource = resources.files("betelgeuze_engine_v2.docking").joinpath(
            "interpretable_scorer.py"
        )
        payload = resource.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise EngineV2CliError(
            "installed scorer source resource is unavailable"
        ) from exc
    if not payload:
        raise EngineV2CliError("installed scorer source resource is empty")
    return _sha256_bytes(payload)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("CLI output write made no progress")
        view = view[written:]


def _write_output(
    document: Mapping[str, object],
    path: Path,
    *,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        existing = None
    if existing is not None:
        if not overwrite:
            raise EngineV2CliError(
                "output already exists; use --overwrite to replace it"
            )
        if not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1:
            raise EngineV2CliError(
                "output must be absent or a single-link regular file"
            )
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(temporary, flags, 0o600)
        _write_all(descriptor, _canonical_bytes(document) + b"\n")
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_flags |= getattr(os, "O_CLOEXEC", 0)
        directory = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise EngineV2CliError("CLI output could not be written durably") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@dataclass(frozen=True, slots=True)
class _CanonicalDockingRequest:
    receptor_path: Path
    ligand_path: Path
    pocket_path: Path
    candidate_count: int
    top_k: int
    max_torsions: int
    translation_radius_angstrom: float
    seed: int
    receptor_margin_angstrom: float


@dataclass(frozen=True, slots=True)
class _CanonicalPreparedInput:
    request: _CanonicalDockingRequest
    receptor_bytes: bytes
    ligand_bytes: bytes
    pocket_bytes: bytes
    receptor: object
    ligand: object
    pocket: PocketDefinition
    authority: object
    budget: DockingBudget
    scorer_source_sha256: str


@dataclass(frozen=True, slots=True)
class _CanonicalProposalBatch:
    proposals: tuple[DockingProposal, ...]
    placement_receipt: PocketPlacementReceipt

    def __post_init__(self) -> None:
        proposals = tuple(self.proposals)
        if not proposals or not isinstance(
            self.placement_receipt,
            PocketPlacementReceipt,
        ):
            raise EngineV2CliError("canonical proposal batch is invalid")
        for proposal in proposals:
            if not isinstance(proposal, DockingProposal):
                raise EngineV2CliError("canonical proposal batch is untyped")
            proposal.assert_integrity()
        if self.placement_receipt.proposal_fingerprint_sha256s != tuple(
            proposal.fingerprint_sha256 for proposal in proposals
        ):
            raise EngineV2CliError("canonical proposal receipt is cross-wired")
        self.placement_receipt.receipt_sha256
        object.__setattr__(self, "proposals", proposals)

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(proposal.candidate_id for proposal in self.proposals)

    def integrity_document(self) -> dict[str, object]:
        for proposal in self.proposals:
            proposal.assert_integrity()
        return {
            "placement_receipt_sha256": self.placement_receipt.receipt_sha256,
            "proposal_fingerprint_sha256s": [
                proposal.fingerprint_sha256 for proposal in self.proposals
            ],
            "proposal_coordinate_sha256s": [
                proposal.coordinate_fingerprint_sha256 for proposal in self.proposals
            ],
        }


@dataclass(frozen=True, slots=True)
class _CanonicalRefinementStage:
    proposal_batch: _CanonicalProposalBatch
    refined: RefinedDockingCandidates


@dataclass(frozen=True, slots=True)
class _CanonicalScoringStage:
    proposal_batch: _CanonicalProposalBatch
    scored: ScoredDockingCandidates


@dataclass(frozen=True, slots=True)
class _CanonicalValidityStage:
    proposal_batch: _CanonicalProposalBatch
    validated: ValidatedDockingCandidates


def _canonical_stage(
    value: object,
    *,
    stage_name: str,
) -> VerifiedDockingPipelineStageOutput:
    try:
        return require_pipeline_stage(value, stage_name=stage_name)
    except Exception as exc:
        raise EngineV2CliError("canonical pipeline stage input is invalid") from exc


def _canonical_payload(
    value: object,
    *,
    evidence: Mapping[str, object],
    integrity: Mapping[str, object],
    candidate_ids: tuple[str, ...] = (),
) -> DockingPipelineStagePayload:
    return docking_pipeline_stage_payload(
        value,
        evidence=evidence,
        integrity=integrity,
        candidate_ids=candidate_ids,
        candidate_count=(len(candidate_ids) if candidate_ids else None),
    )


class _CanonicalPipelineComponent:
    def pipeline_configuration(self) -> Mapping[str, object]:
        return {}


class _CanonicalInputPreparer(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.canonical_input_preparer/1.0.0"

    def prepare(self, request: object) -> DockingPipelineStagePayload:
        if not isinstance(request, _CanonicalDockingRequest):
            raise EngineV2CliError("canonical pipeline request is invalid")
        receptor_bytes = _read_bounded(
            request.receptor_path,
            maximum=MAX_CLI_INPUT_BYTES,
            name="receptor canonical document",
        )
        ligand_bytes = _read_bounded(
            request.ligand_path,
            maximum=MAX_CLI_INPUT_BYTES,
            name="ligand canonical document",
        )
        pocket_bytes = _read_bounded(
            request.pocket_path,
            maximum=MAX_CLI_POCKET_BYTES,
            name="pocket canonical document",
        )
        try:
            receptor = all_atom_system_from_canonical_json(receptor_bytes)
            ligand = all_atom_system_from_canonical_json(ligand_bytes)
        except (TypeError, ValueError) as exc:
            raise EngineV2CliError("canonical molecular document is invalid") from exc
        pocket_document = _load_canonical_pocket_document(pocket_bytes)
        pocket = _pocket_from_document(pocket_document)
        authority = build_element_aware_authenticated_known_pocket_docking_problem(
            receptor,
            ligand,
            pocket,
            receptor_margin_angstrom=float(request.receptor_margin_angstrom),
        )
        budget = DockingBudget(
            candidate_count=request.candidate_count,
            top_k=request.top_k,
            max_torsions=request.max_torsions,
            translation_radius_angstrom=(request.translation_radius_angstrom),
            seed=request.seed,
        )
        prepared = _CanonicalPreparedInput(
            request=request,
            receptor_bytes=receptor_bytes,
            ligand_bytes=ligand_bytes,
            pocket_bytes=pocket_bytes,
            receptor=receptor,
            ligand=ligand,
            pocket=pocket,
            authority=authority,
            budget=budget,
            scorer_source_sha256=_installed_scorer_source_sha256(),
        )
        evidence = {
            "authenticated_input_receipt_sha256": authority.input_receipt_sha256,
            "receptor_artifact_sha256": _sha256_bytes(receptor_bytes),
            "ligand_artifact_sha256": _sha256_bytes(ligand_bytes),
            "pocket_artifact_sha256": _sha256_bytes(pocket_bytes),
            "candidate_count": budget.candidate_count,
        }
        return _canonical_payload(
            prepared,
            evidence=evidence,
            integrity={
                **evidence,
                "budget": budget.to_dict(),
                "pocket_definition_sha256": pocket.fingerprint_sha256,
                "scorer_source_sha256": prepared.scorer_source_sha256,
            },
        )


class _CanonicalConformerProvider(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.source_coordinate_conformer_provider/1.0.0"

    def provide(self, prepared_input: object) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        prepared_input = prepared_stage.value
        if not isinstance(prepared_input, _CanonicalPreparedInput):
            raise EngineV2CliError("canonical prepared input is invalid")
        ligand = prepared_input.ligand
        model_count = int(getattr(ligand, "model_count", 0))
        if model_count < 1:
            raise EngineV2CliError("ligand has no explicit coordinate model")
        evidence = {
            "provider_id": self.component_id,
            "source_artifact_sha256": _sha256_bytes(prepared_input.ligand_bytes),
            "available_model_count": model_count,
            "selected_model_index": 0,
            "coordinate_generation_performed": False,
            "result_dependent_selection": False,
        }
        return _canonical_payload(
            evidence,
            evidence=evidence,
            integrity={
                **evidence,
                "authenticated_input_receipt_sha256": (
                    prepared_input.authority.input_receipt_sha256
                ),
            },
        )


class _CanonicalProposalGenerator(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.deterministic_haar_pocket_proposal_plan/1.0.0"

    def generate(
        self,
        prepared_input: object,
        conformer_evidence: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        conformer_stage = _canonical_stage(
            conformer_evidence,
            stage_name="conformer_provider.provide",
        )
        prepared_input = prepared_stage.value
        conformer_evidence = conformer_stage.evidence
        if not isinstance(prepared_input, _CanonicalPreparedInput):
            raise EngineV2CliError("canonical proposal inputs are invalid")
        proposals, placement_receipt = generate_pocket_centered_docking_proposals(
            prepared_input.authority,
            prepared_input.budget,
        )
        batch = _CanonicalProposalBatch(proposals, placement_receipt)
        evidence = {
            "generator_id": self.component_id,
            "candidate_count": prepared_input.budget.candidate_count,
            "seed": prepared_input.budget.seed,
            "translation_radius_angstrom_binary64_hex": float(
                prepared_input.budget.translation_radius_angstrom
            ).hex(),
            "orientation_sequence": "index_stable_deterministic_haar",
            "allocation_result_independent": True,
            "candidate_denominator_preserved": True,
        }
        return _canonical_payload(
            batch,
            evidence=evidence,
            integrity={
                **batch.integrity_document(),
                "conformer_stage_receipt_sha256": conformer_stage.receipt_sha256,
                "authenticated_input_receipt_sha256": (
                    prepared_input.authority.input_receipt_sha256
                ),
            },
            candidate_ids=batch.candidate_ids,
        )


class _CanonicalGeometricAdmission(_CanonicalPipelineComponent):
    component_id = (
        "betelgeuze.engine_v2.denominator_preserving_validity_admission/1.0.0"
    )

    def admit(
        self,
        prepared_input: object,
        proposal_evidence: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        proposal_stage = _canonical_stage(
            proposal_evidence,
            stage_name="proposal_generator.generate",
        )
        prepared_input = prepared_stage.value
        proposal_batch = proposal_stage.value
        if not isinstance(prepared_input, _CanonicalPreparedInput) or not isinstance(
            proposal_batch,
            _CanonicalProposalBatch,
        ):
            raise EngineV2CliError("canonical geometric admission input is invalid")
        count = len(proposal_batch.proposals)
        if count != prepared_input.budget.candidate_count:
            raise EngineV2CliError("proposal denominator changed before admission")
        evidence = {
            "admission_id": self.component_id,
            "candidate_slot_count": count,
            "pre_score_candidate_deletion_performed": False,
            "pose_validity_evaluated_in_search": True,
            "failure_slots_retained": True,
        }
        return _canonical_payload(
            proposal_batch,
            evidence=evidence,
            integrity={
                **proposal_batch.integrity_document(),
                "proposal_stage_receipt_sha256": proposal_stage.receipt_sha256,
                "all_proposals_integrity_checked": True,
            },
            candidate_ids=proposal_batch.candidate_ids,
        )


class _CanonicalScorer(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.interpretable_pose_scorer_v0_executor/1.0.0"

    def bind(
        self,
        prepared_input: object,
        admission_evidence: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        admission_stage = _canonical_stage(
            admission_evidence,
            stage_name="geometric_admission.admit",
        )
        prepared_input = prepared_stage.value
        proposal_batch = admission_stage.value
        if not isinstance(prepared_input, _CanonicalPreparedInput) or not isinstance(
            proposal_batch,
            _CanonicalProposalBatch,
        ):
            raise EngineV2CliError("canonical scorer binding input is invalid")
        scorer = InterpretablePoseScorerV0(
            prepared_input.authority,
            implementation_source_sha256=(prepared_input.scorer_source_sha256),
        )
        qualification = scorer.qualification_document()
        return _canonical_payload(
            scorer,
            evidence={
                "scorer_id": self.component_id,
                "scorer_contract_fingerprint_sha256": (
                    scorer.contract_fingerprint_sha256
                ),
            },
            integrity={
                "scorer_contract_fingerprint_sha256": (
                    scorer.contract_fingerprint_sha256
                ),
                "scorer_authority_input_receipt_sha256": (
                    scorer.authority_input_receipt_sha256
                ),
                "qualification_document_sha256": _sha256_document(qualification),
                "admission_stage_receipt_sha256": admission_stage.receipt_sha256,
            },
            candidate_ids=proposal_batch.candidate_ids,
        )

    def score(
        self,
        prepared_input: object,
        refined_candidates: object,
        scorer_binding: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        refiner_stage = _canonical_stage(
            refined_candidates,
            stage_name="refiner.refine",
        )
        scorer_stage = _canonical_stage(
            scorer_binding,
            stage_name="scorer.bind",
        )
        prepared_input = prepared_stage.value
        refinement = refiner_stage.value
        scorer_binding = scorer_stage.value
        if (
            not isinstance(prepared_input, _CanonicalPreparedInput)
            or not isinstance(refinement, _CanonicalRefinementStage)
            or not isinstance(scorer_binding, InterpretablePoseScorerV0)
        ):
            raise EngineV2CliError("canonical scorer inputs are invalid")
        if refinement.refined.prepared_search.scorer is not scorer_binding:
            raise EngineV2CliError("canonical scorer authority is cross-wired")
        scored = score_refined_docking_candidates(refinement.refined)
        stage = _CanonicalScoringStage(
            proposal_batch=refinement.proposal_batch,
            scored=scored,
        )
        if tuple(row.candidate_id for row in scored.rows) != (
            refinement.proposal_batch.candidate_ids
        ):
            raise EngineV2CliError("canonical scorer changed candidate authority")
        success_count = sum(row.succeeded for row in scored.rows)
        return _canonical_payload(
            stage,
            evidence={
                "scorer_id": self.component_id,
                "candidate_slot_count": len(scored.rows),
                "success_count": success_count,
                "failure_count": len(scored.rows) - success_count,
                "validity_evaluated": False,
                "ranking_performed": False,
            },
            integrity={
                "scorer_stage_receipt_sha256": scorer_stage.receipt_sha256,
                "refiner_stage_receipt_sha256": refiner_stage.receipt_sha256,
                "score_binary64_hex_by_slot": [
                    None if row.score is None else float(row.score).hex()
                    for row in scored.rows
                ],
                "status_by_slot": [row.status for row in scored.rows],
            },
            candidate_ids=refinement.proposal_batch.candidate_ids,
        )


class _CanonicalNoOpRefiner(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.no_refinement/1.0.0"

    def refine(
        self,
        prepared_input: object,
        admission_evidence: object,
        scorer_binding: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        admission_stage = _canonical_stage(
            admission_evidence,
            stage_name="geometric_admission.admit",
        )
        scorer_stage = _canonical_stage(
            scorer_binding,
            stage_name="scorer.bind",
        )
        prepared_input = prepared_stage.value
        proposal_batch = admission_stage.value
        scorer = scorer_stage.value
        if (
            not isinstance(prepared_input, _CanonicalPreparedInput)
            or not isinstance(
                proposal_batch,
                _CanonicalProposalBatch,
            )
            or not isinstance(scorer, InterpretablePoseScorerV0)
        ):
            raise EngineV2CliError("canonical refiner input is invalid")
        prepared_search = prepare_bounded_docking_search(
            prepared_input.authority.search_space,
            prepared_input.budget,
            scorer,
            refiner=None,
            validity_context=prepared_input.authority.validity_context,
            problem=prepared_input.authority.problem,
            proposals=proposal_batch.proposals,
        )
        refined = refine_bounded_docking_candidates(prepared_search)
        stage = _CanonicalRefinementStage(
            proposal_batch=proposal_batch,
            refined=refined,
        )
        evidence = {
            "refiner_id": self.component_id,
            "refinement_performed": False,
            "candidate_slot_count": len(refined.candidates),
        }
        return _canonical_payload(
            stage,
            evidence=evidence,
            integrity={
                **evidence,
                "admission_stage_receipt_sha256": admission_stage.receipt_sha256,
                "scorer_stage_receipt_sha256": scorer_stage.receipt_sha256,
                "proposal_fingerprint_sha256s": list(
                    proposal_batch.placement_receipt.proposal_fingerprint_sha256s
                ),
            },
            candidate_ids=proposal_batch.candidate_ids,
        )


def _generic_search_result(scored_result: object) -> object:
    try:
        return scored_result.placement_search_result.authenticated_search_result.search_result
    except AttributeError as exc:
        raise EngineV2CliError("canonical scored result is invalid") from exc


class _CanonicalValidityEvaluator(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.element_aware_validity_evaluator/1.0.0"

    def evaluate(
        self,
        prepared_input: object,
        scored_result: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        scored_stage = _canonical_stage(
            scored_result,
            stage_name="scorer.score",
        )
        prepared_input = prepared_stage.value
        scoring = scored_stage.value
        if not isinstance(prepared_input, _CanonicalPreparedInput) or not isinstance(
            scoring,
            _CanonicalScoringStage,
        ):
            raise EngineV2CliError("canonical validity input is invalid")
        validated = evaluate_scored_docking_candidates(scoring.scored)
        stage = _CanonicalValidityStage(
            proposal_batch=scoring.proposal_batch,
            validated=validated,
        )
        rows = validated.rows
        if len(rows) != prepared_input.budget.candidate_count:
            raise EngineV2CliError("canonical search denominator is incomplete")
        successful = tuple(row for row in rows if row.succeeded)
        if any(
            row.pose_validity is None or not row.pose_validity.complete
            for row in successful
        ):
            raise EngineV2CliError(
                "successful canonical candidate lacks complete validity evidence"
            )
        evidence = {
            "evaluator_id": self.component_id,
            "candidate_slot_count": len(rows),
            "successful_candidate_count": len(successful),
            "valid_candidate_count": sum(row.pose_valid for row in successful),
            "invalid_candidate_count": sum(not row.pose_valid for row in successful),
            "failure_count": len(rows) - len(successful),
            "validity_complete": True,
            "failure_slots_retained": True,
        }
        return _canonical_payload(
            stage,
            evidence=evidence,
            integrity={
                **evidence,
                "scored_stage_receipt_sha256": scored_stage.receipt_sha256,
                "validity_context_fingerprint_sha256": (
                    prepared_input.authority.validity_context.fingerprint_sha256
                ),
                "validity_by_slot": [
                    None if row.pose_validity is None else row.pose_validity.to_dict()
                    for row in rows
                ],
            },
            candidate_ids=scored_stage.candidate_ids,
        )


class _CanonicalRanker(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.raw_and_eligible_stable_ranker/1.0.0"

    def rank(
        self,
        prepared_input: object,
        scored_result: object,
        validity_evidence: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _canonical_stage(
            prepared_input,
            stage_name="input_preparer.prepare",
        )
        scored_stage = _canonical_stage(
            scored_result,
            stage_name="scorer.score",
        )
        validity_stage = _canonical_stage(
            validity_evidence,
            stage_name="validity_evaluator.evaluate",
        )
        prepared_input = prepared_stage.value
        scoring = scored_stage.value
        validity = validity_stage.value
        if (
            not isinstance(prepared_input, _CanonicalPreparedInput)
            or not isinstance(scoring, _CanonicalScoringStage)
            or not isinstance(validity, _CanonicalValidityStage)
            or validity.validated.scored_candidates is not scoring.scored
        ):
            raise EngineV2CliError("canonical ranking input is invalid")
        search = rank_validated_docking_candidates(validity.validated)
        authenticated = AuthenticatedDockingSearchResult(
            authenticated_input_receipt_sha256=(
                prepared_input.authority.input_receipt_sha256
            ),
            search_result=search,
        )
        placement = PocketPlacementSearchResult(
            placement_receipt=validity.proposal_batch.placement_receipt,
            authenticated_search_result=authenticated,
        )
        scorer = scoring.scored.refined_candidates.prepared_search.scorer
        result = build_interpretable_scored_search_result(placement, scorer)
        successful = tuple(
            row for row in search.rows if row.succeeded and row.score is not None
        )
        raw_ranked = tuple(
            sorted(
                successful,
                key=lambda row: (
                    float(row.score),
                    row.proposal_index,
                    row.candidate_id,
                ),
            )
        )
        eligible_top = tuple(search.top_rows)
        if any(not row.selection_eligible for row in eligible_top):
            raise EngineV2CliError("canonical top-k contains an ineligible pose")
        evidence = {
            "ranker_id": self.component_id,
            "raw_score_rank_candidate_ids": [row.candidate_id for row in raw_ranked],
            "validity_eligible_top_candidate_ids": [
                row.candidate_id for row in eligible_top
            ],
            "raw_rank_preserves_invalid_candidates": True,
            "stable_tie_break": "score_then_proposal_index_then_candidate_id",
            "result_dependent_reranking": False,
        }
        return _canonical_payload(
            result,
            evidence=evidence,
            integrity={
                "result_receipt_sha256": result.receipt_sha256,
                "scored_stage_receipt_sha256": scored_stage.receipt_sha256,
                "validity_stage_receipt_sha256": validity_stage.receipt_sha256,
                "raw_rank_candidate_ids": evidence["raw_score_rank_candidate_ids"],
                "eligible_top_candidate_ids": evidence[
                    "validity_eligible_top_candidate_ids"
                ],
            },
            candidate_ids=scored_stage.candidate_ids,
        )


class _CanonicalEvidenceRecorder(_CanonicalPipelineComponent):
    component_id = "betelgeuze.engine_v2.canonical_pipeline_evidence_recorder/1.0.0"

    def record(
        self,
        execution: DockingPipelineExecution,
    ) -> DockingPipelineStagePayload:
        prepared = execution.prepared_input
        scorer = execution.scorer_binding
        result = execution.scored_result
        if not isinstance(prepared, _CanonicalPreparedInput) or not isinstance(
            scorer,
            InterpretablePoseScorerV0,
        ):
            raise EngineV2CliError("canonical pipeline evidence is cross-wired")
        pipeline_evidence: dict[str, object] = {
            "schema_id": execution.schema_id,
            "pipeline_profile_id": execution.pipeline_profile_id,
            "pipeline_profile_sha256": execution.pipeline_profile_sha256,
            "conformer_evidence": execution.conformer_evidence,
            "proposal_evidence": execution.proposal_evidence,
            "geometric_admission_evidence": execution.admission_evidence,
            "refiner_id": _CanonicalNoOpRefiner.component_id,
            "refinement_performed": False,
            "validity_evidence": execution.validity_evidence,
            "ranking_evidence": execution.ranking_evidence,
            "candidate_denominator_preserved": True,
            "failure_complete": True,
            "scientifically_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }
        pipeline_evidence["receipt_sha256"] = _sha256_document(pipeline_evidence)
        projection: dict[str, object] = {
            "schema_id": CLI_DOCKING_RESULT_SCHEMA_ID,
            "command_id": CLI_COMMAND_ID,
            "engine_api_version": ENGINE_API_VERSION,
            "distribution_version": DISTRIBUTION_VERSION,
            "receptor_artifact_sha256": _sha256_bytes(prepared.receptor_bytes),
            "ligand_artifact_sha256": _sha256_bytes(prepared.ligand_bytes),
            "pocket_artifact_sha256": _sha256_bytes(prepared.pocket_bytes),
            "pocket_definition_sha256": prepared.pocket.fingerprint_sha256,
            "authenticated_input_receipt_sha256": (
                prepared.authority.input_receipt_sha256
            ),
            "scorer_source_sha256": prepared.scorer_source_sha256,
            "scorer_source_binding_mode": SCORER_SOURCE_BINDING_MODE,
            "scorer_source_preimport_attested": False,
            "scorer_qualification": scorer.qualification_document(),
            "result_receipt_sha256": result.receipt_sha256,
            "candidate_count": len(result.rows),
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "pipeline_evidence": pipeline_evidence,
            "network_fetch_performed": False,
            "chemistry_inference_performed": False,
            "pocket_prediction_performed": False,
            "calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
            "result": result.to_dict(),
        }
        projection["document_sha256"] = _sha256_document(projection)
        proposal_stage = execution.stage_outputs[2]
        if proposal_stage.stage_name != "proposal_generator.generate":
            raise EngineV2CliError("canonical recorder candidate authority is invalid")
        return _canonical_payload(
            projection,
            evidence={
                "document_sha256": projection["document_sha256"],
                "result_receipt_sha256": result.receipt_sha256,
                "candidate_count": len(result.rows),
                "failure_complete": True,
            },
            integrity={
                "document_sha256": projection["document_sha256"],
                "pipeline_evidence_receipt_sha256": pipeline_evidence["receipt_sha256"],
                "result_receipt_sha256": result.receipt_sha256,
                "ranking_stage_receipt_sha256": execution.stage_outputs[
                    -1
                ].receipt_sha256,
            },
            candidate_ids=proposal_stage.candidate_ids,
        )


def build_canonical_docking_pipeline() -> DockingPipeline:
    """Build the unqualified standalone CPU reference profile."""

    return DockingPipeline(
        _CanonicalInputPreparer(),
        _CanonicalConformerProvider(),
        _CanonicalProposalGenerator(),
        _CanonicalGeometricAdmission(),
        _CanonicalScorer(),
        _CanonicalNoOpRefiner(),
        _CanonicalValidityEvaluator(),
        _CanonicalRanker(),
        _CanonicalEvidenceRecorder(),
        profile_id=CANONICAL_DOCKING_PIPELINE_PROFILE_ID,
    )


def run_canonical_docking(
    *,
    receptor_path: Path,
    ligand_path: Path,
    pocket_path: Path,
    candidate_count: int,
    top_k: int,
    max_torsions: int,
    translation_radius_angstrom: float,
    seed: int,
    receptor_margin_angstrom: float,
) -> dict[str, object]:
    verified = run_canonical_docking_verified(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        candidate_count=candidate_count,
        top_k=top_k,
        max_torsions=max_torsions,
        translation_radius_angstrom=translation_radius_angstrom,
        seed=seed,
        receptor_margin_angstrom=receptor_margin_angstrom,
    )
    return dict(verified.recorded_evidence)


def run_canonical_docking_verified(
    *,
    receptor_path: Path,
    ligand_path: Path,
    pocket_path: Path,
    candidate_count: int,
    top_k: int,
    max_torsions: int,
    translation_radius_angstrom: float,
    seed: int,
    receptor_margin_angstrom: float,
) -> VerifiedDockingPipelineExecution:
    """Execute the standalone adapter and retain typed pipeline authority."""

    request = _CanonicalDockingRequest(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        candidate_count=candidate_count,
        top_k=top_k,
        max_torsions=max_torsions,
        translation_radius_angstrom=translation_radius_angstrom,
        seed=seed,
        receptor_margin_angstrom=receptor_margin_angstrom,
    )
    return build_canonical_docking_pipeline().run_verified(request)


def _failure_document(exc: BaseException) -> dict[str, object]:
    private = (
        f"{exc.__class__.__module__}.{exc.__class__.__qualname__}: {exc}"
    ).encode("utf-8", errors="replace")
    return {
        "schema_id": CLI_FAILURE_SCHEMA_ID,
        "status": "failure",
        "error_code": "engine_v2_cli_failed",
        "public_message": "Engine v2 canonical docking command failed",
        "private_error_sha256": _sha256_bytes(private),
        "private_error_byte_length": len(private),
        "claim_safe": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2",
        description=("Fail-closed Engine v2 canonical-input research commands."),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    dock = subparsers.add_parser(
        "dock-canonical",
        help=(
            "Run authenticated known-pocket docking from canonical Engine v2 inputs."
        ),
    )
    dock.add_argument("--receptor", type=Path, required=True)
    dock.add_argument("--ligand", type=Path, required=True)
    dock.add_argument("--pocket", type=Path, required=True)
    dock.add_argument("--output", type=Path)
    dock.add_argument("--overwrite", action="store_true")
    dock.add_argument("--candidate-count", type=int, default=64)
    dock.add_argument("--top-k", type=int, default=10)
    dock.add_argument("--max-torsions", type=int, default=32)
    dock.add_argument("--translation-radius-angstrom", type=float, default=4.0)
    dock.add_argument("--receptor-margin-angstrom", type=float, default=4.0)
    dock.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command != "dock-canonical":
            raise EngineV2CliError("unsupported command")
        document = run_canonical_docking(
            receptor_path=arguments.receptor,
            ligand_path=arguments.ligand,
            pocket_path=arguments.pocket,
            candidate_count=arguments.candidate_count,
            top_k=arguments.top_k,
            max_torsions=arguments.max_torsions,
            translation_radius_angstrom=(arguments.translation_radius_angstrom),
            seed=arguments.seed,
            receptor_margin_angstrom=(arguments.receptor_margin_angstrom),
        )
        if arguments.output is None:
            sys.stdout.buffer.write(_canonical_bytes(document) + b"\n")
            sys.stdout.buffer.flush()
        else:
            _write_output(
                document,
                arguments.output,
                overwrite=bool(arguments.overwrite),
            )
        return 0
    except Exception as exc:
        failure = _failure_document(exc)
        sys.stderr.buffer.write(_canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CLI_COMMAND_ID",
    "CLI_DOCKING_RESULT_LEGACY_SCHEMA_ID",
    "CLI_DOCKING_RESULT_SCHEMA_ID",
    "CLI_FAILURE_SCHEMA_ID",
    "CLI_POCKET_INPUT_SCHEMA_ID",
    "EngineV2CliError",
    "SCORER_SOURCE_BINDING_MODE",
    "main",
    "run_canonical_docking",
    "run_canonical_docking_verified",
]

"""Build the exact mixed64 source bundle for the repository synthetic D0 case."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import stat
from typing import TYPE_CHECKING, Final

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
)
from .authority import AuthenticatedDockingProblem
from .contact_validity import (
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from .guided_placement import (
    GuidedPlacementContext,
    GuidedPlacementPolicy,
    GuidedPlacementReceipt,
    build_guided_placement_context,
    generate_guided_docking_proposals,
)
from .mixed64_allocation import (
    FEATURE_LIGAND_ACCEPTOR,
    FEATURE_LIGAND_AROMATIC_PLANE,
    FEATURE_LIGAND_DONOR,
    FEATURE_LIGAND_NEGATIVE_SITE,
    FEATURE_LIGAND_POSITIVE_SITE,
    FEATURE_LIGAND_SHAPE_AXIS,
    FEATURE_POCKET_SHAPE_AXIS,
    FEATURE_RECEPTOR_ACCEPTOR,
    FEATURE_RECEPTOR_AROMATIC_PLANE,
    FEATURE_RECEPTOR_DONOR,
    FEATURE_RECEPTOR_NEGATIVE_SITE,
    FEATURE_RECEPTOR_POSITIVE_SITE,
    Mixed64AtomicFeatureEvidence,
    Mixed64FeatureEvidence,
    Mixed64RetainedSourceEvidence,
    Mixed64V7ControlSourceEvidence,
    build_fixed_mixed64_allocation,
)
from .mixed64_proposal_geometry_v3 import coordinate_sha256
from .mixed64_proposal_producer_v3 import (
    SOURCE_KIND_EXACT_V11_BASE,
    SOURCE_KIND_RETAINED_CONTROL,
    SOURCE_KIND_V7_CONTROL,
    Mixed64CoordinateSourcePayloadV1,
    Mixed64ProposalSourceBundleV1,
)
from .proposals import DockingBudget, DockingProposal
from .synthetic_d0_mixed64_source_policy_v3 import (
    BOUND_FIXTURE_ID,
    BOUND_FIXTURE_MANIFEST_SHA256,
    BOUND_GUIDED_POLICY_SHA256,
    BOUND_PIPELINE_PROFILE_RECEIPT_SHA256,
    BOUND_REQUEST_SHA256,
    BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256,
    PARTIAL_CHARGE_SITE_THRESHOLD,
    RETAINED_SOURCE_INDICES,
    SYNTHETIC_D0_MIXED64_SOURCE_COMPONENT_ID,
    SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
    SYNTHETIC_D0_MIXED64_SOURCE_PROFILE_ID,
    SYNTHETIC_D0_MIXED64_SOURCE_RECEIPT_SCHEMA_ID,
    V7_CONTROL_SOURCE_INDICES,
    frozen_synthetic_d0_mixed64_source_policy,
)

if TYPE_CHECKING:
    from .pipeline import DockingPipelineRequestV1


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_FACTORY_SEAL = object()
_MAX_CANONICAL_BYTES: Final = 128 * 1024 * 1024
_EXACT_SOURCE_RECEIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_exact_prepared_source/1.0.0"
)
_PROPOSAL_SOURCE_RECEIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_v7_proposal_source/1.0.0"
)
_PROPOSAL_LINEAGE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_v7_proposal_lineage/1.0.0"
)
_FEATURE_GEOMETRY_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_synthetic_d0_atomic_feature_geometry/1.0.0"
)


class SyntheticD0Mixed64SourceV3Error(ValueError):
    """Raised when the repository synthetic source adapter fails closed."""


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw(item) for item in value]
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        payload = json.dumps(
            _thaw(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 source evidence is not canonical JSON"
        ) from exc
    if len(payload) > _MAX_CANONICAL_BYTES:
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 source evidence exceeds its byte bound"
        )
    return payload


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _receipt_bytes(projection: Mapping[str, object]) -> bytes:
    document = dict(projection)
    document["receipt_sha256"] = _sha256(document)
    return _canonical_bytes(document)


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise SyntheticD0Mixed64SourceV3Error(f"{name} must be SHA-256")
    return value


def _stable_source_sha256(path: Path) -> str:
    try:
        if path.is_symlink():
            raise OSError("source is a symlink")
        before = path.stat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > 4 * 1024 * 1024
        ):
            raise OSError("source is not bounded regular data")
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 source adapter implementation is unavailable"
        ) from exc
    if (
        len(payload) != before.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 source adapter changed during read"
        )
    return hashlib.sha256(payload).hexdigest()


def _coordinates(value: torch.Tensor) -> tuple[tuple[float, float, float], ...]:
    if (
        type(value) is not torch.Tensor
        or value.device.type != "cpu"
        or value.dtype != torch.float64
        or value.ndim != 2
        or value.shape[1] != 3
        or not bool(torch.isfinite(value).all().item())
    ):
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 proposal coordinates are not exact CPU float64"
        )
    return tuple(
        tuple(float(component) for component in point)
        for point in value.tolist()
    )


def _proposal_source_receipt(
    *,
    proposal: DockingProposal,
    source_index: int,
    source_role: str,
    guided_receipt_sha256: str,
    request_sha256: str,
    authority_input_receipt_sha256: str,
) -> bytes:
    coordinates = _coordinates(proposal.coordinates)
    return _receipt_bytes(
        {
            "schema_id": _PROPOSAL_SOURCE_RECEIPT_SCHEMA_ID,
            "adapter_policy_sha256": SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
            "request_sha256": request_sha256,
            "authority_input_receipt_sha256": authority_input_receipt_sha256,
            "guided_placement_receipt_sha256": guided_receipt_sha256,
            "source_role": source_role,
            "source_index": source_index,
            "proposal_sha256": proposal.fingerprint_sha256,
            "coordinate_sha256": coordinate_sha256(coordinates),
            "result_fields_consumed": False,
        }
    )


def _proposal_lineage(
    *,
    proposal: DockingProposal,
    source_index: int,
    guided_receipt: GuidedPlacementReceipt,
    source_receipt_sha256: str,
) -> bytes:
    return _canonical_bytes(
        {
            "schema_id": _PROPOSAL_LINEAGE_SCHEMA_ID,
            "adapter_policy_sha256": SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
            "guided_placement_receipt_sha256": guided_receipt.receipt_sha256,
            "source_index": source_index,
            "proposal_mode": guided_receipt.proposal_modes[source_index],
            "ensemble_source_proposal_index": (
                guided_receipt.ensemble_source_proposal_indices[source_index]
            ),
            "proposal_sha256": proposal.fingerprint_sha256,
            "source_receipt_sha256": source_receipt_sha256,
            "result_fields_consumed": False,
        }
    )


def _coordinate_source(
    proposal: DockingProposal,
    *,
    source_kind: str,
    source_ordinal: int | None,
    source_receipt: bytes,
    guided_receipt: GuidedPlacementReceipt | None = None,
) -> Mixed64CoordinateSourcePayloadV1:
    proposal.assert_integrity()
    lineage: bytes | None = None
    if guided_receipt is not None:
        receipt_document = json.loads(source_receipt)
        lineage = _proposal_lineage(
            proposal=proposal,
            source_index=int(source_ordinal),
            guided_receipt=guided_receipt,
            source_receipt_sha256=receipt_document["receipt_sha256"],
        )
    return Mixed64CoordinateSourcePayloadV1(
        source_kind=source_kind,
        source_ordinal=source_ordinal,
        proposal_identity_payload_canonical_json=_canonical_bytes(
            proposal.identity_payload()
        ),
        source_receipt_canonical_json=source_receipt,
        coordinates=_coordinates(proposal.coordinates),
        proposal_lineage_canonical_json=lineage,
    )


def _attached_hydrogen(
    system: AllAtomSystem,
    atom_index: int,
) -> int | None:
    neighbors: list[int] = []
    for bond in system.bonds:
        if int(bond.atom_i) == atom_index:
            neighbors.append(int(bond.atom_j))
        elif int(bond.atom_j) == atom_index:
            neighbors.append(int(bond.atom_i))
    hydrogens = tuple(
        sorted(
            index
            for index in neighbors
            if system.atoms[index].element.upper() == "H"
        )
    )
    return None if not hydrogens else hydrogens[0]


def _feature_geometry_sha256(
    *,
    kind: str,
    atom_indices: tuple[int, ...],
    system: AllAtomSystem,
    model_index: int,
    source_receipt_sha256: str,
) -> str:
    coordinates = system.coordinates[model_index]
    return _sha256(
        {
            "schema_id": _FEATURE_GEOMETRY_SCHEMA_ID,
            "adapter_policy_sha256": SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
            "kind": kind,
            "atom_indices": list(atom_indices),
            "coordinates_binary64_hex": [
                [float(value).hex() for value in coordinates[index].tolist()]
                for index in atom_indices
            ],
            "source_receipt_sha256": source_receipt_sha256,
            "result_fields_consumed": False,
        }
    )


def _atomic_feature(
    *,
    kind: str,
    atom_indices: tuple[int, ...],
    system: AllAtomSystem,
    model_index: int,
    source_receipt_sha256: str,
) -> Mixed64AtomicFeatureEvidence:
    return Mixed64AtomicFeatureEvidence(
        kind=kind,
        atom_indices=atom_indices,
        source_receipt_sha256=source_receipt_sha256,
        geometry_receipt_sha256=_feature_geometry_sha256(
            kind=kind,
            atom_indices=atom_indices,
            system=system,
            model_index=model_index,
            source_receipt_sha256=source_receipt_sha256,
        ),
    )


def _atomic_features(
    *,
    context: GuidedPlacementContext,
    authority: AuthenticatedDockingProblem,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    source_receipt_sha256: str,
) -> tuple[Mixed64AtomicFeatureEvidence, ...]:
    rows: list[Mixed64AtomicFeatureEvidence] = []

    def add(
        kind: str,
        indices: tuple[int, ...],
        system: AllAtomSystem,
        model_index: int,
    ) -> None:
        rows.append(
            _atomic_feature(
                kind=kind,
                atom_indices=indices,
                system=system,
                model_index=model_index,
                source_receipt_sha256=source_receipt_sha256,
            )
        )

    for index in context.ligand_features["donor"]:
        hydrogen = _attached_hydrogen(ligand_system, int(index))
        if hydrogen is not None:
            add(
                FEATURE_LIGAND_DONOR,
                (int(index), hydrogen),
                ligand_system,
                authority.ligand_model_index,
            )
    for index in context.ligand_features["acceptor"]:
        add(
            FEATURE_LIGAND_ACCEPTOR,
            (int(index),),
            ligand_system,
            authority.ligand_model_index,
        )
    receptor_donors = tuple(
        int(value[0]) for value in context.receptor_feature_rows["donor"]
    )
    for index in receptor_donors:
        hydrogen = _attached_hydrogen(receptor_system, index)
        if hydrogen is not None:
            add(
                FEATURE_RECEPTOR_DONOR,
                (index, hydrogen),
                receptor_system,
                authority.receptor_model_index,
            )
    for value in context.receptor_feature_rows["acceptor"]:
        add(
            FEATURE_RECEPTOR_ACCEPTOR,
            (int(value[0]),),
            receptor_system,
            authority.receptor_model_index,
        )

    for system, model_index, positive_kind, negative_kind, allowed in (
        (
            ligand_system,
            authority.ligand_model_index,
            FEATURE_LIGAND_POSITIVE_SITE,
            FEATURE_LIGAND_NEGATIVE_SITE,
            tuple(range(ligand_system.atom_count)),
        ),
        (
            receptor_system,
            authority.receptor_model_index,
            FEATURE_RECEPTOR_POSITIVE_SITE,
            FEATURE_RECEPTOR_NEGATIVE_SITE,
            authority.receptor_atom_indices,
        ),
    ):
        for index in allowed:
            charge = system.atoms[int(index)].partial_charge_e
            if charge is None:
                raise SyntheticD0Mixed64SourceV3Error(
                    "synthetic D0 prepared atom lacks partial charge"
                )
            if float(charge) >= PARTIAL_CHARGE_SITE_THRESHOLD:
                add(positive_kind, (int(index),), system, model_index)
            elif float(charge) <= -PARTIAL_CHARGE_SITE_THRESHOLD:
                add(negative_kind, (int(index),), system, model_index)

    for indices in context.ligand_aromatic_systems:
        add(
            FEATURE_LIGAND_AROMATIC_PLANE,
            tuple(int(index) for index in indices),
            ligand_system,
            authority.ligand_model_index,
        )
    for indices, _center, _normal in context.receptor_aromatic_planes:
        add(
            FEATURE_RECEPTOR_AROMATIC_PLANE,
            tuple(int(index) for index in indices),
            receptor_system,
            authority.receptor_model_index,
        )
    ligand_heavy = tuple(
        atom.index
        for atom in ligand_system.atoms
        if atom.element.upper() != "H"
    )
    receptor_heavy = tuple(
        int(index)
        for index in authority.receptor_atom_indices
        if receptor_system.atoms[int(index)].element.upper() != "H"
    )
    if len(ligand_heavy) >= 2 and context.ligand_shape_frame_available:
        add(
            FEATURE_LIGAND_SHAPE_AXIS,
            ligand_heavy,
            ligand_system,
            authority.ligand_model_index,
        )
    if len(receptor_heavy) >= 2 and context.receptor_shape_axes:
        add(
            FEATURE_POCKET_SHAPE_AXIS,
            receptor_heavy,
            receptor_system,
            authority.receptor_model_index,
        )
    return tuple(sorted(rows, key=lambda value: (value.kind, value.receipt_sha256)))


def _pocket_normal(
    *,
    authority: AuthenticatedDockingProblem,
    receptor_system: AllAtomSystem,
    context: GuidedPlacementContext,
) -> tuple[float, float, float]:
    receptor_indices = list(authority.receptor_atom_indices)
    receptor = receptor_system.coordinates[
        authority.receptor_model_index,
        receptor_indices,
    ].to(dtype=torch.float64, device="cpu")
    center = authority.pocket.center.to(dtype=torch.float64, device="cpu")
    direction = center - receptor.mean(dim=0)
    norm = float(torch.linalg.vector_norm(direction).item())
    if norm <= 1.0e-12:
        if not context.receptor_shape_axes:
            raise SyntheticD0Mixed64SourceV3Error(
                "synthetic D0 pocket normal is degenerate"
            )
        direction = torch.tensor(
            context.receptor_shape_axes[0],
            dtype=torch.float64,
        )
        norm = float(torch.linalg.vector_norm(direction).item())
    normalized = direction / norm
    values = tuple(float(value) for value in normalized.tolist())
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 pocket normal is invalid"
        )
    return values  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class RepositorySyntheticD0Mixed64SourceReceiptV1:
    authority: AuthenticatedDockingProblem = field(repr=False)
    source_bundle: Mixed64ProposalSourceBundleV1 = field(repr=False)
    guided_placement_receipt: GuidedPlacementReceipt = field(repr=False)
    prepared_input_receipt_sha256: str
    adapter_implementation_source_sha256: str
    request_sha256: str
    fixture_admission_receipt_sha256: str
    _factory_seal: InitVar[object | None] = None
    schema_id: str = SYNTHETIC_D0_MIXED64_SOURCE_RECEIPT_SCHEMA_ID
    profile_id: str = SYNTHETIC_D0_MIXED64_SOURCE_PROFILE_ID
    _canonical_projection_bytes: bytes = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECEIPT_FACTORY_SEAL:
            raise SyntheticD0Mixed64SourceV3Error(
                "synthetic D0 source receipt requires the bounded adapter"
            )
        if (
            self.schema_id != SYNTHETIC_D0_MIXED64_SOURCE_RECEIPT_SCHEMA_ID
            or self.profile_id != SYNTHETIC_D0_MIXED64_SOURCE_PROFILE_ID
        ):
            raise SyntheticD0Mixed64SourceV3Error(
                "synthetic D0 source receipt identity changed"
            )
        if type(self.authority) is not AuthenticatedDockingProblem:
            raise TypeError("authority must be exact")
        if type(self.source_bundle) is not Mixed64ProposalSourceBundleV1:
            raise TypeError("source_bundle must be exact")
        if type(self.guided_placement_receipt) is not GuidedPlacementReceipt:
            raise TypeError("guided_placement_receipt must be exact")
        for name in (
            "prepared_input_receipt_sha256",
            "adapter_implementation_source_sha256",
            "request_sha256",
            "fixture_admission_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        self._validate()
        payload = _canonical_bytes(self._projection())
        object.__setattr__(self, "_canonical_projection_bytes", payload)
        object.__setattr__(self, "_receipt_sha256", hashlib.sha256(payload).hexdigest())

    def _validate(self) -> None:
        if self.request_sha256 != BOUND_REQUEST_SHA256:
            raise SyntheticD0Mixed64SourceV3Error(
                "synthetic D0 request binding changed"
            )
        if (
            self.source_bundle.allocation.features.exact_v11_source_receipt_sha256
            != self.source_bundle.receptor_source_receipt_sha256
            or len(self.guided_placement_receipt.proposal_fingerprint_sha256s) != 64
            or self.guided_placement_receipt.guided_policy_sha256
            != BOUND_GUIDED_POLICY_SHA256
            or self.guided_placement_receipt.authenticated_input_receipt_sha256
            != self.authority.input_receipt_sha256
        ):
            raise SyntheticD0Mixed64SourceV3Error(
                "synthetic D0 source or guided receipt is cross-wired"
            )
        self.source_bundle.receipt_sha256
        self.source_bundle.allocation.receipt_sha256
        self.guided_placement_receipt.receipt_sha256
        if (
            _stable_source_sha256(Path(__file__))
            != self.adapter_implementation_source_sha256
        ):
            raise SyntheticD0Mixed64SourceV3Error(
                "synthetic D0 source adapter implementation identity changed"
            )

    def _projection(self) -> dict[str, object]:
        allocation = self.source_bundle.allocation
        return {
            "schema_id": self.schema_id,
            "component_id": SYNTHETIC_D0_MIXED64_SOURCE_COMPONENT_ID,
            "profile_id": self.profile_id,
            "policy": frozen_synthetic_d0_mixed64_source_policy(),
            "policy_sha256": SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
            "scientific_pipeline_policy_sha256": (
                BOUND_SCIENTIFIC_PIPELINE_POLICY_SHA256
            ),
            "adapter_implementation_source_sha256": (
                self.adapter_implementation_source_sha256
            ),
            "request_sha256": self.request_sha256,
            "fixture_id": BOUND_FIXTURE_ID,
            "fixture_manifest_sha256": BOUND_FIXTURE_MANIFEST_SHA256,
            "fixture_admission_receipt_sha256": (
                self.fixture_admission_receipt_sha256
            ),
            "pipeline_profile_receipt_sha256": (
                BOUND_PIPELINE_PROFILE_RECEIPT_SHA256
            ),
            "prepared_input_receipt_sha256": self.prepared_input_receipt_sha256,
            "authority_input_receipt_sha256": self.authority.input_receipt_sha256,
            "problem_fingerprint_sha256": self.authority.problem.fingerprint_sha256,
            "search_space_fingerprint_sha256": (
                self.authority.search_space.fingerprint_sha256
            ),
            "guided_placement_receipt": self.guided_placement_receipt.to_dict(),
            "guided_placement_receipt_sha256": (
                self.guided_placement_receipt.receipt_sha256
            ),
            "allocation_receipt_sha256": allocation.receipt_sha256,
            "source_bundle_receipt_sha256": self.source_bundle.receipt_sha256,
            "source_bundle": self.source_bundle.to_dict(),
            "candidate_denominator": 64,
            "v7_control_source_count": len(
                allocation.features.v7_control_sources
            ),
            "true_conformer_source_count": len(
                allocation.features.conformer_sources
            ),
            "retained_source_count": len(allocation.features.retained_sources),
            "atomic_feature_count": len(allocation.features.atomic_features),
            "result_fields_consumed": False,
            "standalone_binding_ready": True,
            "standalone_activation_authorized": False,
            "benchmark_activation_authorized": False,
            "api_activation_authorized": False,
            "product_shadow_activation_authorized": False,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "reservation_allowed": False,
            "molecular_cohort_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "hip_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        self._validate()
        observed = hashlib.sha256(self._canonical_projection_bytes).hexdigest()
        if observed != self._receipt_sha256:
            raise SyntheticD0Mixed64SourceV3Error(
                "sealed synthetic D0 source receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        document = json.loads(self._canonical_projection_bytes)
        return {**document, "receipt_sha256": self.receipt_sha256}


def build_repository_synthetic_d0_mixed64_source(
    request: DockingPipelineRequestV1,
) -> RepositorySyntheticD0Mixed64SourceReceiptV1:
    """Derive the exact source bundle without accepting caller allocation."""

    from .pipeline import (
        CanonicalPreparedInputPreparer,
        DockingPipelineRequestV1,
        SYNTHETIC_D0_FIXTURE_ID,
        SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
        SYNTHETIC_D0_FIXTURE_REQUEST_SHA256,
    )

    if type(request) is not DockingPipelineRequestV1:
        raise TypeError("request must be exact DockingPipelineRequestV1")
    request._assert_fixture_admission()
    if (
        SYNTHETIC_D0_FIXTURE_ID != BOUND_FIXTURE_ID
        or SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256
        != BOUND_FIXTURE_MANIFEST_SHA256
        or SYNTHETIC_D0_FIXTURE_REQUEST_SHA256 != BOUND_REQUEST_SHA256
        or request.request_sha256 != BOUND_REQUEST_SHA256
        or request.fixture_admission.fixture_id != BOUND_FIXTURE_ID
        or request.fixture_admission.manifest_sha256
        != BOUND_FIXTURE_MANIFEST_SHA256
        or request.profile.receipt_sha256
        != BOUND_PIPELINE_PROFILE_RECEIPT_SHA256
        or request.seed != 4301
        or request.profile.candidate_count != 64
        or request.profile.top_k != 5
    ):
        raise SyntheticD0Mixed64SourceV3Error(
            "request is not the exact repository synthetic D0 fixture"
        )
    source_path = Path(__file__)
    adapter_source_sha256 = _stable_source_sha256(source_path)
    prepared = CanonicalPreparedInputPreparer().prepare(request)
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        prepared.receptor_system,
        prepared.ligand_system,
        prepared.pocket,
        receptor_margin_angstrom=request.profile.receptor_margin_angstrom,
    )
    if authority.receptor_atom_indices != tuple(
        range(prepared.receptor_system.atom_count)
    ):
        raise SyntheticD0Mixed64SourceV3Error(
            "repository synthetic D0 receptor subset is not exact contiguous input"
        )
    budget = DockingBudget(
        candidate_count=64,
        top_k=5,
        max_torsions=request.profile.max_torsions,
        max_refinement_steps=request.profile.max_refinement_steps,
        translation_radius_angstrom=min(
            request.profile.translation_radius_angstrom,
            prepared.pocket.radius_angstrom,
        ),
        seed=request.seed,
    )
    context = build_guided_placement_context(
        authority,
        prepared.receptor_system,
        prepared.ligand_system,
    )
    guided_policy = GuidedPlacementPolicy(uniform_v3_ensemble_enabled=True)
    if guided_policy.fingerprint_sha256 != BOUND_GUIDED_POLICY_SHA256:
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 guided source policy changed"
        )
    proposals, guided_receipt = generate_guided_docking_proposals(
        authority,
        budget,
        context,
        receptor_system=prepared.receptor_system,
        ligand_system=prepared.ligand_system,
        policy=guided_policy,
    )
    if (
        type(proposals) is not tuple
        or len(proposals) != 64
        or any(type(value) is not DockingProposal for value in proposals)
        or tuple(value.proposal_index for value in proposals) != tuple(range(64))
        or tuple(value.fingerprint_sha256 for value in proposals)
        != guided_receipt.proposal_fingerprint_sha256s
    ):
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 guided source denominator or identity changed"
        )

    exact_source_receipt = _receipt_bytes(
        {
            "schema_id": _EXACT_SOURCE_RECEIPT_SCHEMA_ID,
            "adapter_policy_sha256": SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256,
            "request_sha256": request.request_sha256,
            "fixture_admission_receipt_sha256": (
                request.fixture_admission.receipt_sha256
            ),
            "prepared_input_receipt_sha256": prepared.receipt_sha256,
            "authority_input_receipt_sha256": authority.input_receipt_sha256,
            "receptor_system_sha256": canonical_system_sha256(
                prepared.receptor_system
            ),
            "ligand_system_sha256": canonical_system_sha256(
                prepared.ligand_system
            ),
            "pocket_fingerprint_sha256": prepared.pocket.fingerprint_sha256,
            "result_fields_consumed": False,
        }
    )
    exact_source = _coordinate_source(
        proposals[0],
        source_kind=SOURCE_KIND_EXACT_V11_BASE,
        source_ordinal=None,
        source_receipt=exact_source_receipt,
    )

    controls: list[Mixed64CoordinateSourcePayloadV1] = []
    for index in V7_CONTROL_SOURCE_INDICES:
        source_receipt = _proposal_source_receipt(
            proposal=proposals[index],
            source_index=index,
            source_role="v7_control",
            guided_receipt_sha256=guided_receipt.receipt_sha256,
            request_sha256=request.request_sha256,
            authority_input_receipt_sha256=authority.input_receipt_sha256,
        )
        controls.append(
            _coordinate_source(
                proposals[index],
                source_kind=SOURCE_KIND_V7_CONTROL,
                source_ordinal=index,
                source_receipt=source_receipt,
                guided_receipt=guided_receipt,
            )
        )
    retained: list[Mixed64CoordinateSourcePayloadV1] = []
    for index in RETAINED_SOURCE_INDICES:
        source_receipt = _proposal_source_receipt(
            proposal=proposals[index],
            source_index=index,
            source_role="retained_control",
            guided_receipt_sha256=guided_receipt.receipt_sha256,
            request_sha256=request.request_sha256,
            authority_input_receipt_sha256=authority.input_receipt_sha256,
        )
        retained.append(
            _coordinate_source(
                proposals[index],
                source_kind=SOURCE_KIND_RETAINED_CONTROL,
                source_ordinal=index,
                source_receipt=source_receipt,
            )
        )

    atomic_features = _atomic_features(
        context=context,
        authority=authority,
        receptor_system=prepared.receptor_system,
        ligand_system=prepared.ligand_system,
        source_receipt_sha256=exact_source.source_receipt_sha256,
    )
    feature_evidence = Mixed64FeatureEvidence(
        exact_v11_source_receipt_sha256=exact_source.source_receipt_sha256,
        prepared_ligand_topology_sha256=canonical_system_sha256(
            prepared.ligand_system
        ),
        prepared_receptor_topology_sha256=canonical_system_sha256(
            prepared.receptor_system
        ),
        feature_extractor_policy_sha256=(
            SYNTHETIC_D0_MIXED64_SOURCE_POLICY_SHA256
        ),
        atomic_features=atomic_features,
        v7_control_sources=tuple(
            Mixed64V7ControlSourceEvidence(
                source_index=int(source.source_ordinal),
                proposal_mode=(
                    "pocket_centered_control"
                    if int(source.source_ordinal) < 8
                    else "uniform_source_control"
                ),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                proposal_lineage_sha256=str(source.proposal_lineage_sha256),
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in controls
        ),
        conformer_sources=(),
        retained_sources=tuple(
            Mixed64RetainedSourceEvidence(
                source_index=int(source.source_ordinal),
                proposal_sha256=source.proposal_sha256,
                coordinate_sha256=source.coordinate_sha256,
                source_receipt_sha256=source.source_receipt_sha256,
            )
            for source in retained
        ),
    )
    allocation = build_fixed_mixed64_allocation(feature_evidence)
    contact_policy = authority.validity_context.contact_policy
    receptor_indices = list(authority.receptor_atom_indices)
    receptor_coordinates = _coordinates(
        prepared.receptor_system.coordinates[
            authority.receptor_model_index,
            receptor_indices,
        ]
        .to(dtype=torch.float64, device="cpu")
        .contiguous()
    )
    source_bundle = Mixed64ProposalSourceBundleV1(
        allocation=allocation,
        exact_v11_source=exact_source,
        v7_control_sources=tuple(controls),
        conformer_sources=(),
        retained_sources=tuple(retained),
        ligand_vdw_radii=tuple(
            contact_policy.radius(atom.element)
            for atom in prepared.ligand_system.atoms
        ),
        ligand_heavy_atom_mask=tuple(
            atom.element.upper() != "H" for atom in prepared.ligand_system.atoms
        ),
        receptor_coordinates=receptor_coordinates,
        receptor_vdw_radii=tuple(
            contact_policy.radius(prepared.receptor_system.atoms[index].element)
            for index in receptor_indices
        ),
        receptor_source_receipt_canonical_json=exact_source_receipt,
        pocket_center=tuple(
            float(value)
            for value in prepared.pocket.center.to(
                dtype=torch.float64,
                device="cpu",
            ).tolist()
        ),
        pocket_normal=_pocket_normal(
            authority=authority,
            receptor_system=prepared.receptor_system,
            context=context,
        ),
        pocket_radius=prepared.pocket.radius_angstrom,
    )
    if _stable_source_sha256(source_path) != adapter_source_sha256:
        raise SyntheticD0Mixed64SourceV3Error(
            "synthetic D0 source adapter changed during execution"
        )
    return RepositorySyntheticD0Mixed64SourceReceiptV1(
        authority=authority,
        source_bundle=source_bundle,
        guided_placement_receipt=guided_receipt,
        prepared_input_receipt_sha256=prepared.receipt_sha256,
        adapter_implementation_source_sha256=adapter_source_sha256,
        request_sha256=request.request_sha256,
        fixture_admission_receipt_sha256=request.fixture_admission.receipt_sha256,
        _factory_seal=_RECEIPT_FACTORY_SEAL,
    )


__all__ = [
    "RepositorySyntheticD0Mixed64SourceReceiptV1",
    "SyntheticD0Mixed64SourceV3Error",
    "build_repository_synthetic_d0_mixed64_source",
]

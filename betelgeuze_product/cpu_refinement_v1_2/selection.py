"""Final cross-variant Top-K in the receptor frame; no ligand-only alignment."""
from __future__ import annotations

from dataclasses import dataclass
import math

from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.metrics import direct_rmsd
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, score_sort_key
from .provenance import ResearchError, decode_coordinates, finite, integer, require_digest


@dataclass(frozen=True)
class SelectionConfig:
    top_k: int
    diversity_rmsd_angstrom: float = .5

    def __post_init__(self):
        integer(self.top_k, 1, 256)
        value = finite(self.diversity_rmsd_angstrom, nonnegative=True)
        if value > 1000:
            raise ResearchError("diversity distance exceeds supported bound")

    def to_dict(self):
        return {"top_k": self.top_k, "diversity_rmsd_angstrom": self.diversity_rmsd_angstrom,
                "metric": "direct_rmsd_in_receptor_frame", "exact_coordinate_deduplication": True}


def candidate_from_row(row: dict, variant: str) -> dict:
    if variant not in {"baseline", "refined"}:
        raise ResearchError("unknown selected variant")
    names = ("candidate_id", "proposal_index", "score", "coordinates_sha256", "coordinates_binary64_hex",
             "proposal_fingerprint_sha256", "result_proposal_fingerprint_sha256",
             "selection_eligible", "pose_valid", "validity_complete")
    return {**{name: row[name] for name in names}, "variant": variant}


def select_final_candidates(candidates: list[dict], descriptor: DockingScoreDescriptor,
                            config: SelectionConfig, atom_count: int) -> dict:
    """Use existing score direction and direct-RMSD primitives with stable ties."""
    if type(config) is not SelectionConfig or not isinstance(descriptor, DockingScoreDescriptor):
        raise ResearchError("explicit score and selection contracts required")
    integer(atom_count, 1, 256)
    if type(candidates) is not list or len(candidates) > 256:
        raise ResearchError("candidate capacity exceeded")
    seen_ids, rows = set(), []
    for candidate in candidates:
        identifier = candidate["candidate_id"]
        if type(identifier) is not str or not identifier or identifier in seen_ids:
            raise ResearchError("candidate IDs must be nonempty and unique")
        seen_ids.add(identifier)
        integer(candidate["proposal_index"], 0, 1_000_000)
        if candidate["variant"] not in {"baseline", "refined"}:
            raise ResearchError("unknown variant")
        if any(candidate[name] is not True for name in ("selection_eligible", "pose_valid", "validity_complete")):
            raise ResearchError("invalid or incomplete candidate cannot enter final selection")
        score = finite(candidate["score"])
        for key in ("coordinates_sha256", "proposal_fingerprint_sha256", "result_proposal_fingerprint_sha256"):
            require_digest(candidate[key])
        xyz = decode_coordinates(candidate["coordinates_binary64_hex"], atom_count)[0]
        if coordinate_fingerprint(xyz) != candidate["coordinates_sha256"]:
            raise ResearchError("selected coordinates do not match their digest")
        rows.append((candidate, xyz, score_sort_key(score, descriptor)))
    rows.sort(key=lambda item: (item[2], item[0]["proposal_index"], item[0]["candidate_id"], item[0]["variant"]))
    selected, xyz_selected, coordinate_ids, decisions = [], [], set(), []
    for candidate, xyz, _ in rows:
        if candidate["coordinates_sha256"] in coordinate_ids:
            reason = "duplicate_coordinates"
        elif any(direct_rmsd(xyz, other) < config.diversity_rmsd_angstrom for other in xyz_selected):
            reason = "within_diversity_distance"
        elif len(selected) >= config.top_k:
            reason = "outside_top_k"
        else:
            reason = "selected"
            selected.append(dict(candidate))
            xyz_selected.append(xyz)
            coordinate_ids.add(candidate["coordinates_sha256"])
        decisions.append({"candidate_id": candidate["candidate_id"], "variant": candidate["variant"], "reason": reason})
    # All scalar sorting keys were checked above; no NaN-dependent ordering.
    assert all(math.isfinite(row[2]) for row in rows)
    return {"config": config.to_dict(), "score_descriptor": descriptor.to_dict(),
            "input_candidate_count": len(candidates), "selected_candidates": selected,
            "decisions": decisions, "globally_ranked": True, "scientifically_validated": False}

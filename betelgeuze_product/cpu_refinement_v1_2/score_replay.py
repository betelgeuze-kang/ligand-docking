"""Reconstruct bound successful ScorerV1 terms without recomputing the score.

This is internal consistency, not an independent physics or scorer validation.
The workflow must bind its journal to request/source/environment and account for
historical scoring work separately from replay overhead. Failure rows are not
converted into successful terms by this codec.
"""
from dataclasses import fields

from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1, ScorerV1Terms
from .provenance import ResearchError, canonical, exact_fields


_IDENTITIES = (
    "proposal_fingerprint_sha256", "authority_input_receipt_sha256",
    "context_fingerprint_sha256", "config_fingerprint_sha256", "backend_receipt_sha256",
)
_COUNTS = (
    "receptor_candidate_pair_count", "ligand_pair_count", "hbond_count",
    "hydrophobic_contact_count", "buried_polar_count",
)
_VALUES = tuple(f.name for f in fields(ScorerV1Terms)
                if f.init and f.name not in _IDENTITIES + _COUNTS)


def restore_score_terms(scorer, proposal, document):
    """Require canonical binary64 terms and all live candidate/scorer identities."""
    try:
        return _restore_score_terms(scorer, proposal, document)
    except ResearchError:
        raise
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise ResearchError("malformed or inconsistent saved scorer terms") from exc


def _restore_score_terms(scorer, proposal, document):
    if not isinstance(scorer, ChemistryPoseScorerV1):
        raise ResearchError("authenticated ScorerV1 required for replay")
    scorer._assert_proposal(proposal)
    expected = {
        "proposal_fingerprint_sha256": proposal.fingerprint_sha256,
        "authority_input_receipt_sha256": scorer.authority_input_receipt_sha256,
        "context_fingerprint_sha256": scorer.context.fingerprint_sha256,
        "config_fingerprint_sha256": scorer.config.fingerprint_sha256,
        "backend_receipt_sha256": scorer.backend_receipt_sha256,
    }
    exact_fields(document, set(_IDENTITIES + _COUNTS) | {f"{name}_binary64_hex" for name in _VALUES}
                 | {"schema_id", "score_id", "calibrated", "scientifically_validated", "claim_safe", "receipt_sha256"})
    if any(document[name] != value for name, value in expected.items()):
        raise ResearchError("saved score candidate or scorer identity mismatch")
    values = {}
    for name in _VALUES:
        text = document[f"{name}_binary64_hex"]
        if type(text) is not str:
            raise ResearchError("canonical hexadecimal score term required")
        value = float.fromhex(text)
        if value.hex() != text:
            raise ResearchError("noncanonical hexadecimal score term")
        values[name] = value
    result = ScorerV1Terms(**expected, **values, **{name: document[name] for name in _COUNTS})
    # Constructor verifies finite components, counts and the actual term sum.
    # Exact reproduction also checks schema, claim flags, and retained receipt.
    if canonical(result.to_dict()) != canonical(document):
        raise ResearchError("saved scorer terms do not reproduce canonical receipt")
    scorer._assert_proposal(proposal)
    return result

"""Restore a failed search row directly, preserving the original error receipt.

Re-raising a reconstructed exception would create a different private diagnostic
hash. This codec therefore restores the row, not the original exception. The
caller still binds the candidate journal to its request/source/environment.
"""
from betelgeuze_engine_v2.docking.search import DockingSearchRow
from .provenance import ResearchError, canonical, exact_fields, integer, require_digest


def restore_failure_row(authority, proposal, document, *, refined):
    try:
        return _restore_failure_row(authority, proposal, document, refined=refined)
    except ResearchError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise ResearchError("malformed or inconsistent failed candidate row") from exc


def _restore_failure_row(authority, proposal, document, *, refined):
    if type(refined) is not bool:
        raise ResearchError("explicit failed candidate refinement state required")
    proposal.assert_integrity()
    # Validate the live source and authority before trusting retained identity.
    authority.input_receipt_sha256
    if (proposal.problem_fingerprint_sha256 != authority.problem.fingerprint_sha256
            or proposal.search_space_fingerprint_sha256 != authority.search_space.fingerprint_sha256):
        raise ResearchError("failed candidate source is cross-wired")
    if type(document) is not dict:
        raise ResearchError("explicit failed candidate document required")
    error_code = document["error_code"]
    if type(error_code) is not str or not error_code or len(error_code) > 256:
        raise ResearchError("bounded public failure code required")
    require_digest(document["private_error_sha256"])
    integer(document["private_error_byte_length"], 1, 2**63 - 1)
    row = DockingSearchRow(
        candidate_id=proposal.candidate_id, proposal_index=proposal.proposal_index,
        proposal_fingerprint_sha256=proposal.fingerprint_sha256,
        result_proposal_fingerprint_sha256="", problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
        search_space_fingerprint_sha256=proposal.search_space_fingerprint_sha256,
        status="failure", score=None, proposal=None,
        validity_context_fingerprint_sha256=authority.validity_context.fingerprint_sha256,
        selection_eligible=False, error_code=error_code,
        error_message="docking candidate execution failed",
        private_error_sha256=document["private_error_sha256"],
        private_error_byte_length=document["private_error_byte_length"], refined=refined)
    expected = row.to_dict()
    exact_fields(document, set(expected))
    if canonical(expected) != canonical(document):
        raise ResearchError("failed candidate identity or failure semantics changed")
    return row

"""Journal one authenticated candidate using the existing search execution path.

Full comparison scheduling/report publication is separate. Saved work describes
the original execution; replay verification/validity checks are current work.
"""
from betelgeuze_engine_v2.docking.search import DockingSearchRow
from .candidate_search import _evaluate_candidate_rows
from betelgeuze_product.cpu_refinement.refinement_comparison import _pose
from .provenance import ResearchError, canonical, decode_coordinates, exact_fields
from .score_replay import restore_score_terms
from .failure_replay import restore_failure_row
from .work import WorkMeter


class CandidateExecution:
    def __init__(self, authority, budget, scorer, proposals, *, refiner=None):
        authority.input_receipt_sha256
        self.authority, self.budget, self.scorer = authority, budget, scorer
        self.proposals = tuple(proposals)
        self.refiner = refiner
        if len(self.proposals) != budget.candidate_count:
            raise ResearchError("candidate execution denominator mismatch")
        if scorer.authority_input_receipt_sha256 != authority.input_receipt_sha256:
            raise ResearchError("candidate scorer authority mismatch")
        if bool(budget.max_refinement_steps) != (refiner is not None):
            raise ResearchError("candidate refinement budget mismatch")

    def compute(self, index):
        proposal = self.proposals[index]
        meter = WorkMeter()
        scorer = self.scorer

        class Measured:
            scorer_id = scorer.scorer_id
            scorer_version = scorer.scorer_version
            validated_for_docking_ranking = scorer.validated_for_docking_ranking

            def score_batch(self, rows):
                # The shared search receives exactly one candidate here.
                if not rows:
                    return ()
                with meter.measure("score.evaluate"):
                    outcomes = scorer.score_batch(rows)
                    if len(outcomes) == 1 and outcomes[0].error is not None:
                        raise outcomes[0].error
                    return outcomes

            def score(self, row):
                with meter.measure("score.evaluate"):
                    return scorer.score(row)

        with meter.measure("search.execute"):
            row, = _evaluate_candidate_rows((proposal,), search_space=self.authority.search_space,
                budget=self.budget, scorer=Measured(), refiner=self.refiner,
                problem_fingerprint=self.authority.problem.fingerprint_sha256,
                context=self.authority.validity_context,
                validity_fingerprint=self.authority.validity_context.fingerprint_sha256,
                unbound_validity_compatibility=False)
        attempt = None if self.refiner is None else self.refiner.attempt_for(proposal.fingerprint_sha256)
        return {"row": _pose(row, row.score_evidence),
                "attempt": None if attempt is None else attempt.to_dict(),
                "refinement_work": None if attempt is None else attempt.work(),
                "execution_work": meter.snapshot()}

    def validate(self, index, record):
        exact_fields(record, {"row", "attempt", "refinement_work", "execution_work"})
        from .evidence_contracts import verify_work, same
        stages = verify_work(record["execution_work"])
        if not set(stages) <= {"search.execute", "score.evaluate"} or record["execution_work"]["counters"]:
            raise ResearchError("unexpected candidate execution work")
        for metric, value in (("calls", 1), ("completed", 1), ("failed", 0)):
            same(stages.get("search.execute", {}).get(metric), value, "candidate execution count")
        proposal = self.proposals[index]
        self.scorer._assert_proposal(proposal)
        current = proposal
        if self.refiner is not None:
            doc, _ = self.refiner.validate_saved_attempt(proposal, record["attempt"], record["refinement_work"],
                                                        max_steps=self.budget.max_refinement_steps)
            if doc["status"] == "success":
                after = decode_coordinates(doc["post_coordinates_binary64_hex"], self.authority.search_space.atom_count)[0]
                current = proposal.with_refined_coordinates(after, refiner_id=self.refiner.refiner_id,
                    refiner_version=self.refiner.refiner_version, refinement_receipt_sha256=doc["receipt_sha256"],
                    torsion_angles=self.refiner._torsion_angles_for(after))
        elif record["attempt"] is not None or record["refinement_work"] is not None:
            raise ResearchError("baseline candidate contains refinement evidence")
        saved = record["row"]
        scored = self.refiner is None or record["attempt"]["status"] == "success"
        same(stages.get("score.evaluate", {}).get("calls", 0), int(scored), "candidate score calls")
        if saved["status"] == "success":
            same(stages.get("score.evaluate", {}).get("completed", 0), 1, "successful score completion")
        if saved["status"] == "failure":
            row_doc = {k: v for k, v in saved.items() if k not in {"terms", "coordinates_sha256", "coordinates_binary64_hex"}}
            row = restore_failure_row(self.authority, proposal, row_doc, refined=current.refined)
            terms = None
        else:
            if self.refiner is not None and record["attempt"]["status"] != "success":
                raise ResearchError("failed refinement cannot produce successful row")
            terms = restore_score_terms(self.scorer, current, saved["terms"])
            validity = self.authority.validity_context.evaluate(current)
            row = DockingSearchRow(candidate_id=current.candidate_id, proposal_index=proposal.proposal_index,
                proposal_fingerprint_sha256=proposal.fingerprint_sha256,
                result_proposal_fingerprint_sha256=current.fingerprint_sha256,
                problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
                search_space_fingerprint_sha256=proposal.search_space_fingerprint_sha256,
                status="success", score=terms.total_score, proposal=current, pose_validity=validity,
                validity_context_fingerprint_sha256=self.authority.validity_context.fingerprint_sha256,
                selection_eligible=validity.valid, refined=current.refined, score_evidence=terms)
        if canonical(_pose(row, terms)) != canonical(saved):
            raise ResearchError("saved candidate row does not reproduce live validity/score/coordinates")
        return row

    def execute(self, journal, index):
        """Return restored row and historical execution record; no hidden new budget."""
        saved = journal.evaluate(index, lambda: self.compute(index))
        row = self.validate(index, saved)
        proposal = self.proposals[index]
        if self.refiner is not None and proposal.fingerprint_sha256 not in self.refiner.attempts:
            try:
                self.refiner.restore_attempt(proposal, saved["attempt"], saved["refinement_work"],
                                             max_steps=self.budget.max_refinement_steps)
            except ResearchError:
                if saved["attempt"]["status"] != "failure" or proposal.fingerprint_sha256 not in self.refiner.replayed_attempts:
                    raise
        return row, saved

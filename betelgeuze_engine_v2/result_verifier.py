"""Offline verification of canonical Engine v2 docking result documents.

The verifier consumes the canonical JSON emitted by ``dock-canonical`` and
recomputes every available nested receipt without re-running the calculation. It
checks:

* canonical raw bytes and the top-level document SHA;
* CLI, interpretable-result, placement, and authenticated-search schemas;
* placement proposal fingerprints against the complete generic search rows;
* every generic search-row document hash retained by the term evidence;
* every successful score-term receipt and bit-exact scalar equality;
* failure rows without fabricated terms;
* candidate, success, failure, top-k, and valid-pose counts;
* all authority, scorer, placement, search, and result cross-links;
* unchanged false calibration, scientific, benchmark, product, customer, and
  claim flags.

The generic search fingerprint itself is retained and cross-linked but cannot be
fully recomputed from the current public report because symmetry mappings are not
expanded in ``DockingSearchResult.to_dict``. The verifier reports this limitation
explicitly and does not promote the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Mapping


CLI_RESULT_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_cli_result_verification/1.0.0"
)
MAX_CLI_RESULT_BYTES = 256 * 1024 * 1024
MAX_CLI_RESULT_JSON_DEPTH = 128
MAX_CLI_RESULT_JSON_NODES = 10_000_000


class CliResultVerificationError(ValueError):
    """The canonical CLI result or one of its nested receipts is invalid."""


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
        raise CliResultVerificationError(
            "result document is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise CliResultVerificationError(f"{name} must be a lowercase SHA-256")
    return text


def _require_dict(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CliResultVerificationError(f"{name} must be a JSON object")
    return value


def _require_list(value: object, *, name: str) -> list[object]:
    if not isinstance(value, list):
        raise CliResultVerificationError(f"{name} must be a JSON array")
    return value


def _exact_int(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CliResultVerificationError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool):
        raise CliResultVerificationError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise CliResultVerificationError(f"{name} must be finite")
    return result


def _reject_duplicate_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CliResultVerificationError(
                f"result document contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def _bounded_walk(value: object, *, depth: int = 0) -> int:
    if depth > MAX_CLI_RESULT_JSON_DEPTH:
        raise CliResultVerificationError(
            "result JSON nesting exceeds the hard bound"
        )
    count = 1
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CliResultVerificationError(
                    "result JSON object keys must be text"
                )
            count += _bounded_walk(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            count += _bounded_walk(item, depth=depth + 1)
    if count > MAX_CLI_RESULT_JSON_NODES:
        raise CliResultVerificationError(
            "result JSON node count exceeds the hard bound"
        )
    return count


def _verify_receipt(
    document: Mapping[str, object],
    *,
    name: str,
    expanded_keys: tuple[str, ...] = (),
    receipt_key: str = "receipt_sha256",
) -> str:
    receipt = _require_sha256(document.get(receipt_key), name=f"{name} {receipt_key}")
    projection = dict(document)
    projection.pop(receipt_key, None)
    for key in expanded_keys:
        projection.pop(key, None)
    observed = _sha256(projection)
    if observed != receipt:
        raise CliResultVerificationError(f"{name} receipt SHA does not match")
    return receipt


def _require_false(document: Mapping[str, object], *keys: str) -> None:
    for key in keys:
        if document.get(key) is not False:
            raise CliResultVerificationError(
                f"result must retain {key}=false"
            )


def _verify_score_terms(document: object) -> tuple[str, str]:
    from .docking import INTERPRETABLE_POSE_SCORE_TERMS_SCHEMA_ID

    terms = _require_dict(document, name="score terms")
    if terms.get("schema_id") != INTERPRETABLE_POSE_SCORE_TERMS_SCHEMA_ID:
        raise CliResultVerificationError("score-term schema is unsupported")
    receipt = _verify_receipt(terms, name="score terms")
    component_keys = (
        "ligand_overlap_penalty_hex",
        "receptor_overlap_penalty_hex",
        "contact_reward_hex",
        "pocket_center_penalty_hex",
        "torsion_penalty_hex",
    )
    parsed: list[float] = []
    for key in (*component_keys, "total_score_hex"):
        value = terms.get(key)
        if not isinstance(value, str):
            raise CliResultVerificationError(
                f"score-term {key} is not a hexadecimal float"
            )
        try:
            number = float.fromhex(value)
        except ValueError as exc:
            raise CliResultVerificationError(
                f"score-term {key} is not a hexadecimal float"
            ) from exc
        if not math.isfinite(number) or number.hex() != value:
            raise CliResultVerificationError(
                f"score-term {key} is non-finite or non-canonical"
            )
        parsed.append(number)
    expected_total = (
        parsed[0] + parsed[1] - parsed[2] + parsed[3] + parsed[4]
    )
    total_hex = str(terms["total_score_hex"])
    if expected_total.hex() != total_hex:
        raise CliResultVerificationError(
            "score-term components do not reproduce the total"
        )
    _require_false(
        terms,
        "calibrated",
        "scientifically_validated",
        "claim_safe",
    )
    return receipt, total_hex


def _verify_scorer_qualification(
    document: object,
    *,
    expected_source_sha256: str,
    expected_contract_sha256: str,
    expected_problem_sha256: str,
    expected_authority_sha256: str,
) -> None:
    qualification = _require_dict(
        document,
        name="scorer qualification",
    )
    fields = {
        "schema_id",
        "scorer_id",
        "scorer_version",
        "score_descriptor",
        "problem_fingerprint_sha256",
        "authority_input_receipt_sha256",
        "implementation_source_sha256",
        "config_fingerprint_sha256",
        "component_contract_fingerprint_sha256",
        "validated_for_docking_ranking",
        "affinity_estimate",
        "free_energy_estimate",
        "calibrated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "claim_safe",
        "document_sha256",
    }
    if set(qualification) != fields:
        raise CliResultVerificationError(
            "scorer qualification fields are invalid"
        )
    if (
        qualification.get("schema_id")
        != "betelgeuze.engine_v2_interpretable_pose_scorer_status/1.0.0"
    ):
        raise CliResultVerificationError(
            "scorer qualification schema is unsupported"
        )
    projection = dict(qualification)
    retained_document_sha = _require_sha256(
        projection.pop("document_sha256"),
        name="scorer qualification document",
    )
    if _sha256(projection) != retained_document_sha:
        raise CliResultVerificationError(
            "scorer qualification document SHA does not match"
        )
    source = _require_sha256(
        qualification.get("implementation_source_sha256"),
        name="scorer qualification source",
    )
    problem = _require_sha256(
        qualification.get("problem_fingerprint_sha256"),
        name="scorer qualification problem",
    )
    authority = _require_sha256(
        qualification.get("authority_input_receipt_sha256"),
        name="scorer qualification authority",
    )
    config = _require_sha256(
        qualification.get("config_fingerprint_sha256"),
        name="scorer qualification config",
    )
    descriptor = _require_dict(
        qualification.get("score_descriptor"),
        name="scorer qualification descriptor",
    )
    contract_projection = {
        "schema_id": "betelgeuze.engine_v2_docking_component_contract/2.0.0",
        "kind": "scorer",
        "id": qualification.get("scorer_id"),
        "version": qualification.get("scorer_version"),
        "class": (
            "betelgeuze_engine_v2.docking.interpretable_scorer."
            "InterpretablePoseScorerV0"
        ),
        "problem_fingerprint_sha256": problem,
        "implementation_source_sha256": source,
        "config_fingerprint_sha256": config,
        "unbound_internal_compatibility": False,
        "validated_for_docking_ranking": False,
        "score_descriptor": descriptor,
    }
    contract = _require_sha256(
        qualification.get("component_contract_fingerprint_sha256"),
        name="scorer qualification contract",
    )
    if _sha256(contract_projection) != contract:
        raise CliResultVerificationError(
            "scorer qualification contract does not match its material"
        )
    if (
        source != expected_source_sha256
        or contract != expected_contract_sha256
        or problem != expected_problem_sha256
        or authority != expected_authority_sha256
    ):
        raise CliResultVerificationError(
            "scorer qualification is cross-wired"
        )
    if qualification.get("validated_for_docking_ranking") is not False:
        raise CliResultVerificationError(
            "scorer qualification overstates ranking validation"
        )
    _require_false(
        qualification,
        "affinity_estimate",
        "free_energy_estimate",
        "calibrated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "claim_safe",
    )


def _verify_term_row(document: object) -> dict[str, object]:
    from .docking import INTERPRETABLE_SEARCH_TERM_ROW_SCHEMA_ID

    row = _require_dict(document, name="retained term row")
    if row.get("schema_id") != INTERPRETABLE_SEARCH_TERM_ROW_SCHEMA_ID:
        raise CliResultVerificationError(
            "retained term-row schema is unsupported"
        )
    receipt = _verify_receipt(
        row,
        name="retained term row",
        expanded_keys=("terms",),
    )
    status = str(row.get("search_status") or "")
    if status not in {"success", "failure"}:
        raise CliResultVerificationError("retained term-row status is invalid")
    score_hex = row.get("score_binary64_hex")
    terms_document = row.get("terms")
    term_receipt = str(row.get("score_terms_receipt_sha256") or "")
    if status == "success":
        if not isinstance(score_hex, str):
            raise CliResultVerificationError(
                "successful term row lacks scalar score"
            )
        try:
            score = float.fromhex(score_hex)
        except ValueError as exc:
            raise CliResultVerificationError(
                "term-row score is not a hexadecimal float"
            ) from exc
        if not math.isfinite(score) or score.hex() != score_hex:
            raise CliResultVerificationError(
                "term-row score is non-finite or non-canonical"
            )
        observed_term_receipt, total_hex = _verify_score_terms(terms_document)
        if observed_term_receipt != _require_sha256(
            term_receipt,
            name="term-row score_terms_receipt_sha256",
        ):
            raise CliResultVerificationError(
                "term-row and expanded score terms are cross-wired"
            )
        if total_hex != score_hex:
            raise CliResultVerificationError(
                "retained terms do not reproduce the scalar bit-exactly"
            )
        if str(row.get("error_code") or ""):
            raise CliResultVerificationError(
                "successful term row contains an error code"
            )
    else:
        if score_hex is not None or terms_document is not None or term_receipt:
            raise CliResultVerificationError(
                "failed term row fabricates score evidence"
            )
        if row.get("selection_eligible") is not False:
            raise CliResultVerificationError(
                "failed term row is selection eligible"
            )
        if row.get("failure_row_retained") is not True:
            raise CliResultVerificationError(
                "failed term row is not marked retained"
            )
    _require_false(row, "calibrated", "scientifically_validated", "claim_safe")
    return {
        "receipt_sha256": receipt,
        "candidate_id": str(row.get("candidate_id") or ""),
        "proposal_index": _exact_int(
            row.get("proposal_index"),
            name="term-row proposal_index",
        ),
        "status": status,
        "search_row_sha256": _require_sha256(
            row.get("search_row_sha256"),
            name="term-row search_row_sha256",
        ),
        "score_hex": score_hex,
        "selection_eligible": bool(row.get("selection_eligible")),
        "error_code": str(row.get("error_code") or ""),
    }


def _verify_generic_search(document: object) -> dict[str, object]:
    search = _require_dict(document, name="generic search result")
    if search.get("schema_id") != "betelgeuze.engine_v2_docking_search_result/1.0.0":
        raise CliResultVerificationError(
            "generic search-result schema is unsupported"
        )
    rows = _require_list(search.get("rows"), name="generic search rows")
    top_ids = _require_list(
        search.get("top_candidate_ids"),
        name="generic top candidate IDs",
    )
    candidate_count = _exact_int(
        search.get("candidate_count"),
        name="generic candidate_count",
    )
    if candidate_count != len(rows):
        raise CliResultVerificationError(
            "generic search candidate count does not match rows"
        )
    success_count = sum(
        _require_dict(row, name="generic search row").get("status") == "success"
        for row in rows
    )
    failure_count = len(rows) - success_count
    if _exact_int(search.get("success_count"), name="generic success_count") != success_count:
        raise CliResultVerificationError("generic success count does not match rows")
    if _exact_int(search.get("failure_count"), name="generic failure_count") != failure_count:
        raise CliResultVerificationError("generic failure count does not match rows")
    candidate_ids: list[str] = []
    proposal_fingerprints: list[str] = []
    raw_score_rank: list[tuple[float, int, str]] = []
    valid_pose_count = 0
    selection_eligible_ids: set[str] = set()
    for raw_row in rows:
        row = _require_dict(raw_row, name="generic search row")
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in candidate_ids:
            raise CliResultVerificationError(
                "generic search candidate IDs are empty or duplicated"
            )
        candidate_ids.append(candidate_id)
        proposal_fingerprints.append(
            _require_sha256(
                row.get("proposal_fingerprint_sha256"),
                name="generic proposal fingerprint",
            )
        )
        status = row.get("status")
        if status not in {"success", "failure"}:
            raise CliResultVerificationError("generic search-row status is invalid")
        if status == "success":
            score = _finite_float(
                row.get("score"), name="generic successful score"
            )
            raw_score_rank.append(
                (
                    score,
                    _exact_int(
                        row.get("proposal_index"),
                        name="generic proposal_index",
                        minimum=0,
                    ),
                    candidate_id,
                )
            )
            if row.get("valid_pose") is True:
                valid_pose_count += 1
            if row.get("selection_eligible") is True:
                selection_eligible_ids.add(candidate_id)
        else:
            if row.get("score") is not None:
                raise CliResultVerificationError(
                    "generic failed row contains a score"
                )
            if row.get("selection_eligible") is not False:
                raise CliResultVerificationError(
                    "generic failed row is selection eligible"
                )
    if _exact_int(search.get("valid_pose_count"), name="generic valid_pose_count") != valid_pose_count:
        raise CliResultVerificationError("generic valid-pose count does not match rows")
    if _exact_int(search.get("selected_count"), name="generic selected_count") != len(top_ids):
        raise CliResultVerificationError("generic selected count does not match top IDs")
    normalized_top = [str(value) for value in top_ids]
    if len(set(normalized_top)) != len(normalized_top):
        raise CliResultVerificationError("generic top candidate IDs are duplicated")
    if not set(normalized_top).issubset(selection_eligible_ids):
        raise CliResultVerificationError(
            "generic top candidates are not selection eligible"
        )
    _require_false(
        search,
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    )
    descriptor = _require_dict(
        search.get("score_descriptor"),
        name="generic score descriptor",
    )
    if descriptor.get("calibrated") is not False:
        raise CliResultVerificationError(
            "generic score descriptor must remain uncalibrated"
        )
    return {
        "document": search,
        "rows": rows,
        "candidate_ids": candidate_ids,
        "proposal_fingerprints": proposal_fingerprints,
        "raw_score_rank_candidate_ids": [
            item[2] for item in sorted(raw_score_rank)
        ],
        "top_candidate_ids": normalized_top,
        "candidate_count": candidate_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "valid_pose_count": valid_pose_count,
        "search_fingerprint_sha256": _require_sha256(
            search.get("search_fingerprint_sha256"),
            name="generic search fingerprint",
        ),
        "problem_fingerprint_sha256": _require_sha256(
            search.get("problem_fingerprint_sha256"),
            name="generic problem fingerprint",
        ),
        "search_space_fingerprint_sha256": _require_sha256(
            search.get("search_space_fingerprint_sha256"),
            name="generic search-space fingerprint",
        ),
        "validity_context_fingerprint_sha256": _require_sha256(
            search.get("validity_context_fingerprint_sha256"),
            name="generic validity-context fingerprint",
        ),
        "scorer_contract_fingerprint_sha256": _require_sha256(
            search.get("scorer_contract_fingerprint_sha256"),
            name="generic scorer-contract fingerprint",
        ),
    }


def _verify_authenticated_search(document: object) -> dict[str, object]:
    from .docking import AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID

    authenticated = _require_dict(document, name="authenticated search result")
    if authenticated.get("schema_id") != AUTHENTICATED_DOCKING_SEARCH_RESULT_SCHEMA_ID:
        raise CliResultVerificationError(
            "authenticated search-result schema is unsupported"
        )
    receipt = _verify_receipt(
        authenticated,
        name="authenticated search result",
        expanded_keys=("search_result",),
    )
    generic = _verify_generic_search(authenticated.get("search_result"))
    crosslinks = {
        "search_fingerprint_sha256": generic["search_fingerprint_sha256"],
        "problem_fingerprint_sha256": generic["problem_fingerprint_sha256"],
        "search_space_fingerprint_sha256": generic["search_space_fingerprint_sha256"],
        "validity_context_fingerprint_sha256": generic["validity_context_fingerprint_sha256"],
    }
    for key, expected in crosslinks.items():
        if _require_sha256(authenticated.get(key), name=f"authenticated {key}") != expected:
            raise CliResultVerificationError(
                f"authenticated search and generic search disagree on {key}"
            )
    for key in ("candidate_count", "success_count", "failure_count", "valid_pose_count"):
        if _exact_int(authenticated.get(key), name=f"authenticated {key}") != generic[key]:
            raise CliResultVerificationError(
                f"authenticated search {key} does not match generic rows"
            )
    _require_false(
        authenticated,
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    )
    return {
        "receipt_sha256": receipt,
        "authenticated_input_receipt_sha256": _require_sha256(
            authenticated.get("authenticated_input_receipt_sha256"),
            name="authenticated input receipt",
        ),
        "generic": generic,
    }


def _verify_placement_receipt(document: object) -> dict[str, object]:
    from .docking import POCKET_PLACEMENT_RECEIPT_SCHEMA_ID

    placement = _require_dict(document, name="placement receipt")
    if placement.get("schema_id") != POCKET_PLACEMENT_RECEIPT_SCHEMA_ID:
        raise CliResultVerificationError("placement receipt schema is unsupported")
    receipt = _verify_receipt(placement, name="placement receipt")
    proposals = _require_list(
        placement.get("proposal_fingerprint_sha256s"),
        name="placement proposal fingerprints",
    )
    proposal_count = _exact_int(
        placement.get("proposal_count"),
        name="placement proposal_count",
        minimum=1,
    )
    if proposal_count != len(proposals):
        raise CliResultVerificationError(
            "placement proposal count does not match fingerprints"
        )
    normalized = [
        _require_sha256(value, name="placement proposal fingerprint")
        for value in proposals
    ]
    offsets = _require_list(
        placement.get("centroid_offset_angstrom_binary64_hex"),
        name="placement centroid offsets",
    )
    if len(offsets) != proposal_count:
        raise CliResultVerificationError(
            "placement centroid offsets do not match proposals"
        )
    for value in offsets:
        try:
            parsed = float.fromhex(str(value))
        except ValueError as exc:
            raise CliResultVerificationError(
                "placement centroid offset is not hexadecimal"
            ) from exc
        if not math.isfinite(parsed) or parsed < 0.0 or parsed.hex() != value:
            raise CliResultVerificationError(
                "placement centroid offset is invalid"
            )
    if placement.get("failure_rows_retained_by_search") is not True:
        raise CliResultVerificationError(
            "placement receipt does not require retained failure rows"
        )
    _require_false(placement, "scientifically_validated", "claim_safe")
    return {
        "receipt_sha256": receipt,
        "authenticated_input_receipt_sha256": _require_sha256(
            placement.get("authenticated_input_receipt_sha256"),
            name="placement authenticated input receipt",
        ),
        "proposal_fingerprints": normalized,
    }


def _verify_placement_search(document: object) -> dict[str, object]:
    from .docking import POCKET_PLACEMENT_SEARCH_RESULT_SCHEMA_ID

    placement_search = _require_dict(document, name="placement search result")
    if placement_search.get("schema_id") != POCKET_PLACEMENT_SEARCH_RESULT_SCHEMA_ID:
        raise CliResultVerificationError(
            "placement search-result schema is unsupported"
        )
    receipt = _verify_receipt(
        placement_search,
        name="placement search result",
        expanded_keys=("placement", "search"),
    )
    placement = _verify_placement_receipt(placement_search.get("placement"))
    authenticated = _verify_authenticated_search(placement_search.get("search"))
    if _require_sha256(
        placement_search.get("placement_receipt_sha256"),
        name="placement-search placement receipt",
    ) != placement["receipt_sha256"]:
        raise CliResultVerificationError(
            "placement search and expanded placement receipt are cross-wired"
        )
    if _require_sha256(
        placement_search.get("authenticated_search_receipt_sha256"),
        name="placement-search authenticated search receipt",
    ) != authenticated["receipt_sha256"]:
        raise CliResultVerificationError(
            "placement search and authenticated search are cross-wired"
        )
    input_receipt = _require_sha256(
        placement_search.get("authenticated_input_receipt_sha256"),
        name="placement-search authenticated input receipt",
    )
    if input_receipt not in {
        placement["authenticated_input_receipt_sha256"],
        authenticated["authenticated_input_receipt_sha256"],
    } or (
        placement["authenticated_input_receipt_sha256"]
        != authenticated["authenticated_input_receipt_sha256"]
    ):
        raise CliResultVerificationError(
            "placement and authenticated search input receipts disagree"
        )
    generic = authenticated["generic"]
    if placement["proposal_fingerprints"] != generic["proposal_fingerprints"]:
        raise CliResultVerificationError(
            "placement proposal batch and generic search rows disagree"
        )
    if _require_sha256(
        placement_search.get("search_fingerprint_sha256"),
        name="placement-search fingerprint",
    ) != generic["search_fingerprint_sha256"]:
        raise CliResultVerificationError(
            "placement search fingerprint is cross-wired"
        )
    _require_false(
        placement_search,
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    )
    return {
        "receipt_sha256": receipt,
        "authenticated_input_receipt_sha256": input_receipt,
        "authenticated_search_receipt_sha256": authenticated["receipt_sha256"],
        "generic": generic,
    }


def _verify_interpretable_result(document: object) -> dict[str, object]:
    from .docking import INTERPRETABLE_SCORED_SEARCH_RESULT_SCHEMA_ID

    result = _require_dict(document, name="interpretable scored search result")
    if result.get("schema_id") != INTERPRETABLE_SCORED_SEARCH_RESULT_SCHEMA_ID:
        raise CliResultVerificationError(
            "interpretable result schema is unsupported"
        )
    receipt = _verify_receipt(
        result,
        name="interpretable scored search result",
        expanded_keys=("rows", "placement_search_result"),
    )
    placement = _verify_placement_search(result.get("placement_search_result"))
    rows = _require_list(result.get("rows"), name="retained term rows")
    retained = [_verify_term_row(row) for row in rows]
    row_receipts = _require_list(
        result.get("row_receipt_sha256s"),
        name="retained row receipt SHA list",
    )
    if [row["receipt_sha256"] for row in retained] != row_receipts:
        raise CliResultVerificationError(
            "retained row receipt list does not match expanded rows"
        )
    generic = placement["generic"]
    if len(retained) != generic["candidate_count"]:
        raise CliResultVerificationError(
            "retained terms do not preserve the search denominator"
        )
    success_count = sum(row["status"] == "success" for row in retained)
    failure_count = len(retained) - success_count
    if _exact_int(result.get("candidate_count"), name="interpretable candidate_count") != len(retained):
        raise CliResultVerificationError(
            "interpretable candidate count does not match rows"
        )
    if _exact_int(result.get("success_count"), name="interpretable success_count") != success_count:
        raise CliResultVerificationError(
            "interpretable success count does not match rows"
        )
    if _exact_int(result.get("failure_count"), name="interpretable failure_count") != failure_count:
        raise CliResultVerificationError(
            "interpretable failure count does not match rows"
        )
    for retained_row, raw_search_row in zip(retained, generic["rows"], strict=True):
        search_row = _require_dict(raw_search_row, name="generic search row")
        if retained_row["candidate_id"] != str(search_row.get("candidate_id") or ""):
            raise CliResultVerificationError(
                "retained and generic candidate identities disagree"
            )
        if retained_row["proposal_index"] != search_row.get("proposal_index"):
            raise CliResultVerificationError(
                "retained and generic proposal indices disagree"
            )
        if retained_row["status"] != search_row.get("status"):
            raise CliResultVerificationError(
                "retained and generic row status disagree"
            )
        if retained_row["search_row_sha256"] != _sha256(search_row):
            raise CliResultVerificationError(
                "retained row does not bind the generic search row"
            )
        if retained_row["status"] == "success":
            if retained_row["score_hex"] != _finite_float(
                search_row.get("score"),
                name="generic successful score",
            ).hex():
                raise CliResultVerificationError(
                    "retained term score and generic scalar disagree"
                )
        elif retained_row["error_code"] != str(search_row.get("error_code") or ""):
            raise CliResultVerificationError(
                "retained and generic failure codes disagree"
            )
    if _require_sha256(
        result.get("placement_search_receipt_sha256"),
        name="interpretable placement-search receipt",
    ) != placement["receipt_sha256"]:
        raise CliResultVerificationError(
            "interpretable and placement search receipts disagree"
        )
    if _require_sha256(
        result.get("authenticated_search_receipt_sha256"),
        name="interpretable authenticated-search receipt",
    ) != placement["authenticated_search_receipt_sha256"]:
        raise CliResultVerificationError(
            "interpretable and authenticated search receipts disagree"
        )
    input_receipt = _require_sha256(
        result.get("authenticated_input_receipt_sha256"),
        name="interpretable authenticated-input receipt",
    )
    if input_receipt != placement["authenticated_input_receipt_sha256"]:
        raise CliResultVerificationError(
            "interpretable and placement input receipts disagree"
        )
    scorer_contract = _require_sha256(
        result.get("scorer_contract_fingerprint_sha256"),
        name="interpretable scorer contract",
    )
    if scorer_contract != generic["scorer_contract_fingerprint_sha256"]:
        raise CliResultVerificationError(
            "interpretable and generic scorer contracts disagree"
        )
    if _require_sha256(
        result.get("scorer_authority_input_receipt_sha256"),
        name="interpretable scorer authority receipt",
    ) != input_receipt:
        raise CliResultVerificationError(
            "interpretable scorer authority is cross-wired"
        )
    if result.get("failure_rows_retained") is not True:
        raise CliResultVerificationError(
            "interpretable result does not retain failure rows"
        )
    _require_false(
        result,
        "calibrated",
        "validated_for_docking_ranking",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    )
    return {
        "receipt_sha256": receipt,
        "authenticated_input_receipt_sha256": input_receipt,
        "candidate_count": len(retained),
        "success_count": success_count,
        "failure_count": failure_count,
        "generic_search_fingerprint_sha256": generic["search_fingerprint_sha256"],
        "generic_problem_fingerprint_sha256": (
            generic["problem_fingerprint_sha256"]
        ),
        "scorer_contract_fingerprint_sha256": scorer_contract,
        "raw_score_rank_candidate_ids": generic[
            "raw_score_rank_candidate_ids"
        ],
        "top_candidate_ids": generic["top_candidate_ids"],
    }


def _verify_pipeline_evidence(
    document: object,
    *,
    candidate_count: int,
    success_count: int,
    failure_count: int,
    raw_score_rank_candidate_ids: list[str],
    top_candidate_ids: list[str],
) -> None:
    from .cli import (
        CANONICAL_DOCKING_PIPELINE_PROFILE_ID,
        build_canonical_docking_pipeline,
    )
    from .pipeline import DOCKING_PIPELINE_EXECUTION_SCHEMA_ID

    evidence = _require_dict(document, name="pipeline evidence")
    expected_fields = {
        "schema_id",
        "pipeline_profile_id",
        "pipeline_profile_sha256",
        "conformer_evidence",
        "proposal_evidence",
        "geometric_admission_evidence",
        "refiner_id",
        "refinement_performed",
        "validity_evidence",
        "ranking_evidence",
        "candidate_denominator_preserved",
        "failure_complete",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
        "receipt_sha256",
    }
    if set(evidence) != expected_fields:
        raise CliResultVerificationError("pipeline evidence fields are invalid")
    pipeline = build_canonical_docking_pipeline()
    if (
        evidence.get("schema_id") != DOCKING_PIPELINE_EXECUTION_SCHEMA_ID
        or evidence.get("pipeline_profile_id")
        != CANONICAL_DOCKING_PIPELINE_PROFILE_ID
        or evidence.get("pipeline_profile_sha256") != pipeline.profile_sha256
        or evidence.get("refiner_id")
        != "betelgeuze.engine_v2.no_refinement/1.0.0"
        or evidence.get("refinement_performed") is not False
        or evidence.get("candidate_denominator_preserved") is not True
        or evidence.get("failure_complete") is not True
    ):
        raise CliResultVerificationError("pipeline profile binding is invalid")
    _verify_receipt(evidence, name="pipeline evidence")
    conformer = _require_dict(
        evidence.get("conformer_evidence"),
        name="pipeline conformer evidence",
    )
    if (
        set(conformer)
        != {
            "provider_id",
            "source_artifact_sha256",
            "available_model_count",
            "selected_model_index",
            "coordinate_generation_performed",
            "result_dependent_selection",
        }
        or conformer.get("provider_id")
        != "betelgeuze.engine_v2.source_coordinate_conformer_provider/1.0.0"
        or conformer.get("coordinate_generation_performed") is not False
        or conformer.get("result_dependent_selection") is not False
        or conformer.get("selected_model_index") != 0
        or _exact_int(
            conformer.get("available_model_count"),
            name="pipeline conformer model count",
            minimum=1,
        )
        < 1
    ):
        raise CliResultVerificationError("pipeline conformer evidence is invalid")
    _require_sha256(
        conformer.get("source_artifact_sha256"),
        name="pipeline conformer source artifact",
    )
    proposal = _require_dict(
        evidence.get("proposal_evidence"),
        name="pipeline proposal evidence",
    )
    admission = _require_dict(
        evidence.get("geometric_admission_evidence"),
        name="pipeline geometric admission evidence",
    )
    if (
        set(proposal)
        != {
            "generator_id",
            "candidate_count",
            "seed",
            "translation_radius_angstrom_binary64_hex",
            "orientation_sequence",
            "allocation_result_independent",
            "candidate_denominator_preserved",
        }
        or proposal.get("generator_id")
        != "betelgeuze.engine_v2.deterministic_haar_pocket_proposal_plan/1.0.0"
        or proposal.get("orientation_sequence")
        != "index_stable_deterministic_haar"
        or _exact_int(
            proposal.get("candidate_count"),
            name="pipeline proposal candidate count",
            minimum=1,
        )
        != candidate_count
        or proposal.get("allocation_result_independent") is not True
        or proposal.get("candidate_denominator_preserved") is not True
        or set(admission)
        != {
            "admission_id",
            "candidate_slot_count",
            "pre_score_candidate_deletion_performed",
            "pose_validity_evaluated_in_search",
            "failure_slots_retained",
        }
        or admission.get("admission_id")
        != "betelgeuze.engine_v2.denominator_preserving_validity_admission/1.0.0"
        or _exact_int(
            admission.get("candidate_slot_count"),
            name="pipeline admission slot count",
            minimum=1,
        )
        != candidate_count
        or admission.get("pre_score_candidate_deletion_performed") is not False
        or admission.get("pose_validity_evaluated_in_search") is not True
        or admission.get("failure_slots_retained") is not True
    ):
        raise CliResultVerificationError(
            "pipeline proposal or admission denominator is invalid"
        )
    validity = _require_dict(
        evidence.get("validity_evidence"),
        name="pipeline validity evidence",
    )
    if (
        set(validity)
        != {
            "evaluator_id",
            "candidate_slot_count",
            "successful_candidate_count",
            "valid_candidate_count",
            "invalid_candidate_count",
            "failure_count",
            "validity_complete",
            "failure_slots_retained",
        }
        or validity.get("evaluator_id")
        != "betelgeuze.engine_v2.element_aware_validity_evaluator/1.0.0"
        or validity.get("candidate_slot_count") != candidate_count
        or validity.get("successful_candidate_count") != success_count
        or validity.get("failure_count") != failure_count
        or validity.get("validity_complete") is not True
        or validity.get("failure_slots_retained") is not True
        or _exact_int(
            validity.get("valid_candidate_count"),
            name="pipeline valid candidate count",
            minimum=0,
        )
        + _exact_int(
            validity.get("invalid_candidate_count"),
            name="pipeline invalid candidate count",
            minimum=0,
        )
        != success_count
    ):
        raise CliResultVerificationError("pipeline validity denominator is invalid")
    ranking = _require_dict(
        evidence.get("ranking_evidence"),
        name="pipeline ranking evidence",
    )
    raw_rank = _require_list(
        ranking.get("raw_score_rank_candidate_ids"),
        name="pipeline raw score rank",
    )
    eligible_rank = _require_list(
        ranking.get("validity_eligible_top_candidate_ids"),
        name="pipeline eligible rank",
    )
    if (
        set(ranking)
        != {
            "ranker_id",
            "raw_score_rank_candidate_ids",
            "validity_eligible_top_candidate_ids",
            "raw_rank_preserves_invalid_candidates",
            "stable_tie_break",
            "result_dependent_reranking",
        }
        or ranking.get("ranker_id")
        != "betelgeuze.engine_v2.raw_and_eligible_stable_ranker/1.0.0"
        or len(raw_rank) != success_count
        or len(raw_rank) != len(set(raw_rank))
        or len(eligible_rank) != len(set(eligible_rank))
        or not set(eligible_rank).issubset(set(raw_rank))
        or raw_rank != raw_score_rank_candidate_ids
        or eligible_rank != top_candidate_ids
        or ranking.get("raw_rank_preserves_invalid_candidates") is not True
        or ranking.get("stable_tie_break")
        != "score_then_proposal_index_then_candidate_id"
        or ranking.get("result_dependent_reranking") is not False
    ):
        raise CliResultVerificationError("pipeline ranking evidence is invalid")
    _require_false(
        evidence,
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
    )


@dataclass(frozen=True, slots=True)
class CliResultVerificationReceipt:
    input_document_sha256: str
    nested_result_receipt_sha256: str
    authenticated_input_receipt_sha256: str
    generic_search_fingerprint_sha256: str
    candidate_count: int
    success_count: int
    failure_count: int
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "input_document_sha256",
            "nested_result_receipt_sha256",
            "authenticated_input_receipt_sha256",
            "generic_search_fingerprint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _require_sha256(getattr(self, name), name=name),
            )
        for name in ("candidate_count", "success_count", "failure_count"):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name),
            )
        if self.success_count + self.failure_count != self.candidate_count:
            raise CliResultVerificationError(
                "verification receipt counts do not preserve the denominator"
            )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": CLI_RESULT_VERIFICATION_SCHEMA_ID,
            "input_document_sha256": self.input_document_sha256,
            "nested_result_receipt_sha256": self.nested_result_receipt_sha256,
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "generic_search_fingerprint_sha256": (
                self.generic_search_fingerprint_sha256
            ),
            "candidate_count": self.candidate_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "canonical_bytes_verified": True,
            "nested_receipts_verified": True,
            "failure_denominator_verified": True,
            "generic_search_fingerprint_fully_recomputed": False,
            "generic_search_fingerprint_crosslinked": True,
            "network_fetch_performed": False,
            "calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise CliResultVerificationError(
                "verification receipt changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


def verify_canonical_cli_result_document(
    document: Mapping[str, object],
) -> CliResultVerificationReceipt:
    from .cli import (
        CLI_COMMAND_ID,
        CLI_DOCKING_RESULT_LEGACY_SCHEMA_ID,
        CLI_DOCKING_RESULT_SCHEMA_ID,
        DISTRIBUTION_VERSION,
        ENGINE_API_VERSION,
        SCORER_SOURCE_BINDING_MODE,
    )

    result_document = _require_dict(document, name="CLI docking result")
    result_schema_id = result_document.get("schema_id")
    if result_schema_id not in {
        CLI_DOCKING_RESULT_LEGACY_SCHEMA_ID,
        CLI_DOCKING_RESULT_SCHEMA_ID,
    }:
        raise CliResultVerificationError("CLI docking-result schema is unsupported")
    if (
        result_schema_id == CLI_DOCKING_RESULT_LEGACY_SCHEMA_ID
        and "pipeline_evidence" in result_document
    ):
        raise CliResultVerificationError(
            "legacy CLI result cannot claim pipeline evidence"
        )
    common_fields = {
        "schema_id",
        "command_id",
        "engine_api_version",
        "distribution_version",
        "receptor_artifact_sha256",
        "ligand_artifact_sha256",
        "pocket_artifact_sha256",
        "pocket_definition_sha256",
        "authenticated_input_receipt_sha256",
        "scorer_source_sha256",
        "scorer_source_binding_mode",
        "scorer_source_preimport_attested",
        "scorer_qualification",
        "result_receipt_sha256",
        "candidate_count",
        "success_count",
        "failure_count",
        "network_fetch_performed",
        "chemistry_inference_performed",
        "pocket_prediction_performed",
        "calibrated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
        "result",
        "document_sha256",
    }
    expected_fields = (
        common_fields | {"pipeline_evidence"}
        if result_schema_id == CLI_DOCKING_RESULT_SCHEMA_ID
        else common_fields
    )
    execution_extension_fields = {
        "execution_parameters",
        "execution_parameters_receipt_sha256",
    }
    observed_fields = set(result_document)
    if observed_fields not in {
        frozenset(expected_fields),
        frozenset(expected_fields | execution_extension_fields),
    }:
        raise CliResultVerificationError("CLI docking-result fields are invalid")
    producer_fields = {
        "command_id": CLI_COMMAND_ID,
        "engine_api_version": ENGINE_API_VERSION,
        "distribution_version": DISTRIBUTION_VERSION,
    }
    for key, expected in producer_fields.items():
        if result_document.get(key) != expected:
            raise CliResultVerificationError(
                f"CLI {key} is unsupported"
            )
    document_sha = _require_sha256(
        result_document.get("document_sha256"),
        name="CLI document_sha256",
    )
    projection = dict(result_document)
    projection.pop("document_sha256", None)
    if _sha256(projection) != document_sha:
        raise CliResultVerificationError("CLI document SHA does not match")
    digests: dict[str, str] = {}
    for name in (
        "receptor_artifact_sha256",
        "ligand_artifact_sha256",
        "pocket_artifact_sha256",
        "pocket_definition_sha256",
        "authenticated_input_receipt_sha256",
        "scorer_source_sha256",
        "result_receipt_sha256",
    ):
        digests[name] = _require_sha256(
            result_document.get(name), name=f"CLI {name}"
        )
    if result_document.get("scorer_source_binding_mode") != SCORER_SOURCE_BINDING_MODE:
        raise CliResultVerificationError("CLI scorer-source binding mode changed")
    if result_document.get("scorer_source_preimport_attested") is not False:
        raise CliResultVerificationError(
            "CLI result overstates scorer source attestation"
        )
    if result_document.get("network_fetch_performed") is not False:
        raise CliResultVerificationError("CLI result reports network activity")
    if result_document.get("chemistry_inference_performed") is not False:
        raise CliResultVerificationError(
            "CLI result reports unsupported chemistry inference"
        )
    if result_document.get("pocket_prediction_performed") is not False:
        raise CliResultVerificationError(
            "CLI result reports unsupported pocket prediction"
        )
    _require_false(
        result_document,
        "calibrated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    )
    nested = _verify_interpretable_result(result_document.get("result"))
    if result_schema_id == CLI_DOCKING_RESULT_SCHEMA_ID:
        _verify_pipeline_evidence(
            result_document.get("pipeline_evidence"),
            candidate_count=int(nested["candidate_count"]),
            success_count=int(nested["success_count"]),
            failure_count=int(nested["failure_count"]),
            raw_score_rank_candidate_ids=list(
                nested["raw_score_rank_candidate_ids"]
            ),
            top_candidate_ids=list(nested["top_candidate_ids"]),
        )
    elif "pipeline_evidence" in result_document:
        raise CliResultVerificationError(
            "legacy CLI result cannot claim pipeline evidence"
        )
    if _require_sha256(
        result_document.get("result_receipt_sha256"),
        name="CLI result receipt",
    ) != nested["receipt_sha256"]:
        raise CliResultVerificationError(
            "CLI and nested result receipts disagree"
        )
    authority = _require_sha256(
        result_document.get("authenticated_input_receipt_sha256"),
        name="CLI authenticated input receipt",
    )
    if authority != nested["authenticated_input_receipt_sha256"]:
        raise CliResultVerificationError(
            "CLI and nested authenticated input receipts disagree"
        )
    _verify_scorer_qualification(
        result_document.get("scorer_qualification"),
        expected_source_sha256=digests["scorer_source_sha256"],
        expected_contract_sha256=(
            nested["scorer_contract_fingerprint_sha256"]
        ),
        expected_problem_sha256=(
            nested["generic_problem_fingerprint_sha256"]
        ),
        expected_authority_sha256=authority,
    )
    for key in ("candidate_count", "success_count", "failure_count"):
        if _exact_int(result_document.get(key), name=f"CLI {key}") != nested[key]:
            raise CliResultVerificationError(
                f"CLI {key} does not match nested rows"
            )
    return CliResultVerificationReceipt(
        input_document_sha256=document_sha,
        nested_result_receipt_sha256=nested["receipt_sha256"],
        authenticated_input_receipt_sha256=authority,
        generic_search_fingerprint_sha256=(
            nested["generic_search_fingerprint_sha256"]
        ),
        candidate_count=nested["candidate_count"],
        success_count=nested["success_count"],
        failure_count=nested["failure_count"],
    )


def verify_canonical_cli_result_bytes(
    raw: bytes,
) -> CliResultVerificationReceipt:
    if not isinstance(raw, bytes):
        raise TypeError("result source must be bytes")
    if not raw or len(raw) > MAX_CLI_RESULT_BYTES:
        raise CliResultVerificationError(
            "result document exceeds its byte bound"
        )
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise CliResultVerificationError(
            "result document has non-canonical line endings"
        )
    try:
        text = canonical.decode("ascii")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliResultVerificationError(
            "result document is invalid JSON"
        ) from exc
    _bounded_walk(document)
    if _canonical_bytes(document) != canonical:
        raise CliResultVerificationError(
            "result document bytes are not canonical"
        )
    return verify_canonical_cli_result_document(
        _require_dict(document, name="CLI docking result")
    )


__all__ = [
    "CLI_RESULT_VERIFICATION_SCHEMA_ID",
    "MAX_CLI_RESULT_BYTES",
    "MAX_CLI_RESULT_JSON_DEPTH",
    "MAX_CLI_RESULT_JSON_NODES",
    "CliResultVerificationError",
    "CliResultVerificationReceipt",
    "verify_canonical_cli_result_bytes",
    "verify_canonical_cli_result_document",
]

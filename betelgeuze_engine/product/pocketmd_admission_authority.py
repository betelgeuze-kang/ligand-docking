"""Authority-backed derivation of authenticated PocketMD admission batches.

The public derivation function is the only code path that can authenticate a
batch.  Validation binds every decision to the complete admission-relevant
population, source position, candidate identity, current selection authority,
and PocketMD policy before a caller can consume it.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import re
import secrets
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from betelgeuze_engine.product.selection_score_authority import (
    SelectionScoreAuthority,
    rank_selection_frame,
    selection_sort_metadata,
    topk_eligible_frame,
)
from betelgeuze_product.pocketmd_lite_contract import (
    PocketMdAdmissionPolicy,
    PocketMdLiteError,
    _decide_pocketmd_admission_from_derived_inputs,
)


POCKETMD_ADMISSION_BATCH_SCHEMA_VERSION = "pocketmd_admission_batch_v1"
_ADMISSION_POPULATION_SCHEMA_VERSION = "pocketmd_admission_population_v1"
_SOURCE_INDEX_COLUMN = "__pocketmd_authority_source_index"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _text(value: Any) -> str:
    canonical = _canonical_scalar(value)
    if canonical is None:
        return ""
    text = str(canonical).strip()
    return "" if text.lower() in {"", "nan", "none", "null", "<na>"} else text


def _mapping_json(payload: str, *, label: str) -> dict[str, Any]:
    if type(payload) is not str:
        raise PocketMdLiteError(f"PocketMD {label} must be canonical JSON")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PocketMdLiteError(f"PocketMD {label} is malformed") from exc
    if not isinstance(value, dict):
        raise PocketMdLiteError(f"PocketMD {label} must be an object")
    return value


@dataclass(frozen=True)
class _DerivedPocketMdAdmission:
    source_index: int
    entry_id: str
    candidate_identity_sha256: str
    population_sha256: str
    selection_policy_sha256: str
    selection_authority_schema_version: str
    policy_sha256: str
    decision_json: str
    authentication_sha256: str

    def decision(self) -> dict[str, Any]:
        return _mapping_json(self.decision_json, label="admission decision")


@dataclass(frozen=True)
class PocketMdAdmissionBatch:
    schema_version: str
    population_sha256: str
    admission_columns: tuple[str, ...]
    entry_id_column: str
    input_count: int
    authority_eligible_count: int
    policy_json: str
    selection_authority_json: str
    receipts: tuple[_DerivedPocketMdAdmission, ...]
    authentication_sha256: str

    def policy(self) -> PocketMdAdmissionPolicy:
        return PocketMdAdmissionPolicy.from_mapping(
            _mapping_json(self.policy_json, label="admission policy")
        )

    def selection_authority(self) -> dict[str, Any]:
        return _mapping_json(
            self.selection_authority_json,
            label="selection authority",
        )


def _receipt_unsigned(receipt: _DerivedPocketMdAdmission) -> dict[str, Any]:
    return {
        "source_index": receipt.source_index,
        "entry_id": receipt.entry_id,
        "candidate_identity_sha256": receipt.candidate_identity_sha256,
        "population_sha256": receipt.population_sha256,
        "selection_policy_sha256": receipt.selection_policy_sha256,
        "selection_authority_schema_version": (
            receipt.selection_authority_schema_version
        ),
        "policy_sha256": receipt.policy_sha256,
        "decision_json": receipt.decision_json,
    }


def _batch_unsigned(batch: PocketMdAdmissionBatch) -> dict[str, Any]:
    return {
        "schema_version": batch.schema_version,
        "population_sha256": batch.population_sha256,
        "admission_columns": list(batch.admission_columns),
        "entry_id_column": batch.entry_id_column,
        "input_count": batch.input_count,
        "authority_eligible_count": batch.authority_eligible_count,
        "policy_json": batch.policy_json,
        "selection_authority_json": batch.selection_authority_json,
        "receipts": [
            {
                **_receipt_unsigned(receipt),
                "authentication_sha256": receipt.authentication_sha256,
            }
            for receipt in batch.receipts
        ],
    }


def _candidate_frame(
    candidates: pd.DataFrame | Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    if isinstance(candidates, pd.DataFrame):
        frame = candidates.copy()
    elif isinstance(candidates, Sequence) and not isinstance(
        candidates, (str, bytes)
    ):
        if any(not isinstance(row, Mapping) for row in candidates):
            raise PocketMdLiteError("PocketMD report candidates must be mappings")
        frame = pd.DataFrame([dict(row) for row in candidates])
    else:
        raise PocketMdLiteError(
            "PocketMD admission candidates must be a frame or mapping sequence"
        )
    if frame.columns.duplicated().any():
        raise PocketMdLiteError("PocketMD admission columns must be unique")
    return frame.reset_index(drop=True)


def _admission_columns(
    population: pd.DataFrame,
    *,
    authority: SelectionScoreAuthority,
    policy: PocketMdAdmissionPolicy,
    entry_id_column: str,
) -> tuple[str, ...]:
    sort_columns = selection_sort_metadata(population, authority)["sort_columns"]
    required = [
        entry_id_column,
        authority.score_column,
        *sort_columns,
        policy.target_column,
        policy.family_column,
        policy.base_proxy_column,
        policy.cost_column,
    ]
    required_columns: list[str] = []
    for column in required:
        name = str(column or "").strip()
        if name and name not in required_columns:
            required_columns.append(name)
    missing = sorted(
        column for column in required_columns if column not in population.columns
    )
    if missing:
        raise PocketMdLiteError(
            f"PocketMD admission population missing columns: {missing}"
        )
    if any(type(column) is not str or not column for column in population.columns):
        raise PocketMdLiteError(
            "PocketMD admission population columns must be non-empty strings"
        )
    # Bind the entire source row, not only columns that influence ranking.  A
    # ligand/pose identity field can be behavior-neutral for admission yet still
    # be essential to prevent a valid decision from being replayed for another
    # molecule with the same score and entry ID.  Refinement outputs are added
    # after admission and therefore do not appear in this source-column set.
    return tuple(population.columns)


def _population_snapshot(
    frame: pd.DataFrame,
    *,
    admission_columns: Sequence[str],
    entry_id_column: str,
    selection_policy_sha256: str,
    policy_sha256: str,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    columns = tuple(str(column) for column in admission_columns)
    if not columns or len(set(columns)) != len(columns):
        raise PocketMdLiteError("PocketMD admission column binding is invalid")
    missing = sorted(column for column in columns if column not in frame.columns)
    if missing:
        raise PocketMdLiteError(
            f"PocketMD admission candidates missing bound columns: {missing}"
        )
    if entry_id_column not in columns:
        raise PocketMdLiteError("PocketMD entry ID is not bound into admission identity")
    entry_ids: list[str] = []
    identity_hashes: list[str] = []
    for source_index in range(len(frame)):
        row = frame.iloc[source_index]
        entry_id = _text(row[entry_id_column])
        if not entry_id:
            raise PocketMdLiteError(
                "PocketMD admission entry IDs must be non-empty and unique"
            )
        row_payload = {
            "schema_version": _ADMISSION_POPULATION_SCHEMA_VERSION,
            "source_index": source_index,
            "entry_id": entry_id,
            "columns": list(columns),
            "values": [_canonical_scalar(row[column]) for column in columns],
            "selection_policy_sha256": selection_policy_sha256,
            "policy_sha256": policy_sha256,
        }
        entry_ids.append(entry_id)
        identity_hashes.append(_sha256(row_payload))
    if len(set(entry_ids)) != len(entry_ids):
        raise PocketMdLiteError(
            "PocketMD admission entry IDs must be non-empty and unique"
        )
    population_payload = {
        "schema_version": _ADMISSION_POPULATION_SCHEMA_VERSION,
        "columns": list(columns),
        "entry_id_column": entry_id_column,
        "selection_policy_sha256": selection_policy_sha256,
        "policy_sha256": policy_sha256,
        "candidate_identity_sha256": identity_hashes,
    }
    return _sha256(population_payload), tuple(entry_ids), tuple(identity_hashes)


def _topk_source_indices(
    ranked_eligible: pd.DataFrame,
    *,
    policy: PocketMdAdmissionPolicy,
) -> set[int]:
    global_indices = {
        int(value)
        for value in ranked_eligible.head(policy.topk_global)[
            _SOURCE_INDEX_COLUMN
        ].tolist()
    }
    target_indices: set[int] = set()
    if policy.topk_per_target > 0:
        target_indices = {
            int(value)
            for _, part in ranked_eligible.groupby(
                policy.target_column,
                sort=False,
                dropna=False,
            )
            for value in part.head(policy.topk_per_target)[
                _SOURCE_INDEX_COLUMN
            ].tolist()
        }
    if policy.selection_mode == "intersection":
        return global_indices & target_indices
    return global_indices | target_indices


def _build_authenticated_authority_api():
    authentication_key = secrets.token_bytes(32)

    def authenticate(payload: Mapping[str, Any]) -> str:
        return hmac.new(
            authentication_key,
            _canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def derive_pocketmd_admission_batch(
        population: pd.DataFrame,
        *,
        authority: SelectionScoreAuthority | Mapping[str, Any],
        policy: PocketMdAdmissionPolicy,
        entry_id_column: str,
    ) -> PocketMdAdmissionBatch:
        """Derive and authenticate decisions from one full current-authority population."""

        if not isinstance(population, pd.DataFrame) or population.empty:
            raise PocketMdLiteError(
                "PocketMD admission population must be a non-empty frame"
            )
        frame = _candidate_frame(population)
        authority_payload = (
            authority.to_dict()
            if isinstance(authority, SelectionScoreAuthority)
            else authority
        )
        current_authority = SelectionScoreAuthority.from_mapping(
            authority_payload,
            require_current=True,
        )
        if not isinstance(policy, PocketMdAdmissionPolicy):
            raise PocketMdLiteError("PocketMD admission policy must be validated")
        current_policy = PocketMdAdmissionPolicy.from_mapping(policy.to_dict())
        if (
            current_policy.selection_policy_sha256
            != current_authority.policy_sha256
            or current_policy.selection_authority_schema_version
            != current_authority.schema_version
        ):
            raise PocketMdLiteError(
                "PocketMD policy does not match Selection Score Authority"
            )
        entry_column = str(entry_id_column or "").strip()
        if not entry_column:
            raise PocketMdLiteError("PocketMD admission entry_id_column is required")
        if _SOURCE_INDEX_COLUMN in frame.columns:
            raise PocketMdLiteError(
                f"PocketMD admission population contains reserved column: {_SOURCE_INDEX_COLUMN}"
            )
        columns = _admission_columns(
            frame,
            authority=current_authority,
            policy=current_policy,
            entry_id_column=entry_column,
        )
        population_sha256, entry_ids, identity_hashes = _population_snapshot(
            frame,
            admission_columns=columns,
            entry_id_column=entry_column,
            selection_policy_sha256=current_authority.policy_sha256,
            policy_sha256=current_policy.policy_sha256,
        )

        ranked_all = rank_selection_frame(
            frame.assign(
                **{_SOURCE_INDEX_COLUMN: np.arange(len(frame), dtype=int)}
            ),
            current_authority,
        )
        eligible_ranked = topk_eligible_frame(ranked_all, current_authority).copy()
        eligible_count = len(eligible_ranked)
        eligible_ranked["__pocketmd_authority_rank_global"] = np.arange(
            1,
            eligible_count + 1,
            dtype=int,
        )
        upstream_source_indices = _topk_source_indices(
            eligible_ranked,
            policy=current_policy,
        )
        rank_by_source = {
            int(row[_SOURCE_INDEX_COLUMN]): int(
                row["__pocketmd_authority_rank_global"]
            )
            for row in eligible_ranked.to_dict(orient="records")
        }

        target_admitted_counts: dict[str, int] = {}
        job_admitted_count = 0
        cumulative_cost = 0.0
        receipts: list[_DerivedPocketMdAdmission] = []
        for row in ranked_all.to_dict(orient="records"):
            source_index = int(row[_SOURCE_INDEX_COLUMN])
            target = _text(row.get(current_policy.target_column))
            rank_global = rank_by_source.get(source_index)
            rank_pct = (
                float(rank_global / eligible_count)
                if rank_global is not None and eligible_count > 0
                else None
            )
            decision = _decide_pocketmd_admission_from_derived_inputs(
                family=_text(row.get(current_policy.family_column)),
                target=target,
                base_proxy_value=row.get(current_policy.base_proxy_column),
                upstream_topk_selected=source_index in upstream_source_indices,
                rank_pct=rank_pct,
                authority_rank_global=rank_global,
                authority_population_size=eligible_count,
                target_selected_count=target_admitted_counts.get(target, 0),
                job_selected_count=job_admitted_count,
                cumulative_cost=cumulative_cost,
                estimated_cost=(
                    row.get(current_policy.cost_column)
                    if current_policy.cost_column
                    else None
                ),
                policy=current_policy,
                selection_authority_bound=True,
            )
            if rank_global is None:
                reasons = ["primary_score_ineligible", *decision["reason_codes"]]
                decision = {
                    **decision,
                    "admitted": False,
                    "reason_codes": list(dict.fromkeys(reasons)),
                    "primary_reason": "primary_score_ineligible",
                }
            if decision["admitted"]:
                target_admitted_counts[target] = (
                    target_admitted_counts.get(target, 0) + 1
                )
                job_admitted_count += 1
                cumulative_cost = float(decision["projected_cumulative_cost"])
            decision["cumulative_cost_after"] = cumulative_cost
            receipt_unsigned = {
                "source_index": source_index,
                "entry_id": entry_ids[source_index],
                "candidate_identity_sha256": identity_hashes[source_index],
                "population_sha256": population_sha256,
                "selection_policy_sha256": current_authority.policy_sha256,
                "selection_authority_schema_version": current_authority.schema_version,
                "policy_sha256": current_policy.policy_sha256,
                "decision_json": _canonical_json(decision),
            }
            receipts.append(
                _DerivedPocketMdAdmission(
                    **receipt_unsigned,
                    authentication_sha256=authenticate(receipt_unsigned),
                )
            )

        batch_unsigned = {
            "schema_version": POCKETMD_ADMISSION_BATCH_SCHEMA_VERSION,
            "population_sha256": population_sha256,
            "admission_columns": list(columns),
            "entry_id_column": entry_column,
            "input_count": len(frame),
            "authority_eligible_count": eligible_count,
            "policy_json": _canonical_json(current_policy.to_dict()),
            "selection_authority_json": _canonical_json(
                current_authority.to_dict()
            ),
            "receipts": [
                {
                    **_receipt_unsigned(receipt),
                    "authentication_sha256": receipt.authentication_sha256,
                }
                for receipt in receipts
            ],
        }
        return PocketMdAdmissionBatch(
            schema_version=batch_unsigned["schema_version"],
            population_sha256=batch_unsigned["population_sha256"],
            admission_columns=columns,
            entry_id_column=entry_column,
            input_count=len(frame),
            authority_eligible_count=eligible_count,
            policy_json=batch_unsigned["policy_json"],
            selection_authority_json=batch_unsigned[
                "selection_authority_json"
            ],
            receipts=tuple(receipts),
            authentication_sha256=authenticate(batch_unsigned),
        )

    def validate_pocketmd_admission_batch(
        batch: PocketMdAdmissionBatch,
        candidates: pd.DataFrame | Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Authenticate a batch and bind it to the supplied candidate population."""

        if type(batch) is not PocketMdAdmissionBatch:
            raise PocketMdLiteError(
                "PocketMD admission batch was not issued by the authority bridge"
            )
        if batch.schema_version != POCKETMD_ADMISSION_BATCH_SCHEMA_VERSION:
            raise PocketMdLiteError("PocketMD admission batch schema is invalid")
        if not _SHA256_RE.fullmatch(str(batch.population_sha256)):
            raise PocketMdLiteError("PocketMD admission population_sha256 is invalid")
        if (
            type(batch.admission_columns) is not tuple
            or not batch.admission_columns
            or any(type(column) is not str or not column for column in batch.admission_columns)
            or len(set(batch.admission_columns)) != len(batch.admission_columns)
        ):
            raise PocketMdLiteError("PocketMD admission column binding is invalid")
        if type(batch.entry_id_column) is not str or not batch.entry_id_column:
            raise PocketMdLiteError("PocketMD admission entry_id_column is required")
        if type(batch.input_count) is not int or batch.input_count < 0:
            raise PocketMdLiteError("PocketMD admission input_count is invalid")
        if type(batch.authority_eligible_count) is not int or not (
            0 <= batch.authority_eligible_count <= batch.input_count
        ):
            raise PocketMdLiteError("PocketMD authority_eligible_count is invalid")
        if type(batch.receipts) is not tuple or len(batch.receipts) != batch.input_count:
            raise PocketMdLiteError("PocketMD admission batch receipt coverage mismatch")
        if not _SHA256_RE.fullmatch(str(batch.authentication_sha256)):
            raise PocketMdLiteError("PocketMD admission batch authentication is invalid")

        policy = batch.policy()
        selection_authority = SelectionScoreAuthority.from_mapping(
            batch.selection_authority(),
            require_current=True,
        )
        if (
            policy.selection_policy_sha256 != selection_authority.policy_sha256
            or policy.selection_authority_schema_version
            != selection_authority.schema_version
        ):
            raise PocketMdLiteError("PocketMD batch authority/policy binding mismatch")
        required_columns = {
            batch.entry_id_column,
            selection_authority.score_column,
            policy.target_column,
            policy.family_column,
            policy.base_proxy_column,
        }
        if policy.cost_column:
            required_columns.add(policy.cost_column)
        if not required_columns.issubset(batch.admission_columns):
            raise PocketMdLiteError(
                "PocketMD batch omits required admission identity columns"
            )

        receipt_by_source: dict[int, _DerivedPocketMdAdmission] = {}
        for receipt in batch.receipts:
            if type(receipt) is not _DerivedPocketMdAdmission:
                raise PocketMdLiteError("PocketMD admission receipt type mismatch")
            if (
                type(receipt.source_index) is not int
                or receipt.source_index < 0
                or receipt.source_index >= batch.input_count
                or receipt.source_index in receipt_by_source
                or type(receipt.entry_id) is not str
                or not receipt.entry_id
            ):
                raise PocketMdLiteError("PocketMD admission receipt identity mismatch")
            hashes = (
                receipt.candidate_identity_sha256,
                receipt.population_sha256,
                receipt.selection_policy_sha256,
                receipt.policy_sha256,
                receipt.authentication_sha256,
            )
            if any(type(value) is not str or not _SHA256_RE.fullmatch(value) for value in hashes):
                raise PocketMdLiteError("PocketMD admission receipt hash is invalid")
            if (
                receipt.population_sha256 != batch.population_sha256
                or receipt.selection_policy_sha256
                != selection_authority.policy_sha256
                or receipt.selection_authority_schema_version
                != selection_authority.schema_version
                or receipt.policy_sha256 != policy.policy_sha256
            ):
                raise PocketMdLiteError("PocketMD admission receipt binding mismatch")
            expected_receipt_authentication = authenticate(
                _receipt_unsigned(receipt)
            )
            if not hmac.compare_digest(
                receipt.authentication_sha256,
                expected_receipt_authentication,
            ):
                raise PocketMdLiteError(
                    "PocketMD admission receipt authentication mismatch"
                )
            decision = receipt.decision()
            if (
                decision.get("policy_sha256") != policy.policy_sha256
                or type(decision.get("admitted")) is not bool
                or not isinstance(decision.get("reason_codes"), list)
            ):
                raise PocketMdLiteError("PocketMD admission receipt decision mismatch")
            receipt_by_source[receipt.source_index] = receipt
        if set(receipt_by_source) != set(range(batch.input_count)):
            raise PocketMdLiteError("PocketMD admission source-index coverage mismatch")

        expected_batch_authentication = authenticate(_batch_unsigned(batch))
        if not hmac.compare_digest(
            batch.authentication_sha256,
            expected_batch_authentication,
        ):
            raise PocketMdLiteError(
                "PocketMD admission batch authentication mismatch"
            )

        frame = _candidate_frame(candidates)
        if len(frame) != batch.input_count:
            raise PocketMdLiteError("PocketMD report candidate coverage mismatch")
        population_sha256, entry_ids, identity_hashes = _population_snapshot(
            frame,
            admission_columns=batch.admission_columns,
            entry_id_column=batch.entry_id_column,
            selection_policy_sha256=selection_authority.policy_sha256,
            policy_sha256=policy.policy_sha256,
        )
        if not hmac.compare_digest(population_sha256, batch.population_sha256):
            raise PocketMdLiteError("PocketMD admission population binding mismatch")

        records: list[dict[str, Any]] = []
        for source_index in range(batch.input_count):
            receipt = receipt_by_source[source_index]
            if (
                receipt.entry_id != entry_ids[source_index]
                or not hmac.compare_digest(
                    receipt.candidate_identity_sha256,
                    identity_hashes[source_index],
                )
            ):
                raise PocketMdLiteError(
                    "PocketMD admission candidate identity mismatch"
                )
            records.append(
                {
                    "source_index": source_index,
                    "entry_id": receipt.entry_id,
                    "candidate_identity_sha256": (
                        receipt.candidate_identity_sha256
                    ),
                    "decision": receipt.decision(),
                }
            )

        # HMACs make accidental mutation evident, but Python introspection is not
        # a security boundary.  Independently re-derive every decision from the
        # validated candidate population so possession of in-process signer
        # material cannot authorize a semantically false admission.
        expected_batch = derive_pocketmd_admission_batch(
            frame,
            authority=selection_authority,
            policy=policy,
            entry_id_column=batch.entry_id_column,
        )
        if (
            expected_batch.population_sha256 != batch.population_sha256
            or expected_batch.admission_columns != batch.admission_columns
            or expected_batch.authority_eligible_count
            != batch.authority_eligible_count
        ):
            raise PocketMdLiteError(
                "PocketMD admission batch semantic population mismatch"
            )
        expected_by_source = {
            receipt.source_index: receipt
            for receipt in expected_batch.receipts
        }
        for source_index, receipt in receipt_by_source.items():
            expected_receipt = expected_by_source[source_index]
            if (
                receipt.entry_id != expected_receipt.entry_id
                or receipt.candidate_identity_sha256
                != expected_receipt.candidate_identity_sha256
                or receipt.decision_json != expected_receipt.decision_json
            ):
                raise PocketMdLiteError(
                    "PocketMD admission decision semantics mismatch"
                )
        return {
            "schema_version": batch.schema_version,
            "population_sha256": batch.population_sha256,
            "entry_id_column": batch.entry_id_column,
            "input_count": batch.input_count,
            "authority_eligible_count": batch.authority_eligible_count,
            "policy": policy,
            "selection_authority": selection_authority.to_dict(),
            "records": tuple(records),
        }

    return derive_pocketmd_admission_batch, validate_pocketmd_admission_batch


(
    derive_pocketmd_admission_batch,
    validate_pocketmd_admission_batch,
) = _build_authenticated_authority_api()
del _build_authenticated_authority_api


__all__ = [
    "POCKETMD_ADMISSION_BATCH_SCHEMA_VERSION",
    "PocketMdAdmissionBatch",
    "derive_pocketmd_admission_batch",
    "validate_pocketmd_admission_batch",
]

"""Canonical, fail-closed authority for product ranking and Top-K admission."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

import pandas as pd


SELECTION_SCORE_AUTHORITY_SCHEMA_VERSION = "selection_score_authority_v1"
DEFAULT_SELECTION_SCORE_COLUMN = "binding_score_composite_v7"
DEFAULT_SELECTION_SOURCE_STAGE = "stage3_backmapping_scoring"
SELECTION_SCORE_DIRECTIONS = frozenset({"ascending", "descending"})
SELECTION_RESIDUAL_MODES = frozenset({"base", "apply"})

_AUTHORITY_FIELDS = frozenset(
    {
        "score_column",
        "score_version",
        "score_direction",
        "residual_mode",
        "source_stage",
        "fallback_used",
        "policy_sha256",
    }
)
_COMPATIBILITY_SCORE_COLUMNS: tuple[str, ...] = (
    "binding_score_composite_v3",
    "binding_score_composite_v2",
    "binding_energy_mmpbsa_kcal_mol_calibrated",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
)
_NUMERIC_TIE_BREAKERS: tuple[tuple[str, str], ...] = (
    ("binding_energy_mmpbsa_kcal_mol_proxy", "ascending"),
    ("stability_score", "descending"),
)
_IDENTITY_TIE_BREAKERS: tuple[str, ...] = (
    "target",
    "ligand_id",
    "queue_id",
    "job_id",
    "replicate_id",
    "seed",
)
_RANKING_POLICY = {
    "numeric_tie_breakers": [list(item) for item in _NUMERIC_TIE_BREAKERS],
    "identity_tie_breakers": list(_IDENTITY_TIE_BREAKERS),
    "nan_policy": "primary_score_nan_sorted_last_and_ineligible_for_topk",
    "final_tie_breaker": "stable_input_order",
}


class SelectionScoreAuthorityError(ValueError):
    """Raised when ranking authority is absent, inconsistent, or unusable."""


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _score_version(score_column: str) -> str:
    match = re.search(r"(?:^|_)(v\d+)(?:_|$)", score_column)
    return str(match.group(1)) if match else score_column


def _residual_mode(score_column: str) -> str:
    return "apply" if score_column.endswith("_residual_active") else "base"


def infer_score_direction(score_column: str) -> str | None:
    """Return a direction only where the score convention is unambiguous."""

    column = str(score_column or "").strip()
    if column == "stability_score":
        return "descending"
    if column.startswith("binding_score_") or column.startswith("binding_energy_"):
        return "ascending"
    return None


def _policy_payload(
    *,
    score_column: str,
    score_version: str,
    score_direction: str,
    residual_mode: str,
    source_stage: str,
    fallback_used: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SELECTION_SCORE_AUTHORITY_SCHEMA_VERSION,
        "authority": {
            "score_column": score_column,
            "score_version": score_version,
            "score_direction": score_direction,
            "residual_mode": residual_mode,
            "source_stage": source_stage,
            "fallback_used": fallback_used,
        },
        "ranking_policy": _RANKING_POLICY,
    }


def _policy_sha256(**kwargs: Any) -> str:
    return hashlib.sha256(_canonical_json(_policy_payload(**kwargs)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SelectionScoreAuthority:
    score_column: str
    score_version: str
    score_direction: str
    residual_mode: str
    source_stage: str
    fallback_used: bool
    policy_sha256: str

    @classmethod
    def create(
        cls,
        *,
        score_column: str,
        score_direction: str,
        source_stage: str = DEFAULT_SELECTION_SOURCE_STAGE,
        fallback_used: bool = False,
    ) -> "SelectionScoreAuthority":
        column = str(score_column or "").strip()
        direction = str(score_direction or "").strip().lower()
        stage = str(source_stage or "").strip()
        version = _score_version(column)
        residual_mode = _residual_mode(column)
        values = {
            "score_column": column,
            "score_version": version,
            "score_direction": direction,
            "residual_mode": residual_mode,
            "source_stage": stage,
            "fallback_used": bool(fallback_used),
        }
        authority = cls(**values, policy_sha256=_policy_sha256(**values))
        authority._validate_semantics()
        return authority

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SelectionScoreAuthority":
        if not isinstance(payload, Mapping):
            raise SelectionScoreAuthorityError("selection score authority must be a mapping")
        keys = frozenset(str(key) for key in payload)
        missing = sorted(_AUTHORITY_FIELDS - keys)
        extra = sorted(keys - _AUTHORITY_FIELDS)
        if missing or extra:
            raise SelectionScoreAuthorityError(
                f"selection score authority fields mismatch: missing={missing}, extra={extra}"
            )
        if type(payload.get("fallback_used")) is not bool:
            raise SelectionScoreAuthorityError("selection score authority fallback_used must be boolean")
        authority = cls(
            score_column=str(payload.get("score_column") or "").strip(),
            score_version=str(payload.get("score_version") or "").strip(),
            score_direction=str(payload.get("score_direction") or "").strip().lower(),
            residual_mode=str(payload.get("residual_mode") or "").strip().lower(),
            source_stage=str(payload.get("source_stage") or "").strip(),
            fallback_used=payload["fallback_used"],
            policy_sha256=str(payload.get("policy_sha256") or "").strip().lower(),
        )
        authority._validate_semantics()
        expected = _policy_sha256(**authority._unsigned_mapping())
        if authority.policy_sha256 != expected:
            raise SelectionScoreAuthorityError("selection score authority policy_sha256 mismatch")
        return authority

    def _unsigned_mapping(self) -> dict[str, Any]:
        return {
            "score_column": self.score_column,
            "score_version": self.score_version,
            "score_direction": self.score_direction,
            "residual_mode": self.residual_mode,
            "source_stage": self.source_stage,
            "fallback_used": self.fallback_used,
        }

    def _validate_semantics(self) -> None:
        if not self.score_column:
            raise SelectionScoreAuthorityError("selection score authority score_column is required")
        if not self.source_stage:
            raise SelectionScoreAuthorityError("selection score authority source_stage is required")
        if self.score_direction not in SELECTION_SCORE_DIRECTIONS:
            raise SelectionScoreAuthorityError(
                f"unsupported selection score direction: {self.score_direction}"
            )
        if self.residual_mode not in SELECTION_RESIDUAL_MODES:
            raise SelectionScoreAuthorityError(
                f"unsupported selection residual mode: {self.residual_mode}"
            )
        if self.score_version != _score_version(self.score_column):
            raise SelectionScoreAuthorityError("selection score authority score_version mismatch")
        if self.residual_mode != _residual_mode(self.score_column):
            raise SelectionScoreAuthorityError("selection score authority residual_mode mismatch")
        inferred_direction = infer_score_direction(self.score_column)
        if inferred_direction and self.score_direction != inferred_direction:
            raise SelectionScoreAuthorityError(
                f"selection score direction for {self.score_column} must be {inferred_direction}"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.policy_sha256):
            raise SelectionScoreAuthorityError("selection score authority policy_sha256 must be lowercase sha256")

    def to_dict(self) -> dict[str, Any]:
        return {**self._unsigned_mapping(), "policy_sha256": self.policy_sha256}


def _usable_numeric(df: pd.DataFrame, column: str) -> bool:
    if column not in df.columns:
        return False
    return bool(pd.to_numeric(df[column], errors="coerce").notna().any())


def validate_authority_for_frame(
    df: pd.DataFrame,
    authority: SelectionScoreAuthority,
) -> None:
    if authority.score_column not in df.columns:
        raise SelectionScoreAuthorityError(
            f"authorized score column missing: {authority.score_column}"
        )
    if not _usable_numeric(df, authority.score_column):
        raise SelectionScoreAuthorityError(
            f"authorized score column has no numeric values: {authority.score_column}"
        )


def resolve_selection_score_authority(
    df: pd.DataFrame,
    *,
    declared_authority: Mapping[str, Any] | None = None,
    requested_score_column: str = "",
    requested_score_direction: str = "",
    residual_metadata: Mapping[str, Any] | None = None,
    source_stage: str = DEFAULT_SELECTION_SOURCE_STAGE,
    allow_compatibility_fallback: bool = False,
) -> SelectionScoreAuthority:
    requested_column = str(requested_score_column or "").strip()
    requested_direction = str(requested_score_direction or "").strip().lower()
    if declared_authority is not None:
        authority = SelectionScoreAuthority.from_mapping(declared_authority)
        if requested_column and requested_column != authority.score_column:
            raise SelectionScoreAuthorityError(
                "requested score column does not match declared selection score authority"
            )
        if requested_direction and requested_direction != authority.score_direction:
            raise SelectionScoreAuthorityError(
                "requested score direction does not match declared selection score authority"
            )
        validate_authority_for_frame(df, authority)
        return authority

    column = requested_column
    if not column and isinstance(residual_metadata, Mapping):
        active_column = str(residual_metadata.get("active_score_col") or "").strip()
        residual_status = str(residual_metadata.get("status") or "").strip().lower()
        residual_runtime_mode = str(
            residual_metadata.get("residual_assist_mode")
            or residual_metadata.get("mode")
            or ""
        ).strip().lower()
        residual_apply_active = bool(
            residual_status in {"apply_ready", "residual_assist_ready"}
            or residual_runtime_mode in {"apply", "apply_ranking", "assist", "production", "production_guarded"}
        )
        if active_column.endswith("_residual_active") and not residual_apply_active:
            raise SelectionScoreAuthorityError(
                "residual-active score authority requires an apply-capable residual mode"
            )
        if active_column in {
            DEFAULT_SELECTION_SCORE_COLUMN,
            f"{DEFAULT_SELECTION_SCORE_COLUMN}_residual_active",
        }:
            column = active_column
    if not column:
        column = DEFAULT_SELECTION_SCORE_COLUMN

    fallback_used = False
    if not _usable_numeric(df, column):
        if requested_column:
            raise SelectionScoreAuthorityError(f"requested score column is missing or non-numeric: {column}")
        if not allow_compatibility_fallback:
            raise SelectionScoreAuthorityError(f"canonical score column is missing or non-numeric: {column}")
        for candidate in _COMPATIBILITY_SCORE_COLUMNS:
            if _usable_numeric(df, candidate):
                column = candidate
                fallback_used = True
                break
        else:
            raise SelectionScoreAuthorityError("no usable compatibility score column found")

    direction = requested_direction or infer_score_direction(column)
    if direction is None:
        raise SelectionScoreAuthorityError(
            f"score direction must be explicit for non-canonical column: {column}"
        )
    authority = SelectionScoreAuthority.create(
        score_column=column,
        score_direction=direction,
        source_stage=source_stage,
        fallback_used=fallback_used,
    )
    validate_authority_for_frame(df, authority)
    return authority


def selection_sort_metadata(
    df: pd.DataFrame,
    authority: SelectionScoreAuthority,
) -> dict[str, Any]:
    validate_authority_for_frame(df, authority)
    columns = [authority.score_column]
    ascending = [authority.score_direction == "ascending"]
    for column, direction in _NUMERIC_TIE_BREAKERS:
        if column not in columns and _usable_numeric(df, column):
            columns.append(column)
            ascending.append(direction == "ascending")
    identity_columns = [column for column in _IDENTITY_TIE_BREAKERS if column in df.columns]
    return {
        "sort_columns": columns + identity_columns,
        "ascending": ascending + [True] * len(identity_columns),
        "nan_position": "last",
        "primary_nan_topk_eligible": False,
    }


def rank_selection_frame(
    df: pd.DataFrame,
    authority: SelectionScoreAuthority,
) -> pd.DataFrame:
    """Sort a frame by the canonical policy without dropping primary-score NaNs."""

    metadata = selection_sort_metadata(df, authority)
    out = df.copy()
    numeric_columns = metadata["sort_columns"][: len(metadata["sort_columns"]) - sum(
        1 for column in _IDENTITY_TIE_BREAKERS if column in df.columns
    )]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    sort_columns = list(numeric_columns)
    ascending = list(metadata["ascending"][: len(numeric_columns)])
    temp_columns: list[str] = []
    for index, column in enumerate(
        item for item in _IDENTITY_TIE_BREAKERS if item in out.columns
    ):
        temp = f"__selection_authority_identity_{index}"
        out[temp] = out[column].map(lambda value: "" if pd.isna(value) else str(value))
        temp_columns.append(temp)
        sort_columns.append(temp)
        ascending.append(True)
    input_order = "__selection_authority_input_order"
    out[input_order] = range(len(out))
    sort_columns.append(input_order)
    ascending.append(True)
    out = out.sort_values(
        sort_columns,
        ascending=ascending,
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)
    return out.drop(columns=[*temp_columns, input_order])


def topk_eligible_frame(
    ranked_df: pd.DataFrame,
    authority: SelectionScoreAuthority,
) -> pd.DataFrame:
    validate_authority_for_frame(ranked_df, authority)
    eligible = pd.to_numeric(ranked_df[authority.score_column], errors="coerce").notna()
    return ranked_df.loc[eligible].reset_index(drop=True).copy()


def authority_from_summary_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("summary") if isinstance(payload, Mapping) else None
    source = summary if isinstance(summary, Mapping) else payload
    authority = source.get("selection_score_authority") if isinstance(source, Mapping) else None
    if not isinstance(authority, Mapping):
        raise SelectionScoreAuthorityError("selection_score_authority missing from summary")
    return authority


def load_authority_summary(path: str) -> Mapping[str, Any]:
    source = str(path or "").strip()
    if not source:
        raise SelectionScoreAuthorityError("selection authority summary path is required")
    try:
        with open(source, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectionScoreAuthorityError(
            f"unable to read selection authority summary: {source}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise SelectionScoreAuthorityError("selection authority summary must be a JSON object")
    return authority_from_summary_payload(payload)


def compatibility_score_columns() -> Sequence[str]:
    return _COMPATIBILITY_SCORE_COLUMNS

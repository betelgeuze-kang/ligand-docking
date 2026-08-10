"""Independent external-engine adapters for validation benchmarks only."""

from __future__ import annotations

from .errors import (
    OracleContractError,
    OracleExecutionError,
    OraclePackError,
    OracleUnavailableError,
)
from .contract import (
    CANONICAL_UNITS,
    OracleRequest,
    OracleResult,
    REQUEST_SCHEMA_ID,
    RESULT_SCHEMA_ID,
    canonical_json_bytes,
    canonical_sha256,
)

__all__ = [
    "OracleContractError",
    "OracleExecutionError",
    "OraclePackError",
    "OracleUnavailableError",
    "CANONICAL_UNITS",
    "OracleRequest",
    "OracleResult",
    "REQUEST_SCHEMA_ID",
    "RESULT_SCHEMA_ID",
    "canonical_json_bytes",
    "canonical_sha256",
]

"""Public, sanitized errors for the external-oracle benchmark pack."""

from __future__ import annotations

import hashlib
from typing import Sequence


class OraclePackError(RuntimeError):
    """Base error for benchmark-only external oracle operations."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OracleUnavailableError(OraclePackError):
    """Raised when an explicitly requested external oracle is unavailable."""

    def __init__(self, oracle: str) -> None:
        super().__init__(
            "oracle_unavailable",
            f"{oracle} external oracle is unavailable in this benchmark environment",
        )


class OracleContractError(OraclePackError, ValueError):
    """Raised when canonical request or result data is invalid."""

    def __init__(
        self, message: str = "external oracle contract validation failed"
    ) -> None:
        super().__init__("contract_invalid", message)


class OracleExecutionError(OraclePackError):
    """Raised for a fail-closed external command failure."""

    def __init__(
        self,
        code: str,
        *,
        argv: Sequence[str] = (),
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int | None = None,
        capture_complete: bool = False,
    ) -> None:
        super().__init__(code, "external oracle execution failed")
        self.argv = tuple(str(value) for value in argv)
        self.stdout = bytes(stdout)
        self.stderr = bytes(stderr)
        self.returncode = returncode
        self.capture_complete = bool(capture_complete)

    @property
    def stdout_sha256(self) -> str:
        return hashlib.sha256(self.stdout).hexdigest()

    @property
    def stderr_sha256(self) -> str:
        return hashlib.sha256(self.stderr).hexdigest()

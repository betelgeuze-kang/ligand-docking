"""Safe public failure receipts with private diagnostic fingerprints."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class FailureReceipt:
    public_error_code: str
    public_message: str
    private_error_sha256: str
    private_error_byte_length: int

    def to_dict(self) -> dict[str, object]:
        return {
            "public_error_code": self.public_error_code,
            "public_message": self.public_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": int(self.private_error_byte_length),
        }


def failure_receipt(
    exc: BaseException,
    *,
    public_message: str = "internal component execution failed",
) -> FailureReceipt:
    """Return a stable public classification without exposing exception text."""

    raw = f"{exc.__class__.__module__}.{exc.__class__.__qualname__}: {exc}".encode(
        "utf-8", errors="replace"
    )
    return FailureReceipt(
        public_error_code=exc.__class__.__name__,
        public_message=str(public_message),
        private_error_sha256=hashlib.sha256(raw).hexdigest(),
        private_error_byte_length=len(raw),
    )


__all__ = ["FailureReceipt", "failure_receipt"]

from __future__ import annotations


class ContractValidationError(ValueError):
    """Raised when an AI-MD contract would allow an unsafe product claim."""

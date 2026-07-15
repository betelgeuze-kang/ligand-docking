from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class AttemptArtifactBinding:
    job_id: str
    results_dir: Path


_CURRENT_ATTEMPT: ContextVar[AttemptArtifactBinding | None] = ContextVar(
    "api_current_job_attempt_artifacts",
    default=None,
)


def token_fingerprint(attempt_token: str) -> str:
    """Return the non-capability identifier safe to persist in artifacts."""

    return hashlib.sha256(attempt_token.encode("utf-8")).hexdigest()


def create_attempt_results_dir(
    *,
    storage_root: str | Path,
    job_id: str,
    worker_id: str,
    attempt_token: str,
    attempt_count: int,
) -> Path:
    """Create an exclusive directory bound to one acquired worker attempt."""

    if not worker_id or not attempt_token or attempt_count < 1:
        raise ValueError("a live worker attempt is required for artifact staging")
    worker_fingerprint = hashlib.sha256(worker_id.encode("utf-8")).hexdigest()
    attempt_fingerprint = token_fingerprint(attempt_token)
    attempts_root = Path(storage_root) / job_id / ".attempts"
    attempts_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    attempt_dir = attempts_root / (
        f"attempt-{attempt_count:06d}-{worker_fingerprint}-{attempt_fingerprint}"
    )
    attempt_dir.mkdir(mode=0o700, exist_ok=False)
    return attempt_dir


def activate_attempt_results_dir(
    job_id: str,
    results_dir: str | Path,
) -> Token[AttemptArtifactBinding | None]:
    return _CURRENT_ATTEMPT.set(
        AttemptArtifactBinding(job_id=job_id, results_dir=Path(results_dir))
    )


def reset_attempt_results_dir(token: Token[AttemptArtifactBinding | None]) -> None:
    _CURRENT_ATTEMPT.reset(token)


def resolve_job_results_dir(job_id: str, storage_root: str | Path) -> Path:
    binding = _CURRENT_ATTEMPT.get()
    if binding is not None and binding.job_id == job_id:
        return binding.results_dir
    return Path(storage_root) / job_id

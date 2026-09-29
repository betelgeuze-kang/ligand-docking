"""Exercise frozen protocols against their pinned pre-3ad331560 source view.

The fixture records the 187 Python source hashes at eb07925cf. Only explicitly
reviewed source changes are projected back to historical
hashes for these protocol-metadata tests; every live byte, including each
reviewed file, and the exact source path set must agree with the current pins.
This view does not execute historical code or authorize the live frozen protocol.
This keeps historical protocol tests useful without changing their frozen seal.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import verify_engine_v2_global_orientation_contaminated_development as verifier


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_COMMIT = "eb07925cfbf517603f967386faa18cacb64456f6"
HISTORICAL_MANIFEST_SHA256 = (
    "7db2a8ba4bdf4c70c941b106892e36aaccd253c6a88d31ac4ef78e73fd416aa7"
)
CURRENT_MANIFEST_SHA256 = (
    "6f8f3797a3b97d3f04cba224a579a3dcd10e108b79dc5ab43e8825a33e95e6c6"
)
HISTORICAL_PROTOCOL_SHA256 = (
    "7ecbb5fa10ce95b035cdc0c11b2c27469caa019aa994315831ad2631cca0fdc3"
)
MANIFEST_FIXTURE = (
    REPOSITORY_ROOT / "tests/fixtures/engine_v2_python_sources_eb07925cf.json"
)

# Pin the complete allowed current delta, including the new bytes of each file.
KNOWN_3AD331560_SOURCE_SHA256 = {
    "betelgeuze_engine_v2/benchmark/public_evaluator_authenticated.py": (
        "6e00e5fbac73b6e30ecf694a268228de2792a118953fe8b8e353434e5cd2b077"
    ),
    "betelgeuze_engine_v2/docking/conformers.py": (
        "5e064f41ffe3a15bedb2d6079ed6057c9e09ea4370ce97795b6d4d399d8abacf"
    ),
    "betelgeuze_engine_v2/io/sdf.py": (
        "f7f72fca33e3dc79017d646ada6f6f51ab5bfc30e3a68e9be1606869a500635a"
    ),
    "betelgeuze_engine_v2/io/writers.py": (
        "1d90b0543039e92698f68de54a0a3c9b72ffa6c8297fdd0277cd8cedd21065cd"
    ),
    "betelgeuze_engine_v2/molecular/validation.py": (
        "e33cd30641aaf07ae9eaf6912525ec50ae0b7abf23e3fa0976a6a4a647b80ba5"
    ),
}


# The canonical-normalization change preserves bytes, SHA identities, diagnostics
# and fresh mutation checks; its differential and real-state evidence is recorded
# in docs/research/cpu_canonical_normalization_20260929.md. Keep the historical
# fixture/protocol seals untouched and continue rejecting any unreviewed byte.
REVIEWED_CURRENT_SOURCE_SHA256 = {
    **KNOWN_3AD331560_SOURCE_SHA256,
    "betelgeuze_engine_v2/molecular/serialization.py": (
        "5a697e413368137308076632437452a7fcb39a1e949f56ace14c749d271195b6"
    ),
}


class HistoricalSourceViewError(ValueError):
    """The pinned historical fixture or allowed current source delta drifted."""


def historical_python_source_rows() -> list[dict[str, str]]:
    payload = json.loads(MANIFEST_FIXTURE.read_text(encoding="utf-8"))
    if set(payload) != {"source_commit", "manifest_sha256", "rows"}:
        raise HistoricalSourceViewError("historical manifest fixture keys drifted")
    if payload["source_commit"] != HISTORICAL_COMMIT:
        raise HistoricalSourceViewError("historical source commit drifted")
    if payload["manifest_sha256"] != HISTORICAL_MANIFEST_SHA256:
        raise HistoricalSourceViewError("historical manifest seal drifted")
    rows = payload["rows"]
    if (
        not isinstance(rows, list)
        or len(rows) != 187
        or any(
            not isinstance(row, dict)
            or set(row) != {"path", "sha256"}
            or type(row["path"]) is not str
            or type(row["sha256"]) is not str
            for row in rows
        )
        or [row["path"] for row in rows] != sorted({row["path"] for row in rows})
        or verifier._sha256(rows) != HISTORICAL_MANIFEST_SHA256
    ):
        raise HistoricalSourceViewError("historical source manifest drifted")
    return rows


def verify_known_live_source_delta() -> dict[str, str]:
    historical = {row["path"]: row["sha256"] for row in historical_python_source_rows()}
    if not set(REVIEWED_CURRENT_SOURCE_SHA256) <= set(historical):
        raise HistoricalSourceViewError("allowed changed source paths are unbound")
    root = REPOSITORY_ROOT / "betelgeuze_engine_v2"
    paths = {
        path.relative_to(REPOSITORY_ROOT).as_posix(): path
        for path in root.rglob("*.py")
    }
    if set(paths) != set(historical):
        raise HistoricalSourceViewError("live Python source path set drifted")
    current_rows = []
    for relative_path in sorted(paths):
        path = paths[relative_path]
        if path.is_symlink() or not path.is_file():
            raise HistoricalSourceViewError(
                f"live Python source is not a regular file: {relative_path}"
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = REVIEWED_CURRENT_SOURCE_SHA256.get(
            relative_path, historical[relative_path]
        )
        if actual != expected:
            raise HistoricalSourceViewError(
                f"unreviewed live Python source drift: {relative_path}"
            )
        current_rows.append({"path": relative_path, "sha256": actual})
    if verifier._sha256(current_rows) != CURRENT_MANIFEST_SHA256:
        raise HistoricalSourceViewError("current Python source manifest drifted")
    return historical


def historical_file_sha256(
    live_file_sha256: Callable[[str], str],
) -> Callable[[str], str]:
    historical = verify_known_live_source_delta()

    def read_hash(relative_path: str) -> str:
        observed = live_file_sha256(relative_path)
        if relative_path in REVIEWED_CURRENT_SOURCE_SHA256:
            if observed != REVIEWED_CURRENT_SOURCE_SHA256[relative_path]:
                raise HistoricalSourceViewError(
                    f"unreviewed live Python source drift: {relative_path}"
                )
            return historical[relative_path]
        return observed

    return read_hash


def verify_historical_protocol_and_live_drift() -> str:
    """CI entry point: require live rejection and historical acceptance."""
    protocol = verifier.load_protocol(
        REPOSITORY_ROOT
        / "config/engine_v2_global_orientation_contaminated_development.json"
    )
    live_file_sha256 = verifier._file_sha256
    historical_reader = historical_file_sha256(live_file_sha256)
    try:
        verifier.verify_protocol(protocol)
    except verifier.GlobalOrientationDevelopmentProtocolError as exc:
        if str(exc) != "pre-import ScorerV1 source manifest drifted":
            raise HistoricalSourceViewError(
                f"unexpected current protocol rejection: {exc}"
            ) from exc
    else:
        raise HistoricalSourceViewError("frozen protocol accepted current source")

    verifier._file_sha256 = historical_reader
    try:
        observed = verifier.verify_protocol(protocol)
    finally:
        verifier._file_sha256 = live_file_sha256
    if observed != HISTORICAL_PROTOCOL_SHA256:
        raise HistoricalSourceViewError("historical protocol identity drifted")
    return observed


if __name__ == "__main__":
    print(verify_historical_protocol_and_live_drift())

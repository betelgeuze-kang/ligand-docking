"""Runtime gate for the versioned installed native v4 replay commands.

Keep the source and comparison imports lazy so incompatible canonicalization
dependencies are rejected before any bound intake is opened.
"""

from __future__ import annotations

import importlib.metadata
import sys

PYTHON_MINOR = (3, 10)
RDKIT_DISTRIBUTION_VERSION = "2022.9.5"
RDKIT_RUNTIME_VERSION = "2022.09.5"


def require_replay_runtime() -> None:
    if sys.version_info[:2] != PYTHON_MINOR:
        raise RuntimeError("native_v4_replay_requires_python_3_10")
    try:
        installed_version = importlib.metadata.version("rdkit-pypi")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("native_v4_replay_requires_rdkit_pypi_2022_9_5") from exc
    if installed_version != RDKIT_DISTRIBUTION_VERSION:
        raise RuntimeError("native_v4_replay_requires_rdkit_pypi_2022_9_5")
    try:
        from rdkit import rdBase
    except ImportError as exc:
        raise RuntimeError("native_v4_replay_requires_rdkit_2022_09_5") from exc
    if rdBase.rdkitVersion != RDKIT_RUNTIME_VERSION:
        raise RuntimeError("native_v4_replay_requires_rdkit_2022_09_5")


def source_main(argv=None) -> int:
    require_replay_runtime()
    from .installed_native_v4_source import main

    return main(argv)


def comparison_main(argv=None) -> int:
    require_replay_runtime()
    from .installed_native_v4_comparison import main

    return main(argv)

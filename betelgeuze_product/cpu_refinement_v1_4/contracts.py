"""Opt-in diagnostic identities over the unchanged Cartesian 1.3 solver."""
import hashlib
from pathlib import Path

from ..cpu_refinement_v1_2.provenance import ResearchError
from ..cpu_refinement_v1_3.contracts import SolverConfig as SolverConfig
from ..cpu_refinement_v1_3.contracts import source_manifest as parent_source_manifest

BINDING_SCHEMA = "cpu_cartesian_diagnostic_run_binding/1.4.0"
RESULT_SCHEMA = "cpu_cartesian_diagnostic_minimization_result/1.4.0"


def source_manifest():
    """Bind the complete parent closure and every opt-in diagnostic module."""
    result = parent_source_manifest()
    folder = Path(__file__).resolve().parent
    for path in sorted(folder.glob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise ResearchError("diagnostic implementation source must be a regular file")
        result["betelgeuze_product/cpu_refinement_v1_4/" + path.name] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return result

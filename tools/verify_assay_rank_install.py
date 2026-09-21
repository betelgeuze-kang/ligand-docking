"""Isolated installed stdlib-only E1/E3 probes; no claim of complete dependencies."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from betelgeuze_product import public_assay_preflight as preflight
from betelgeuze_product import public_assay_components as components
from betelgeuze_product import residual_evidence
from betelgeuze_engine.product import paired_rank_metrics as metric


def verify():
    modules = (preflight, components, residual_evidence, metric)
    assert all(Path(m.__file__).resolve().is_relative_to(Path(sys.prefix)) for m in modules)
    assert not any(n == "tools" or n.startswith("tools.") for n in sys.modules)
    node = {"schema_version": components.SCHEMA, "node_id": "a", "record_id": "a", "keys": [],
            "policy_declarations": [{}], "protected": False, "chemical_identity_available": True,
            "document_identity_available": True, "source": {}}
    assert preflight.preflight([], [node])["results"][0]["status"] == "identity_incomplete"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        context, candidates, output = root / "context", root / "candidates", root / "result"
        context.write_text("")
        candidates.write_text(json.dumps([node]))
        preflight.main(["--context", str(context), "--context-sha256", hashlib.sha256(context.read_bytes()).hexdigest(),
                        "--candidates", str(candidates), "--candidates-sha256", hashlib.sha256(candidates.read_bytes()).hexdigest(),
                        "--output", str(output)])
        result = json.loads(output.read_bytes())
        assert set(result["implementation_sha256"]) == {"preflight", "components", "residual_evidence"}
    summary = metric.compare_cohort({str(i): {"value": i+1, "relation": "="} for i in range(4)},
        {"a": {"0": 0, "1": 2, "2": 1}, "b": {"1": 3, "2": 2, "3": 1}}, [["a", "b"]])
    assert summary["common_coverage"][0]["second_minus_first_on_common_pairs"] == 0
    assert summary["common_coverage"][0]["same_available_candidate_ids"] is False
    return {"installed_stdlib_paths_verified": True, "preflight_and_paired_metric_passed": True,
            "module_sources": {m.__name__: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in modules},
            "full_product_dependencies_verified": False, "scientifically_validated": False}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))

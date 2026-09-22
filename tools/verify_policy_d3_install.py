"""Execute installed D3 adapter outside checkout with isolated Python.

Synthetic inputs are created by the source-side driver. The installed child
loads no tests or source checkout modules. Dependencies may be shared by venv.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture


def verify(python, output):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="installed-policy-d3-") as temporary:
        root = Path(temporary)
        request = request_fixture(root)
        path = root / "request.json"
        path.write_text(json.dumps(request))
        script = """
import json, sys, hashlib
from pathlib import Path
from betelgeuze_product.cpu_refinement_v1_2 import policy_adapter
module = Path(policy_adapter.__file__).resolve()
assert module.is_relative_to(Path(sys.prefix))
request = json.loads(Path(sys.argv[1]).read_bytes())
result = policy_adapter.evaluate(request)
summary = policy_adapter.summarize(result, request=request)
assert summary['status'] == 'evaluated'
assert summary['work']['actual_force_evaluation_calls'] > 0
assert summary['score_quantity'] == policy_adapter.SCORE_QUANTITY
assert any(a['pre_coordinates_sha256'] != a['post_coordinates_sha256'] for a in result['comparison']['attempts'])
print(json.dumps({'module':str(module), 'sha256':hashlib.sha256(module.read_bytes()).hexdigest(), 'summary':summary, 'scientifically_validated':False}))
"""
        run = subprocess.run([str(Path(python).absolute()), "-I", "-c", script, str(path)], cwd=root,
            env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            capture_output=True, text=True, timeout=180)
        (output / "stdout.json").write_text(run.stdout)
        (output / "stderr.log").write_text(run.stderr)
        if run.returncode:
            raise RuntimeError("installed D3 verification failed; see retained logs")
        return json.loads(run.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verify(args.python, args.output_dir)

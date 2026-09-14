"""Fresh-process import boundary and original package export compatibility."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(code):
    code = "import sys;sys.path.insert(0," + repr(str(ROOT)) + ");" + code
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_metadata_adapter_import_does_not_load_physics_or_tensor_runtime():
    result = run("""
import json
from betelgeuze_engine.product import public_assay_selector_shadow as shadow
try:
    shadow.load_public_assay_selector('never-opened.json', expected_sha256='unregistered')
except shadow.SelectorContractError as exc:
    assert str(exc) == 'unregistered_checkpoint_sha256'
print(json.dumps({'torch': 'torch' in sys.modules,
                  'physics': 'betelgeuze_engine.physics' in sys.modules,
                  'numpy': 'numpy' in sys.modules,
                  'rdkit': 'rdkit' in sys.modules}))
""")
    assert result == {"torch": False, "physics": False, "numpy": False, "rdkit": False}


def test_all_legacy_package_exports_keep_defining_identity_and_star_import():
    result = run("""
import json, importlib, pickle
import betelgeuze_engine as engine
expected = {
    'EnergyForces': 'contracts.result', 'TermResult': 'contracts.result',
    'EngineState': 'contracts.state', 'ProductForceField': 'physics.forcefield',
    'ForceTermRegistry': 'physics.forcefield', 'default_force_term_registry': 'physics.forcefield',
    'guarded_force_term_registry': 'physics.forcefield', 'ForceResidualDecision': 'residual.guarded_force',
    'ForceResidualPolicy': 'residual.guarded_force', 'ForceResidualReport': 'residual.guarded_force',
}
assert set(engine.__all__) == set(expected)
assert set(expected).issubset(dir(engine))
for name, path in expected.items():
    value = getattr(engine, name)
    assert value is getattr(importlib.import_module('betelgeuze_engine.' + path), name)
    assert pickle.loads(pickle.dumps(value)) is value
    assert engine.__dict__[name] is value
namespace = {}
exec('from betelgeuze_engine import *', namespace)
assert all(namespace[name] is getattr(engine, name) for name in expected)
print(json.dumps({'exports_checked': len(expected)}))
""")
    assert result["exports_checked"] == 10


def test_unknown_attributes_raise_and_submodule_access_remains_available():
    result = run("""
import json, importlib
import betelgeuze_engine as engine
assert not hasattr(engine, 'unknown_typo')
for name in ['contracts', 'physics', 'residual']:
    assert getattr(engine, name) is importlib.import_module('betelgeuze_engine.' + name)
print(json.dumps({'ok': True}))
""")
    assert result == {"ok": True}

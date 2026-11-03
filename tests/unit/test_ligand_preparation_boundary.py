"""Architecture regression tests, not native execution or containment evidence."""
import ast
import builtins
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

class ResearchBoundaryTests(unittest.TestCase):
    def test_product_converter_has_only_stdlib_imports(self):
        tree = ast.parse((ROOT / 'betelgeuze_product/openmm_fourier_export.py').read_text())
        allowed = {'__future__', 'hashlib', 'json', 'math', 'itertools'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split('.')[0] in allowed for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                self.assertIn(node.module.split('.')[0], allowed)

    def test_no_product_native_shim(self):
        self.assertFalse((ROOT / 'betelgeuze_product/openff_ligand_preparation.py').exists())
        from betelgeuze_product import openmm_fourier_export
        self.assertFalse(hasattr(openmm_fourier_export, 'capture_openmm_ligand'))

    def test_research_modules_import_without_native_dependencies(self):
        original_import = builtins.__import__
        forbidden = {'openmm', 'simtk', 'openff', 'numpy', 'rdkit'}
        def guarded(name, *args, **kwargs):
            if name.split('.')[0] in forbidden:
                raise AssertionError('unexpected native import: ' + name)
            return original_import(name, *args, **kwargs)
        with patch('builtins.__import__', guarded):
            for name in ('benchmarks.oracles.ligand_preparation.openff_sage',
                         'benchmarks.oracles.ligand_preparation.openmm_capture'):
                module = importlib.import_module(name)
                importlib.reload(module)

if __name__ == '__main__':
    unittest.main()

"""Pure-Python policy tests; do not substitute for the actual native fixture run."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).parents[1] / 'betelgeuze_product/openff_ligand_preparation.py'
spec = importlib.util.spec_from_file_location('prep_under_test', MODULE)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

class PreparationPolicyTests(unittest.TestCase):
    def test_missing_input_before_native_import(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'input SDF missing'):
                prep.prepare_sage_ligand(Path(d)/'missing', Path(d)/'out', forcefield_path=Path(d)/'ff')

    def test_wrong_forcefield_before_native_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'mol.sdf').write_text('not run'); (p/'ff').write_text('wrong model')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                prep.prepare_sage_ligand(p/'mol.sdf', p/'out', forcefield_path=p/'ff')
            self.assertFalse((p/'out').exists())

    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'mol.sdf').write_text('not run'); (p/'ff').write_text('test')
            digest=prep.hashlib.sha256((p/'ff').read_bytes()).hexdigest()
            with patch.object(prep, 'SAGE_SHA256', digest):
                with self.assertRaisesRegex(ValueError, 'must be new'):
                    prep.prepare_sage_ligand(p/'mol.sdf',p,forcefield_path=p/'ff')

    def test_normalized_representation_accepted(self):
        expected = {'atoms': [(6, 0, True, None), (7, 0, True, None)], 'bonds': [(0, 1, 2.0, True, None)]}
        # Comparison is of explicitly normalized representations, not raw default flags.
        prep.require_normalized_chemistry(expected, dict(expected))

    def test_real_bond_order_change_rejected(self):
        expected = {'atoms': [(6, 0, True, None), (7, 0, True, None)], 'bonds': [(0, 1, 2.0, True, None)]}
        changed = dict(expected, bonds=[(0, 1, 1.0, True, None)])
        with self.assertRaisesRegex(ValueError, 'normalized ordered chemistry changed'):
            prep.require_normalized_chemistry(expected, changed)

    def test_aromatic_representation_only_allowed(self):
        before = {'atoms': [(6, 0, 0, 0, 0, 0, None)], 'bonds': [(0, 1, 2.0, 'STEREONONE')], 'coordinates': [[1., 2., 3.]], 'atom_aromaticity': [True], 'bond_aromaticity': [True]}
        after = dict(before, atom_aromaticity=[False], bond_aromaticity=[False])
        prep.require_representation_only(before, after)
        for key, change in [('atoms', [(6, 1, 0, 0, 0, 0, None)]), ('bonds', [(0, 1, 1.0, 'STEREONONE')]), ('coordinates', [[2., 2., 3.]])]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'changed chemical state'):
                prep.require_representation_only(before, dict(after, **{key: change}))

    def original(self):
        return '<System><Forces><Force type="NonbondedForce" method="0" useSwitchingFunction="1"><P q="1"/></Force><Force type="CMMotionRemover" frequency="1"/></Forces></System>'
    def derived(self):
        return '<System><Forces><Force type="NonbondedForce" method="0" useSwitchingFunction="0"><P q="1"/></Force></Forces></System>'
    def test_allowed_xml_derivation(self):
        self.assertTrue(prep.verify_static_derivation(self.original(),self.derived()))
    def test_active_coefficient_change_rejected(self):
        self.assertFalse(prep.verify_static_derivation(self.original(),self.derived().replace('q="1"','q="2"')))
    def test_cutoff_model_rejected(self):
        self.assertFalse(prep.verify_static_derivation(self.original().replace('method="0"','method="1"'),self.derived()))
    def test_duplicate_bookkeeping_rejected(self):
        self.assertFalse(prep.verify_static_derivation(self.original().replace('</Forces>','<Force type="CMMotionRemover"/></Forces>'),self.derived()))
    def test_unexpected_force_removal_rejected(self):
        self.assertFalse(prep.verify_static_derivation(self.original().replace('</Forces>','<Force type="CustomForce"/></Forces>'),self.derived()))
    def test_whitespace_only_ignored(self):
        self.assertTrue(prep.verify_static_derivation(self.original().replace('><','>\n  <'),self.derived()))

if __name__ == '__main__': unittest.main()

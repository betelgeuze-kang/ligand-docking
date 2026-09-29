"""Geometry boundary tests; no research outcome or source pose is opened."""
import importlib.util
import copy
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location('ht6_complex_preparer_geometry', Path(__file__).with_name('prepare_complex.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verify_spec = importlib.util.spec_from_file_location('ht6_complex_independent_geometry', Path(__file__).with_name('verify_registration.py'))
verifier = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verifier)


class RegistrationTests(unittest.TestCase):
    def test_resealed_protocol_tolerance_weakening_is_rejected(self):
        modified = copy.deepcopy(module.PROTOCOL)
        modified['all_atom_minimum_radius_sum_ratio'] = 0.01
        with self.assertRaisesRegex(ValueError, 'FROZEN_GEOMETRY_PROTOCOL_CHANGED'):
            verifier.verify_geometry(None, None, None, None, None, modified)

    def test_reflection_scale_and_nonfinite_transforms_rejected(self):
        coordinates = np.array([[0., 1., 0.], [1., 0., 1.]])
        for matrix in (np.diag([-1., 1., 1.]), np.eye(3)*2, np.full((3, 3), np.nan)):
            with self.subTest(matrix=matrix):
                with self.assertRaisesRegex(ValueError, 'INVALID_PROPER_RIGID_TRANSFORM'):
                    module.rigid_transform(coordinates, matrix, np.zeros(3))

    def test_rotation_preserves_pair_distances_and_chirality(self):
        xyz = np.array([[0.,0.,0.], [1.,0.,0.], [0.,2.,0.], [0.,0.,3.]])
        signed_volume = np.linalg.det(xyz[1:]-xyz[0])
        matrices = module.proper_rotations()
        self.assertEqual(len(matrices), 24)
        for matrix in matrices:
            transformed = module.rigid_transform(xyz, matrix, [10., -3., 5.])
            np.testing.assert_allclose(np.linalg.norm(xyz[:,None]-xyz[None,:], axis=2),
                                       np.linalg.norm(transformed[:,None]-transformed[None,:], axis=2), atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(transformed[1:]-transformed[0]), signed_volume)

    def test_collision_and_pocket_membership_are_independent(self):
        receptor = np.array([[0.,0.,0.]])
        colliding = module.geometry_metrics(receptor, ['C'], [[0.5,0.,0.]], ['C'], np.zeros(3))
        distant = module.geometry_metrics(receptor, ['C'], [[20.,0.,0.]], ['C'], np.zeros(3))
        valid = module.geometry_metrics(receptor, ['C'], [[4.,0.,0.]], ['C'], np.zeros(3))
        self.assertFalse(module.accepted(colliding))
        self.assertFalse(module.accepted(distant))
        self.assertTrue(module.accepted(valid))

    def test_element_trees_match_all_pairs_including_hydrogens(self):
        from scipy.spatial import cKDTree
        receptor = np.array([[0.,0.,0.], [1.,2.,0.], [6.,3.,0.], [-2.,-2.,1.]])
        elements = np.array(['C','H','N','O'])
        ligand = np.array([[3.,0.,1.], [4.,1.,2.]])
        trees = {element: cKDTree(receptor[elements == element]) for element in elements}
        first = module.geometry_metrics(receptor, elements, ligand, ['C','H'], np.zeros(3))
        second = module.geometry_metrics(receptor, elements, ligand, ['C','H'], np.zeros(3), trees)
        for key in first:
            self.assertAlmostEqual(first[key], second[key], places=12)

    def test_actual_coordinates_are_registered_and_atom_order_retained(self):
        original = np.array([[100.,0.,0.], [101.4,0.,0.]])
        receptor = np.array([[0.,0.,0.]])
        registered, receipt = module.choose_pose(receptor, ['C'], original, ['C','C'], np.array([5.,0.,0.]))
        np.testing.assert_allclose(registered.mean(axis=0), [5.,0.,0.])
        self.assertAlmostEqual(np.linalg.norm(registered[1]-registered[0]), 1.4)
        self.assertEqual(receipt['selected_ordinal'], 0)
        self.assertTrue(receipt['all_receptor_atoms_explicitly_rechecked_for_selected_pose'])
        reconstructed = module.rigid_transform(original, receipt['rotation_matrix'], receipt['translation_angstrom'])
        np.testing.assert_allclose(registered, reconstructed, atol=0.00005)

    def test_independent_verifier_rejects_relabelled_frame_without_coordinate_transform(self):
        original = np.array([[100.,0.,0.], [101.4,0.,0.]])
        receptor = np.array([[0.,0.,0.]])
        center = np.array([5.,0.,0.])
        registered, receipt = module.choose_pose(receptor, ['C'], original, ['C','C'], center)
        receipt['source_atom_mapping'] = [{'prepared_index_zero_based': i, 'source_index_zero_based': i, 'element': 'C'} for i in range(2)]
        receipt['pocket_center_angstrom'] = center.tolist()
        def as_sdf(xyz):
            header = 'test\nsource\n\n  2  1  0  0  0  0            999 V2000\n'
            rows = ''.join(''.join(f'{x:10.4f}' for x in point)+' C   0  0  0  0  0  0  0  0  0  0  0  0\n' for point in xyz)
            return (header+rows+'  1  2  1  0\nM  END\n$$$$\n').encode()
        result = verifier.verify_geometry(receptor, ['C'], as_sdf(original), as_sdf(registered), receipt, module.PROTOCOL)
        self.assertEqual(result['registered_atoms'], 2)
        renamed = copy.deepcopy(receipt)
        renamed['coordinate_frame_id'] = 'claimed_shared_frame'
        with self.assertRaisesRegex(ValueError, 'WRITTEN_COORDINATES_DO_NOT_MATCH_TRANSFORM'):
            verifier.verify_geometry(receptor, ['C'], as_sdf(original), as_sdf(original), renamed, module.PROTOCOL)
        corrupted = as_sdf(registered).replace(b'  1  2  1  0', b'  1  2  2  0')
        with self.assertRaisesRegex(ValueError, 'NONCOORDINATE_LIGAND_BYTES_CHANGED'):
            verifier.verify_geometry(receptor, ['C'], as_sdf(original), corrupted, receipt, module.PROTOCOL)


if __name__ == '__main__':
    unittest.main()

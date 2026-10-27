"""Stdlib mathematical tests; no engine package/native import or molecule claim."""
from dataclasses import asdict, FrozenInstanceError
import importlib.util
import math
from pathlib import Path
import random
import sys
import unittest

PATH = Path(__file__).resolve().parents[2] / "betelgeuze_product/structure_preserving.py"
SPEC = importlib.util.spec_from_file_location("_structure_preserving_owning_tests", PATH)
assert SPEC is not None and SPEC.loader is not None
m = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = m
SPEC.loader.exec_module(m)

X = ((0.,0.,0.), (1.3,.2,.1), (2.2,1.1,.4), (2.8,1.4,1.6),
     (1.5,-.8,.7), (3.3,2.1,1.4), (-.4,.8,-.2))
BONDS = ((0,1,"single"), (1,2,"single"), (2,3,"single"), (1,4,"single"),
         (3,5,"single"), (0,6,"single"))
TOPOLOGY = m.StructureTopology(len(X), BONDS, ((1,2),(2,3)))


def distance(a, b):
    return math.dist(a, b)


def volume(points, center, a, b, c):
    u, v, w = [tuple(points[i][j]-points[center][j] for j in range(3)) for i in (a,b,c)]
    return (u[0]*(v[1]*w[2]-v[2]*w[1]) - u[1]*(v[0]*w[2]-v[2]*w[0])
            + u[2]*(v[0]*w[1]-v[1]*w[0]))


def harmonic(target):
    def evaluate(points):
        weights = tuple(0.7 + i*.31 for i in range(len(points)))
        forces = tuple(tuple(-k*(x-y) for x,y in zip(p,t)) for k,p,t in zip(weights,points,target))
        energy = math.fsum(.5*k*math.fsum((x-y)**2 for x,y in zip(p,t))
                           for k,p,t in zip(weights,points,target))
        return m.Evaluation(energy, forces)
    return evaluate


class StructurePreservingTests(unittest.TestCase):
    def assertPointsClose(self, first, second, tolerance=2.e-12):
        for a,b in zip(first,second):
            self.assertLessEqual(distance(a,b), tolerance)

    def test_rigid_pair_distances_and_chirality(self):
        moved = m.rigid_move(X, translation=(.5,-.3,.2), rotation=(.3,-.2,.4), pivot=(1.,-.5,.3))
        for i in range(len(X)):
            for j in range(i):
                self.assertAlmostEqual(distance(X[i],X[j]), distance(moved[i],moved[j]), places=12)
        self.assertAlmostEqual(volume(X,1,0,2,4),volume(moved,1,0,2,4),places=12)

    def test_inverse_rigid_rotation(self):
        pivot=(1.,-.5,.3)
        moved=m.rigid_move(X, rotation=(.3,-.2,.4),pivot=pivot)
        self.assertPointsClose(X,m.rigid_move(moved,rotation=(-.3,.2,-.4),pivot=pivot))

    def test_rigid_zero_exact_identity(self):
        self.assertEqual(m.rigid_move(X), X)

    def test_move_component_is_full_branch(self):
        self.assertEqual(TOPOLOGY.moving_atoms(0),(2,3,5))
        self.assertEqual(TOPOLOGY.moving_atoms(1),(3,5))
        after=m.torsion_move(X,TOPOLOGY,0,.8)
        for index in (0,1,2,4,6):
            self.assertEqual(X[index],after[index])
        self.assertGreater(distance(X[3],after[3]),.1)

    def test_torsion_bonds_and_local_stereo(self):
        after=m.torsion_move(X,TOPOLOGY,0,.8)
        for i,j,_ in BONDS:
            self.assertAlmostEqual(distance(X[i],X[j]),distance(after[i],after[j]),places=12)
        self.assertAlmostEqual(volume(X,1,0,2,4),volume(after,1,0,2,4),places=12)

    def test_nested_current_axes_and_inverse(self):
        first=m.torsion_move(X,TOPOLOGY,0,.73)
        second=m.torsion_move(first,TOPOLOGY,1,-.81)
        undone=m.torsion_move(m.torsion_move(second,TOPOLOGY,1,.81),TOPOLOGY,0,-.73)
        self.assertPointsClose(X,undone)
        for i,j,_ in BONDS:
            self.assertAlmostEqual(distance(X[i],X[j]),distance(second[i],second[j]),places=12)

    def test_torsion_preserves_side_ring_geometry(self):
        points=((0.,0.,0.),(1.,0.,0.),(2.,1.,0.),(2.,0.,1.))
        top=m.StructureTopology(4,((0,1,"single"),(1,2,"aromatic"),(2,3,"aromatic"),
                                   (1,3,"aromatic")),((0,1),))
        moved=m.torsion_move(points,top,0,.4)
        for i in (1,2,3):
            for j in (1,2,3):
                self.assertAlmostEqual(distance(points[i],points[j]),distance(moved[i],moved[j]),places=12)

    def test_ring_rotor_rejected(self):
        with self.assertRaises(m.StructureSearchError):
            m.StructureTopology(3,((0,1,"single"),(1,2,"single"),(2,0,"single")),((0,1),))

    def test_unsupported_and_duplicate_rotors(self):
        for kind in ("double","triple","aromatic","amide","other"):
            with self.subTest(kind=kind), self.assertRaises(m.StructureSearchError):
                m.StructureTopology(2,((0,1,kind),),((0,1),))
        with self.assertRaises(m.StructureSearchError):
            m.StructureTopology(2,((0,1,"single"),),((0,1),(1,0)))

    def test_authority_does_not_auto_enumerate_single_bonds(self):
        top=m.StructureTopology(len(X),BONDS)
        self.assertEqual(top.rotatable_bonds,())

    def test_topology_defensive_copy_and_frozen(self):
        edges=[[0,1,"single"]]
        rotors=[[0,1]]
        top=m.StructureTopology(2,edges,rotors)
        edges[0][2]="double"
        rotors.clear()
        self.assertEqual(top.bonds,((0,1,"single"),))
        self.assertEqual(top.rotatable_bonds,((0,1),))
        with self.assertRaises(FrozenInstanceError):
            top.atom_count=3

    def test_bad_topologies(self):
        cases=((0,(),()),(True,(),()),(513,(),()),(2,(),()),
               (2,((0,0,"single"),),()),(2,((0,1,"single"),(1,0,"single")),()),
               (2,((0,1,"bad"),),()),(2,((0,1,"single"),),((0,2),)))
        for args in cases:
            with self.subTest(args=args), self.assertRaises(m.StructureSearchError):
                m.StructureTopology(*args)

    def test_all_generalized_forces_multi_h(self):
        target=tuple((p[0]+.17*(i+1),p[1]-.23,p[2]+.11*i) for i,p in enumerate(X))
        evaluate=harmonic(target)
        states=(X,m.rigid_move(m.torsion_move(m.torsion_move(X,TOPOLOGY,0,.6),TOPOLOGY,1,-.4),
                               translation=(.1,-.2,.3),rotation=(.8,-.3,.2)))
        for points in states:
            projection=m.project_forces(points,evaluate(points).forces,TOPOLOGY)
            for h in (1.e-4,1.e-5,1.e-6):
                for axis in range(3):
                    inc=tuple(h if j==axis else 0. for j in range(3))
                    neg=tuple(-x for x in inc)
                    for name in ("translation","rotation"):
                        plus=m.rigid_move(points,**{name:inc})
                        minus=m.rigid_move(points,**{name:neg})
                        fd=-(evaluate(plus).energy-evaluate(minus).energy)/(2*h)
                        self.assertAlmostEqual(getattr(projection,name)[axis],fd,delta=2.e-7)
                for rotor,q in enumerate(projection.torsions):
                    plus=m.torsion_move(points,TOPOLOGY,rotor,h)
                    minus=m.torsion_move(points,TOPOLOGY,rotor,-h)
                    fd=-(evaluate(plus).energy-evaluate(minus).energy)/(2*h)
                    self.assertAlmostEqual(q,fd,delta=2.e-7)

    def test_force_shape_and_nan_rejected(self):
        for forces in ((), ((float("nan"),0.,0.),)*len(X), ((0.,0.),)*len(X)):
            with self.subTest(forces=forces),self.assertRaises(m.StructureSearchError):
                m.project_forces(X,forces,TOPOLOGY)

    def test_axis_endpoint_is_exactly_zero_torsion_derivative(self):
        points=((0.,0.,0.),(-2.9263305156121473,-2.3256068335185853,-.6429758306955446))
        top=m.StructureTopology(2,((0,1,"single"),),((0,1),))
        projection=m.project_forces(points,((0.,0.,0.),(1.e20,3.e20,7.e20)),top)
        self.assertEqual(projection.torsions,(0.,))
        self.assertEqual(m.torsion_move(points,top,0,.7),points)

    def test_degenerate_preflight_no_callback(self):
        top=m.StructureTopology(2,((0,1,"single"),),((0,1),))
        calls=[]
        with self.assertRaises(m.StructureSearchError):
            m.refine_structure(((0.,0.,0.),(0.,0.,0.)),top,lambda x:calls.append(x))
        self.assertEqual(calls,[])

    def test_oversized_and_nonfinite_moves(self):
        for value in (float("nan"),float("inf"),True,"1"):
            with self.subTest(value=value),self.assertRaises(m.StructureSearchError):
                m.torsion_move(X,TOPOLOGY,0,value)
        with self.assertRaises(m.StructureSearchError):
            m.rigid_move(X,rotation=(4.,0.,0.))
        with self.assertRaises(m.StructureSearchError):
            m.rigid_move(((1.e7,0.,0.),))

    def test_translation_refinement_reproducible_and_monotone(self):
        target=m.rigid_move(X,translation=(.3,-.1,.2))
        # Uniform force isolates translation while retaining full topology.
        def evaluate(points):
            forces=tuple(tuple(t-p for p,t in zip(row,goal)) for row,goal in zip(points,target))
            return m.Evaluation(.5*sum(v*v for row in forces for v in row),forces)
        config=m.SearchConfig(max_steps=30,max_evaluations=150,translation_force_tolerance=1.e-4)
        first=m.refine_structure(X,TOPOLOGY,evaluate,config)
        second=m.refine_structure(X,TOPOLOGY,evaluate,config)
        self.assertEqual(first,second)
        self.assertLess(first.energy,first.initial_energy)
        accepted=[r.energy for r in first.history if r.status in ("initial","accepted")]
        self.assertTrue(all(b<a for a,b in zip(accepted,accepted[1:])))
        self.assertLessEqual(first.evaluation_attempts,150)
        self.assertEqual(first.evaluation_attempts,len(first.history))
        self.assertEqual(X[0],(0.,0.,0.))

    def test_projected_stationary_not_cartesian(self):
        points=((-1.,0.,0.),(1.,0.,0.))
        top=m.StructureTopology(2,((0,1,"single"),))
        result=m.refine_structure(points,top,lambda p:m.Evaluation(1.,((1.,0.,0.),(-1.,0.,0.))))
        self.assertEqual(result.status,"projected_stationary")
        self.assertTrue(result.projected_stationary)
        self.assertEqual(result.evaluation_attempts,1)
        self.assertNotEqual(result.forces,((0.,0.,0.),)*2)

    def test_initial_failure_preserves_state_and_counts(self):
        def failing(points):
            raise RuntimeError("private backend details")
        result=m.refine_structure(X,TOPOLOGY,failing)
        self.assertEqual((result.evaluation_attempts,result.successful_evaluations,result.failed_evaluations),(1,0,1))
        self.assertEqual(result.coordinates,X)
        self.assertIsNone(result.energy)
        self.assertNotIn("private",repr(result))

    def test_trial_failure_retains_last_accepted_state(self):
        calls=[]
        def failing(points):
            calls.append(points)
            if len(calls)==3:
                raise RuntimeError("do not leak")
            return m.Evaluation(-sum(p[0] for p in points),((1.,0.,0.),)*len(points))
        result=m.refine_structure(X,TOPOLOGY,failing)
        self.assertEqual(result.accepted_steps,1)
        self.assertEqual(result.coordinates,calls[1])
        self.assertEqual(result.status,"evaluation_failed")
        self.assertEqual(result.evaluation_attempts,3)
        self.assertEqual(result.failed_evaluations,1)

    def test_malformed_callback_is_charged(self):
        for callback in (lambda p:None, lambda p:m.Evaluation(0.,((0.,0.,0.),))):
            result=m.refine_structure(X,TOPOLOGY,callback)
            self.assertEqual(result.status,"evaluation_failed")
            self.assertEqual(result.evaluation_attempts,1)

    def test_rejected_evaluations_charge_exact_budget(self):
        def inconsistent(points):
            return m.Evaluation(0.,((1.,0.,0.),)*len(points))
        result=m.refine_structure(X,TOPOLOGY,inconsistent,m.SearchConfig(max_evaluations=3))
        self.assertEqual(result.status,"evaluation_limit")
        self.assertEqual(result.evaluation_attempts,3)
        self.assertEqual([r.status for r in result.history],["initial","rejected","rejected"])
        self.assertEqual(result.coordinates,X)

    def test_backtrack_limit_has_no_hidden_final_call(self):
        result=m.refine_structure(X,TOPOLOGY,lambda p:m.Evaluation(0.,((1.,0.,0.),)*len(p)),
                                 m.SearchConfig(max_backtracks=2))
        self.assertEqual(result.status,"line_search_failed")
        self.assertEqual(result.evaluation_attempts,4)

    def test_initial_only_budget(self):
        result=m.refine_structure(X,TOPOLOGY,lambda p:m.Evaluation(0.,((1.,0.,0.),)*len(p)),
                                 m.SearchConfig(max_evaluations=1))
        self.assertEqual(result.status,"evaluation_limit")
        self.assertEqual(result.evaluation_attempts,1)

    def test_step_limit(self):
        result=m.refine_structure(X,TOPOLOGY,lambda p:m.Evaluation(-sum(row[0] for row in p),
                                 ((1.,0.,0.),)*len(p)),m.SearchConfig(max_steps=1))
        self.assertEqual(result.status,"step_limit")
        self.assertEqual((result.accepted_steps,result.evaluation_attempts),(1,2))

    def test_no_representable_step_no_trial_call(self):
        points=((1.e6,0.,0.),)
        result=m.refine_structure(points,m.StructureTopology(1,()),
                                 lambda p:m.Evaluation(0.,((1.,0.,0.),)),
                                 m.SearchConfig(translation_step_angstrom=1.e-100))
        self.assertEqual(result.status,"no_representable_step")
        self.assertEqual(result.evaluation_attempts,1)
        self.assertEqual(result.coordinates,points)

    def test_geometry_guard_retains_state_before_evaluation(self):
        from unittest.mock import patch
        bad=((X[0][0]-.5,X[0][1],X[0][2]),)+X[1:]
        with patch.object(m,"rigid_move",return_value=bad):
            result=m.refine_structure(X,TOPOLOGY,
                                     lambda p:m.Evaluation(0.,((1.,0.,0.),)*len(p)))
        self.assertEqual(result.status,"geometry_failure")
        self.assertEqual(result.evaluation_attempts,1)
        self.assertEqual(result.coordinates,X)

    def test_cumulative_translation_bound(self):
        points=((0.,0.,0.),)
        result=m.refine_structure(points,m.StructureTopology(1,()),
                                 lambda p:m.Evaluation(-p[0][0],((1.,0.,0.),)),
                                 m.SearchConfig(max_steps=64,max_total_translation_angstrom=.25))
        self.assertEqual(result.status,"motion_limit")
        self.assertAlmostEqual(result.coordinates[0][0],.25)
        self.assertEqual(result.accepted_steps,3)

    def test_capped_torsion_does_not_chase_subtolerance_rigid_noise(self):
        points=((0.,1.,.2),(0.,0.,0.),(1.,0.,0.),(1.,.3,1.))
        top=m.StructureTopology(4,((0,1,"single"),(1,2,"single"),(2,3,"single")),((1,2),))
        def internal_only(p):
            d=tuple(p[3][i]-p[0][i] for i in range(3))
            return m.Evaluation(.5*sum(v*v for v in d),
                                (d,(0.,0.,0.),(0.,0.,0.),tuple(-v for v in d)))
        result=m.refine_structure(points,top,internal_only,
                                 m.SearchConfig(torsion_step_radians=.03,max_total_torsion_radians=.11))
        self.assertEqual(result.status,"motion_limit")
        self.assertEqual((result.accepted_steps,result.evaluation_attempts),(4,5))
        self.assertTrue(all(row.move=="torsion:0" for row in result.history[1:]))

    def test_random_sequence_invariants(self):
        rng=random.Random(20261027)
        points=X
        for _ in range(100):
            points=m.torsion_move(points,TOPOLOGY,rng.randrange(2),rng.uniform(-.2,.2))
            points=m.rigid_move(points,translation=tuple(rng.uniform(-.02,.02) for _ in range(3)),
                                rotation=tuple(rng.uniform(-.05,.05) for _ in range(3)))
        for i,j,_ in BONDS:
            self.assertAlmostEqual(distance(X[i],X[j]),distance(points[i],points[j]),places=11)
        self.assertAlmostEqual(volume(X,1,0,2,4),volume(points,1,0,2,4),places=11)

    def test_bad_config(self):
        for kwargs in ({"max_steps":True},{"max_evaluations":0},{"max_backtracks":25},
                       {"rotation_step_radians":4.},{"armijo":0.},
                       {"angular_force_tolerance":float("nan")},
                       {"max_total_rotation_radians":.01}):
            with self.subTest(kwargs=kwargs),self.assertRaises(m.StructureSearchError):
                m.SearchConfig(**kwargs)

    def test_json_compatible_config(self):
        import json
        self.assertIn("max_evaluations",json.loads(json.dumps(asdict(m.SearchConfig()),allow_nan=False)))


if __name__ == "__main__":
    unittest.main()

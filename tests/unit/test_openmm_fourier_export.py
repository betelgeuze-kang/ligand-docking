"""Synthetic coefficients only; no OpenMM/RDKit/Torch import or molecule run."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

p=Path(__file__).resolve().parents[2]/'betelgeuze_product/openmm_fourier_export.py'
spec=importlib.util.spec_from_file_location('export_under_test',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def source():
    atoms=['C1','C2','C3','C4']
    return dict(schema_id=m.SOURCE_SCHEMA,
                source=dict(parameterizer='synthetic',version='test1',system_xml_sha256='a'*64,
                            forcefield_sha256='b'*64,charge_method='test',chemical_state_id='test',
                            atom_mapping_sha256=m.digest(atoms),openmm_version='synthetic'),atom_ids=atoms,
                particles=[dict(atom_index=i,charge_e=q,sigma_nm=.3,epsilon_kj_per_mol=.4)
                           for i,q in enumerate([.2,-.3,.4,-.3])],
                bonds=[dict(source_term_id=f'b{i}',atoms=[i,i+1],length_nm=.15,k_kj_per_mol_nm2=41840.) for i in range(3)],
                angles=[dict(source_term_id=f'a{i}',atoms=[i,i+1,i+2],theta_radians=1.9,k_kj_per_mol_radian2=418.4) for i in range(2)],
                torsions=[dict(source_term_id='t0',atoms=[0,1,2,3],kind='proper',star_center=None,
                               periodicity=3,phase_radians=.7,k_kj_per_mol=8.368)],
                exceptions=[dict(source_term_id=f'e{i}{j}',atoms=[i,j],charge_product_e2=0.,sigma_nm=.1,epsilon_kj_per_mol=0.)
                            for i,j in [(0,1),(1,2),(2,3),(0,2),(1,3)]],
                bond_graph=[[0,1],[1,2],[2,3]],
                force_inventory=dict(HarmonicBondForce=3,HarmonicAngleForce=2,PeriodicTorsionForce=1,NonbondedForce=4),
                constraints=[],virtual_sites=[],force_metadata={f:dict(instances=1,uses_periodic_boundary_conditions=False) for f in m.FORCES},
                nonbonded=dict(method='NoCutoff',periodic=False,switching=False,dispersion_correction=True,
                               particle_offsets=[],exception_offsets=[],global_parameters=[],
                               coulomb_kj_nm_per_mol_e2=138.93545764438198,mixing_rule='lorentz_berthelot',exceptions_periodic=False,exception_count=5,include_direct_space=True))


def export(s=None):
    return m.export_ligand(source() if s is None else s,target_topology_sha256='c'*64,
                           parameter_set_id='synthetic',parameter_set_version='1')


class ExportTests(unittest.TestCase):
    def test_unit_conversion(self):
        p=export()['parameters']
        self.assertEqual(p['bonds'][0]['equilibrium_angstrom'],1.5)
        self.assertAlmostEqual(p['bonds'][0]['force_constant_kcal_per_mol_angstrom2'],100.)
        self.assertAlmostEqual(p['angles'][0]['force_constant_kcal_per_mol_radian2'],100.)
        self.assertEqual(p['torsions'][0]['amplitude_kcal_per_mol'],2.)
        self.assertEqual(p['torsions'][0]['phase_radians'],.7)
        self.assertEqual(p['atom_parameters'][0]['sigma_angstrom'],3.)

    def test_all_pair_accounting_no_switch(self):
        out=export();p=out['parameters'];r=out['receipt']
        self.assertEqual(len(p['excluded_pairs']),6)
        self.assertEqual(p['scaled_pairs'],[])
        self.assertEqual([(r['atom_i'],r['atom_j']) for r in p['listed_pairs']],[(0,3)])
        self.assertEqual(r['all_pair_count'],6)
        self.assertEqual(r['excluded_only_zero_pair_count'],5)
        self.assertFalse(r['source_equivalence_verified'])
        self.assertEqual(r['energy_force_evaluations'],0)

    def test_exception_explicit_parameters(self):
        s=source();s['exceptions'].append(dict(source_term_id='e03',atoms=[0,3],charge_product_e2=-.05,
                                             sigma_nm=.27,epsilon_kj_per_mol=.2092))
        s['nonbonded']['exception_count']=6
        row=export(s)['parameters']['listed_pairs'][0]
        self.assertAlmostEqual(row['electrostatic_scale'],5/6)
        self.assertAlmostEqual(row['sigma_angstrom'],2.7)
        self.assertAlmostEqual(row['epsilon_kcal_per_mol'],.05)

    def test_constant_delta_not_fitted(self):
        r=export()['receipt']
        self.assertLess(abs(r['coulomb_constant_delta']),3e-10)
        self.assertNotEqual(r['coulomb_constant_delta'],0.)

    def test_signed_and_duplicate_fourier(self):
        s=source();a=copy.deepcopy(s['torsions'][0]);a['source_term_id']='t1';a['k_kj_per_mol']=-4.184
        a['atoms'].reverse();s['torsions'].append(a);s['force_inventory']['PeriodicTorsionForce']=2
        p=export(s)['parameters'];self.assertEqual(len(p['torsions']),1)
        self.assertEqual(p['torsions'][0]['amplitude_kcal_per_mol'],1.)
        self.assertEqual(len([x for x in p['metadata']['source_term_accounting'] if x['kind']=='proper']),2)

    def test_distinct_phase_not_merged(self):
        s=source();a=copy.deepcopy(s['torsions'][0]);a['source_term_id']='t1';a['phase_radians']=.8
        s['torsions'].append(a);s['force_inventory']['PeriodicTorsionForce']=2
        self.assertEqual(len(export(s)['parameters']['torsions']),2)

    def test_improper_order_and_star_preserved(self):
        s=source();s['bond_graph']=[[0,1],[0,2],[0,3]]
        for row,path in zip(s['bonds'],s['bond_graph']):row['atoms']=path
        s['angles']=[dict(source_term_id=f'a{i}',atoms=p,theta_radians=1.9,k_kj_per_mol_radian2=418.4)
                     for i,p in enumerate([[1,0,2],[1,0,3],[2,0,3]])]
        s['force_inventory']['HarmonicAngleForce']=3
        s['torsions'][0].update(atoms=[2,0,1,3],kind='improper',star_center=0)
        p=export(s)['parameters'];self.assertEqual(p['torsions'],[])
        self.assertEqual([p['periodic_impropers'][0][k] for k in ('atom_i','atom_j','atom_k','atom_l')],[2,0,1,3])
        self.assertEqual(p['periodic_impropers'][0]['star_center'],0)

    def test_no_input_mutation_and_detached_metadata(self):
        s=source();before=copy.deepcopy(s);out=export(s);self.assertEqual(s,before)
        s['source']['parameterizer']='changed';s['atom_ids'][0]='changed'
        self.assertEqual(out['parameters']['metadata']['source']['parameterizer'],'synthetic')
        self.assertEqual(out['parameters']['metadata']['atom_ids'][0],'C1')

    def test_charge_zero_unrepresentable_exception_rejected(self):
        s=source();s['particles'][0]['charge_e']=0.;s['exceptions'][0]['charge_product_e2']=.1
        with self.assertRaises(m.FourierExportError):export(s)

    def test_negative_and_above_one_exception_scale_rejected(self):
        for q in [.1,-.1]:
            s=source();s['exceptions'][0]['charge_product_e2']=q
            with self.assertRaises(m.FourierExportError):export(s)

    def test_zero_sigma_zero_epsilon_allowed(self):
        s=source();s['particles'][0].update(sigma_nm=0.,epsilon_kj_per_mol=0.)
        self.assertEqual(export(s)['parameters']['atom_parameters'][0]['sigma_angstrom'],0.)

    def test_zero_sigma_positive_epsilon_rejected(self):
        s=source();s['particles'][0]['sigma_nm']=0.
        with self.assertRaises(m.FourierExportError):export(s)

    def test_offsets_rejected(self):
        for key in ('particle_offsets','exception_offsets','global_parameters'):
            s=source();s['nonbonded'][key]=[{'x':1}]
            with self.assertRaises(m.FourierExportError):export(s)

    def test_cutoff_pme_periodic_switch_rejected(self):
        for key,value in [('method','PME'),('method','CutoffNonPeriodic'),('periodic',True),('switching',True)]:
            s=source();s['nonbonded'][key]=value
            with self.assertRaises(m.FourierExportError):export(s)

    def test_constraints_virtual_sites_rejected(self):
        for key in ('constraints','virtual_sites'):
            s=source();s[key]=[{'x':1}]
            with self.assertRaises(m.FourierExportError):export(s)

    def test_bonded_periodic_rejected(self):
        s=source();s['force_metadata']['HarmonicBondForce']['uses_periodic_boundary_conditions']=True
        with self.assertRaises(m.FourierExportError):export(s)

    def test_unlisted_force_rejected(self):
        s=source();s['force_inventory']['CustomBondForce']=1
        with self.assertRaises(m.FourierExportError):export(s)

    def test_count_mismatch_rejected(self):
        s=source();s['force_inventory']['PeriodicTorsionForce']=0
        with self.assertRaises(m.FourierExportError):export(s)

    def test_atom_order_map_rejected(self):
        s=source();s['atom_ids'].reverse()
        with self.assertRaises(m.FourierExportError):export(s)
        s=source();s['particles'][0]['atom_index']=1
        with self.assertRaises(m.FourierExportError):export(s)

    def test_missing_angle_or_torsion_never_zero_filled(self):
        for key,force in [('angles','HarmonicAngleForce'),('torsions','PeriodicTorsionForce')]:
            s=source();s[key]=[];s['force_inventory'][force]=0
            with self.assertRaises(m.FourierExportError):export(s)

    def test_missing_bond_rejected(self):
        s=source();s['bonds'].pop();s['force_inventory']['HarmonicBondForce']=2
        with self.assertRaises(m.FourierExportError):export(s)

    def test_unknown_improper_rejected(self):
        s=source();s['torsions'][0]['kind']='unknown'
        with self.assertRaises(m.FourierExportError):export(s)
        s['torsions'][0].update(kind='improper',star_center=1)
        with self.assertRaises(m.FourierExportError):export(s)

    def test_nonfinite_overflow_and_bool_rejected(self):
        for x in [float('nan'),float('inf'),10**1000,True]:
            s=source();s['particles'][0]['charge_e']=x
            with self.assertRaises(m.FourierExportError):export(s)

    def test_linear_angle_rejected(self):
        s=source();s['angles'][0]['theta_radians']=math.pi
        with self.assertRaises(m.FourierExportError):export(s)

    def test_duplicate_source_id_rejected(self):
        s=source();s['angles'][0]['source_term_id']='b0'
        with self.assertRaises(m.FourierExportError):export(s)

    def test_duplicate_exception_rejected(self):
        s=source();a=copy.deepcopy(s['exceptions'][0]);a['source_term_id']='eNEW';s['exceptions'].append(a)
        with self.assertRaises(m.FourierExportError):export(s)

    def test_zero_periodic_source_term_retained(self):
        s=source();s['torsions'][0]['k_kj_per_mol']=0.
        self.assertEqual(export(s)['parameters']['torsions'][0]['amplitude_kcal_per_mol'],0.)

    def test_disabled_direct_space_rejected(self):
        s=source();s['nonbonded']['include_direct_space']=False
        with self.assertRaises(m.FourierExportError):export(s)

    def test_exception_periodic_rejected(self):
        s=source();s['nonbonded']['exceptions_periodic']=True
        with self.assertRaises(m.FourierExportError):export(s)

    def test_force_instances_rejected(self):
        s=source();s['force_metadata']['HarmonicBondForce']['instances']=2
        with self.assertRaises(m.FourierExportError):export(s)

    def test_unknown_source_constant_rejected(self):
        s=source();s['nonbonded']['coulomb_kj_nm_per_mol_e2']=100.
        with self.assertRaises(m.FourierExportError):export(s)

    def test_converted_length_overflow_rejected(self):
        s=source();s['bonds'][0]['length_nm']=1e308
        with self.assertRaises(m.FourierExportError):export(s)

    def test_atom_id_unhashable_rejected(self):
        s=source();s['atom_ids'][0]={}
        with self.assertRaises(m.FourierExportError):export(s)

    def test_receipt_fingerprints(self):
        s=source();out=export(s)
        self.assertEqual(out['receipt']['source_snapshot_sha256'],m.digest(s))
        self.assertEqual(out['receipt']['target_parameters_sha256'],m.digest(out['parameters']))
        self.assertEqual(out['receipt']['source_term_count'],out['receipt']['accounted_source_term_count'])




class FakeQuantity:
    def __init__(self, value): self.value=value
    def value_in_unit(self, unit): return self.value


def fake_openmm(snapshot):
    """API-control-flow test double, not native or unit-physics evidence."""
    class HarmonicBondForce:
        def usesPeriodicBoundaryConditions(self): return False
        def getNumBonds(self): return len(snapshot['bonds'])
        def getBondParameters(self,i):
            r=snapshot['bonds'][i];return (*r['atoms'],FakeQuantity(r['length_nm']),FakeQuantity(r['k_kj_per_mol_nm2']))
    class HarmonicAngleForce:
        def usesPeriodicBoundaryConditions(self): return False
        def getNumAngles(self): return len(snapshot['angles'])
        def getAngleParameters(self,i):
            r=snapshot['angles'][i];return (*r['atoms'],FakeQuantity(r['theta_radians']),FakeQuantity(r['k_kj_per_mol_radian2']))
    class PeriodicTorsionForce:
        def usesPeriodicBoundaryConditions(self): return False
        def getNumTorsions(self): return len(snapshot['torsions'])
        def getTorsionParameters(self,i):
            r=snapshot['torsions'][i];return (*r['atoms'],r['periodicity'],FakeQuantity(r['phase_radians']),FakeQuantity(r['k_kj_per_mol']))
    class NonbondedForce:
        NoCutoff=0
        def usesPeriodicBoundaryConditions(self): return False
        def getNonbondedMethod(self): return 0
        def getNumParticles(self): return len(snapshot['particles'])
        def getNumParticleParameterOffsets(self): return 0
        def getNumExceptionParameterOffsets(self): return 0
        def getNumGlobalParameters(self): return 0
        def getNumExceptions(self): return len(snapshot['exceptions'])
        def getUseSwitchingFunction(self): return False
        def getUseDispersionCorrection(self): return True
        def getExceptionsUsePeriodicBoundaryConditions(self): return False
        def getIncludeDirectSpace(self): return True
        def getParticleParameters(self,i):
            r=snapshot['particles'][i];return tuple(FakeQuantity(r[k]) for k in ('charge_e','sigma_nm','epsilon_kj_per_mol'))
        def getExceptionParameters(self,i):
            r=snapshot['exceptions'][i];return (*r['atoms'],*(FakeQuantity(r[k]) for k in ('charge_product_e2','sigma_nm','epsilon_kj_per_mol')))
    class System:
        def __init__(self):self.forces=[HarmonicBondForce(),HarmonicAngleForce(),PeriodicTorsionForce(),NonbondedForce()]
        def getNumParticles(self):return len(snapshot['particles'])
        def getNumConstraints(self):return 0
        def isVirtualSite(self,i):return False
        def getNumForces(self):return len(self.forces)
        def getForce(self,i):return self.forces[i]
    module=SimpleNamespace(System=System,HarmonicBondForce=HarmonicBondForce,HarmonicAngleForce=HarmonicAngleForce,
                           PeriodicTorsionForce=PeriodicTorsionForce,NonbondedForce=NonbondedForce,
                           version=SimpleNamespace(short_version='8.4.0'),
                           unit=SimpleNamespace(nanometer=1,kilojoule_per_mole=1,radian=1,elementary_charge=1),
                           XmlSerializer=SimpleNamespace(serialize=lambda x: '<System>synthetic-api-double</System>'))
    return module,System()


class CaptureControlFlowTests(unittest.TestCase):
    def capture(self,s,system,module,assignments=None):
        if assignments is None:
            assignments=[dict(force_index=2,term_index=i,atoms=r['atoms'],kind=r['kind'],star_center=r['star_center']) for i,r in enumerate(s['torsions'])]
        with patch.dict('sys.modules',{'openmm':module}):
            return m.capture_openmm_ligand(system,atom_ids=s['atom_ids'],bond_graph=s['bond_graph'],torsion_assignments=assignments,
                                           parameterizer='synthetic',parameterizer_version='test',forcefield_sha256='b'*64,
                                           expected_system_xml_sha256=m.hashlib.sha256(module.XmlSerializer.serialize(system).encode()).hexdigest(),
                                           charge_method='synthetic',chemical_state_id='synthetic')

    def test_capture_complete_api_double(self):
        s=source();module,system=fake_openmm(s);observed=self.capture(s,system,module)
        result=export(observed)
        self.assertEqual(result['receipt']['all_pair_count'],6)
        self.assertEqual(observed['source']['openmm_version'],'8.4.0')
        self.assertEqual(observed['torsions'][0]['source_term_id'],'PeriodicTorsionForce:2:0')

    def test_capture_missing_assignment(self):
        s=source();module,system=fake_openmm(s)
        with self.assertRaises(m.FourierExportError):self.capture(s,system,module,[])

    def test_capture_assignment_order_mismatch(self):
        s=source();module,system=fake_openmm(s)
        a=[dict(force_index=2,term_index=0,atoms=[3,2,1,0],kind='proper',star_center=None)]
        with self.assertRaises(m.FourierExportError):self.capture(s,system,module,a)

    def test_capture_unconsumed_assignment(self):
        s=source();module,system=fake_openmm(s)
        a=[dict(force_index=2,term_index=i,atoms=[0,1,2,3],kind='proper',star_center=None) for i in (0,1)]
        with self.assertRaises(m.FourierExportError):self.capture(s,system,module,a)

    def test_capture_multiple_force_instances(self):
        s=source();module,system=fake_openmm(s);system.forces.append(module.NonbondedForce())
        with self.assertRaises(m.FourierExportError):self.capture(s,system,module)

    def test_capture_unknown_force(self):
        s=source();module,system=fake_openmm(s);system.forces.append(object())
        with self.assertRaises(m.FourierExportError):self.capture(s,system,module)

    def test_capture_constraints_and_virtual_sites(self):
        for name,fn in [('getNumConstraints',lambda:1),('isVirtualSite',lambda i:True)]:
            s=source();module,system=fake_openmm(s);setattr(system,name,fn)
            with self.assertRaises(m.FourierExportError):self.capture(s,system,module)

    def test_capture_unsupported_version(self):
        s=source();module,system=fake_openmm(s);module.version.short_version='7.7.0'
        with self.assertRaises(m.FourierExportError):self.capture(s,system,module)

if __name__=='__main__':unittest.main()

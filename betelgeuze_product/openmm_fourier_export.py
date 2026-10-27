"""Strict, source-record-preserving NoCutoff ligand parameter conversion.

The input is a complete unit-normalized OpenMM observation, not a parameterizer.
All ordinary ligand pairs are excluded and active pairs are explicitly listed,
so the target's ordinary nonbonded switch cannot alter source NoCutoff physics.
No receptor preparation, coordinate execution admission, or parity is implied.
"""
from __future__ import annotations
import hashlib
import json
import math
from itertools import combinations

SOURCE_SCHEMA = 'openmm_ligand_parameter_snapshot/1.0.0'
TARGET_SCHEMA = 'cpu_prepared_fourier_parameters/1.0.0'
EXPORT_SCHEMA = 'openmm_fourier_export_receipt/1.0.0'
TARGET_COULOMB = 332.063713299
SOURCE_COULOMB = 138.93545764438198
KJ_PER_KCAL = 4.184
FORCES = ('HarmonicBondForce', 'HarmonicAngleForce', 'PeriodicTorsionForce', 'NonbondedForce')


class FourierExportError(ValueError):
    """Source model cannot be represented by this narrow export contract."""


def require(ok, reason):
    if not ok:
        raise FourierExportError(reason)


def exact(value, names, label):
    require(type(value) is dict and set(value) == set(names), label)


def number(value, label, minimum=None, maximum=None):
    require(type(value) in (int, float), label)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise FourierExportError(label) from None
    require(math.isfinite(result), label)
    require(minimum is None or result >= minimum, label)
    require(maximum is None or result <= maximum, label)
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(value):
    require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'SHA256 required')
    return value


def token(value):
    require(type(value) is str and 0 < len(value) <= 200 and value.strip() == value and all(ord(c) >= 32 for c in value), 'bounded source identity required')
    return value


def indices(value, count, size):
    require(type(value) is list and len(value) == size, 'explicit ordered atom indices required')
    require(all(type(i) is int and 0 <= i < count for i in value) and len(set(value)) == size, 'invalid atom indices')
    return tuple(value)


def nonbonded(sigma, epsilon):
    sigma = number(sigma, 'invalid sigma', 0, 10) * 10
    epsilon = number(epsilon, 'invalid epsilon', 0, 4.184e6) / KJ_PER_KCAL
    require(sigma != 0 or epsilon == 0, 'zero sigma with positive epsilon is unsupported')
    return sigma, epsilon


def export_ligand(snapshot, *, target_topology_sha256, parameter_set_id, parameter_set_version,
                  minimum_distance_angstrom=0.35):
    """Return target owning-schema JSON plus source-term accounting receipt.

    Hashes bind declarations and bytes; they do not authenticate preparation or
    prove the target topology's atom identities. The owning loader must verify
    the supplied atom map and target canonical topology before any evaluation.
    """
    exact(snapshot, ('schema_id', 'source', 'atom_ids', 'particles', 'bonds', 'angles',
                     'torsions', 'exceptions', 'bond_graph', 'force_inventory',
                     'constraints', 'virtual_sites', 'force_metadata', 'nonbonded'), 'exact source snapshot required')
    require(snapshot['schema_id'] == SOURCE_SCHEMA, 'unsupported snapshot schema')
    exact(snapshot['source'], ('parameterizer', 'version', 'system_xml_sha256', 'forcefield_sha256',
                              'charge_method', 'chemical_state_id', 'atom_mapping_sha256', 'openmm_version'), 'complete source provenance required')
    for k, v in snapshot['source'].items():
        (sha if k.endswith('sha256') else token)(v)
    sha(target_topology_sha256)
    token(parameter_set_id); token(parameter_set_version)
    min_distance = number(minimum_distance_angstrom, 'invalid minimum distance', 1e-12, 100)
    exact(snapshot['force_metadata'], FORCES, 'complete source force metadata required')
    for force in FORCES:
        meta = snapshot['force_metadata'][force]
        exact(meta, ('instances', 'uses_periodic_boundary_conditions'), 'force instance and periodic flags required')
        require(type(meta['instances']) is int and meta['instances'] == 1, 'exactly one instance of each supported force required')
        require(meta['uses_periodic_boundary_conditions'] is False, 'periodic source force unsupported')
    require(snapshot['constraints'] == [] and type(snapshot['constraints']) is list,
            'constraints cannot be dropped')
    require(snapshot['virtual_sites'] == [] and type(snapshot['virtual_sites']) is list,
            'virtual sites cannot be dropped')
    exact(snapshot['nonbonded'], ('method', 'periodic', 'switching', 'dispersion_correction',
                                 'particle_offsets', 'exception_offsets', 'global_parameters',
                                 'coulomb_kj_nm_per_mol_e2', 'mixing_rule', 'exceptions_periodic', 'exception_count', 'include_direct_space'), 'complete nonbonded policy required')
    nb = snapshot['nonbonded']
    require(nb['include_direct_space'] is True, 'disabled direct space unsupported')
    require(nb['exceptions_periodic'] is False, 'periodic exceptions unsupported')
    require(nb['method'] == 'NoCutoff' and nb['periodic'] is False and nb['switching'] is False,
            'only nonperiodic unswitched NoCutoff source is supported')
    require(type(nb['dispersion_correction']) is bool, 'dispersion flag required')
    # OpenMM's dispersion correction flag has no effect in NoCutoff mode.
    require(nb['mixing_rule'] == 'lorentz_berthelot', 'unsupported mixing rule')
    for key in ('particle_offsets', 'exception_offsets', 'global_parameters'):
        require(type(nb[key]) is list and not nb[key], 'parameter offsets/global parameters unsupported')
    source_coulomb = number(nb['coulomb_kj_nm_per_mol_e2'], 'source Coulomb constant required', 1e-12, 1e6)
    require(abs(source_coulomb - SOURCE_COULOMB) <= 1e-12, 'source Coulomb constant unsupported by this OpenMM contract')
    atoms = snapshot['atom_ids']; particles = snapshot['particles']
    require(type(atoms) is list and 1 <= len(atoms) <= 256, 'bounded atom map required')
    for a in atoms: token(a)
    require(len(set(atoms)) == len(atoms), 'unique atom map required')
    n = len(atoms)
    require(snapshot['source']['atom_mapping_sha256'] == digest(atoms), 'atom map digest mismatch')
    require(type(particles) is list and len(particles) == n, 'complete particle coverage required')
    for key in ('bonds', 'angles', 'torsions', 'exceptions', 'bond_graph'):
        require(type(snapshot[key]) is list and len(snapshot[key]) <= 32640, 'bounded explicit source terms required')
    require(type(nb['exception_count']) is int and nb['exception_count'] == len(snapshot['exceptions']), 'exception count differs from rows')
    exact(snapshot['force_inventory'], FORCES, 'unknown or missing source forces')
    expected_counts = dict(zip(FORCES, (len(snapshot['bonds']), len(snapshot['angles']), len(snapshot['torsions']), n)))
    require(all(type(v) is int for v in snapshot['force_inventory'].values()) and snapshot['force_inventory'] == expected_counts,
            'source force inventory differs from rows')
    graph = {tuple(sorted(indices(row, n, 2))) for row in snapshot['bond_graph']}
    require(len(graph) == len(snapshot['bond_graph']), 'duplicate source graph edge')
    atom_rows = []
    for i, row in enumerate(particles):
        exact(row, ('atom_index', 'charge_e', 'sigma_nm', 'epsilon_kj_per_mol'), 'invalid particle row')
        require(type(row['atom_index']) is int and row['atom_index'] == i, 'particle order must match atom map')
        sigma, epsilon = nonbonded(row['sigma_nm'], row['epsilon_kj_per_mol'])
        atom_rows.append(dict(atom_index=i, charge_e=number(row['charge_e'], 'invalid charge', -100, 100),
                              sigma_angstrom=sigma, epsilon_kcal_per_mol=epsilon))
    source_ids = set(); accounts = []
    def account(row, kind):
        source_id = token(row['source_term_id'])
        require(source_id not in source_ids, 'duplicate source term identifier')
        source_ids.add(source_id)
        accounts.append({'source_term_id': source_id, 'kind': kind})
    bonds = []; seen_bonds = set()
    for row in snapshot['bonds']:
        exact(row, ('source_term_id', 'atoms', 'length_nm', 'k_kj_per_mol_nm2'), 'invalid bond row')
        pair = tuple(sorted(indices(row['atoms'], n, 2)))
        require(pair not in seen_bonds, 'duplicate harmonic bond unsupported')
        seen_bonds.add(pair); account(row, 'bond')
        length = number(number(row['length_nm'], 'invalid bond length', 1e-12) * 10, 'converted bond length nonfinite', 1e-12)
        k = number(row['k_kj_per_mol_nm2'], 'zero/negative bond force constant unsupported', 1e-12) / (KJ_PER_KCAL * 100)
        bonds.append(dict(atom_i=pair[0], atom_j=pair[1], equilibrium_angstrom=length,
                          force_constant_kcal_per_mol_angstrom2=k))
    require(seen_bonds == graph, 'bond force terms must exactly cover declared graph')
    angles = []; seen_angles = set()
    for row in snapshot['angles']:
        exact(row, ('source_term_id', 'atoms', 'theta_radians', 'k_kj_per_mol_radian2'), 'invalid angle row')
        i,j,k = indices(row['atoms'], n, 3)
        key = (min(i,k), j, max(i,k))
        require(key not in seen_angles, 'duplicate harmonic angle unsupported')
        require(tuple(sorted((i,j))) in graph and tuple(sorted((j,k))) in graph, 'angle absent from graph')
        theta = number(row['theta_radians'], 'invalid angle', 1e-12)
        require(theta < math.pi, 'linear angle requires separate owning model')
        seen_angles.add(key); account(row, 'angle')
        angles.append(dict(atom_i=i, atom_j=j, atom_k=k, equilibrium_radians=theta,
                           force_constant_kcal_per_mol_radian2=number(row['k_kj_per_mol_radian2'], 'invalid angle force constant', 1e-12) / KJ_PER_KCAL))
    # Exact same ordered definitions can be merged, but their source IDs remain.
    grouped = {}
    for row in snapshot['torsions']:
        exact(row, ('source_term_id', 'atoms', 'kind', 'star_center', 'periodicity', 'phase_radians', 'k_kj_per_mol'), 'invalid torsion row')
        path = indices(row['atoms'], n, 4); kind = row['kind']; center = row['star_center']
        require(kind in ('proper', 'improper'), 'explicit source proper/improper assignment required')
        if kind == 'proper':
            require(center is None and all(tuple(sorted(p)) in graph for p in zip(path, path[1:])), 'proper torsion lacks graph path')
            path = min(path, path[::-1])
        else:
            require(type(center) is int and center in path and all(tuple(sorted((center,i))) in graph for i in path if i != center), 'improper lacks declared bonded star')
        periodicity = row['periodicity']
        require(type(periodicity) is int and 1 <= periodicity <= 12, 'unsupported torsion periodicity')
        phase = number(row['phase_radians'], 'invalid phase', -1e6, 1e6)
        amplitude = number(row['k_kj_per_mol'], 'invalid torsion amplitude', -4.184e6, 4.184e6) / KJ_PER_KCAL
        account(row, kind)
        key = (kind, path, center, periodicity, phase)
        grouped.setdefault(key, []).append(amplitude)
    torsions=[]; impropers=[]
    for (kind, path, center, periodicity, phase), amplitudes in grouped.items():
        amplitude = number(math.fsum(amplitudes), 'summed torsion amplitude outside target bounds', -1e6, 1e6)
        row = dict(zip(('atom_i','atom_j','atom_k','atom_l'), path))
        row.update(periodicity=periodicity, phase_radians=phase, amplitude_kcal_per_mol=amplitude)
        if kind == 'improper': row['star_center']=center
        (torsions if kind == 'proper' else impropers).append(row)
    require(len(impropers) <= 4096, 'periodic improper target capacity exceeded')
    # The current owning evaluator demands every graph angle/proper path. Do not
    # invent zero terms to satisfy it when source assignment lacks a path.
    neighbors=[set() for _ in atoms]
    for i,j in graph: neighbors[i].add(j); neighbors[j].add(i)
    expected_angles={(i,j,k) for j, ns in enumerate(neighbors) for i,k in combinations(sorted(ns),2)}
    expected_propers=set()
    for j,k in graph:
        for i in neighbors[j]-{k}:
            for l in neighbors[k]-{j}:
                if len({i,j,k,l})==4: expected_propers.add(min((i,j,k,l),(l,k,j,i)))
    require(seen_angles == expected_angles, 'source angles do not satisfy owning graph coverage')
    require({(r['atom_i'],r['atom_j'],r['atom_k'],r['atom_l']) for r in torsions} == expected_propers,
            'source proper assignments do not satisfy owning graph coverage')
    exceptions={}
    for row in snapshot['exceptions']:
        exact(row, ('source_term_id', 'atoms', 'charge_product_e2', 'sigma_nm', 'epsilon_kj_per_mol'), 'invalid exception row')
        pair=tuple(sorted(indices(row['atoms'],n,2)))
        require(pair not in exceptions, 'duplicate exception pair')
        account(row,'exception'); exceptions[pair]=row
    listed=[]; excluded=[]
    for i,j in combinations(range(n),2):
        excluded.append([i,j]); a,b=atom_rows[i],atom_rows[j]
        product=a['charge_e']*b['charge_e']
        if (i,j) in exceptions:
            row=exceptions[(i,j)]
            sigma,epsilon=nonbonded(row['sigma_nm'],row['epsilon_kj_per_mol'])
            qprod=number(row['charge_product_e2'],'invalid exception charge product')
            if product==0:
                require(qprod==0,'exception charge product cannot be represented with source charges')
                scale=0.0
            else:
                scale=number(qprod/product,'exception charge scale outside target range',0,1)
        else:
            sigma=(a['sigma_angstrom']+b['sigma_angstrom'])/2
            epsilon=math.sqrt(a['epsilon_kcal_per_mol']*b['epsilon_kcal_per_mol'])
            scale=1.0
        if epsilon == 0 and (product == 0 or scale == 0): continue
        listed.append(dict(atom_i=i,atom_j=j,sigma_angstrom=sigma,epsilon_kcal_per_mol=epsilon,electrostatic_scale=scale))
    source_digest=digest(snapshot)
    metadata={'exporter_schema':EXPORT_SCHEMA,'source_snapshot_sha256':source_digest,'source':json.loads(json.dumps(snapshot['source'])),
              'atom_ids':list(atoms),'source_exception_charge_products':[{
                  'source_term_id':r['source_term_id'],'atoms':list(r['atoms']),
                  'charge_product_e2':r['charge_product_e2']} for r in snapshot['exceptions']],
              'all_ordinary_pairs_replaced_by_unswitched_listed_pairs':True,
              'source_term_accounting':accounts,'source_coulomb_kcal_angstrom_per_mol_e2':source_coulomb*10/KJ_PER_KCAL,
              'target_coulomb_kcal_angstrom_per_mol_e2':TARGET_COULOMB,'source_equivalence_verified':False}
    result=dict(schema_id=TARGET_SCHEMA, parameter_set_id=parameter_set_id,parameter_set_version=parameter_set_version,
                topology_sha256=target_topology_sha256,atom_parameters=atom_rows,bonds=bonds,angles=angles,torsions=torsions,
                periodic_impropers=impropers,excluded_pairs=excluded,scaled_pairs=[],listed_pairs=listed,
                cutoff_angstrom=10.0,switch_start_angstrom=8.0,dielectric=1.0,screening_kappa_per_angstrom=0.0,
                applicability_domain=dict(max_atoms=256,max_bonds=40000,max_angles=80000,max_torsions=160000,
                                          max_nonbonded_pairs=32640,periodic_orthorhombic_supported=False,
                                          minimum_pair_distance_angstrom=min_distance),metadata=metadata)
    # Conversion has no access to actual source evaluator or authenticated topology.
    receipt=dict(schema_id=EXPORT_SCHEMA,source_snapshot_sha256=source_digest,target_parameters_sha256=digest(result),
                 source_term_count=len(accounts),accounted_source_term_count=len(source_ids),
                 all_pair_count=n*(n-1)//2,listed_active_pair_count=len(listed),
                 excluded_only_zero_pair_count=n*(n-1)//2-len(listed),
                 coulomb_constant_delta=TARGET_COULOMB-source_coulomb*10/KJ_PER_KCAL,
                 energy_force_evaluations=0,engine_admission_performed=False,source_equivalence_verified=False)
    return {'parameters':result,'receipt':receipt}


def capture_openmm_ligand(system, *, atom_ids, bond_graph, torsion_assignments,
                          parameterizer, parameterizer_version, forcefield_sha256,
                          expected_system_xml_sha256, charge_method, chemical_state_id):
    """Read actual OpenMM 8.4 System APIs into the complete source snapshot.

    Optional native imports occur ONLY on this explicitly requested call.
    Assignment rows must come from the preparing force field, not graph guessing:
    force_index, term_index, atoms (exact ordered tuple), kind, star_center.
    The expected hash must be the exact UTF-8 XmlSerializer output artifact;
    differently formatted original XML must be preserved as a separate source.
    Atom IDs/graph/state provenance are supplied by the owning preparation step;
    this capture checks consistency, not the scientific correctness of that step.
    No Context, energy, minimization, or particle mutation is performed.
    """
    import openmm
    from openmm import unit
    version = str(openmm.version.short_version)
    require(version == '8.4.0', 'native capture currently supports pinned OpenMM 8.4.0 only')
    require(type(system) is openmm.System, 'exact OpenMM System required')
    n = system.getNumParticles()
    require(1 <= n <= 256 and len(atom_ids) == n, 'ligand particle capacity/map mismatch')
    require(system.getNumConstraints() == 0, 'source constrained System unsupported')
    require(not any(system.isVirtualSite(i) for i in range(n)), 'source virtual sites unsupported')
    before_xml = openmm.XmlSerializer.serialize(system)
    xml_sha = hashlib.sha256(before_xml.encode()).hexdigest()
    require(xml_sha == sha(expected_system_xml_sha256), 'serialized source System differs from pinned XML artifact')
    require(type(torsion_assignments) is list and len(torsion_assignments) <= 32640, 'bounded torsion assignments required')
    assignments = {}
    for row in torsion_assignments:
        exact(row, ('force_index','term_index','atoms','kind','star_center'), 'exact source torsion assignment required')
        require(type(row['force_index']) is int and type(row['term_index']) is int and row['force_index'] >= 0 and row['term_index'] >= 0,
                'invalid torsion source index')
        key=(row['force_index'],row['term_index'])
        require(key not in assignments,'duplicate source torsion assignment')
        assignments[key]=row
    result=dict(schema_id=SOURCE_SCHEMA,
                source=dict(parameterizer=parameterizer,version=parameterizer_version,
                            system_xml_sha256=xml_sha,forcefield_sha256=forcefield_sha256,
                            charge_method=charge_method,chemical_state_id=chemical_state_id,
                            atom_mapping_sha256=digest(atom_ids),openmm_version=version),
                atom_ids=list(atom_ids),bond_graph=[list(p) for p in bond_graph],
                particles=[],bonds=[],angles=[],torsions=[],exceptions=[],constraints=[],virtual_sites=[],
                force_inventory={},force_metadata={},nonbonded={})
    used=set();seen=set()
    for fi in range(system.getNumForces()):
        force=system.getForce(fi);kind=type(force).__name__
        require(kind in FORCES and type(force) is getattr(openmm,kind), 'unsupported source force type')
        require(kind not in seen,'multiple source force instances unsupported')
        seen.add(kind)
        periodic=bool(force.usesPeriodicBoundaryConditions())
        require(not periodic,'periodic source force unsupported')
        result['force_metadata'][kind]=dict(instances=1,uses_periodic_boundary_conditions=periodic)
        if kind=='HarmonicBondForce':
            count=force.getNumBonds()
            require(count<=32640,'source bond capacity exceeded')
            for ti in range(count):
                i,j,r,k=force.getBondParameters(ti)
                result['bonds'].append(dict(source_term_id=f'{kind}:{fi}:{ti}',atoms=[int(i),int(j)],
                                           length_nm=r.value_in_unit(unit.nanometer),
                                           k_kj_per_mol_nm2=k.value_in_unit(unit.kilojoule_per_mole/unit.nanometer**2)))
        elif kind=='HarmonicAngleForce':
            count=force.getNumAngles()
            require(count<=32640,'source angle capacity exceeded')
            for ti in range(count):
                i,j,k,a,fc=force.getAngleParameters(ti)
                result['angles'].append(dict(source_term_id=f'{kind}:{fi}:{ti}',atoms=[int(i),int(j),int(k)],
                                            theta_radians=a.value_in_unit(unit.radian),
                                            k_kj_per_mol_radian2=fc.value_in_unit(unit.kilojoule_per_mole/unit.radian**2)))
        elif kind=='PeriodicTorsionForce':
            count=force.getNumTorsions()
            require(count<=32640,'source torsion capacity exceeded')
            for ti in range(count):
                i,j,k,l,period,phase,fc=force.getTorsionParameters(ti)
                path=[int(i),int(j),int(k),int(l)];key=(fi,ti)
                require(key in assignments,'missing force-field torsion assignment')
                assignment=assignments[key]
                require(assignment['atoms']==path,'source assignment changes ordered torsion')
                used.add(key)
                result['torsions'].append(dict(source_term_id=f'{kind}:{fi}:{ti}',atoms=path,
                                              kind=assignment['kind'],star_center=assignment['star_center'],
                                              periodicity=int(period),phase_radians=phase.value_in_unit(unit.radian),
                                              k_kj_per_mol=fc.value_in_unit(unit.kilojoule_per_mole)))
        else:
            count=force.getNumParticles()
            require(count==n,'nonbonded particle coverage differs from System')
            require(force.getNonbondedMethod()==openmm.NonbondedForce.NoCutoff,'source nonbonded method unsupported')
            require(force.getNumParticleParameterOffsets()==0 and force.getNumExceptionParameterOffsets()==0 and force.getNumGlobalParameters()==0,
                    'source global parameters or offsets unsupported')
            exception_count=force.getNumExceptions()
            require(exception_count<=n*(n-1)//2,'source exception capacity exceeded')
            result['nonbonded']=dict(method='NoCutoff',periodic=False,switching=bool(force.getUseSwitchingFunction()),
                                    dispersion_correction=bool(force.getUseDispersionCorrection()),particle_offsets=[],exception_offsets=[],
                                    global_parameters=[],coulomb_kj_nm_per_mol_e2=SOURCE_COULOMB,mixing_rule='lorentz_berthelot',
                                    exceptions_periodic=bool(force.getExceptionsUsePeriodicBoundaryConditions()),
                                    exception_count=exception_count,include_direct_space=bool(force.getIncludeDirectSpace()))
            for ti in range(count):
                q,s,e=force.getParticleParameters(ti)
                result['particles'].append(dict(atom_index=ti,charge_e=q.value_in_unit(unit.elementary_charge),
                                                sigma_nm=s.value_in_unit(unit.nanometer),epsilon_kj_per_mol=e.value_in_unit(unit.kilojoule_per_mole)))
            for ti in range(exception_count):
                i,j,q,s,e=force.getExceptionParameters(ti)
                result['exceptions'].append(dict(source_term_id=f'{kind}:{fi}:exception:{ti}',atoms=[int(i),int(j)],
                                                 charge_product_e2=q.value_in_unit(unit.elementary_charge**2),
                                                 sigma_nm=s.value_in_unit(unit.nanometer),epsilon_kj_per_mol=e.value_in_unit(unit.kilojoule_per_mole)))
        result['force_inventory'][kind]=count
    require(seen==set(FORCES),'source System missing supported force instance')
    require(used==set(assignments),'unconsumed source torsion assignments')
    require(openmm.XmlSerializer.serialize(system)==before_xml,'source System changed during capture')
    # All remaining graph/value/pair checks occur in export_ligand. The snapshot
    # is an observation, never a readiness certificate or evaluator admission.
    return result

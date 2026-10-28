"""Opt-in research-only native System observation; not a product integration.

Use only within a separately authorized bounded research worker. This helper
is not a provenance-bearing contained oracle entrypoint: it does not implement
that pack's pinned-child containment or grant runtime qualification. Native
imports remain lazy. The returned neutral data must cross the artifact boundary;
product code must never import or invoke this module.
"""
import hashlib
from betelgeuze_product.openmm_fourier_export import (
    FORCES, SOURCE_SCHEMA, SOURCE_COULOMB, digest, exact, require, sha,
)


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

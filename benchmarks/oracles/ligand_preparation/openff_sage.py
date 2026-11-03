"""Opt-in research-only Sage/AM1-BCC preparation, not a product integration.

Call only inside a separately authorized bounded research worker.
This is not the oracle pack's provenance-bearing pinned-child entrypoint and
does not implement its containment or grant runtime qualification. Product
code must never import or invoke this module; outputs cross a data boundary. Imports may execute native
code; AmberTools starts subprocesses. No package installation or receptor repair.
The output directory must not exist. Failure leaves partial evidence, never success.
"""
from pathlib import Path
import hashlib
import sys
import shutil
import json
import xml.etree.ElementTree as ET
from importlib.metadata import version
SAGE_SHA256 = '1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a'
PINNED_VERSIONS = {'openmm': '8.4.0', 'openff-toolkit': '0.19.0', 'openff-interchange': '0.5.5', 'rdkit': '2026.3.1'}

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def verify_static_derivation(original_xml, derived_xml):
    """Compare every XML tag/attribute/order after exactly allowed bookkeeping edits."""
    original, derived = (ET.fromstring(original_xml), ET.fromstring(derived_xml))
    forces = original.find('Forces')
    if forces is None:
        return False
    removed = [f for f in forces if f.get('type') == 'CMMotionRemover']
    nonbonded = [f for f in forces if f.get('type') == 'NonbondedForce']
    if len(removed) != 1 or len(nonbonded) != 1 or nonbonded[0].get('method') != '0':
        return False
    forces.remove(removed[0])
    nonbonded[0].set('useSwitchingFunction', '0')

    def structural(node):
        return (node.tag, sorted(node.attrib.items()), (node.text or '').strip(), (node.tail or '').strip(), [structural(c) for c in node])
    return structural(original) == structural(derived)

def require_representation_only(before, after):
    """Allow only aromatic flags to differ between ordered Kekule signatures."""
    required = {'atoms', 'bonds', 'coordinates', 'atom_aromaticity', 'bond_aromaticity'}
    require(set(before) == set(after) == required, 'representation signature schema mismatch')
    require(all(before[key] == after[key] for key in ('atoms', 'bonds', 'coordinates')), 'representation conversion changed chemical state')

def require_normalized_chemistry(expected, actual):
    """Exact ordered-chemistry comparison after the declared MDL representation step."""
    require(expected == actual, 'normalized ordered chemistry changed')

def prepare_sage_ligand(input_sdf, output_directory, *, forcefield_path):
    """Prepare one already explicit-H, stereo-defined SDF without chemical repair.

    Fixed Sage 2.2.1, AmberTools 26 AM1-BCC, supplied coordinates, no charge cache.
    Caller must separately enforce CPU/wall/memory/process/filesystem policy.
    A successful return is parameterization evidence, not docking accuracy evidence.
    """
    input_sdf, output_directory, forcefield_path = map(Path, (input_sdf, output_directory, forcefield_path))
    require(input_sdf.is_file(), 'input SDF missing')
    require(forcefield_path.is_file(), 'force-field file missing')
    forcefield_bytes = forcefield_path.read_bytes()
    require(hashlib.sha256(forcefield_bytes).hexdigest() == SAGE_SHA256, 'Sage 2.2.1 hash mismatch')
    require(not output_directory.exists(), 'output directory must be new')
    import numpy as np
    import openmm
    from openmm import unit as omu
    from openff.toolkit import Molecule, ForceField
    from openff.toolkit.utils import AmberToolsToolkitWrapper, RDKitToolkitWrapper
    from openff.units import unit
    from rdkit import Chem
    versions = {name: version(name) for name in PINNED_VERSIONS}
    require(versions == PINNED_VERSIONS, 'unsupported backend versions')
    amber_records = list((Path(sys.prefix) / 'conda-meta').glob('ambertools-26.0-*.json'))
    require(len(amber_records) == 1, 'pinned AmberTools conda provenance required')
    amber_record = json.loads(amber_records[0].read_text())
    require(amber_record.get('name') == 'ambertools' and amber_record.get('version') == '26.0', 'unsupported AmberTools version')
    for executable in ('antechamber', 'sqm'):
        resolved = shutil.which(executable)
        require(resolved is not None and Path(resolved).resolve().is_relative_to(Path(sys.prefix).resolve()), 'AmberTools executable outside pinned prefix')
    versions['ambertools'] = '26.0'
    versions['ambertools_build'] = amber_record.get('build')
    S = input_sdf
    input_bytes = S.read_bytes()
    inputsha = hashlib.sha256(input_bytes).hexdigest()
    raw_molecules = list(Chem.SDMolSupplier(str(S), removeHs=False))
    require(len(raw_molecules) == 1 and raw_molecules[0] is not None, 'one valid SDF molecule required')
    original_raw = raw_molecules[0]
    raw = Chem.Mol(original_raw)
    require(all(a.GetIsotope() == 0 for a in raw.GetAtoms()), 'isotopically labeled inputs unsupported')
    require(len(Chem.GetMolFrags(raw)) == 1, 'disconnected input unsupported')
    raw_observations = {'atoms': [{'atomic_number': a.GetAtomicNum(), 'formal_charge': a.GetFormalCharge(), 'isotope': a.GetIsotope(), 'atom_map': a.GetAtomMapNum(), 'aromatic': a.GetIsAromatic(), 'stereo': a.GetProp('_CIPCode') if a.HasProp('_CIPCode') else None} for a in original_raw.GetAtoms()], 'bonds': [{'atoms': [b.GetBeginAtomIdx(), b.GetEndAtomIdx()], 'order': b.GetBondTypeAsDouble(), 'aromatic': b.GetIsAromatic(), 'stereo': str(b.GetStereo())} for b in original_raw.GetBonds()]}
    input_aromaticity = {'model': 'RDKit_default', 'atom_flags': [a.GetIsAromatic() for a in raw.GetAtoms()], 'bond_flags': [b.GetIsAromatic() for b in raw.GetBonds()]}
    Chem.SanitizeMol(raw, Chem.SANITIZE_ALL ^ Chem.SANITIZE_SETAROMATICITY ^ Chem.SANITIZE_ADJUSTHS ^ Chem.SANITIZE_CLEANUPCHIRALITY)
    Chem.SetAromaticity(raw, Chem.AromaticityModel.AROMATICITY_MDL)
    Chem.Kekulize(raw)
    Chem.AssignStereochemistry(raw, cleanIt=False)
    original_kekule = Chem.Mol(original_raw)
    Chem.Kekulize(original_kekule)
    def invariant_atoms(molecule):
        return [(a.GetAtomicNum(), a.GetFormalCharge(), a.GetIsotope(), a.GetAtomMapNum(), a.GetNumImplicitHs(), a.GetNumExplicitHs(), a.GetProp('_CIPCode') if a.HasProp('_CIPCode') else None) for a in molecule.GetAtoms()]
    def invariant_bonds(molecule):
        return [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), b.GetBondTypeAsDouble(), str(b.GetStereo())) for b in molecule.GetBonds()]
    require(invariant_atoms(original_raw) == invariant_atoms(raw), 'MDL conversion changed atom state')
    require(invariant_bonds(original_kekule) == invariant_bonds(raw), 'MDL conversion changed ordered bond state')
    require(np.array_equal(original_raw.GetConformer().GetPositions(), raw.GetConformer().GetPositions()), 'MDL conversion changed coordinates')
    def representation_signature(molecule):
        return {'atoms': invariant_atoms(molecule), 'bonds': invariant_bonds(molecule), 'coordinates': molecule.GetConformer().GetPositions().tolist(), 'atom_aromaticity': [a.GetIsAromatic() for a in molecule.GetAtoms()], 'bond_aromaticity': [b.GetIsAromatic() for b in molecule.GetBonds()]}
    require_representation_only(representation_signature(original_kekule), representation_signature(raw))
    require(all((a.GetNumImplicitHs() == 0 and a.GetNumExplicitHs() == 0 for a in raw.GetAtoms())), 'all hydrogens must be explicit atom records')
    require(raw.GetNumConformers() == 1, 'one input conformer required')
    output_directory.mkdir(parents=False, exist_ok=False)
    (output_directory / 'input.sdf').write_bytes(input_bytes)

    def artifact(name):
        return output_directory / name

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def artifact_sha(name):
        return sha(artifact(name))

    def dump(name, data):
        temporary = artifact(name + '.tmp')
        temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
        temporary.replace(artifact(name))
    rd = RDKitToolkitWrapper()
    mol = Molecule.from_file(S, file_format='sdf', toolkit_registry=rd, allow_undefined_stereo=False)
    require(type(mol) is Molecule, 'single molecule required')
    require(mol.n_atoms == raw.GetNumAtoms() and mol.n_bonds == raw.GetNumBonds(), 'implicit atom repair is forbidden')
    require(mol.n_conformers == 1, 'exactly one conformer required')
    coords = mol.conformers[0].m_as(unit.angstrom).copy()
    require(np.isfinite(coords).all(), 'nonfinite coords')
    require(np.array_equal(coords, raw.GetConformer().GetPositions()), 'input coordinates/order changed')
    require([int(a.formal_charge.m_as(unit.elementary_charge)) for a in mol.atoms] == [a.GetFormalCharge() for a in raw.GetAtoms()], 'formal charge state changed')
    require([(b.atom1_index, b.atom2_index, float(b.bond_order)) for b in mol.bonds] == [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble())) for b in raw.GetBonds()], 'bond state/order changed')
    require([a.atomic_number for a in mol.atoms] == [a.GetAtomicNum() for a in raw.GetAtoms()], 'input atom order changed')
    require([a.is_aromatic for a in mol.atoms] == [a.GetIsAromatic() for a in raw.GetAtoms()], 'atom aromaticity changed')
    require([b.is_aromatic for b in mol.bonds] == [b.GetIsAromatic() for b in raw.GetBonds()], 'bond aromaticity changed')
    require([a.stereochemistry for a in mol.atoms] == [a.GetProp('_CIPCode') if a.HasProp('_CIPCode') else None for a in raw.GetAtoms()], 'atom stereochemistry changed')
    stereo_names = {Chem.BondStereo.STEREONONE: None, Chem.BondStereo.STEREOE: 'E', Chem.BondStereo.STEREOZ: 'Z'}
    require(all(b.GetStereo() in stereo_names for b in raw.GetBonds()), 'unsupported bond stereochemistry')
    require([b.stereochemistry for b in mol.bonds] == [stereo_names[b.GetStereo()] for b in raw.GetBonds()], 'bond stereochemistry changed')
    expected_chemistry = {'atoms': [(a.GetAtomicNum(), a.GetFormalCharge(), a.GetIsAromatic(), a.GetProp('_CIPCode') if a.HasProp('_CIPCode') else None) for a in raw.GetAtoms()], 'bonds': [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()), b.GetIsAromatic(), stereo_names[b.GetStereo()]) for b in raw.GetBonds()]}
    actual_chemistry = {'atoms': [(a.atomic_number, int(a.formal_charge.m_as(unit.elementary_charge)), a.is_aromatic, a.stereochemistry) for a in mol.atoms], 'bonds': [(b.atom1_index, b.atom2_index, float(b.bond_order), b.is_aromatic, b.stereochemistry) for b in mol.bonds]}
    require_normalized_chemistry(expected_chemistry, actual_chemistry)
    atomids = [f'{inputsha}:sdf:{i + 1}' for i in range(mol.n_atoms)]
    companion = {'schema': 'public_ligand_chemical_identity/1.0.0', 'input_sdf_sha256': inputsha, 'atom_ids': atomids, 'coordinates_angstrom': coords.tolist(), 'atoms': [{'index': i, 'element': a.symbol, 'atomic_number': a.atomic_number, 'formal_charge': int(a.formal_charge.m_as(unit.elementary_charge)), 'aromatic': a.is_aromatic, 'stereo': a.stereochemistry, 'name': a.name, 'input_atom_map': raw.GetAtomWithIdx(i).GetAtomMapNum(), 'isotope': raw.GetAtomWithIdx(i).GetIsotope()} for i, a in enumerate(mol.atoms)], 'bonds': [{'atom_i': b.atom1_index, 'atom_j': b.atom2_index, 'order': b.bond_order, 'aromatic': b.is_aromatic, 'stereo': b.stereochemistry} for b in mol.bonds], 'undefined_stereo_allowed': False, 'reference_coordinates_used': False}
    companion['raw_rdkit_observations'] = raw_observations
    companion['normalization_policy'] = 'OpenFF toolkit 0.19.0 RDKit wrapper MDL aromaticity on a copy; no state repair'
    companion['input_rdkit_aromaticity'] = input_aromaticity
    companion['parameterization_aromaticity_model'] = 'MDL'
    companion['aromaticity_representation_changed'] = input_aromaticity['atom_flags'] != [a.is_aromatic for a in mol.atoms] or input_aromaticity['bond_flags'] != [b.is_aromatic for b in mol.bonds]
    dump('chemical-identity.json', companion)
    def chemical_signature():
        return ([(a.atomic_number, int(a.formal_charge.m_as(unit.elementary_charge)), a.is_aromatic, a.stereochemistry) for a in mol.atoms], [(b.atom1_index, b.atom2_index, b.bond_order, b.is_aromatic, b.stereochemistry) for b in mol.bonds])
    original_chemical_signature = chemical_signature()
    formal = float(mol.total_charge.m_as(unit.elementary_charge))
    mol.assign_partial_charges(partial_charge_method='am1bcc', toolkit_registry=AmberToolsToolkitWrapper(), use_conformers=[mol.conformers[0]], strict_n_conformers=True, normalize_partial_charges=False)
    charges = mol.partial_charges.m_as(unit.elementary_charge)
    require(np.isfinite(charges).all(), 'nonfinite charges')
    require(abs(float(charges.sum()) - formal) <= 0.0001, 'AM1BCC net charge mismatch')
    require(np.array_equal(coords, mol.conformers[0].m_as(unit.angstrom)), 'input coordinates changed during charges')
    dump('charges.json', {'method': 'AmberTools26_AM1BCC', 'normalize_partial_charges': False, 'requested_formal_charge_e': formal, 'sum_partial_charge_e': float(charges.sum()), 'sum_tolerance_e': 0.0001, 'charges_e': charges.tolist(), 'supplied_start_conformer_used': True, 'fallback_used': False})
    ffpath = artifact('source-forcefield.offxml')
    ffpath.write_bytes(forcefield_bytes)
    originalsha = sha(ffpath)
    require(originalsha == SAGE_SHA256, 'saved force-field hash mismatch')
    ff = ForceField(str(ffpath))
    removed = 'Constraints' in ff.registered_parameter_handlers
    if removed:
        ff.deregister_parameter_handler('Constraints')
    ff.to_file(str(artifact('resolved-unconstrained-forcefield.offxml')))
    ic = ff.create_interchange(mol.to_topology(), toolkit_registry=rd, charge_from_molecules=[mol], allow_nonintegral_charges=False)
    require(ic.box is None, 'periodic box unexpected')
    system = ic.to_openmm_system(combine_nonbonded_forces=True, add_constrained_forces=True)
    require(system.getNumConstraints() == 0, 'constraints present')
    require(not any((system.isVirtualSite(i) for i in range(system.getNumParticles()))), 'virtual sites unsupported')
    require(system.getNumParticles() == mol.n_atoms, 'particle mismatch')
    original_xml = openmm.XmlSerializer.serialize(system)
    artifact('system-with-momentum-bookkeeping.xml').write_text(original_xml)
    original_force_inventory = [{'index': i, 'class': type(f).__name__} for i, f in enumerate(system.getForces())]
    system = openmm.XmlSerializer.deserialize(original_xml)
    removed_bookkeeping = []
    for i in reversed(range(system.getNumForces())):
        f = system.getForce(i)
        if type(f) is openmm.CMMotionRemover:
            removed_bookkeeping.append({'original_force_index': i, 'class': 'CMMotionRemover', 'frequency': f.getFrequency(), 'name': f.getName(), 'reason': 'explicit_static_energy_model_excludes_momentum_bookkeeping_no_potential_energy'})
            system.removeForce(i)
    require(len(removed_bookkeeping) == 1, 'expected exactly one momentum bookkeeping force')
    forces = {type(f).__name__: f for f in system.getForces()}
    require(len(forces) == system.getNumForces() == 4, 'unexpected/duplicate forceclass')
    require(set(forces) == {'HarmonicBondForce', 'HarmonicAngleForce', 'PeriodicTorsionForce', 'NonbondedForce'}, 'unexpected forceclass')
    nb = forces['NonbondedForce']
    require(nb.getNonbondedMethod() == openmm.NonbondedForce.NoCutoff, 'expectedNoCutoff')
    inactive_switch = {'original_use_switching': nb.getUseSwitchingFunction(), 'switching_distance_nm': nb.getSwitchingDistance().value_in_unit(omu.nanometer), 'cutoff_distance_nm': nb.getCutoffDistance().value_in_unit(omu.nanometer), 'reason': 'explicit_inactive_flag_normalization_under_NoCutoff_only'}
    nb.setUseSwitchingFunction(False)
    inactive_switch['derived_use_switching'] = nb.getUseSwitchingFunction()
    xml = openmm.XmlSerializer.serialize(system)
    artifact('system.xml').write_text(xml)
    tf = forces['PeriodicTorsionForce']
    assignments = []
    idx = 0
    for collname, kind in [('ProperTorsions', 'proper'), ('ImproperTorsions', 'improper')]:
        coll = ic.collections.get(collname)
        if coll is None:
            continue
        for key, pkey in coll.key_map.items():
            atoms = tuple(key.atom_indices)
            params = coll.potentials[pkey].parameters
            per = int(round(float(params['periodicity'])))
            phase = float(params['phase'].m_as(unit.radian))
            idivf = float(params['idivf'])
            k = float(params['k'].m_as(unit.kilojoule_per_mole)) / idivf
            row = tf.getTorsionParameters(idx)
            require(tuple(row[:4]) == atoms and row[4] == per and (abs(row[5].value_in_unit(omu.radian) - phase) < 1e-12) and (abs(row[6].value_in_unit(omu.kilojoule_per_mole) - k) < 1e-12), 'Interchange-to-System torsion mapping mismatch')
            assignments.append({'torsion_index': idx, 'kind': kind, 'atoms': list(atoms), 'star_center': atoms[0] if kind == 'improper' else None, 'periodicity': per, 'phase_radians': phase, 'effective_k_kj_per_mol': k, 'source_smirks': pkey.id, 'source_mult': pkey.mult, 'source_idivf': idivf, 'collection': collname})
            idx += 1
    require(idx == tf.getNumTorsions(), 'incomplete torsion assignment')
    dump('torsion-assignments.json', assignments)
    metadata = {'schema': 'openff_ligand_preparation/1.0.0', 'scope': 'ligand_only_no_receptor', 'source_forcefield': 'openff-2.2.1.offxml', 'original_forcefield_sha256': originalsha, 'resolved_forcefield_sha256': artifact_sha('resolved-unconstrained-forcefield.offxml'), 'constraints_handler_explicitly_removed': removed, 'model': 'nonperiodic_NoCutoff_unconstrained_no_GB', 'system_xml_sha256': artifact_sha('system.xml'), 'chemical_identity_sha256': artifact_sha('chemical-identity.json'), 'torsion_assignment_sha256': artifact_sha('torsion-assignments.json'), 'charges_sha256': artifact_sha('charges.json'), 'input_sdf_sha256': inputsha, 'atoms': mol.n_atoms, 'bonds': forces['HarmonicBondForce'].getNumBonds(), 'angles': forces['HarmonicAngleForce'].getNumAngles(), 'periodic_torsions': tf.getNumTorsions(), 'proper_entries': sum((r['kind'] == 'proper' for r in assignments)), 'improper_entries': sum((r['kind'] == 'improper' for r in assignments)), 'nonbonded_exceptions': nb.getNumExceptions(), 'coordinates_unchanged': np.array_equal(coords, mol.conformers[0].m_as(unit.angstrom)), 'own_engine_calls': 0, 'reference_energy_calls': 0, 'input_sdf_unchanged': sha(S) == inputsha}
    metadata.update({'charge_recomputation': True, 'backend_versions': versions, 'original_system_xml_sha256': artifact_sha('system-with-momentum-bookkeeping.xml'), 'original_force_inventory': original_force_inventory, 'removed_bookkeeping': removed_bookkeeping, 'inactive_switch_derivation': inactive_switch, 'system_charge_e': [nb.getParticleParameters(i)[0].value_in_unit(omu.elementary_charge) for i in range(mol.n_atoms)]})
    require(artifact_sha('input.sdf') == inputsha, 'preserved input artifact changed')
    require(metadata['input_sdf_unchanged'] and metadata['coordinates_unchanged'], 'source or coordinates mutated')
    require(np.allclose(metadata['system_charge_e'], charges, rtol=0, atol=1e-12), 'System changed AM1BCC charges')
    require(chemical_signature() == original_chemical_signature, 'chemical identity changed during parameterization')
    metadata['xml_derivation_structure_verified'] = verify_static_derivation(original_xml, xml)
    require(metadata['xml_derivation_structure_verified'], 'non-allowlisted System XML change')
    dump('parameterization-result.json', metadata)
    return metadata

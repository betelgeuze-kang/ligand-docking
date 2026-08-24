use super::{
    checked_count, digest_present, finite, invalid, Fixed64Identities, Fixed64PipelineContext,
    Result,
};

pub(super) struct ValidatedContext {
    pub(super) receptor_atom_count: u64,
    pub(super) ligand_atom_count: u64,
}

impl Fixed64PipelineContext<'_> {
    pub(super) fn validate(&self) -> Result<ValidatedContext> {
        let receptor_count = self.receptor.coordinates.validate()?;
        let ligand_count = self.ligand.reference_coordinates.validate()?;
        if receptor_count == 0 || ligand_count == 0 {
            return Err(invalid(
                "fixed64 receptor and ligand atom counts must be non-zero",
            ));
        }
        validate_f64_channels(
            receptor_count,
            &[
                (self.receptor.vdw_radius_angstrom, "receptor vdw radii"),
                (self.receptor.charge_elementary, "receptor charges"),
                (
                    self.receptor.epsilon_kcal_per_mol,
                    "receptor epsilon values",
                ),
            ],
        )?;
        validate_masks(
            receptor_count,
            &[
                (self.receptor.hydrophobic_mask, "receptor hydrophobic mask"),
                (self.receptor.acceptor_mask, "receptor acceptor mask"),
            ],
        )?;
        validate_f64_channels(
            ligand_count,
            &[
                (self.ligand.vdw_radius_angstrom, "ligand vdw radii"),
                (self.ligand.charge_elementary, "ligand charges"),
                (self.ligand.epsilon_kcal_per_mol, "ligand epsilon values"),
            ],
        )?;
        validate_masks(
            ligand_count,
            &[
                (self.ligand.heavy_atom_mask, "ligand heavy-atom mask"),
                (self.ligand.hydrophobic_mask, "ligand hydrophobic mask"),
                (self.ligand.acceptor_mask, "ligand acceptor mask"),
            ],
        )?;
        if self.ligand.parent_atom_index.len() != ligand_count {
            return Err(invalid(
                "ligand parent-atom channel must match the ligand atom count",
            ));
        }
        if !finite(&self.pocket_center_angstrom)
            || !self.pocket_radius_angstrom.is_finite()
            || self.pocket_radius_angstrom <= 0.0
        {
            return Err(invalid(
                "fixed64 pocket center and radius must be finite and the radius positive",
            ));
        }
        for radius in self
            .receptor
            .vdw_radius_angstrom
            .iter()
            .chain(self.ligand.vdw_radius_angstrom.iter())
        {
            if *radius <= 0.0 {
                return Err(invalid("fixed64 vdw radii must be strictly positive"));
            }
        }
        for epsilon in self
            .receptor
            .epsilon_kcal_per_mol
            .iter()
            .chain(self.ligand.epsilon_kcal_per_mol.iter())
        {
            if *epsilon < 0.0 {
                return Err(invalid("fixed64 epsilon values must be non-negative"));
            }
        }
        validate_digests(self.identities)?;
        validate_topology(self, receptor_count, ligand_count)?;
        Ok(ValidatedContext {
            receptor_atom_count: checked_count(receptor_count)?,
            ligand_atom_count: checked_count(ligand_count)?,
        })
    }
}

fn validate_f64_channels(expected: usize, channels: &[(&[f64], &str)]) -> Result<()> {
    for (values, label) in channels {
        if values.len() != expected {
            return Err(invalid(format!(
                "{label} must match its molecular atom count"
            )));
        }
        if !finite(values) {
            return Err(invalid(format!("{label} must contain only finite values")));
        }
    }
    Ok(())
}

fn validate_masks(expected: usize, channels: &[(&[u8], &str)]) -> Result<()> {
    for (values, label) in channels {
        if values.len() != expected {
            return Err(invalid(format!(
                "{label} must match its molecular atom count"
            )));
        }
        if values.iter().any(|value| *value > 1) {
            return Err(invalid(format!("{label} must contain only 0 or 1")));
        }
    }
    Ok(())
}

fn validate_digests(identities: Fixed64Identities) -> Result<()> {
    let values = [
        (
            identities.authority_input_receipt_sha256,
            "authority input receipt",
        ),
        (identities.receptor_system_sha256, "receptor system"),
        (identities.ligand_system_sha256, "ligand system"),
        (identities.backend_receipt_sha256, "backend receipt"),
        (
            identities.validity_scorer_context_receipt_sha256,
            "validity scorer-context receipt",
        ),
        (identities.contact_policy_sha256, "contact policy"),
    ];
    for (digest, label) in values {
        if !digest_present(&digest) {
            return Err(invalid(format!("fixed64 {label} SHA-256 is absent")));
        }
    }
    Ok(())
}

fn validate_topology(
    context: &Fixed64PipelineContext<'_>,
    receptor_count: usize,
    ligand_count: usize,
) -> Result<()> {
    for donor in context.receptor.donors {
        validate_index(donor.donor_atom_index, receptor_count, "receptor donor")?;
        validate_index(
            donor.hydrogen_atom_index,
            receptor_count,
            "receptor donor hydrogen",
        )?;
    }
    for donor in context.ligand.donors {
        validate_index(donor.donor_atom_index, ligand_count, "ligand donor")?;
        validate_index(
            donor.hydrogen_atom_index,
            ligand_count,
            "ligand donor hydrogen",
        )?;
    }
    for (pairs, label) in [
        (context.ligand.exclusions, "ligand exclusion"),
        (context.ligand.bonds, "ligand bond"),
        (context.ligand.internal_pairs, "ligand internal pair"),
    ] {
        for pair in pairs {
            validate_index(pair.atom_i, ligand_count, label)?;
            validate_index(pair.atom_j, ligand_count, label)?;
        }
    }
    for rotor in context.ligand.rotors {
        for atom in [rotor.atom_i, rotor.atom_j, rotor.atom_k, rotor.atom_l] {
            validate_index(atom, ligand_count, "ligand rotor")?;
        }
    }
    for center in context.ligand.chirality_centers {
        for atom in [
            center.center_atom,
            center.atom_i,
            center.atom_j,
            center.atom_k,
        ] {
            validate_index(atom, ligand_count, "ligand chirality center")?;
        }
    }
    for child in context.ligand.rotatable_child_atom_index {
        validate_index(*child, ligand_count, "rotatable child atom")?;
    }
    for parent in context.ligand.parent_atom_index {
        if *parent < -1 || (*parent >= 0 && *parent as usize >= ligand_count) {
            return Err(invalid("ligand parent atom index is out of range"));
        }
    }
    Ok(())
}

fn validate_index(index: u64, count: usize, label: &str) -> Result<()> {
    let index =
        usize::try_from(index).map_err(|_| invalid(format!("{label} index does not fit usize")))?;
    if index >= count {
        return Err(invalid(format!("{label} index is out of range")));
    }
    Ok(())
}

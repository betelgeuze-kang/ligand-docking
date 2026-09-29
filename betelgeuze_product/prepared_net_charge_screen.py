"""Source-bound ligand net-charge consistency screen for research ranking.

This only compares the SDF's encoded integral formal charge with the ligand
ITP's printed partial-charge total. It does not assign charges or establish a
chemical state, parameter quality, or physical validity.
"""

from __future__ import annotations

from decimal import Decimal, Inexact, InvalidOperation, localcontext
import math

SCHEMA = "prepared_ligand_net_charge_rank_screen_v1"
MAX_DECIMAL_SPAN = 4096
MAX_RANK_DIFFERENCE_E = Decimal("0.5")
COMPILED_PROFILES = {
    "compiled_gromacs_cross_particles_v1",
    "compiled_gromacs_cross_particles_v2",
}
PREPARED_SOURCE_ROLES = {
    "prepared_gromacs_components_v1": ("ligand_sdf", "ligand_itp"),
    "prepared_gromacs_components_v2": ("ligand_sdf", "ligand_itp"),
    "prepared_gromacs_components_v3": ("ligand_sdf", "ligand_itp"),
    "prepared_gromacs_coordinate_derivation_v1": ("ligand_sdf", "ligand_itp"),
    "prepared_gromacs_coordinate_array_v1": ("parent_ligand_sdf", "parent_ligand_itp"),
}
SDF_FORMAL_STATUS = "sdf_v2000_encoded_formal_charge_not_measurement"
COMPILED_FORMAL_STATUS = "unavailable_canonical_default_not_an_observation"


def _arithmetic(tokens, formal_sum):
    """Repeat the loader's bounded exact arithmetic and add a print bound."""
    values = []
    try:
        for token in tokens:
            if type(token) is not str or len(token) > MAX_DECIMAL_SPAN:
                return None, None, "indeterminate", "charge_token_exceeds_diagnostic_bound", None
            value = Decimal(token)
            if (not value.is_finite()
                    or abs(value.as_tuple().exponent) > MAX_DECIMAL_SPAN):
                return None, None, "indeterminate", "charge_exponent_exceeds_diagnostic_bound", None
            values.append(value)
    except (InvalidOperation, ValueError):
        return None, None, "indeterminate", "charge_token_not_decimal_parseable", None
    reference = Decimal(formal_sum)
    minimum_exponent = min([reference.as_tuple().exponent,
                            *(value.as_tuple().exponent for value in values)])
    maximum_adjusted = max([reference.adjusted(),
                            *(value.adjusted() for value in values)])
    precision = maximum_adjusted - minimum_exponent + len(str(len(values) + 1)) + 2
    if precision > MAX_DECIMAL_SPAN:
        return None, None, "indeterminate", "charge_precision_span_exceeds_diagnostic_bound", None
    try:
        with localcontext() as context:
            context.prec = max(1, precision)
            context.traps[Inexact] = True
            partial_sum = sum(values, Decimal(0))
            difference = partial_sum - reference
            # One unit in each token's last printed decimal place is a
            # conservative representation bound without assuming a rounding mode.
            print_bound = sum((Decimal(1).scaleb(value.as_tuple().exponent)
                               for value in values), Decimal(0))
    except (Inexact, InvalidOperation):
        return None, None, "indeterminate", "charge_decimal_arithmetic_inexact", None
    relation = "equal_as_encoded" if difference == 0 else "different_as_encoded"
    return str(partial_sum), str(difference), relation, None, print_bound


def _source_atoms(report, formal_status):
    """Cross-check the receipt observation against its embedded ligand state."""
    rows = report.get("rows")
    if type(rows) is not list or not rows:
        raise ValueError("pose_report_ligand_charge_source_mismatch")
    signatures = []
    for row in rows:
        try:
            ligand = row["result"]["sources"]["ligand"]
            atoms = ligand["system"]["system"]["topology"]["atoms"]
            parameters = ligand["nonbonded_parameters"]
            if (type(atoms) is not list or not atoms or type(parameters) is not list
                    or len(atoms) != len(parameters)):
                raise ValueError
            formal = []
            tokens = []
            for index, (atom, parameter) in enumerate(zip(atoms, parameters)):
                charge = parameter["charge_e"]
                encoded = atom["partial_charge_e"]["$float_hex"]
                metadata = atom["metadata"]
                origin = metadata["prepared_gromacs_source"]
                source = origin["source_row"]
                token = source["tokens"][6]
                if (type(atom["index"]) is not int or atom["index"] != index
                        or type(atom["formal_charge"]) is not int
                        or origin.get("formal_charge_annotation_status") != formal_status
                        or (formal_status == COMPILED_FORMAL_STATUS
                            and (atom["formal_charge"] != 0
                                 or metadata.get("formal_charge_observation", "missing") is not None))
                        or type(charge) not in (int, float) or not math.isfinite(charge)
                        or type(token) is not str
                        or float(token) != charge or float.fromhex(encoded) != charge):
                    raise ValueError
                formal.append(atom["formal_charge"])
                tokens.append(token)
            signatures.append((tuple(formal), tuple(tokens)))
        except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("pose_report_ligand_charge_source_mismatch") from exc
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise ValueError("pose_report_ligand_charge_source_mismatch")
    formal, tokens = signatures[0]
    return sum(formal), list(tokens)


def _prepared_charge_screen(provenance, formal_sum, tokens):
    """Apply the same rank-only decision to a parsed source or pose report."""
    profile = provenance.get("schema_version")
    observation = provenance.get("ligand_source_net_charge_observation")
    sources = provenance.get("sources")
    if profile not in PREPARED_SOURCE_ROLES or type(observation) is not dict:
        raise ValueError("pose_report_ligand_charge_source_mismatch")
    partial, difference, relation, reason, print_bound = _arithmetic(tokens, formal_sum)
    expected = {
        "selected_atom_count": len(tokens),
        "sdf_encoded_formal_charge_sum_e": formal_sum,
        "itp_printed_partial_charge_sum_e": partial,
        "itp_minus_sdf_charge_sum_e": difference,
        "arithmetic_relation": relation,
        "diagnostic_unavailable_reason": reason,
    }
    if any(observation.get(key) != value for key, value in expected.items()):
        raise ValueError("pose_report_ligand_charge_source_mismatch")
    sdf_role, itp_role = PREPARED_SOURCE_ROLES[profile]
    if (type(sources) is not dict
            or type(sources.get(sdf_role)) is not dict
            or type(sources.get(itp_role)) is not dict
            or type(sources[sdf_role].get("sha256")) is not str
            or type(sources[itp_role].get("sha256")) is not str
            or observation.get("sdf_source_sha256") != sources[sdf_role]["sha256"]
            or observation.get("itp_source_sha256") != sources[itp_role]["sha256"]):
        raise ValueError("pose_report_ligand_charge_source_mismatch")
    if relation == "indeterminate":
        status = "indeterminate"
    elif difference == "0.0" or Decimal(difference) == 0:
        status = "equal_as_encoded"
    elif abs(Decimal(difference)) >= MAX_RANK_DIFFERENCE_E:
        status = "different_integral_state_range"
    elif print_bound >= MAX_RANK_DIFFERENCE_E:
        status = "insufficient_print_resolution"
    elif abs(Decimal(difference)) > print_bound:
        status = "difference_exceeds_print_resolution"
    else:
        status = "within_print_resolution"
    return {
        "schema_version": SCHEMA, "profile": profile,
        "status": status,
        "rank_eligible": status in {"equal_as_encoded", "within_print_resolution"},
        "sdf_formal_charge_sum_e": formal_sum,
        "itp_printed_partial_charge_sum_e": partial,
        "difference_e": difference,
        "print_resolution_bound_e": str(print_bound) if print_bound is not None else None,
        "maximum_rank_difference_e": str(MAX_RANK_DIFFERENCE_E),
        "scope": "source net-charge arithmetic for research ranking only; not chemical or physical validation",
    }


def ligand_net_charge_source_screen(ligand, provenance):
    """Screen loader-verified direct GROMACS sources before numeric execution."""
    try:
        if (type(provenance) is not dict
                or provenance.get("schema_version") not in {
                    "prepared_gromacs_components_v1",
                    "prepared_gromacs_components_v2",
                    "prepared_gromacs_components_v3",
                }
                or provenance.get("source_hashes_postflight_verified") is not True):
            raise ValueError
        rows = provenance["original_topologies"]["ligand_itp"]["sections"]["atoms"]
        if type(rows) is not list or len(rows) != ligand.atom_count:
            raise ValueError
        tokens = [row["tokens"][6] for row in rows]
        formal_sum = sum(atom.formal_charge for atom in ligand.atoms)
        return _prepared_charge_screen(provenance, formal_sum, tokens)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("prepared_ligand_charge_source_mismatch") from exc


def ligand_net_charge_screen(report):
    """Return a fixed rank-only decision; leave the numeric report untouched."""
    shared = report.get("preparation")
    provenance = shared.get("preparation_provenance") if type(shared) is dict else None
    if type(provenance) is not dict:
        raise ValueError("pose_report_ligand_charge_source_mismatch")
    profile = provenance.get("schema_version")
    observation = provenance.get("ligand_source_net_charge_observation")
    sources = provenance.get("sources")
    if profile in COMPILED_PROFILES:
        expected_sources = ({"topology", "coordinates"}
                            if profile == "compiled_gromacs_cross_particles_v1"
                            else {"topology", "coordinates", "refined_coordinates"})
        if (observation is not None or type(sources) is not dict
                or set(sources) != expected_sources
                or type(sources.get("topology")) is not dict
                or type(sources["topology"].get("sha256")) is not str
                or provenance.get("formal_charge_observations_available") is not False
                or provenance.get("source_topology_sha256")
                != sources["topology"]["sha256"]):
            raise ValueError("pose_report_ligand_charge_source_mismatch")
        _source_atoms(report, COMPILED_FORMAL_STATUS)
        return {
            "schema_version": SCHEMA, "profile": profile,
            "status": "not_assessed_compiled_profile", "rank_eligible": True,
            "sdf_formal_charge_sum_e": None,
            "itp_printed_partial_charge_sum_e": None,
            "difference_e": None, "print_resolution_bound_e": None,
            "maximum_rank_difference_e": str(MAX_RANK_DIFFERENCE_E),
            "scope": "no SDF formal-charge source in compiled particle profile; not chemical validation",
        }
    formal_sum, tokens = _source_atoms(report, SDF_FORMAL_STATUS)
    return _prepared_charge_screen(provenance, formal_sum, tokens)

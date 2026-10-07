from dataclasses import replace
import pytest
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter,
    PeriodicTorsionParameter,
    ReferenceParameterError,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from betelgeuze_product.cpu_refinement_fourier_v1 import (
    FourierParameters,
    NonbondedParameter,
    SignedPeriodicTorsionParameter,
    OrderedPeriodicImproperParameter,
    ListedPairParameter,
)


def model():
    return FourierParameters(
        "control",
        "1",
        "a" * 64,
        tuple(NonbondedParameter(i, 1.0, 0.1, 0.0) for i in range(4)),
        torsions=(SignedPeriodicTorsionParameter(0, 1, 2, 3, 2, 0.0, -2.0),),
        excluded_pairs=((0, 3),),
        listed_pairs=(ListedPairParameter(0, 3, 1.5, 0.2, 0.83333),),
    )


def test_old_types_still_reject_new_domain():
    with pytest.raises(ReferenceParameterError):
        AtomNonbondedParameter(0, 0.0, 0.0, 1.0)
    with pytest.raises(ReferenceParameterError):
        PeriodicTorsionParameter(0, 1, 2, 3, 2, 0.0, -2.0)


def test_distinct_types_and_original_signed_value():
    row = SignedPeriodicTorsionParameter(0, 1, 2, 3, 2, 0.0, -2.0)
    assert not isinstance(row, PeriodicTorsionParameter)
    assert row.amplitude_kcal_per_mol == -2.0
    zero = NonbondedParameter(0, 0.0, 0.0, 1.0)
    assert not isinstance(zero, AtomNonbondedParameter)
    assert zero.charge_e == 1.0


def test_no_zero_sigma_positive_epsilon():
    with pytest.raises(ResearchError):
        NonbondedParameter(0, 0.0, 0.1, 1.0)
    with pytest.raises(ResearchError):
        ListedPairParameter(0, 1, 0.0, 0.1, 0.8)


def test_roundtrip_and_schema_separation():
    original = model()
    assert FourierParameters.from_dict(original.to_dict()) == original
    payload = original.to_dict()
    payload["schema_id"] = "betelgeuze.reference_parameters/1.0.0"
    with pytest.raises(ResearchError):
        FourierParameters.from_dict(payload)


def test_listed_pair_no_double_count():
    with pytest.raises(ResearchError):
        replace(model(), excluded_pairs=())
    with pytest.raises(ResearchError):
        replace(model(), listed_pairs=model().listed_pairs * 2)


def test_improper_not_accepted_as_proper_row():
    improper = OrderedPeriodicImproperParameter(0, 1, 2, 3, 2, 0.0, 0.1, star_center=0)
    with pytest.raises(ResearchError):
        replace(model(), torsions=(improper,))
    with pytest.raises(ResearchError):
        OrderedPeriodicImproperParameter(0, 1, 2, 3, 2, 0.0, 0.1, star_center=4)


def test_mutation_changes_fingerprint():
    original = model()
    changed = replace(
        original, torsions=(replace(original.torsions[0], amplitude_kcal_per_mol=-3.0),)
    )
    assert original.fingerprint_sha256 != changed.fingerprint_sha256
    changed = replace(
        original, listed_pairs=(replace(original.listed_pairs[0], sigma_angstrom=1.6),)
    )
    assert original.fingerprint_sha256 != changed.fingerprint_sha256

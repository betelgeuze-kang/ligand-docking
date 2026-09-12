"""Fresh synthetic method/target conflicts; no protected evaluation values."""

import pytest
from tools.product import public_chembl_receptor_intake as intake


def declared(description):
    activity = {
        "assay_chembl_id": "CHEMBL123",
        "document_chembl_id": "CHEMBL456",
        "target_chembl_id": "CHEMBL3371",
    }
    method = {
        **activity,
        "assay_type": "B",
        "assay_tax_id": 9606,
        "confidence_score": 9,
        "description": "Radioligand binding. " + description,
    }
    return method, activity, {"document_chembl_id": "CHEMBL456"}


@pytest.mark.parametrize(
    "receptor",
    [
        "5HT1A",
        "5-HT1A",
        "5 HT 1A",
        "5‐HT1A",
        "5‑HT1A",
        "5–HT1A",
        "5—HT1A",
        "5HT2A",
        "5HT2B",
        "5HT7",
    ],
)
def test_explicit_other_receptor_cannot_pass_matching_catalogue_ids(receptor):
    assert not intake.method_supported(
        *declared(
            "Receptor Source: Human recombinant "
            + receptor
            + " expressed mammalian cells."
        )
    )


def test_multiple_receptors_are_ambiguous_without_explicit_method_resolution():
    assert not intake.method_supported(*declared("Human 5-HT6 and 5-HT1A receptors."))


@pytest.mark.parametrize(
    "description",
    [
        "Receptor Source: Human recombinant 5-HT6 expressed mammalian cells.",
        "Human 5HT 6 receptor; pH 7.4, 1 hour, 10 mM MgSO4.",
        "Synthetic generic binding description; catalogue identity only.",
    ],
)
def test_matching_or_noncontradictory_curated_description_retains_prior_scope(
    description,
):
    assert intake.method_supported(*declared(description))

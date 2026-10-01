"""Filename indexing must not admit malformed or out-of-order journal entries."""

import pytest

from betelgeuze_product.cpu_refinement_v1_2.candidate_journal import open_journal
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_cpu_candidate_journal import binding, validate


@pytest.mark.parametrize(
    "name",
    [
        "candidate-000000-intent-00000.json",
        "candidate-00000-intent-000000.json",
        "candidate-00000-intent-00000.json.extra",
        "candidate-99999-intent-00000.json",
        "candidate-00000-record-00000.json.partial",
        "candidate-00000-intent-00001.json",
        "candidate-０００００-intent-00000.json",
        "candidate-00000-record-00000.json",
    ],
)
def test_untrusted_filename_never_bypasses_order_or_admission(tmp_path, name):
    path = tmp_path / "journal"
    b = binding()
    with open_journal(path, b, validate_record=validate):
        pass
    (path / name).write_text("{}")
    before = {p.name: p.read_bytes() for p in path.iterdir()}
    with pytest.raises(ResearchError):
        with open_journal(path, b, validate_record=validate, resume=True):
            pytest.fail("untrusted filename admitted")
    assert before == {p.name: p.read_bytes() for p in path.iterdir()}

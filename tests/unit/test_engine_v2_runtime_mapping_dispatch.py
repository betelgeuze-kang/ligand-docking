"""Runtime ABC checks must preserve the original typing.Mapping dispatch."""
from collections import UserDict
from types import MappingProxyType

import pytest

from betelgeuze_engine_v2.molecular.serialization import (
    CanonicalSerializationError, _require_mapping, canonical_json_value,
)
from betelgeuze_engine_v2.stack_round3_integrity_compat import _identity_value


class ClaimedMapping:
    """An unsupported object can advertise a dict without actually being one."""
    @property
    def __class__(self):
        return dict

    def __iter__(self):
        return iter({"value": 0.0})

    def __getitem__(self, key):
        return {"value": 0.0}[key]

    def items(self):
        return {"value": 0.0}.items()

    def __repr__(self):
        return "ClaimedMapping()"


@pytest.mark.parametrize("nested", [False, True])
def test_canonical_rejects_object_claiming_mapping_class(nested):
    value = ClaimedMapping()
    if nested:
        value = {"nested": value}
    with pytest.raises(CanonicalSerializationError, match="unsupported canonical value"):
        canonical_json_value(value)


@pytest.mark.parametrize("nested", [False, True])
def test_integrity_retains_repr_identity_for_nonmapping(nested):
    value = ClaimedMapping()
    expected = {"$repr_identity": "ClaimedMapping()"}
    if nested:
        value, expected = {"nested": value}, {"nested": expected}
    assert _identity_value(value) == expected


def test_decoder_rejects_object_claiming_mapping_class():
    with pytest.raises(CanonicalSerializationError, match="mapping"):
        _require_mapping(ClaimedMapping(), path="$.system")


@pytest.mark.parametrize("factory", [dict, UserDict, MappingProxyType])
def test_real_mapping_preserves_zero_and_signed_zero(factory):
    value = factory({"measured": 0.0, "signed": -0.0, "absent": None})
    assert _require_mapping(value, path="$.system") is value
    assert canonical_json_value(value) == {
        "absent": None, "measured": {"$float_hex": "0x0.0p+0"},
        "signed": {"$float_hex": "-0x0.0p+0"},
    }
    assert _identity_value(value) == {
        "absent": None, "measured": {"$float_identity": "0x0.0p+0"},
        "signed": {"$float_identity": "-0x0.0p+0"},
    }

"""Differential coverage against the canonical normalizer at 031894211.

The small frozen oracle below preserves that committed implementation; it does
not import the candidate's decision helpers or require a historical checkout.
"""
from collections import UserDict
from dataclasses import dataclass, fields, is_dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pytest
import torch

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular import serialization as candidate
from betelgeuze_engine_v2.molecular.serialization import CanonicalSerializationError
from betelgeuze_engine_v2.stack_round3_molecular import MolecularIntegrityError
from tests.unit.test_cpu_fixed_receptor import system

def _baseline_float_token(value: float, *, path: str) -> dict[str, str]:
    number = float(value)
    if not math.isfinite(number):
        raise CanonicalSerializationError(f"non-finite float at {path}")
    return {"$float_hex": number.hex()}


def _baseline_value(value: Any, *, path: str = "$") -> Any:
    """Return a JSON-safe value with deterministic ordering and float encoding."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _baseline_float_token(value, path=path)
    if isinstance(value, Path):
        return {"$path": value.as_posix()}
    if isinstance(value, torch.Tensor):
        if not value.is_floating_point() and value.dtype != torch.bool:
            data = value.detach().cpu().reshape(-1).tolist()
        elif value.dtype == torch.bool:
            data = [bool(item) for item in value.detach().cpu().reshape(-1).tolist()]
        else:
            data = [
                _baseline_float_token(float(item), path=f"{path}.values[{index}]")
                for index, item in enumerate(value.detach().cpu().reshape(-1).tolist())
            ]
        return {
            "$tensor": {
                "dtype": str(value.dtype).removeprefix("torch."),
                "shape": [int(size) for size in value.shape],
                "values": data,
            }
        }
    if is_dataclass(value):
        return {
            field.name: _baseline_value(
                getattr(value, field.name),
                path=f"{path}.{field.name}",
            )
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            text = str(key)
            if text in normalized:
                raise CanonicalSerializationError(
                    f"mapping keys collide after string conversion at {path}: {text!r}"
                )
            normalized[text] = _baseline_value(value[key], path=f"{path}.{text}")
        return normalized
    if isinstance(value, (tuple, list)):
        return [
            _baseline_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise CanonicalSerializationError(
        f"unsupported canonical value at {path}: {type(value).__name__}"
    )



def _bytes(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class Record:
    name: str
    values: Any
    metadata: Any


@pytest.mark.parametrize("value", [
    None, True, 17, "한글\n\"", 0.0, -0.0, 1e-300, Path("a/한글"),
    (0.0, [False, -0.0]), {3: "three", "two": 2, 1: -0.0},
    MappingProxyType({"z": [1, -0.0], "a": Path("b")}),
    UserDict({"x": Record("r", (1.25, None), {"q": -0.0})}),
    torch.tensor([[0.0, -0.0], [1.25, -2.0]], dtype=torch.float64).T,
    torch.tensor([True, False]), torch.tensor([1, -2], dtype=torch.int64),
    torch.empty((0, 3), dtype=torch.float32),
])
def test_exact_normalized_value_bytes_and_sha(value):
    expected = _baseline_value(value)
    assert candidate.canonical_json_value(value) == expected
    expected_bytes = _bytes(expected)
    assert candidate.canonical_json_bytes(value) == expected_bytes
    assert candidate.sha256_canonical(value) == hashlib.sha256(expected_bytes).hexdigest()


@pytest.mark.parametrize("value", [
    float("nan"), {"outer": [float("inf")]},
    Record("r", {"negative": float("-inf")}, {}),
    {"t": torch.tensor([[0.0, float("nan")]], dtype=torch.float64)},
    [{"bad": object()}], {"collision": {1: "first", "1": "second"}},
    {"same.first.path": [Record("r", {"x": object()}, {})]},
])
@pytest.mark.parametrize("path", ["$", "custom.root[2]"])
def test_exact_exception_class_message_and_custom_path(value, path):
    errors = []
    for normalize in (_baseline_value, candidate.canonical_json_value):
        with pytest.raises(CanonicalSerializationError) as raised:
            normalize(value, path=path)
        errors.append((type(raised.value), str(raised.value)))
    assert errors[0] == errors[1]


class TracedMapping(Mapping):
    def __init__(self, log, *, mutate=False):
        self.log = log
        self.values = {"z": 2.0, "a": -0.0}
        self.mutate = mutate
    def __iter__(self):
        self.log.append("iter")
        return iter(self.values)
    def __len__(self):
        return len(self.values)
    def __getitem__(self, key):
        self.log.append(("get", key))
        if self.mutate and key == "a":
            self.values["z"] = float("nan")
        return self.values[key]


@pytest.mark.parametrize("mutate", [False, True])
def test_mapping_read_order_and_mutation_during_traversal(mutate):
    outcomes = []
    for normalize in (_baseline_value, candidate.canonical_json_value):
        log = []
        try:
            value = normalize({"nested": TracedMapping(log, mutate=mutate)})
            result = ("ok", _bytes(value))
        except CanonicalSerializationError as error:
            result = (type(error), str(error))
        outcomes.append((log, result))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == ["iter", ("get", "a"), ("get", "z")]


def test_getter_error_is_not_reinterpreted():
    class Broken(TracedMapping):
        def __getitem__(self, key):
            raise CanonicalSerializationError("original getter error")
    for normalize in (_baseline_value, candidate.canonical_json_value):
        with pytest.raises(CanonicalSerializationError, match="^original getter error$"):
            normalize({"nested": Broken([])})


@pytest.mark.parametrize("kind", ["coordinates_data", "coordinates_numpy", "metadata_tensor",
                                  "atom_metadata", "provenance", "signed_zero"])
def test_full_integrity_hash_still_rejects_in_memory_mutation(kind):
    state = system([[0, 0, 0]])
    state = replace(state, metadata={"nested": torch.tensor([1.0])},
                    atoms=(replace(state.atoms[0], metadata={"nested": torch.tensor([1.0])}),))
    expected = canonical_system_sha256(state)
    assert expected == candidate.sha256_canonical(candidate.canonical_system_payload(state))
    if kind == "coordinates_data":
        version = state.coordinates._version
        state.coordinates.data[0, 0, 0] = 1.0
        assert state.coordinates._version == version
    elif kind == "coordinates_numpy":
        version = state.coordinates._version
        state.coordinates.numpy()[0, 0, 0] = 1.0
        assert state.coordinates._version == version
    elif kind == "metadata_tensor":
        state.metadata["nested"].data[0] = 2.0
    elif kind == "atom_metadata":
        state.atoms[0].metadata["nested"].numpy()[0] = 2.0
    elif kind == "provenance":
        object.__setattr__(state.provenance, "source_id", "changed")
    else:
        state.coordinates.data[0, 0, 0] = -0.0
    with pytest.raises(MolecularIntegrityError, match="changed"):
        canonical_system_sha256(state)


@pytest.mark.parametrize("value", [float("nan"), {1: "one", "1": "string one"}, object()])
def test_invalid_at_construction_keeps_raw_integrity_but_fails_canonical(value):
    state = replace(system([[0, 0, 0]]), metadata={"invalid": value})
    state.assert_integrity()
    with pytest.raises(CanonicalSerializationError):
        canonical_system_sha256(state)


def test_equal_replacement_is_not_rejected_and_each_canonical_call_is_fresh(monkeypatch):
    state = system([[0, 0, 0]])
    expected = canonical_system_sha256(state)
    object.__setattr__(state, "atoms", (replace(state.atoms[0]),))
    calls = []
    original = candidate._canonical_json_value
    def counted(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(candidate, "_canonical_json_value", counted)
    assert canonical_system_sha256(state) == expected
    count = len(calls)
    assert count > 20
    assert canonical_system_sha256(state) == expected
    assert len(calls) == 2 * count


def test_canonical_collision_rejected_even_when_raw_integrity_is_unchanged():
    state = replace(system([[0, 0, 0]]), metadata={1: "same"})
    expected_raw = state.integrity_sha256
    canonical_system_sha256(state)
    # The raw identity intentionally stringifies keys, while canonical validity
    # must reject two keys that collapse to the same text.
    object.__setattr__(state, "metadata", {1: "same", "1": "same"})
    state.assert_integrity()
    assert state.integrity_sha256 == expected_raw
    with pytest.raises(CanonicalSerializationError, match="mapping keys collide"):
        canonical_system_sha256(state)


@pytest.mark.parametrize("mutation", ["getter", "child_error"])
def test_dataclass_key_and_diagnostic_name_read_order(mutation):
    outcomes = []
    for normalize in (_baseline_value, candidate.canonical_json_value):
        log = []

        @dataclass
        class MutableField:
            first: Any

            def __getattribute__(self, name):
                if name == "first":
                    log.append("get_first")
                    if mutation == "getter":
                        type(self).__dataclass_fields__["first"].name = "renamed"
                return object.__getattribute__(self, name)

        class MutatingChild(TracedMapping):
            def __getitem__(self, key):
                MutableField.__dataclass_fields__["first"].name = "renamed_by_child"
                return float("nan")

        value = MutableField(2.0 if mutation == "getter" else MutatingChild(log))
        try:
            result = ("ok", _bytes(normalize(value)))
        except CanonicalSerializationError as error:
            result = (type(error), str(error))
        outcomes.append((log, result))
    assert outcomes[0] == outcomes[1]

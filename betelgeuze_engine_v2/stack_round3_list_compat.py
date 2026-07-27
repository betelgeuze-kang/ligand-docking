"""Preserve public container semantics while recursively freezing metadata.

Existing molecular receipts expose ordered values as lists and structured
metadata as dictionaries. ``FrozenList`` and ``FrozenDict`` retain those public
JSON/equality contracts while every ordinary in-place mutation path fails
closed.
"""

from __future__ import annotations

from typing import Any
import hashlib
import json
import sys
from collections.abc import Mapping

import torch


STACK_ROUND3_LIST_COMPAT_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round3_list_compat/1.0.0"
)


class FrozenList(list):
    """List-compatible ordered metadata with all mutation operations disabled."""

    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("frozen metadata lists cannot be mutated")

    @staticmethod
    def _append_unavailable(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AttributeError("frozen metadata lists do not expose append")

    __setitem__ = _immutable
    __delitem__ = _immutable
    append = _append_unavailable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


class FrozenDict(dict):
    """Dict-compatible structured metadata with mutation operations disabled."""

    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("frozen metadata mappings cannot be mutated")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


def _deep_freeze_compatible(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenDict(
            {
                key: _deep_freeze_compatible(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, list):
        return FrozenList(_deep_freeze_compatible(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze_compatible(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(
            sorted(
                (_deep_freeze_compatible(item) for item in value),
                key=repr,
            )
        )
    if isinstance(value, torch.Tensor):
        return value.detach().clone().contiguous()
    return value


def install_stack_round3_list_compat() -> str:
    marker = "_betelgeuze_stack_round3_list_compat_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from betelgeuze_engine_v2 import stack_round3_molecular
    from betelgeuze_engine_v2 import stack_round3_integrity_compat
    from betelgeuze_engine_v2.stack_round3_reader_compat import (
        install_stack_round3_reader_compat,
    )

    stack_round3_molecular._deep_freeze = _deep_freeze_compatible
    stack_round3_integrity_compat._deep_freeze = _deep_freeze_compatible
    reader_receipt = install_stack_round3_reader_compat()

    receipt = hashlib.sha256(
        json.dumps(
            {
                "schema_id": STACK_ROUND3_LIST_COMPAT_SCHEMA_ID,
                "ordered_metadata_remains_list_compatible": True,
                "structured_metadata_remains_dict_compatible": True,
                "all_public_container_mutators_rejected": True,
                "historical_append_failure_semantics_preserved": True,
                "canonical_text_reader_compat_sha256": reader_receipt,
                "scientifically_validated": False,
                "claim_safe": False,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "FrozenDict",
    "FrozenList",
    "STACK_ROUND3_LIST_COMPAT_SCHEMA_ID",
    "install_stack_round3_list_compat",
]

"""Third-round molecular-state and canonical-artifact hardening.

This compatibility layer closes the remaining in-memory and file-identity gaps
on the stacked Engine v2 head:

* molecular metadata is recursively immutable and caller tensors are cloned;
* every newly constructed :class:`AllAtomSystem` carries an integrity digest;
* public canonical SHA functions fail closed after in-place tensor mutation;
* canonical JSON rejects duplicate keys, non-canonical bytes, oversized inputs,
  excessive structure dimensions, and unsupported tensor dtypes;
* canonical writes use a private same-directory temporary file, fsync the file
  and directory, and refuse special-file destinations;
* ordered chemical graph, indexed topology, and source-bound topology identities
  are exposed separately.

These identities do not establish chemistry or scientific validation.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from types import MappingProxyType
from typing import Any

import torch


STACK_ROUND3_MOLECULAR_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round3_molecular/1.0.0"
)
CANONICAL_SYSTEM_MAX_BYTES = 64 * 1024 * 1024
CANONICAL_SYSTEM_MAX_ATOMS = 200_000
CANONICAL_SYSTEM_MAX_BONDS = 800_000
CANONICAL_SYSTEM_MAX_MODELS = 64
CANONICAL_SYSTEM_MAX_JSON_DEPTH = 64
CANONICAL_SYSTEM_MAX_JSON_NODES = 5_000_000
_CANONICAL_TENSOR_DTYPES = frozenset(
    {
        "bool",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint8",
        "float32",
        "float64",
    }
)


class MolecularIntegrityError(RuntimeError):
    """A supposedly immutable molecular object changed after construction."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_deep_freeze(item) for item in value), key=repr))
    if isinstance(value, torch.Tensor):
        return value.detach().clone().contiguous()
    return value


def _patch_molecular_models() -> None:
    from betelgeuze_engine_v2 import molecular as molecular_package
    from betelgeuze_engine_v2.molecular import models
    from betelgeuze_engine_v2.molecular import serialization

    if getattr(models, "_BETELGEUZE_ROUND3_MOLECULAR", False):
        return

    original_system_sha256 = serialization.canonical_system_sha256
    original_topology_sha256 = serialization.canonical_topology_sha256
    original_coordinates_sha256 = serialization.canonical_coordinates_sha256

    for cls in (
        models.Atom,
        models.Bond,
        models.Residue,
        models.Chain,
        models.StructureProvenance,
    ):
        original_post_init = cls.__post_init__

        def make_post_init(original):
            def post_init(self) -> None:
                original(self)
                object.__setattr__(
                    self,
                    "metadata",
                    _deep_freeze(dict(self.metadata)),
                )

            return post_init

        cls.__post_init__ = make_post_init(original_post_init)

    original_cell_post_init = models.UnitCell.__post_init__

    def cell_post_init(self) -> None:
        original_cell_post_init(self)
        object.__setattr__(
            self,
            "vectors",
            self.vectors.detach().clone().contiguous(),
        )

    models.UnitCell.__post_init__ = cell_post_init

    original_system_post_init = models.AllAtomSystem.__post_init__

    def system_post_init(self) -> None:
        original_system_post_init(self)
        object.__setattr__(
            self,
            "coordinates",
            self.coordinates.detach().clone().contiguous(),
        )
        object.__setattr__(
            self,
            "metadata",
            _deep_freeze(dict(self.metadata)),
        )
        object.__setattr__(
            self,
            "_integrity_sha256",
            original_system_sha256(self),
        )

    def assert_integrity(self) -> None:
        expected = getattr(self, "_integrity_sha256", "")
        if not expected:
            raise MolecularIntegrityError(
                "molecular system predates the integrity contract"
            )
        observed = original_system_sha256(self)
        if observed != expected:
            raise MolecularIntegrityError(
                "molecular system changed after construction"
            )

    def integrity_sha256(self) -> str:
        assert_integrity(self)
        return str(self._integrity_sha256)

    models.AllAtomSystem.__post_init__ = system_post_init
    models.AllAtomSystem.assert_integrity = assert_integrity
    models.AllAtomSystem.integrity_sha256 = property(integrity_sha256)

    def guarded_system_sha256(system) -> str:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
            return str(system._integrity_sha256)
        return original_system_sha256(system)

    def guarded_topology_sha256(system) -> str:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        return original_topology_sha256(system)

    def guarded_coordinates_sha256(system) -> str:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        return original_coordinates_sha256(system)

    serialization.canonical_system_sha256 = guarded_system_sha256
    serialization.canonical_topology_sha256 = guarded_topology_sha256
    serialization.canonical_coordinates_sha256 = guarded_coordinates_sha256
    molecular_package.canonical_system_sha256 = guarded_system_sha256
    molecular_package.canonical_topology_sha256 = guarded_topology_sha256
    molecular_package.canonical_coordinates_sha256 = guarded_coordinates_sha256
    molecular_package.MolecularIntegrityError = MolecularIntegrityError

    for loaded in tuple(sys.modules.values()):
        if loaded is None:
            continue
        if getattr(loaded, "canonical_system_sha256", None) is original_system_sha256:
            setattr(loaded, "canonical_system_sha256", guarded_system_sha256)
        if getattr(loaded, "canonical_topology_sha256", None) is original_topology_sha256:
            setattr(loaded, "canonical_topology_sha256", guarded_topology_sha256)
        if getattr(loaded, "canonical_coordinates_sha256", None) is original_coordinates_sha256:
            setattr(loaded, "canonical_coordinates_sha256", guarded_coordinates_sha256)

    models._BETELGEUZE_ROUND3_MOLECULAR = True


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate canonical JSON key {key!r}")
        result[key] = value
    return result


def _bounded_json_walk(value: object, *, depth: int = 0) -> int:
    if depth > CANONICAL_SYSTEM_MAX_JSON_DEPTH:
        raise ValueError("canonical JSON nesting exceeds the hard bound")
    count = 1
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("canonical JSON object keys must be text")
            count += _bounded_json_walk(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            count += _bounded_json_walk(item, depth=depth + 1)
    if count > CANONICAL_SYSTEM_MAX_JSON_NODES:
        raise ValueError("canonical JSON node count exceeds the hard bound")
    return count


def _validate_tensor_dtypes(value: object) -> None:
    if isinstance(value, dict):
        if set(value) == {"$tensor"}:
            payload = value["$tensor"]
            if not isinstance(payload, dict):
                raise ValueError("canonical tensor payload is invalid")
            dtype = str(payload.get("dtype", ""))
            if dtype not in _CANONICAL_TENSOR_DTYPES:
                raise ValueError("canonical tensor dtype is unsupported")
        for item in value.values():
            _validate_tensor_dtypes(item)
    elif isinstance(value, list):
        for item in value:
            _validate_tensor_dtypes(item)


def _patch_canonical_artifacts() -> None:
    from betelgeuze_engine_v2 import molecular as molecular_package
    from betelgeuze_engine_v2.molecular import serialization

    if getattr(serialization, "_BETELGEUZE_ROUND3_CANONICAL", False):
        return

    original_reader = serialization.all_atom_system_from_canonical_json
    original_writer = serialization.write_canonical_system_json

    def strict_reader(
        source: str | bytes,
        *,
        device: torch.device | str = "cpu",
    ):
        raw = source.encode("utf-8") if isinstance(source, str) else source
        if not isinstance(raw, bytes):
            raise TypeError("canonical system source must be str or bytes")
        if not raw or len(raw) > CANONICAL_SYSTEM_MAX_BYTES:
            raise serialization.CanonicalSerializationError(
                "canonical system document exceeds its byte bound"
            )
        canonical_raw = raw[:-1] if raw.endswith(b"\n") else raw
        if b"\r" in raw or raw.endswith(b"\n\n"):
            raise serialization.CanonicalSerializationError(
                "canonical system document has a non-canonical line ending"
            )
        try:
            text = canonical_raw.decode("ascii")
            parsed = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
            _bounded_json_walk(parsed)
            _validate_tensor_dtypes(parsed)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise serialization.CanonicalSerializationError(
                "canonical system document is invalid or ambiguous"
            ) from exc
        observed = json.dumps(
            parsed,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        if observed != canonical_raw:
            raise serialization.CanonicalSerializationError(
                "canonical system document bytes are not canonical"
            )
        system = original_reader(canonical_raw, device=device)
        if system.atom_count > CANONICAL_SYSTEM_MAX_ATOMS:
            raise serialization.CanonicalSerializationError(
                "canonical system atom count exceeds the hard bound"
            )
        if len(system.bonds) > CANONICAL_SYSTEM_MAX_BONDS:
            raise serialization.CanonicalSerializationError(
                "canonical system bond count exceeds the hard bound"
            )
        if system.model_count > CANONICAL_SYSTEM_MAX_MODELS:
            raise serialization.CanonicalSerializationError(
                "canonical system model count exceeds the hard bound"
            )
        return system

    def write_all(descriptor: int, payload: bytes) -> None:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("canonical artifact write made no progress")
            view = view[written:]

    def durable_writer(system, path: str | Path) -> Path:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            current = os.lstat(output)
        except FileNotFoundError:
            current = None
        if current is not None and (
            not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
        ):
            raise serialization.CanonicalSerializationError(
                "canonical output must be absent or a single-link regular file"
            )
        temporary = output.with_name(
            f".{output.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        try:
            descriptor = os.open(temporary, flags, 0o600)
            payload = serialization.canonical_system_json_bytes(system) + b"\n"
            write_all(descriptor, payload)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary, output)
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_flags |= getattr(os, "O_CLOEXEC", 0)
            directory = os.open(output.parent, directory_flags)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            raise serialization.CanonicalSerializationError(
                "canonical system document could not be written durably"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return output

    serialization.all_atom_system_from_canonical_json = strict_reader
    serialization.write_canonical_system_json = durable_writer
    molecular_package.all_atom_system_from_canonical_json = strict_reader
    molecular_package.write_canonical_system_json = durable_writer
    serialization._BETELGEUZE_ROUND3_CANONICAL = True


def _install_identity_layers() -> None:
    from betelgeuze_engine_v2 import molecular as molecular_package
    from betelgeuze_engine_v2.molecular import serialization

    def chemical_graph_payload(system) -> dict[str, object]:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        return {
            "schema_id": "betelgeuze.engine_v2_ordered_chemical_graph/1.0.0",
            "ordering_semantics": "indexed_atom_order",
            "atoms": [
                {
                    "index": int(atom.index),
                    "element": atom.element,
                    "atomic_number": int(atom.atomic_number),
                    "formal_charge": int(atom.formal_charge),
                    "isotope_mass_number": atom.isotope_mass_number,
                    "aromatic": bool(atom.aromatic),
                    "stereo": atom.stereo,
                }
                for atom in system.atoms
            ],
            "bonds": [
                {
                    "index": int(bond.index),
                    "atom_i": int(bond.atom_i),
                    "atom_j": int(bond.atom_j),
                    "order_hex": float(bond.order).hex(),
                    "aromatic": bool(bond.aromatic),
                    "stereo": bond.stereo,
                }
                for bond in system.bonds
            ],
        }

    def indexed_topology_payload(system) -> dict[str, object]:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        return {
            "schema_id": "betelgeuze.engine_v2_indexed_topology/1.0.0",
            "chemical_graph_sha256": serialization.sha256_canonical(
                chemical_graph_payload(system)
            ),
            "system_id": system.system_id,
            "coordinate_unit": system.coordinate_unit,
            "residues": system.residues,
            "chains": system.chains,
            "cell_periodic": None if system.cell is None else system.cell.periodic,
            "metadata": system.metadata,
        }

    def source_bound_topology_payload(system) -> dict[str, object]:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        return {
            "schema_id": "betelgeuze.engine_v2_source_bound_topology/1.0.0",
            "indexed_topology_sha256": serialization.sha256_canonical(
                indexed_topology_payload(system)
            ),
            "source": {
                "format": system.provenance.source_format,
                "id": system.provenance.source_id,
                "sha256": system.provenance.source_sha256,
                "parser_name": system.provenance.parser_name,
                "parser_version": system.provenance.parser_version,
            },
        }

    def chemical_graph_sha256(system) -> str:
        return serialization.sha256_canonical(chemical_graph_payload(system))

    def indexed_topology_sha256(system) -> str:
        return serialization.sha256_canonical(indexed_topology_payload(system))

    def source_bound_topology_sha256(system) -> str:
        return serialization.sha256_canonical(
            source_bound_topology_payload(system)
        )

    for target in (serialization, molecular_package):
        target.chemical_graph_payload = chemical_graph_payload
        target.indexed_topology_payload = indexed_topology_payload
        target.source_bound_topology_payload = source_bound_topology_payload
        target.chemical_graph_sha256 = chemical_graph_sha256
        target.indexed_topology_sha256 = indexed_topology_sha256
        target.source_bound_topology_sha256 = source_bound_topology_sha256


def install_stack_round3_molecular() -> str:
    marker = "_betelgeuze_stack_round3_molecular_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing
    _patch_molecular_models()
    _patch_canonical_artifacts()
    _install_identity_layers()
    receipt = _sha256(
        {
            "schema_id": STACK_ROUND3_MOLECULAR_SCHEMA_ID,
            "caller_tensors_cloned": True,
            "metadata_recursively_immutable": True,
            "system_integrity_guarded": True,
            "duplicate_json_keys_rejected": True,
            "canonical_raw_bytes_required": True,
            "canonical_resource_bounds": True,
            "durable_private_atomic_writer": True,
            "chemical_graph_identity_separated": True,
            "indexed_topology_identity_separated": True,
            "source_bound_topology_identity_separated": True,
            "chemistry_validated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "CANONICAL_SYSTEM_MAX_ATOMS",
    "CANONICAL_SYSTEM_MAX_BONDS",
    "CANONICAL_SYSTEM_MAX_BYTES",
    "CANONICAL_SYSTEM_MAX_JSON_DEPTH",
    "CANONICAL_SYSTEM_MAX_JSON_NODES",
    "CANONICAL_SYSTEM_MAX_MODELS",
    "MolecularIntegrityError",
    "STACK_ROUND3_MOLECULAR_SCHEMA_ID",
    "install_stack_round3_molecular",
]

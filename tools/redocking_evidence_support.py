"""Byte-level provenance and sealed uploads for development redocking.

This module neither installs dependencies nor imports molecular packages.  A
content identity covers the explicitly captured files, interpreter, wheels and
sources; it is not a claim that runner images or all runtime behavior coincide.
Raw installed-file inventories and the older RECORD-based fingerprint remain
available even when validated installer bookkeeping differs.
"""
from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping
import csv
from email.parser import BytesParser
import hashlib
from importlib import metadata, util
import io
import json
import marshal
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
import sysconfig
import tempfile
import types
import zipfile


WHEEL_SCHEMA = "betelgeuze.redocking_wheelhouse/1.0.0"
ENVIRONMENT_SCHEMA = "betelgeuze.redocking_environment/1.0.0"
COMPARISON_SCHEMA = "betelgeuze.redocking_environment_comparison/1.0.0"
ARTIFACT_SCHEMA = "betelgeuze.redocking_artifact_inventory/1.0.0"
POLICY = "validated-derived-bytecode-and-installer-bookkeeping/1.0.0"
INVENTORY_NAME = "artifact-inventory.json"
MAXIMUM_ARTIFACT_BYTES = 512 * 1024 * 1024
EXCLUDED_DIRECTORY = "private-external-binary"
_CHUNK = 1024 * 1024


class EvidenceError(ValueError):
    """Evidence does not support the requested identity or upload."""


class EnvironmentMismatch(EvidenceError):
    """The full per-file comparison is retained on ``comparison``."""

    def __init__(self, comparison):
        self.comparison = comparison
        super().__init__("environment content/source/version/wheel identity differs")


def _require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise EvidenceError(f"nonfinite JSON value: {value}")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)


def _name(value):
    _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value),
             "invalid distribution name")
    return re.sub(r"[-_.]+", "-", value).lower()


def _versions(values):
    _require(isinstance(values, Mapping) and values, "versions must be a nonempty mapping")
    result = {}
    for name, version in values.items():
        normalized = _name(name)
        _require(normalized not in result, "duplicate normalized distribution name")
        _require(isinstance(version, str) and version and not any(c.isspace() for c in version),
                 "invalid distribution version")
        result[normalized] = version
    return dict(sorted(result.items()))


def _relative(value):
    _require(isinstance(value, str) and value and "\\" not in value
             and not any(ord(c) < 32 or ord(c) == 127 for c in value), "unsafe relative path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value
             and not any(part in (".", "..") for part in path.parts), f"unsafe relative path: {value}")
    return path


def _root(path):
    path = Path(path).absolute()
    _require(path.is_dir() and not path.is_symlink(), f"not a regular directory: {path}")
    return path.resolve(strict=True)


def _no_symlink(path, root):
    """Check lexical containment before following any filesystem component."""
    path, root = Path(os.path.abspath(path)), Path(root)
    _require(path.is_relative_to(root), f"path escapes allowed root: {path}")
    cursor = root
    for part in path.relative_to(root).parts:
        cursor /= part
        _require(not cursor.is_symlink(), f"symlink is not an evidence file: {cursor}")
    return path


def _regular(path, *, root=None):
    path = Path(path)
    if root is not None:
        path = _no_symlink(path, root)
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode), f"not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                 f"file changed before read: {path}")
        for block in iter(lambda: stream.read(_CHUNK), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
    _require(signature(before) == signature(after) == signature(current), f"file changed during read: {path}")
    return {"size": before.st_size, "sha256": digest.hexdigest(), "mode": stat.S_IMODE(before.st_mode)}


def _signed(payload, key):
    return {**payload, key: _digest(payload)}


def _verify_signed(payload, key, schema):
    _require(isinstance(payload, dict) and payload.get("schema_id") == schema, "unsupported evidence schema")
    projection = {k: v for k, v in payload.items() if k != key}
    _require(payload.get(key) == _digest(projection), f"{key} mismatch")


def _atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _require(not path.is_symlink(), "cannot overwrite a symlink")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def freeze_wheelhouse(wheelhouse, *, expected_versions=None):
    """Freeze one wheel per distribution, including the transitive wheel set.

    ``expected_versions`` pins a required subset; the returned ``distributions``
    freezes the entire observed set.  Dependency completeness is a separate pip
    check.  Non-wheel payloads are rejected, except this helper's own manifests.
    """
    root = _root(wheelhouse)
    rows, versions = [], {}
    for path in sorted(root.iterdir()):
        _require(not path.is_symlink() and path.is_file(), "wheelhouse contains non-regular entries")
        if path.suffix != ".whl":
            _require(path.name in ("wheelhouse-manifest.json", "requirements-hashed.txt"),
                     f"unexpected wheelhouse file: {path.name}")
            continue
        _relative(path.name)
        row = _regular(path, root=root)
        with zipfile.ZipFile(path) as wheel:
            names = wheel.namelist()
            _require(len(names) == len(set(names)), "duplicate wheel member")
            for info in wheel.infolist():
                _relative(info.filename.rstrip("/"))
                _require(not stat.S_ISLNK(info.external_attr >> 16), "wheel symlink is unsupported")
            candidates = [name for name in names if re.fullmatch(r"[^/]+\.dist-info/METADATA", name)]
            _require(len(candidates) == 1, "wheel must contain exactly one METADATA")
            metadata_bytes = wheel.read(candidates[0])
            meta = BytesParser().parsebytes(metadata_bytes)
            _require(len(meta.get_all("Name", [])) == len(meta.get_all("Version", [])) == 1,
                     "ambiguous wheel Name/Version")
            name, version = _name(meta["Name"]), str(meta["Version"])
            parts = path.name[:-4].split("-")
            _require(len(parts) in (5, 6) and _name(parts[0]) == name and parts[1] == version,
                     "wheel filename and metadata differ")
            _require(name not in versions, f"multiple wheels for distribution: {name}")
            wheel_metadata = wheel.read(candidates[0].rsplit("/", 1)[0] + "/WHEEL")
            versions[name] = version
            rows.append({"filename": path.name, "name": name, "version": version,
                "size": row["size"], "sha256": row["sha256"],
                "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                "wheel_metadata_sha256": hashlib.sha256(wheel_metadata).hexdigest()})
    _require(rows, "wheelhouse has no wheels")
    required = _versions(expected_versions) if expected_versions is not None else {}
    _require(all(versions.get(name) == version for name, version in required.items()),
             "required wheel distribution/version differs")
    projection = {"files": rows, "distributions": dict(sorted(versions.items()))}
    return _signed({"schema_id": WHEEL_SCHEMA, **projection,
        "wheel_set_sha256": _digest(projection)}, "manifest_sha256")


def verify_wheelhouse(wheelhouse, manifest):
    _verify_signed(manifest, "manifest_sha256", WHEEL_SCHEMA)
    actual = freeze_wheelhouse(wheelhouse)
    _require(actual == manifest, "wheelhouse files, bytes, metadata or versions differ from the frozen set")
    requirements = Path(wheelhouse) / "requirements-hashed.txt"
    if requirements.exists():
        _require(requirements.read_text(encoding="utf-8") == hashed_requirements(manifest),
                 "hashed requirements differ from the frozen wheel set")
    return actual


def hashed_requirements(manifest):
    _verify_signed(manifest, "manifest_sha256", WHEEL_SCHEMA)
    return "".join(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}\n"
                   for row in sorted(manifest["files"], key=lambda r: r["name"]))


def _code_value(value):
    """Compare code structure without marshal's object-interning artifacts."""
    if isinstance(value, types.CodeType):
        fields = ("co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals",
                  "co_stacksize", "co_flags", "co_code", "co_consts", "co_names", "co_varnames",
                  "co_filename", "co_name", "co_qualname", "co_firstlineno",
                  "co_linetable", "co_exceptiontable", "co_freevars", "co_cellvars")
        if not hasattr(value, "co_linetable"):
            fields += ("co_lnotab",)
        return {key: _code_value(getattr(value, key)) for key in fields if hasattr(value, key)}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, (tuple, list)):
        return [_code_value(x) for x in value]
    if isinstance(value, frozenset):
        return {"frozenset": sorted((_code_value(x) for x in value), key=_canonical)}
    if isinstance(value, complex):
        return {"complex": [value.real.hex(), value.imag.hex()]}
    if isinstance(value, float):
        return {"float": value.hex()}
    if value is Ellipsis:
        return {"ellipsis": True}
    _require(value is None or type(value) in (bool, int, str), "unsupported bytecode constant")
    return value


def _validate_cache(path, install_root):
    """A pyc is excluded only after proving it compiles from the present source.

    No bytecode or package is executed.  Its complete original hash, header and
    source binding are retained.  An altered or sourceless cache fails closed.
    """
    try:
        source = Path(util.source_from_cache(str(path)))
    except ValueError:
        source = path.with_suffix(".py")
    source = _no_symlink(source, install_root)
    source_row = _regular(source, root=install_root)
    optimization = re.search(r"\.opt-([012])\.pyc$", path.name)
    level = int(optimization[1]) if optimization else 0
    validation = {"source_path": source.relative_to(install_root).as_posix(),
        "source_sha256": source_row["sha256"], "optimization_level": level,
        "interpreter_cache_tag": sys.implementation.cache_tag}
    if not path.exists():
        return {**validation, "validation": "missing_cache_with_present_source"}
    body = path.read_bytes()
    _require(len(body) >= 16 and body[:4] == util.MAGIC_NUMBER, "bytecode magic/header mismatch")
    flags = int.from_bytes(body[4:8], "little")
    _require(flags in (0, 1, 3), "unsupported bytecode flags")
    try:
        with io.BytesIO(body[16:]) as stream:
            code = marshal.load(stream)
            _require(not stream.read(), "trailing bytecode payload")
        _require(isinstance(code, types.CodeType), "bytecode payload is not a code object")
        source_bytes = source.read_bytes()
        _require(hashlib.sha256(source_bytes).hexdigest() == source_row["sha256"], "source changed during cache validation")
        if flags & 1:
            _require(body[8:16] == util.source_hash(source_bytes), "bytecode source hash differs")
        compiled = compile(source_bytes, code.co_filename, "exec", dont_inherit=True, optimize=level)
        _require(_code_value(code) == _code_value(compiled), "bytecode differs from the present source")
    except (EOFError, SyntaxError, TypeError) as exc:
        raise EvidenceError("cannot validate generated bytecode") from exc
    return {**validation, "validation": "code_matches_compilation_of_present_source",
            "header_hex": body[:16].hex(), "recorded_compile_filename": code.co_filename}


def _runtime():
    executable = Path(sys.executable).resolve(strict=True)
    libraries, detected = [], set()
    libdir, libname = sysconfig.get_config_var("LIBDIR"), sysconfig.get_config_var("LDLIBRARY")
    configured = Path(libdir) / libname if libdir and libname else None
    if Path("/proc/self/maps").is_file():
        for line in Path("/proc/self/maps").read_text().splitlines():
            columns = line.split(maxsplit=5)
            if len(columns) == 6 and re.match(r"libpython[^/]*\.(?:so|dylib)", Path(columns[5]).name):
                _require(not columns[5].endswith(" (deleted)"), "loaded libpython has been deleted")
                detected.add(Path(columns[5]).resolve(strict=True))
        detection = "proc_self_maps"
    else:
        detection = "configured_library_fallback"
        if sysconfig.get_config_var("Py_ENABLE_SHARED"):
            _require(configured is not None and configured.is_file(), "shared libpython cannot be identified")
            detected.add(configured.resolve(strict=True))
    for library in sorted(detected):
        libraries.append({"path": str(library), **_regular(library)})
    return {"implementation": sys.implementation.name, "version": sys.version,
        "cache_tag": sys.implementation.cache_tag, "platform": sys.platform,
        "machine": platform.machine(), "byteorder": sys.byteorder,
        "executable": {"path": str(executable), **_regular(executable)}, "libpython": libraries,
        "libpython_detection": detection,
        "configured_libpython": {"path": str(configured) if configured else None,
                                  "exists": configured.is_file() if configured else False},
        "library_scope": "Observed libpython mappings, or an explicit configured fallback; an empty mapping list is not proof of a static build. Other host libraries are outside this identity."}


def _runtime_projection(runtime):
    return {**{k: runtime[k] for k in ("implementation", "version", "cache_tag", "platform", "machine", "byteorder")},
        "executable": {k: runtime["executable"][k] for k in ("size", "sha256", "mode")},
        "libpython": [{k: row[k] for k in ("size", "sha256", "mode")} for row in runtime["libpython"]],
        "libpython_detection": runtime.get("libpython_detection")}


def _file_projection(row):
    return {key: row[key] for key in ("path", "status", "size", "sha256", "mode", "recorded", "content_included", "exclusion_reason")}


def _classify_installed(path, key, row, *, metadata_root, install_root, wheel):
    if path.suffix == ".pyc":
        return False, "validated_derived_bytecode", _validate_cache(path, install_root)
    if path.parent == metadata_root:
        if path.name == "RECORD":
            return False, "installer_file_record", {"validation": "all listed present files independently hashed"}
        if path.name == "REQUESTED":
            _require(row["size"] == 0, "REQUESTED is not empty installer bookkeeping")
            return False, "installer_requested_marker", {"validation": "empty marker"}
        if path.name == "INSTALLER":
            _require(path.read_bytes().strip() == b"pip", "unrecognized installer bookkeeping")
            return False, "installer_name", {"validation": "pip installer marker"}
        if path.name == "direct_url.json":
            url = _json(path.read_bytes())
            info = url.get("archive_info", {})
            hashes = info.get("hashes", {})
            claimed = hashes.get("sha256") or str(info.get("hash", "")).removeprefix("sha256=")
            _require(claimed == wheel["sha256"] and "dir_info" not in url and "vcs_info" not in url,
                     "direct_url is not bound to the frozen wheel")
            return False, "installer_wheel_origin", {"validation": "archive SHA256 equals frozen wheel", "wheel_sha256": claimed,
                                                    "recorded_url": url.get("url")}
    _require(row["status"] == "regular", f"active installed file missing: {key}")
    return True, None, None


def _installed_distribution(name, version, wheel, install_root):
    distribution = metadata.distribution(name)
    _require(_name(distribution.metadata["Name"]) == name and distribution.version == version,
             f"installed distribution version differs: {name}")
    api_files = tuple(distribution.files or ())
    _require(api_files, f"installed distribution has no file record: {name}")
    rows, legacy, seen, scan_roots, source_paths = [], [], set(), set(), set()
    record_keys = [str(p) for p in api_files if re.fullmatch(r"[^/]+\.dist-info/RECORD", str(p))]
    _require(len(record_keys) == 1, f"distribution lacks one RECORD: {name}")
    metadata_root = _no_symlink(Path(distribution.locate_file(record_keys[0])).parent, install_root)
    _require(_regular(metadata_root / "METADATA", root=install_root)["sha256"] == wheel["metadata_sha256"]
             and _regular(metadata_root / "WHEEL", root=install_root)["sha256"] == wheel["wheel_metadata_sha256"],
             f"installed metadata is not bound to the frozen wheel: {name}")
    # Some importlib.metadata versions filter missing paths from .files.  Parse
    # raw RECORD as well so missing binaries and path escapes cannot disappear.
    record_body = (metadata_root / "RECORD").read_bytes()
    recorded = list(csv.reader(io.StringIO(record_body.decode("utf-8"))))
    _require(recorded and all(len(row) == 3 for row in recorded), "malformed installed RECORD")
    api_keys = {str(entry) for entry in api_files}
    for key, record_hash, record_size in sorted(recorded):
        _require(key not in seen and not PurePosixPath(key).is_absolute() and "\\" not in key,
                 "duplicate/unsafe installed-file record")
        _require(key and PurePosixPath(key).as_posix() == key and not any(ord(c) < 32 for c in key),
                 "noncanonical installed-file record")
        seen.add(key)
        path = _no_symlink(distribution.locate_file(key), install_root)
        if path.exists():
            actual = _regular(path, root=install_root)
            row = {"path": key, "location": str(path), "status": "regular", "recorded": True, **actual}
            if key in api_keys:
                legacy.append([key, "regular", actual["size"], actual["sha256"]])
            if record_size:
                _require(int(record_size) == actual["size"], f"RECORD size differs: {name}/{key}")
            if record_hash:
                algorithm, separator, expected_hash = record_hash.partition("=")
                _require(separator and algorithm == "sha256", "unsupported installed RECORD hash algorithm")
                encoded = base64.urlsafe_b64encode(bytes.fromhex(actual["sha256"])).rstrip(b"=").decode("ascii")
                _require(expected_hash == encoded, f"RECORD hash differs: {name}/{key}")
        else:
            _require(path.suffix == ".pyc", f"installed file missing: {name}/{key}")
            row = {"path": key, "location": str(path), "status": "missing", "recorded": True,
                   "size": None, "sha256": None, "mode": None}
            if key in api_keys:
                legacy.append([key, "missing"])
        included, reason, validation = _classify_installed(path, key, row,
            metadata_root=metadata_root, install_root=install_root, wheel=wheel)
        row.update(content_included=included, exclusion_reason=reason, exclusion_validation=validation)
        rows.append(row)
        if path.suffix == ".py" and row["status"] == "regular":
            source_paths.add(path)
        first = PurePosixPath(key).parts[0]
        if first not in ("..", "."):
            directory = _no_symlink(distribution.locate_file(first), install_root)
            if directory.is_dir():
                scan_roots.add(directory)
    # Include generated caches that RECORD did not enumerate.  Unrecorded source,
    # native code or metadata is an error, never a silently omitted active file.
    known_locations = {row["location"] for row in rows}
    discovered = set()
    for directory in sorted(scan_roots):
        for candidate in sorted(directory.rglob("*")):
            _no_symlink(candidate, install_root)
            if candidate.is_dir():
                continue
            _require(candidate.is_file(), f"non-regular installed payload: {candidate}")
            discovered.add(candidate)
    # Standalone modules (for example six.py) share site-packages/__pycache__;
    # capture only caches bound to a source this distribution actually owns.
    for source in source_paths:
        directory = source.parent / "__pycache__"
        _no_symlink(directory, install_root)
        if directory.is_dir():
            discovered.update(p for p in directory.iterdir()
                              if p.name.startswith(source.stem + ".") and p.suffix == ".pyc")
        legacy_cache = source.with_suffix(".pyc")
        if legacy_cache.exists() or legacy_cache.is_symlink():
            discovered.add(legacy_cache)
    for candidate in sorted(discovered):
        _no_symlink(candidate, install_root)
        if str(candidate) in known_locations:
            continue
        _require(candidate.suffix == ".pyc", f"unrecorded active installed file: {candidate}")
        key = os.path.relpath(candidate, distribution.locate_file("")).replace(os.sep, "/")
        row = {"path": key, "location": str(candidate), "status": "regular", "recorded": False,
               **_regular(candidate, root=install_root), "content_included": False,
               "exclusion_reason": "validated_derived_bytecode",
               "exclusion_validation": _validate_cache(candidate, install_root)}
        rows.append(row)
        known_locations.add(str(candidate))
    rows.sort(key=lambda row: row["path"])
    _require(api_keys <= seen, "metadata API file set is outside raw RECORD")
    return {"name": name, "version": version, "files": rows,
        "record_file_sha256": hashlib.sha256(record_body).hexdigest(),
        "legacy_payload_sha256": _digest(legacy),
        "raw_payload_sha256": _digest([_file_projection(row) for row in rows]),
        "active_payload_sha256": _digest([{k: row[k] for k in ("path", "size", "sha256", "mode")}
                                          for row in rows if row["content_included"]])}


def _environment_projection(report):
    return {"policy": report["policy"], "support_module_sha256": report["support_module_sha256"],
        "versions": report["versions"], "wheel_set_sha256": report["wheel_set_sha256"],
        "runtime": _runtime_projection(report["runtime"]),
        "source_files": [{k: row[k] for k in ("path", "size", "sha256", "mode")} for row in report["source_files"]],
        "active_payloads": {name: data["active_payload_sha256"] for name, data in report["distributions"].items()}}


def snapshot_environment(expected_versions, *, source_files, wheelhouse_manifest, install_root=None):
    """Capture actual installed bytes without importing the selected packages.

    ``source_files`` maps stable relative logical names to regular files.  The
    selected versions may be a subset of a wheel set containing loader-only
    wheels; that omission is explicit in the report.  No cache is trusted merely
    because its suffix is ``.pyc``.
    """
    _verify_signed(wheelhouse_manifest, "manifest_sha256", WHEEL_SCHEMA)
    selected = _versions(expected_versions)
    wheels = {row["name"]: row for row in wheelhouse_manifest["files"]}
    _require(all(name in wheels and wheels[name]["version"] == version for name, version in selected.items()),
             "captured versions are not a subset of the frozen wheel set")
    root = _root(sys.prefix if install_root is None else install_root)
    _require(isinstance(source_files, Mapping) and source_files, "source file mapping is required")
    sources = []
    for name, path in sorted(source_files.items()):
        _relative(name)
        path = Path(path).absolute()
        _require(not path.is_symlink(), "source symlink is unsupported")
        sources.append({"path": name, "location": str(path), **_regular(path)})
    distributions = {name: _installed_distribution(name, version, wheels[name], root)
                     for name, version in selected.items()}
    report = {"schema_id": ENVIRONMENT_SCHEMA, "policy": POLICY,
        "support_module_sha256": _regular(Path(__file__))["sha256"],
        "install_root": str(root), "versions": selected, "source_files": sources,
        "wheel_manifest_sha256": wheelhouse_manifest["manifest_sha256"],
        "wheel_set_sha256": wheelhouse_manifest["wheel_set_sha256"],
        "wheel_distributions_not_captured": sorted(set(wheels) - set(selected)),
        "runtime": _runtime(), "distributions": distributions,
        "legacy_payload_sha256s": {name: row["legacy_payload_sha256"] for name, row in distributions.items()},
        "raw_payload_sha256": _digest({name: row["raw_payload_sha256"] for name, row in distributions.items()}),
        "scope": "Selected installed payload, explicit sources, interpreter and frozen wheel set; not complete host-image identity."}
    report["content_identity_sha256"] = _digest(_environment_projection(report))
    return _signed(report, "report_sha256")


def _validate_environment(report):
    _verify_signed(report, "report_sha256", ENVIRONMENT_SCHEMA)
    _require(report["policy"] == POLICY, "unsupported environment comparison policy")
    _require(report["content_identity_sha256"] == _digest(_environment_projection(report)),
             "content identity projection differs")
    for name, distribution in report["distributions"].items():
        rows = distribution["files"]
        _require(len({row["path"] for row in rows}) == len(rows), "duplicate installed snapshot path")
        _require(distribution["raw_payload_sha256"] == _digest([_file_projection(row) for row in rows]),
                 f"raw installed inventory digest differs: {name}")
        active = [{k: row[k] for k in ("path", "size", "sha256", "mode")}
                  for row in rows if row["content_included"]]
        _require(distribution["active_payload_sha256"] == _digest(active), f"active inventory digest differs: {name}")


def compare_environments(reference, observed):
    """Return every raw file difference, even when active identity is equal."""
    _validate_environment(reference)
    _validate_environment(observed)
    differences, forbidden = [], []
    allowed_reasons = {"validated_derived_bytecode", "installer_file_record", "installer_requested_marker",
                       "installer_name", "installer_wheel_origin"}
    for name in sorted(set(reference["distributions"]) | set(observed["distributions"])):
        left = {r["path"]: r for r in reference["distributions"].get(name, {}).get("files", [])}
        right = {r["path"]: r for r in observed["distributions"].get(name, {}).get("files", [])}
        for path in sorted(set(left) | set(right)):
            before, after = left.get(path), right.get(path)
            if (None if before is None else _file_projection(before)) == (None if after is None else _file_projection(after)):
                continue
            present = [r for r in (before, after) if r is not None]
            installation_only = all(r["content_included"] is False and r["exclusion_reason"] in allowed_reasons
                                    and r["exclusion_validation"] for r in present)
            row = {"distribution": name, "path": path, "reference": before, "observed": after,
                   "allowed_installation_only_difference": bool(installation_only)}
            differences.append(row)
            if not installation_only:
                forbidden.append({"distribution": name, "path": path})
    left, right = _environment_projection(reference), _environment_projection(observed)
    contexts = [key for key in sorted(set(left) | set(right)) if key != "active_payloads" and left.get(key) != right.get(key)]
    same_content = reference["content_identity_sha256"] == observed["content_identity_sha256"]
    return {"schema_id": COMPARISON_SCHEMA,
        "matches": same_content and not forbidden and not contexts,
        "content_identity_equal": same_content,
        "raw_installed_payload_equal": reference["raw_payload_sha256"] == observed["raw_payload_sha256"],
        "reference_report_sha256": reference["report_sha256"], "observed_report_sha256": observed["report_sha256"],
        "reference_content_identity_sha256": reference["content_identity_sha256"],
        "observed_content_identity_sha256": observed["content_identity_sha256"],
        "identity_context_differences": {key: {"reference": left.get(key), "observed": right.get(key)} for key in contexts},
        "raw_file_differences": differences, "forbidden_file_differences": forbidden,
        "interpretation": "Validated derived caches/installer bookkeeping may differ; full raw fingerprints and each difference remain visible. No full host-image equivalence is inferred."}


def require_matching_environment(reference, observed):
    comparison = compare_environments(reference, observed)
    if not comparison["matches"]:
        raise EnvironmentMismatch(comparison)
    return comparison


def _artifact_paths(root):
    paths, excluded = [], []

    def visit(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            _relative(relative)
            _no_symlink(path, root)
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                if path.name == EXCLUDED_DIRECTORY:
                    excluded.append({"path": relative, "reason": "private_external_binary_not_uploaded"})
                else:
                    visit(path)
            else:
                _require(stat.S_ISREG(mode), f"artifact contains a non-regular file: {relative}")
                if relative != INVENTORY_NAME:
                    paths.append(path)

    visit(root)
    return paths, excluded


def _zip_info(name):
    info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def seal_artifact_archive(evidence_root, archive_path, *, maximum_bytes=MAXIMUM_ARTIFACT_BYTES):
    """Freeze the actual upload into one ZIP, including hidden pinned inputs.

    The caller must stop all producers and finish status/journal/summary writes
    first.  The old root inventory is not trusted or uploaded: a new inventory is
    generated from the bytes put in this ZIP, then the archive is verified before
    atomic publication.  Original evidence files are never edited.
    """
    root, destination = _root(evidence_root), Path(archive_path).absolute()
    _require(not destination.is_symlink(), "sealed archive destination is a symlink")
    destination = destination.resolve(strict=False)
    _require(not destination.is_relative_to(root),
             "sealed archive must be outside its evidence tree")
    _require(type(maximum_bytes) is int and maximum_bytes > 0, "invalid artifact byte limit")
    paths, excluded = _artifact_paths(root)
    _require(paths, "cannot seal an empty artifact")
    before = {path.relative_to(root).as_posix(): _regular(path, root=root) for path in paths}
    total = sum(row["size"] for row in before.values())
    _require(total <= maximum_bytes, "artifact payload exceeds byte limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=destination.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            rows = []
            for path in paths:
                name = path.relative_to(root).as_posix()
                expected, digest, size = before[name], hashlib.sha256(), 0
                _no_symlink(path, root)
                with path.open("rb") as source, archive.open(_zip_info(name), "w") as target:
                    _require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "artifact file changed type")
                    for block in iter(lambda: source.read(_CHUNK), b""):
                        size += len(block)
                        _require(size <= expected["size"], "artifact grew while freezing")
                        digest.update(block)
                        target.write(block)
                _require(size == expected["size"] and digest.hexdigest() == expected["sha256"],
                         f"artifact changed while freezing: {name}")
                rows.append({"path": name, "size": size, "sha256": digest.hexdigest()})
            after_paths, after_excluded = _artifact_paths(root)
            _require(paths == after_paths and excluded == after_excluded, "artifact file set changed while freezing")
            _require(all(_regular(path, root=root) == before[path.relative_to(root).as_posix()] for path in paths),
                     "artifact changed before seal completion")
            inventory = {"schema_id": ARTIFACT_SCHEMA, "bytes": total, "files": rows,
                "excluded_paths": excluded, "hidden_files_included": True,
                "freeze_order": "producers stopped; payload bytes sealed; fresh inventory written last; archive verified; upload only this archive",
                "payload_file_count": len(rows), "archive_member_count": len(rows) + 1}
            body = json.dumps(inventory, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
            archive.writestr(_zip_info(INVENTORY_NAME), body)
        verified = verify_artifact_archive(temporary, maximum_bytes=maximum_bytes)
        os.replace(temporary, destination)
        return {**verified, "archive_path": str(destination), "excluded_paths": excluded}
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def verify_artifact_archive(archive_path, *, expected_sha256=None, maximum_bytes=MAXIMUM_ARTIFACT_BYTES):
    """Check actual ZIP members against the included inventory, without extraction."""
    path = Path(archive_path)
    actual = _regular(path)
    if expected_sha256 is not None:
        _require(actual["sha256"] == expected_sha256, "sealed archive SHA256 mismatch")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        _require(len(names) == len(set(names)) and INVENTORY_NAME in names, "duplicate/missing inventory member")
        for info in infos:
            _relative(info.filename)
            _require(not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG),
                     "non-regular ZIP member")
            _require(EXCLUDED_DIRECTORY not in PurePosixPath(info.filename).parts, "private binary in sealed upload")
        inventory_info = archive.getinfo(INVENTORY_NAME)
        _require(inventory_info.file_size <= 16 * 1024 * 1024, "inventory is too large")
        body = archive.read(INVENTORY_NAME)
        inventory = _json(body)
        _require(inventory.get("schema_id") == ARTIFACT_SCHEMA and inventory.get("hidden_files_included") is True,
                 "unsupported sealed inventory")
        listed = inventory["files"]
        by_name = {}
        for row in listed:
            _relative(row["path"])
            _require(row["path"] not in by_name and row["path"] != INVENTORY_NAME, "duplicate inventory payload path")
            _require(type(row["size"]) is int and row["size"] >= 0, "invalid inventory size")
            _require(isinstance(row["sha256"], str) and re.fullmatch("[0-9a-f]{64}", row["sha256"]), "invalid inventory digest")
            by_name[row["path"]] = row
        _require(set(names) == set(by_name) | {INVENTORY_NAME}, "upload member set differs from inventory")
        total = sum(row["size"] for row in listed)
        _require(total == inventory["bytes"] and total <= maximum_bytes, "artifact byte count/limit differs")
        _require(inventory["payload_file_count"] == len(listed) and inventory["archive_member_count"] == len(infos),
                 "artifact file counts differ")
        for name, row in by_name.items():
            _require(archive.getinfo(name).file_size == row["size"], f"ZIP size differs: {name}")
            digest, size = hashlib.sha256(), 0
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(_CHUNK), b""):
                    digest.update(block)
                    size += len(block)
            _require(size == row["size"] and digest.hexdigest() == row["sha256"], f"ZIP bytes differ: {name}")
    _require(_regular(path) == actual, "sealed archive changed during verification")
    return {"status": "verified", "archive_sha256": actual["sha256"], "archive_size": actual["size"],
        "inventory_sha256": hashlib.sha256(body).hexdigest(), "payload_files": len(listed),
        "payload_bytes": total, "archive_members": len(infos), "hidden_files_included": True,
        "inventory_matches_actual_upload": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    freeze = commands.add_parser("freeze", help="freeze all wheel bytes and write hashed requirements")
    freeze.add_argument("--wheelhouse", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--versions", type=Path)
    freeze.add_argument("--requirements", type=Path)
    verify = commands.add_parser("verify", help="verify the exact frozen wheel set")
    verify.add_argument("--wheelhouse", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    environment = commands.add_parser("environment", help="capture actual installed payload and compare with a reference")
    environment.add_argument("--manifest", type=Path, required=True)
    environment.add_argument("--source-root", type=Path, required=True)
    environment.add_argument("--source-file", action="append", required=True)
    environment.add_argument("--versions", type=Path)
    environment.add_argument("--install-root", type=Path)
    environment.add_argument("--output", type=Path, required=True)
    environment.add_argument("--reference", type=Path)
    environment.add_argument("--comparison-output", type=Path)
    compare = commands.add_parser("compare", help="write every file difference and enforce active identity")
    compare.add_argument("--reference", type=Path, required=True)
    compare.add_argument("--observed", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    seal = commands.add_parser("seal", help="seal the exact upload payload, including hidden files")
    seal.add_argument("--root", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    seal.add_argument("--maximum-bytes", type=int, default=MAXIMUM_ARTIFACT_BYTES)
    artifact = commands.add_parser("verify-artifact", help="verify a sealed archive without extraction")
    artifact.add_argument("--archive", type=Path, required=True)
    artifact.add_argument("--sha256")
    artifact.add_argument("--maximum-bytes", type=int, default=MAXIMUM_ARTIFACT_BYTES)
    args = parser.parse_args(argv)
    try:
        if args.action == "freeze":
            result = freeze_wheelhouse(args.wheelhouse,
                expected_versions=_json(args.versions.read_bytes()) if args.versions else None)
            _atomic_json(args.output, result)
            if args.requirements:
                _require(not args.requirements.is_symlink(), "requirements destination is a symlink")
                args.requirements.parent.mkdir(parents=True, exist_ok=True)
                args.requirements.write_text(hashed_requirements(result), encoding="utf-8")
            summary = {"wheel_set_sha256": result["wheel_set_sha256"], "manifest_sha256": result["manifest_sha256"],
                       "distributions": result["distributions"], "wheel_count": len(result["files"])}
        elif args.action == "verify":
            result = verify_wheelhouse(args.wheelhouse, _json(args.manifest.read_bytes()))
            summary = {"status": "verified", "wheel_set_sha256": result["wheel_set_sha256"], "wheel_count": len(result["files"])}
        elif args.action == "environment":
            manifest = _json(args.manifest.read_bytes())
            versions = _json(args.versions.read_bytes()) if args.versions else manifest["distributions"]
            source_root = _root(args.source_root)
            sources = {}
            for relative in args.source_file:
                _relative(relative)
                _require(relative not in sources, "duplicate source-file argument")
                sources[relative] = _no_symlink(source_root / relative, source_root)
            result = snapshot_environment(versions, source_files=sources,
                wheelhouse_manifest=manifest, install_root=args.install_root)
            _atomic_json(args.output, result)
            summary = {"content_identity_sha256": result["content_identity_sha256"],
                       "raw_payload_sha256": result["raw_payload_sha256"], "report_sha256": result["report_sha256"]}
            if args.reference:
                _require(args.comparison_output is not None, "a reference requires --comparison-output")
                comparison = compare_environments(_json(args.reference.read_bytes()), result)
                _atomic_json(args.comparison_output, comparison)
                summary["matches_reference"] = comparison["matches"]
                if not comparison["matches"]:
                    print(json.dumps(summary, sort_keys=True))
                    return 1
        elif args.action == "compare":
            comparison = compare_environments(_json(args.reference.read_bytes()), _json(args.observed.read_bytes()))
            _atomic_json(args.output, comparison)
            summary = {"matches": comparison["matches"], "raw_installed_payload_equal": comparison["raw_installed_payload_equal"],
                       "raw_file_difference_count": len(comparison["raw_file_differences"])}
            if not comparison["matches"]:
                print(json.dumps(summary, sort_keys=True))
                return 1
        elif args.action == "seal":
            summary = seal_artifact_archive(args.root, args.output, maximum_bytes=args.maximum_bytes)
        else:
            summary = verify_artifact_archive(args.archive, expected_sha256=args.sha256, maximum_bytes=args.maximum_bytes)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (EvidenceError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, metadata.PackageNotFoundError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

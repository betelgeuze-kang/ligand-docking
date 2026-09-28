"""Check a pinned, source-only PFKFB3 LFS inventory.

The default check is offline: it validates the recorded metadata and an
independently pinned digest without opening prepared files or assay outcomes.
``--live`` additionally asks the official GitHub tree and media endpoints to
revalidate all listed pointer and LFS objects. Neither mode admits labels,
prepared chemical states, or scientific comparisons.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "openff_lfs_inventory.v1.json"
MAX_BYTES = 131_072
REPOSITORY = "openforcefield/protein-ligand-benchmark"
COMMIT = "fe6f96916b2e28f9c14398d77c838d6515e931b0"
ROOT_TREE = "077690dd0efb405133b0f1b133ad27071af7fad1"
LIGANDS_TREE = "c43590caa90f74d4c9894a447532f6c8e02702bf"
BASE = "data/2020-07-06_pfkfb3/02_ligands"
IDS = (
    "lig_19",
    "lig_20",
    "lig_23",
    "lig_24",
    "lig_26",
    "lig_29",
    "lig_30",
    "lig_31",
    "lig_33",
    "lig_34",
    "lig_35",
    "lig_36",
    "lig_37",
    "lig_38",
    "lig_39",
    "lig_41",
    "lig_42",
    "lig_43",
    "lig_44",
    "lig_46",
    "lig_47",
    "lig_48",
    "lig_49",
    "lig_52",
    "lig_53",
    "lig_54",
    "lig_55",
    "lig_56",
    "lig_57",
    "lig_58",
    "lig_59",
    "lig_60",
    "lig_62",
    "lig_63",
    "lig_64",
    "lig_65",
    "lig_67",
    "lig_68",
    "lig_69",
    "lig_70",
)
KINDS = ("sdf", "gro", "ligand_itp", "atomtypes_itp")
FILE_ROWS_SHA256 = "12d9feb949a8733cc81801448985ec611886a157fb95a7332bd6ec39f83c8afd"
PATH_OID_SIZE_SHA256 = (
    "08c1b8ff17dafe1d1f36ba47eef73808fcfea84edb5860668ce2fc4e15a902a4"
)
SUPPORT_ROWS_SHA256 = "98563c95a90a60ee82b39294cf8c09a290667a8294c4e40c7ac4624c8fbb1823"
SUPPORT_PATH_OID_SIZE_SHA256 = (
    "3c93701e1773c8d450074401ebebc2abb6395ace9cec2f0f3e3ea61b42ccb809"
)
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
FILE_FIELDS = {
    "ligand_id",
    "kind",
    "path",
    "git_pointer_blob_sha1",
    "lfs_oid_sha256",
    "lfs_size_bytes",
    "observed_download_sha256",
    "observed_download_size_bytes",
}


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _load(path: Path) -> tuple[dict, str]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > MAX_BYTES
        ):
            raise ValueError("invalid_inventory_file")
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())

    def identity(s):
        return (s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns, s.st_size)

    if len(raw) != before.st_size or identity(before) != identity(after):
        raise ValueError("inventory_changed_during_read")
    doc = json.loads(
        raw,
        object_pairs_hook=_unique_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
    )
    return doc, hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _path(ident: str, kind: str) -> str:
    directory = f"{BASE}/{ident}"
    if kind == "sdf":
        return f"{directory}/crd/{ident}.sdf"
    top = f"{directory}/top/openff-1.0.0.offxml"
    if kind == "gro":
        return f"{top}/{ident}.gro"
    if kind == "ligand_itp":
        return f"{top}/{ident}.itp"
    if kind == "atomtypes_itp":
        return f"{top}/ff{ident}.itp"
    raise ValueError("unknown_file_kind")


def _support_path(ident: str | None, kind: str) -> str:
    study = "data/2020-07-06_pfkfb3"
    if kind == "ligand_top" and ident in IDS:
        return f"{study}/02_ligands/{ident}/top/openff-1.0.0.offxml/{ident}.top"
    if kind == "protein_pdb" and ident is None:
        return f"{study}/01_protein/crd/protein.pdb"
    if kind == "protein_topol_itp" and ident is None:
        return f"{study}/01_protein/top/amber99sb-star-ildn-mut.ff/topol.itp"
    raise ValueError("unknown_support_file_kind")


def _pointer(oid: str, size: int) -> bytes:
    return (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {size}\n"
    ).encode()


def _git_blob_sha1(contents: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(contents)).encode() + b"\0" + contents
    ).hexdigest()


def verify(path: Path = INVENTORY) -> dict:
    doc, digest = _load(path)
    if not isinstance(doc, dict) or set(doc) != {
        "schema_version",
        "status",
        "source",
        "audit",
        "files",
        "support_files",
    }:
        raise ValueError("invalid_inventory_schema")
    if (
        doc["schema_version"] != "pfkfb3_openff_lfs_inventory_v1"
        or doc["status"] != "PINNED_PREPARED_FILE_BYTES_VERIFIED_SOURCE_ROLE_BLOCKED"
    ):
        raise ValueError("invalid_inventory_status")
    source = {
        "repository": REPOSITORY,
        "commit": COMMIT,
        "directory": "data/2020-07-06_pfkfb3",
        "ligands_directory": BASE,
        "git_tree_url": f"https://api.github.com/repos/{REPOSITORY}/git/trees/{COMMIT}?recursive=1",
        "lfs_pointer_url_prefix": f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/",
        "lfs_media_url_prefix": f"https://media.githubusercontent.com/media/{REPOSITORY}/{COMMIT}/",
        "data_license_url": f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/LICENSE_DATA",
        "git_root_tree_sha1": ROOT_TREE,
        "ligands_tree_sha1": LIGANDS_TREE,
    }
    if _canonical(doc["source"]) != _canonical(source):
        raise ValueError("invalid_inventory_source")

    def check_row(row, ident, kind, expected_path):
        if not isinstance(row, dict) or set(row) != FILE_FIELDS:
            raise ValueError("invalid_file_row_fields")
        if (row["ligand_id"], row["kind"], row["path"]) != (ident, kind, expected_path):
            raise ValueError("invalid_file_row_identity")
        oid = row["lfs_oid_sha256"]
        sha1 = row["git_pointer_blob_sha1"]
        size = row["lfs_size_bytes"]
        if not isinstance(oid, str) or not HEX64.fullmatch(oid):
            raise ValueError("invalid_lfs_oid")
        if not isinstance(sha1, str) or not HEX40.fullmatch(sha1):
            raise ValueError("invalid_pointer_blob_sha1")
        if type(size) is not int or not 0 < size < 10_000_000:
            raise ValueError("invalid_lfs_size")
        if (row["observed_download_sha256"], row["observed_download_size_bytes"]) != (
            oid,
            size,
        ) or type(row["observed_download_size_bytes"]) is not int:
            raise ValueError("observed_download_mismatch")
        if _git_blob_sha1(_pointer(oid, size)) != sha1:
            raise ValueError("pointer_blob_mismatch")
        return f"{row['path']} {oid} {size}"

    def check_rows(rows, expected, rows_digest, path_digest):
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise ValueError("invalid_file_count")
        manifest_rows = [
            check_row(row, ident, kind, expected_path)
            for row, (ident, kind, expected_path) in zip(rows, expected, strict=True)
        ]
        manifest = "\n".join(manifest_rows) + "\n"
        if hashlib.sha256(manifest.encode()).hexdigest() != path_digest:
            raise ValueError("pinned_path_oid_size_mismatch")
        if hashlib.sha256(_canonical(rows)).hexdigest() != rows_digest:
            raise ValueError("pinned_file_rows_mismatch")
        return sum(row["lfs_size_bytes"] for row in rows)

    core = doc["files"]
    support = doc["support_files"]
    core_expected = [(i, k, _path(i, k)) for i in IDS for k in KINDS]
    support_expected = [(i, "ligand_top", _support_path(i, "ligand_top")) for i in IDS]
    support_expected += [
        (None, "protein_pdb", _support_path(None, "protein_pdb")),
        (None, "protein_topol_itp", _support_path(None, "protein_topol_itp")),
    ]
    core_bytes = check_rows(core, core_expected, FILE_ROWS_SHA256, PATH_OID_SIZE_SHA256)
    support_bytes = check_rows(
        support, support_expected, SUPPORT_ROWS_SHA256, SUPPORT_PATH_OID_SIZE_SHA256
    )
    audit = {
        "ligand_count": 40,
        "core_ligand_file_count": 160,
        "support_file_count": 42,
        "file_count": 202,
        "core_ligand_download_bytes": core_bytes,
        "support_download_bytes": support_bytes,
        "total_download_bytes": core_bytes + support_bytes,
        "core_ligand_path_oid_size_manifest_sha256": PATH_OID_SIZE_SHA256,
        "support_path_oid_size_manifest_sha256": SUPPORT_PATH_OID_SIZE_SHA256,
        "raw_prepared_bytes_bundled_in_checkout": False,
        "protected_evaluation_outcomes_read": False,
        "experimental_assay_values_read": False,
        "prepared_state_assay_equivalence_verified": False,
        "scientific_comparison_eligible": False,
        "training_admitted": False,
    }
    if _canonical(doc["audit"]) != _canonical(audit):
        raise ValueError("invalid_audit_boundary")
    return {
        "status": "PASS_STATIC_SOURCE_INVENTORY_ROLE_BLOCKED",
        "inventory_sha256": digest,
        "ligand_count": 40,
        "core_ligand_file_count": 160,
        "support_file_count": 42,
        "file_count": 202,
        "total_download_bytes": core_bytes + support_bytes,
        "official_source_rechecked_now": False,
        "protected_evaluation_outcomes_read": False,
    }


def _get(url: str) -> bytes:
    request = Request(
        url, headers={"User-Agent": "Codex-PFKFB3-LFS-inventory-verifier"}
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=35) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def verify_live(path: Path = INVENTORY) -> dict:
    result = verify(path)
    doc, _ = _load(path)
    api = f"https://api.github.com/repos/{REPOSITORY}/git"
    commit = json.loads(_get(f"{api}/commits/{COMMIT}"))
    if commit.get("sha") != COMMIT or commit.get("tree", {}).get("sha") != ROOT_TREE:
        raise ValueError("official_commit_tree_mismatch")
    tree = json.loads(_get(f"{api}/trees/{ROOT_TREE}?recursive=1"))
    if tree.get("sha") != ROOT_TREE or tree.get("truncated"):
        raise ValueError("official_root_tree_mismatch")
    tree_rows = {item["path"]: item for item in tree["tree"] if item["type"] == "blob"}
    tree_dirs = {item["path"]: item for item in tree["tree"] if item["type"] == "tree"}
    if tree_dirs.get(BASE, {}).get("sha") != LIGANDS_TREE:
        raise ValueError("official_ligands_tree_mismatch")
    prefix = BASE + "/"
    tree_ids = {
        item[len(prefix) :]
        for item in tree_dirs
        if item.startswith(prefix) and "/" not in item[len(prefix) :]
    }
    if tree_ids != set(IDS):
        raise ValueError("official_ligand_ids_mismatch")

    def check(row):
        path = row["path"]
        if tree_rows.get(path, {}).get("sha") != row["git_pointer_blob_sha1"]:
            raise ValueError(f"official_pointer_tree_mismatch:{path}")
        pointer = _get(doc["source"]["lfs_pointer_url_prefix"] + path)
        if pointer != _pointer(row["lfs_oid_sha256"], row["lfs_size_bytes"]):
            raise ValueError(f"official_pointer_bytes_mismatch:{path}")
        body = _get(doc["source"]["lfs_media_url_prefix"] + path)
        if (
            len(body) != row["lfs_size_bytes"]
            or hashlib.sha256(body).hexdigest() != row["lfs_oid_sha256"]
        ):
            raise ValueError(f"official_lfs_bytes_mismatch:{path}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(check, doc["files"] + doc["support_files"]))
    return {
        **result,
        "status": "PASS_LIVE_SOURCE_INVENTORY_ROLE_BLOCKED",
        "official_source_rechecked_now": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Recheck pinned official Git tree, pointer, and LFS bytes",
    )
    args = parser.parse_args()
    print(json.dumps(verify_live() if args.live else verify(), sort_keys=True))

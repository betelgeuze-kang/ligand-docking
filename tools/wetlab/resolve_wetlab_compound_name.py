from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import requests

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_PREFIXES = (
    "chembl_cache_",
    "smiles::",
    "cache_",
)
ID_LIKE_PATTERNS = (
    re.compile(r"^CHEMBL\d+$", re.IGNORECASE),
    re.compile(r"^[A-Z_]+__rep\d+__.+$"),
    re.compile(r"^[a-z0-9_]+_\d{2}_of_\d{2}_\d+$", re.IGNORECASE),
)
DEFAULT_LOCAL_REGISTRY_PATHS = [
    ROOT / "runs" / "wetlab_broad_screen_compound_universe_current.csv",
    ROOT / "runs" / "wetlab_broad_screen_compound_universe_current.json",
]
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
CACTUS_API = "https://cactus.nci.nih.gov/chemical/structure"
USER_AGENT = "wetlab-compound-name-resolution/1.0"


def _text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _looks_placeholder_name(value: Any) -> bool:
    text = _text(value)
    if not text:
        return True
    if text.startswith(PLACEHOLDER_PREFIXES):
        return True
    if text == text.lower() and text.startswith("chembl_cache_"):
        return True
    return any(pattern.match(text) for pattern in ID_LIKE_PATTERNS)


def _human_candidate_from_row(row: Mapping[str, Any]) -> str:
    for key in (
        "preferred_name",
        "resolved_pref_name",
        "pref_name",
        "common_name",
        "display_name",
        "molecule_name",
        "compound_name",
        "name",
    ):
        candidate = _text(row.get(key))
        if candidate and not _looks_placeholder_name(candidate):
            return candidate
    return ""


def _fallback_label(row: Mapping[str, Any]) -> str:
    compound_name = _text(row.get("compound_name"))
    if compound_name.startswith("chembl_cache_"):
        return f"cache ligand {compound_name.removeprefix('chembl_cache_')}"
    ligand_id = _text(row.get("ligand_id"))
    if ligand_id:
        return f"ligand {ligand_id}"
    smiles = _text(row.get("smiles"))
    if smiles:
        return f"SMILES ligand {smiles[:24]}{'...' if len(smiles) > 24 else ''}"
    return "unnamed ligand"


def _cache_key_for_smiles(smiles: str) -> str:
    return f"chembl_cache_{hashlib.sha1(smiles.encode('utf-8')).hexdigest()[:12]}"


def _iter_candidate_paths(row: Mapping[str, Any], extra_paths: Sequence[str | Path] | None = None) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()

    def add(path_like: str | Path | None) -> None:
        raw = _text(path_like)
        if not raw:
            return
        path = Path(raw)
        if not path.is_absolute():
            path = (ROOT / raw).resolve()
            if not path.exists() and raw and "/" not in raw:
                candidate = (ROOT / "runs" / raw).resolve()
                if candidate.exists():
                    path = candidate
        else:
            path = path.resolve()
        if path in seen:
            return
        seen.add(path)
        paths.append(path)

    add(row.get("source_anchor"))
    add(row.get("source_dataset"))
    add(row.get("source_url"))
    if extra_paths:
        for path_like in extra_paths:
            add(path_like)
    for default_path in DEFAULT_LOCAL_REGISTRY_PATHS:
        add(default_path)
    for config_path in sorted((ROOT / "config").glob("ligand_meta*.csv")):
        add(config_path)
    return [path for path in paths if path.exists() and path.is_file()]


def _load_registry_rows(path: Path) -> list[dict[str, Any]]:
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            return [dict(row) for row in payload.get("rows", []) if isinstance(row, dict)]
        return []
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    return []


def _row_matches(reference: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    ref_smiles = _text(reference.get("smiles"))
    ref_ligand_id = _text(reference.get("ligand_id"))
    ref_compound = _text(reference.get("compound_name"))
    candidate_smiles = _text(candidate.get("smiles"), candidate.get("canonical_smiles"))
    candidate_ligand_id = _text(candidate.get("ligand_id"))
    candidate_compound = _text(candidate.get("compound_name"), candidate.get("name"))
    if ref_smiles and candidate_smiles and ref_smiles == candidate_smiles:
        return True
    if ref_ligand_id and candidate_ligand_id and ref_ligand_id == candidate_ligand_id:
        return True
    if ref_compound and candidate_compound and ref_compound == candidate_compound:
        return True
    if ref_smiles and candidate_compound == _cache_key_for_smiles(ref_smiles):
        return True
    return False


def _resolve_local_name(row: Mapping[str, Any], *, extra_paths: Sequence[str | Path] | None = None) -> tuple[str, str]:
    for path in _iter_candidate_paths(row, extra_paths):
        for candidate in _load_registry_rows(path):
            if not _row_matches(row, candidate):
                continue
            human_name = _human_candidate_from_row(candidate)
            if human_name:
                return human_name, f"local:{path}"
    return "", ""


def _http_get_text(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return response.text.strip()


def _lookup_cactus_identifiers(smiles: str, session: requests.Session) -> dict[str, str]:
    results: dict[str, str] = {}
    for suffix, key in (("smiles", "canonical_smiles"), ("stdinchi", "standard_inchi"), ("stdinchikey", "standard_inchi_key")):
        try:
            value = _http_get_text(session, f"{CACTUS_API}/{requests.utils.quote(smiles, safe='')}/{suffix}")
        except Exception:
            continue
        if value and not value.startswith("<"):
            results[key] = value.removeprefix("InChIKey=").removeprefix("InChI=")
            if key == "standard_inchi":
                results[key] = "InChI=" + results[key] if not results[key].startswith("InChI=") else results[key]
    return results


def _lookup_pubchem_by_smiles(smiles: str, session: requests.Session) -> tuple[str, str]:
    try:
        response = session.get(
            f"{PUBCHEM_API}/smiles/{requests.utils.quote(smiles, safe='')}/property/Title,IUPACName/JSON",
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return "", ""
    for row in payload.get("PropertyTable", {}).get("Properties", []) or []:
        title = _text(row.get("Title"))
        if title and not title.isdigit():
            return title, "pubchem:title"
        iupac = _text(row.get("IUPACName"))
        if iupac:
            return iupac, "pubchem:iupac"
    return "", ""


def _lookup_pubchem_by_inchikey(inchikey: str, session: requests.Session) -> tuple[str, str]:
    try:
        response = session.get(
            f"{PUBCHEM_API}/inchikey/{requests.utils.quote(inchikey, safe='')}/property/Title,IUPACName/JSON",
            timeout=20,
        )
        if response.status_code >= 400:
            return "", ""
        payload = response.json()
    except Exception:
        return "", ""
    for row in payload.get("PropertyTable", {}).get("Properties", []) or []:
        title = _text(row.get("Title"))
        if title and not title.isdigit():
            return title, "pubchem_inchikey:title"
        iupac = _text(row.get("IUPACName"))
        if iupac:
            return iupac, "pubchem_inchikey:iupac"
    return "", ""


def _lookup_chembl_by_exact_smiles(smiles: str, session: requests.Session) -> tuple[str, str]:
    try:
        response = session.get(
            f"{CHEMBL_API}/molecule.json",
            params={"molecule_structures__canonical_smiles__iexact": smiles},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return "", ""
    for molecule in payload.get("molecules", []) or []:
        pref_name = _text(molecule.get("pref_name"))
        if pref_name:
            return pref_name, "chembl:pref_name"
        chembl_id = _text(molecule.get("molecule_chembl_id"))
        if chembl_id:
            return chembl_id, "chembl:id"
    return "", ""


def _lookup_chembl_by_inchikey(inchikey: str, session: requests.Session) -> tuple[str, str]:
    try:
        search = session.get(f"{CHEMBL_API}/molecule/search.json", params={"q": inchikey}, timeout=20)
        search.raise_for_status()
        payload = search.json()
    except Exception:
        return "", ""
    for molecule in (payload.get("molecules", []) or [])[:5]:
        chembl_id = _text(molecule.get("molecule_chembl_id"))
        if not chembl_id:
            continue
        try:
            detail = session.get(f"{CHEMBL_API}/molecule/{chembl_id}.json", timeout=20)
            detail.raise_for_status()
            detail_payload = detail.json()
        except Exception:
            continue
        structures = dict(detail_payload.get("molecule_structures", {}) or {})
        if _text(structures.get("standard_inchi_key")).upper() != inchikey.upper():
            continue
        pref_name = _text(detail_payload.get("pref_name"))
        if pref_name:
            return pref_name, "chembl_inchikey:pref_name"
        return chembl_id, "chembl_inchikey:id"
    return "", ""


def _resolve_external_name(row: Mapping[str, Any], session: requests.Session | None = None) -> tuple[str, str, dict[str, str]]:
    smiles = _text(row.get("smiles"))
    if not smiles:
        return "", "", {}
    own_session = session is None
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)
    identifiers = _lookup_cactus_identifiers(smiles, session)
    exact_smiles = identifiers.get("canonical_smiles") or smiles
    for lookup in (
        lambda: _lookup_pubchem_by_smiles(exact_smiles, session),
        lambda: _lookup_chembl_by_exact_smiles(exact_smiles, session),
        lambda: _lookup_pubchem_by_inchikey(identifiers.get("standard_inchi_key", ""), session),
        lambda: _lookup_chembl_by_inchikey(identifiers.get("standard_inchi_key", ""), session),
    ):
        name, source = lookup()
        if name:
            if own_session:
                session.close()
            return name, source, identifiers
    if own_session:
        session.close()
    return "", "", identifiers


def resolve_compound_name(
    row: Mapping[str, Any],
    *,
    extra_registry_paths: Sequence[str | Path] | None = None,
    allow_external: bool = True,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    literal_name = _human_candidate_from_row(row)
    if literal_name:
        return {
            "best_name": literal_name,
            "exact_human_name_found": True,
            "resolution_level": "literal_row",
            "resolution_source": "row",
            "compound_name": _text(row.get("compound_name")),
            "ligand_id": _text(row.get("ligand_id")),
            "smiles": _text(row.get("smiles")),
        }

    local_name, local_source = _resolve_local_name(row, extra_paths=extra_registry_paths)
    if local_name:
        return {
            "best_name": local_name,
            "exact_human_name_found": True,
            "resolution_level": "local_registry",
            "resolution_source": local_source,
            "compound_name": _text(row.get("compound_name")),
            "ligand_id": _text(row.get("ligand_id")),
            "smiles": _text(row.get("smiles")),
        }

    external_identifiers: dict[str, str] = {}
    if allow_external:
        external_name, external_source, external_identifiers = _resolve_external_name(row, session=session)
        if external_name:
            return {
                "best_name": external_name,
                "exact_human_name_found": True,
                "resolution_level": "external_registry",
                "resolution_source": external_source,
                "compound_name": _text(row.get("compound_name")),
                "ligand_id": _text(row.get("ligand_id")),
                "smiles": _text(row.get("smiles")),
                "canonical_smiles": _text(external_identifiers.get("canonical_smiles")),
                "standard_inchi": _text(external_identifiers.get("standard_inchi")),
                "standard_inchi_key": _text(external_identifiers.get("standard_inchi_key")),
            }

    return {
        "best_name": _fallback_label(row),
        "exact_human_name_found": False,
        "resolution_level": "fallback_alias",
        "resolution_source": "generated",
        "compound_name": _text(row.get("compound_name")),
        "ligand_id": _text(row.get("ligand_id")),
        "smiles": _text(row.get("smiles")),
        "canonical_smiles": _text(external_identifiers.get("canonical_smiles")),
        "standard_inchi": _text(external_identifiers.get("standard_inchi")),
        "standard_inchi_key": _text(external_identifiers.get("standard_inchi_key")),
    }


def load_ligand_row_from_manifest(manifest_csv: str | Path, ligand_id: str) -> dict[str, Any]:
    path = Path(manifest_csv)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if _text(row.get("ligand_id")) == ligand_id:
                return dict(row)
    raise KeyError(f"Ligand '{ligand_id}' not found in {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the best available human-readable compound name for a wetlab ligand row.")
    parser.add_argument("--manifest-csv", help="Ligand manifest CSV to load the row from.")
    parser.add_argument("--ligand-id", help="Ligand id to resolve from the manifest or row context.")
    parser.add_argument("--compound-name", default="")
    parser.add_argument("--smiles", default="")
    parser.add_argument("--source-dataset", default="")
    parser.add_argument("--source-anchor", default="")
    parser.add_argument("--no-external", action="store_true")
    parser.add_argument("--out-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    row: dict[str, Any]
    if _text(args.manifest_csv, args.ligand_id):
        row = load_ligand_row_from_manifest(args.manifest_csv, args.ligand_id)
    else:
        row = {
            "ligand_id": args.ligand_id,
            "compound_name": args.compound_name,
            "smiles": args.smiles,
            "source_dataset": args.source_dataset,
            "source_anchor": args.source_anchor,
        }
    payload = resolve_compound_name(row, allow_external=not args.no_external)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
from pathlib import Path

from tools import wetlab_compound_name_resolution as mod


class FakeResponse:
    def __init__(self, status_code=200, *, text="", json_payload=None):
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._json_payload


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.headers = {}

    def get(self, url, params=None, timeout=20):
        key = (url, tuple(sorted((params or {}).items())))
        response = self.routes.get(key)
        if response is None:
            response = self.routes.get(url)
        if response is None:
            return FakeResponse(status_code=404, text="")
        return response

    def close(self):
        return None


def test_resolve_compound_name_uses_literal_human_name():
    payload = mod.resolve_compound_name(
        {
            "ligand_id": "lig1",
            "compound_name": "Brequinar",
            "smiles": "CCO",
        },
        allow_external=False,
    )

    assert payload["best_name"] == "Brequinar"
    assert payload["exact_human_name_found"] is True
    assert payload["resolution_level"] == "literal_row"


def test_resolve_compound_name_uses_local_registry_match(tmp_path: Path):
    registry = tmp_path / "registry.csv"
    with registry.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ligand_id", "smiles", "compound_name", "preferred_name"])
        writer.writeheader()
        writer.writerow(
            {
                "ligand_id": "chembl123",
                "smiles": "CCCC",
                "compound_name": "chembl_cache_deadbeef0001",
                "preferred_name": "Local Preferred Name",
            }
        )

    payload = mod.resolve_compound_name(
        {
            "ligand_id": "row1",
            "compound_name": "chembl_cache_deadbeef0001",
            "smiles": "CCCC",
        },
        extra_registry_paths=[registry],
        allow_external=False,
    )

    assert payload["best_name"] == "Local Preferred Name"
    assert payload["exact_human_name_found"] is True
    assert payload["resolution_level"] == "local_registry"


def test_resolve_compound_name_uses_external_exact_lookup():
    smiles = "CCCC1C(COC(C)C)CCCC1NCCO"
    quoted = "CCCC1C%28COC%28C%29C%29CCCC1NCCO"
    routes = {
        f"{mod.CACTUS_API}/{quoted}/smiles": FakeResponse(text=smiles),
        f"{mod.CACTUS_API}/{quoted}/stdinchi": FakeResponse(text="InChI=1S/example"),
        f"{mod.CACTUS_API}/{quoted}/stdinchikey": FakeResponse(text="InChIKey=EXAMPLEKEY-UHFFFAOYSA-N"),
        f"{mod.PUBCHEM_API}/smiles/{quoted}/property/Title,IUPACName/JSON": FakeResponse(
            json_payload={"PropertyTable": {"Properties": [{"Title": "Resolved External Name"}]}}
        ),
    }
    session = FakeSession(routes)

    payload = mod.resolve_compound_name(
        {
            "ligand_id": "row2",
            "compound_name": "chembl_cache_e76db773befe",
            "smiles": smiles,
        },
        extra_registry_paths=[],
        allow_external=True,
        session=session,
    )

    assert payload["best_name"] == "Resolved External Name"
    assert payload["exact_human_name_found"] is True
    assert payload["resolution_level"] == "external_registry"
    assert payload["standard_inchi_key"] == "EXAMPLEKEY-UHFFFAOYSA-N"


def test_resolve_compound_name_falls_back_when_no_exact_name():
    smiles = "CCCC1C(COC(C)C)CCCC1NCCO"
    quoted = "CCCC1C%28COC%28C%29C%29CCCC1NCCO"
    routes = {
        f"{mod.CACTUS_API}/{quoted}/smiles": FakeResponse(text=smiles),
        f"{mod.CACTUS_API}/{quoted}/stdinchi": FakeResponse(text="InChI=1S/example"),
        f"{mod.CACTUS_API}/{quoted}/stdinchikey": FakeResponse(text="InChIKey=KCIJELFEAWYHMG-UHFFFAOYSA-N"),
        f"{mod.PUBCHEM_API}/smiles/{quoted}/property/Title,IUPACName/JSON": FakeResponse(
            json_payload={"PropertyTable": {"Properties": [{"CID": 0}]}}
        ),
        (f"{mod.CHEMBL_API}/molecule.json", (("molecule_structures__canonical_smiles__iexact", smiles),)): FakeResponse(
            json_payload={"molecules": []}
        ),
        f"{mod.PUBCHEM_API}/inchikey/KCIJELFEAWYHMG-UHFFFAOYSA-N/property/Title,IUPACName/JSON": FakeResponse(status_code=404),
        (f"{mod.CHEMBL_API}/molecule/search.json", (("q", "KCIJELFEAWYHMG-UHFFFAOYSA-N"),)): FakeResponse(
            json_payload={"molecules": []}
        ),
    }
    session = FakeSession(routes)

    payload = mod.resolve_compound_name(
        {
            "ligand_id": "t_cruzi_pde_20_of_20_095609",
            "compound_name": "chembl_cache_e76db773befe",
            "smiles": smiles,
        },
        allow_external=True,
        session=session,
    )

    assert payload["best_name"] == "cache ligand e76db773befe"
    assert payload["exact_human_name_found"] is False
    assert payload["resolution_level"] == "fallback_alias"
    assert payload["standard_inchi_key"] == "KCIJELFEAWYHMG-UHFFFAOYSA-N"


def test_load_ligand_row_from_manifest(tmp_path: Path):
    manifest = tmp_path / "ligand_manifest.csv"
    manifest.write_text(
        "ligand_id,smiles,compound_name\nrow_a,CCO,Sample\nrow_b,CCC,Other\n",
        encoding="utf-8",
    )

    row = mod.load_ligand_row_from_manifest(manifest, "row_b")
    assert row["compound_name"] == "Other"

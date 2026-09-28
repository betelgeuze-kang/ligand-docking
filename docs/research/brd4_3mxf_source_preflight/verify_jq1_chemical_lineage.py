"""Verify a bounded source-only JQ1 graph and proton-location contrast.

The committed PubChem projection contains selected structural facts, not raw
PubChem responses or prepared ligands. ``--live`` separately checks those facts
against the four official PUG REST responses. No crystallographic hydrogen,
assay microstate, parameter, or evaluation role is inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
PROJECTION_NAME = "pubchem_jq1_structure_projection.v1.json"
RECEIPT_NAME = "jq1_chemical_lineage.v1.json"
PROJECTION_SHA256 = "de411616d5ac55c32e9e2788ab13bafb9c68d43d560ca1c728489b8e9fb81957"
SOURCES = {
    "coordinates": (
        "official_sources/coordinates-3mxf.cif",
        287430,
        "fb123201edb59709d14b64c5cb4296a90b6d35c45505baba48600d04e4cdd401",
    ),
    "ccd_jq1": (
        "official_sources/chemcomp-jq1.cif",
        10889,
        "9652a88ed9dd1f78e4dbfd2fcd127e40a9643fc5b111d84d8e615adc399213e5",
    ),
}
CIDS = (46907787, 49871818, 49867179, 144913635)
EXPECTED_STEREO = {46907787: "S", 49871818: "R", 49867179: "S", 144913635: "S"}
EXPECTED_TETRAHEDRAL = {
    "S": {
        "center": 9,
        "above": 6,
        "top": 13,
        "bottom": 10,
        "below": 32,
        "parity": 2,
        "type": 1,
    },
    "R": {
        "center": 9,
        "above": 6,
        "top": 10,
        "bottom": 13,
        "below": 32,
        "parity": 1,
        "type": 1,
    },
}
ELEMENTS = {1: "H", 6: "C", 7: "N", 8: "O", 16: "S", 17: "CL"}
UNPREPARED_ELIGIBILITY = {
    "assay_microstate_selected": False,
    "receptor_prepared": False,
    "s_ligand_prepared": False,
    "r_ligand_prepared": False,
    "charges_or_parameters_assigned": False,
    "physical_evaluations": 0,
    "source_roles_assigned": False,
    "training_admitted": False,
    "independent_evaluation_admitted": False,
    "scientifically_validated": False,
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def json_bytes(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("ascii")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _load_json(path: Path):
    require(path.is_file() and not path.is_symlink(), "file_missing_or_symlink")
    return json.loads(path.read_bytes(), object_pairs_hook=_unique_pairs)


def _load_parser():
    path = REPOSITORY / "betelgeuze_engine_v2/molecular/mmcif_syntax.py"
    spec = importlib.util.spec_from_file_location("_brd4_jq1_lineage_cif", path)
    require(spec is not None and spec.loader is not None, "cif_parser_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses inspects the importing module
    spec.loader.exec_module(module)
    return module.parse_cif_block


def _rows(block, category: str):
    prefix = category + "."
    loops = [loop for loop in block.loops if category in loop.categories]
    scalars = {
        key: value
        for key, value in block.scalar_values.items()
        if key.startswith(prefix)
    }
    require(not (loops and scalars) and len(loops) <= 1, "ambiguous_cif_category")
    if loops:
        loop = loops[0]
        require(loop.categories == (category,), "mixed_cif_category")
        values = [dict(zip(loop.tags, row)) for row in loop.rows]
    else:
        require(bool(scalars), "missing_cif_category")
        values = [scalars]
    return [
        {key[len(prefix) :]: token.value for key, token in row.items()}
        for row in values
    ]


def _read_cif_sources(root: Path):
    source_bytes = {}
    for key, (relative, size, digest) in SOURCES.items():
        path = root / relative
        require(
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve()),
            "cif_source_missing_or_outside_packet",
        )
        raw = path.read_bytes()
        require(
            len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
            "cif_source_bytes_changed",
        )
        source_bytes[key] = raw
    return source_bytes


def _property(record: dict, label: str, name: str = "") -> str:
    found = [
        item["value"]["sval"]
        for item in record["props"]
        if item["urn"]["label"] == label and item["urn"].get("name", "") == name
    ]
    require(len(found) == 1, "pubchem_property_missing_or_ambiguous")
    return found[0]


def project_pubchem_response(cid: int, raw: bytes) -> dict:
    document = json.loads(raw, object_pairs_hook=_unique_pairs)
    records = document["PC_Compounds"]
    require(len(records) == 1, "pubchem_record_count_changed")
    record = records[0]
    require(record["id"]["id"]["cid"] == cid, "pubchem_cid_changed")
    atoms, bonds = record["atoms"], record["bonds"]
    aids = atoms["aid"]
    require(aids == list(range(1, len(aids) + 1)), "pubchem_atom_ids_changed")
    require(len(aids) == len(atoms["element"]), "pubchem_atom_element_count_changed")
    require(
        len(bonds["aid1"]) == len(bonds["aid2"]) == len(bonds["order"]),
        "pubchem_bond_columns_changed",
    )
    require(
        len(record["stereo"]) == 1 and set(record["stereo"][0]) == {"tetrahedral"},
        "pubchem_stereo_count_changed",
    )
    return {
        "cid": cid,
        "source_url": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/record/JSON?record_type=2d",
        "source_response_sha256": hashlib.sha256(raw).hexdigest(),
        "evidence_class": "standardized_pubchem_compound_2d_structure_not_assay_material",
        "formula": _property(record, "Molecular Formula"),
        "charge": record["charge"],
        "inchi": _property(record, "InChI", "Standard"),
        "inchikey": _property(record, "InChIKey", "Standard"),
        "systematic_name": _property(record, "IUPAC Name", "Systematic"),
        "atomic_numbers_by_aid": atoms["element"],
        "atom_formal_charges": sorted(
            [[item["aid"], item["value"]] for item in atoms.get("charge", [])]
        ),
        "bonds": [
            [first, second, order]
            for first, second, order in zip(
                bonds["aid1"], bonds["aid2"], bonds["order"]
            )
        ],
        "tetrahedral": record["stereo"][0]["tetrahedral"],
    }


def _pubchem_projection(cids_and_raw: dict[int, bytes]) -> dict:
    require(set(cids_and_raw) == set(CIDS), "pubchem_candidate_set_changed")
    return {
        "schema_version": "brd4_jq1_pubchem_structure_projection_v1",
        "scope": "Selected derived molecular identity facts; original PUG responses and SDFs are not redistributed",
        "research_source_use_only": True,
        "product_source_rights_reviewed": False,
        "records": [project_pubchem_response(cid, cids_and_raw[cid]) for cid in CIDS],
    }


def fetch_live_projection() -> dict:
    responses = {}
    for cid in CIDS:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/record/JSON?record_type=2d"
        with urlopen(url, timeout=25) as response:
            require(response.status == 200, "pubchem_live_response_failed")
            responses[cid] = response.read(100_000)
        require(0 < len(responses[cid]) < 100_000, "pubchem_live_response_size_invalid")
    return _pubchem_projection(responses)


def _checked_projection(root: Path):
    path = root / PROJECTION_NAME
    projection = _load_json(path)
    require(
        hashlib.sha256(path.read_bytes()).hexdigest() == PROJECTION_SHA256,
        "pubchem_projection_bytes_changed",
    )
    require(
        projection["schema_version"] == "brd4_jq1_pubchem_structure_projection_v1",
        "pubchem_projection_schema_changed",
    )
    require(
        projection["research_source_use_only"] is True
        and projection["product_source_rights_reviewed"] is False,
        "pubchem_projection_rights_promoted",
    )
    require(
        [item["cid"] for item in projection["records"]] == list(CIDS),
        "pubchem_projection_cid_order_changed",
    )
    return projection


def _graph(elements: dict, bonds: list[tuple], hydrogen: str | int):
    heavy = {name: element for name, element in elements.items() if element != hydrogen}
    adjacency = {name: set() for name in heavy}
    h_count = {name: 0 for name in heavy}
    for first, second in bonds:
        require(
            first in elements and second in elements and first != second,
            "invalid_source_bond",
        )
        if first in heavy and second in heavy:
            require(second not in adjacency[first], "duplicate_heavy_bond")
            adjacency[first].add(second)
            adjacency[second].add(first)
        elif first in heavy and elements[second] == hydrogen:
            h_count[first] += 1
        elif second in heavy and elements[first] == hydrogen:
            h_count[second] += 1
        else:
            require(False, "hydrogen_hydrogen_bond")
    return heavy, adjacency, h_count


def _all_heavy_isomorphisms(ccd_graph, pubchem_graph):
    first, adj_first, _ = ccd_graph
    second, adj_second, _ = pubchem_graph
    require(len(first) == len(second), "heavy_atom_count_mismatch")
    require(
        sum(map(len, adj_first.values())) == sum(map(len, adj_second.values())),
        "heavy_bond_count_mismatch",
    )

    def signature(name, elements, adjacency):
        return (
            elements[name],
            len(adjacency[name]),
            tuple(sorted(elements[n] for n in adjacency[name])),
        )

    candidates = {
        name: [
            other
            for other in second
            if signature(name, first, adj_first) == signature(other, second, adj_second)
        ]
        for name in first
    }
    require(all(candidates.values()), "heavy_graph_element_environment_mismatch")
    order = sorted(
        first, key=lambda name: (len(candidates[name]), -len(adj_first[name]), name)
    )
    solutions = []

    def search(mapping, used):
        require(len(solutions) <= 1000, "heavy_graph_mapping_explosion")
        if len(mapping) == len(order):
            solutions.append(dict(mapping))
            return
        name = order[len(mapping)]
        for other in candidates[name]:
            if other in used:
                continue
            if any(
                (prior in adj_first[name]) != (mapped in adj_second[other])
                for prior, mapped in mapping.items()
            ):
                continue
            mapping[name] = other
            used.add(other)
            search(mapping, used)
            used.remove(other)
            del mapping[name]

    search({}, set())
    require(bool(solutions), "heavy_graph_not_isomorphic")
    return solutions


def _ccd_observation(root: Path):
    raw = _read_cif_sources(root)
    parse = _load_parser()
    ccd = parse(raw["ccd_jq1"].decode("ascii"))
    coordinates = parse(raw["coordinates"].decode("ascii"))
    comp = _rows(ccd, "_chem_comp")
    require(len(comp) == 1 and comp[0]["id"] == "JQ1", "ccd_component_changed")
    atoms = [row for row in _rows(ccd, "_chem_comp_atom") if row["comp_id"] == "JQ1"]
    names = {row["atom_id"]: row for row in atoms}
    require(len(names) == len(atoms) == 57, "ccd_atom_inventory_changed")
    bonds = [row for row in _rows(ccd, "_chem_comp_bond") if row["comp_id"] == "JQ1"]
    graph = _graph(
        {name: row["type_symbol"] for name, row in names.items()},
        [(row["atom_id_1"], row["atom_id_2"]) for row in bonds],
        "H",
    )
    require(
        len(graph[0]) == 31 and sum(map(len, graph[1].values())) == 68,
        "ccd_heavy_graph_changed",
    )
    charged = {
        name: int(row["charge"]) for name, row in names.items() if row["charge"] != "0"
    }
    stereo = {
        name: row["pdbx_stereo_config"]
        for name, row in names.items()
        if row["pdbx_stereo_config"] in {"R", "S"}
    }
    require(
        charged == {"NBD": 1} and stereo == {"CBC": "S"} and graph[2]["NAP"] == 1,
        "ccd_charge_stereo_or_hydrogen_changed",
    )
    descriptors = [
        row
        for row in _rows(ccd, "_pdbx_chem_comp_descriptor")
        if row["comp_id"] == "JQ1"
    ]
    inchi = [row["descriptor"] for row in descriptors if row["type"] == "InChI"]
    key = [row["descriptor"] for row in descriptors if row["type"] == "InChIKey"]
    require(len(inchi) == len(key) == 1, "ccd_identity_descriptor_changed")
    sites = [
        row
        for row in _rows(coordinates, "_atom_site")
        if row["label_comp_id"] == "JQ1"
        and row["label_asym_id"] == "B"
        and row["pdbx_pdb_model_num"] == "1"
    ]
    require(
        len(sites) == 31
        and all(
            row["type_symbol"] != "H" and row["pdbx_formal_charge"] == "?"
            for row in sites
        ),
        "deposited_jq1_observation_changed",
    )
    return {
        "graph": graph,
        "heavy_bond_orders": {
            frozenset((row["atom_id_1"], row["atom_id_2"])): {
                "SING": 1,
                "DOUB": 2,
                "TRIP": 3,
            }[row["value_order"]]
            for row in bonds
            if row["atom_id_1"] in graph[0] and row["atom_id_2"] in graph[0]
        },
        "summary": {
            "ccd_formula": comp[0]["formula"],
            "ccd_formal_charge": int(comp[0]["pdbx_formal_charge"]),
            "ccd_inchi": inchi[0],
            "ccd_inchikey": key[0],
            "ccd_stereocenters": stereo,
            "ccd_nonzero_atom_charges": charged,
            "ccd_explicit_hydrogen_bonds": {
                name: count for name, count in graph[2].items() if count
            },
            "ccd_heavy_atom_count": len(graph[0]),
            "ccd_heavy_bond_count": sum(map(len, graph[1].values())) // 2,
            "deposited_heavy_atom_count": len(sites),
            "deposited_hydrogen_count": 0,
            "deposited_unknown_atom_site_formal_charge_count": len(sites),
            "ccd_dictionary_state_is_experimentally_observed_microstate": False,
        },
    }


def _pubchem_graph(record: dict):
    atomic_numbers = record["atomic_numbers_by_aid"]
    elements = {
        aid: ELEMENTS[number] for aid, number in enumerate(atomic_numbers, start=1)
    }
    bonds = [
        (first, second)
        for first, second, order in record["bonds"]
        if order in {1, 2, 3}
    ]
    require(len(bonds) == len(record["bonds"]), "pubchem_bond_order_unexpected")
    return _graph(elements, bonds, "H")


def build_observation(root: Path = ROOT, projection: dict | None = None):
    ccd = _ccd_observation(root)
    if projection is None:
        projection = _checked_projection(root)
    require(
        [item["cid"] for item in projection["records"]] == list(CIDS),
        "pubchem_candidate_set_changed",
    )
    comparisons = []
    for record in projection["records"]:
        cid = record["cid"]
        graph = _pubchem_graph(record)
        solutions = _all_heavy_isomorphisms(ccd["graph"], graph)
        require(len(solutions) == 12, "heavy_graph_automorphism_count_changed")
        mapped_center = {mapping["CBC"] for mapping in solutions}
        tetra = record["tetrahedral"]
        require(
            mapped_center == {tetra["center"]},
            "stereocenter_atom_mapping_not_invariant",
        )
        stereodescriptor = EXPECTED_STEREO[cid]
        require(
            f"(9{stereodescriptor})" in record["systematic_name"],
            "pubchem_stereo_descriptor_changed",
        )
        require(
            tetra == EXPECTED_TETRAHEDRAL[stereodescriptor],
            "pubchem_tetrahedral_source_changed",
        )
        require(
            len(record["inchi"].split("/m")) == 2 and record["charge"] in {0, 1},
            "pubchem_identity_or_charge_changed",
        )
        require(
            len(graph[0]) == 31 and sum(map(len, graph[1].values())) == 68,
            "pubchem_heavy_graph_changed",
        )
        pubchem_orders = {
            frozenset((first, second)): order
            for first, second, order in record["bonds"]
            if first in graph[0] and second in graph[0]
        }
        literal_bond_order_matches = sum(
            all(
                ccd_order == pubchem_orders[frozenset(mapping[name] for name in names)]
                for names, ccd_order in ccd["heavy_bond_orders"].items()
            )
            for mapping in solutions
        )
        require(literal_bond_order_matches == 0, "literal_bond_order_contrast_changed")
        h_changes = set()
        charge_changes = set()
        charge_map = dict(record["atom_formal_charges"])
        for mapping in solutions:
            h_changes.add(
                tuple(
                    sorted(
                        (name, ccd["graph"][2][name], graph[2][aid])
                        for name, aid in mapping.items()
                        if ccd["graph"][2][name] != graph[2][aid]
                    )
                )
            )
            charge_changes.add(
                tuple(
                    sorted(
                        (name, int(name == "NBD"), charge_map.get(aid, 0))
                        for name, aid in mapping.items()
                        if int(name == "NBD") != charge_map.get(aid, 0)
                    )
                )
            )
        require(
            len(h_changes) == len(charge_changes) == 1,
            "ambiguous_proton_or_charge_mapping",
        )
        invariant = {
            name: sorted({mapping[name] for mapping in solutions})
            for name in ccd["graph"][0]
        }
        comparisons.append(
            {
                "cid": cid,
                "source_url": record["source_url"],
                "source_response_sha256": record["source_response_sha256"],
                "pubchem_formula": record["formula"],
                "pubchem_charge": record["charge"],
                "pubchem_inchi": record["inchi"],
                "pubchem_inchikey": record["inchikey"],
                "pubchem_systematic_stereo": stereodescriptor,
                "pubchem_tetrahedral_center_aid": tetra["center"],
                "pubchem_tetrahedral_source_record": tetra,
                "heavy_atom_count": len(graph[0]),
                "heavy_bond_count": sum(map(len, graph[1].values())) // 2,
                "element_graph_isomorphism_count": len(solutions),
                "literal_bond_order_preserving_mapping_count": literal_bond_order_matches,
                "unique_full_heavy_atom_name_mapping": False,
                "invariant_ccd_to_pubchem_aids": {
                    name: aids[0] for name, aids in invariant.items() if len(aids) == 1
                },
                "nonunique_ccd_to_pubchem_aids": {
                    name: aids for name, aids in invariant.items() if len(aids) > 1
                },
                "ccd_vs_pubchem_explicit_hydrogen_count_changes": [
                    list(item) for item in next(iter(h_changes))
                ],
                "ccd_vs_pubchem_atom_charge_changes": [
                    list(item) for item in next(iter(charge_changes))
                ],
                "same_inchi_as_ccd": record["inchi"] == ccd["summary"]["ccd_inchi"],
                "same_inchikey_as_ccd": record["inchikey"]
                == ccd["summary"]["ccd_inchikey"],
                "assay_microstate_equivalence_inferred": False,
            }
        )
    by_cid = {item["cid"]: item for item in comparisons}
    require(
        by_cid[46907787]["ccd_vs_pubchem_explicit_hydrogen_count_changes"]
        == [["NAP", 1, 0]],
        "neutral_s_proton_contrast_changed",
    )
    require(
        by_cid[49871818]["ccd_vs_pubchem_explicit_hydrogen_count_changes"]
        == [["NAP", 1, 0]],
        "neutral_r_proton_contrast_changed",
    )
    require(
        by_cid[49867179]["ccd_vs_pubchem_explicit_hydrogen_count_changes"]
        == [["NAO", 0, 1], ["NAP", 1, 0]],
        "ring_cation_proton_contrast_changed",
    )
    require(
        by_cid[144913635]["ccd_vs_pubchem_explicit_hydrogen_count_changes"]
        == [["NAP", 1, 0], ["OAG", 0, 1]],
        "oxygen_cation_proton_contrast_changed",
    )
    require(
        by_cid[46907787]["ccd_vs_pubchem_atom_charge_changes"] == [["NBD", 1, 0]],
        "neutral_s_charge_contrast_changed",
    )
    require(
        by_cid[49871818]["ccd_vs_pubchem_atom_charge_changes"] == [["NBD", 1, 0]],
        "neutral_r_charge_contrast_changed",
    )
    require(
        by_cid[49867179]["ccd_vs_pubchem_atom_charge_changes"] == [],
        "ring_cation_charge_contrast_changed",
    )
    require(
        by_cid[144913635]["ccd_vs_pubchem_atom_charge_changes"]
        == [["NBD", 1, 0], ["OAG", 0, 1]],
        "oxygen_cation_charge_contrast_changed",
    )
    require(
        by_cid[46907787]["pubchem_charge"] == by_cid[49871818]["pubchem_charge"] == 0,
        "neutral_pair_charge_changed",
    )
    require(
        by_cid[49867179]["pubchem_charge"] == by_cid[144913635]["pubchem_charge"] == 1,
        "cation_charge_changed",
    )
    require(
        all(by_cid[cid]["same_inchi_as_ccd"] for cid in (49867179, 144913635)),
        "cation_inchi_contrast_changed",
    )
    require(
        not any(by_cid[cid]["same_inchi_as_ccd"] for cid in (46907787, 49871818)),
        "neutral_inchi_contrast_changed",
    )
    return {
        "schema_version": "brd4_jq1_chemical_lineage_observation_v1",
        "status": "SOURCE_CHEMICAL_LINEAGE_OBSERVED_PREPARATION_AND_ADMISSION_BLOCKED",
        "qualification": "NOT_QUALIFIED",
        "evidence_class": "ccd_dictionary_and_pubchem_standardized_identity_contrast_not_experimental_microstate",
        "ccd_sources": {
            key: {"relative_path": relative, "size_bytes": size, "sha256": digest}
            for key, (relative, size, digest) in SOURCES.items()
        },
        "pubchem_projection": {
            "relative_path": PROJECTION_NAME,
            "sha256": PROJECTION_SHA256,
            "raw_pug_records_redistributed": False,
            "product_source_rights_reviewed": False,
        },
        "ccd_and_3mxf": ccd["summary"],
        "comparisons": comparisons,
        "interpretation_boundaries": {
            "inchi_or_inchikey_match_proves_explicit_hydrogen_location": False,
            "ccd_dictionary_charge_or_hydrogen_observed_in_xray": False,
            "pubchem_identity_proves_tanaka_assay_material_microstate": False,
            "r_enantiomer_bound_pose_in_3mxf": False,
            "complete_unique_ccd_to_pubchem_atom_map": False,
            "literal_bond_order_match_or_mismatch_establishes_chemical_equivalence": False,
            "ion_or_water_treatment_selected": False,
        },
        "eligibility": UNPREPARED_ELIGIBILITY,
    }


def verify(root: Path = ROOT, live: bool = False):
    projection = _checked_projection(root)
    if live:
        require(
            fetch_live_projection() == projection, "live_pubchem_projection_mismatch"
        )
    expected = json_bytes(build_observation(root, projection))
    path = root / RECEIPT_NAME
    require(
        path.is_file() and not path.is_symlink(), "lineage_receipt_missing_or_symlink"
    )
    require(path.read_bytes() == expected, "lineage_receipt_mismatch")
    return {
        "status": "PASS_SOURCE_CHEMICAL_LINEAGE_ONLY",
        "live_pubchem_rechecked": live,
        "prepared_pairs": 0,
        "scientifically_validated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="also refetch and compare official PubChem responses",
    )
    parser.add_argument(
        "--write", action="store_true", help="create the receipt; never overwrite"
    )
    args = parser.parse_args()
    if args.write:
        with (ROOT / RECEIPT_NAME).open("xb") as stream:
            stream.write(json_bytes(build_observation()))
    print(json.dumps(verify(live=args.live), sort_keys=True))


if __name__ == "__main__":
    main()

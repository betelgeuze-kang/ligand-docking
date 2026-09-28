"""Offline check of the source-only PFKFB3 primary-structure crosswalk.

This validates a frozen transcription against constants in this file and the
already pinned OpenFF inventory in this checkout. It does not fetch a paper,
supplement, PDB record, or SDF, and it does not inspect experimental values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "primary_structure_crosswalk.v1.json"
INVENTORY = ROOT / "openff_lfs_inventory.v1.json"
INVENTORY_BYTES = 102836
INVENTORY_SHA256 = "23345cfcb902ee7d0009ee630760797a6212ed7047f273eb4edef9487bc56e13"
COMMIT = "fe6f96916b2e28f9c14398d77c838d6515e931b0"
DOI = "10.1002/cmdc.201800569"
MANUSCRIPT_URL = (
    "https://www.researchgate.net/publication/328632054_"
    "Discovery_and_Structure-Activity_Relationships_of_N-Aryl_"
    "6-Aminoquinoxalines_as_Potent_PFKFB3_Kinase_Inhibitors"
)
PUBLISHER_URL = "https://chemistry-europe.onlinelibrary.wiley.com/doi/abs/" + DOI
PATENT_URL = "https://patents.google.com/patent/WO2016180537A1/en"
MAX_BYTES = 65536
IDS = (
    19,
    20,
    23,
    24,
    26,
    29,
    30,
    31,
    33,
    34,
    35,
    36,
    37,
    38,
    39,
    41,
    42,
    43,
    44,
    46,
    47,
    48,
    49,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    62,
    63,
    64,
    65,
    67,
    68,
    69,
    70,
)
DIRECT = {20, 37, 38, 70}
MOTIF = {19, 23, 35, 36, 52, 57, 58, 59, 60, 62, 63, 67, 68, 69}

# (manuscript page, sentence locator, manuscript structure description,
#  structure observed in the hash-pinned OpenFF SDF, additional primary source,
#  additional source locator)
EVIDENCE = {
    19: (
        3,
        "Chemistry; Scheme 1 paragraph on the aniline coupling",
        "Phenylamino compound 19 made from aniline on the 1-methylindole series.",
        "Phenylamino quinoxaline bearing 1-methylindole.",
        None,
        None,
    ),
    20: (
        3,
        "Chemistry; final paragraph before Results and Discussion",
        "Compound 20 made with 3-methoxyphenylboronic acid; Figure 6 depicts its crystal overlay.",
        "Meta-methoxyphenyl quinoxaline.",
        None,
        None,
    ),
    23: (
        5,
        "Results and Discussion; paragraph after Table 1 on pyridyl isomers",
        "Compound 23 replaces the phenylamino group with 3-pyridyl.",
        "3-pyridylamino quinoxaline bearing 1-methylindole.",
        None,
        None,
    ),
    35: (
        5,
        "Results and Discussion; paragraph identifying the best ortho groups",
        "Compound 35 has an ortho methylsulfone on the arylamino group; the subsequent paragraph identifies a 3-amino-4-methylsulfonylpyridine pendant.",
        "Ortho methylsulfone on 3-pyridylamino; 1-methylindole on quinoxaline.",
        None,
        None,
    ),
    36: (
        5,
        "Results and Discussion; paragraph on bridge methylation",
        "Compound 36 is the bridging N-methyl analogue of compound 35.",
        "Bridge N-methyl analogue of the lig_35 graph.",
        None,
        None,
    ),
    37: (
        5,
        "Results and Discussion; carboxamide crystal paragraph and Figure 4",
        "Compound 37 is the carboxamide analogue crystallized as PDB 6HVH.",
        "Carboxamide-substituted pyridylamino quinoxaline with 1-methylindole; agrees with GV2.",
        "https://www.rcsb.org/structure/6HVH",
        "PDB 6HVH, chemical component GV2",
    ),
    38: (
        7,
        "Figure 6 caption identifying compound 38 and PDB 6HVI",
        "Compound 38 has the 6HVI crystal structure; the manuscript prose describing its substituent conflicts with its other structure evidence.",
        "Meta-dimethylaminophenyl quinoxaline; agrees with GV5.",
        "https://www.rcsb.org/structure/6HVI",
        "PDB 6HVI, chemical component GV5",
    ),
    52: (
        7,
        "Results and Discussion; paragraph on indole N-substitution",
        "Compound 52 changes the indole N-methyl group to N-ethyl.",
        "N-ethylindole quinoxaline.",
        None,
        None,
    ),
    57: (
        7,
        "Results and Discussion; paragraph on indole N-substitution",
        "Compound 57 changes the indole N-methyl group to N-difluoromethyl.",
        "N-difluoromethylindole quinoxaline.",
        None,
        None,
    ),
    58: (
        7,
        "Results and Discussion; paragraph on distal-ring planarity",
        "Compound 58 carries a dihydrofuran fused ring.",
        "Dihydrobenzofuran-substituted quinoxaline.",
        None,
        None,
    ),
    59: (
        7,
        "Results and Discussion; paragraph on distal-ring planarity",
        "Compound 59 carries a fused 1,4-dioxine ring.",
        "Saturated two-carbon 1,4-dioxine-derived fused ring on quinoxaline.",
        None,
        None,
    ),
    60: (
        7,
        "Results and Discussion; paragraph on distal-ring planarity",
        "Compound 60 carries a 3,3-dimethyl dihydrofuran fused ring.",
        "3,3-dimethyl dihydrobenzofuran-substituted quinoxaline.",
        None,
        None,
    ),
    62: (
        8,
        "Results and Discussion; first paragraph after Table 2",
        "Compound 62 carries a benzoxadiazole ring.",
        "Benzoxadiazole-substituted quinoxaline.",
        None,
        None,
    ),
    63: (
        8,
        "Results and Discussion; first paragraph after Table 2",
        "Compound 63 carries a benzothiadiazole ring.",
        "Benzothiadiazole-substituted quinoxaline.",
        None,
        None,
    ),
    67: (
        8,
        "Results and Discussion; paragraph on 2-substituted benzothiazoles",
        "Compound 67 adds a 2-amino group to the benzothiazole series.",
        "2-aminobenzothiazole-substituted quinoxaline.",
        None,
        None,
    ),
    68: (
        8,
        "Results and Discussion; paragraph replacing benzothiazole",
        "Compound 68 swaps the 2-aminobenzothiazole ring for a benzothiophene ring.",
        "2-aminobenzothiophene-substituted quinoxaline.",
        None,
        None,
    ),
    69: (
        8,
        "Results and Discussion; paragraph on 3-methyl benzothiophene",
        "Compound 69 carries 3-methylbenzothiophene; the publisher abstract gives its full systematic name.",
        "3-methylbenzothiophene and 4-methylsulfonyl-3-pyridylamino quinoxaline.",
        PATENT_URL,
        "Patent Example 110 independently names the same chemical graph",
    ),
    70: (
        8,
        "Results and Discussion; benzofuran paragraph and Figure 7",
        "Compound 70 is the corresponding benzofuran and is crystallized as PDB 6HVJ.",
        "3-methylbenzofuran quinoxaline; agrees with GV8.",
        "https://www.rcsb.org/structure/6HVJ",
        "PDB 6HVJ, chemical component GV8",
    ),
}

DIRECT_LIMIT = (
    "Structure-specific primary evidence supports this number; assay state, "
    "prepared-state equivalence, and comparison eligibility remain unverified."
)
MOTIF_LIMIT = (
    "The primary text names this motif or relationship, but an individual "
    "atom-resolved paper/SI structure check remains outstanding."
)
UNVERIFIED_LIMIT = (
    "No individual primary-paper structure match is established by this receipt."
)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _load(path: Path, max_bytes: int) -> tuple[dict, bytes]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > max_bytes
        ):
            raise ValueError("invalid_receipt_file")
        raw = stream.read(max_bytes + 1)
        after = os.fstat(stream.fileno())

    def identity(s):
        return (s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns, s.st_size)

    if len(raw) != before.st_size or identity(before) != identity(after):
        raise ValueError("receipt_changed_during_read")
    document = json.loads(
        raw,
        object_pairs_hook=_unique_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
    )
    if type(document) is not dict:
        raise ValueError("receipt_object_required")
    return document, raw


def _source_sdfs(inventory_path: Path) -> dict[str, dict]:
    document, raw = _load(inventory_path, INVENTORY_BYTES)
    if (
        len(raw) != INVENTORY_BYTES
        or hashlib.sha256(raw).hexdigest() != INVENTORY_SHA256
    ):
        raise ValueError("pinned_inventory_bytes_changed")
    if document.get("source", {}).get("commit") != COMMIT:
        raise ValueError("pinned_inventory_commit_changed")
    result = {}
    for item in document["files"]:
        if item["kind"] == "sdf":
            ident = item["ligand_id"]
            if ident in result:
                raise ValueError("duplicate_inventory_sdf")
            result[ident] = item
    if set(result) != {f"lig_{number}" for number in IDS}:
        raise ValueError("inventory_sdf_set_changed")
    return result


def expected_receipt(inventory_path: Path = INVENTORY) -> dict:
    """Build the frozen expected claims from code constants and pinned local inventory."""
    sdfs = _source_sdfs(inventory_path)
    records = []
    for number in IDS:
        ident = f"lig_{number}"
        item = sdfs[ident]
        path = f"data/2020-07-06_pfkfb3/02_ligands/{ident}/crd/{ident}.sdf"
        if item["path"] != path:
            raise ValueError("inventory_sdf_path_changed")
        if number in DIRECT:
            grade, limit = "direct_primary_anchor", DIRECT_LIMIT
        elif number in MOTIF:
            grade, limit = "primary_text_motif_match", MOTIF_LIMIT
        else:
            grade, limit = "unverified", UNVERIFIED_LIMIT
        statement = EVIDENCE.get(number)
        primary = (
            None
            if statement is None
            else {
                "manuscript_url": MANUSCRIPT_URL,
                "manuscript_page": statement[0],
                "sentence_locator": statement[1],
                "structure_description": statement[2],
                "additional_primary_url": statement[4],
                "additional_primary_locator": statement[5],
            }
        )
        records.append(
            {
                "ligand_id": ident,
                "evidence_grade": grade,
                "official_sdf": {
                    "repository_path": path,
                    "sha256": item["lfs_oid_sha256"],
                    "bytes": item["lfs_size_bytes"],
                },
                "primary_evidence": primary,
                "observed_sdf_structure": None if statement is None else statement[3],
                "interpretation_limit": limit,
            }
        )
    return {
        "schema_version": "pfkfb3_openff_primary_structure_crosswalk_v1",
        "status": "SOURCE_ONLY_PARTIAL_PRIMARY_STRUCTURE_CROSSWALK_BLOCKED",
        "sources": {
            "openff_commit": COMMIT,
            "openff_inventory_sha256": INVENTORY_SHA256,
            "primary_paper_doi": DOI,
            "author_posted_accepted_manuscript_url": MANUSCRIPT_URL,
            "publisher_url": PUBLISHER_URL,
            "publisher_supplement_filename": "cmdc201800569-sup-0001-misc_information.pdf",
            "supplement_download_observation": "HTTP_403_FORBIDDEN_2026-09-29",
            "patent_url_for_separate_example_numbering": PATENT_URL,
            "openff_ligands_yml_per_ligand_comment_fields": 0,
        },
        "boundary": {
            "source_only": True,
            "experimental_values_recorded": False,
            "source_bytes_bundled": False,
            "external_sources_rechecked_by_static_verifier": False,
            "paper_or_sdf_rechecked_by_static_verifier": False,
            "all_40_primary_structures_verified": False,
            "prepared_state_equivalence_verified": False,
            "comparison_eligible": False,
        },
        "counts": {
            "candidate_count": 40,
            "direct_primary_anchor_count": 4,
            "primary_text_motif_match_count": 14,
            "unverified_count": 22,
        },
        "local_manuscript_discrepancies": [
            "The manuscript's compound 20/38 substituent prose conflicts with its synthesis and crystallographic anchors; do not generalize this local discrepancy.",
            "One paragraph calls para-bromophenyl compound 43; the pinned lig_43 SDF is meta-bromophenyl and lig_44 is para-bromophenyl. Treat this as a possible local prose numbering error; neither row is promoted here.",
        ],
        "records": records,
    }


def verify(path: Path = MANIFEST, inventory_path: Path = INVENTORY) -> dict:
    actual, _ = _load(path, MAX_BYTES)
    expected = expected_receipt(inventory_path)

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    if canonical(actual) != canonical(expected):
        raise ValueError("primary_structure_crosswalk_receipt_mismatch")
    return {
        "status": "PASS_STATIC_PRIMARY_STRUCTURE_CROSSWALK_PARTIAL_BLOCKED",
        **expected["counts"],
        "external_sources_rechecked_by_static_verifier": False,
        "paper_or_sdf_rechecked_by_static_verifier": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=MANIFEST)
    args = parser.parse_args()
    print(json.dumps(verify(args.path), sort_keys=True))


if __name__ == "__main__":
    main()

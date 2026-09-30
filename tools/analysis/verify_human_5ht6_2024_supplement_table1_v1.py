"""Verify a bounded Table S1 occurrence transcription against retained source bytes.

No PDF is bundled. This command fails if the caller-pinned source or receipts are
absent or changed; a CI job without them cannot claim source verification. It
does not parse retention values, create chemical graphs, or assign dataset roles.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile


SCHEMA = "human_5ht6_2024_supplement_table1_occurrences/1"
DOI = "10.3390/ijms251910287"
ARCHIVE_SIZE = 16820378
ARCHIVE_SHA = "f27fbee99054e7b3d866e1e46164961758d4c5fd3c031e871aff9c454f3a8363"
LAYOUT_SIZE = 15086
LAYOUT_SHA = "b85979e353b171ad0961b80973600bca8c433f499da6dbdcc4e94c99dec3774a"
MEMBERS = {
    "SI_biological_research.pdf": (3548804, "425159e0da28fca8f3074e452c50a99c662230918be54c30660a3428606fb093"),
    "SI_synthesis.pdf": (14617785, "0f0714a7cade0f6f9715ecab40f268caaefeb730b8f9d59b83bd82bce5094894"),
    "SI_Table1.pdf": (545203, "d4998be58c84f82a42291db53370620caa313c7431f5fabf7f0a4194e3e65f8d"),
}
INPUTS = {
    "supplement_access": ("docs/evidence/human_5ht6_2024_supplement_access_v1.json", 1858, "c0727e764f69a6ae436bcaf78d732343f2d75135e34e9180e93c097ef419987e"),
    "supplement_review": ("docs/evidence/human_5ht6_2024_supplement_review_v1.json", 18686, "7cceca45b8d899d0a001b5a1e7ed71b68914fa75078713790ec1d551b05b30ad"),
    "supplement_review_document": ("docs/research/human_5ht6_2024_supplement_review_20260930.md", 6358, "12046558f50371de2950e0b5877a687dc3c429d72c694c813f4b66382338d494"),
    "earlier_occurrence_contract": ("docs/evidence/human_5ht6_2024_occurrence_contract_v1.json", 31266, "55fab87416d876a0ffd24313446590a5d2e1b0d775b3f7389d4b321c4b2292cc"),
    "earlier_occurrences": ("docs/evidence/human_5ht6_2024_occurrences_v1.json", 154330, "6261d248b41d68a4754ea800b1a577c2de1442846b54c17b16e0a2fc1740dd64"),
    "earlier_identity_receipt": ("docs/evidence/human_5ht6_2024_identity_manifest_v1.json", 9067, "d7a82bacb00c18f27cbf82cae393422bc4e8be0f0c2ac2f33b0abf18a9a4067e"),
}
LITERAL_SIZE = 84617
LITERAL_SHA = "14ea7c3d094b233e9e81b7404de31cc09099b04f3f8b65f4e27da8aa3101374f"
NUMBERED = [
    "PR 68", "PR 73", "PR 71", "PR 77", "PR 9", "PR 41", "PR 17", "PR 11", "PR 47", "PR 54",
    "PR 19", "PR 42", "PR 44", "PR 75", "PR 58", "PR 61", "PR 53", "PR 51", "PR 66", "PR 74",
    "PR8", "PR109", "PR 30", "PR 21", "PR 14", "PR 31", "PR 33", "PR 37", "PR 48", "PR 56",
    "PR 59", "PR 62", "PR 70", "PR 18", "PR 24", "PR 25", "PR 60", "PR 23", "PR 50", "PR 72",
    "Venlafaxine", "Mirtazapine", "Amitriptyline", "Desipramine", "Mianserin",
]
CALIBRATION = {
    "C18": (51, ["Theophylline", "Benzimidazole", "Colichicine", "Acetophenone", "Indole", "Propiophenone", "Butyrophenone", "Valerophenone"]),
    "IAM": (59, ["Paracetamol", "Acetanilidine", "Acetophenone", "Propiohenone", "Butyrophenone", "Valerophenone", "Hexanophenone", "Heptanophenone", "Octanophenone"]),
    "HSA": (68, ["Paracetamol", "Nizatidine", "Trimetoprim", "Carbamazepine", "Propranolol", "Nicardipine", "Warfarin", "Diclofenac", "Indometacin"]),
}
ENDPOINT_SLICES = [("C18_pH_2.6", 28, 67), ("C18_pH_7.4", 67, 103), ("C18_pH_10.5", 103, 148), ("IAM", 148, 187), ("HSA", 187, None)]
HEADERS = ["C18 at pH 2.6", "C18 at pH 7.4", "C18 at pH 10.5", "IAM", "HSA"]
ADDITIONAL_NAMES = ["Venlafaxine", "Mirtazapine", "Amitriptyline", "Desipramine", "Mianserin", "Trimetoprim", "Propranolol"]
COUNTS = {
    "physical_row_occurrences": 71, "numbered_rows": 45, "calibration_rows": 26,
    "numbered_study_label_rows": 40, "numbered_comparison_drug_rows": 5,
    "prior_PR1_PR78_label_matches": 39, "unresolved_PR109_rows": 1,
    "calibration_rows_by_block": {"C18": 8, "IAM": 9, "HSA": 9},
    "name_display_spans": 89, "numbered_rows_with_HSA_numeric_content": 25,
    "numbered_rows_with_HSA_blank_group": 20,
    "new_numeric_human_5HT6_Ki_rows_transcribed": 0,
    "new_independent_human_5HT6_Ki_observations_credited": 0,
    "independent_measurement_denominator": None,
}
BOUNDARY = {
    "additive_only": True, "earlier_205_occurrence_contract_preserved": True,
    "earlier_123_literal_manifest_preserved": True, "numeric_retention_values_transcribed": False,
    "numeric_chromatography_to_Ki_conversion": False, "graph_nodes_emitted": 0,
    "graph_inclusion": "unknown_pending_separate_policy_review", "assigned_role": None,
    "new_assay_rows_admitted": 0, "new_training_admission": 0,
    "new_calibration_admission": 0, "new_independent_evaluation_admission": 0,
    "independent_measurement_denominator": None, "new_independent_source_component_established": False,
    "protected_fresh128_touched": False, "protected_context_opened": False,
    "new_preflight_executed": False, "fit_or_model_change": False,
    "full_source_clearance": False, "scientifically_qualified": False,
}
EXCEPTIONS = {
    "PR109": {"numbered_row": 22, "printed_name": "PR109", "status": "unresolved_local_label", "mapped_to_other_PR_label": False},
    "PR49": {"found_in_numbered_name_column": False, "absence_is_measurement": False},
    "PR59": {"numbered_row": 31, "printed_name": "PR 59", "C18_and_IAM_numeric_content_present": True, "HSA_group": "blank", "blank_to_zero_conversion": False},
    "seven_additional_names_vs_prior_literal_manifest": ADDITIONAL_NAMES,
    "additional_name_status": "literal_occurrences_only_not_verified_chemical_identities",
    "spelling_variants": [
        {"printed_name": "Colichicine", "prior_literal_lead": "colchicine", "aliases_merged": False},
        {"printed_name": "Acetanilidine", "prior_literal_lead": "acetanilide", "aliases_merged": False},
        {"printed_name": "Propiohenone", "prior_literal_lead": "propiophenone", "aliases_merged": False},
        {"printed_name": "Octanophenone", "prior_literal_lead": "octanonophenone", "aliases_merged": False},
    ],
    "PR8": {"numbered_row": 21, "printed_name": "PR8", "whitespace_only_label_lookup": "PR8", "chemical_equivalence_established": False},
    "prior_other_target_PR78_vs_main_Table6_PR77": {"review_receipt_only": True, "status": "unresolved_correspondence", "relabeling_performed": False},
}
CURVE_SCOPE = {
    "source": "pinned supplement_review receipt only; no biological curve transcription in this sidecar",
    "printed_5HT6_binding_curve_label_count": 78,
    "count_is_independent_Ki_denominator": False,
    "new_independent_numeric_Ki_rows_credited": 0,
    "independent_measurement_denominator": None,
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key:" + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite_json_constant:" + value)

    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    require(isinstance(result, dict), "json_root_not_object")
    return result


def pinned(path: Path, size: int, expected: str) -> bytes:
    require(path.is_file(), "required_source_absent:" + str(path))
    require(path.stat().st_size == size, "source_size_mismatch:" + str(path))
    raw = path.read_bytes()
    require(sha(raw) == expected, "source_sha_mismatch:" + str(path))
    return raw


def span(line: bytes, start: int, text: str, kind: str) -> dict:
    raw = text.encode("ascii")
    require(line[start:start + len(raw)] == raw, "printed_span_mismatch:" + text)
    return {"kind": kind, "printed_text": text, "start_byte_1based": start + 1,
            "end_byte_1based_inclusive": start + len(raw), "sha256": sha(raw)}


def endpoint_definitions(lines: list[bytes]) -> list[dict]:
    result = []
    for (key, start, end), header in zip(ENDPOINT_SLICES, HEADERS):
        owner = "C18" if key.startswith("C18_") else key
        result.append({
            "id": key, "printed_header": header, "header_layout_LF_line_1based": 1,
            "header_span": span(lines[0], lines[0].index(header.encode()), header, "endpoint_header"),
            "layout_numeric_group_slice_0based_half_open": [start, end],
            "stationary_phase_or_column": owner,
            "chromatography_pH_as_printed": key.split("_pH_")[1] if owner == "C18" else None,
            "endpoint_family": "chromatography_retention_and_derived_indices",
            "reported_column_headers": ["t1", "t2", "t3", "tm", "SD", "CHI C18"] if owner == "C18" else
                (["t1", "t2", "t3", "tm", "SD", "CHI IAM"] if owner == "IAM" else
                 ["t1", "t2", "t3", "tm", "SD", "log(t)", "logKHSA", "%HSA"]),
            "receptor_target": None, "species": None, "receptor_assay_pH": None,
            "binding_Ki_equivalence": False,
        })
    return result


def derive_rows(raw: bytes, manifest: dict) -> list[dict]:
    require(len(raw) == LAYOUT_SIZE and sha(raw) == LAYOUT_SHA, "layout_bytes_mismatch")
    lines = raw.split(b"\n")  # Form feed remains the final byte line; do not use splitlines().
    require(len(lines) == 77 and lines[76] == b"\x0c", "layout_LF_line_count_mismatch")
    require(lines[49].strip() == b"Calibration SET", "calibration_boundary_mismatch")
    studies = {row["printed_label"] for row in manifest["study_compounds"]}
    others = {row["literal_entity"].casefold() for row in manifest["other_literal_entities"]}
    require(len(studies) == 78 and len(others) == 45, "earlier_literal_manifest_count_mismatch")
    require(not any(name.casefold() in others for name in ADDITIONAL_NAMES), "additional_name_prior_match_changed")
    result = []
    specs = [(i + 5, "numbered", i + 1, name) for i, name in enumerate(NUMBERED)]
    for block, (first, names) in CALIBRATION.items():
        specs.extend((first + i, "calibration_" + block, i + 1, name) for i, name in enumerate(names))
    for line_number, group, row_number, name in specs:
        line = lines[line_number - 1]
        require(line[10:28].strip().decode("ascii") == name, "printed_name_mismatch:" + str(line_number))
        displays = [span(line, 10, name, "primary_name_column")]
        numbered = group == "numbered"
        if numbered:
            require(int(re.match(rb"\s*(\d+)\s", line).group(1)) == row_number, "numbered_row_mismatch")
        elif group != "calibration_C18":
            repeated = name if group == "calibration_IAM" else name.lower()
            displays.append(span(line, 133, repeated, "repeated_name_display_same_physical_row"))
        label = re.sub(r"\s", "", name) if numbered and row_number <= 40 else None
        match = "same_local_label_present" if label in studies else ("local_label_absent" if label else
                ("casefold_literal_present" if name.casefold() in others else "casefold_literal_absent"))
        contexts = []
        for key, start, end in ENDPOINT_SLICES:
            in_block = numbered or (group == "calibration_C18" and key.startswith("C18_")) or group == "calibration_" + key
            segment = line[start:end]
            numeric = bool(re.search(rb"\d", segment))
            require(in_block or not numeric, "numeric_content_outside_row_block:" + str(line_number))
            contexts.append({"endpoint_id": key, "owned_by_row_block": in_block,
                             "numeric_content_present": numeric,
                             "cell_group_status": ("numeric_content_present" if numeric else "blank") if in_block else "not_in_row_block",
                             "individual_numeric_cells_transcribed": False,
                             "all_replicate_cells_complete_established": False})
        result.append({
            "occurrence_id": "supplement_table1:" + group + ":" + str(row_number),
            "occurrence_unit": "physical_table_row", "source_member": "SI_Table1.pdf",
            "physical_pdf_page_1based": 1, "row_group": group, "row_in_group_1based": row_number,
            "printed_row_number": row_number if numbered else None,
            "printed_name": name, "source_local_label_after_whitespace_removal": label,
            "name_kind": ("study_literal_label" if row_number <= 40 else "comparison_drug_name") if numbered else "calibration_standard_name",
            "layout_LF_line_1based": line_number, "layout_line_bytes_excluding_LF": len(line),
            "layout_line_sha256": sha(line), "name_display_spans": displays,
            "endpoint_contexts": contexts, "prior_literal_manifest_lookup": match,
            "lookup_basis": "study-label whitespace only; other-name casefold only; no chemical equivalence or alias merge",
            "chemical_identity_verified": False, "assayed_microstate_verified": False,
            "assigned_role": None, "graph_inclusion": "unknown", "admitted": False,
            "human_5HT6_Ki_measurement": False, "new_independent_measurement_credited": False,
        })
    return result


def verify(args) -> dict:
    require(re.fullmatch(r"[0-9a-f]{64}", args.expected_sidecar_sha256) is not None, "caller_sidecar_sha_required")
    require(args.sidecar.is_file() and args.sidecar.stat().st_size <= 524288, "sidecar_absent_or_oversize")
    sidecar_raw = args.sidecar.read_bytes()
    require(sha(sidecar_raw) == args.expected_sidecar_sha256, "caller_sidecar_sha_mismatch")
    sidecar = strict_json(sidecar_raw)
    require(sidecar["schema_id"] == SCHEMA and sidecar["source_doi"] == DOI, "wrong_schema_or_doi")
    require(sidecar["counts"] == COUNTS and sidecar["boundary"] == BOUNDARY, "count_or_boundary_promotion")
    require(sidecar["semantic_exceptions"] == EXCEPTIONS and sidecar["biological_curve_count_only"] == CURVE_SCOPE,
            "review_exception_or_curve_scope_mismatch")
    captured = {}
    for key, (relative, size, expected) in INPUTS.items():
        require(sidecar["inputs"][key] == {"path": relative, "bytes": size, "sha256": expected}, "input_pin_declaration_mismatch:" + key)
        captured[key] = pinned(args.repo_root / relative, size, expected)
    require(sidecar["inputs"]["retained_archive"]["sha256"] == ARCHIVE_SHA and
            sidecar["inputs"]["retained_archive"]["bytes"] == ARCHIVE_SIZE, "archive_pin_declaration_mismatch")
    require(sidecar["inputs"]["retained_literal_manifest"]["sha256"] == LITERAL_SHA and
            sidecar["inputs"]["retained_literal_manifest"]["bytes"] == LITERAL_SIZE, "literal_pin_declaration_mismatch")
    access = strict_json(captured["supplement_access"])
    review = strict_json(captured["supplement_review"])
    require(access["source_doi"] == DOI and access["archive"]["sha256"] == ARCHIVE_SHA, "access_receipt_archive_mismatch")
    require(review["source_doi"] == DOI and review["inputs"]["supplement_access"]["sha256"] == INPUTS["supplement_access"][2], "review_receipt_access_mismatch")
    archive_raw = pinned(args.archive, ARCHIVE_SIZE, ARCHIVE_SHA)
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        require(len(archive.infolist()) == 3 and set(archive.namelist()) == set(MEMBERS), "archive_members_mismatch")
        require(archive.testzip() is None, "archive_crc_mismatch")
        pdf = None
        for name, (size, expected) in MEMBERS.items():
            member = archive.read(name)
            require(len(member) == size and sha(member) == expected and member.startswith(b"%PDF"), "member_pin_mismatch:" + name)
            if name == "SI_Table1.pdf":
                pdf = member
    require(shutil.which("pdftotext") is not None, "pdftotext_unavailable")
    process = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=True, timeout=30)
    version = subprocess.run(["pdftotext", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             check=True, timeout=10).stderr.decode("utf-8").splitlines()[0]
    layout = process.stdout
    manifest = strict_json(pinned(args.literal_manifest, LITERAL_SIZE, LITERAL_SHA))
    require(sidecar["occurrences"] == derive_rows(layout, manifest), "typed_occurrences_do_not_match_source")
    require(sidecar["endpoint_definitions"] == endpoint_definitions(layout.split(b"\n")), "endpoint_definition_mismatch")
    require(sidecar["extraction"]["layout_sha256"] == LAYOUT_SHA and sidecar["extraction"]["layout_bytes"] == LAYOUT_SIZE,
            "layout_pin_declaration_mismatch")
    return {
        "schema_id": "human_5ht6_2024_supplement_table1_verification/1",
        "verification_status": "PASS_bounded_source_bytes_and_typed_rows",
        "source_pdf_present": True, "archive_crc_valid": True,
        "archive_sha256": ARCHIVE_SHA, "table1_member_sha256": MEMBERS["SI_Table1.pdf"][1],
        "layout_sha256": LAYOUT_SHA, "extractor_observed_version": version,
        "caller_pinned_sidecar_sha256": sha(sidecar_raw), "verifier_sha256": sha(Path(__file__).read_bytes()),
        "receipt_inputs_sha256": {key: sha(raw) for key, raw in captured.items()},
        "retained_literal_manifest_sha256": LITERAL_SHA,
        "counts": COUNTS, "boundary": BOUNDARY,
        "actual_paths": {"sidecar": str(args.sidecar), "repo_root": str(args.repo_root),
                         "archive": str(args.archive), "literal_manifest": str(args.literal_manifest)},
        "validation_scope": "Local byte/row/header/presence binding only; visual review, rights and chemical/assay eligibility are not newly verified by this script.",
        "hosted_CI_source_verification_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-sidecar-sha256", required=True)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--literal-manifest", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(json.dumps({"verification_status": "FAIL_closed", "source_verification_established": False,
                          "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

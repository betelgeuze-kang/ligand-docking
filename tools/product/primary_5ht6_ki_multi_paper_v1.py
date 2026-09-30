"""Verify a bounded, research-only human 5-HT6 Ki paper intake.

The five PDFs and ledger are exact byte inputs. The optional joint screen reads
only a caller-supplied, hash-bound identity metadata context. Neither route
opens outcome files, assigns a source role, or prepares a ligand.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from betelgeuze_product import public_assay_components as components
from betelgeuze_product import public_assay_graph_diagnostic as diagnostic
from betelgeuze_product import public_assay_preflight as preflight
from tools.product.public_assay_dataset import chemical_identity


SCHEMA = "primary_human_5ht6_ki_multi_paper_source_ledger_v1"
RECEIPT_SCHEMA = "primary_human_5ht6_ki_multi_paper_verification_v1"
PINNED_LEDGER_SHA256 = "e5b5af4caa0e4efa3e5e3a502236357276051044431f45bda77b8b5163ca0452"
MAX_LEDGER_BYTES = 128 * 1024
MAX_PDF_BYTES = 16 * 1024 * 1024
PDFS = {
    "10.3390/molecules22122221": ("587fc617390edebfef7fd05414e13fdc246a464d08408a4a31c1efa35daad1b3", 9685822),
    "10.3390/molecules28031108": ("2d3c5dc362370879d2693ff1d99ee1f4a1b9fd920715e94a6b2b9e07e63bca4e", 11145467),
    "10.3390/molecules28031096": ("7fd0054bcfd1acbd5eb59c145f2f23dd2666d62dbdf1ad4f433332c83881a260", 7707916),
    "10.3390/ijms251910287": ("4bd52d8bbb3c216b3d6976d17584a2d00b6608643df50278b80e7b94f4ab02ca", 7957708),
    "10.3390/biom13010012": ("beae8647ae1a6cfda6ed7e91673ad86384c55f22f8c794bb4d70e630e0f90d40", 2614808),
}
EXPECTED_LABELS = {
    "10.3390/molecules22122221": (("44a", "4.53", "µM"), ("44b", "1.97", "µM"),
        ("44c", "1.77", "µM"), ("46a", "0.19", "µM"), ("46b", "0.71", "µM"),
        ("46c", "2.45", "µM")),
    "10.3390/molecules28031108": (("2", "21", "nM"), ("3", "13", "nM"),
        ("4", "41", "nM"), ("5", "108", "nM")),
    "10.3390/molecules28031096": (("8", "11", "nM"), ("9", "6", "nM"),
        ("10", "84", "nM"), ("11", "17", "nM"), ("12", "556", "nM")),
    "10.3390/biom13010012": (("3a", "6", "nM"), ("3b", "7", "nM"),
        ("3c", "10", "nM"), ("3d", "87", "nM"), ("3e", "2", "nM"),
        ("3f", "1", "nM"), ("3g", "1", "nM"), ("3h", "4", "nM"),
        ("3i", "977", "nM"), ("3j", "918", "nM"),
        ("3k", "32", "nM"), ("3l", "1175", "nM")),
    "10.3390/ijms251910287": (("PR49", "0.077", "µM"),
        ("PR58", "0.172", "µM"), ("PR59", "1.964", "µM")),
}
EXPECTED_GRAPH_KEYS = {
    "10.3390/molecules22122221": (
        "TWABTBZJPRUUNH-UHFFFAOYSA-N", "VDVAKXREAFXXMM-UHFFFAOYSA-N",
        "BRCDNWOOZUUKMT-UHFFFAOYSA-N", "DBPXMXJCGXIYMZ-UHFFFAOYSA-N",
        "GOUZRHBNOBNWLY-UHFFFAOYSA-N", "MLSXXAAHSBIJBL-UHFFFAOYSA-N"),
    "10.3390/molecules28031108": (
        "MDXHLQNOYUMLOM-UHFFFAOYSA-N", "MTJKIXJSTBPNKR-UHFFFAOYSA-N",
        "FDDWBYRVXLUYQU-UHFFFAOYSA-N", "COVZWSKBXOCVHJ-UHFFFAOYSA-N"),
    "10.3390/molecules28031096": (
        "JBMVEDPXPJGTIA-WMZOPIPTSA-N", "JBMVEDPXPJGTIA-AEFFLSMTSA-N",
        "ZWMFNWTXMSTEAO-KRWDZBQOSA-N", "NSVCKGFBOYNJTE-IBGZPJMESA-N",
        "NQVPAJYKEZHKET-KRWDZBQOSA-N"),
    "10.3390/biom13010012": (
        "MGOHQJLSYXOYHL-UHFFFAOYSA-N", "ALUHYNXMSBVYAO-UHFFFAOYSA-N",
        "LFVCVBVFZKVXQP-UHFFFAOYSA-N", "OVUUGSWCEGWFIR-UHFFFAOYSA-N",
        "HMUGZARPEYRDTI-UHFFFAOYSA-N", "SEVQGZHMUFYYKQ-UHFFFAOYSA-N",
        "KVTPGEYXEBAPSU-UHFFFAOYSA-N", "VBDNDQIOSKCJSB-UHFFFAOYSA-N",
        "FYVVUNJUCLOMIX-UHFFFAOYSA-N", "OZQUGHAXWKPEAS-UHFFFAOYSA-N",
        "ZVVILMIZTGEYPV-UHFFFAOYSA-N", "KNGOAIOZJHPJEW-UHFFFAOYSA-N"),
    "10.3390/ijms251910287": (
        "QQYXUBNTHMWUNC-UHFFFAOYSA-N", "QGXGSTXGPRUKQP-UHFFFAOYSA-N",
        "PKYFJQXPMNODTI-UHFFFAOYSA-N"),
}


EXPECTED_UNCERTAINTY = {
    "10.3390/ijms251910287": (("SD", "0.018"), ("SD", "0.041"),
        ("SD", "0.452")),
    "10.3390/biom13010012": (("SEM", "1"), ("SEM", "1"),
        ("SEM", "2"), ("SEM", "12"), ("SEM", "0.8"), ("SEM", "0.2"),
        ("SEM", "0.3"), ("SEM", "0.5"), ("SEM", "43"), ("SEM", "55"),
        ("SEM", "5"), ("SEM", "99")),
}
EXPECTED_PURITY = {
    "10.3390/molecules28031108": ("100", "100", "100", "100"),
    "10.3390/molecules28031096": (">95",) * 5,
    "10.3390/ijms251910287": ("92", "99", "96"),
    "10.3390/biom13010012": (100, 100, 99, 100, 100, 99,
        100, 100, 100, 99, 100, 100),
}


def _read_regular_bounded(path: Path, limit: int) -> bytes:
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("noncanonical_source_path")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise ValueError("source_file_not_regular_or_outside_capacity")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        if (len(raw) != before.st_size or len(raw) > limit or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError("source_file_changed_during_read")
        return raw
    finally:
        os.close(fd)


def _strict_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_ledger_json_key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite_ledger_json_number")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    if type(value) is not dict:
        raise ValueError("invalid_ledger_document")
    return value


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def _check_semantics(ledger: dict) -> None:
    if ledger.get("schema_version") != SCHEMA or set(ledger) != {
            "schema_version", "sources", "rows", "rights_scope", "role_policy",
            "source_boundary"}:
        raise ValueError("invalid_source_ledger_schema")
    if (type(ledger["sources"]) is not list or len(ledger["sources"]) != 5 or
            type(ledger["rows"]) is not list or len(ledger["rows"]) != 30):
        raise ValueError("invalid_source_or_row_count")
    if set(PDFS) != {source["doi"] for source in ledger["sources"]}:
        raise ValueError("source_set_mismatch")
    for source in ledger["sources"]:
        doi = source["doi"]
        if (source["component_id"] != "doi:" + doi or
                (source["pdf_sha256"], source["pdf_byte_count"]) != PDFS[doi] or
                source["license_notice_in_pdf"] != "CC BY 4.0" or
                source["method"]["target"] != "human 5-HT6 receptor" or
                source["method"]["conversion"] not in {
                    "Cheng-Prusoff Ki", "reported Ki; detailed derivation delegated to reference 12"} or
                source["method"]["cross_paper_equivalence_verified"] is not False):
            raise ValueError("source_method_rights_or_hash_mismatch")
        if source["row_ids"] != [label[0] for label in EXPECTED_LABELS[doi]]:
            raise ValueError("source_row_set_mismatch")
    if (set(ledger["role_policy"]) != {
            "roles_frozen", "fit_rows_admitted", "calibration_rows_admitted",
            "development_rows_admitted", "independent_evaluation_rows_admitted",
            "protected_identity_and_scaffold_screen_complete",
            "complete_source_family_reviewed", "assay_method_equivalence_verified",
            "prepared_states_bound", "scientific_validation", "protected_outcomes_read"} or
            any(type(value) is not bool or value is not False
                for key, value in ledger["role_policy"].items()
                if not key.endswith("_rows_admitted")) or
            any(type(value) is not int or value != 0
                for key, value in ledger["role_policy"].items()
                if key.endswith("_rows_admitted"))):
        raise ValueError("source_role_authority_promoted")
    rows = defaultdict(list)
    graph_keys = set()
    for row in ledger["rows"]:
        doi = row["source_component_id"].removeprefix("doi:")
        if doi not in PDFS or row["source_component_id"] != "doi:" + doi:
            raise ValueError("unknown_row_source_component")
        measure = row["reported_ki"]
        if (measure["relation"] != "=" or type(measure["value"]) is not str or
                type(measure["unit"]) is not str or
                not Decimal(measure["value"]).is_finite() or
                Decimal(measure["value"]) <= 0 or
                row["assigned_role"] is not None or
                row["fit_admitted"] is not False or
                row["prepared_state_origin"] is not None):
            raise ValueError("source_measurement_or_role_invalid")
        if doi == "10.3390/ijms251910287":
            uncertainty = measure["uncertainty"]
            if (type(uncertainty) is not dict or uncertainty.get("kind") != "SD" or
                    Decimal(uncertainty["value"]) <= 0):
                raise ValueError("reported_sd_invalid")
        elif doi == "10.3390/biom13010012":
            uncertainty = measure["uncertainty"]
            if (type(uncertainty) is not dict or uncertainty.get("kind") != "SEM" or
                    Decimal(uncertainty["value"]) <= 0):
                raise ValueError("reported_sem_invalid")
        elif measure["uncertainty"] is not None:
            raise ValueError("invented_per_row_uncertainty")
        graph = row["proposed_neutral_graph"]
        if (graph["status"] != "proposed_from_paper_name_and_drawing" or
                graph["assayed_microstate_verified"] is not False or
                graph["source_graph_mapping_verified"] is not False):
            raise ValueError("source_graph_authority_promoted")
        mol = Chem.MolFromSmiles(graph["canonical_isomeric_smiles"])
        if (mol is None or Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
                != graph["canonical_isomeric_smiles"] or
                rdMolDescriptors.CalcMolFormula(mol) != graph["formula"] or
                Chem.MolToInchiKey(mol) != graph["inchikey"] or
                Chem.GetFormalCharge(mol) != graph["formal_charge"] or
                len(Chem.GetMolFrags(mol)) != graph["fragment_count"] or
                graph["fragment_count"] != 1 or graph["formal_charge"] != 0):
            raise ValueError("proposed_neutral_graph_mismatch")
        if graph["inchikey"] in graph_keys:
            raise ValueError("duplicate_proposed_graph")
        graph_keys.add(graph["inchikey"])
        rows[doi].append(row)
    for doi, expected in EXPECTED_LABELS.items():
        observed = tuple((row["paper_row_id"], row["reported_ki"]["value"],
                          row["reported_ki"]["unit"]) for row in rows[doi])
        keys = tuple(row["proposed_neutral_graph"]["inchikey"] for row in rows[doi])
        uncertainty = tuple((row["reported_ki"]["uncertainty"]["kind"],
                             row["reported_ki"]["uncertainty"]["value"])
                            for row in rows[doi]
                            if row["reported_ki"]["uncertainty"] is not None)
        purity = tuple(row["reported_purity_percent"] for row in rows[doi])
        if (observed != expected or keys != EXPECTED_GRAPH_KEYS[doi] or
                uncertainty != EXPECTED_UNCERTAINTY.get(doi, ()) or
                purity != EXPECTED_PURITY.get(doi, (None,) * len(rows[doi]))):
            raise ValueError("source_row_label_or_graph_pin_mismatch")


def verify_ledger(path: Path) -> tuple[dict, str]:
    raw = _read_regular_bounded(path, MAX_LEDGER_BYTES)
    ledger = _strict_json(raw)
    _check_semantics(ledger)
    digest = hashlib.sha256(raw).hexdigest()
    if raw != _canonical(ledger) or digest != PINNED_LEDGER_SHA256:
        raise ValueError("source_ledger_does_not_match_pinned_capture")
    return ledger, digest


def verify_pdfs(ledger: dict, paths: dict[str, Path]) -> dict[str, str]:
    if set(paths) != set(PDFS):
        raise ValueError("missing_or_extra_primary_pdf")
    observed = {}
    for source in ledger["sources"]:
        doi = source["doi"]
        raw = _read_regular_bounded(paths[doi], MAX_PDF_BYTES)
        digest = hashlib.sha256(raw).hexdigest()
        if (not raw.startswith(b"%PDF-") or len(raw) != source["pdf_byte_count"] or
                digest != source["pdf_sha256"] or digest != PDFS[doi][0]):
            raise ValueError("primary_pdf_sha256_or_size_mismatch:" + doi)
        observed[doi] = digest
    return observed


def candidate_nodes(ledger: dict) -> list[dict]:
    """Build metadata graph nodes; a proposed graph is never admission proof."""
    source_map = {source["component_id"]: source for source in ledger["sources"]}
    nodes = []
    for row in ledger["rows"]:
        source = source_map[row["source_component_id"]]
        identity = chemical_identity(row["proposed_neutral_graph"]["canonical_isomeric_smiles"])
        node_id = "paper:" + source["doi"] + ":" + row["paper_row_id"]
        nodes.append(components.node_from_raw(
            {"Article DOI": source["doi"]}, identity, node_id=node_id,
            record_id=node_id, ligand_id="",
            origin={"source_sha256": source["pdf_sha256"],
                    "source_member": "paper_table_page_" + str(row["table_page"])},
            extra_declarations=[{"role": "unassigned"}]))
    components.component_index(nodes)
    return nodes


def joint_identity_screen(ledger: dict, context_path: Path, context_sha256: str) -> dict:
    """Run the existing component policy on hash-bound identity metadata only."""
    raw = preflight.checked_bytes(context_path, context_sha256)
    if raw.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            decoded = stream.read(preflight.MAX_BYTES + 1)
        if len(decoded) > preflight.MAX_BYTES:
            raise ValueError("decoded_context_capacity_exceeded")
    else:
        decoded = raw
    context = [components.loads(line) for line in decoded.decode("utf-8").splitlines()
               if line.strip()]
    candidates = candidate_nodes(ledger)
    screen = preflight.preflight(context, candidates)
    reserved_keys, unknown_keys = set(), set()
    for node in context:
        reserved, unknown = components.node_reservation_status(node)
        if reserved or node["protected"]:
            reserved_keys.update(map(tuple, node["keys"]))
        if unknown:
            unknown_keys.update(map(tuple, node["keys"]))
    results = []
    for node, result in zip(candidates, screen["results"], strict=True):
        keys = set(map(tuple, node["keys"]))
        results.append({
            "candidate_id": node["node_id"],
            "status": result["status"],
            "identity_component_id": result["component_id"],
            "component_nodes": result["component_nodes"],
            "reserved_nodes_count": result["reserved_nodes_count"],
            "unknown_policy_nodes_count": result["unknown_policy_nodes_count"],
            "direct_reserved_key_overlap": bool(keys & reserved_keys),
            "direct_unknown_policy_key_overlap": bool(keys & unknown_keys),
            "chemical_key_available": result["identity_evidence"]["chemical_key_available"],
            "document_key_available": result["identity_evidence"]["document_key_available"],
        })
    if preflight.checked_bytes(context_path, context_sha256) != raw:
        raise ValueError("identity_context_changed_during_screen")
    witness = None
    blocked = next((row for row in results if row["status"] == "blocked_identity"), None)
    if blocked is not None:
        nodes = {node["node_id"]: node for node in context + candidates}
        by_key = defaultdict(list)
        for node_id in sorted(nodes):
            for key in sorted({tuple(key) for key in nodes[node_id]["keys"]}):
                by_key[key].append(node_id)
        path = diagnostic._witness(blocked["candidate_id"], nodes, by_key,
                                   max_visits=diagnostic.DEFAULT_MAX_WITNESS_VISITS)
        if path["status"] != "boundary_found":
            raise ValueError("blocked_component_without_complete_boundary_witness")
        witness = {
            "candidate_id": blocked["candidate_id"],
            "edge_kinds": [segment["key_kind"] for segment in path["segments"]],
            "hops": len(path["segments"]),
            "boundary_reasons": path["boundary_reasons"],
            "witness_sha256": hashlib.sha256(components.canonical(path).encode()).hexdigest(),
            "scope": "shortest typed metadata path in the supplied graph; no chemical equivalence conclusion",
        }
    return {
        "policy": components.POLICY,
        "screen_schema": preflight.SCHEMA,
        "context_sha256": context_sha256,
        "candidate_nodes_sha256": components.node_set_sha(candidates),
        "context_nodes": len(context),
        "status_counts": dict(sorted(Counter(row["status"] for row in results).items())),
        "candidate_results": results,
        "representative_blocked_witness": witness,
        "protected_outcomes_read": False,
        "complete_family_clearance": False,
        "source_roles_assigned": False,
    }


def verify_bundle(ledger_path: Path, pdf_paths: dict[str, Path], *,
                  context_path: Path | None = None, context_sha256: str | None = None) -> dict:
    ledger, ledger_sha256 = verify_ledger(ledger_path)
    pdf_hashes = verify_pdfs(ledger, pdf_paths)
    if (context_path is None) != (context_sha256 is None):
        raise ValueError("context_path_and_sha256_required_together")
    screen = (joint_identity_screen(ledger, context_path, context_sha256)
              if context_path is not None else None)
    return {
        "schema_version": RECEIPT_SCHEMA,
        "ledger_sha256": ledger_sha256,
        "pdf_sha256_by_doi": pdf_hashes,
        "paper_count": len(ledger["sources"]),
        "source_row_count": len(ledger["rows"]),
        "exact_ki_source_rows_in_two_blocked_2023_papers": 9,
        "exact_ki_source_rows_in_alternative_2023_paper": 12,
        "joint_identity_screen": screen,
        "source_pdf_hashes_matched": True,
        "source_authenticated": False,
        "paper_to_assayed_graph_verified": False,
        "assay_method_equivalence_verified": False,
        "fit_calibration_development_or_evaluation_admitted": False,
        "independent_evaluation_established": False,
        "protected_outcomes_read": False,
        "scientifically_validated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--pdf-2017", type=Path, required=True)
    parser.add_argument("--pdf-2023-triazine", type=Path, required=True)
    parser.add_argument("--pdf-2023-pyrrolo", type=Path, required=True)
    parser.add_argument("--pdf-2024", type=Path, required=True)
    parser.add_argument("--pdf-2023-biomolecules", type=Path, required=True)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--context-sha256")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    receipt = verify_bundle(args.ledger, {
        "10.3390/molecules22122221": args.pdf_2017,
        "10.3390/molecules28031108": args.pdf_2023_triazine,
        "10.3390/molecules28031096": args.pdf_2023_pyrrolo,
        "10.3390/ijms251910287": args.pdf_2024,
        "10.3390/biom13010012": args.pdf_2023_biomolecules,
    }, context_path=args.context, context_sha256=args.context_sha256)
    payload = _canonical(receipt)
    if args.receipt is not None:
        with args.receipt.open("xb") as stream:
            stream.write(payload)
    print(payload.decode().rstrip("\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

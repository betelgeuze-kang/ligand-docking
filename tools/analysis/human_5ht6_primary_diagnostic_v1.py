"""Reproduce a retrospective, source-bound 5-HT6 diagnostic; never admission.

Published labels were seen before this diagnostic was planned. The frozen model
and its original mean are replayed without fitting. The cited Table 1 reference
participates in the identity graph, but is not counted as a new experiment.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

from rdkit import Chem, rdBase

from betelgeuze_engine.product import public_assay_selector_shadow as shadow
from betelgeuze_engine.product import public_assay_streaming as streaming
from betelgeuze_product import public_assay_components as components
from betelgeuze_product import public_assay_graph_diagnostic as graph_diagnostic
from betelgeuze_product import public_assay_preflight as preflight
from tools.product import primary_5ht6_ki_multi_paper_v1 as paper
from tools.product.public_assay_dataset import chemical_identity

SCHEMA = "human_5ht6_primary_retrospective_diagnostic_v1"
CHECKPOINT_SHA256 = "818f2b324f5b1e1c5e17aaf68de791edf9dfb3476dbffce1177cb3cb08ba1dea"
PLAN_SHA256 = "326ac102ab6763e2953d5528274e2c541afdfded4c6bd93a08ad7878d0e74b73"
CONTEXT_SHA256 = "7345f148051c04f5fdfaa12be1abf7ad81cbf96409bbaaf96d57ce8644d52519"
BIOM_DOI = "10.3390/biom13010012"
REFERENCE_ID = "paper:" + BIOM_DOI + ":SB-258585-cited-reference"
SOURCE_FILES = {
    "biom13010012-s001.zip": (3273743, "57fdb4cfc9f52391fa3770daf4799d68db98f3dbb5a0e59f223a8e62bcb55f74"),
    "biom13010012-supplementary.pdf": (3586798, "5b34bf7db08a28bf27cf4f151d116b05ccbdb6cf43b0253ec4fb9bc38a6ce19e"),
    "sb258585-pubchem-properties.json": (262, "376c75688a3087730348870ad6fd63f8f4c73b5c15a5e955db81cb7a2c0e3a5f"),
}
PDF_NAMES = {
    "10.3390/molecules22122221": "2017.pdf",
    "10.3390/molecules28031108": "2023.pdf",
    "10.3390/molecules28031096": "2023b.pdf",
    "10.3390/ijms251910287": "2024.pdf",
    BIOM_DOI: "2023-biomolecules-alternate.pdf",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_supplement(directory: Path) -> tuple[dict, dict]:
    captured = {}
    for name, (size, expected) in SOURCE_FILES.items():
        raw = paper._read_regular_bounded(directory / name, paper.MAX_PDF_BYTES)
        if len(raw) != size or digest(raw) != expected:
            raise ValueError("supplement_or_reference_source_mismatch:" + name)
        captured[name] = raw
    with zipfile.ZipFile(io.BytesIO(captured["biom13010012-s001.zip"])) as archive:
        members = archive.infolist()
        if (len(members) != 1 or members[0].filename != "biomolecules-2094241-supplementary.pdf"
                or members[0].file_size != SOURCE_FILES["biom13010012-supplementary.pdf"][0]):
            raise ValueError("unexpected_supplement_archive_members")
        if archive.read(members[0]) != captured["biom13010012-supplementary.pdf"]:
            raise ValueError("extracted_supplement_mismatch")
    properties = paper._strict_json(captured["sb258585-pubchem-properties.json"])
    records = properties["PropertyTable"]["Properties"]
    if len(records) != 1 or records[0]["CID"] != 3248571:
        raise ValueError("wrong_cited_reference_identity")
    record = records[0]
    mol = Chem.MolFromSmiles(record["SMILES"])
    if mol is None or Chem.MolToInchiKey(mol) != "BDHMSYNBSBZCAF-UHFFFAOYSA-N":
        raise ValueError("wrong_cited_reference_graph")
    return record, {name: digest(raw) for name, raw in captured.items()}


def family_nodes(ledger: dict, reference_properties: dict) -> list[dict]:
    nodes = paper.candidate_nodes(ledger)
    nodes.append(components.node_from_raw(
        {"Article DOI": BIOM_DOI}, chemical_identity(reference_properties["SMILES"]),
        node_id=REFERENCE_ID, record_id=REFERENCE_ID, ligand_id="",
        origin={"source_sha256": paper.PDFS[BIOM_DOI][0],
                "source_member": "paper_table_page_9_reference_row"},
        extra_declarations=[{"role": "unassigned"}]))
    return nodes


def screen_family(context: list[dict], candidates: list[dict]) -> dict:
    result = preflight.preflight(context, candidates)
    # Retain a typed shortest path to distinguish a policy connection from a
    # direct chemical match. No experimental outcome is present in these nodes.
    all_nodes = {node["node_id"]: node for node in context + candidates}
    by_key = defaultdict(list)
    for node_id in sorted(all_nodes):
        for key in sorted({tuple(key) for key in all_nodes[node_id]["keys"]}):
            by_key[key].append(node_id)
    candidate_id = "paper:" + BIOM_DOI + ":3a"
    row = next(row for row in result["results"] if row["candidate_id"] == candidate_id)
    witness = graph_diagnostic._witness(
        candidate_id, all_nodes, by_key,
        max_visits=graph_diagnostic.DEFAULT_MAX_WITNESS_VISITS)
    if row["status"] == "blocked_identity" and witness["status"] != "boundary_found":
        raise ValueError("incomplete_blocked_family_witness")
    result.update(
        policy=components.POLICY,
        candidate_nodes_sha256=components.node_set_sha(candidates),
        status_counts=dict(sorted(Counter(row["status"] for row in result["results"]).items())),
        representative_biomolecules_witness={
            "candidate_id": candidate_id, "status": witness["status"],
            "edge_kinds": [segment["key_kind"] for segment in witness["segments"]],
            "hops": len(witness["segments"]),
            "witness_sha256": digest(components.canonical(witness).encode()),
            "scope": "metadata linkage only; not chemical equivalence or direct outcome leakage",
        },
        whole_article_source_family_complete=False,
        biomolecules_table1_rows_including_cited_reference_complete=True,
        protected_outcomes_read=False, roles_assigned=False)
    return result


def measurement(row: dict) -> dict:
    reported = row["reported_ki"]
    value = Decimal(reported["value"])
    if reported["relation"] != "=" or not value.is_finite() or value <= 0:
        raise ValueError("nonexact_or_invalid_ki")
    factors = {"nM": Decimal(1), "µM": Decimal(1000)}
    if reported["unit"] not in factors:
        raise ValueError("unsupported_ki_unit")
    nm = value * factors[reported["unit"]]
    return {"reported_ki": reported, "ki_nm": str(nm),
            "pki": 9.0 - math.log10(float(nm)),
            "observed_active_at_ki_le_1000nm": nm <= Decimal(1000)}


def point_metrics(rows: list[dict], key: str) -> dict:
    supported = [row for row in rows if row[key] is not None]
    if not supported:
        return {"requested": len(rows), "supported": 0, "mae": None, "rmse": None,
                "predicted_pki_range": None, "predicted_active": 0,
                "observed_inactive_predicted_active": 0}
    errors = [row[key] - row["pki"] for row in supported]
    return {"requested": len(rows), "supported": len(supported),
            "mae": math.fsum(abs(value) for value in errors) / len(errors),
            "rmse": math.sqrt(math.fsum(value * value for value in errors) / len(errors)),
            "predicted_pki_range": [min(row[key] for row in supported),
                                    max(row[key] for row in supported)],
            "predicted_active": sum(row[key] >= 6.0 for row in supported),
            "observed_inactive_predicted_active": sum(
                not row["observed_active_at_ki_le_1000nm"] and row[key] >= 6.0
                for row in supported)}


def model_diagnostic(ledger: dict, checkpoint: Path) -> dict:
    selector = shadow.load_public_assay_selector(checkpoint, expected_sha256=CHECKPOINT_SHA256)
    if rdBase.rdkitVersion != selector.metadata["rdkit_version"]:
        raise ValueError("diagnostic_rdkit_version_mismatch")
    payload = paper._strict_json(preflight.checked_bytes(checkpoint, CHECKPOINT_SHA256))
    inputs = [{"smiles": row["proposed_neutral_graph"]["canonical_isomeric_smiles"],
               "endpoint": "Ki", "target_annotation_sha256": selector.metadata["target_annotation_sha256"]}
              for row in ledger["rows"]]
    predictions = selector.predict_rows(inputs)
    rows, by_paper, scalar_errors = [], defaultdict(list), []
    for source, input_row, prediction in zip(ledger["rows"], inputs, predictions, strict=True):
        value = prediction.get("predicted_value")
        if value is not None:
            fingerprint = selector._fingerprint(input_row)
            scalar = math.fsum([float(payload["intercept"])] + [
                float(coefficient) * int(bit)
                for coefficient, bit in zip(payload["coefficients"], fingerprint, strict=True)])
            difference = abs(scalar - value)
            if difference > 1e-10:
                raise ValueError("scalar_and_product_prediction_disagree")
            scalar_errors.append(difference)
        row = {"source_component_id": source["source_component_id"],
               "paper_row_id": source["paper_row_id"],
               "source_graph_inchikey": source["proposed_neutral_graph"]["inchikey"],
               **measurement(source), "prediction_status": prediction["status"],
               "prediction_reason": prediction["reason"], "predicted_pki": value,
               "frozen_fit_mean_pki": prediction.get("mean_baseline_value"),
               "assigned_role": None, "independent_evaluation_admitted": False}
        rows.append(row)
        by_paper[source["source_component_id"]].append(row)
    per_paper = []
    for source_id, values in sorted(by_paper.items()):
        per_paper.append({"source_component_id": source_id, "requested": len(values),
                          "observed_active": sum(row["observed_active_at_ki_le_1000nm"] for row in values),
                          "observed_inactive": sum(not row["observed_active_at_ki_le_1000nm"] for row in values),
                          "observed_pki_range": [min(row["pki"] for row in values), max(row["pki"] for row in values)],
                          "frozen_ridge": point_metrics(values, "predicted_pki"),
                          "frozen_fit_mean": point_metrics(values, "frozen_fit_mean_pki")})
    return {"rows": rows, "per_paper": per_paper,
            "requested": len(rows), "predicted": len(scalar_errors),
            "observed_active": sum(row["observed_active_at_ki_le_1000nm"] for row in rows),
            "observed_inactive": sum(not row["observed_active_at_ki_le_1000nm"] for row in rows),
            "max_scalar_product_difference": max(scalar_errors, default=None),
            "scalar_check_scope": "independent dot arithmetic with the same molecular fingerprints; not chemical or scientific validation",
            "checkpoint_sha256": CHECKPOINT_SHA256, "rdkit_version": rdBase.rdkitVersion,
            "prediction_quantity": selector.metadata["prediction_quantity"],
            "new_training_runs": 0, "new_calibration_runs": 0,
            "protected_outcomes_read": False, "fresh128_opened": False,
            "independent_evaluation": False, "ranking_enabled": False,
            "customer_execution": False, "promotion_status": "NOT_PROMOTED"}


def build(ledger_path: Path, pdf_directory: Path, source_directory: Path,
          context_path: Path, checkpoint: Path, plan_path: Path) -> dict:
    plan_raw = preflight.checked_bytes(plan_path, PLAN_SHA256)
    ledger, ledger_sha = paper.verify_ledger(ledger_path)
    pdf_shas = paper.verify_pdfs(ledger, {
        doi: pdf_directory / name for doi, name in PDF_NAMES.items()})
    properties, source_shas = checked_supplement(source_directory)
    raw_context = preflight.checked_bytes(context_path, CONTEXT_SHA256)
    context = graph_diagnostic._read_context(raw_context)
    candidates = family_nodes(ledger, properties)
    screen = screen_family(context, candidates)
    screen["context_sha256"] = CONTEXT_SHA256
    result = model_diagnostic(ledger, checkpoint)
    preflight.checked_bytes(context_path, CONTEXT_SHA256)
    preflight.checked_bytes(checkpoint, CHECKPOINT_SHA256)
    preflight.checked_bytes(plan_path, PLAN_SHA256)
    return {"schema_version": SCHEMA, "source_ledger_sha256": ledger_sha,
            "primary_pdf_sha256": pdf_shas, "additional_source_sha256": source_shas,
            "plan_sha256": digest(plan_raw), "scope": "retrospective diagnostic after published labels were read",
            "identity_screen_with_cited_reference": screen,
            "source_experimental_rows": len(ledger["rows"]), "cited_reference_rows_not_experiments": 1,
            "frozen_model_diagnostic": result,
            "implementation_sha256": {module.__name__: digest(Path(module.__file__).read_bytes())
                for module in (paper, shadow, streaming, components, preflight, graph_diagnostic)},
            "producer_sha256": digest(Path(__file__).read_bytes()),
            "biomolecules_assay_correspondence": {
                "primary_pages_visually_reviewed": [4, 5, 6, 9],
                "supplement_pages_visually_reviewed": [58],
                "reported_system": "human 5-HT6 expressed in HEK293; membrane radioligand competition",
                "endpoint": "Cheng-Prusoff Ki, not cAMP Kb, IC50, or docking energy",
                "reported_uncertainty": "Table 1 mean +/- SEM; three independent binding experiments",
                "within_experiment_replicates": "triplicate at seven concentrations",
                "binding_assay_ph": None,
                "binding_assay_ph_note": "not stated in the reviewed binding protocol; pH 7.4 elsewhere refers to microsomal stability",
                "raw_binding_curves_or_replicate_values_acquired": False,
                "assayed_microstate_verified": False,
                "prepared_receptor_state_equivalence": False,
                "table2_sem_conflict_retained": ["3e", "3g"],
                "cited_reference": {"name": "SB-258585", "reported_ki_nm": "8.9",
                    "original_source": "reference 20: Hirst et al. 2000, DOI 10.1038/sj.bjp.0703458",
                    "new_measurement_in_this_paper": False, "included_in_identity_screen": True,
                    "included_in_model_diagnostic": False}},
            "scientifically_qualified": False, "service_ready": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ledger", "pdf-directory", "source-directory", "context", "checkpoint", "plan", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("refuse_existing_diagnostic")
    result = build(args.ledger, args.pdf_directory, args.source_directory,
                   args.context, args.checkpoint, args.plan)
    preflight._publish(args.output, json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output.read_bytes()),
                      "predicted": result["frozen_model_diagnostic"]["predicted"],
                      "identity_status_counts": result["identity_screen_with_cited_reference"]["status_counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

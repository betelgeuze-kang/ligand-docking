"""Research-only primary-paper intake and joint metadata screen regressions."""

from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_product import public_assay_components as components
from tools.product import primary_5ht6_ki_multi_paper_v1 as paper


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/evidence/human_5ht6_ki_multi_paper_source_ledger_v1.json"
SCREEN = ROOT / "docs/evidence/human_5ht6_ki_multi_paper_identity_screen_v1.json"


def _write_ledger(tmp_path, value):
    path = tmp_path / "ledger.json"
    path.write_bytes(paper._canonical(value))
    return path


def test_exact_primary_rows_graphs_and_closed_authority():
    ledger, digest = paper.verify_ledger(LEDGER)
    assert digest == paper.PINNED_LEDGER_SHA256
    assert len(ledger["sources"]) == 5 and len(ledger["rows"]) == 30
    assert {source["component_id"] for source in ledger["sources"]} == {
        "doi:" + doi for doi in paper.PDFS}
    assert set(ledger["role_policy"].values()) == {False, 0}
    assert all(row["assigned_role"] is None and not row["fit_admitted"]
               and row["prepared_state_origin"] is None
               and not row["proposed_neutral_graph"]["assayed_microstate_verified"]
               and not row["proposed_neutral_graph"]["source_graph_mapping_verified"]
               for row in ledger["rows"])
    assert not any(row["source_component_id"].endswith("1108")
                   and row["paper_row_id"] == "17" for row in ledger["rows"])
    assert [row["paper_row_id"] for row in ledger["rows"] if
            row["source_component_id"].endswith("1096")] == ["8", "9", "10", "11", "12"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda d: d["rows"][0]["reported_ki"].update(value="0.19"),
     "source_row_label_or_graph_pin_mismatch"),
    (lambda d: d["rows"][6]["proposed_neutral_graph"].update(
        canonical_isomeric_smiles=d["rows"][7]["proposed_neutral_graph"]["canonical_isomeric_smiles"]),
     "proposed_neutral_graph_mismatch"),
    (lambda d: d["rows"][0].update(assigned_role="fit"),
     "source_measurement_or_role_invalid"),
    (lambda d: d["rows"][10]["reported_ki"].update(uncertainty={"kind": "SD", "value": "1"}),
     "invented_per_row_uncertainty"),
    (lambda d: d["rows"][18]["reported_ki"].update(uncertainty={"kind": "SD", "value": "1"}),
     "reported_sem_invalid"),
    (lambda d: d["sources"][0].update(license_notice_in_pdf="CC0"),
     "source_method_rights_or_hash_mismatch"),
    (lambda d: d["role_policy"].update(roles_frozen=True),
     "source_role_authority_promoted"),
    (lambda d: d["role_policy"].update(fit_rows_admitted=False),
     "source_role_authority_promoted"),
])
def test_resealed_mutations_cannot_change_measurement_graph_rights_or_role(
        tmp_path, monkeypatch, mutation, reason):
    ledger, _ = paper.verify_ledger(LEDGER)
    changed = deepcopy(ledger)
    mutation(changed)
    raw = paper._canonical(changed)
    monkeypatch.setattr(paper, "PINNED_LEDGER_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match=reason):
        paper.verify_ledger(_write_ledger(tmp_path, changed))


def test_canonical_bytes_duplicate_keys_and_symlink_fail_closed(tmp_path):
    ledger, _ = paper.verify_ledger(LEDGER)
    path = _write_ledger(tmp_path, ledger)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source_ledger_does_not_match"):
        paper.verify_ledger(path)
    path.write_bytes(b'{"schema_version":"a","schema_version":"b"}\n')
    with pytest.raises(ValueError, match="duplicate_ledger_json_key"):
        paper.verify_ledger(path)
    link = tmp_path / "link.json"
    link.symlink_to(LEDGER)
    with pytest.raises(ValueError, match="noncanonical_source_path"):
        paper.verify_ledger(link)


def test_pdf_size_and_hash_bind_each_source_without_external_files(tmp_path, monkeypatch):
    ledger, _ = paper.verify_ledger(LEDGER)
    altered = deepcopy(ledger)
    paths, pinned = {}, {}
    for source in altered["sources"]:
        doi = source["doi"]
        path = tmp_path / (doi.split("/")[-1] + ".pdf")
        raw = b"%PDF-1.7\n" + doi.encode()
        path.write_bytes(raw)
        source["pdf_sha256"] = hashlib.sha256(raw).hexdigest()
        source["pdf_byte_count"] = len(raw)
        paths[doi] = path
        pinned[doi] = (source["pdf_sha256"], len(raw))
    monkeypatch.setattr(paper, "PDFS", pinned)
    assert paper.verify_pdfs(altered, paths) == {
        doi: value[0] for doi, value in pinned.items()}
    bad = paths["10.3390/molecules28031096"]
    bad.write_bytes(bad.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="primary_pdf_sha256_or_size_mismatch"):
        paper.verify_pdfs(altered, paths)


def test_joint_screen_uses_only_metadata_and_detects_transitive_reservation(tmp_path):
    ledger, _ = paper.verify_ledger(LEDGER)
    nodes = paper.candidate_nodes(ledger)
    protected = deepcopy(nodes[0])
    protected["node_id"] = "external:synthetic-reservation"
    protected["record_id"] = "external:synthetic-reservation"
    protected["protected"] = True
    context = tmp_path / "metadata-only.jsonl.gz"
    context.write_bytes(gzip.compress((json.dumps(protected, sort_keys=True) + "\n").encode()))
    digest = hashlib.sha256(context.read_bytes()).hexdigest()
    screen = paper.joint_identity_screen(ledger, context, digest)
    assert screen["status_counts"] == {
        "blocked_identity": 6, "identity_clear_review_required": 24}
    assert sum(row["direct_reserved_key_overlap"]
               for row in screen["candidate_results"]) == 6
    assert screen["protected_outcomes_read"] is False
    assert screen["source_roles_assigned"] is False
    context.write_bytes(context.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="preflight_input_sha256_mismatch"):
        paper.joint_identity_screen(ledger, context, digest)


def test_context_rejects_observation_fields_even_when_hash_bound(tmp_path):
    ledger, _ = paper.verify_ledger(LEDGER)
    node = paper.candidate_nodes(ledger)[0]
    node["measured_ki"] = "forbidden"
    context = tmp_path / "bad-context.jsonl"
    context.write_text(json.dumps(node) + "\n")
    with pytest.raises(ValueError, match="nonmetadata_or_missing_identity_context_field"):
        paper.joint_identity_screen(
            ledger, context, hashlib.sha256(context.read_bytes()).hexdigest())


def test_saved_joint_screen_is_narrow_and_bound_to_candidate_graphs():
    ledger, _ = paper.verify_ledger(LEDGER)
    receipt = json.loads(SCREEN.read_text())
    screen = receipt["joint_identity_screen"]
    assert screen["candidate_nodes_sha256"] == components.node_set_sha(
        paper.candidate_nodes(ledger))
    assert receipt["ledger_sha256"] == paper.PINNED_LEDGER_SHA256
    assert screen["context_sha256"] == (
        "7345f148051c04f5fdfaa12be1abf7ad81cbf96409bbaaf96d57ce8644d52519")
    assert screen["status_counts"] == {
        "blocked_identity": 9, "identity_clear_review_required": 21}
    witness = screen["representative_blocked_witness"]
    assert witness["candidate_id"] == "paper:10.3390/molecules28031108:2"
    assert witness["edge_kinds"] == ["scaffold", "document", "scaffold"]
    assert witness["hops"] == 3
    assert witness["boundary_reasons"] == ["reserved"]
    assert not any(row["direct_reserved_key_overlap"] or
                   row["direct_unknown_policy_key_overlap"]
                   for row in screen["candidate_results"])
    assert receipt["fit_calibration_development_or_evaluation_admitted"] is False
    assert receipt["protected_outcomes_read"] is False


def test_official_pdf_bundle_and_joint_context_when_supplied():
    pdf_dir = os.environ.get("BETELGEUZE_HT6_PRIMARY_PDF_DIR")
    context = os.environ.get("BETELGEUZE_HT6_IDENTITY_CONTEXT")
    if not pdf_dir or not context:
        pytest.skip("official PDFs and metadata-only identity context not supplied")
    directory = Path(pdf_dir)
    receipt = paper.verify_bundle(LEDGER, {
        "10.3390/molecules22122221": directory / "2017.pdf",
        "10.3390/molecules28031108": directory / "2023.pdf",
        "10.3390/molecules28031096": directory / "2023b.pdf",
        "10.3390/ijms251910287": directory / "2024.pdf",
        "10.3390/biom13010012": directory / "2023-biomolecules-alternate.pdf",
    }, context_path=Path(context), context_sha256=
        "7345f148051c04f5fdfaa12be1abf7ad81cbf96409bbaaf96d57ce8644d52519")
    assert receipt == json.loads(SCREEN.read_text())

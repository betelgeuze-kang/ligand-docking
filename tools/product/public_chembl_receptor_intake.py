"""Source-bound receptor Ki research intake, distinct from physical validation.

The v4 route retains the existing normalizer, identity graph and Ridge trainer.
It never assigns roles, infers receptor state, or replaces a censored label with
a point. Native source-37 patent data require a separate primary correspondence
record; literature-only admission remains the default in older versions.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from decimal import Decimal
import gzip
from pathlib import Path
import re

from tools.product import public_assay_components as components
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as bound
from tools.product import public_chembl_measurement as measurement
from tools.product import public_chembl_primary_correspondence as primary

KIND = "native_chembl_receptor_research_v4"
SUBTYPE = "receptor_radioligand_binding_Ki"


def resolve(entry, cache):
    """Hash-bound raw JSON with a strict JSON pointer; no default/last-row join."""
    pointer = entry.get("pointer", "")
    if (
        not isinstance(pointer, str)
        or (pointer and not pointer.startswith("/"))
        or re.search(r"~(?![01])", pointer)
    ):
        raise ValueError("invalid_source_pointer")
    key = (entry["path"], entry["sha256"], entry.get("format", "json"))
    if key[2] not in {"json", "jsonl"}:
        raise ValueError("unsupported_source_format")
    if key not in cache:
        raw = bound.read_bound(key[0], key[1]).decode()
        cache[key] = (
            [measurement.strict_loads(line) for line in raw.splitlines()]
            if key[2] == "jsonl"
            else measurement.strict_loads(raw)
        )
    value = cache[key]
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or int(token) >= len(value):
                raise ValueError("invalid_source_array_pointer")
            value = value[int(token)]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise ValueError("unresolved_source_pointer")
    return deepcopy(value)


def source_policies(*values):
    declarations = []

    def visit(value):
        if isinstance(value, dict):
            declared = {
                k: v
                for k, v in value.items()
                if k.strip().casefold() in components.POLICY_FIELDS
            }
            declarations.append(declared)
            if "assigned_role" in value:
                declarations.append({"role": value["assigned_role"]})
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    for value in values:
        visit(value)
    components.reservation_status(declarations)
    return declarations


def revalidate_primary(evidence, native, cache):
    """Recompute name/value correspondence from bound HTML and native records.

    This checks only the two declared development table formats. It does not
    verify physical assay state, units in the first patent, or primary accuracy.
    """
    primary._fit_policies(evidence)
    record = resolve(evidence["native_record_origin"], cache)
    if record != evidence["native_record"] or any(
        record.get(k) != native.get(k)
        for k in ("record_id", "src_id", "molecule_chembl_id", "document_chembl_id")
    ):
        raise ValueError("primary_native_record_mismatch")
    origin = evidence["primary_origin"]
    patent = evidence["patent_id"]
    key = (origin["path"], origin["sha256"], "primary_html", patent)
    if key not in cache:
        html = bound.read_bound(origin["path"], origin["sha256"]).decode()
        if patent == primary.PATENT:
            cache[key] = primary.extract_primary(html, patent_id=patent)
        elif patent == "US8569318B2":
            parser = primary._Rows()
            parser.feed(html)
            parser.close()
            if (
                parser.cells is not None
                or parser.cell is not None
                or ["No", "IC50, μM", "Ki, μM"] not in parser.rows
            ):
                raise ValueError("primary_endpoint_or_table_changed")
            cache[key] = parser.rows
        else:
            raise ValueError("unsupported_primary_correspondence_reader")
    tokens = record["compound_name"].split("::")
    conflicts = []
    if patent == primary.PATENT:
        aliases = []
        for token in tokens:
            match = re.fullmatch(r"US9067949, ([0-9]+[a-z]?)", token)
            if not match:
                raise ValueError("unsupported_native_example_alias")
            aliases.append(match[1])
        if len(aliases) != len(set(aliases)):
            raise ValueError("duplicate_native_example_alias")
        table = {row["example"]: row for row in cache[key]}
        rows = [table[alias] for alias in aliases]
        number = primary._number(native.get("value"))
        numeric = (
            len(rows) == 1
            and number is not None
            and primary._number(rows[0]["raw_value"]) == number
        )
    else:
        aliases = []
        for token in tokens:
            if token == native["molecule_chembl_id"]:
                continue
            match = re.fullmatch(r"US8569318, ([0-9]+[.][0-9]+[(][0-9]+[)])", token)
            if not match:
                raise ValueError("unsupported_native_example_alias")
            aliases.append(match[1])
        if len(aliases) != 1:
            raise ValueError("ambiguous_native_example_alias")
        rows = [row for row in cache[key] if len(row) == 3 and row[0] == aliases[0]]
        if len(rows) != 1:
            raise ValueError("ambiguous_primary_example")
        ic50, ki = primary._number(rows[0][1]), primary._number(rows[0][2])
        numeric = ki is not None and ki * Decimal(1000) == primary._number(
            native.get("value")
        )
        if ic50 is None or ki is None or ic50 <= 0 or ki <= 0 or ki >= ic50:
            conflicts.append("same_assay_declared_Cheng_Prusoff_pair_inconsistent")
    unique = (
        len(aliases) == 1
        and numeric
        and native.get("units") == "nM"
        and native.get("relation") == "="
    )
    if (
        evidence["primary_rows"] != rows
        or evidence["unique_native_name_and_numeric_match"] is not bool(unique)
        or evidence["primary_internal_conflicts"] != conflicts
    ):
        raise ValueError("primary_correspondence_cache_mismatch")
    return deepcopy(evidence)


def document_kind(document, bibliography):
    if document.get("doc_type") == "PATENT":
        return "patent"
    if (
        document.get("doc_type") == "PUBLICATION"
        and document.get("pubmed_id") is not None
        and bibliography.get("uid") == str(document["pubmed_id"])
        and isinstance(bibliography.get("pubtype"), list)
        and "Journal Article" in bibliography["pubtype"]
        and "Review" not in bibliography["pubtype"]
    ):
        return "research_article"
    return "unresolved"


def method_supported(method, activity, document):
    if not isinstance(method.get("description"), str):
        return False
    text = method["description"].casefold()
    return (
        method.get("assay_chembl_id") == activity["assay_chembl_id"]
        and method.get("document_chembl_id")
        == activity["document_chembl_id"]
        == document.get("document_chembl_id")
        and method.get("target_chembl_id") == activity["target_chembl_id"]
        and method.get("assay_type") == "B"
        and method.get("assay_tax_id") == 9606
        and method.get("confidence_score") == 9
        and (
            "radioligand" in text
            or "displacement" in text
            or "competitive binding" in text
        )
        and not any(word in text for word in ("camp", "qsar", "predicted", "docking"))
    )


def derive(manifest_path, manifest_sha256):
    manifest = bound.bound_json({"path": str(manifest_path), "sha256": manifest_sha256})
    scope = bound.bound_json(manifest["scope"])
    if (
        scope.get("intake_source_kind") != KIND
        or scope.get("endpoint") != "Ki"
        or scope.get("endpoint_subtype") != SUBTYPE
        or scope.get("source_database_license") != "CC-BY-SA-3.0"
        or scope.get("evidence_scope") != measurement.DB_CURATED_SCOPE
        or scope.get("physical_target_state_verified") is not False
        or scope.get("resplit_after_exclusions") is not False
    ):
        raise ValueError("unsupported_receptor_research_scope")
    if (
        manifest.get("schema_version")
        != bound.endpoint_contract(scope)["manifest_schema"]
    ):
        raise ValueError("unsupported_receptor_manifest")
    inputs = bound.bound_jsonl(manifest["metadata_records"])
    indexed = bound.unique_index(inputs, "activity_id")
    context_bytes = bound.read_bound(
        manifest["identity_context"]["path"], manifest["identity_context"]["sha256"]
    )
    context = [
        components.loads(line)
        for line in gzip.decompress(context_bytes).decode().splitlines()
    ]
    graph = components.component_index(context)
    nodes = {r["node_id"]: r for r in context}
    cache, loaded, assignments = {}, {}, []
    # Verify prospective assignments and original identity metadata BEFORE labels.
    for aid, entry in indexed.items():
        metadata_source = resolve(entry["metadata_origin"], cache)
        metadata = metadata_source.get("activity_metadata", metadata_source)
        metadata = metadata.get("ChEMBL activity metadata", metadata)
        if metadata.get("activity_id") != aid:
            raise ValueError("native_metadata_identity_mismatch")
        role = resolve(entry["role_origin"], cache)
        if (
            role.get("record_id") != "chembl:activity:" + str(aid)
            or role.get("assigned_role") not in bound.ROLES
        ):
            raise ValueError("invalid_preassigned_receptor_role")
        nid = entry["node_id"]
        if (
            nid != role.get("node_id")
            or nid not in graph
            or nodes[nid]["record_id"] != role["record_id"]
        ):
            raise ValueError("preassigned_role_node_mismatch")
        declarations = source_policies(metadata_source, role, nodes[nid])
        reserved, unknown = components.reservation_status(declarations)
        if unknown or (
            role["assigned_role"] == "fit" and (reserved or graph[nid]["blocked"])
        ):
            raise ValueError("reserved_or_unknown_fit_component")
        try:
            identity = common.chemical_identity(metadata["canonical_smiles"])
        except (ValueError, TypeError):
            identity = None
        expected = components.node_from_raw(
            {
                "ChEMBL Assay ID": metadata["assay_chembl_id"],
                "ChEMBL Document ID": metadata["document_chembl_id"],
            },
            identity,
            node_id=nid,
            record_id=role["record_id"],
            ligand_id="chembl:molecule:" + metadata["molecule_chembl_id"],
        )
        if not set(map(tuple, expected["keys"])) <= set(map(tuple, nodes[nid]["keys"])):
            raise ValueError("receptor_native_identity_graph_mismatch")
        assignment = {
            "activity_id": aid,
            "record_id": role["record_id"],
            "identity_context_node_id": nid,
            "component_id": graph[nid]["component_id"],
            "role": role["assigned_role"],
            "original": role,
        }
        assignments.append(assignment)
        loaded[aid] = (metadata, identity, assignment, declarations)
    # A capture is explicitly bound even for rejected rows; evaluation values
    # cannot enter this fit-only adapter. Output flags are recomputed, not read.
    output = []
    target = {
        "chembl_target_id": scope["target_annotation"],
        "scope": "catalogue target annotation only",
        "physical_state_verified": False,
        "endpoint_subtype": SUBTYPE,
    }
    for aid, entry in sorted(indexed.items()):
        metadata, identity, assignment, declarations = loaded[aid]
        issues, warnings = [], []
        prediction_issues = []
        if (
            metadata["target_chembl_id"] != scope["target_annotation"]
            or metadata["standard_type"] != "Ki"
        ):
            issues.append("target_or_endpoint_outside_binding_Ki_scope")
            prediction_issues.append("target_or_endpoint_outside_binding_Ki_scope")
        if identity is None:
            issues.append("chemical_identity_unresolved")
            prediction_issues.append("chemical_identity_unresolved")
        else:
            chemical = bound.chemistry_issues(identity, scope)
            if abs(identity["formal_charge"]) > 2:
                chemical.append("chemical_charge_outside_scope")
            issues.extend(chemical)
            prediction_issues.extend(chemical)
        native = None
        if entry.get("activity_origin") is not None:
            if assignment["role"] != "fit":
                raise ValueError("evaluation_outcome_in_fit_input")
            native = resolve(entry["activity_origin"], cache)
            if any(native.get(k) != metadata.get(k) for k in bound.METADATA_FIELDS):
                raise ValueError("native_value_metadata_mismatch")
            if set(native) != bound.ACTIVITY_FIELDS:
                raise ValueError("incomplete_or_extra_native_capture_fields")
        observation = measurement.normalize_measurement(native) if native else None
        method = (
            resolve(entry["method_origin"], cache) if entry.get("method_origin") else {}
        )
        document = resolve(entry["document_origin"], cache)
        document = document.get("native_document", document)
        if document.get("src_id") != metadata["src_id"]:
            raise ValueError("native_document_source_id_mismatch")
        declarations = source_policies(declarations, method, document)
        supported_method = method_supported(method, metadata, document)
        if not supported_method:
            issues.append("assay_method_not_verified_binding_Ki")
        correspondence = (
            resolve(entry["primary_origin"], cache)
            if entry.get("primary_origin")
            else {}
        )
        if correspondence:
            if (
                correspondence.get("activity_id") != aid
                or native is None
                or correspondence.get("native_activity") != native
            ):
                raise ValueError("primary_correspondence_activity_mismatch")
            correspondence = revalidate_primary(correspondence, native, cache)
        conflicts = correspondence.get("primary_internal_conflicts", [])
        unique = correspondence.get("unique_native_name_and_numeric_match") is True
        if metadata["src_id"] == 37:
            warnings.append(
                "primary_units_and_assayed_microstate_not_independently_verified"
            )
        comment = native.get("activity_comment") if native else None
        if comment not in (None, ""):
            if (
                metadata["src_id"] == 37
                and unique
                and isinstance(comment, str)
                and re.fullmatch(r"[0-9]+", comment)
            ):
                warnings.append(
                    "opaque_numeric_native_annotation_preserved_not_used_as_label_or_ID"
                )
            else:
                issues.append("activity_comment_requires_individual_resolution")
        profile = {
            "evidence_scope": scope["evidence_scope"],
            "evidence_kind": "experimental_label",
            "source_id": metadata["src_id"],
            "document_kind": document_kind(
                document,
                resolve(entry["bibliography_origin"], cache)
                if entry.get("bibliography_origin")
                else {},
            ),
            "citation_identity_status": "resolved"
            if document.get("document_chembl_id") == metadata["document_chembl_id"]
            else "unresolved",
            "assay_method_evidence_status": "curated_description_bound"
            if supported_method
            else "unresolved",
            "primary_source_status": "not_independently_verified",
            "endpoint_subtype": SUBTYPE,
            "requested_endpoint_subtype": SUBTYPE,
            "source_license": scope["source_database_license"],
            "target_state_status": "catalogue_annotation_only",
            "source_policy_declarations": declarations,
            "assigned_role": assignment["role"],
            "graph_blocked": graph[entry["node_id"]]["blocked"],
            "measurement_status": observation["status"] if observation else "withheld",
            "potential_duplicate": native.get("potential_duplicate")
            if native
            else None,
            "data_validity_comment": native.get("data_validity_comment")
            if native
            else None,
            "native_patent_identity_matches": bool(document.get("patent_id"))
            and correspondence.get("patent_id")
            == components.patent_publication(document.get("patent_id")),
            "primary_point_correspondence": "unique_native_name_and_numeric_match"
            if unique
            else "unresolved",
            "primary_internal_conflicts": conflicts,
        }
        admission = (
            measurement.admission(
                profile, "fit", source_profile="chembl_receptor_research_v4"
            )
            if native
            else None
        )
        if admission:
            issues.extend(admission["issues"])
            if (
                not observation["measurement_is_exact_for_fit"]
                or observation["endpoint"] != "Ki"
            ):
                issues.append("measurement_not_supported_exact_point")
            if (
                type(native.get("standard_flag")) not in (bool, int)
                or native["standard_flag"] != 1
            ):
                issues.append("standard_flag_not_confirmed")
        else:
            issues.append("native_label_withheld")
        output.append(
            {
                "schema_version": bound.SCHEMA_V4,
                "activity_id": aid,
                "record_id": assignment["record_id"],
                "assigned_role": assignment["role"],
                "component_id": assignment["component_id"],
                "assignment": assignment,
                "source_policy_declarations": declarations,
                "source_origins": deepcopy(entry),
                "native_metadata": metadata,
                "native_activity": native,
                "native_activity_origin": entry.get("activity_origin"),
                "method_evidence": method,
                "document_evidence": document,
                "primary_evidence": correspondence,
                "observation": observation,
                "admission": admission,
                "admission_issues": sorted(set(issues)),
                "prediction_issues": sorted(set(prediction_issues)),
                "evidence_warnings": sorted(set(warnings)),
                "eligible_for_point_model": native is not None and not issues,
                "chemical_identity": identity,
                "target_annotation": target,
                "target_annotation_sha256": components.digest(
                    components.canonical(target)
                ),
                "assay_id": "chembl:assay:" + metadata["assay_chembl_id"],
                "assayed_microstate_verified": False,
                "coordinates": None,
                "atom_order": None,
                "pose": None,
                "environment": None,
                "physical_energy": None,
                "force_labels": None,
                "source_license": scope["source_database_license"],
                "scientific_validation": False,
            }
        )
    role_sources = sorted(
        {(r["role_origin"]["path"], r["role_origin"]["sha256"]) for r in inputs}
    )
    plan = {
        "seed": 20260910,
        "preassigned_role_sources": [dict(path=p, sha256=h) for p, h in role_sources],
        "assignments": assignments,
        "counts": {
            role: sum(r["role"] == role for r in assignments) for role in bound.ROLES
        },
    }
    return manifest, plan, scope, output


def build(manifest_path, manifest_sha256, output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("output_already_exists")
    manifest, plan, scope, rows = derive(manifest_path, manifest_sha256)
    output_dir.mkdir(parents=True)
    path = output_dir / "records.jsonl"
    path.write_text("".join(common.json_text(r) + "\n" for r in rows))
    summary = {
        "schema_version": bound.SCHEMA_V4,
        "phase": "fit",
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "records_sha256": common.file_sha(path),
        "split_plan_sha256": components.digest(
            components.canonical(plan["preassigned_role_sources"])
        ),
        "intake_scope_sha256": manifest["scope"]["sha256"],
        "identity_context_sha256": manifest["identity_context"]["sha256"],
        "requested_metadata_rows": len(rows),
        "assigned_role_counts": plan["counts"],
        "point_eligible": sum(r["eligible_for_point_model"] for r in rows),
        "exclusions": dict(
            Counter(issue for r in rows for issue in r["admission_issues"])
        ),
    }
    (output_dir / "summary.json").write_text(common.json_text(summary) + "\n")
    return summary


def load_intake(input_dir, summary_sha256, phase):
    if phase != "fit":
        raise ValueError("receptor_v4_evaluation_adapter_not_enabled")
    summary = bound.bound_json(
        {"path": str(Path(input_dir) / "summary.json"), "sha256": summary_sha256}
    )
    manifest, plan, scope, expected = derive(
        summary["manifest_path"], summary["manifest_sha256"]
    )
    saved = bound.bound_jsonl(
        {
            "path": str(Path(input_dir) / "records.jsonl"),
            "sha256": summary["records_sha256"],
        }
    )
    if (
        saved != expected
        or summary.get("schema_version") != bound.SCHEMA_V4
        or summary.get("phase") != "fit"
    ):
        raise ValueError("receptor_intake_cache_does_not_match_native_source")
    fields = {
        "requested_metadata_rows": len(expected),
        "assigned_role_counts": plan["counts"],
        "point_eligible": sum(r["eligible_for_point_model"] for r in expected),
        "split_plan_sha256": components.digest(
            components.canonical(plan["preassigned_role_sources"])
        ),
        "intake_scope_sha256": manifest["scope"]["sha256"],
        "identity_context_sha256": manifest["identity_context"]["sha256"],
        "exclusions": dict(
            Counter(issue for r in expected for issue in r["admission_issues"])
        ),
    }
    if any(summary.get(k) != v for k, v in fields.items()):
        raise ValueError("receptor_intake_summary_does_not_match_source")
    return summary, plan, scope, expected

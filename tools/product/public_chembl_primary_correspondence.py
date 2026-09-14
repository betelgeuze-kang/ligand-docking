"""Fit-only primary example audit, not measurement or training admission.

This first reader supports the human 5HT6 Ki table in US9067949B2's Google
Patents HTML mirror. Native compound-name aliases identify groups; observations
are never paired to examples by value or row order. No units are corrected.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re

from tools.product import public_assay_components as components
from tools.product import public_chembl_measurement as measurement

PATENT = "US9067949B2"
DOCUMENT = "CHEMBL3638925"
ASSAY = "CHEMBL3706364"
TARGET = "CHEMBL3371"


def _fit_policies(value):
    """Inspect every nested source declaration before any numeric work."""
    if isinstance(value, dict):
        declarations = {k: v for k, v in value.items()
                        if k.strip().casefold() in components.POLICY_FIELDS}
        reserved, unknown = components.reservation_status([declarations])
        if reserved or unknown:
            raise ValueError("reserved_or_unknown_source_policy")
        if "assigned_role" in value and value["assigned_role"] != "fit":
            raise ValueError("nonfit_source_role")
        for nested in value.values():
            _fit_policies(nested)
    elif isinstance(value, list):
        for nested in value:
            _fit_policies(nested)


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.cells, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            if self.cells is not None:
                raise ValueError("nested_primary_table_row")
            self.cells = []
        elif tag in {"td", "th"} and self.cells is not None:
            if self.cell is not None:
                raise ValueError("nested_primary_table_cell")
            self.cell = []

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.cells is not None:
            if self.cell is not None:
                raise ValueError("unclosed_primary_table_cell")
            self.rows.append(self.cells)
            self.cells = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def extract_primary(html, *, patent_id):
    if patent_id != PATENT:
        raise ValueError("unsupported_primary_table_reader")
    parser = _Rows()
    parser.feed(html)
    parser.close()
    if parser.cells is not None or parser.cell is not None:
        raise ValueError("incomplete_primary_table")
    if not any("human 5HT6 Ki (nm)" in cells for cells in parser.rows):
        raise ValueError("primary_endpoint_or_printed_unit_changed")
    result, seen = [], set()
    for ordinal, raw in enumerate(parser.rows):
        cells = [cell for cell in raw if cell]
        labels = [cell for cell in cells if cell.startswith("Compound of Example")]
        if not labels:
            continue
        if len(cells) != 2 or not re.fullmatch(r"Compound of Example [0-9]+[a-z]?", cells[0]):
            raise ValueError("ambiguous_primary_example_row")
        example = cells[0].removeprefix("Compound of Example ")
        if example in seen:
            raise ValueError("duplicate_primary_example")
        seen.add(example)
        result.append({"example": example, "printed_label": cells[0], "raw_value": cells[1],
                       "printed_unit": "nm", "html_row_ordinal": ordinal})
    if not result:
        raise ValueError("no_primary_examples")
    return result


def _number(value):
    if type(value) not in (int, float, str):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def audit_fit(activities, compound_records, primary_rows, assignments):
    """Retain all requested fit rows, including ambiguity and measurement failures.

    The caller must verify the role plan against the current full identity graph
    and bind all source bytes. This local correspondence audit cannot grant fit
    eligibility, source approval, chemical-state verification, or independence.
    """
    roles = {}
    for row in assignments:
        key = row["activity_id"]
        if type(key) is not int or key <= 0 or key in roles:
            raise ValueError("duplicate_or_invalid_assignment")
        roles[key] = row
    measurement.require_unique_activity_ids(activities)
    expected = {k for k, row in roles.items() if row["assigned_role"] == "fit"}
    if {row["activity_id"] for row in activities} != expected:
        raise ValueError("fit_activity_coverage_mismatch")
    records, examples = {}, {}
    for row in compound_records:
        rid = row["record_id"]
        if type(rid) is not int or rid <= 0 or rid in records:
            raise ValueError("duplicate_or_invalid_native_record")
        records[rid] = row
    for row in primary_rows:
        key = row["example"]
        if key in examples:
            raise ValueError("duplicate_primary_example")
        examples[key] = row
    _fit_policies([activities, compound_records, primary_rows, [roles[k] for k in expected]])
    grouped = defaultdict(list)
    for row in activities:
        role = roles[row["activity_id"]]
        if (role.get("evaluation_only") is not False or role.get("source_document") != DOCUMENT
                or role.get("assay_id") != ASSAY or role.get("endpoint") != "Ki"):
            raise ValueError("fit_assignment_scope_mismatch")
        record = records.get(row["record_id"])
        if (record is None or row.get("src_id") != 37 or record.get("src_id") != 37
                or row.get("document_chembl_id") != DOCUMENT or record.get("document_chembl_id") != DOCUMENT
                or row.get("assay_chembl_id") != ASSAY or row.get("target_chembl_id") != TARGET
                or row.get("molecule_chembl_id") != record.get("molecule_chembl_id")):
            raise ValueError("native_source_identity_mismatch")
        grouped[row["record_id"]].append(row)
    if set(grouped) != set(records):
        raise ValueError("native_record_coverage_mismatch")
    ledger, used_examples = [], set()
    for rid in sorted(grouped):
        record, observations = records[rid], grouped[rid]
        aliases = []
        for token in record["compound_name"].split("::"):
            match = re.fullmatch(r"US9067949, ([0-9]+[a-z]?)", token)
            if match is None:
                raise ValueError("unsupported_native_example_alias")
            aliases.append(match[1])
        if len(aliases) != len(set(aliases)) or used_examples.intersection(aliases):
            raise ValueError("duplicate_native_example_alias")
        if any(alias not in examples for alias in aliases):
            raise ValueError("missing_primary_example")
        used_examples.update(aliases)
        primary_values = [_number(examples[key]["raw_value"]) for key in aliases]
        db_values = [_number(row.get("value")) for row in observations]
        numeric_match = (None not in primary_values + db_values
                         and Counter(primary_values) == Counter(db_values))
        unique = len(aliases) == len(observations) == 1
        for row in sorted(observations, key=lambda item: item["activity_id"]):
            observation = measurement.normalize_measurement(row)
            literal_units = all(examples[key]["printed_unit"] == row.get("units") for key in aliases)
            issues = []
            if not numeric_match:
                issues.append("primary_numeric_multiset_mismatch")
            if not unique:
                issues.append("native_record_merges_multiple_primary_examples")
            if not literal_units:
                issues.append("primary_literal_unit_disagreement")
            if (observation["status"] != "exact" or observation["endpoint"] != "Ki"
                    or observation["issues"]):
                issues.append("nonexact_or_invalid_database_Ki")
            if row.get("relation") != "=":
                issues.append("primary_exact_relation_disagreement")
            ledger.append({"source_activity": deepcopy(row), "source_assignment": deepcopy(roles[row["activity_id"]]),
                           "native_compound_record": deepcopy(record), "primary_rows": deepcopy([examples[key] for key in aliases]),
                           "normalized_observation": observation, "source_example": aliases[0] if unique else None,
                           "unique_name_correspondence": unique, "numeric_multiset_match": numeric_match,
                           "individual_pairs_inferred_from_values": False, "primary_literal_unit_agreement": literal_units,
                           "issues": issues, "source_stereochemical_state_verified": False,
                           "eligible_for_point_model": False, "scientific_admission": False,
                           "assigned_role": "fit", "evaluation_only": False})
    if used_examples != set(examples):
        raise ValueError("primary_example_coverage_mismatch")
    return ledger

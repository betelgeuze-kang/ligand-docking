"""Bounded-row JSON output shared by installed and checkout consumers."""

import json


def write_report_json(result: dict, output) -> None:
    """Keep the full JSON payload while encoding at most one case at a time."""
    options = {"sort_keys": True, "separators": (",", ":"), "allow_nan": False}
    output.write("{")
    for index, key in enumerate(sorted(result)):
        if index:
            output.write(",")
        output.write(json.dumps(key) + ":")
        value = result[key]
        if key == "rows" and isinstance(value, list):
            output.write("[")
            for row_index, row in enumerate(value):
                if row_index:
                    output.write(",")
                output.write(json.dumps(row, **options))
            output.write("]")
        else:
            output.write(json.dumps(value, **options))
    output.write("}\n")


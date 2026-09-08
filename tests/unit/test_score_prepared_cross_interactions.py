"""Consumer integration with fresh, one-atom, explicit synthetic local files.

The module subprocess executes parsing and fixed-coordinate cross arithmetic
only. No real molecular sources, learned weights, solver or search are used.
"""

from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tracemalloc
from types import SimpleNamespace

import pytest

from tools.product import score_prepared_cross_interactions as consumer


REPOSITORY = Path(__file__).resolve().parents[2]
ENVIRONMENT = {
    "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "BETELGEUZE_PRODUCT_TEST_ARTIFACT_BOOTSTRAP": "disabled", "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": "", "HIP_VISIBLE_DEVICES": "", "ROCR_VISIBLE_DEVICES": "",
}


def test_report_writer_preserves_measured_zero_absence_failure_and_provenance():
    report = {"rows": [
        {"case_id": "같은 ID", "status": "evaluated", "coordinates": [[-0.0, 1e-300, 1e300]],
         "force": [[0.0, -0.0, 0.0]], "affinity": None, "source": {"IC50[uM]": "0", "error": "-1"}},
        {"case_id": "같은 ID", "status": "failed", "reason": "missing \"charge\"\nfield", "force": None}],
        "denominator": {"requested": 2, "evaluated": 1, "failed": 1, "skipped": 0},
        "customer_execution": False, "large_integer_source_id": 2**60 + 1}
    output = io.StringIO()
    consumer._write_report_json(report, output)
    decoded = json.loads(output.getvalue())
    # The standard encoder comparison also distinguishes signed zero, bool,
    # integer and float representations that ordinary Python equality merges.
    assert json.dumps(decoded, sort_keys=True) == json.dumps(report, sort_keys=True)
    assert output.getvalue().endswith("\n")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_report_writer_still_rejects_nonfinite_nested_numbers(value):
    with pytest.raises(ValueError, match="Out of range float"):
        consumer._write_report_json({"rows": [{"force": [[value, 0.0, 0.0]]}]}, io.StringIO())


def test_report_writer_limits_each_output_chunk_to_one_case():
    class ObservedOutput(io.StringIO):
        largest_chunk = 0

        def write(self, text):
            self.largest_chunk = max(self.largest_chunk, len(text))
            return super().write(text)

    row = {"source": "supplied metadata " * 100, "score": 0.0, "unevaluated": None}
    report = {"rows": [row] * 32, "denominator": {"requested": 32}}
    output = ObservedOutput()
    consumer._write_report_json(report, output)
    assert json.loads(output.getvalue()) == report
    assert output.largest_chunk == len(json.dumps(row, sort_keys=True, separators=(",", ":")))


@pytest.mark.parametrize("failed", [False, True])
def test_explicit_compact_main_preserves_full_payload_and_exit(monkeypatch, tmp_path, capsys, failed):
    report = _serialization_report(failed=failed, unicode=True)
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    before = request.read_bytes()
    code = consumer.main(argv + ["--output-format", "compact"])
    expected = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    assert output.read_bytes() == expected
    assert code == (2 if failed else 0)
    assert request.read_bytes() == before
    assert report["consumer_source_sha256"] == hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest()
    summary = json.loads(capsys.readouterr().out)
    assert summary["exit_code"] == code and summary["denominator"] == report["denominator"]


@pytest.mark.parametrize("inside_row", [False, True])
def test_compact_main_nonfinite_failure_never_reports_success(monkeypatch, tmp_path, capsys, inside_row):
    report = _serialization_report()
    if inside_row:
        report["rows"][-1]["result"]["values"].append(math.nan)
    else:
        report["zz_invalid"] = math.nan
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    before = request.read_bytes()
    with pytest.raises(ValueError, match="JSON compliant"):
        consumer.main(argv + ["--output-format", "compact"])
    assert not capsys.readouterr().out
    assert request.read_bytes() == before
    with pytest.raises(json.JSONDecodeError):
        json.loads(output.read_text())


def test_compact_main_write_failure_propagates_and_preserves_request(monkeypatch, tmp_path, capsys):
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, _serialization_report())
    before = request.read_bytes()
    original_open = Path.open

    class FailingOutput:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, text):
            self.stream.write(text[:1])
            raise OSError("synthetic compact storage failure")

    def open_output(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return FailingOutput(stream) if path == output and mode == "x" else stream

    monkeypatch.setattr(Path, "open", open_output)
    with pytest.raises(OSError, match="synthetic compact storage failure"):
        consumer.main(argv + ["--output-format", "compact"])
    assert not capsys.readouterr().out
    assert request.read_bytes() == before
    with pytest.raises(json.JSONDecodeError):
        json.loads(output.read_text())


@pytest.mark.parametrize("missing", [False, True])
def test_compact_main_invalid_request_retains_null_denominator(tmp_path, capsys, missing):
    request, output = tmp_path / "invalid.json", tmp_path / "invalid-report.json"
    if not missing:
        request.write_text("{ invalid JSON")
    code = consumer.main(["--request", str(request), "--output", str(output), "--output-format", "compact"])
    report = json.loads(output.read_text())
    assert code == 2 and report["status"] == "invalid_request"
    assert report["denominator"] is None and report["customer_execution"] is False
    assert report["request_sha256"] == (None if missing else hashlib.sha256(request.read_bytes()).hexdigest())
    assert json.loads(capsys.readouterr().out)["exit_code"] == 2
    assert request.exists() is not missing


def _write_source(directory, filename, content):
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_id": "synthetic-local-constants:" + filename}


def _prepared(directory):
    directory.mkdir(parents=True, exist_ok=True)
    pdb = f"ATOM  {1:5d} {'C1':>4s} {'SYN':>3s} A{1:4d}    {0.0:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}          {'C':>2s}  \nEND\n"
    sdf = ("Synthetic explicit carbon\n  local synthetic test\n\n"
           "  1  0  0  0  0  0            999 V2000\n"
           f"{4.0:10.4f}{0.0:10.4f}{0.0:10.4f} C   0  0  0  0  0  0  0  0  0  0  0  0\nM  END\n$$$$\n")
    gro = ("Synthetic explicit carbon\n1\n"
           f"{1:5d}{'LIG':<5s}{'C1':>5s}{1:5d}{0.4:8.3f}{0.0:8.3f}{0.0:8.3f}\n0.0 0.0 0.0\n")
    atomtypes = "[ atomtypes ]\nC 6 12.011 0.0 A 0.300000 0.836800\n"
    defaults = "[ defaults ]\n1 2 yes 0.5 0.833333\n"
    protein_itp = "[ moleculetype ]\nSYN 3\n[ atoms ]\n1 C 1 SYN C1 1 0.2 12.011\n"
    ligand_itp = "[ moleculetype ]\nLIG 3\n[ atoms ]\n1 C 1 LIG C1 1 -0.3 12.011\n"
    content = {"protein_pdb": ("receptor.pdb", pdb), "protein_atomtypes": ("receptor-types.itp", atomtypes),
               "protein_defaults": ("receptor-defaults.itp", defaults), "ligand_sdf": ("ligand.sdf", sdf),
               "ligand_gro": ("ligand.gro", gro), "ligand_itp": ("ligand.itp", ligand_itp),
               "ligand_atomtypes": ("ligand-types.itp", atomtypes), "ligand_defaults": ("ligand-defaults.itp", defaults)}
    request = {key: _write_source(directory, filename, text) for key, (filename, text) in content.items()}
    request.update(schema_version="prepared_gromacs_components_v1",
        protein_chains=[{"chain_id": "A", "molecule_itp": _write_source(directory, "receptor.itp", protein_itp)}],
        ligand_atomtype_name_mapping={}, ligand_residue_name_mapping={"gro": "LIG", "itp": "LIG"},
        naming_convention="exact", pdb_element_policy="reject_missing",
        source_relationship="independent synthetic text constants in a declared frame",
        source_declarations={"coordinate_frame_id": "synthetic-frame", "prepared_state_id": "synthetic-state",
            "parameter_source_id": "synthetic-explicit-tables", "charge_source_id": "synthetic-explicit-charge"})
    return request


def _case(prepared, *, case_id="duplicate-id"):
    return {"case_id": case_id, "prepared_input": prepared, "evaluation": {
        "pocket_center_angstrom": [0.0, 0.0, 0.0], "pocket_radius_angstrom": 10.0,
        "cutoff_angstrom": 10.0, "switch_start_angstrom": 8.0, "dielectric": 4.0,
        "screening_kappa_per_angstrom": 0.1}}


def _request(cases):
    return {"schema_version": "prepared_cross_interaction_request_v1", "cases": cases}


def _run(request_path, output_path, evidence):
    argv = [sys.executable, "-B", "-m", "tools.product.score_prepared_cross_interactions",
            "--request", str(request_path), "--output", str(output_path)]
    result = subprocess.run(argv, cwd=REPOSITORY, env={**os.environ, **ENVIRONMENT},
                            text=True, capture_output=True, timeout=30)
    (evidence / "subprocess.stdout").write_text(result.stdout)
    (evidence / "subprocess.stderr").write_text(result.stderr)
    sources = ["tools/product/score_prepared_cross_interactions.py",
               "betelgeuze_engine/product/prepared_gromacs_input.py", "betelgeuze_engine/product/v2_cross_interaction.py"]
    (evidence / "subprocess-execution.json").write_text(json.dumps({"argv": argv, "workdir": str(REPOSITORY),
        "environment_overrides": ENVIRONMENT, "observed_exit": result.returncode,
        "source_sha256": {p: hashlib.sha256((REPOSITORY / p).read_bytes()).hexdigest() for p in sources}}, indent=2) + "\n")
    return result


def _assert_unqualified(report):
    for field in ("customer_execution", "scientifically_validated", "external_solver_called"):
        assert report[field] is False


def _assert_scalar_pair(result):
    r, sigma, epsilon = 4.0, 3.0, 0.2
    a6 = (sigma / r) ** 6
    lj = 4 * epsilon * (a6 * a6 - a6)
    coulomb = 332.063713299 * 0.2 * -0.3 * math.exp(-0.1 * r) / (4.0 * r)
    derivative = 24 * epsilon * (a6 - 2 * a6 * a6) / r - coulomb * (0.1 + 1 / r)
    quantities = result["quantities"]
    assert quantities["cross_total_kcal_per_mol"] == pytest.approx(lj + coulomb, rel=2e-12)
    assert quantities["receptor_cross_forces_kcal_per_mol_angstrom"][0] == pytest.approx([derivative, 0, 0], rel=2e-12)
    assert quantities["ligand_cross_forces_kcal_per_mol_angstrom"][0] == pytest.approx([-derivative, 0, 0], rel=2e-12)
    for field in ("internal_energy", "strain", "solvation", "residual", "affinity"):
        assert quantities[field] is None


def test_real_parser_runtime_and_module_subprocess_agree_on_synthetic_files(tmp_path):
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine.product.v2_cross_interaction import evaluate_prepared_cross_interaction

    prepared = _prepared(tmp_path / "sources")
    case = _case(prepared)
    receptor, ligand, rp, lp, provenance = load_prepared_gromacs_components(prepared)
    direct = evaluate_prepared_cross_interaction(receptor, ligand, rp, lp,
        source_declarations=prepared["source_declarations"], **case["evaluation"])
    _assert_scalar_pair(direct)
    source_before = {ref["path"]: Path(ref["path"]).read_bytes() for ref in provenance["sources"].values()}
    request_path, output_path = tmp_path / "request.json", tmp_path / "report.json"
    request_path.write_text(json.dumps(_request([case])))
    process = _run(request_path, output_path, tmp_path)
    assert process.returncode == 0, process.stderr
    report = json.loads(output_path.read_text())
    assert report["denominator"] == {"requested": 1, "evaluated": 1, "failed": 0, "skipped": 0}
    row = report["rows"][0]
    assert row["request_index"] == 0
    assert row["result"]["quantities"] == direct["quantities"]
    assert row["result"]["sources"] == direct["sources"]
    assert row["preparation_provenance"]["source_hashes_postflight_verified"] is True
    assert report["request_sha256"] == hashlib.sha256(request_path.read_bytes()).hexdigest()
    assert report["consumer_source_sha256"] == hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest()
    _assert_scalar_pair(row["result"])
    _assert_unqualified(report)
    assert all(Path(path).read_bytes() == raw for path, raw in source_before.items())


def test_actual_subprocess_retains_failed_cases_and_duplicate_ids_in_original_order(tmp_path):
    prepared = _prepared(tmp_path / "sources")
    success = _case(prepared)
    mismatched = copy.deepcopy(success)
    mismatched["prepared_input"]["ligand_gro"]["sha256"] = "0" * 64
    missing = copy.deepcopy(success)
    del missing["evaluation"]["dielectric"]
    request = _request([success, mismatched, None, missing, copy.deepcopy(success)])
    request_path, output_path = tmp_path / "request.json", tmp_path / "report.json"
    request_path.write_text(json.dumps(request))
    process = _run(request_path, output_path, tmp_path)
    assert process.returncode == 2
    report = json.loads(output_path.read_text())
    assert report["denominator"] == {"requested": 5, "evaluated": 2, "failed": 3, "skipped": 0}
    assert [row["request_index"] for row in report["rows"]] == list(range(5))
    assert [row["case_id"] for row in report["rows"]] == ["duplicate-id", "duplicate-id", None, "duplicate-id", "duplicate-id"]
    assert [row["status"] for row in report["rows"]] == ["evaluated", "failed", "failed", "failed", "evaluated"]
    assert "SHA-256 mismatch" in report["rows"][1]["reason"]
    _assert_unqualified(report)


@pytest.mark.parametrize("raw", [
    "{", "null", "[]", "{}", '{"schema_version":"wrong","cases":[null]}',
    '{"schema_version":"prepared_cross_interaction_request_v1","cases":[]}',
    '{"schema_version":"prepared_cross_interaction_request_v1","cases":[null],"extra":1}',
    '{"schema_version":"prepared_cross_interaction_request_v1","cases":[null],"cases":[null]}',
    '{"schema_version":"prepared_cross_interaction_request_v1","cases":[{"case_id":NaN}]}',
    '{"schema_version":"prepared_cross_interaction_request_v1","cases":[{"case_id":Infinity}]}',
    '{"schema_version":"prepared_cross_interaction_request_v1","cases":[{"case_id":-Infinity}]}',
])
def test_malformed_or_nonfinite_json_has_no_invented_denominator(tmp_path, raw):
    request_path, output_path = tmp_path / "request.json", tmp_path / "report.json"
    request_path.write_text(raw)
    process = _run(request_path, output_path, tmp_path)
    assert process.returncode == 2
    report = json.loads(output_path.read_text())
    assert report["status"] == "invalid_request"
    assert report["denominator"] is None
    assert report["request_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    _assert_unqualified(report)


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink", "existing", "broken_symlink"])
def test_output_alias_or_existing_file_is_preserved(tmp_path, alias):
    request_path, output_path = tmp_path / "request.json", tmp_path / "report.json"
    original = b'{"synthetic_original":"preserve byte for byte"}\n'
    request_path.write_bytes(original)
    if alias == "same":
        output_path = request_path
    elif alias == "symlink":
        output_path.symlink_to(request_path)
    elif alias == "hardlink":
        os.link(request_path, output_path)
    elif alias == "existing":
        output_path.write_bytes(b"existing evidence\n")
    else:
        output_path.symlink_to(tmp_path / "absent-target")
    before = output_path.read_bytes() if output_path.exists() else None
    process = _run(request_path, output_path, tmp_path)
    assert process.returncode == 2
    assert request_path.read_bytes() == original
    assert (output_path.read_bytes() if output_path.exists() else None) == before
    assert "output must be a new path" in process.stderr


def test_actual_source_file_cannot_be_used_as_output(tmp_path):
    prepared = _prepared(tmp_path / "sources")
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request([_case(prepared)])))
    output_path = Path(prepared["protein_pdb"]["path"])
    before = output_path.read_bytes()
    process = _run(request_path, output_path, tmp_path)
    assert process.returncode == 2
    assert output_path.read_bytes() == before


@pytest.mark.parametrize("case", [None, [], {}, 42, {"case_id": True}, {"case_id": float("inf")},
    {"case_id": " "}, {"case_id": "x", "prepared_input": {}, "evaluation": {}, "extra": 1}])
def test_invalid_case_shapes_preserve_one_finite_ledger_row(case):
    result = consumer.evaluate_request(_request([case]))
    assert result["denominator"] == {"requested": 1, "evaluated": 0, "failed": 1, "skipped": 0}
    assert result["rows"][0]["request_index"] == 0
    assert result["rows"][0]["status"] == "failed"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("count", [0, 33])
def test_request_case_capacity_is_explicit(count):
    with pytest.raises(ValueError):
        consumer.evaluate_request(_request([None] * count))


def test_maximum_32_requests_keep_every_failure_and_index():
    report = consumer.evaluate_request(_request([None] * 32))
    assert report["denominator"] == {"requested": 32, "evaluated": 0, "failed": 32, "skipped": 0}
    assert [row["request_index"] for row in report["rows"]] == list(range(32))


def test_missing_reader_dependency_is_a_per_case_failure_with_known_denominator(monkeypatch):
    original_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "betelgeuze_engine.product.prepared_gromacs_input":
            raise ModuleNotFoundError("synthetic missing optional reader dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    report = consumer.evaluate_request(_request([_case({}), _case({})]))
    assert report["denominator"] == {"requested": 2, "evaluated": 0, "failed": 2, "skipped": 0}
    assert [row["request_index"] for row in report["rows"]] == [0, 1]
    assert all(row["error_type"] == "ModuleNotFoundError" for row in report["rows"])


def test_missing_request_file_reports_unknown_denominator_and_no_fabricated_hash(tmp_path):
    request_path, output_path = tmp_path / "absent-request.json", tmp_path / "report.json"
    process = _run(request_path, output_path, tmp_path)
    assert process.returncode == 2
    report = json.loads(output_path.read_text())
    assert report["status"] == "invalid_request"
    assert report["denominator"] is None
    assert report["request_sha256"] is None
    _assert_unqualified(report)


def test_prepared_reader_and_consumer_have_no_solver_import_or_invocation():
    # Inspect these two adapter sources only; package-wide imports are not claimed.
    paths = [REPOSITORY / "betelgeuze_engine/product/prepared_gromacs_input.py", Path(consumer.__file__)]
    forbidden = {"subprocess", "openmm", "simtk", "gromacs", "mdtraj", "rdkit", "sklearn"}
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not forbidden.intersection(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"exec", "eval", "__import__"}


def _serialization_report(*, failed=False, unicode=False, many_values=False):
    count = 32 if many_values else 2
    rows = [{"request_index": i, "case_id": f"synthetic-{i}", "status": "evaluated",
             "result": {"values": list(range(4096)) if many_values else [0.0, -0.0, 1e-30, 1e30, None],
                        "metadata": {"text": 'escaped "text" and \\ and \n', "measured": False}}}
            for i in range(count)]
    if failed:
        rows[-1] = {"request_index": count - 1, "case_id": "synthetic-failure", "status": "failed",
                    "error_type": "SyntheticUnsupported", "reason": "explicit synthetic failure"}
    if unicode:
        rows[0]["result"]["metadata"]["text"] = "공개 개발 · café · ΔG · 😀"
    return {"schema_version": "prepared_cross_interaction_report_v1", "rows": rows,
            "denominator": {"requested": count, "evaluated": count - int(failed),
                            "failed": int(failed), "skipped": 0},
            "customer_execution": False, "scientifically_validated": False, "external_solver_called": False}


def _fixed_report_main(monkeypatch, tmp_path, report):
    request = tmp_path / "writer-request.json"
    output = tmp_path / "writer-report.json"
    request.write_text(json.dumps(_request([None])))
    monkeypatch.setattr(consumer, "evaluate_request", lambda request: report)
    monkeypatch.setattr(consumer, "time", SimpleNamespace(perf_counter=lambda: 123.0, process_time=lambda: 45.0))
    monkeypatch.setattr(consumer, "platform", SimpleNamespace(platform=lambda: "synthetic fixed platform"))
    monkeypatch.setattr(consumer, "resource", SimpleNamespace(RUSAGE_SELF=0,
        getrusage=lambda who: SimpleNamespace(ru_maxrss=256)))
    return request, output, ["--request", str(request), "--output", str(output)]


@pytest.mark.parametrize("failed,unicode", [(False, False), (True, False), (False, True), (True, True)])
def test_report_serialization_bytes_equal_legacy_for_same_emitted_object(monkeypatch, tmp_path, capsys, failed, unicode):
    report = _serialization_report(failed=failed, unicode=unicode)
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    before = request.read_bytes()
    code = consumer.main(argv)
    # main enriches this same object with the actual, unmodified source SHA and
    # fixed process observations; no other revision's provenance is fabricated.
    legacy_bytes = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    assert output.read_bytes() == legacy_bytes
    assert code == (2 if failed else 0)
    assert report["consumer_source_sha256"] == hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest()
    assert request.read_bytes() == before
    summary = json.loads(capsys.readouterr().out)
    assert summary["exit_code"] == code and summary["denominator"] == report["denominator"]


class _DigestSink:
    """Consume text without retaining the report or choosing encoder chunks."""
    def __init__(self):
        self.sha = hashlib.sha256()
        self.bytes = 0
        self.largest_write = 0

    def write(self, text):
        payload = text.encode("utf-8")
        self.sha.update(payload)
        self.bytes += len(payload)
        self.largest_write = max(self.largest_write, len(payload))
        return len(text)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_report_writer_does_not_materialize_aggregate_text(monkeypatch, tmp_path):
    # Construct the retained producer object BEFORE tracing writer allocations.
    # Many small fields are deliberate: this does not bound one giant string.
    report = _serialization_report(many_values=True)
    _, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    sink = _DigestSink()
    original_open = Path.open

    def open_output(path, mode="r", *args, **kwargs):
        if path == output and mode == "x":
            return sink
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_output)
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        code = consumer.main(argv)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # The compatibility oracle is deliberately outside the measured interval.
    legacy_bytes = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    assert code == 0
    assert sink.bytes == len(legacy_bytes)
    assert sink.sha.hexdigest() == hashlib.sha256(legacy_bytes).hexdigest()
    observation = {"serialized_bytes": sink.bytes, "peak_additional_python_bytes": peak,
                   "largest_write_bytes": sink.largest_write,
                   "scope": "writer-only tracemalloc, prebuilt report, many small tokens; not whole-process RSS"}
    (tmp_path / "writer-memory-observation.json").write_text(json.dumps(observation, indent=2) + "\n")
    print(json.dumps(observation, sort_keys=True))
    assert sink.bytes > 1024 * 1024
    assert peak < 1024 * 1024
    assert sink.largest_write < sink.bytes // 8


def test_report_writer_late_nonfinite_error_has_no_success_summary(monkeypatch, tmp_path, capsys):
    report = _serialization_report()
    report["zz_invalid"] = float("nan")
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    before = request.read_bytes()
    with pytest.raises(ValueError, match="JSON compliant"):
        consumer.main(argv)
    assert not capsys.readouterr().out
    assert request.read_bytes() == before
    # Neither an empty legacy file nor a streaming prefix is a valid report.
    # Publication was already non-atomic; errors propagate rather than succeed.
    with pytest.raises(json.JSONDecodeError):
        json.loads(output.read_text())


def test_report_writer_io_error_propagates_without_success_or_source_change(monkeypatch, tmp_path, capsys):
    report = _serialization_report()
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    before = request.read_bytes()
    original_open = Path.open

    class FailAfterPrefix:
        def __init__(self, stream):
            self.stream, self.remaining = stream, 30

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()
            return False

        def write(self, text):
            prefix = text[:self.remaining]
            self.stream.write(prefix)
            self.remaining -= len(prefix)
            if len(prefix) < len(text):
                raise OSError("synthetic output storage failure")
            return len(text)

    def open_output(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return FailAfterPrefix(stream) if path == output and mode == "x" else stream

    monkeypatch.setattr(Path, "open", open_output)
    with pytest.raises(OSError, match="synthetic output storage failure"):
        consumer.main(argv)
    assert not capsys.readouterr().out
    assert request.read_bytes() == before
    with pytest.raises(json.JSONDecodeError):
        json.loads(output.read_text())


def test_report_writer_exclusive_open_keeps_racing_existing_output(monkeypatch, tmp_path, capsys):
    report = _serialization_report()
    request, output, argv = _fixed_report_main(monkeypatch, tmp_path, report)
    before = request.read_bytes()
    original_open = Path.open

    def open_output(path, mode="r", *args, **kwargs):
        if path == output and mode == "x":
            with original_open(path, "x", encoding="utf-8") as competing:
                competing.write("competing evidence\n")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_output)
    with pytest.raises(FileExistsError):
        consumer.main(argv)
    assert not capsys.readouterr().out
    assert request.read_bytes() == before
    assert output.read_bytes() == b"competing evidence\n"

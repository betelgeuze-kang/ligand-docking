from __future__ import annotations

import json

import pytest

from tools.redocking_development_p1 import (
    DevelopmentObservation,
    DevelopmentObservationError,
)


def _observation(events=None, **kwargs):
    return DevelopmentObservation(
        "fixture",
        event_sink=([] if events is None else events).append,
        evaluator_identity="a" * 64,
        **kwargs,
    )


def _records(n=64):
    return tuple(
        f"fixture_engine_v2_rank_{i}\n$$$$\n".encode() for i in range(1, n + 1)
    )


def _outcomes(n):
    return (
        tuple(float(i) for i in range(n)),
        (True,) * n,
        (False,) * n,
        (("minimum_distance_to_protein",),) * n,
    )


def test_exact_top5_reuses_only_completed_matching_records():
    events, calls = [], []
    observer = _observation(events)
    records = _records()

    def evaluate():
        calls.append(1)
        return _outcomes(64)

    first = observer.evaluate(
        records,
        native_payload=b"native",
        receptor_payload=b"receptor",
        evaluate=evaluate,
    )
    selected = observer.evaluate(
        records[:5],
        native_payload=b"native",
        receptor_payload=b"receptor",
        evaluate=lambda: pytest.fail("matching Top5 must use retained evaluations"),
    )
    assert selected == tuple(values[:5] for values in first)
    assert len(calls) == 1
    assert observer.summary()["evaluation_cache"]["reused_records"] == 5
    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    assert all(e["profile"] == "development_observation_v1" for e in events)


@pytest.mark.parametrize("changed", ["native", "receptor", "pose", "title"])
def test_changed_bytes_force_evaluation(changed):
    observer = _observation()
    records = _records(5)
    observer.evaluate(
        records,
        native_payload=b"native",
        receptor_payload=b"receptor",
        evaluate=lambda: _outcomes(5),
    )
    changed_records = records
    if changed in {"pose", "title"}:
        changed_records = (
            records[0].replace(b"fixture", changed.encode()),
            *records[1:],
        )
    calls = []
    observer.evaluate(
        changed_records,
        native_payload=b"other" if changed == "native" else b"native",
        receptor_payload=b"other" if changed == "receptor" else b"receptor",
        evaluate=lambda: (calls.append(1), _outcomes(5))[1],
    )
    assert calls == [1]
    assert observer.summary()["evaluation_cache"]["reused_records"] == 0


def test_disabled_reuse_still_measures_and_evaluates():
    observer = _observation(reuse_evaluations=False)
    calls = []
    for _ in range(2):
        observer.evaluate(
            _records(5),
            native_payload=b"native",
            receptor_payload=b"receptor",
            evaluate=lambda: (calls.append(1), _outcomes(5))[1],
        )
    assert len(calls) == 2
    assert observer.summary()["evaluation_cache"]["reused_records"] == 0


@pytest.mark.parametrize(
    "bad",
    [
        ((1.0,), (True,), (True,), ((),)),
        ((float("nan"),) * 5, (True,) * 5, (True,) * 5, ((),) * 5),
        ((1.0,) * 5, (1,) * 5, (True,) * 5, ((),) * 5),
    ],
)
def test_incomplete_or_invalid_evaluation_is_never_cached(bad):
    observer = _observation()
    with pytest.raises(DevelopmentObservationError):
        observer.evaluate(
            _records(5),
            native_payload=b"native",
            receptor_payload=b"receptor",
            evaluate=lambda: bad,
        )
    assert observer.summary()["evaluation_cache"]["cached_records"] == 0


def test_backend_exception_is_not_cached():
    observer = _observation()

    def fail():
        raise RuntimeError("evaluation interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        observer.evaluate(
            _records(5),
            native_payload=b"native",
            receptor_payload=b"receptor",
            evaluate=fail,
        )
    assert observer.summary()["evaluation_cache"]["cached_records"] == 0


def test_reference_preparation_cache_clones_before_exposing_objects():
    observer = _observation()
    seen = []

    def decode(prepared):
        seen.append(prepared)
        return (
            (("pose",), ["native"], ["receptor"])
            if prepared is None
            else (("pose",), *prepared)
        )

    _, native, receptor = observer.decode_inputs(
        native_payload=b"native",
        receptor_payload=b"receptor",
        decode=decode,
        clone=list,
    )
    native.append("mutated by evaluator")
    receptor.append("mutated by evaluator")
    _, native2, receptor2 = observer.decode_inputs(
        native_payload=b"native",
        receptor_payload=b"receptor",
        decode=decode,
        clone=list,
    )
    assert seen[0] is None
    assert native2 == ["native"] and receptor2 == ["receptor"]
    assert observer.summary()["prepared_inputs"]["cache_hits"] == 1


def test_failed_sink_latches_and_cannot_be_silently_ignored():
    def fail(event):
        raise OSError("checkpoint disk full")

    observer = DevelopmentObservation(
        "fixture", event_sink=fail, evaluator_identity="a" * 64
    )
    with pytest.raises(DevelopmentObservationError, match="sink"):
        observer.core_event("proposal_generation", "start", {})
    with pytest.raises(DevelopmentObservationError):
        observer.assert_healthy()


def test_search_observer_rejects_reference_labels():
    observer = _observation()
    with pytest.raises(DevelopmentObservationError, match="reference"):
        observer.core_event("proposal_generated", "snapshot", {"rmsd_angstrom": 0.1})
    with pytest.raises(DevelopmentObservationError):
        observer.assert_healthy()


def test_stage_error_keeps_error_event_and_original_exception():
    events = []
    observer = _observation(events)
    with pytest.raises(ValueError, match="fixture"):
        with observer.stage("prepare"):
            raise ValueError("fixture")
    assert [e["phase"] for e in events] == ["start", "error"]
    assert events[-1]["details"]["error_type"] == "ValueError"
    assert events[-1]["elapsed_seconds"] >= 0
    json.dumps(events, allow_nan=False)


def test_event_identity_and_context_are_not_cross_wired():
    observer = _observation()
    observer.assert_case("fixture")
    with pytest.raises(DevelopmentObservationError, match="case"):
        observer.assert_case("other")
    with pytest.raises(DevelopmentObservationError, match="identity"):
        DevelopmentObservation(
            "fixture", event_sink=lambda e: None, evaluator_identity="mutable-version"
        )

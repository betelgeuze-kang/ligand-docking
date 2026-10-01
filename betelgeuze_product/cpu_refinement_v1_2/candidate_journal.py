"""Immutable ordered candidate commits for the forthcoming comparison resume path.

Storage integrity is separate from candidate semantics: the caller must validate
every record on both commit and replay. An intent without a commit has unknown
lost work. This module does not itself enable workflow/CLI resume.
"""
from contextlib import contextmanager
import json
import re

from betelgeuze_product.reference_minimization_workflow import _directory, _publish, _read
from .provenance import ResearchError, canonical, digest, exact_fields, require_digest


def _copy(value):
    return json.loads(canonical(value))


def _envelope(value):
    return {"payload": value, "sha256": digest(value)}


def _load(path):
    value = json.loads(_read(path))
    exact_fields(value, {"payload", "sha256"})
    if value["sha256"] != digest(value["payload"]):
        raise ResearchError("candidate journal digest mismatch")
    return value["payload"]


class CandidateJournal:
    """Used only while open_journal holds the private directory writer lock."""

    def __init__(self, directory, binding, validate_record):
        self.directory = directory
        self.binding = _copy(binding)
        self.binding_sha256 = digest(binding)
        self.validate_record = validate_record
        self.records = []
        self.intents = []
        self.closed = False
        self._scan()

    def _scan(self):
        if (digest(self.binding) != self.binding_sha256
                or canonical(_load(self.directory / "binding.json")) != canonical(self.binding)):
            raise ResearchError("candidate journal binding changed")
        names = {p.name for p in self.directory.iterdir()}
        allowed = {"binding.json", ".minimization.lock"}
        records, intents = [], []
        # Index names once; retain every per-candidate byte and semantic check.
        indexed = {}
        for name in names:
            match = re.fullmatch(r"(candidate-\d{5})-(intent|record)-\d{5}\.json", name)
            if match:
                indexed.setdefault((match[1], match[2]), []).append(name)
        for index, key in enumerate(self.binding["candidate_keys"]):
            prefix = f"candidate-{index:05d}"
            attempts = sorted(indexed.get((prefix, "intent"), ()))
            if len(attempts) > 64:
                raise ResearchError("candidate retry capacity exceeded")
            for ordinal, name in enumerate(attempts):
                expected = f"{prefix}-intent-{ordinal:05d}.json"
                if name != expected or canonical(_load(self.directory / name)) != canonical({
                    "binding_sha256": self.binding_sha256, "index": index, "key": key, "ordinal": ordinal
                }):
                    raise ResearchError("candidate intent order or binding mismatch")
                allowed.add(name)
                # Interrupted commit publication is retained, never reused.
                partial = name.replace("-intent-", "-record-") + ".partial"
                if partial in names:
                    _read(self.directory / partial)
                    allowed.add(partial)
            committed = sorted(indexed.get((prefix, "record"), ()))
            if committed:
                if len(committed) != 1 or not attempts or index != len(records):
                    raise ResearchError("candidate commits must form one ordered prefix")
                name = committed[0]
                if name != attempts[-1].replace("-intent-", "-record-"):
                    raise ResearchError("candidate commit must bind latest intent")
                value = _load(self.directory / name)
                exact_fields(value, {"binding_sha256", "index", "key", "record"})
                if (value["binding_sha256"] != self.binding_sha256
                        or type(value["index"]) is not int or value["index"] != index or value["key"] != key):
                    raise ResearchError("candidate record identity mismatch")
                self.validate_record(key, _copy(value["record"]))
                records.append(value["record"])
                allowed.add(name)
            elif attempts and index != len(records):
                raise ResearchError("intent beyond first uncommitted candidate")
            intents.append(attempts)
        if names != allowed:
            raise ResearchError("unexpected candidate journal files")
        self.records, self.intents = records, intents

    @property
    def unknown_attempts(self):
        return sum(len(rows) - int(i < len(self.records)) for i, rows in enumerate(self.intents))

    def evaluate(self, index, compute):
        if self.closed:
            raise ResearchError("candidate journal lock is no longer held")
        if type(index) is not int or not 0 <= index < len(self.binding["candidate_keys"]):
            raise ResearchError("candidate index out of range")
        self._scan()
        if index < len(self.records):
            return _copy(self.records[index])
        if index != len(self.records):
            raise ResearchError("candidate execution must follow declared order")
        ordinal = len(self.intents[index])
        if ordinal >= 64:
            raise ResearchError("candidate retry capacity exceeded")
        key = self.binding["candidate_keys"][index]
        stem = f"candidate-{index:05d}"
        _publish(self.directory / f"{stem}-intent-{ordinal:05d}.json", _envelope({
            "binding_sha256": self.binding_sha256, "index": index, "key": key, "ordinal": ordinal}))
        record = _copy(compute())
        self.validate_record(key, _copy(record))
        _publish(self.directory / f"{stem}-record-{ordinal:05d}.json", _envelope({
            "binding_sha256": self.binding_sha256, "index": index, "key": key, "record": record}))
        self._scan()
        return _copy(record)


@contextmanager
def open_journal(path, binding, *, validate_record, resume=False):
    if type(resume) is not bool or not callable(validate_record):
        raise ResearchError("explicit resume flag and semantic validator required")
    exact_fields(binding, {"schema_id", "request_sha256", "implementation_sha256", "environment_sha256", "candidate_keys"})
    if binding["schema_id"] != "cpu_comparison_candidate_journal/1.0.0":
        raise ResearchError("unsupported candidate journal schema")
    for name in ("request_sha256", "implementation_sha256", "environment_sha256"):
        require_digest(binding[name])
    keys = binding["candidate_keys"]
    if type(keys) is not list or not 1 <= len(keys) <= 100000:
        raise ResearchError("bounded candidate key list required")
    for key in keys:
        require_digest(key)
    if len(set(keys)) != len(keys):
        raise ResearchError("duplicate candidate keys")
    binding = _copy(binding)
    with _directory(path, resume=resume) as directory:
        if resume:
            if _load(directory / "binding.json") != binding:
                raise ResearchError("candidate journal request/source/environment/order changed")
        else:
            _publish(directory / "binding.json", _envelope(binding))
        journal = CandidateJournal(directory, binding, validate_record)
        try:
            yield journal
        finally:
            journal.closed = True

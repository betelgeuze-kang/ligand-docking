from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_native_fixed64_context_lease_v1 import (
    ContractError,
    DEFAULT_CONTEXT_SOURCE,
    DEFAULT_CONTRACT,
    DEFAULT_DOCUMENTATION,
    DEFAULT_PIPELINE_SOURCE,
    DEFAULT_TEST_SOURCE,
    verify,
)


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )


def test_context_lease_contract_verifies() -> None:
    result = verify()

    assert result["status"] == "verified_static_non_authoritative"
    assert result["all_authority_false"] is True
    assert result["candidate_denominator"] == 64
    assert result["context_wrapper_may_drop_before_pipeline"] is True
    assert result["last_context_lease_destroys_native_context"] is True
    assert len(result["contract_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document["authority"].update(
            molecular_execution_authorized=True
        ),
        lambda document: document["lifecycle"].update(
            pipeline_owns_context_lease=False
        ),
        lambda document: document["lifecycle"].update(send=True),
        lambda document: document["scope"].update(candidate_denominator=63),
    ),
)
def test_context_lease_contract_rejects_policy_drift(
    tmp_path: Path, mutation
) -> None:
    document = json.loads(DEFAULT_CONTRACT.read_text(encoding="ascii"))
    mutation(document)
    contract = tmp_path / "contract.json"
    _write_json(contract, document)

    with pytest.raises(ContractError):
        verify(contract_path=contract)


@pytest.mark.parametrize(
    ("source_kind", "needle"),
    (
        ("context", "pub(crate) fn lease(&self) -> Rc<ContextInner>"),
        ("pipeline", "context_lease: context.lease(),"),
        (
            "test",
            "multiple_pipelines_keep_the_shared_context_alive_after_wrapper_drop",
        ),
        ("documentation", "External authority must reach blocker zero"),
    ),
)
def test_context_lease_contract_rejects_source_binding_drift(
    tmp_path: Path, source_kind: str, needle: str
) -> None:
    paths = {
        "context": DEFAULT_CONTEXT_SOURCE,
        "pipeline": DEFAULT_PIPELINE_SOURCE,
        "test": DEFAULT_TEST_SOURCE,
        "documentation": DEFAULT_DOCUMENTATION,
    }
    drifted = tmp_path / paths[source_kind].name
    source = paths[source_kind].read_text(encoding="utf-8")
    assert needle in source
    drifted.write_text(source.replace(needle, "DRIFTED", 1), encoding="utf-8")
    kwargs = {
        "contract_path": DEFAULT_CONTRACT,
        "context_source_path": DEFAULT_CONTEXT_SOURCE,
        "pipeline_source_path": DEFAULT_PIPELINE_SOURCE,
        "test_source_path": DEFAULT_TEST_SOURCE,
        "documentation_path": DEFAULT_DOCUMENTATION,
    }
    argument = {
        "context": "context_source_path",
        "pipeline": "pipeline_source_path",
        "test": "test_source_path",
        "documentation": "documentation_path",
    }[source_kind]
    kwargs[argument] = drifted

    with pytest.raises(ContractError, match="missing frozen contract snippets"):
        verify(**kwargs)


def test_context_lease_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    contract = tmp_path / "duplicate.json"
    contract.write_text(
        '{"schema_id":"first","schema_id":"second"}\n', encoding="ascii"
    )

    with pytest.raises(ContractError, match="duplicate JSON key"):
        verify(contract_path=contract)

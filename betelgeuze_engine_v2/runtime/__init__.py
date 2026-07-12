"""Runtime-input, vocabulary, and fingerprint contracts for Engine v2."""

from .conditioning import (
    RuntimeConditioningBatch,
    RuntimeConditioningError,
    build_runtime_conditioning_batch,
)
from .fingerprints import (
    FingerprintError,
    canonical_json_sha256,
    model_architecture_fingerprint,
    model_architecture_payload,
    runtime_contract_fingerprint,
    runtime_contract_payload,
    state_dict_fingerprint,
)
from .vocabulary import (
    RESIDUE_ID_BY_LABEL,
    RESIDUE_LABELS,
    RESIDUE_UNK_ID,
    RESIDUE_VOCABULARY,
    RESIDUE_VOCABULARY_SCHEMA_ID,
    RESIDUE_VOCABULARY_SIZE,
    ResidueVocabularyError,
    ResidueVocabularyMetadata,
    normalize_residue_ids,
    residue_one_hot,
)

__all__ = [
    "FingerprintError",
    "RESIDUE_ID_BY_LABEL",
    "RESIDUE_LABELS",
    "RESIDUE_UNK_ID",
    "RESIDUE_VOCABULARY",
    "RESIDUE_VOCABULARY_SCHEMA_ID",
    "RESIDUE_VOCABULARY_SIZE",
    "ResidueVocabularyError",
    "ResidueVocabularyMetadata",
    "RuntimeConditioningBatch",
    "RuntimeConditioningError",
    "build_runtime_conditioning_batch",
    "canonical_json_sha256",
    "model_architecture_fingerprint",
    "model_architecture_payload",
    "normalize_residue_ids",
    "residue_one_hot",
    "runtime_contract_fingerprint",
    "runtime_contract_payload",
    "state_dict_fingerprint",
]

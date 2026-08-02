from __future__ import annotations

from dataclasses import replace

import pytest

import betelgeuze_engine_v2.docking as docking_public
from betelgeuze_engine_v2.docking.backend_abi import (
    BackendABIError,
    BackendSourceBinding,
    DeviceABI,
    DeviceKind,
    EngineV2ABIStage,
    EngineV2Backend,
    EngineV2BackendReceipt,
    EngineV2NativeABI,
    HIP_FAST_BUILD_FLAGS,
    HIP_SAFE_BUILD_FLAGS,
    MathMode,
    StageABI,
    StreamABI,
    StreamKind,
    StreamOwnership,
    SynchronizationProtocol,
    TensorDType,
    TensorRole,
    build_engine_v2_native_abi,
    canonical_backend,
    compatibility_alias,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ScorerBackend


def _cpu_device() -> DeviceABI:
    return DeviceABI(
        kind=DeviceKind.CPU,
        ordinal=0,
        architecture="x86_64",
        runtime_name="cpython",
        runtime_version="3.11.9",
        device_identity_sha256="a" * 64,
    )


def _hip_device(architecture: str = "gfx1030") -> DeviceABI:
    return DeviceABI(
        kind=DeviceKind.HIP,
        ordinal=0,
        architecture=architecture,
        runtime_name="rocm",
        runtime_version="6.3.0",
        device_identity_sha256="b" * 64,
    )


def _stream(device: DeviceABI) -> StreamABI:
    if device.kind is DeviceKind.CPU:
        return StreamABI(
            kind=StreamKind.HOST_SYNCHRONOUS,
            ownership=StreamOwnership.BACKEND,
            synchronization=SynchronizationProtocol.HOST_BLOCKING,
            device_fingerprint_sha256=device.fingerprint_sha256,
        )
    return StreamABI(
        kind=StreamKind.HIP_STREAM,
        ownership=StreamOwnership.CALLER,
        synchronization=SynchronizationProtocol.CALLER_EVENT_HANDOFF,
        device_fingerprint_sha256=device.fingerprint_sha256,
        stream_ordinal=2,
    )


def _abi(
    backend: EngineV2Backend,
    device: DeviceABI | None = None,
    *,
    max_batch_size: int = 64,
) -> EngineV2NativeABI:
    if device is None:
        device = (
            _hip_device()
            if backend in {EngineV2Backend.HIP_SAFE, EngineV2Backend.HIP_FAST}
            else _cpu_device()
        )
    return build_engine_v2_native_abi(
        backend=backend,
        device=device,
        stream=_stream(device),
        receptor_atom_count=100,
        receptor_feature_count=16,
        ligand_atom_count=12,
        pair_capacity=4096,
        max_batch_size=max_batch_size,
    )


def _source_binding(implementation: str = "c") -> BackendSourceBinding:
    return BackendSourceBinding(
        exact_source_receipt_sha256="1" * 64,
        implementation_source_sha256=implementation * 64,
        algorithm_profile_id="engine-v2-stage0-algorithm-v1",
        algorithm_profile_sha256="2" * 64,
        execution_profile_id="engine-v2-stage0-execution-v1",
        execution_profile_sha256="3" * 64,
        native_build_provenance_sha256="4" * 64,
    )


def backend_receipt(
    backend: EngineV2Backend,
    *,
    architecture: str = "gfx1030",
    exact_source: str = "1",
    algorithm_profile: str = "2",
    execution_profile: str = "3",
) -> EngineV2BackendReceipt:
    device = (
        _hip_device(architecture)
        if backend in {EngineV2Backend.HIP_SAFE, EngineV2Backend.HIP_FAST}
        else _cpu_device()
    )
    binding = replace(
        _source_binding(
            "e"
            if backend in {EngineV2Backend.HIP_SAFE, EngineV2Backend.HIP_FAST}
            else "c"
        ),
        exact_source_receipt_sha256=exact_source * 64,
        algorithm_profile_sha256=algorithm_profile * 64,
        execution_profile_sha256=execution_profile * 64,
    )
    common = {
        "native_abi": _abi(backend, device),
        "source_binding": binding,
        "backend_version": "contract-only-1",
        "execution_available": backend
        not in {
            EngineV2Backend.HIP_SAFE,
            EngineV2Backend.HIP_FAST,
        },
    }
    if backend is EngineV2Backend.PYTHON_REFERENCE:
        return EngineV2BackendReceipt(**common)
    if backend is EngineV2Backend.RUST_CPU:
        return EngineV2BackendReceipt(
            **common,
            artifact_sha256="d" * 64,
            compiler_name="rustc",
            compiler_version="1.84.0",
            target_triple="x86_64-unknown-linux-gnu",
            build_flags=("-Copt-level=2",),
        )
    return EngineV2BackendReceipt(
        **common,
        artifact_sha256="d" * 64,
        compiler_name="hipcc",
        compiler_version="6.3.0",
        target_triple="amdgcn-amd-amdhsa",
        build_flags=(
            HIP_SAFE_BUILD_FLAGS
            if backend is EngineV2Backend.HIP_SAFE
            else HIP_FAST_BUILD_FLAGS
        ),
        math_mode=(
            MathMode.STRICT_BINARY64
            if backend is EngineV2Backend.HIP_SAFE
            else MathMode.PARITY_QUALIFIED_FAST
        ),
        hip_safe_qualification_receipt_sha256=(
            "" if backend is EngineV2Backend.HIP_SAFE else "f" * 64
        ),
    )


def _replace_stage(
    abi: EngineV2NativeABI, stage: EngineV2ABIStage, replacement: StageABI
) -> EngineV2NativeABI:
    return replace(
        abi,
        stages=tuple(
            replacement if value.stage is stage else value for value in abi.stages
        ),
    )


def test_current_scorer_backend_names_are_compatibility_only() -> None:
    assert docking_public.EngineV2Backend is EngineV2Backend
    assert docking_public.verify_gpu_architecture_qualification is not None
    assert (
        canonical_backend(ScorerBackend.PYTHON_REFERENCE)
        is EngineV2Backend.PYTHON_REFERENCE
    )
    assert (
        canonical_backend(ScorerBackend.RUST_CPU_REQUIRED) is EngineV2Backend.RUST_CPU
    )
    assert canonical_backend(ScorerBackend.CPP_HIP_REQUIRED) is EngineV2Backend.HIP_SAFE
    assert compatibility_alias(ScorerBackend.CPP_HIP_REQUIRED) == "cpp_hip_required"

    device = _hip_device()
    with pytest.raises(BackendABIError, match="legacy backend aliases"):
        build_engine_v2_native_abi(
            backend=ScorerBackend.CPP_HIP_REQUIRED,
            device=device,
            stream=_stream(device),
            receptor_atom_count=100,
            receptor_feature_count=16,
            ligand_atom_count=12,
            pair_capacity=4096,
        )


def test_complete_versioned_stage_tensor_stream_device_abi_is_identity_bound() -> None:
    abi = _abi(EngineV2Backend.PYTHON_REFERENCE)
    payload = abi.to_dict()

    assert payload["abi_version"] == "1.1.0"
    assert payload["backend"] == "python_reference"
    assert payload["implicit_fallback_allowed"] is False
    assert payload["stream"]["raw_pointer_serialized"] is False
    assert payload["stage_order"] == [value.value for value in EngineV2ABIStage]
    assert len(payload["stages"]) == 11
    scorer = abi.stage(EngineV2ABIStage.SCORER_V1_8TERM)
    assert scorer.tensor(TensorRole.SCORER_TERMS).shape == (64, 8)
    top_k = abi.stage(EngineV2ABIStage.STABLE_TOP_K)
    assert top_k.tensor(TensorRole.FAILURE_CODES).shape == (64,)
    assert top_k.tensor(TensorRole.TOPK_COUNT).shape == (1,)
    assert len(abi.fingerprint_sha256) == 64

    foreign = _abi(EngineV2Backend.HIP_SAFE)
    with pytest.raises(BackendABIError, match="tensor and device identities"):
        replace(abi, stages=foreign.stages)


def test_stage_contract_rejects_unknown_missing_extra_or_reordered_roles() -> None:
    abi = _abi(EngineV2Backend.PYTHON_REFERENCE)
    scorer = abi.stage(EngineV2ABIStage.SCORER_V1_8TERM)
    with pytest.raises(BackendABIError, match="unsupported tensor role"):
        replace(scorer.tensors[0], role="arbitrary_kernel_buffer")
    with pytest.raises(BackendABIError, match="exact ordered tensor-role signature"):
        replace(scorer, tensors=scorer.tensors[:-1])
    with pytest.raises(BackendABIError, match="exact ordered tensor-role signature"):
        replace(scorer, tensors=(*scorer.tensors, scorer.tensors[-1]))
    with pytest.raises(BackendABIError, match="exact ordered tensor-role signature"):
        replace(scorer, tensors=tuple(reversed(scorer.tensors)))
    with pytest.raises(BackendABIError, match="exact Engine V2 stage order"):
        replace(abi, stages=abi.stages[:-1])


def test_stage_contract_rejects_dtype_shape_and_cross_stage_drift() -> None:
    abi = _abi(EngineV2Backend.PYTHON_REFERENCE)
    scorer = abi.stage(EngineV2ABIStage.SCORER_V1_8TERM)
    terms = scorer.tensor(TensorRole.SCORER_TERMS)
    with pytest.raises(BackendABIError, match="exact tensor contract"):
        replace(
            scorer,
            tensors=tuple(
                replace(value, dtype=TensorDType.FLOAT32, strides_bytes=(32, 4))
                if value.role is TensorRole.SCORER_TERMS
                else value
                for value in scorer.tensors
            ),
        )
    with pytest.raises(BackendABIError, match="trailing shape"):
        replace(
            scorer,
            tensors=tuple(
                replace(terms, shape=(64, 7), strides_bytes=(56, 8))
                if value.role is TensorRole.SCORER_TERMS
                else value
                for value in scorer.tensors
            ),
        )

    smaller = _abi(EngineV2Backend.PYTHON_REFERENCE, max_batch_size=63)
    with pytest.raises(BackendABIError, match="one candidate tensor"):
        _replace_stage(
            abi,
            EngineV2ABIStage.POSE_VALIDITY,
            smaller.stage(EngineV2ABIStage.POSE_VALIDITY),
        )


def test_tensor_contract_represents_empty_pair_lists_but_rejects_negative_capacity() -> (
    None
):
    abi = build_engine_v2_native_abi(
        backend=EngineV2Backend.PYTHON_REFERENCE,
        device=_cpu_device(),
        stream=_stream(_cpu_device()),
        receptor_atom_count=100,
        receptor_feature_count=16,
        ligand_atom_count=12,
        pair_capacity=0,
    )
    pair_indices = abi.stage(EngineV2ABIStage.PAIR_LIST).tensor(TensorRole.PAIR_INDICES)
    assert pair_indices.shape == (0, 3)
    assert pair_indices.strides_bytes == (12, 4)
    with pytest.raises(BackendABIError, match="non-negative"):
        build_engine_v2_native_abi(
            backend=EngineV2Backend.PYTHON_REFERENCE,
            device=_cpu_device(),
            stream=_stream(_cpu_device()),
            receptor_atom_count=100,
            receptor_feature_count=16,
            ligand_atom_count=12,
            pair_capacity=-1,
        )


def test_backend_receipt_embeds_typed_abi_and_exact_source_profile_binding() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE, architecture="gfx1100")
    payload = receipt.to_dict()

    assert receipt.backend is EngineV2Backend.HIP_SAFE
    assert receipt.architecture == "gfx1100"
    assert (
        payload["abi_fingerprint_sha256"] == payload["native_abi"]["fingerprint_sha256"]
    )
    assert payload["architecture"] == payload["native_abi"]["device"]["architecture"]
    assert (
        payload["source_binding_receipt_sha256"]
        == payload["source_binding"]["receipt_sha256"]
    )
    assert (
        payload["implementation_source_sha256"]
        == payload["source_binding"]["implementation_source_sha256"]
    )


@pytest.mark.parametrize(
    "unsafe_flags",
    [
        ("-Ofast",),
        ("-funsafe-math-optimizations",),
        ("-ffinite-math-only",),
        ("-fno-signed-zeros",),
        ("-ffast-math",),
        ("--rocm-device-library-fallback",),
        ("-munsafe-fp-atomics",),
    ],
)
def test_hip_safe_requires_exact_predeclared_build_profile(
    unsafe_flags: tuple[str, ...],
) -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    with pytest.raises(BackendABIError, match="exact predeclared build profile"):
        replace(receipt, build_flags=unsafe_flags)


def test_hip_safe_contract_is_strict_and_product_unavailable() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    assert receipt.execution_available is False
    assert receipt.to_dict()["implicit_fallback_allowed"] is False
    with pytest.raises(BackendABIError, match="declared unavailable"):
        replace(receipt, execution_available=True)
    with pytest.raises(BackendABIError, match="must be deterministic"):
        replace(receipt, deterministic=False)
    with pytest.raises(BackendABIError, match="unsafe floating-point atomics"):
        replace(receipt, unsafe_fp_atomics=True)
    with pytest.raises(BackendABIError, match="device-library fallback"):
        replace(receipt, rocm_device_library_fallback_used=True)


def test_hip_fast_requires_fast_abi_profile_and_prior_safe_qualification() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_FAST)
    assert receipt.execution_available is False
    assert receipt.math_mode is MathMode.PARITY_QUALIFIED_FAST
    with pytest.raises(BackendABIError, match="prior hip_safe qualification"):
        replace(receipt, hip_safe_qualification_receipt_sha256="")
    with pytest.raises(BackendABIError, match="parity-qualified fast math"):
        replace(receipt, math_mode=MathMode.STRICT_BINARY64)
    with pytest.raises(BackendABIError, match="exact predeclared build profile"):
        replace(receipt, build_flags=HIP_SAFE_BUILD_FLAGS)
    with pytest.raises(BackendABIError, match="reserved for hip_fast"):
        replace(_abi(EngineV2Backend.HIP_SAFE), fast_math_allowed=True)
    with pytest.raises(BackendABIError, match="explicit fast-math ABI mode"):
        replace(_abi(EngineV2Backend.HIP_FAST), fast_math_allowed=False)

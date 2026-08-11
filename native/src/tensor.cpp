#include "internal.hpp"

#include <cstdint>
#include <limits>
#include <type_traits>

namespace betelgeuze::native {
namespace {

static_assert(sizeof(float) == 4, "BG_SCALAR_F32 requires IEEE-width float");
static_assert(sizeof(double) == 8, "BG_SCALAR_F64 requires IEEE-width double");
static_assert(std::numeric_limits<float>::is_iec559, "BG_SCALAR_F32 requires IEEE 754");
static_assert(std::numeric_limits<double>::is_iec559, "BG_SCALAR_F64 requires IEEE 754");
static_assert(sizeof(int32_t) == 4, "BG_SCALAR_I32 requires 32-bit int32_t");
static_assert(sizeof(int64_t) == 8, "BG_SCALAR_I64 requires 64-bit int64_t");

bg_status scalar_layout(
    bg_scalar_type scalar_type,
    uint64_t *size,
    std::uintptr_t *alignment) noexcept {
    if (size == nullptr || alignment == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "scalar layout output is null");
    }
    switch (scalar_type) {
        case BG_SCALAR_F32:
            *size = sizeof(float);
            *alignment = alignof(float);
            return BG_STATUS_OK;
        case BG_SCALAR_F64:
            *size = sizeof(double);
            *alignment = alignof(double);
            return BG_STATUS_OK;
        case BG_SCALAR_I32:
            *size = sizeof(int32_t);
            *alignment = alignof(int32_t);
            return BG_STATUS_OK;
        case BG_SCALAR_I64:
            *size = sizeof(int64_t);
            *alignment = alignof(int64_t);
            return BG_STATUS_OK;
        case BG_SCALAR_U8:
            *size = sizeof(uint8_t);
            *alignment = alignof(uint8_t);
            return BG_STATUS_OK;
        default:
            return fail(BG_STATUS_INVALID_ARGUMENT, "unsupported tensor scalar_type");
    }
}

bg_status checked_multiply(
    uint64_t left,
    uint64_t right,
    uint64_t *product,
    const char *message) noexcept {
    if (product == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "tensor product output is null");
    }
    if (left != UINT64_C(0) &&
        right > std::numeric_limits<uint64_t>::max() / left) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, message);
    }
    *product = left * right;
    return BG_STATUS_OK;
}

bg_status validate_memory(
    bg_memory_kind memory_kind,
    int32_t device_ordinal) noexcept {
    switch (memory_kind) {
        case BG_MEMORY_HOST:
            if (device_ordinal != 0) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "host tensors require device_ordinal 0");
            }
            return BG_STATUS_OK;
        case BG_MEMORY_HIP_DEVICE:
        case BG_MEMORY_HIP_MANAGED:
            if (device_ordinal < 0) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "HIP tensors require a non-negative device_ordinal");
            }
            return BG_STATUS_OK;
        default:
            return fail(BG_STATUS_INVALID_ARGUMENT, "unsupported tensor memory_kind");
    }
}

template <typename Tensor>
bg_status validate_tensor_descriptor(
    const Tensor &tensor,
    uint64_t *element_count,
    uint64_t *required_bytes) noexcept {
    static_assert(
        std::is_same_v<Tensor, bg_tensor_view_v1> ||
        std::is_same_v<Tensor, bg_mutable_tensor_view_v1>);

    bg_status status = validate_descriptor_header(
        tensor.struct_size,
        sizeof(Tensor),
        tensor.abi_version,
        "tensor struct_size does not match ABI v1",
        "tensor abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (element_count == nullptr || required_bytes == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "tensor validation outputs must not be null");
    }
    *element_count = UINT64_C(0);
    *required_bytes = UINT64_C(0);
    if (!reserved_is_zero(tensor.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "tensor reserved fields must be zero");
    }
    if (tensor.flags != BG_TENSOR_FLAG_C_CONTIGUOUS) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "tensor flags must be BG_TENSOR_FLAG_C_CONTIGUOUS");
    }
    if (tensor.rank > BG_TENSOR_MAX_RANK) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "tensor rank exceeds ABI v1 capacity");
    }
    status = validate_memory(tensor.memory_kind, tensor.device_ordinal);
    if (status != BG_STATUS_OK) {
        return status;
    }

    uint64_t scalar_size = UINT64_C(0);
    std::uintptr_t scalar_alignment = 0;
    status = scalar_layout(tensor.scalar_type, &scalar_size, &scalar_alignment);
    if (status != BG_STATUS_OK) {
        return status;
    }

    for (uint32_t index = tensor.rank; index < BG_TENSOR_MAX_RANK; ++index) {
        if (tensor.shape[index] != UINT64_C(0) ||
            tensor.stride_bytes[index] != INT64_C(0)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "tensor shape and strides outside rank must be zero");
        }
    }

    uint64_t count = UINT64_C(1);
    uint64_t expected_stride = scalar_size;
    for (uint32_t offset = 0; offset < tensor.rank; ++offset) {
        const uint32_t index = tensor.rank - UINT32_C(1) - offset;
        if (expected_stride >
            static_cast<uint64_t>(std::numeric_limits<int64_t>::max())) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "tensor contiguous stride exceeds int64 capacity");
        }
        if (tensor.stride_bytes[index] !=
            static_cast<int64_t>(expected_stride)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "tensor strides are not compact C-contiguous");
        }
        status = checked_multiply(
            count,
            tensor.shape[index],
            &count,
            "tensor element count overflows uint64");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_multiply(
            expected_stride,
            tensor.shape[index],
            &expected_stride,
            "tensor contiguous stride overflows uint64");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }

    uint64_t bytes = UINT64_C(0);
    status = checked_multiply(
        count,
        scalar_size,
        &bytes,
        "tensor byte count overflows uint64");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (tensor.byte_capacity != bytes) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "tensor byte_capacity must equal the compact tensor byte count");
    }
    if (bytes == UINT64_C(0)) {
        if (tensor.data != nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "empty tensors require a null data pointer");
        }
    } else {
        if (tensor.data == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "non-empty tensors require a data pointer");
        }
        if (reinterpret_cast<std::uintptr_t>(tensor.data) % scalar_alignment != 0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "tensor data pointer does not satisfy scalar alignment");
        }
    }

    *element_count = count;
    *required_bytes = bytes;
    return BG_STATUS_OK;
}

template <typename Tensor>
bg_status initialize_tensor(
    Tensor *tensor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version,
    const char *null_error,
    const char *size_error) noexcept {
    const bg_status status = validate_initializer_compatibility(
        tensor,
        caller_struct_size,
        sizeof(Tensor),
        caller_abi_version,
        null_error,
        size_error,
        "tensor initializer ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    *tensor = Tensor{};
    tensor->struct_size = static_cast<uint32_t>(sizeof(Tensor));
    tensor->abi_version = BG_ABI_VERSION;
    tensor->memory_kind = BG_MEMORY_HOST;
    tensor->device_ordinal = 0;
    tensor->flags = BG_TENSOR_FLAG_C_CONTIGUOUS;
    return BG_STATUS_OK;
}

}  // namespace
}  // namespace betelgeuze::native

extern "C" BG_API bg_status BG_CALL bg_tensor_view_v1_init(
    bg_tensor_view_v1 *tensor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        return initialize_tensor(
            tensor,
            caller_struct_size,
            caller_abi_version,
            "bg_tensor_view_v1 pointer must not be null",
            "bg_tensor_view_v1 initializer size does not match the native ABI");
    });
}

extern "C" BG_API bg_status BG_CALL bg_mutable_tensor_view_v1_init(
    bg_mutable_tensor_view_v1 *tensor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        return initialize_tensor(
            tensor,
            caller_struct_size,
            caller_abi_version,
            "bg_mutable_tensor_view_v1 pointer must not be null",
            "bg_mutable_tensor_view_v1 initializer size does not match the native ABI");
    });
}

extern "C" BG_API bg_status BG_CALL bg_stream_v1_init(
    bg_stream_v1 *stream,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            stream,
            caller_struct_size,
            sizeof(bg_stream_v1),
            caller_abi_version,
            "bg_stream_v1 pointer must not be null",
            "bg_stream_v1 initializer size does not match the native ABI",
            "bg_stream_v1 initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *stream = bg_stream_v1{};
        stream->struct_size = static_cast<uint32_t>(sizeof(bg_stream_v1));
        stream->abi_version = BG_ABI_VERSION;
        stream->backend = BG_BACKEND_RUST_CPU;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_tensor_view_v1_validate(
    const bg_tensor_view_v1 *tensor,
    uint64_t *element_count,
    uint64_t *required_bytes) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    if (element_count != nullptr) {
        *element_count = UINT64_C(0);
    }
    if (required_bytes != nullptr) {
        *required_bytes = UINT64_C(0);
    }
    return guarded_status([&]() -> bg_status {
        if (tensor == nullptr) {
            return fail(BG_STATUS_INVALID_ARGUMENT, "tensor pointer must not be null");
        }
        return validate_tensor_descriptor(*tensor, element_count, required_bytes);
    });
}

extern "C" BG_API bg_status BG_CALL bg_mutable_tensor_view_v1_validate(
    const bg_mutable_tensor_view_v1 *tensor,
    uint64_t *element_count,
    uint64_t *required_bytes) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    if (element_count != nullptr) {
        *element_count = UINT64_C(0);
    }
    if (required_bytes != nullptr) {
        *required_bytes = UINT64_C(0);
    }
    return guarded_status([&]() -> bg_status {
        if (tensor == nullptr) {
            return fail(BG_STATUS_INVALID_ARGUMENT, "mutable tensor pointer must not be null");
        }
        return validate_tensor_descriptor(*tensor, element_count, required_bytes);
    });
}

extern "C" BG_API bg_status BG_CALL bg_stream_v1_validate(
    const bg_stream_v1 *stream) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (stream == nullptr) {
            return fail(BG_STATUS_INVALID_ARGUMENT, "stream pointer must not be null");
        }
        bg_status status = validate_descriptor_header(
            stream->struct_size,
            sizeof(bg_stream_v1),
            stream->abi_version,
            "bg_stream_v1 struct_size does not match ABI v1",
            "bg_stream_v1 abi_version does not match the native library");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!reserved_is_zero(stream->reserved)) {
            return fail(BG_STATUS_INVALID_ARGUMENT, "stream reserved fields must be zero");
        }
        switch (stream->backend) {
            case BG_BACKEND_RUST_CPU:
                if (stream->device_ordinal != 0 ||
                    stream->native_handle != UINT64_C(0) ||
                    stream->flags != UINT64_C(0)) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "rust_cpu stream requires ordinal, handle, and flags 0");
                }
                return BG_STATUS_OK;
            case BG_BACKEND_HIP_SAFE:
            case BG_BACKEND_HIP_FAST:
                if (stream->device_ordinal < 0) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "HIP stream requires a non-negative device_ordinal");
                }
                if (stream->native_handle == UINT64_C(0)) {
                    if (stream->flags != UINT64_C(0)) {
                        return fail(
                            BG_STATUS_INVALID_ARGUMENT,
                            "default HIP stream requires flags 0");
                    }
                } else if (stream->flags != BG_STREAM_FLAG_BORROWED) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "non-default HIP stream must be explicitly borrowed");
                }
                return BG_STATUS_OK;
            default:
                return fail(
                    BG_STATUS_UNSUPPORTED_BACKEND,
                    "stream backend must be rust_cpu, hip_safe, or hip_fast");
        }
    });
}

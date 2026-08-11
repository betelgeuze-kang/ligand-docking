#include <betelgeuze/engine.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(BG_ABI_VERSION == UINT32_C(1), "unexpected ABI version");
_Static_assert(BG_STATUS_OK == 0, "unexpected success status");
_Static_assert(
    BG_BACKEND_CPP_CPU_REFERENCE == 1,
    "unexpected C++ CPU reference backend value");
_Static_assert(BG_BACKEND_RUST_CPU == 2, "unexpected Rust CPU backend value");
_Static_assert(BG_BACKEND_HIP == 3, "unexpected HIP backend value");
_Static_assert(BG_BACKEND_HIP_FAST == 4, "unexpected HIP fast backend value");
_Static_assert(
    BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL == 1,
    "unexpected canonical unit-system value");
_Static_assert(sizeof(bg_status) == sizeof(int32_t), "bg_status width changed");
_Static_assert(sizeof(bg_backend) == sizeof(int32_t), "bg_backend width changed");
_Static_assert(
    sizeof(bg_unit_system) == sizeof(int32_t),
    "bg_unit_system width changed");
_Static_assert(sizeof(bg_context_options) == 64, "context options ABI changed");
_Static_assert(sizeof(bg_stream_v1) == 64, "stream ABI changed");

void betelgeuze_sys_header_c11_typecheck(void) {
    bg_context *context = NULL;
    bg_system *system = NULL;
    bg_context_options options;
    bg_particle_soa particles;
    bg_particle_soa_view view;
    bg_position_soa positions;
    bg_tensor_view_v1 tensor;
    bg_mutable_tensor_view_v1 mutable_tensor;
    bg_stream_v1 stream;
    (void)context;
    (void)system;
    (void)options;
    (void)particles;
    (void)view;
    (void)positions;
    (void)tensor;
    (void)mutable_tensor;
    (void)stream;
}

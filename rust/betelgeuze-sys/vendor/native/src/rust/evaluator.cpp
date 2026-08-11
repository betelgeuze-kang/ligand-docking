#include "evaluator.hpp"

#include "../internal.hpp"
#include "provider.h"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <utility>

namespace betelgeuze::native::rust_cpu {
namespace {

template <typename Value>
const Value *data_or_null(const std::vector<Value> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

bg_status normalize_provider_status(int32_t status) noexcept {
    switch (status) {
        case BG_STATUS_OK:
        case BG_STATUS_INVALID_ARGUMENT:
        case BG_STATUS_ABI_MISMATCH:
        case BG_STATUS_UNSUPPORTED_BACKEND:
        case BG_STATUS_BACKEND_UNAVAILABLE:
        case BG_STATUS_OUT_OF_MEMORY:
        case BG_STATUS_CAPACITY_OVERFLOW:
        case BG_STATUS_BUFFER_TOO_SMALL:
        case BG_STATUS_BACKEND_ERROR:
        case BG_STATUS_INTERNAL_ERROR:
        case BG_STATUS_NUMERICAL_ERROR:
            return status;
        default:
            return BG_STATUS_INTERNAL_ERROR;
    }
}

}  // namespace

bg_status evaluate(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation) {
    static_assert(std::is_standard_layout_v<bg_forcefield::Pair>);
    static_assert(std::is_standard_layout_v<bg_forcefield::PairScale>);
    static_assert(sizeof(bg_forcefield::Pair) == sizeof(bg_rust_cpu_pair_v1));
    static_assert(alignof(bg_forcefield::Pair) == alignof(bg_rust_cpu_pair_v1));
    static_assert(offsetof(bg_forcefield::Pair, atom_i) ==
                  offsetof(bg_rust_cpu_pair_v1, atom_i));
    static_assert(offsetof(bg_forcefield::Pair, atom_j) ==
                  offsetof(bg_rust_cpu_pair_v1, atom_j));
    static_assert(
        sizeof(bg_forcefield::PairScale) == sizeof(bg_rust_cpu_pair_scale_v1));
    static_assert(
        alignof(bg_forcefield::PairScale) == alignof(bg_rust_cpu_pair_scale_v1));
    static_assert(offsetof(bg_forcefield::PairScale, pair) == 0);
    static_assert(offsetof(bg_forcefield::PairScale, lennard_jones) ==
                  offsetof(bg_rust_cpu_pair_scale_v1, lennard_jones));
    static_assert(offsetof(bg_forcefield::PairScale, coulomb) ==
                  offsetof(bg_rust_cpu_pair_scale_v1, coulomb));

    if (out_evaluation == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "rust_cpu evaluation output is null");
    }
    if (bg_rust_cpu_provider_abi_version_v1() !=
        BG_RUST_CPU_PROVIDER_ABI_VERSION) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "rust_cpu provider ABI is unavailable or incompatible");
    }

    bg_rust_cpu_system_v1 provider_system{};
    provider_system.struct_size =
        static_cast<uint32_t>(sizeof(provider_system));
    provider_system.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    provider_system.atom_count = system.position_x.size();
    provider_system.position_x = data_or_null(system.position_x);
    provider_system.position_y = data_or_null(system.position_y);
    provider_system.position_z = data_or_null(system.position_z);
    provider_system.charge = data_or_null(system.charge);

    bg_rust_cpu_forcefield_v1 provider_forcefield{};
    provider_forcefield.struct_size =
        static_cast<uint32_t>(sizeof(provider_forcefield));
    provider_forcefield.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    provider_forcefield.atom_count = forcefield.atom_count;
    provider_forcefield.sigma = data_or_null(forcefield.sigma);
    provider_forcefield.epsilon = data_or_null(forcefield.epsilon);
    provider_forcefield.bonds = {
        forcefield.bonds.atom_i.size(),
        data_or_null(forcefield.bonds.atom_i),
        data_or_null(forcefield.bonds.atom_j),
        data_or_null(forcefield.bonds.equilibrium),
        data_or_null(forcefield.bonds.force_constant),
    };
    provider_forcefield.angles = {
        forcefield.angles.atom_i.size(),
        data_or_null(forcefield.angles.atom_i),
        data_or_null(forcefield.angles.atom_j),
        data_or_null(forcefield.angles.atom_k),
        data_or_null(forcefield.angles.equilibrium),
        data_or_null(forcefield.angles.force_constant),
    };
    provider_forcefield.torsions = {
        forcefield.torsions.atom_i.size(),
        data_or_null(forcefield.torsions.atom_i),
        data_or_null(forcefield.torsions.atom_j),
        data_or_null(forcefield.torsions.atom_k),
        data_or_null(forcefield.torsions.atom_l),
        data_or_null(forcefield.torsions.periodicity),
        data_or_null(forcefield.torsions.phase),
        data_or_null(forcefield.torsions.amplitude),
    };
    provider_forcefield.exclusion_count = forcefield.exclusions.size();
    provider_forcefield.exclusions =
        reinterpret_cast<const bg_rust_cpu_pair_v1 *>(
            data_or_null(forcefield.exclusions));
    provider_forcefield.pair_scale_count = forcefield.pair_scales.size();
    provider_forcefield.pair_scales =
        reinterpret_cast<const bg_rust_cpu_pair_scale_v1 *>(
            data_or_null(forcefield.pair_scales));
    provider_forcefield.periodic_axes_mask = forcefield.periodic_axes_mask;
    provider_forcefield.cell_lengths[0] = forcefield.cell_lengths[0];
    provider_forcefield.cell_lengths[1] = forcefield.cell_lengths[1];
    provider_forcefield.cell_lengths[2] = forcefield.cell_lengths[2];
    provider_forcefield.cutoff = forcefield.cutoff;
    provider_forcefield.switch_start = forcefield.switch_start;
    provider_forcefield.dielectric = forcefield.dielectric;
    provider_forcefield.screening_kappa = forcefield.screening_kappa;
    provider_forcefield.minimum_pair_distance =
        forcefield.minimum_pair_distance;

    cpu::Evaluation candidate;
    if (compute_forces) {
        candidate.force_x.assign(forcefield.atom_count, 0.0);
        candidate.force_y.assign(forcefield.atom_count, 0.0);
        candidate.force_z.assign(forcefield.atom_count, 0.0);
    }
    bg_rust_cpu_energy_v1 provider_energy{};
    provider_energy.struct_size =
        static_cast<uint32_t>(sizeof(provider_energy));
    provider_energy.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    bg_rust_cpu_force_output_v1 provider_forces{};
    provider_forces.struct_size =
        static_cast<uint32_t>(sizeof(provider_forces));
    provider_forces.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    provider_forces.capacity = forcefield.atom_count;
    provider_forces.x = compute_forces ? candidate.force_x.data() : nullptr;
    provider_forces.y = compute_forces ? candidate.force_y.data() : nullptr;
    provider_forces.z = compute_forces ? candidate.force_z.data() : nullptr;
    bg_rust_cpu_error_v1 provider_error{};
    provider_error.struct_size = static_cast<uint32_t>(sizeof(provider_error));
    provider_error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;

    const int32_t raw_status = bg_rust_cpu_evaluate_v1(
        &provider_system,
        &provider_forcefield,
        compute_forces ? UINT8_C(1) : UINT8_C(0),
        &provider_energy,
        compute_forces ? &provider_forces : nullptr,
        &provider_error);
    const bg_status status = normalize_provider_status(raw_status);
    if (status != BG_STATUS_OK) {
        provider_error.message[BG_RUST_CPU_ERROR_CAPACITY - 1U] = '\0';
        const char *message = provider_error.message[0] == '\0'
                                  ? "rust_cpu provider failed without a diagnostic"
                                  : provider_error.message;
        return fail(status, message);
    }

    candidate.energy.struct_size =
        static_cast<uint32_t>(sizeof(candidate.energy));
    candidate.energy.abi_version = BG_ABI_VERSION;
    candidate.energy.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    candidate.energy.harmonic_bond_kcal_per_mol =
        provider_energy.harmonic_bond;
    candidate.energy.harmonic_angle_kcal_per_mol =
        provider_energy.harmonic_angle;
    candidate.energy.periodic_torsion_kcal_per_mol =
        provider_energy.periodic_torsion;
    candidate.energy.lennard_jones_kcal_per_mol =
        provider_energy.lennard_jones;
    candidate.energy.coulomb_kcal_per_mol = provider_energy.coulomb;
    candidate.energy.total_kcal_per_mol = provider_energy.total;
    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::rust_cpu

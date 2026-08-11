#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <type_traits>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kLigandAtoms = 4;

struct Fixture final {
    std::array<double, 4> receptor_x = {3.0, 2.0, 2.0, 4.0};
    std::array<double, 4> receptor_y = {0.0, 3.0, 2.0, 1.0};
    std::array<double, 4> receptor_z = {0.0, 0.0, 0.0, 1.0};
    std::array<double, 4> receptor_charge = {-0.5, 0.2, 0.3, 0.0};
    std::array<double, 4> receptor_radius = {1.5, 1.55, 1.0, 1.7};
    std::array<double, 4> receptor_epsilon = {0.2, 0.18, 0.05, 0.25};
    std::array<uint8_t, 4> receptor_hydrophobic = {0, 0, 0, 1};
    std::array<uint8_t, 4> receptor_acceptor = {1, 0, 0, 0};

    std::array<double, 4> ligand_x = {0.0, 1.0, 1.0, 1.0};
    std::array<double, 4> ligand_y = {0.0, 0.0, 1.0, 1.0};
    std::array<double, 4> ligand_z = {0.0, 0.0, 0.0, 1.0};
    std::array<double, 4> ligand_charge = {0.2, 0.25, -0.45, 0.0};
    std::array<double, 4> ligand_radius = {1.55, 1.0, 1.5, 1.7};
    std::array<double, 4> ligand_epsilon = {0.18, 0.05, 0.2, 0.25};
    std::array<uint8_t, 4> ligand_hydrophobic = {0, 0, 0, 1};
    std::array<uint8_t, 4> ligand_acceptor = {0, 0, 1, 1};

    std::array<uint64_t, 1> receptor_donor = {1};
    std::array<uint64_t, 1> receptor_hydrogen = {2};
    std::array<uint64_t, 1> ligand_donor = {0};
    std::array<uint64_t, 1> ligand_hydrogen = {1};
    std::array<uint64_t, 3> exclusion_i = {0, 1, 2};
    std::array<uint64_t, 3> exclusion_j = {1, 2, 3};
    std::array<uint64_t, 1> rotor_i = {0};
    std::array<uint64_t, 1> rotor_j = {1};
    std::array<uint64_t, 1> rotor_k = {2};
    std::array<uint64_t, 1> rotor_l = {3};

    std::array<bg_docking_scorer_v1_candidate_state, kSlots> states{};
    std::array<double, kSlots * kLigandAtoms> candidate_x{};
    std::array<double, kSlots * kLigandAtoms> candidate_y{};
    std::array<double, kSlots * kLigandAtoms> candidate_z{};

    Fixture() {
        states.fill(BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            for (std::size_t atom = 0; atom < kLigandAtoms; ++atom) {
                const std::size_t offset = slot * kLigandAtoms + atom;
                candidate_x[offset] = ligand_x[atom] + 1.0;
                candidate_y[offset] = ligand_y[atom];
                candidate_z[offset] = ligand_z[atom];
            }
        }
        states[0] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
        states[1] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
        candidate_x[kLigandAtoms + 3] = 1.2;
        candidate_y[kLigandAtoms + 3] = 0.2;
        candidate_z[kLigandAtoms + 3] = 0.3;
    }

    bg_docking_scorer_v1_context_soa_v1 context_descriptor(
        uint64_t receptor_pair_capacity = 1000) const {
        bg_docking_scorer_v1_context_soa_v1 value{};
        assert(bg_docking_scorer_v1_context_soa_v1_init(&value) == BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_x.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_charge_elementary = receptor_charge.data();
        value.receptor_vdw_radius_angstrom = receptor_radius.data();
        value.receptor_epsilon_kcal_per_mol = receptor_epsilon.data();
        value.receptor_hydrophobic = receptor_hydrophobic.data();
        value.receptor_acceptor = receptor_acceptor.data();
        value.ligand_reference_x_angstrom = ligand_x.data();
        value.ligand_reference_y_angstrom = ligand_y.data();
        value.ligand_reference_z_angstrom = ligand_z.data();
        value.ligand_charge_elementary = ligand_charge.data();
        value.ligand_vdw_radius_angstrom = ligand_radius.data();
        value.ligand_epsilon_kcal_per_mol = ligand_epsilon.data();
        value.ligand_hydrophobic = ligand_hydrophobic.data();
        value.ligand_acceptor = ligand_acceptor.data();
        value.receptor_donor_count = receptor_donor.size();
        value.receptor_donor_atom_index = receptor_donor.data();
        value.receptor_hydrogen_atom_index = receptor_hydrogen.data();
        value.ligand_donor_count = ligand_donor.size();
        value.ligand_donor_atom_index = ligand_donor.data();
        value.ligand_hydrogen_atom_index = ligand_hydrogen.data();
        value.ligand_exclusion_count = exclusion_i.size();
        value.ligand_exclusion_atom_i = exclusion_i.data();
        value.ligand_exclusion_atom_j = exclusion_j.data();
        value.rotor_count = rotor_i.size();
        value.rotor_atom_i = rotor_i.data();
        value.rotor_atom_j = rotor_j.data();
        value.rotor_atom_k = rotor_k.data();
        value.rotor_atom_l = rotor_l.data();
        value.pocket_center_angstrom[0] = 1.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.0;
        value.pocket_radius_angstrom = 10.0;
        value.max_receptor_candidate_pairs = receptor_pair_capacity;
        std::fill(
            std::begin(value.authority_input_receipt_sha256),
            std::end(value.authority_input_receipt_sha256),
            UINT8_C(0x11));
        std::fill(
            std::begin(value.receptor_system_sha256),
            std::end(value.receptor_system_sha256),
            UINT8_C(0x22));
        std::fill(
            std::begin(value.ligand_system_sha256),
            std::end(value.ligand_system_sha256),
            UINT8_C(0x33));
        std::fill(
            std::begin(value.backend_receipt_sha256),
            std::end(value.backend_receipt_sha256),
            UINT8_C(0x44));
        return value;
    }

    bg_docking_scorer_v1_candidate_batch_soa_v1 batch() const {
        bg_docking_scorer_v1_candidate_batch_soa_v1 value{};
        assert(
            bg_docking_scorer_v1_candidate_batch_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.ligand_atom_count = kLigandAtoms;
        value.candidate_state = states.data();
        value.x_angstrom = candidate_x.data();
        value.y_angstrom = candidate_y.data();
        value.z_angstrom = candidate_z.data();
        return value;
    }
};

bg_context *create_context(bg_backend backend) {
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != nullptr);
    return context;
}

bg_docking_scorer_v1 *create_scorer(
    bg_context *context,
    const bg_docking_scorer_v1_context_soa_v1 &descriptor) {
    bg_docking_scorer_v1 *scorer = nullptr;
    assert(bg_docking_scorer_v1_create(context, &descriptor, &scorer) == BG_STATUS_OK);
    assert(scorer != nullptr);
    return scorer;
}

std::array<bg_docking_scorer_v1_row_v1, kSlots> score(
    bg_context *context,
    bg_docking_scorer_v1 *scorer,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &batch) {
    std::array<bg_docking_scorer_v1_row_v1, kSlots> rows{};
    bg_docking_scorer_v1_output_v1 output{};
    assert(bg_docking_scorer_v1_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = rows.size();
    output.rows = rows.data();
    assert(
        bg_docking_scorer_v1_score_fixed64(context, scorer, &batch, &output) ==
        BG_STATUS_OK);
    assert(output.row_count == rows.size());
    return rows;
}

bool close_with_tolerance(double left, double right, double tolerance) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= tolerance * scale;
}

void assert_row_parity_with_tolerance(
    const bg_docking_scorer_v1_row_v1 &observed,
    const bg_docking_scorer_v1_row_v1 &reference,
    double tolerance) {
    assert(observed.slot_index == reference.slot_index);
    assert(observed.status == reference.status);
    assert(observed.failure_code == reference.failure_code);
    assert(
        observed.receptor_candidate_pair_count ==
        reference.receptor_candidate_pair_count);
    assert(observed.ligand_pair_count == reference.ligand_pair_count);
    assert(observed.hbond_count == reference.hbond_count);
    assert(
        observed.hydrophobic_contact_count ==
        reference.hydrophobic_contact_count);
    assert(observed.buried_polar_count == reference.buried_polar_count);
    for (std::size_t term = 0; term < BG_DOCKING_SCORER_V1_TERM_COUNT; ++term) {
        assert(close_with_tolerance(
            observed.weighted_terms[term],
            reference.weighted_terms[term],
            tolerance));
    }
    assert(close_with_tolerance(
        observed.total_score, reference.total_score, tolerance));
}

void assert_row_parity(
    const bg_docking_scorer_v1_row_v1 &cpp,
    const bg_docking_scorer_v1_row_v1 &rust) {
    assert_row_parity_with_tolerance(cpp, rust, 2.0e-12);
}

void test_cpu_backend_parity_and_fixed64_failure_preservation() {
    Fixture fixture;
    const auto descriptor = fixture.context_descriptor();
    const auto batch = fixture.batch();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_scorer_v1 *cpp_scorer = create_scorer(cpp_context, descriptor);
    bg_docking_scorer_v1 *rust_scorer = create_scorer(rust_context, descriptor);

    bg_backend observed = BG_BACKEND_AUTO;
    assert(bg_docking_scorer_v1_get_backend(cpp_scorer, &observed) == BG_STATUS_OK);
    assert(observed == BG_BACKEND_CPP_CPU_REFERENCE);
    assert(bg_docking_scorer_v1_get_backend(rust_scorer, &observed) == BG_STATUS_OK);
    assert(observed == BG_BACKEND_RUST_CPU);

    const auto cpp_rows = score(cpp_context, cpp_scorer, batch);
    const auto rust_rows = score(rust_context, rust_scorer, batch);
    const auto rust_repeat = score(rust_context, rust_scorer, batch);
    assert(std::memcmp(rust_rows.data(), rust_repeat.data(), sizeof(rust_rows)) == 0);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_rows[slot], rust_rows[slot]);
    }
    assert(cpp_rows[0].status == BG_DOCKING_SCORER_V1_ROW_SCORED);
    assert(cpp_rows[1].status == BG_DOCKING_SCORER_V1_ROW_SCORED);
    assert(cpp_rows[1].weighted_terms[5] > 0.0);
    assert(cpp_rows[1].weighted_terms[6] > 0.0);
    assert(cpp_rows[2].status == BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE);
    assert(
        cpp_rows[2].failure_code ==
        BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED);

    bg_docking_scorer_v1_destroy(cpp_scorer);
    bg_docking_scorer_v1_destroy(rust_scorer);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_candidate_local_failures_match_without_changing_the_denominator() {
    Fixture fixture;
    fixture.states[2] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
    fixture.candidate_x[2 * kLigandAtoms] =
        std::numeric_limits<double>::quiet_NaN();
    fixture.states[3] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
    for (std::size_t atom = 0; atom < kLigandAtoms; ++atom) {
        fixture.candidate_x[3 * kLigandAtoms + atom] = 1.0;
        fixture.candidate_y[3 * kLigandAtoms + atom] = 1.0;
        fixture.candidate_z[3 * kLigandAtoms + atom] = 1.0;
    }
    const auto descriptor = fixture.context_descriptor();
    const auto batch = fixture.batch();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_scorer_v1 *cpp_scorer = create_scorer(cpp_context, descriptor);
    bg_docking_scorer_v1 *rust_scorer = create_scorer(rust_context, descriptor);
    const auto cpp_rows = score(cpp_context, cpp_scorer, batch);
    const auto rust_rows = score(rust_context, rust_scorer, batch);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_rows[slot], rust_rows[slot]);
    }
    assert(
        cpp_rows[2].failure_code ==
        BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES);
    assert(
        cpp_rows[3].failure_code ==
        BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR);
    bg_docking_scorer_v1_destroy(cpp_scorer);
    bg_docking_scorer_v1_destroy(rust_scorer);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_receptor_capacity_failure_and_transactionality() {
    Fixture fixture;
    const auto descriptor = fixture.context_descriptor(1);
    auto batch = fixture.batch();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_scorer_v1 *cpp_scorer = create_scorer(cpp_context, descriptor);
    bg_docking_scorer_v1 *rust_scorer = create_scorer(rust_context, descriptor);
    const auto cpp_rows = score(cpp_context, cpp_scorer, batch);
    const auto rust_rows = score(rust_context, rust_scorer, batch);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_rows[slot], rust_rows[slot]);
    }
    assert(
        cpp_rows[0].failure_code ==
        BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY);

    std::array<bg_docking_scorer_v1_row_v1, kSlots> sentinel_rows{};
    std::memset(sentinel_rows.data(), 0x5a, sizeof(sentinel_rows));
    const auto before = sentinel_rows;
    bg_docking_scorer_v1_output_v1 output{};
    assert(bg_docking_scorer_v1_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = sentinel_rows.size();
    output.row_count = 17;
    output.rows = sentinel_rows.data();
    auto invalid_states = fixture.states;
    invalid_states[0] = 99;
    batch.candidate_state = invalid_states.data();
    assert(
        bg_docking_scorer_v1_score_fixed64(
            rust_context, rust_scorer, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == 17);
    assert(std::memcmp(sentinel_rows.data(), before.data(), sizeof(before)) == 0);

    const auto valid_batch = fixture.batch();
    assert(
        bg_docking_scorer_v1_score_fixed64(
            cpp_context, rust_scorer, &valid_batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_docking_scorer_v1_destroy(cpp_scorer);
    bg_docking_scorer_v1_destroy(rust_scorer);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void assert_hip_fixture_parity(
    const Fixture &fixture,
    bg_backend backend,
    uint64_t receptor_pair_capacity = 1000) {
    const auto descriptor = fixture.context_descriptor(receptor_pair_capacity);
    const auto batch = fixture.batch();
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_context *hip_context = create_context(backend);
    bg_docking_scorer_v1 *rust_scorer = create_scorer(rust_context, descriptor);
    bg_docking_scorer_v1 *hip_scorer = create_scorer(hip_context, descriptor);

    bg_backend observed = BG_BACKEND_AUTO;
    assert(bg_docking_scorer_v1_get_backend(hip_scorer, &observed) == BG_STATUS_OK);
    assert(observed == backend);

    const auto rust_rows = score(rust_context, rust_scorer, batch);
    const auto hip_rows = score(hip_context, hip_scorer, batch);
    const auto hip_repeat = score(hip_context, hip_scorer, batch);
    assert(std::memcmp(hip_rows.data(), hip_repeat.data(), sizeof(hip_rows)) == 0);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity_with_tolerance(hip_rows[slot], rust_rows[slot], 1.0e-10);
    }

    bg_docking_scorer_v1_destroy(rust_scorer);
    bg_docking_scorer_v1_destroy(hip_scorer);
    bg_context_destroy(rust_context);
    bg_context_destroy(hip_context);
}

void test_hip_scorer_parity_when_device_is_available(bg_backend backend) {
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return;
    }

    const Fixture nominal;
    assert_hip_fixture_parity(nominal, backend);

    Fixture candidate_failures;
    candidate_failures.states[2] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
    candidate_failures.candidate_x[2 * kLigandAtoms] =
        std::numeric_limits<double>::quiet_NaN();
    candidate_failures.states[3] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
    for (std::size_t atom = 0; atom < kLigandAtoms; ++atom) {
        candidate_failures.candidate_x[3 * kLigandAtoms + atom] = 1.0;
        candidate_failures.candidate_y[3 * kLigandAtoms + atom] = 1.0;
        candidate_failures.candidate_z[3 * kLigandAtoms + atom] = 1.0;
    }
    assert_hip_fixture_parity(candidate_failures, backend);

    const Fixture receptor_capacity;
    assert_hip_fixture_parity(receptor_capacity, backend, 1);
}

}  // namespace

int main() {
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_context_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_candidate_batch_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_row_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_output_v1>);
    test_cpu_backend_parity_and_fixed64_failure_preservation();
    test_candidate_local_failures_match_without_changing_the_denominator();
    test_receptor_capacity_failure_and_transactionality();
    test_hip_scorer_parity_when_device_is_available(BG_BACKEND_HIP_SAFE);
    test_hip_scorer_parity_when_device_is_available(BG_BACKEND_HIP_FAST);
    return 0;
}

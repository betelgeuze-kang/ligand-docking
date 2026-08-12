#pragma once

#include "betelgeuze/engine.h"

#include <array>

namespace betelgeuze::native::docking::fixed64_so3 {

[[nodiscard]] std::array<
    bg_docking_fixed64_so3_row_v1,
    BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT>
reference_rows(const bg_docking_fixed64_so3_input_v1 &input) noexcept;

}  // namespace betelgeuze::native::docking::fixed64_so3

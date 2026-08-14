#include <iostream>

namespace {

constexpr char kExpectedPreflightSha256[] =
    "aca96d31bb1ca09d9eb83a10bb7a8a91192fc1405a9eaa8011d94453a28a306e";
constexpr char kRequiredSupervisor[] =
    "mount-independent initial-namespace attestation and trace-excluding exec "
    "supervisor";
constexpr bool kTrustedSupervisorOperational = false;

}  // namespace

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;
    static_assert(!kTrustedSupervisorOperational);
    std::cerr << "Engine V2 full-pipeline CPU preflight is unavailable: "
              << kRequiredSupervisor
              << " is not implemented; expected_preflight_sha256="
              << kExpectedPreflightSha256 << '\n';
    return 125;
}

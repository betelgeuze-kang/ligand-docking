#include <iostream>

namespace {

constexpr char kExpectedPreflightSha256[] =
    "1c50fa1b3bb183f63070873840a53a648e810a3240ff1829e2a49cca8373bdb5";
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

use std::process::Command;

use betelgeuze_runtime::{
    fixed64_cpu_v4_live_activation_admitted, FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED,
};

#[test]
fn native_fixed64_cpu_probe_is_blocked_before_measurement() {
    // Integration tests link the ordinary non-test library artifact. Keep
    // these checks before spawning the binary so an activation-open build
    // fails without entering qualification configuration or measurement.
    assert!(!FIXED64_CPU_V4_LIVE_ACTIVATION_ADMITTED);
    assert!(!fixed64_cpu_v4_live_activation_admitted());

    let output = Command::new(env!("CARGO_BIN_EXE_betelgeuze-fixed64-cpu-probe-v4"))
        .output()
        .expect("blocked probe binary must be launchable");

    assert_eq!(output.status.code(), Some(3));
    assert!(output.stdout.is_empty());
    assert_eq!(
        String::from_utf8(output.stderr).expect("probe stderr must be UTF-8"),
        "fixed64 CPU probe v4 failed closed: reviewed live activation is absent\n"
    );
}

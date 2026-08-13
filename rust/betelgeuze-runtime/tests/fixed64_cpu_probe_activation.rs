use std::process::Command;

#[test]
fn native_fixed64_cpu_probe_is_blocked_before_measurement() {
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

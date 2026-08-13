use std::fmt::Write as _;
use std::process::ExitCode;

use betelgeuze_runtime::{
    fixed64_cpu_v5_live_activation_admitted, run_native_fixed64_cpu_probe_v5,
    Fixed64CpuFixtureProbeV5, Fixed64CpuProbeConfigV5,
};

fn digest(value: [u8; 32]) -> String {
    let mut output = String::with_capacity(64);
    for byte in value {
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

fn integer_array(values: &[u64]) -> String {
    let mut output = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index != 0 {
            output.push(',');
        }
        write!(&mut output, "{value}").expect("writing to String cannot fail");
    }
    output.push(']');
    output
}

fn fixture_json(value: &Fixed64CpuFixtureProbeV5) -> String {
    format!(
        concat!(
            "{{\"authority_false\":{},",
            "\"candidate_denominator\":{},",
            "\"cpp_decision_sha256\":\"{}\",",
            "\"cpp_median_nanoseconds\":{},",
            "\"cpp_projection_sha256\":\"{}\",",
            "\"cpp_repeat_stable\":{},",
            "\"cpp_sample_nanoseconds\":{},",
            "\"decision_parity\":{},",
            "\"fixture_id\":\"{}\",",
            "\"fixture_payload_sha256\":\"{}\",",
            "\"gate_passed\":{},",
            "\"generated_count\":{},",
            "\"ligand_atom_count\":{},",
            "\"numeric_parity\":{{",
            "\"compared_f64_count\":{},",
            "\"first_violation_index\":{},",
            "\"maximum_absolute_difference\":{},",
            "\"maximum_scaled_difference\":{},",
            "\"tolerance_violation_count\":{}",
            "}},",
            "\"persistent_cpp_context_count\":{},",
            "\"persistent_rust_context_count\":{},",
            "\"receptor_atom_count\":{},",
            "\"rust_decision_sha256\":\"{}\",",
            "\"rust_median_nanoseconds\":{},",
            "\"rust_projection_sha256\":\"{}\",",
            "\"rust_repeat_stable\":{},",
            "\"rust_sample_nanoseconds\":{},",
            "\"rust_to_cpp_median_ratio\":{},",
            "\"score_term_count\":{},",
            "\"typed_failure_count\":{}",
            "}}"
        ),
        value.authority_false,
        value.candidate_denominator,
        digest(value.cpp_decision_sha256),
        value.cpp_median_nanoseconds,
        digest(value.cpp_projection_sha256),
        value.cpp_repeat_stable,
        integer_array(&value.cpp_sample_nanoseconds),
        value.decision_parity,
        value.fixture_id,
        digest(value.fixture_payload_sha256),
        value.gate_passed,
        value.generated_count,
        value.ligand_atom_count,
        value.numeric_parity.compared_f64_count,
        value
            .numeric_parity
            .first_violation_index
            .map_or_else(|| "null".to_owned(), |index| index.to_string()),
        value.numeric_parity.maximum_absolute_difference,
        value.numeric_parity.maximum_scaled_difference,
        value.numeric_parity.tolerance_violation_count,
        value.persistent_cpp_context_count,
        value.persistent_rust_context_count,
        value.receptor_atom_count,
        digest(value.rust_decision_sha256),
        value.rust_median_nanoseconds,
        digest(value.rust_projection_sha256),
        value.rust_repeat_stable,
        integer_array(&value.rust_sample_nanoseconds),
        value.rust_to_cpp_median_ratio,
        value.score_term_count,
        value.typed_failure_count,
    )
}

fn main() -> ExitCode {
    if std::env::args_os().count() != 1 {
        eprintln!("fixed64 CPU probe v5 accepts no caller-supplied arguments");
        return ExitCode::from(2);
    }
    if !fixed64_cpu_v5_live_activation_admitted() {
        eprintln!("fixed64 CPU probe v5 failed closed: reviewed live activation is absent");
        return ExitCode::from(3);
    }
    let config = Fixed64CpuProbeConfigV5::qualification_profile();
    let report = match run_native_fixed64_cpu_probe_v5(config) {
        Ok(report) => report,
        Err(error) => {
            eprintln!("fixed64 CPU probe v5 failed closed: {error}");
            return ExitCode::from(1);
        }
    };
    let fixtures = report
        .fixtures
        .iter()
        .map(fixture_json)
        .collect::<Vec<_>>()
        .join(",");
    println!(
        concat!(
            "{{\"authority\":{{",
            "\"molecular_execution_authorized\":{},",
            "\"product_performance_claim_authorized\":{},",
            "\"public_benchmark_authorized\":{},",
            "\"qualification_authority\":{},",
            "\"reservation_authorized\":{}",
            "}},",
            "\"fixtures\":[{}],",
            "\"gate_passed\":{},",
            "\"profile_id\":\"{}\",",
            "\"sampling\":{{",
            "\"absolute_tolerance\":{},",
            "\"maximum_rust_to_cpp_median_ratio\":{},",
            "\"relative_tolerance\":{},",
            "\"sample_rounds\":{},",
            "\"schedule\":\"paired_ab_ba\",",
            "\"warmup_rounds\":{}",
            "}},",
            "\"schema_id\":\"{}\"}}"
        ),
        report.molecular_execution_authorized,
        report.product_performance_claim_authorized,
        report.public_benchmark_authorized,
        report.qualification_authority,
        report.reservation_authorized,
        fixtures,
        report.gate_passed,
        report.profile_id,
        config.absolute_tolerance,
        config.maximum_rust_to_cpp_median_ratio,
        config.relative_tolerance,
        config.sample_rounds,
        config.warmup_rounds,
        report.schema_id,
    );
    if report.gate_passed {
        ExitCode::SUCCESS
    } else {
        eprintln!("fixed64 CPU probe v5 gates did not pass");
        ExitCode::from(1)
    }
}

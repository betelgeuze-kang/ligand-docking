use std::ffi::OsStr;
use std::fmt::Write as _;
use std::path::Path;
use std::process::ExitCode;

use betelgeuze_runtime::{
    preflight_native_fixed64_cpu_v6, run_native_fixed64_cpu_qualification_v6,
    verify_native_fixed64_cpu_v6_activation,
};

fn json_string(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\u{08}' => output.push_str("\\b"),
            '\u{0c}' => output.push_str("\\f"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            value if value <= '\u{1f}' => {
                write!(&mut output, "\\u{:04x}", u32::from(value))
                    .expect("writing to String cannot fail");
            }
            value => output.push(value),
        }
    }
    output.push('"');
    output
}

fn string_array(values: &[String]) -> String {
    format!(
        "[{}]",
        values
            .iter()
            .map(|value| json_string(value))
            .collect::<Vec<_>>()
            .join(",")
    )
}

fn optional_string(value: Option<&str>) -> String {
    value.map_or_else(|| "null".to_owned(), json_string)
}

fn optional_bool(value: Option<bool>) -> &'static str {
    match value {
        Some(true) => "true",
        Some(false) => "false",
        None => "null",
    }
}

fn optional_usize(value: Option<usize>) -> String {
    value.map_or_else(|| "null".to_owned(), |value| value.to_string())
}

fn validated_path_text(path: &Path) -> &str {
    path.to_str()
        .expect("v6 validates all returned paths as UTF-8 before consuming the attempt")
}

fn fail(message: &str) -> ExitCode {
    eprintln!("native fixed64 CPU qualification v6 failed closed: {message}");
    ExitCode::from(1)
}

fn main() -> ExitCode {
    let arguments = std::env::args_os().collect::<Vec<_>>();
    if arguments.len() == 2 && arguments[1] == OsStr::new("--verify-activation") {
        let status = match verify_native_fixed64_cpu_v6_activation() {
            Ok(value) => value,
            Err(error) => return fail(error.message()),
        };
        println!(
            concat!(
                "{{\"activation_sha256\":\"{}\",",
                "\"authority\":{{",
                "\"hip_device_execution_authorized\":{},",
                "\"molecular_execution_authorized\":{},",
                "\"product_performance_claim_authorized\":{},",
                "\"public_benchmark_authorized\":{},",
                "\"qualification_authority\":{}",
                "}},",
                "\"build_configuration_sha256\":\"{}\",",
                "\"execution_consumed\":{},",
                "\"live_execution_implemented\":{},",
                "\"profile_id\":\"{}\",",
                "\"profile_sha256\":\"{}\",",
                "\"verification_only\":true}}"
            ),
            status.activation_sha256,
            status.hip_device_execution_authorized,
            status.molecular_execution_authorized,
            status.product_performance_claim_authorized,
            status.public_benchmark_authorized,
            status.qualification_authority,
            status.build_configuration_sha256,
            status.execution_consumed,
            status.live_execution_implemented,
            status.profile_id,
            status.profile_sha256,
        );
        return ExitCode::SUCCESS;
    }
    if arguments.len() == 2 && arguments[1] == OsStr::new("--preflight") {
        let preflight = match preflight_native_fixed64_cpu_v6() {
            Ok(value) => value,
            Err(error) => return fail(error.message()),
        };
        println!(
            concat!(
                "{{\"activation_sha256\":\"{}\",",
                "\"blockers\":{},",
                "\"boost_disabled\":{},",
                "\"build_configuration_sha256\":\"{}\",",
                "\"cpu_model\":{},",
                "\"measurement_cpu_available\":{},",
                "\"process_task_count\":{},",
                "\"profile_sha256\":\"{}\",",
                "\"ready\":{},",
                "\"source_commit_oid\":{},",
                "\"verification_only\":true}}"
            ),
            preflight.activation_sha256,
            string_array(&preflight.blockers),
            optional_bool(preflight.boost_disabled),
            preflight.build_configuration_sha256,
            optional_string(preflight.cpu_model.as_deref()),
            preflight.measurement_cpu_available,
            optional_usize(preflight.process_task_count),
            preflight.profile_sha256,
            preflight.ready(),
            optional_string(preflight.source_commit_oid.as_deref()),
        );
        return ExitCode::SUCCESS;
    }
    if arguments.len() == 3 && arguments[1] == OsStr::new("--run-output") {
        let result = match run_native_fixed64_cpu_qualification_v6(Path::new(&arguments[2])) {
            Ok(value) => value,
            Err(error) => return fail(error.message()),
        };
        println!(
            concat!(
                "{{\"artifact_path\":{},",
                "\"artifact_sha256\":\"{}\",",
                "\"attempt_ledger_path\":{},",
                "\"blockers\":{},",
                "\"qualification_authority\":{},",
                "\"recorded_decision\":{},",
                "\"terminal_state_path\":{},",
                "\"terminal_state_sha256\":\"{}\"}}"
            ),
            json_string(validated_path_text(&result.artifact_path)),
            result.artifact_sha256,
            json_string(validated_path_text(&result.attempt_ledger_path)),
            string_array(&result.blockers),
            result.qualification_authority,
            json_string(&result.recorded_decision),
            json_string(validated_path_text(&result.terminal_state_path)),
            result.terminal_state_sha256,
        );
        return ExitCode::SUCCESS;
    }
    eprintln!(
        "usage: betelgeuze-fixed64-cpu-qualify-v6 \
         (--verify-activation | --preflight | --run-output ABSENT_OWNER_JSON)"
    );
    ExitCode::from(2)
}

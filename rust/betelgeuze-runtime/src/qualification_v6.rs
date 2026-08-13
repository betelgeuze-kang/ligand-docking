//! Account-scoped, exactly-once activation for the synthetic fixed64 CPU probe.
//!
//! The measured graph remains native C++/Rust and contains no molecular input.
//! This module owns the local attempt ledger and publication transaction so a
//! caller cannot bypass it to obtain admitted v6 execution evidence.

use std::env;
use std::ffi::{CStr, CString, OsStr};
use std::fmt::{self, Write as _};
use std::fs;
use std::io::{self, Read as _, Write as _};
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd, RawFd};
use std::os::unix::ffi::{OsStrExt as _, OsStringExt as _};
use std::os::unix::fs::MetadataExt as _;
use std::path::{Path, PathBuf};
use std::process::Command;

use sha2::{Digest as _, Sha256};

use crate::qualification::{
    run_native_fixed64_cpu_qualification_successor, Fixed64CpuFixtureProbeV5,
    Fixed64CpuProbeReportV5,
};

pub const FIXED64_CPU_QUALIFICATION_V6_PROFILE_ID: &str =
    "engine_v2_native_fixed64_cpu_synthetic_v6";
pub const FIXED64_CPU_QUALIFICATION_V6_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_cpu_probe/6.0.0";

const PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_fixed64_cpu_profile_v6.json");
const PREDECESSOR_ARCHIVE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_fixed64_cpu_profile_v5_archive.json");
const TRANSITIVE_SOURCE_MANIFEST_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json");
const QUALIFICATION_SOURCE_BYTES: &[u8] = include_bytes!("qualification.rs");
const RUNNER_SOURCE_BYTES: &[u8] = include_bytes!("qualification_v6.rs");
const BINARY_SOURCE_BYTES: &[u8] = include_bytes!("bin/betelgeuze-fixed64-cpu-qualify-v6.rs");
const CARGO_MANIFEST_BYTES: &[u8] = include_bytes!("../assets/original-Cargo.toml");
const CARGO_LOCK_BYTES: &[u8] = include_bytes!("../assets/workspace-Cargo.lock");
const COMPILED_SOURCE_MANIFEST_SHA256: &str = env!("BETELGEUZE_V6_COMPILED_SOURCE_MANIFEST_SHA256");
const COMPILED_SOURCE_COUNT: &str = env!("BETELGEUZE_V6_COMPILED_SOURCE_COUNT");
const COMPILED_PROFILE_SHA256: &str = env!("BETELGEUZE_V6_COMPILED_PROFILE_SHA256");
const BUILD_COMMIT_OID: &str = env!("BETELGEUZE_V6_BUILD_COMMIT_OID");
const BUILD_COMMIT_BOUND: &str = env!("BETELGEUZE_V6_BUILD_COMMIT_BOUND");
const VERIFIED_SOURCE_ROOT: &str = env!("BETELGEUZE_V6_VERIFIED_SOURCE_ROOT");

const ATTEMPT_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_fixed64_cpu_attempt/6.0.0";
const ARTIFACT_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_fixed64_cpu_qualification_artifact/6.0.0";
const TERMINAL_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_fixed64_cpu_terminal/6.0.0";
const STATE_ROOT_NAME: &str = ".betelgeuze-engine-v2";
const STATE_QUALIFICATION_NAME: &str = "native-fixed64-qualification";
const ATTEMPT_FILENAME: &str = "attempt.json";
const TERMINAL_FILENAME: &str = "terminal.json";
const MEASUREMENT_CPU_ORDINAL: usize = 2;
const MAX_PROFILE_BYTES: usize = 32 * 1024;
const MAX_STATE_BYTES: usize = 64 * 1024;
const MAX_ARTIFACT_BYTES: usize = 4 * 1024 * 1024;
const STAGING_NAME_OVERHEAD_BYTES: usize = 1 + 5 + 64;
const ACTIVATION_DOMAIN: &[u8] = b"betelgeuze.engine_v2_native_fixed64_cpu_activation_v6\0";
const ATTEMPT_DOMAIN: &[u8] = b"betelgeuze.engine_v2_native_fixed64_cpu_attempt_v6\0";
const ARTIFACT_DOMAIN: &[u8] = b"betelgeuze.engine_v2_native_fixed64_cpu_artifact_v6\0";
const TERMINAL_DOMAIN: &[u8] = b"betelgeuze.engine_v2_native_fixed64_cpu_terminal_v6\0";

const AUTHORITY_FALSE_JSON: &str = concat!(
    "{\"fresh_holdout_execution_authorized\":false,",
    "\"historical_ab_execution_authorized\":false,",
    "\"molecular_execution_authorized\":false,",
    "\"product_performance_claim_authorized\":false,",
    "\"public_benchmark_authorized\":false,",
    "\"qualification_authority\":false,",
    "\"reservation_authorized\":false,",
    "\"scientific_claim_authorized\":false,",
    "\"stage0_admission_authorized\":false}"
);
const RESTRICTIONS_JSON: &str = concat!(
    "{\"actual_molecular_execution_allowed\":false,",
    "\"contains_molecular_cases\":false,",
    "\"fresh_or_historical_case_input_allowed\":false,",
    "\"github_actions_live_qualification_allowed\":false,",
    "\"github_actions_production_authority_allowed\":false,",
    "\"hip_device_execution_allowed\":false,",
    "\"public_or_scientific_performance_claim_allowed\":false,",
    "\"reservation_allowed\":false,",
    "\"result_dependent_configuration_allowed\":false,",
    "\"test_double_production_authority_allowed\":false}"
);

#[derive(Debug)]
pub struct NativeFixed64CpuQualificationV6Error {
    message: String,
}

impl NativeFixed64CpuQualificationV6Error {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }

    #[must_use]
    pub fn message(&self) -> &str {
        &self.message
    }
}

impl fmt::Display for NativeFixed64CpuQualificationV6Error {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for NativeFixed64CpuQualificationV6Error {}

type V6Result<T> = std::result::Result<T, NativeFixed64CpuQualificationV6Error>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fixed64CpuActivationStatusV6 {
    pub profile_id: &'static str,
    pub profile_sha256: String,
    pub activation_sha256: String,
    pub live_execution_implemented: bool,
    pub execution_consumed: bool,
    pub qualification_authority: bool,
    pub molecular_execution_authorized: bool,
    pub public_benchmark_authorized: bool,
    pub product_performance_claim_authorized: bool,
    pub hip_device_execution_authorized: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fixed64CpuPreflightV6 {
    pub profile_sha256: String,
    pub activation_sha256: String,
    pub source_commit_oid: Option<String>,
    pub cpu_model: Option<String>,
    pub boost_disabled: Option<bool>,
    pub measurement_cpu_available: bool,
    pub process_task_count: Option<usize>,
    pub blockers: Vec<String>,
}

impl Fixed64CpuPreflightV6 {
    #[must_use]
    pub fn ready(&self) -> bool {
        self.blockers.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fixed64CpuPersistedQualificationV6 {
    pub artifact_path: PathBuf,
    pub attempt_ledger_path: PathBuf,
    pub terminal_state_path: PathBuf,
    pub artifact_sha256: String,
    pub terminal_state_sha256: String,
    pub recorded_decision: String,
    pub blockers: Vec<String>,
    pub qualification_authority: bool,
}

#[derive(Debug)]
struct AccountStateDirectory {
    path: PathBuf,
    descriptor: OwnedFd,
    device: u64,
    inode: u64,
}

#[derive(Debug)]
struct ValidatedOutputTarget {
    path: PathBuf,
    parent_path: PathBuf,
    name: CString,
    parent_descriptor: OwnedFd,
    parent_device: u64,
    parent_inode: u64,
}

#[derive(Debug)]
struct AttemptLeaseV6 {
    raw: Vec<u8>,
    raw_sha256: String,
    receipt_sha256: String,
    run_nonce: String,
    output_path_sha256: String,
}

#[derive(Debug)]
struct MeasurementOutcomeV6 {
    report: Option<Fixed64CpuProbeReportV5>,
    measurement_started: bool,
    blockers: Vec<String>,
}

#[derive(Debug)]
struct ArtifactDocumentV6 {
    raw: Vec<u8>,
    receipt_sha256: String,
    recorded_decision: String,
    recorded_gate_passed: Option<bool>,
    blockers: Vec<String>,
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn digest_hex(value: [u8; 32]) -> String {
    let mut output = String::with_capacity(64);
    for byte in value {
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

fn sha256_hex(bytes: &[u8]) -> String {
    digest_hex(sha256(bytes))
}

fn domain_digest(domain: &[u8], bytes: &[u8]) -> String {
    let mut hash = Sha256::new();
    hash.update(domain);
    hash.update(bytes);
    digest_hex(hash.finalize().into())
}

fn profile_text() -> V6Result<&'static str> {
    if PROFILE_BYTES.len() > MAX_PROFILE_BYTES || !PROFILE_BYTES.ends_with(b"}\n") {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 profile byte envelope changed",
        ));
    }
    std::str::from_utf8(PROFILE_BYTES).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 profile is not canonical UTF-8",
        )
    })
}

fn require_profile_literal(profile: &str, literal: &str, label: &str) -> V6Result<()> {
    if profile.matches(literal).count() != 1 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} binding changed"
        )));
    }
    Ok(())
}

fn require_source_binding(profile: &str, key: &str, source_bytes: &[u8]) -> V6Result<()> {
    let expected = format!("\"{key}\": \"{}\"", sha256_hex(source_bytes));
    require_profile_literal(profile, &expected, key)
}

/// Verify the compile-bound, non-consuming v6 activation contract.
pub fn verify_native_fixed64_cpu_v6_activation() -> V6Result<Fixed64CpuActivationStatusV6> {
    let profile = profile_text()?;
    for (literal, label) in [
        (
            "\"schema_id\": \"betelgeuze.engine_v2_native_fixed64_cpu_profile/6.0.0\"",
            "schema",
        ),
        (
            "\"profile_id\": \"engine_v2_native_fixed64_cpu_synthetic_v6\"",
            "profile identity",
        ),
        (
            "\"status\": \"native_activation_implementation_frozen_execution_not_consumed\"",
            "execution state",
        ),
        (
            "\"predecessor_profile_sha256\": \"f5b3f288b432a15a1382a175b70821c1c57e8d41a986de2dea8898712374aece\"",
            "predecessor profile",
        ),
        ("\"native_abi_version\": \"1.21\"", "native ABI"),
        ("\"candidate_denominator_exact\": 64", "candidate denominator"),
        ("\"sample_rounds\": 25", "sample rounds"),
        ("\"warmup_rounds\": 5", "warmup rounds"),
        (
            "\"github_actions_live_qualification_allowed\": false",
            "GitHub Actions boundary",
        ),
        (
            "\"hip_device_execution_allowed\": false",
            "HIP execution boundary",
        ),
        (
            "\"actual_molecular_execution_allowed\": false",
            "molecular execution boundary",
        ),
        ("\"account_scoped_exactly_once\": true", "exactly-once runner"),
        (
            "\"compiled_transitive_sources_verified_at_build\": true",
            "compiled source graph",
        ),
        (
            "\"build_source_root_bound\": true",
            "verified build source root",
        ),
        (
            "\"build_commit_bound\": true",
            "verified build commit",
        ),
        (
            "\"compiled_activation_profile_verified_at_build\": true",
            "compiled activation profile",
        ),
        (
            "\"non_authoritative_package_build_activation_rejected\": true",
            "non-authoritative package activation boundary",
        ),
        (
            "\"output_path_utf8_required\": true",
            "output path encoding",
        ),
        (
            "\"post_measurement_host_revalidation_required\": true",
            "post-measurement host revalidation",
        ),
    ] {
        require_profile_literal(profile, literal, label)?;
    }
    require_source_binding(
        profile,
        "native_qualification_source_sha256",
        QUALIFICATION_SOURCE_BYTES,
    )?;
    require_source_binding(profile, "native_runner_source_sha256", RUNNER_SOURCE_BYTES)?;
    require_source_binding(profile, "native_binary_source_sha256", BINARY_SOURCE_BYTES)?;
    require_source_binding(profile, "cargo_manifest_sha256", CARGO_MANIFEST_BYTES)?;
    require_source_binding(profile, "cargo_lock_sha256", CARGO_LOCK_BYTES)?;
    require_source_binding(
        profile,
        "predecessor_archive_sha256",
        PREDECESSOR_ARCHIVE_BYTES,
    )?;
    require_source_binding(
        profile,
        "transitive_source_manifest_sha256",
        TRANSITIVE_SOURCE_MANIFEST_BYTES,
    )?;
    let profile_sha256 = sha256_hex(PROFILE_BYTES);
    if BUILD_COMMIT_BOUND != "true" {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 non-authoritative package build cannot activate",
        ));
    }
    if COMPILED_PROFILE_SHA256 != profile_sha256
        || BUILD_COMMIT_OID.len() != 40
        || BUILD_COMMIT_OID == "0000000000000000000000000000000000000000"
        || !BUILD_COMMIT_OID
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
        || COMPILED_SOURCE_MANIFEST_SHA256 != sha256_hex(TRANSITIVE_SOURCE_MANIFEST_BYTES)
        || COMPILED_SOURCE_COUNT != "192"
        || std::str::from_utf8(TRANSITIVE_SOURCE_MANIFEST_BYTES)
            .ok()
            .is_none_or(|manifest| manifest.matches("\"source_count\": 192").count() != 1)
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 compiled transitive source graph is not exact",
        ));
    }
    let activation_sha256 = domain_digest(ACTIVATION_DOMAIN, PROFILE_BYTES);
    Ok(Fixed64CpuActivationStatusV6 {
        profile_id: FIXED64_CPU_QUALIFICATION_V6_PROFILE_ID,
        profile_sha256,
        activation_sha256,
        live_execution_implemented: true,
        execution_consumed: false,
        qualification_authority: false,
        molecular_execution_authorized: false,
        public_benchmark_authorized: false,
        product_performance_claim_authorized: false,
        hip_device_execution_authorized: false,
    })
}

fn source_root() -> V6Result<PathBuf> {
    let root = PathBuf::from(VERIFIED_SOURCE_ROOT);
    if !root.is_absolute() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 verified source root is invalid",
        ));
    }
    let canonical = fs::canonicalize(&root).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source root is unavailable",
        )
    })?;
    if canonical != root {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source root traverses a symlink",
        ));
    }
    Ok(root)
}

fn exact_command(root: &Path, args: &[&str]) -> V6Result<String> {
    let output = Command::new(args[0])
        .args(&args[1..])
        .current_dir(root)
        .env_remove("GIT_DIR")
        .env_remove("GIT_WORK_TREE")
        .env_remove("GIT_INDEX_FILE")
        .env_remove("GIT_OBJECT_DIRECTORY")
        .env_remove("GIT_ALTERNATE_OBJECT_DIRECTORIES")
        .output()
        .map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 source command is unavailable",
            )
        })?;
    if !output.status.success() || !output.stderr.is_empty() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source command failed closed",
        ));
    }
    let value = std::str::from_utf8(&output.stdout).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source command returned non-UTF-8 output",
        )
    })?;
    Ok(value.trim_end_matches('\n').to_owned())
}

fn source_checkout_evidence() -> V6Result<String> {
    let root = source_root()?;
    let reported_root = exact_command(&root, &["git", "rev-parse", "--show-toplevel"])?;
    if Path::new(&reported_root) != root {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source checkout root changed",
        ));
    }
    let branch = exact_command(
        &root,
        &["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
    )?;
    if branch != "main" {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 live execution requires branch main",
        ));
    }
    let status = exact_command(
        &root,
        &[
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        ],
    )?;
    if !status.is_empty() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 live execution requires a clean checkout",
        ));
    }
    let oid = exact_command(&root, &["git", "rev-parse", "HEAD"])?;
    if oid.len() != 40 || !oid.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source commit identity is invalid",
        ));
    }
    let oid = oid.to_ascii_lowercase();
    if oid != BUILD_COMMIT_OID {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 source commit differs from the verified build commit",
        ));
    }
    Ok(oid)
}

fn cpu_model() -> V6Result<String> {
    let raw = fs::read_to_string("/proc/cpuinfo").map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new("native fixed64 CPU v6 CPU model is unavailable")
    })?;
    let mut models = raw
        .lines()
        .filter_map(|line| line.strip_prefix("model name\t: "));
    let first = models.next().ok_or_else(|| {
        NativeFixed64CpuQualificationV6Error::new("native fixed64 CPU v6 CPU model is missing")
    })?;
    if first != "AMD Ryzen 9 5900X 12-Core Processor" || models.any(|value| value != first) {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 CPU model is not qualified",
        ));
    }
    Ok(first.to_owned())
}

fn process_task_count() -> V6Result<usize> {
    let count = fs::read_dir("/proc/self/task")
        .map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 task inventory is unavailable",
            )
        })?
        .filter_map(std::result::Result::ok)
        .count();
    if count == 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 task inventory is empty",
        ));
    }
    Ok(count)
}

fn current_affinity() -> V6Result<libc::cpu_set_t> {
    // SAFETY: `cpu_set_t` is plain data, and sched_getaffinity writes exactly
    // the provided initialized object for the current process.
    unsafe {
        let mut set: libc::cpu_set_t = std::mem::zeroed();
        if libc::sched_getaffinity(
            0,
            std::mem::size_of::<libc::cpu_set_t>(),
            std::ptr::addr_of_mut!(set),
        ) != 0
        {
            return Err(NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 affinity is unavailable",
            ));
        }
        Ok(set)
    }
}

fn cpu_is_set(set: &libc::cpu_set_t, ordinal: usize) -> bool {
    // SAFETY: the reference points to a valid `cpu_set_t`; ordinal is the
    // fixed small profile value 2.
    unsafe { libc::CPU_ISSET(ordinal, set) }
}

fn affinity_is_exact_measurement_cpu(set: &libc::cpu_set_t) -> bool {
    // SAFETY: both values are fully initialized `cpu_set_t` objects and are
    // compared over exactly their common object representation.
    unsafe {
        let mut expected: libc::cpu_set_t = std::mem::zeroed();
        libc::CPU_ZERO(&mut expected);
        libc::CPU_SET(MEASUREMENT_CPU_ORDINAL, &mut expected);
        let observed_bytes = std::slice::from_raw_parts(
            std::ptr::from_ref(set).cast::<u8>(),
            std::mem::size_of::<libc::cpu_set_t>(),
        );
        let expected_bytes = std::slice::from_raw_parts(
            std::ptr::from_ref(&expected).cast::<u8>(),
            std::mem::size_of::<libc::cpu_set_t>(),
        );
        observed_bytes == expected_bytes
    }
}

fn pin_measurement_cpu() -> V6Result<()> {
    // SAFETY: the zeroed `cpu_set_t` is initialized with the libc CPU macros
    // before being passed to sched_setaffinity for the current process.
    unsafe {
        let mut set: libc::cpu_set_t = std::mem::zeroed();
        libc::CPU_ZERO(&mut set);
        libc::CPU_SET(MEASUREMENT_CPU_ORDINAL, &mut set);
        if libc::sched_setaffinity(
            0,
            std::mem::size_of::<libc::cpu_set_t>(),
            std::ptr::addr_of!(set),
        ) != 0
        {
            return Err(NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 measurement affinity cannot be pinned",
            ));
        }
    }
    let observed = current_affinity()?;
    if !affinity_is_exact_measurement_cpu(&observed) {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 measurement affinity did not persist",
        ));
    }
    Ok(())
}

fn read_boost_disabled() -> V6Result<bool> {
    let path =
        CString::new("/sys/devices/system/cpu/cpufreq/boost").expect("static path contains no NUL");
    // SAFETY: the static C string is valid for the duration of open.
    let raw_fd = unsafe {
        libc::open(
            path.as_ptr(),
            libc::O_RDONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW,
        )
    };
    if raw_fd < 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 boost state is unavailable",
        ));
    }
    // SAFETY: a successful open returns an owned descriptor.
    let mut file = unsafe { fs::File::from_raw_fd(raw_fd) };
    let metadata = file.metadata().map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 boost metadata is unavailable",
        )
    })?;
    if !metadata.file_type().is_file()
        || metadata.uid() != 0
        || metadata.nlink() != 1
        || metadata.mode() & 0o022 != 0
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 boost state identity is untrusted",
        ));
    }
    let mut raw = Vec::with_capacity(32);
    std::io::Read::by_ref(&mut file)
        .take(33)
        .read_to_end(&mut raw)
        .map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 boost state cannot be read",
            )
        })?;
    match raw.as_slice() {
        b"0" | b"0\n" => Ok(true),
        b"1" | b"1\n" => Ok(false),
        _ => Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 boost state payload is invalid",
        )),
    }
}

fn blocker_from<T>(result: V6Result<T>, blockers: &mut Vec<String>, code: &str) -> Option<T> {
    match result {
        Ok(value) => Some(value),
        Err(_) => {
            blockers.push(code.to_owned());
            None
        }
    }
}

/// Run the non-consuming host and source preflight. It never creates state.
pub fn preflight_native_fixed64_cpu_v6() -> V6Result<Fixed64CpuPreflightV6> {
    let activation = verify_native_fixed64_cpu_v6_activation()?;
    let mut blockers = Vec::new();
    let source_commit_oid = blocker_from(
        source_checkout_evidence(),
        &mut blockers,
        "source_checkout_not_exact_main",
    );
    let model = blocker_from(cpu_model(), &mut blockers, "cpu_model_not_qualified");
    let boost_disabled = blocker_from(
        read_boost_disabled(),
        &mut blockers,
        "boost_state_unavailable",
    );
    if boost_disabled == Some(false) {
        blockers.push("boost_not_disabled".to_owned());
    }
    let affinity = blocker_from(current_affinity(), &mut blockers, "affinity_unavailable");
    let measurement_cpu_available = affinity
        .as_ref()
        .is_some_and(|value| cpu_is_set(value, MEASUREMENT_CPU_ORDINAL));
    if !measurement_cpu_available {
        blockers.push("measurement_cpu_unavailable".to_owned());
    }
    let task_count = blocker_from(
        process_task_count(),
        &mut blockers,
        "process_task_count_unavailable",
    );
    if task_count.is_some_and(|value| value != 1) {
        blockers.push("process_task_count_not_one".to_owned());
    }
    blockers.sort();
    blockers.dedup();
    Ok(Fixed64CpuPreflightV6 {
        profile_sha256: activation.profile_sha256,
        activation_sha256: activation.activation_sha256,
        source_commit_oid,
        cpu_model: model,
        boost_disabled,
        measurement_cpu_available,
        process_task_count: task_count,
        blockers,
    })
}

fn c_string_path(path: &Path, label: &str) -> V6Result<CString> {
    CString::new(path.as_os_str().as_bytes()).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} contains NUL"
        ))
    })
}

fn fstat_descriptor(descriptor: RawFd, label: &str) -> V6Result<libc::stat> {
    // SAFETY: fstat initializes the supplied stat buffer for a valid descriptor.
    unsafe {
        let mut metadata: libc::stat = std::mem::zeroed();
        if libc::fstat(descriptor, std::ptr::addr_of_mut!(metadata)) != 0 {
            return Err(NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} metadata is unavailable"
            )));
        }
        Ok(metadata)
    }
}

fn is_directory_mode(mode: libc::mode_t) -> bool {
    mode & libc::S_IFMT == libc::S_IFDIR
}

fn is_regular_mode(mode: libc::mode_t) -> bool {
    mode & libc::S_IFMT == libc::S_IFREG
}

fn login_account_home() -> V6Result<PathBuf> {
    // SAFETY: getpwuid_r receives an initialized passwd and an owned scratch
    // buffer; result is used only while the scratch buffer remains alive.
    unsafe {
        let uid = libc::geteuid();
        let requested = libc::sysconf(libc::_SC_GETPW_R_SIZE_MAX);
        let capacity = if requested < 1024 {
            16 * 1024
        } else {
            usize::try_from(requested)
                .unwrap_or(16 * 1024)
                .min(1024 * 1024)
        };
        let mut scratch = vec![0_u8; capacity];
        let mut passwd: libc::passwd = std::mem::zeroed();
        let mut result: *mut libc::passwd = std::ptr::null_mut();
        let status = libc::getpwuid_r(
            uid,
            std::ptr::addr_of_mut!(passwd),
            scratch.as_mut_ptr().cast(),
            scratch.len(),
            std::ptr::addr_of_mut!(result),
        );
        if status != 0 || result.is_null() || passwd.pw_dir.is_null() || passwd.pw_uid != uid {
            return Err(NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 login account home is unavailable",
            ));
        }
        let bytes = CStr::from_ptr(passwd.pw_dir).to_bytes().to_vec();
        let home = PathBuf::from(std::ffi::OsString::from_vec(bytes));
        if !home.is_absolute() || fs::canonicalize(&home).ok().as_ref() != Some(&home) {
            return Err(NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 login account home is not canonical",
            ));
        }
        Ok(home)
    }
}

fn open_owned_directory(path: &Path, exact_owner_only: bool, label: &str) -> V6Result<OwnedFd> {
    let raw_path = c_string_path(path, label)?;
    // SAFETY: raw_path is a valid NUL-terminated path and a successful open
    // returns one owned descriptor.
    let descriptor = unsafe {
        libc::open(
            raw_path.as_ptr(),
            libc::O_RDONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW | libc::O_DIRECTORY,
        )
    };
    if descriptor < 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} cannot be opened safely"
        )));
    }
    // SAFETY: descriptor was returned by open and is now uniquely owned.
    let owned = unsafe { OwnedFd::from_raw_fd(descriptor) };
    let metadata = fstat_descriptor(owned.as_raw_fd(), label)?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    let permissions = metadata.st_mode & 0o777;
    if !is_directory_mode(metadata.st_mode)
        || metadata.st_uid != uid
        || metadata.st_nlink < 2
        || permissions & 0o022 != 0
        || (exact_owner_only && permissions != 0o700)
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} identity is untrusted"
        )));
    }
    Ok(owned)
}

fn open_or_create_owner_directory(parent: RawFd, name: &str, label: &str) -> V6Result<OwnedFd> {
    let raw_name = CString::new(name).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} name is invalid"
        ))
    })?;
    // SAFETY: parent is an open directory and raw_name is a single component.
    let created = unsafe { libc::mkdirat(parent, raw_name.as_ptr(), 0o700) } == 0;
    if !created {
        let error = io::Error::last_os_error();
        if error.raw_os_error() != Some(libc::EEXIST) {
            return Err(NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} cannot be created"
            )));
        }
    }
    // SAFETY: a successful openat returns one owned descriptor.
    let descriptor = unsafe {
        libc::openat(
            parent,
            raw_name.as_ptr(),
            libc::O_RDONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW | libc::O_DIRECTORY,
        )
    };
    if descriptor < 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} cannot be opened safely"
        )));
    }
    // SAFETY: descriptor was returned by openat and is now uniquely owned.
    let owned = unsafe { OwnedFd::from_raw_fd(descriptor) };
    if created {
        // SAFETY: descriptor is open and the mode contains only permission bits.
        if unsafe { libc::fchmod(owned.as_raw_fd(), 0o700) } != 0 {
            return Err(NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} permissions cannot be sealed"
            )));
        }
    }
    let metadata = fstat_descriptor(owned.as_raw_fd(), label)?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    if !is_directory_mode(metadata.st_mode)
        || metadata.st_uid != uid
        || metadata.st_nlink < 2
        || metadata.st_mode & 0o777 != 0o700
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} identity is untrusted"
        )));
    }
    // SAFETY: fsync on an open directory persists its entries on Linux.
    if created && unsafe { libc::fsync(parent) } != 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} parent cannot be synchronized"
        )));
    }
    Ok(owned)
}

fn open_account_state(profile_sha256: &str) -> V6Result<AccountStateDirectory> {
    if profile_sha256.len() != 64 || !profile_sha256.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 profile digest is invalid",
        ));
    }
    let home = login_account_home()?;
    let home_descriptor = open_owned_directory(&home, false, "login account home")?;
    let root = open_or_create_owner_directory(
        home_descriptor.as_raw_fd(),
        STATE_ROOT_NAME,
        "account state root",
    )?;
    let qualification = open_or_create_owner_directory(
        root.as_raw_fd(),
        STATE_QUALIFICATION_NAME,
        "qualification state root",
    )?;
    let profile = open_or_create_owner_directory(
        qualification.as_raw_fd(),
        profile_sha256,
        "profile state directory",
    )?;
    let metadata = fstat_descriptor(profile.as_raw_fd(), "profile state directory")?;
    Ok(AccountStateDirectory {
        path: home
            .join(STATE_ROOT_NAME)
            .join(STATE_QUALIFICATION_NAME)
            .join(profile_sha256),
        descriptor: profile,
        device: metadata.st_dev,
        inode: metadata.st_ino,
    })
}

fn require_account_state_binding(state: &AccountStateDirectory) -> V6Result<()> {
    let descriptor = fstat_descriptor(state.descriptor.as_raw_fd(), "profile state directory")?;
    let path = fs::symlink_metadata(&state.path).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 profile state path is unavailable",
        )
    })?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    if descriptor.st_dev != state.device
        || descriptor.st_ino != state.inode
        || path.dev() != state.device
        || path.ino() != state.inode
        || !path.file_type().is_dir()
        || path.uid() != uid
        || path.mode() & 0o777 != 0o700
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 profile state binding changed",
        ));
    }
    Ok(())
}

fn path_exists_at(parent: RawFd, name: &CStr) -> V6Result<bool> {
    // SAFETY: fstatat initializes metadata when the fixed relative name exists.
    unsafe {
        let mut metadata: libc::stat = std::mem::zeroed();
        if libc::fstatat(
            parent,
            name.as_ptr(),
            std::ptr::addr_of_mut!(metadata),
            libc::AT_SYMLINK_NOFOLLOW,
        ) == 0
        {
            return Ok(true);
        }
    }
    let error = io::Error::last_os_error();
    if error.raw_os_error() == Some(libc::ENOENT) {
        Ok(false)
    } else {
        Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 path state is ambiguous",
        ))
    }
}

fn validate_absent_output(path: &Path) -> V6Result<ValidatedOutputTarget> {
    if !path.is_absolute()
        || path.to_str().is_none()
        || path.as_os_str().as_bytes().len() > 4096
        || path.extension() != Some(OsStr::new("json"))
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output path is invalid",
        ));
    }
    let name = path.file_name().ok_or_else(|| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output filename is invalid",
        )
    })?;
    if name.as_bytes().is_empty() || name.as_bytes().len() > 240 {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output filename is invalid",
        ));
    }
    let parent = path.parent().ok_or_else(|| {
        NativeFixed64CpuQualificationV6Error::new("native fixed64 CPU v6 output parent is invalid")
    })?;
    let canonical_parent = fs::canonicalize(parent).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent is unavailable",
        )
    })?;
    if canonical_parent != parent || path != canonical_parent.join(name) {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent traverses a symlink",
        ));
    }
    if path.starts_with(source_root()?) {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output cannot modify the source checkout",
        ));
    }
    let account_home = login_account_home()?;
    if account_home.to_str().is_none() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 account home path is not UTF-8",
        ));
    }
    let account_state_root = account_home.join(STATE_ROOT_NAME);
    if path.starts_with(account_state_root)
        || name == OsStr::new(ATTEMPT_FILENAME)
        || name == OsStr::new(TERMINAL_FILENAME)
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output cannot cross-wire account state",
        ));
    }
    let metadata = fs::symlink_metadata(&canonical_parent).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent metadata is unavailable",
        )
    })?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    if !metadata.file_type().is_dir() || metadata.uid() != uid || metadata.mode() & 0o022 != 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent is not owner controlled",
        ));
    }
    let parent_descriptor =
        open_owned_directory(&canonical_parent, false, "output parent directory")?;
    let bound = fstat_descriptor(parent_descriptor.as_raw_fd(), "output parent directory")?;
    if bound.st_dev != metadata.dev() || bound.st_ino != metadata.ino() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent changed during binding",
        ));
    }
    let raw_name = CString::new(name.as_bytes()).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output filename contains NUL",
        )
    })?;
    // SAFETY: fpathconf only reads the limit associated with this open
    // directory descriptor.
    let name_max = unsafe { libc::fpathconf(parent_descriptor.as_raw_fd(), libc::_PC_NAME_MAX) };
    let staging_name_length = name
        .as_bytes()
        .len()
        .checked_add(STAGING_NAME_OVERHEAD_BYTES)
        .ok_or_else(|| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 output staging filename length overflowed",
            )
        })?;
    if name_max < 1
        || usize::try_from(name_max)
            .ok()
            .is_none_or(|maximum| staging_name_length > maximum)
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output filename cannot support atomic staging",
        ));
    }
    if path_exists_at(parent_descriptor.as_raw_fd(), &raw_name)? {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output must be absent",
        ));
    }
    Ok(ValidatedOutputTarget {
        path: path.to_path_buf(),
        parent_path: canonical_parent,
        name: raw_name,
        parent_descriptor,
        parent_device: bound.st_dev,
        parent_inode: bound.st_ino,
    })
}

fn require_output_parent_binding(target: &ValidatedOutputTarget) -> V6Result<()> {
    let metadata = fstat_descriptor(
        target.parent_descriptor.as_raw_fd(),
        "output parent directory",
    )?;
    let path = fs::symlink_metadata(&target.parent_path).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent path is unavailable",
        )
    })?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    if metadata.st_dev != target.parent_device
        || metadata.st_ino != target.parent_inode
        || path.dev() != target.parent_device
        || path.ino() != target.parent_inode
        || !path.file_type().is_dir()
        || !is_directory_mode(metadata.st_mode)
        || metadata.st_uid != uid
        || path.uid() != uid
        || metadata.st_mode & 0o022 != 0
        || path.mode() & 0o022 != 0
        || metadata.st_mode != path.mode()
        || metadata.st_gid != path.gid()
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 output parent binding changed",
        ));
    }
    Ok(())
}

fn random_nonce() -> V6Result<[u8; 32]> {
    let mut nonce = [0_u8; 32];
    let mut offset = 0;
    while offset < nonce.len() {
        // SAFETY: the remaining nonce slice is valid writable memory.
        let received = unsafe {
            libc::getrandom(nonce[offset..].as_mut_ptr().cast(), nonce.len() - offset, 0)
        };
        if received <= 0 {
            return Err(NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 run nonce is unavailable",
            ));
        }
        offset += usize::try_from(received).map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 run nonce length is invalid",
            )
        })?;
    }
    Ok(nonce)
}

fn process_start_ticks() -> V6Result<u64> {
    let raw = fs::read_to_string("/proc/self/stat").map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 process identity is unavailable",
        )
    })?;
    let close = raw.rfind(") ").ok_or_else(|| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 process identity is invalid",
        )
    })?;
    raw[close + 2..]
        .split_ascii_whitespace()
        .nth(19)
        .ok_or_else(|| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 process start time is missing",
            )
        })?
        .parse::<u64>()
        .map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(
                "native fixed64 CPU v6 process start time is invalid",
            )
        })
}

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

fn json_string_array(values: &[String]) -> String {
    let body = values
        .iter()
        .map(|value| json_string(value))
        .collect::<Vec<_>>()
        .join(",");
    format!("[{body}]")
}

fn json_optional_string(value: Option<&str>) -> String {
    value.map_or_else(|| "null".to_owned(), json_string)
}

fn json_optional_bool(value: Option<bool>) -> &'static str {
    match value {
        Some(true) => "true",
        Some(false) => "false",
        None => "null",
    }
}

fn json_optional_usize(value: Option<usize>) -> String {
    value.map_or_else(|| "null".to_owned(), |value| value.to_string())
}

fn json_u64_array(values: &[u64]) -> String {
    let body = values
        .iter()
        .map(u64::to_string)
        .collect::<Vec<_>>()
        .join(",");
    format!("[{body}]")
}

fn json_f64(value: f64) -> V6Result<String> {
    if !value.is_finite() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 evidence contains a non-finite number",
        ));
    }
    Ok(value.to_string())
}

fn write_exclusive_state_file(directory: RawFd, filename: &str, raw: &[u8]) -> V6Result<()> {
    if raw.is_empty() || raw.len() > MAX_STATE_BYTES {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 state bytes are outside the envelope",
        ));
    }
    let name = CString::new(filename).expect("fixed state filename contains no NUL");
    // SAFETY: directory is open, name is relative, and a successful openat
    // returns one newly owned descriptor.
    let descriptor = unsafe {
        libc::openat(
            directory,
            name.as_ptr(),
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            0o600,
        )
    };
    if descriptor < 0 {
        let error = io::Error::last_os_error();
        let message = if error.raw_os_error() == Some(libc::EEXIST) {
            "native fixed64 CPU v6 exactly-once state was already consumed"
        } else {
            "native fixed64 CPU v6 state cannot be created atomically"
        };
        return Err(NativeFixed64CpuQualificationV6Error::new(message));
    }
    // SAFETY: descriptor was returned by openat and is now uniquely owned.
    let owned = unsafe { OwnedFd::from_raw_fd(descriptor) };
    // SAFETY: descriptor is valid and the mode contains only permission bits.
    if unsafe { libc::fchmod(owned.as_raw_fd(), 0o600) } != 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 state permissions cannot be sealed",
        ));
    }
    let initial = fstat_descriptor(owned.as_raw_fd(), "state file")?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    if !is_regular_mode(initial.st_mode)
        || initial.st_uid != uid
        || initial.st_nlink != 1
        || initial.st_size != 0
        || initial.st_mode & 0o777 != 0o600
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 initial state identity is invalid",
        ));
    }
    let mut file = fs::File::from(owned);
    file.write_all(raw).map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new("native fixed64 CPU v6 state write failed")
    })?;
    file.sync_all().map_err(|_| {
        NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 state cannot be synchronized",
        )
    })?;
    let final_metadata = fstat_descriptor(file.as_raw_fd(), "state file")?;
    if final_metadata.st_dev != initial.st_dev
        || final_metadata.st_ino != initial.st_ino
        || final_metadata.st_nlink != 1
        || final_metadata.st_size != i64::try_from(raw.len()).unwrap_or(-1)
        || final_metadata.st_mode & 0o777 != 0o600
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 final state identity is invalid",
        ));
    }
    // SAFETY: fsync on an open directory persists its entries on Linux.
    if unsafe { libc::fsync(directory) } != 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 state directory cannot be synchronized",
        ));
    }
    Ok(())
}

fn read_bounded_file_at(
    directory: RawFd,
    name: &CStr,
    maximum: usize,
    label: &str,
) -> V6Result<Vec<u8>> {
    // SAFETY: directory is open, name is relative, and a successful openat
    // returns one newly owned descriptor.
    let descriptor = unsafe {
        libc::openat(
            directory,
            name.as_ptr(),
            libc::O_RDONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW,
        )
    };
    if descriptor < 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} cannot be opened safely"
        )));
    }
    // SAFETY: descriptor was returned by openat and is now uniquely owned.
    let owned = unsafe { OwnedFd::from_raw_fd(descriptor) };
    let before = fstat_descriptor(owned.as_raw_fd(), label)?;
    // SAFETY: geteuid has no preconditions.
    let uid = unsafe { libc::geteuid() };
    if !is_regular_mode(before.st_mode)
        || before.st_uid != uid
        || before.st_nlink != 1
        || before.st_mode & 0o777 != 0o600
        || before.st_size < 1
        || usize::try_from(before.st_size)
            .ok()
            .is_none_or(|size| size > maximum)
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} identity is invalid"
        )));
    }
    let mut file = fs::File::from(owned);
    let mut raw = Vec::with_capacity(usize::try_from(before.st_size).unwrap_or(0));
    std::io::Read::by_ref(&mut file)
        .take(u64::try_from(maximum).unwrap_or(u64::MAX) + 1)
        .read_to_end(&mut raw)
        .map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} cannot be read"
            ))
        })?;
    let after = fstat_descriptor(file.as_raw_fd(), label)?;
    if raw.len() > maximum
        || usize::try_from(before.st_size).ok() != Some(raw.len())
        || before.st_dev != after.st_dev
        || before.st_ino != after.st_ino
        || before.st_mode != after.st_mode
        || before.st_uid != after.st_uid
        || before.st_gid != after.st_gid
        || before.st_nlink != after.st_nlink
        || before.st_size != after.st_size
        || before.st_mtime != after.st_mtime
        || before.st_mtime_nsec != after.st_mtime_nsec
        || before.st_ctime != after.st_ctime
        || before.st_ctime_nsec != after.st_ctime_nsec
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} changed while read"
        )));
    }
    Ok(raw)
}

fn publish_absent_file_at(
    directory: RawFd,
    target_name: &CStr,
    raw: &[u8],
    maximum: usize,
    label: &str,
) -> V6Result<Vec<u8>> {
    if raw.is_empty() || raw.len() > maximum {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} bytes are outside the envelope"
        )));
    }
    if path_exists_at(directory, target_name)? {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} target already exists"
        )));
    }
    let nonce = digest_hex(random_nonce()?);
    let mut temporary_bytes = Vec::with_capacity(
        target_name
            .to_bytes()
            .len()
            .saturating_add(STAGING_NAME_OVERHEAD_BYTES),
    );
    temporary_bytes.push(b'.');
    temporary_bytes.extend_from_slice(target_name.to_bytes());
    temporary_bytes.extend_from_slice(b".tmp.");
    temporary_bytes.extend_from_slice(nonce.as_bytes());
    let temporary =
        CString::new(temporary_bytes).expect("generated temporary filename contains no NUL");
    // SAFETY: directory is open, temporary is relative, and successful openat
    // returns one newly owned descriptor.
    let descriptor = unsafe {
        libc::openat(
            directory,
            temporary.as_ptr(),
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            0o600,
        )
    };
    if descriptor < 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} staging file cannot be created"
        )));
    }
    // SAFETY: descriptor was returned by openat and is now uniquely owned.
    let owned = unsafe { OwnedFd::from_raw_fd(descriptor) };
    // SAFETY: descriptor is valid and mode contains only permission bits.
    if unsafe { libc::fchmod(owned.as_raw_fd(), 0o600) } != 0 {
        // SAFETY: temporary is the exact file just created in this directory.
        unsafe { libc::unlinkat(directory, temporary.as_ptr(), 0) };
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} staging permissions cannot be sealed"
        )));
    }
    let initial = fstat_descriptor(owned.as_raw_fd(), label)?;
    let mut file = fs::File::from(owned);
    let write_result = (|| -> V6Result<()> {
        if !is_regular_mode(initial.st_mode)
            || initial.st_nlink != 1
            || initial.st_size != 0
            || initial.st_mode & 0o777 != 0o600
        {
            return Err(NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} staging identity is invalid"
            )));
        }
        file.write_all(raw).map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} write failed"
            ))
        })?;
        file.sync_all().map_err(|_| {
            NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} cannot be synchronized"
            ))
        })?;
        let final_metadata = fstat_descriptor(file.as_raw_fd(), label)?;
        if final_metadata.st_dev != initial.st_dev
            || final_metadata.st_ino != initial.st_ino
            || final_metadata.st_nlink != 1
            || final_metadata.st_size != i64::try_from(raw.len()).unwrap_or(-1)
            || final_metadata.st_mode & 0o777 != 0o600
        {
            return Err(NativeFixed64CpuQualificationV6Error::new(format!(
                "native fixed64 CPU v6 {label} staging identity changed"
            )));
        }
        Ok(())
    })();
    if let Err(error) = write_result {
        // SAFETY: temporary still names the staging inode owned by this call.
        unsafe { libc::unlinkat(directory, temporary.as_ptr(), 0) };
        return Err(error);
    }
    // SAFETY: linkat adds the absent target name to the staging inode.
    if unsafe {
        libc::linkat(
            directory,
            temporary.as_ptr(),
            directory,
            target_name.as_ptr(),
            0,
        )
    } != 0
    {
        // SAFETY: temporary still names the staging inode owned by this call.
        unsafe { libc::unlinkat(directory, temporary.as_ptr(), 0) };
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} cannot be published atomically"
        )));
    }
    let linked = fstat_descriptor(file.as_raw_fd(), label)?;
    if linked.st_nlink != 2 {
        // SAFETY: both names refer to the staging inode owned by this call.
        unsafe {
            libc::unlinkat(directory, target_name.as_ptr(), 0);
            libc::unlinkat(directory, temporary.as_ptr(), 0);
        }
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} published link identity is invalid"
        )));
    }
    // SAFETY: temporary is the staging name owned by this call.
    if unsafe { libc::unlinkat(directory, temporary.as_ptr(), 0) } != 0 {
        // Leave both links as fail-closed ambiguous evidence rather than risk
        // deleting a target whose state cannot be proved.
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} staging name cannot be retired"
        )));
    }
    if fstat_descriptor(file.as_raw_fd(), label)?.st_nlink != 1 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} final link identity is invalid"
        )));
    }
    // SAFETY: fsync on an open directory persists its entries on Linux.
    if unsafe { libc::fsync(directory) } != 0 {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} directory cannot be synchronized"
        )));
    }
    let observed = read_bounded_file_at(directory, target_name, maximum, label)?;
    if observed != raw {
        return Err(NativeFixed64CpuQualificationV6Error::new(format!(
            "native fixed64 CPU v6 {label} published bytes changed"
        )));
    }
    Ok(observed)
}

fn create_attempt(
    state_directory: RawFd,
    activation: &Fixed64CpuActivationStatusV6,
    output_path_sha256: String,
) -> V6Result<AttemptLeaseV6> {
    let attempt_name = CString::new(ATTEMPT_FILENAME).expect("fixed filename contains no NUL");
    let terminal_name = CString::new(TERMINAL_FILENAME).expect("fixed filename contains no NUL");
    if path_exists_at(state_directory, &attempt_name)? {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 exactly-once profile attempt was already consumed",
        ));
    }
    if path_exists_at(state_directory, &terminal_name)? {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 terminal exists without an available attempt",
        ));
    }
    let run_nonce = digest_hex(random_nonce()?);
    // SAFETY: getpid has no preconditions.
    let process_id = unsafe { libc::getpid() };
    let projection = format!(
        concat!(
            "{{\"activation_sha256\":\"{}\",",
            "\"attempt_ordinal\":1,",
            "\"authority\":{},",
            "\"measurement_started\":false,",
            "\"output_path_sha256\":\"{}\",",
            "\"process_id\":{},",
            "\"process_start_ticks\":{},",
            "\"profile_id\":\"{}\",",
            "\"profile_sha256\":\"{}\",",
            "\"restrictions\":{},",
            "\"run_nonce\":\"{}\",",
            "\"schema_id\":\"{}\"}}"
        ),
        activation.activation_sha256,
        AUTHORITY_FALSE_JSON,
        output_path_sha256,
        process_id,
        process_start_ticks()?,
        activation.profile_id,
        activation.profile_sha256,
        RESTRICTIONS_JSON,
        run_nonce,
        ATTEMPT_SCHEMA_ID,
    );
    let receipt_sha256 = domain_digest(ATTEMPT_DOMAIN, projection.as_bytes());
    let raw = format!(
        "{{\"projection\":{},\"receipt_sha256\":\"{}\"}}\n",
        projection, receipt_sha256
    )
    .into_bytes();
    write_exclusive_state_file(state_directory, ATTEMPT_FILENAME, &raw)?;
    let observed = read_bounded_file_at(
        state_directory,
        &attempt_name,
        MAX_STATE_BYTES,
        "attempt ledger",
    )?;
    if observed != raw {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 attempt ledger changed after creation",
        ));
    }
    Ok(AttemptLeaseV6 {
        raw_sha256: sha256_hex(&raw),
        raw,
        receipt_sha256,
        run_nonce,
        output_path_sha256,
    })
}

fn report_contract_is_valid(report: &Fixed64CpuProbeReportV5) -> bool {
    report.schema_id == FIXED64_CPU_QUALIFICATION_V6_SCHEMA_ID
        && report.profile_id == FIXED64_CPU_QUALIFICATION_V6_PROFILE_ID
        && !report.qualification_authority
        && !report.molecular_execution_authorized
        && !report.reservation_authorized
        && !report.public_benchmark_authorized
        && !report.product_performance_claim_authorized
        && report.fixtures.len() == 2
        && report.fixtures.iter().all(|fixture| {
            fixture.candidate_denominator == 64
                && fixture.receptor_atom_count == 12
                && fixture.ligand_atom_count == 12
                && fixture.score_term_count == 8
                && fixture.generated_count == fixture.cpp_generated_count
                && fixture.typed_failure_count == fixture.cpp_typed_failure_count
                && fixture.cpp_generated_count + fixture.cpp_typed_failure_count == 64
                && fixture.rust_generated_count + fixture.rust_typed_failure_count == 64
                && fixture.authority_false
        })
}

fn execute_measurement(preflight: &Fixed64CpuPreflightV6) -> MeasurementOutcomeV6 {
    let mut blockers = preflight.blockers.clone();
    if !preflight.ready() {
        return MeasurementOutcomeV6 {
            report: None,
            measurement_started: false,
            blockers,
        };
    }
    if pin_measurement_cpu().is_err() {
        blockers.push("measurement_affinity_pin_failed".to_owned());
        return MeasurementOutcomeV6 {
            report: None,
            measurement_started: false,
            blockers,
        };
    }
    if process_task_count().ok() != Some(1) {
        blockers.push("post_pin_process_task_count_not_one".to_owned());
        return MeasurementOutcomeV6 {
            report: None,
            measurement_started: false,
            blockers,
        };
    }
    if read_boost_disabled().ok() != Some(true) {
        blockers.push("post_pin_boost_not_disabled".to_owned());
        return MeasurementOutcomeV6 {
            report: None,
            measurement_started: false,
            blockers,
        };
    }
    let result = run_native_fixed64_cpu_qualification_successor(
        FIXED64_CPU_QUALIFICATION_V6_SCHEMA_ID,
        FIXED64_CPU_QUALIFICATION_V6_PROFILE_ID,
    );
    let mut report = match result {
        Ok(value) if report_contract_is_valid(&value) => Some(value),
        Ok(_) => {
            blockers.push("native_measurement_report_contract_failed".to_owned());
            None
        }
        Err(_) => {
            blockers.push("native_measurement_failed".to_owned());
            None
        }
    };
    let post_measurement_host_valid = current_affinity()
        .ok()
        .as_ref()
        .is_some_and(affinity_is_exact_measurement_cpu)
        && read_boost_disabled().ok() == Some(true)
        && process_task_count().ok() == Some(1)
        && cpu_model().ok().as_ref() == preflight.cpu_model.as_ref()
        && source_checkout_evidence().ok().as_ref() == preflight.source_commit_oid.as_ref();
    if !post_measurement_host_valid {
        blockers.push("post_measurement_host_invariant_failed".to_owned());
        report = None;
    }
    if report.as_ref().is_some_and(|value| !value.gate_passed) {
        blockers.push("native_qualification_gate_failed".to_owned());
    }
    blockers.sort();
    blockers.dedup();
    MeasurementOutcomeV6 {
        report,
        measurement_started: true,
        blockers,
    }
}

fn fixture_json(value: &Fixed64CpuFixtureProbeV5) -> V6Result<String> {
    let first_violation = value
        .numeric_parity
        .first_violation_index
        .map_or_else(|| "null".to_owned(), |index| index.to_string());
    Ok(format!(
        concat!(
            "{{\"authority_false\":{},",
            "\"candidate_denominator\":{},",
            "\"cpp_decision_sha256\":\"{}\",",
            "\"cpp_generated_count\":{},",
            "\"cpp_median_nanoseconds\":{},",
            "\"cpp_projection_sha256\":\"{}\",",
            "\"cpp_repeat_stable\":{},",
            "\"cpp_sample_nanoseconds\":{},",
            "\"cpp_typed_failure_count\":{},",
            "\"decision_parity\":{},",
            "\"fixture_id\":{},",
            "\"fixture_payload_sha256\":\"{}\",",
            "\"gate_passed\":{},",
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
            "\"rust_generated_count\":{},",
            "\"rust_median_nanoseconds\":{},",
            "\"rust_projection_sha256\":\"{}\",",
            "\"rust_repeat_stable\":{},",
            "\"rust_sample_nanoseconds\":{},",
            "\"rust_to_cpp_median_ratio\":{},",
            "\"rust_typed_failure_count\":{},",
            "\"score_term_count\":{}",
            "}}"
        ),
        value.authority_false,
        value.candidate_denominator,
        digest_hex(value.cpp_decision_sha256),
        value.cpp_generated_count,
        value.cpp_median_nanoseconds,
        digest_hex(value.cpp_projection_sha256),
        value.cpp_repeat_stable,
        json_u64_array(&value.cpp_sample_nanoseconds),
        value.cpp_typed_failure_count,
        value.decision_parity,
        json_string(value.fixture_id),
        digest_hex(value.fixture_payload_sha256),
        value.gate_passed,
        value.ligand_atom_count,
        value.numeric_parity.compared_f64_count,
        first_violation,
        json_f64(value.numeric_parity.maximum_absolute_difference)?,
        json_f64(value.numeric_parity.maximum_scaled_difference)?,
        value.numeric_parity.tolerance_violation_count,
        value.persistent_cpp_context_count,
        value.persistent_rust_context_count,
        value.receptor_atom_count,
        digest_hex(value.rust_decision_sha256),
        value.rust_generated_count,
        value.rust_median_nanoseconds,
        digest_hex(value.rust_projection_sha256),
        value.rust_repeat_stable,
        json_u64_array(&value.rust_sample_nanoseconds),
        json_f64(value.rust_to_cpp_median_ratio)?,
        value.rust_typed_failure_count,
        value.score_term_count,
    ))
}

fn build_artifact(
    activation: &Fixed64CpuActivationStatusV6,
    attempt: &AttemptLeaseV6,
    preflight: &Fixed64CpuPreflightV6,
    outcome: MeasurementOutcomeV6,
) -> V6Result<ArtifactDocumentV6> {
    let report = outcome.report.as_ref();
    let recorded_gate_passed = report.map(|value| value.gate_passed);
    let recorded_numeric_gate_passed = report.map(|value| {
        value
            .fixtures
            .iter()
            .all(|fixture| fixture.numeric_parity.passed())
    });
    let recorded_decision =
        if report.is_some_and(|value| value.gate_passed) && outcome.blockers.is_empty() {
            "PASS"
        } else if report.is_some() {
            "NO_GO"
        } else {
            "BLOCKED"
        }
        .to_owned();
    let fixtures = report
        .map(|value| {
            value
                .fixtures
                .iter()
                .map(fixture_json)
                .collect::<V6Result<Vec<_>>>()
        })
        .transpose()?
        .unwrap_or_default()
        .join(",");
    let projection = format!(
        concat!(
            "{{\"activation_sha256\":\"{}\",",
            "\"attempt_ledger_raw_sha256\":\"{}\",",
            "\"attempt_receipt_sha256\":\"{}\",",
            "\"authority\":{},",
            "\"blockers\":{},",
            "\"execution\":{{",
            "\"execution_attested\":false,",
            "\"measurement_started\":{},",
            "\"offline_replay_only\":true,",
            "\"recorded_decision\":{},",
            "\"recorded_gate_passed\":{},",
            "\"recorded_numeric_gate_passed\":{}",
            "}},",
            "\"fixtures\":[{}],",
            "\"host\":{{",
            "\"boost_disabled\":{},",
            "\"cpu_model\":{},",
            "\"measurement_cpu_available\":{},",
            "\"measurement_cpu_ordinal\":{},",
            "\"process_task_count\":{},",
            "\"source_commit_oid\":{}",
            "}},",
            "\"output_path_sha256\":\"{}\",",
            "\"profile_id\":\"{}\",",
            "\"profile_sha256\":\"{}\",",
            "\"qualification_authority\":false,",
            "\"restrictions\":{},",
            "\"run_nonce\":\"{}\",",
            "\"schema_id\":\"{}\",",
            "\"status\":\"terminal_measurement_evidence\"}}"
        ),
        activation.activation_sha256,
        attempt.raw_sha256,
        attempt.receipt_sha256,
        AUTHORITY_FALSE_JSON,
        json_string_array(&outcome.blockers),
        outcome.measurement_started,
        json_string(&recorded_decision),
        json_optional_bool(recorded_gate_passed),
        json_optional_bool(recorded_numeric_gate_passed),
        fixtures,
        json_optional_bool(preflight.boost_disabled),
        json_optional_string(preflight.cpu_model.as_deref()),
        preflight.measurement_cpu_available,
        MEASUREMENT_CPU_ORDINAL,
        json_optional_usize(preflight.process_task_count),
        json_optional_string(preflight.source_commit_oid.as_deref()),
        attempt.output_path_sha256,
        activation.profile_id,
        activation.profile_sha256,
        RESTRICTIONS_JSON,
        attempt.run_nonce,
        ARTIFACT_SCHEMA_ID,
    );
    let receipt_sha256 = domain_digest(ARTIFACT_DOMAIN, projection.as_bytes());
    let raw = format!(
        "{{\"projection\":{},\"receipt_sha256\":\"{}\"}}\n",
        projection, receipt_sha256
    )
    .into_bytes();
    if raw.len() > MAX_ARTIFACT_BYTES {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 artifact exceeds its byte envelope",
        ));
    }
    Ok(ArtifactDocumentV6 {
        raw,
        receipt_sha256,
        recorded_decision,
        recorded_gate_passed,
        blockers: outcome.blockers,
    })
}

fn build_terminal(
    activation: &Fixed64CpuActivationStatusV6,
    attempt: &AttemptLeaseV6,
    artifact: &ArtifactDocumentV6,
) -> V6Result<Vec<u8>> {
    let projection = format!(
        concat!(
            "{{\"activation_sha256\":\"{}\",",
            "\"artifact_byte_count\":{},",
            "\"artifact_persisted\":true,",
            "\"artifact_raw_sha256\":\"{}\",",
            "\"artifact_receipt_sha256\":\"{}\",",
            "\"attempt_ledger_raw_sha256\":\"{}\",",
            "\"attempt_receipt_sha256\":\"{}\",",
            "\"authority\":{},",
            "\"blockers\":{},",
            "\"decision_returned_only_after_terminal_persistence\":true,",
            "\"execution_attested\":false,",
            "\"execution_consumed\":true,",
            "\"output_path_sha256\":\"{}\",",
            "\"profile_id\":\"{}\",",
            "\"profile_sha256\":\"{}\",",
            "\"qualification_authority\":false,",
            "\"recorded_decision\":{},",
            "\"recorded_gate_passed\":{},",
            "\"restrictions\":{},",
            "\"run_nonce\":\"{}\",",
            "\"schema_id\":\"{}\",",
            "\"status\":\"terminal_recorded\"}}"
        ),
        activation.activation_sha256,
        artifact.raw.len(),
        sha256_hex(&artifact.raw),
        artifact.receipt_sha256,
        attempt.raw_sha256,
        attempt.receipt_sha256,
        AUTHORITY_FALSE_JSON,
        json_string_array(&artifact.blockers),
        attempt.output_path_sha256,
        activation.profile_id,
        activation.profile_sha256,
        json_string(&artifact.recorded_decision),
        json_optional_bool(artifact.recorded_gate_passed),
        RESTRICTIONS_JSON,
        attempt.run_nonce,
        TERMINAL_SCHEMA_ID,
    );
    let receipt_sha256 = domain_digest(TERMINAL_DOMAIN, projection.as_bytes());
    let raw = format!(
        "{{\"projection\":{},\"receipt_sha256\":\"{}\"}}\n",
        projection, receipt_sha256
    )
    .into_bytes();
    if raw.len() > MAX_STATE_BYTES {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 terminal exceeds its byte envelope",
        ));
    }
    Ok(raw)
}

fn deny_github_actions_live_execution() -> V6Result<()> {
    if env::var_os("GITHUB_ACTIONS").is_some() {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 GitHub Actions live execution is forbidden",
        ));
    }
    Ok(())
}

/// Consume the v6 local profile exactly once and persist artifact plus terminal.
///
/// This operation contains no molecular input, creates no external reservation,
/// and grants no qualification, product, public benchmark, or HIP authority.
pub fn run_native_fixed64_cpu_qualification_v6(
    output_path: &Path,
) -> V6Result<Fixed64CpuPersistedQualificationV6> {
    deny_github_actions_live_execution()?;
    let activation = verify_native_fixed64_cpu_v6_activation()?;
    let target = validate_absent_output(output_path)?;
    let state = open_account_state(&activation.profile_sha256)?;
    require_account_state_binding(&state)?;
    let output_path_sha256 = sha256_hex(target.path.as_os_str().as_bytes());
    let attempt = create_attempt(
        state.descriptor.as_raw_fd(),
        &activation,
        output_path_sha256,
    )?;
    let preflight = preflight_native_fixed64_cpu_v6()?;
    if preflight.profile_sha256 != activation.profile_sha256
        || preflight.activation_sha256 != activation.activation_sha256
    {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 preflight activation identity changed",
        ));
    }
    let measurement = execute_measurement(&preflight);
    let artifact = build_artifact(&activation, &attempt, &preflight, measurement)?;
    require_output_parent_binding(&target)?;
    let persisted_artifact = publish_absent_file_at(
        target.parent_descriptor.as_raw_fd(),
        &target.name,
        &artifact.raw,
        MAX_ARTIFACT_BYTES,
        "qualification artifact",
    )?;
    if persisted_artifact != artifact.raw {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 artifact changed after publication",
        ));
    }
    let attempt_name = CString::new(ATTEMPT_FILENAME).expect("fixed filename contains no NUL");
    let persisted_attempt = read_bounded_file_at(
        state.descriptor.as_raw_fd(),
        &attempt_name,
        MAX_STATE_BYTES,
        "attempt ledger",
    )?;
    if persisted_attempt != attempt.raw {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 attempt ledger changed during execution",
        ));
    }
    let terminal_raw = build_terminal(&activation, &attempt, &artifact)?;
    require_account_state_binding(&state)?;
    let terminal_name = CString::new(TERMINAL_FILENAME).expect("fixed filename contains no NUL");
    let persisted_terminal = publish_absent_file_at(
        state.descriptor.as_raw_fd(),
        &terminal_name,
        &terminal_raw,
        MAX_STATE_BYTES,
        "terminal state",
    )?;
    if persisted_terminal != terminal_raw {
        return Err(NativeFixed64CpuQualificationV6Error::new(
            "native fixed64 CPU v6 terminal changed after publication",
        ));
    }
    require_account_state_binding(&state)?;
    require_output_parent_binding(&target)?;
    Ok(Fixed64CpuPersistedQualificationV6 {
        artifact_path: target.path,
        attempt_ledger_path: state.path.join(ATTEMPT_FILENAME),
        terminal_state_path: state.path.join(TERMINAL_FILENAME),
        artifact_sha256: sha256_hex(&persisted_artifact),
        terminal_state_sha256: sha256_hex(&persisted_terminal),
        recorded_decision: artifact.recorded_decision,
        blockers: artifact.blockers,
        qualification_authority: false,
    })
}

#[cfg(test)]
mod tests {
    use std::ffi::OsString;
    use std::os::unix::ffi::OsStringExt as _;
    use std::os::unix::fs::PermissionsExt as _;
    use std::sync::{Arc, Barrier};
    use std::thread;

    use super::*;

    struct TestDirectory {
        path: PathBuf,
        descriptor: OwnedFd,
    }

    impl TestDirectory {
        fn new() -> Self {
            let path = PathBuf::from(format!(
                "/tmp/betelgeuze-fixed64-v6-test-{}-{}",
                std::process::id(),
                digest_hex(random_nonce().expect("test nonce"))
            ));
            fs::create_dir(&path).expect("create test directory");
            fs::set_permissions(&path, fs::Permissions::from_mode(0o700))
                .expect("seal test directory");
            let descriptor =
                open_owned_directory(&path, true, "test directory").expect("open test directory");
            Self { path, descriptor }
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.path).expect("remove isolated test directory");
        }
    }

    fn test_activation() -> Fixed64CpuActivationStatusV6 {
        Fixed64CpuActivationStatusV6 {
            profile_id: FIXED64_CPU_QUALIFICATION_V6_PROFILE_ID,
            profile_sha256: "11".repeat(32),
            activation_sha256: "22".repeat(32),
            live_execution_implemented: true,
            execution_consumed: false,
            qualification_authority: false,
            molecular_execution_authorized: false,
            public_benchmark_authorized: false,
            product_performance_claim_authorized: false,
            hip_device_execution_authorized: false,
        }
    }

    #[test]
    fn fixture_artifact_persists_each_backend_failure_denominator() {
        let report = crate::qualification::run_native_fixed64_cpu_probe_v5(
            crate::qualification::Fixed64CpuProbeConfigV5::unit_test(),
        )
        .expect("synthetic fixed64 backend evidence");
        for fixture in &report.fixtures {
            let text = fixture_json(fixture).expect("serialize fixture evidence");
            assert!(text.contains("\"cpp_generated_count\":"));
            assert!(text.contains("\"cpp_typed_failure_count\":"));
            assert!(text.contains("\"rust_generated_count\":"));
            assert!(text.contains("\"rust_typed_failure_count\":"));
            assert!(!text.contains("\"generated_count\":"));
            assert!(!text.contains("\"typed_failure_count\":"));
            assert!(!text.contains(",}"));
        }
    }

    #[test]
    fn compile_bound_activation_is_non_consuming_and_all_authority_false() {
        let status = verify_native_fixed64_cpu_v6_activation().expect("activation contract");
        assert!(status.live_execution_implemented);
        assert!(!status.execution_consumed);
        assert!(!status.qualification_authority);
        assert!(!status.molecular_execution_authorized);
        assert!(!status.public_benchmark_authorized);
        assert!(!status.product_performance_claim_authorized);
        assert!(!status.hip_device_execution_authorized);
    }

    #[test]
    fn absent_only_publication_preserves_exact_bytes_and_rejects_replacement() {
        let directory = TestDirectory::new();
        let name = CString::new("artifact.json").unwrap();
        let raw = b"{\"authority\":false}\n";
        let observed = publish_absent_file_at(
            directory.descriptor.as_raw_fd(),
            &name,
            raw,
            4096,
            "test artifact",
        )
        .expect("publish once");
        assert_eq!(observed, raw);
        let error = publish_absent_file_at(
            directory.descriptor.as_raw_fd(),
            &name,
            b"{}\n",
            4096,
            "test artifact",
        )
        .expect_err("replacement must fail");
        assert!(error.message().contains("already exists"));
        assert_eq!(
            read_bounded_file_at(
                directory.descriptor.as_raw_fd(),
                &name,
                4096,
                "test artifact"
            )
            .unwrap(),
            raw
        );
    }

    #[test]
    fn output_cannot_cross_wire_state_names() {
        let directory = TestDirectory::new();
        for name in [ATTEMPT_FILENAME, TERMINAL_FILENAME] {
            let error = validate_absent_output(&directory.path.join(name))
                .expect_err("state filename must be rejected");
            assert!(error.message().contains("cross-wire account state"));
        }
    }

    #[test]
    fn output_validation_reserves_the_complete_atomic_staging_name() {
        let directory = TestDirectory::new();
        let exact_limit = format!("{}.json", "a".repeat(180));
        validate_absent_output(&directory.path.join(exact_limit))
            .expect("185-byte target leaves room for the staging suffix");
        let too_long = format!("{}.json", "a".repeat(181));
        let error = validate_absent_output(&directory.path.join(too_long))
            .expect_err("186-byte target cannot be staged under NAME_MAX=255");
        assert!(error.message().contains("cannot support atomic staging"));
    }

    #[test]
    fn output_validation_rejects_non_utf8_before_attempt_creation() {
        let directory = TestDirectory::new();
        let name = OsString::from_vec(b"result-\xff.json".to_vec());
        let error = validate_absent_output(&directory.path.join(name))
            .expect_err("non-UTF-8 output must be rejected before state creation");
        assert!(error.message().contains("output path is invalid"));
    }

    #[test]
    fn output_parent_path_replacement_is_detected_after_descriptor_binding() {
        let directory = TestDirectory::new();
        let target = validate_absent_output(&directory.path.join("result.json"))
            .expect("bind output target");
        let displaced = directory.path.with_extension("displaced");
        fs::rename(&directory.path, &displaced).expect("displace bound directory");
        fs::create_dir(&directory.path).expect("create replacement directory");
        fs::set_permissions(&directory.path, fs::Permissions::from_mode(0o700))
            .expect("seal replacement directory");
        let error =
            require_output_parent_binding(&target).expect_err("path replacement must be rejected");
        assert!(error.message().contains("binding changed"));
        fs::remove_dir(&directory.path).expect("remove replacement directory");
        fs::rename(&displaced, &directory.path).expect("restore bound directory");
    }

    #[test]
    fn output_parent_permission_drift_is_detected_after_descriptor_binding() {
        let directory = TestDirectory::new();
        let target = validate_absent_output(&directory.path.join("result.json"))
            .expect("bind output target");
        fs::set_permissions(&directory.path, fs::Permissions::from_mode(0o770))
            .expect("make output parent group writable");
        let error =
            require_output_parent_binding(&target).expect_err("permission drift must be rejected");
        assert!(error.message().contains("binding changed"));
        fs::set_permissions(&directory.path, fs::Permissions::from_mode(0o700))
            .expect("restore test directory permissions");
    }

    #[test]
    fn measurement_affinity_requires_exactly_the_frozen_cpu() {
        // SAFETY: the zeroed CPU sets are initialized only through libc's CPU
        // macros before being passed by shared reference.
        unsafe {
            let mut exact: libc::cpu_set_t = std::mem::zeroed();
            libc::CPU_ZERO(&mut exact);
            libc::CPU_SET(MEASUREMENT_CPU_ORDINAL, &mut exact);
            assert!(affinity_is_exact_measurement_cpu(&exact));
            libc::CPU_SET(MEASUREMENT_CPU_ORDINAL + 1, &mut exact);
            assert!(!affinity_is_exact_measurement_cpu(&exact));
        }
    }

    #[test]
    fn attempt_is_account_profile_scoped_and_exactly_once() {
        let directory = TestDirectory::new();
        let activation = test_activation();
        let first = create_attempt(
            directory.descriptor.as_raw_fd(),
            &activation,
            "33".repeat(32),
        )
        .expect("first attempt");
        assert_eq!(first.raw_sha256, sha256_hex(&first.raw));
        let error = create_attempt(
            directory.descriptor.as_raw_fd(),
            &activation,
            "33".repeat(32),
        )
        .expect_err("second attempt must fail");
        assert!(error.message().contains("already consumed"));
    }

    #[test]
    fn concurrent_attempts_admit_exactly_one_writer() {
        let directory = TestDirectory::new();
        let left = directory.descriptor.try_clone().unwrap();
        let right = directory.descriptor.try_clone().unwrap();
        let barrier = Arc::new(Barrier::new(2));
        let workers = [left, right].map(|descriptor| {
            let barrier = Arc::clone(&barrier);
            thread::spawn(move || {
                barrier.wait();
                create_attempt(descriptor.as_raw_fd(), &test_activation(), "44".repeat(32)).is_ok()
            })
        });
        let admitted = workers
            .into_iter()
            .map(|worker| worker.join().unwrap())
            .filter(|value| *value)
            .count();
        assert_eq!(admitted, 1);
    }

    #[test]
    fn blocked_artifact_is_terminal_and_never_grants_authority() {
        let activation = test_activation();
        let attempt = AttemptLeaseV6 {
            raw: b"attempt\n".to_vec(),
            raw_sha256: sha256_hex(b"attempt\n"),
            receipt_sha256: "55".repeat(32),
            run_nonce: "66".repeat(32),
            output_path_sha256: "77".repeat(32),
        };
        let preflight = Fixed64CpuPreflightV6 {
            profile_sha256: activation.profile_sha256.clone(),
            activation_sha256: activation.activation_sha256.clone(),
            source_commit_oid: None,
            cpu_model: None,
            boost_disabled: None,
            measurement_cpu_available: false,
            process_task_count: None,
            blockers: vec!["source_checkout_not_exact_main".to_owned()],
        };
        let outcome = MeasurementOutcomeV6 {
            report: None,
            measurement_started: false,
            blockers: preflight.blockers.clone(),
        };
        let artifact = build_artifact(&activation, &attempt, &preflight, outcome).unwrap();
        let text = std::str::from_utf8(&artifact.raw).unwrap();
        assert_eq!(artifact.recorded_decision, "BLOCKED");
        assert!(text.contains("\"qualification_authority\":false"));
        assert!(text.contains("\"measurement_started\":false"));
        let terminal = build_terminal(&activation, &attempt, &artifact).unwrap();
        let terminal = std::str::from_utf8(&terminal).unwrap();
        assert!(terminal.contains("\"execution_consumed\":true"));
        assert!(terminal.contains("\"decision_returned_only_after_terminal_persistence\":true"));
    }
}

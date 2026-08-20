//! Non-authoritative synthetic CPU observations for the native 512-row pool.

use std::env;
use std::fmt::Write as _;
use std::fs;
use std::hint::black_box;
use std::process::{Command, ExitCode};
use std::time::Instant;

use betelgeuze_docking_search::{
    produce_native_sampling_pool, AnchorId, AnchorKind, Fixed64GeometricInput, LigandAnchor,
    LigandAtom, ReceptorAtom, SearchInput, SurfaceId, SurfaceSample, Vec3,
};

const SCHEMA_ID: &str = "betelgeuze.engine_v2_sampling_pool_cpu_observation/1.0.0";
const PROFILE_ID: &str = "engine_v2_sampling_pool_synthetic_cpu_observation_v1";
const DEFAULT_SAMPLE_COUNT: usize = 7;
const MINIMUM_SAMPLE_COUNT: usize = 3;
const MAXIMUM_SAMPLE_COUNT: usize = 100;

#[derive(Clone, Copy)]
struct FixtureSpec {
    id: &'static str,
    seed_byte: u8,
    ligand_atom_count: usize,
    receptor_atom_count: usize,
    expected_receipt_sha256: &'static str,
}

const FIXTURES: [FixtureSpec; 3] = [
    FixtureSpec {
        id: "small",
        seed_byte: 0x11,
        ligand_atom_count: 8,
        receptor_atom_count: 64,
        expected_receipt_sha256: "2603c7b0b13dd2af26313d26ce63e73e8162de396a1fb5d7030a31a993c60831",
    },
    FixtureSpec {
        id: "medium",
        seed_byte: 0x23,
        ligand_atom_count: 24,
        receptor_atom_count: 256,
        expected_receipt_sha256: "61a8bb8490359fa03f0fb8fc0a12514203d602dc6539faac447f0e65e8e8d3a5",
    },
    FixtureSpec {
        id: "large",
        seed_byte: 0x47,
        ligand_atom_count: 48,
        receptor_atom_count: 512,
        expected_receipt_sha256: "ded4134a8cd2e0c6d42f096c0220c22931378a5cba96e2fc36dba54f77bdc0bb",
    },
];

#[derive(Clone, Debug, PartialEq, Eq)]
struct ChildObservation {
    fixture_id: String,
    receipt_sha256: String,
    exact_pair_evaluation_count: usize,
    wall_time_ns: u128,
    baseline_peak_rss_kib: u64,
    final_peak_rss_kib: u64,
    peak_rss_delta_kib: u64,
}

fn main() -> ExitCode {
    match run(env::args().skip(1).collect()) {
        Ok(output) => {
            println!("{output}");
            ExitCode::SUCCESS
        }
        Err(message) => {
            eprintln!("sampling-pool CPU observation: {message}");
            ExitCode::FAILURE
        }
    }
}

fn run(arguments: Vec<String>) -> Result<String, String> {
    match arguments.as_slice() {
        [mode] if mode == "--verify-fixtures" => verify_fixtures(),
        [mode, fixture_id] if mode == "--child" => child(fixture_id),
        [mode] if mode == "--observe" => observe(DEFAULT_SAMPLE_COUNT),
        [mode, sample_count] if mode == "--observe" => {
            let sample_count = sample_count
                .parse::<usize>()
                .map_err(|_| "sample count must be an integer".to_owned())?;
            observe(sample_count)
        }
        _ => Err("expected --verify-fixtures, --child FIXTURE, or --observe [SAMPLES]".to_owned()),
    }
}

fn verify_fixtures() -> Result<String, String> {
    let mut rows = Vec::with_capacity(FIXTURES.len());
    for spec in FIXTURES {
        let (input, geometric) = fixture(spec)?;
        let first = produce_native_sampling_pool(&input, &geometric)
            .map_err(|error| format!("{} first run failed: {error}", spec.id))?;
        let second = produce_native_sampling_pool(&input, &geometric)
            .map_err(|error| format!("{} second run failed: {error}", spec.id))?;
        if first != second
            || !first.verifies_against(&input, &geometric)
            || hex(first.receipt_sha256()) != spec.expected_receipt_sha256
            || first.exact_pair_evaluation_count() != expected_pair_count(spec)
        {
            return Err(format!("{} is not repeat-stable", spec.id));
        }
        rows.push(format!(
            "{{\"exact_pair_evaluation_count\":{},\"fixture_id\":\"{}\",\"ligand_atom_count\":{},\"receptor_atom_count\":{},\"receipt_sha256\":\"{}\"}}",
            first.exact_pair_evaluation_count(),
            spec.id,
            spec.ligand_atom_count,
            spec.receptor_atom_count,
            hex(first.receipt_sha256())
        ));
    }
    Ok(format!(
        "{{\"all_authority_false\":true,\"fixtures\":[{}],\"profile_id\":\"{PROFILE_ID}\",\"schema_id\":\"{SCHEMA_ID}\",\"status\":\"synthetic_fixture_verification_only\"}}",
        rows.join(",")
    ))
}

fn child(fixture_id: &str) -> Result<String, String> {
    reject_github_actions_timing()?;
    let spec = fixture_spec(fixture_id)?;
    let (input, geometric) = fixture(spec)?;
    let baseline_peak_rss_kib = peak_rss_kib()?;
    let started = Instant::now();
    let observed = produce_native_sampling_pool(&input, &geometric)
        .map_err(|error| format!("producer failed: {error}"))?;
    let wall_time_ns = started.elapsed().as_nanos();
    black_box(&observed);
    let final_peak_rss_kib = peak_rss_kib()?;
    if wall_time_ns == 0 || !observed.has_valid_receipt() {
        return Err("timed producer observation is invalid".to_owned());
    }
    let row = ChildObservation {
        fixture_id: spec.id.to_owned(),
        receipt_sha256: hex(observed.receipt_sha256()),
        exact_pair_evaluation_count: observed.exact_pair_evaluation_count(),
        wall_time_ns,
        baseline_peak_rss_kib,
        final_peak_rss_kib,
        peak_rss_delta_kib: final_peak_rss_kib.saturating_sub(baseline_peak_rss_kib),
    };
    Ok(format_child(&row))
}

fn observe(sample_count: usize) -> Result<String, String> {
    reject_github_actions_timing()?;
    if !(MINIMUM_SAMPLE_COUNT..=MAXIMUM_SAMPLE_COUNT).contains(&sample_count) {
        return Err(format!(
            "sample count must be within [{MINIMUM_SAMPLE_COUNT}, {MAXIMUM_SAMPLE_COUNT}]"
        ));
    }
    let executable = env::current_exe().map_err(|error| format!("current executable: {error}"))?;
    let mut fixture_rows = Vec::with_capacity(FIXTURES.len());
    for spec in FIXTURES {
        let mut observations = Vec::with_capacity(sample_count);
        for _ in 0..sample_count {
            let output = Command::new(&executable)
                .args(["--child", spec.id])
                .env("RAYON_NUM_THREADS", "1")
                .env("OMP_NUM_THREADS", "1")
                .env("OPENBLAS_NUM_THREADS", "1")
                .output()
                .map_err(|error| format!("{} child launch failed: {error}", spec.id))?;
            if !output.status.success() {
                return Err(format!(
                    "{} child failed: {}",
                    spec.id,
                    String::from_utf8_lossy(&output.stderr).trim()
                ));
            }
            let stdout = String::from_utf8(output.stdout)
                .map_err(|_| format!("{} child output is not UTF-8", spec.id))?;
            observations.push(parse_child(stdout.trim())?);
        }
        let receipt = observations[0].receipt_sha256.clone();
        let pair_count = observations[0].exact_pair_evaluation_count;
        if observations.iter().any(|row| {
            row.fixture_id != spec.id
                || row.receipt_sha256 != receipt
                || row.receipt_sha256 != spec.expected_receipt_sha256
                || row.exact_pair_evaluation_count != pair_count
                || row.exact_pair_evaluation_count != expected_pair_count(spec)
                || row.wall_time_ns == 0
                || row.final_peak_rss_kib < row.baseline_peak_rss_kib
        }) {
            return Err(format!("{} child observations are cross-wired", spec.id));
        }
        fixture_rows.push(format_observed_fixture(spec, &observations));
    }
    let cpu_model = json_escape(&cpu_model()?);
    Ok(format!(
        "{{\"authority\":{{\"customer_pose_authorized\":false,\"fresh_128_execution_authorized\":false,\"hip_device_execution_authorized\":false,\"molecular_execution_authorized\":false,\"performance_claim_authorized\":false,\"product_authorized\":false,\"public_benchmark_authorized\":false,\"rank_mutation_authorized\":false,\"reservation_authorized\":false,\"scientific_claim_authorized\":false,\"stage0_admission_authorized\":false}},\"cpu_model\":\"{cpu_model}\",\"fixtures\":[{}],\"memory_role\":\"descriptive_process_peak_rss_only\",\"profile_id\":\"{PROFILE_ID}\",\"sample_count\":{sample_count},\"schema_id\":\"{SCHEMA_ID}\",\"status\":\"local_synthetic_development_observation_only\",\"timed_boundary\":\"produce_native_sampling_pool_only_fixture_construction_excluded\",\"wall_time_role\":\"descriptive_no_threshold_no_claim\"}}",
        fixture_rows.join(",")
    ))
}

fn reject_github_actions_timing() -> Result<(), String> {
    if env::var("GITHUB_ACTIONS").is_ok_and(|value| value.eq_ignore_ascii_case("true")) {
        Err("GitHub Actions cannot create timing observations".to_owned())
    } else {
        Ok(())
    }
}

fn format_observed_fixture(spec: FixtureSpec, rows: &[ChildObservation]) -> String {
    let mut wall_times = rows.iter().map(|row| row.wall_time_ns).collect::<Vec<_>>();
    wall_times.sort_unstable();
    let p50 = nearest_rank(&wall_times, 50);
    let p95 = nearest_rank(&wall_times, 95);
    let peak_rss_kib = rows
        .iter()
        .map(|row| row.final_peak_rss_kib)
        .max()
        .expect("non-empty observations");
    let peak_rss_delta_kib = rows
        .iter()
        .map(|row| row.peak_rss_delta_kib)
        .max()
        .expect("non-empty observations");
    let samples = rows
        .iter()
        .map(|row| row.wall_time_ns.to_string())
        .collect::<Vec<_>>()
        .join(",");
    format!(
        "{{\"exact_pair_evaluation_count\":{},\"fixture_id\":\"{}\",\"ligand_atom_count\":{},\"peak_rss_delta_kib\":{peak_rss_delta_kib},\"peak_rss_kib\":{peak_rss_kib},\"receptor_atom_count\":{},\"receipt_sha256\":\"{}\",\"wall_time_ns_p50\":{p50},\"wall_time_ns_p95\":{p95},\"wall_time_ns_samples\":[{samples}]}}",
        rows[0].exact_pair_evaluation_count,
        spec.id,
        spec.ligand_atom_count,
        spec.receptor_atom_count,
        rows[0].receipt_sha256
    )
}

fn format_child(row: &ChildObservation) -> String {
    format!(
        "{}\t{}\t{}\t{}\t{}\t{}\t{}",
        row.fixture_id,
        row.receipt_sha256,
        row.exact_pair_evaluation_count,
        row.wall_time_ns,
        row.baseline_peak_rss_kib,
        row.final_peak_rss_kib,
        row.peak_rss_delta_kib
    )
}

fn parse_child(value: &str) -> Result<ChildObservation, String> {
    let fields = value.split('\t').collect::<Vec<_>>();
    if fields.len() != 7 {
        return Err("child output field denominator changed".to_owned());
    }
    if fields[1].len() != 64 || !fields[1].bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err("invalid child receipt SHA-256".to_owned());
    }
    Ok(ChildObservation {
        fixture_id: fields[0].to_owned(),
        receipt_sha256: fields[1].to_owned(),
        exact_pair_evaluation_count: parse_number(fields[2], "pair count")?,
        wall_time_ns: parse_number(fields[3], "wall time")?,
        baseline_peak_rss_kib: parse_number(fields[4], "baseline RSS")?,
        final_peak_rss_kib: parse_number(fields[5], "final RSS")?,
        peak_rss_delta_kib: parse_number(fields[6], "RSS delta")?,
    })
}

fn parse_number<T: std::str::FromStr>(value: &str, label: &str) -> Result<T, String> {
    value.parse().map_err(|_| format!("invalid child {label}"))
}

fn nearest_rank(sorted: &[u128], percentile: usize) -> u128 {
    let rank = sorted.len().saturating_mul(percentile).div_ceil(100);
    sorted[rank.saturating_sub(1)]
}

fn fixture_spec(id: &str) -> Result<FixtureSpec, String> {
    FIXTURES
        .iter()
        .copied()
        .find(|spec| spec.id == id)
        .ok_or_else(|| format!("unknown fixture: {id}"))
}

const fn expected_pair_count(spec: FixtureSpec) -> usize {
    spec.ligand_atom_count * spec.receptor_atom_count * 512
}

fn fixture(spec: FixtureSpec) -> Result<(SearchInput, Fixed64GeometricInput), String> {
    let ligand_atoms = (0..spec.ligand_atom_count)
        .map(|index| {
            let (x, y, z) = if index == 0 {
                (0.0, -0.5, 0.0)
            } else if index == 1 {
                (0.0, 0.5, 0.0)
            } else {
                let local = index - 2;
                (
                    (local % 4) as f64 * 0.65 - 0.975,
                    ((local / 4) % 4) as f64 * 0.65 - 0.975,
                    (local / 16) as f64 * 0.65 - 0.65,
                )
            };
            LigandAtom {
                position_angstrom: Vec3::new(x, y, z),
                vdw_radius_angstrom: 1.4 + (index % 3) as f64 * 0.1,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.0,
            }
        })
        .collect::<Vec<_>>();
    let receptor_atoms = (0..spec.receptor_atom_count)
        .map(|index| {
            let x = 16.0 + (index % 8) as f64 * 1.1;
            let y = -4.0 + ((index / 8) % 8) as f64 * 1.1;
            let z = -4.0 + (index / 64) as f64 * 1.1;
            ReceptorAtom {
                position_angstrom: Vec3::new(x, y, z),
                vdw_radius_angstrom: 1.5,
                epsilon_kcal_per_mol: 0.2,
                charge_elementary: 0.0,
            }
        })
        .collect::<Vec<_>>();
    let input = SearchInput {
        source_seed: [spec.seed_byte; 32],
        ligand_atoms,
        ligand_anchors: vec![
            LigandAnchor {
                id: AnchorId(1),
                atom_index: 0,
                direction: Vec3::new(1.0, 0.0, 0.0),
                kind: AnchorKind::HydrogenBondDonor,
            },
            LigandAnchor {
                id: AnchorId(2),
                atom_index: 1,
                direction: Vec3::new(1.0, 0.0, 0.0),
                kind: AnchorKind::HydrogenBondAcceptor,
            },
        ],
        receptor_atoms,
        surface_samples: vec![
            SurfaceSample {
                id: SurfaceId(1),
                position_angstrom: Vec3::new(18.5, -0.5, 0.0),
                outward_normal: Vec3::new(1.0, 0.0, 0.0),
                anchor_kind: AnchorKind::HydrogenBondAcceptor,
            },
            SurfaceSample {
                id: SurfaceId(2),
                position_angstrom: Vec3::new(18.5, 0.5, 0.0),
                outward_normal: Vec3::new(1.0, 0.0, 0.0),
                anchor_kind: AnchorKind::HydrogenBondDonor,
            },
        ],
    };
    let geometric = Fixed64GeometricInput::new(
        input
            .ligand_atoms
            .iter()
            .map(|atom| atom.vdw_radius_angstrom)
            .collect(),
        vec![true; input.ligand_atoms.len()],
        input
            .receptor_atoms
            .iter()
            .map(|atom| atom.position_angstrom)
            .collect(),
        input
            .receptor_atoms
            .iter()
            .map(|atom| atom.vdw_radius_angstrom)
            .collect(),
        Vec3::new(20.0, 0.0, 0.0),
        12.0,
    )
    .map_err(|error| format!("{} geometric fixture: {error}", spec.id))?;
    Ok((input, geometric))
}

fn peak_rss_kib() -> Result<u64, String> {
    let status = fs::read_to_string("/proc/self/status")
        .map_err(|error| format!("read /proc/self/status: {error}"))?;
    let row = status
        .lines()
        .find(|line| line.starts_with("VmHWM:"))
        .ok_or_else(|| "VmHWM is absent from /proc/self/status".to_owned())?;
    let fields = row.split_ascii_whitespace().collect::<Vec<_>>();
    if fields.len() != 3 || fields[0] != "VmHWM:" || fields[2] != "kB" {
        return Err("VmHWM row format changed".to_owned());
    }
    parse_number(fields[1], "VmHWM")
}

fn cpu_model() -> Result<String, String> {
    let cpuinfo = fs::read_to_string("/proc/cpuinfo")
        .map_err(|error| format!("read /proc/cpuinfo: {error}"))?;
    cpuinfo
        .lines()
        .find_map(|line| line.strip_prefix("model name\t: "))
        .map(str::to_owned)
        .ok_or_else(|| "CPU model is absent from /proc/cpuinfo".to_owned())
}

fn hex(value: [u8; 32]) -> String {
    let mut output = String::with_capacity(64);
    for byte in value {
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

fn json_escape(value: &str) -> String {
    let mut output = String::with_capacity(value.len());
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            value if value.is_control() => {
                write!(&mut output, "\\u{:04x}", value as u32)
                    .expect("writing to String cannot fail");
            }
            value => output.push(value),
        }
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn child_rows_round_trip_and_percentiles_are_nearest_rank() {
        let row = ChildObservation {
            fixture_id: "small".to_owned(),
            receipt_sha256: "ab".repeat(32),
            exact_pair_evaluation_count: 262_144,
            wall_time_ns: 123,
            baseline_peak_rss_kib: 1000,
            final_peak_rss_kib: 1200,
            peak_rss_delta_kib: 200,
        };
        assert_eq!(parse_child(&format_child(&row)).unwrap(), row);
        assert_eq!(nearest_rank(&[1, 2, 3, 4, 5, 6, 7], 50), 4);
        assert_eq!(nearest_rank(&[1, 2, 3, 4, 5, 6, 7], 95), 7);
    }

    #[test]
    fn fixtures_are_bounded_repeat_stable_and_authority_false() {
        let output = verify_fixtures().unwrap();
        assert!(output.contains("\"all_authority_false\":true"));
        for fixture in FIXTURES {
            assert!(output.contains(&format!("\"fixture_id\":\"{}\"", fixture.id)));
        }
    }

    #[test]
    fn invalid_modes_fixtures_and_sample_counts_fail_closed() {
        assert!(run(vec![]).is_err());
        assert!(run(vec!["--child".to_owned(), "unknown".to_owned()]).is_err());
        assert!(observe(MINIMUM_SAMPLE_COUNT - 1).is_err());
        assert!(observe(MAXIMUM_SAMPLE_COUNT + 1).is_err());
        assert!(parse_child("short").is_err());
    }
}

#[cfg(not(feature = "native-inference"))]
fn main() {
    eprintln!(
        "router_onnx_poc requires --features native-inference (tract-onnx optional dependency)."
    );
    std::process::exit(2);
}

#[cfg(feature = "native-inference")]
mod app {
    use rand::{rngs::StdRng, Rng, SeedableRng};
    use serde_json::json;
    use std::collections::HashMap;
    use std::error::Error;
    use std::fs;
    use std::time::Instant;
    use tract_onnx::prelude::*;
    use tract_onnx::prelude::tract_ndarray::{Array2, Array3};

    fn parse_args() -> Result<HashMap<String, String>, Box<dyn Error>> {
        let mut out = HashMap::<String, String>::new();
        let mut it = std::env::args().skip(1);
        while let Some(k) = it.next() {
            if !k.starts_with("--") {
                continue;
            }
            let key = k.trim_start_matches("--").to_string();
            let value = it.next().ok_or_else(|| format!("missing value for --{}", key))?;
            out.insert(key, value);
        }
        Ok(out)
    }

    fn get_str<'a>(args: &'a HashMap<String, String>, key: &str) -> Result<&'a str, Box<dyn Error>> {
        args.get(key)
            .map(String::as_str)
            .ok_or_else(|| format!("required argument --{} is missing", key).into())
    }

    fn get_usize(
        args: &HashMap<String, String>,
        key: &str,
        default: usize,
    ) -> Result<usize, Box<dyn Error>> {
        match args.get(key) {
            Some(v) => Ok(v.parse::<usize>()?),
            None => Ok(default),
        }
    }

    fn get_u64(args: &HashMap<String, String>, key: &str, default: u64) -> Result<u64, Box<dyn Error>> {
        match args.get(key) {
            Some(v) => Ok(v.parse::<u64>()?),
            None => Ok(default),
        }
    }

    pub fn run() -> Result<(), Box<dyn Error>> {
        let args = parse_args()?;
        let onnx_path = get_str(&args, "onnx")?.to_string();
        let out_json = args.get("out-json").cloned();
        let batch = get_usize(&args, "batch", 1)?;
        let atoms = get_usize(&args, "atoms", 35)?;
        let topo_dim = get_usize(&args, "topo-dim", 64)?;
        let sim_dim = get_usize(&args, "sim-dim", 19)?;
        let seed = get_u64(&args, "seed", 1234)?;

        let mut rng = StdRng::seed_from_u64(seed);
        let c = Array3::<f32>::from_shape_fn((batch, atoms, 3), |_| rng.gen_range(-1.0f32..1.0f32));
        let topo = Array3::<f32>::from_shape_fn((batch, atoms, topo_dim), |_| rng.gen_range(-1.0f32..1.0f32));
        let sim = Array2::<f32>::from_shape_fn((batch, sim_dim), |_| rng.gen_range(0.0f32..1.0f32));

        let model = tract_onnx::onnx()
            .model_for_path(&onnx_path)?
            .into_optimized()?
            .into_runnable()?;

        let start = Instant::now();
        let outputs = model.run(tvec![
            c.into_dyn().into_tensor().into(),
            topo.into_dyn().into_tensor().into(),
            sim.into_dyn().into_tensor().into()
        ])?;
        let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;

        if outputs.len() < 2 {
            return Err("router onnx output count is less than 2".into());
        }

        let weights = outputs[0].to_array_view::<f32>()?;
        let mask = outputs[1].to_array_view::<f32>()?;

        let payload = json!({
            "ok": true,
            "onnx_path": onnx_path,
            "batch": batch,
            "atoms": atoms,
            "topo_dim": topo_dim,
            "sim_dim": sim_dim,
            "elapsed_ms": elapsed_ms,
            "weights_shape": weights.shape(),
            "active_mask_shape": mask.shape(),
            "weights_mean": weights.iter().copied().sum::<f32>() / (weights.len() as f32).max(1.0),
            "active_mask_mean": mask.iter().copied().sum::<f32>() / (mask.len() as f32).max(1.0)
        });

        if let Some(path) = out_json {
            fs::write(&path, serde_json::to_string_pretty(&payload)?)?;
        }
        println!("{}", serde_json::to_string_pretty(&payload)?);
        Ok(())
    }
}

#[cfg(feature = "native-inference")]
fn main() {
    if let Err(e) = app::run() {
        eprintln!("router_onnx_poc failed: {e}");
        std::process::exit(1);
    }
}

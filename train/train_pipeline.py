# train/train_pipeline.py

import datetime as dt
import gc
import json
import os
import csv
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, WeightedRandomSampler
from rich.console import Console
from core.config import config, logger
from core.tracking import ExperimentTracker
from theory.strategy import StrategicOrchestrator
from train.data_sources import build_sampling_weights, build_split_dataset
from train.trainer import AIRouterTrainer
from train.evaluator import evaluate_model
from train.target_scheduler import resolve_targets

try:
    import optuna # For hyperparameter optimization
except ImportError:
    optuna = None


def _bool_from_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, str(int(bool(default))))).strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return bool(default)


def _int_from_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(int(default))))
    except Exception:
        return int(default)


def _resolve_batch_size(default_batch_size: int) -> int:
    bs = _int_from_env("TRAIN_BATCH_SIZE", int(default_batch_size))
    return max(int(bs), 1)


def _build_dataloader_kwargs() -> dict:
    has_cuda = torch.cuda.is_available()
    cpu_count = os.cpu_count() or 1
    default_workers = min(max(cpu_count // 2, 1), 8)
    num_workers = max(_int_from_env("TRAIN_NUM_WORKERS", default_workers), 0)
    pin_memory = _bool_from_env("TRAIN_PIN_MEMORY", has_cuda)
    persistent_workers = _bool_from_env("TRAIN_PERSISTENT_WORKERS", False)
    prefetch_factor = max(_int_from_env("TRAIN_PREFETCH_FACTOR", 2), 1)

    kwargs = {
        "num_workers": int(num_workers),
        "pin_memory": bool(pin_memory),
    }
    if num_workers > 0:
        kwargs["persistent_workers"] = bool(persistent_workers)
        kwargs["prefetch_factor"] = int(prefetch_factor)
    return kwargs


def _build_train_loader(
    train_dataset,
    batch_size: int,
    data_source: str,
    distilled_use_weighted_sampler: bool,
    distilled_weighted_sampler_replacement: bool,
    distilled_min_sampling_weight: float,
    loader_kwargs: dict | None = None,
):
    loader_kwargs_i = dict(loader_kwargs or {})
    if str(data_source).strip().lower() == "distilled" and bool(distilled_use_weighted_sampler):
        sample_weights = build_sampling_weights(
            train_dataset,
            min_sampling_weight=float(distilled_min_sampling_weight),
        )
        sampler = WeightedRandomSampler(
            weights=torch.as_tensor(sample_weights, dtype=torch.double),
            num_samples=int(len(sample_weights)),
            replacement=bool(distilled_weighted_sampler_replacement),
        )
        return DataLoader(
            train_dataset,
            batch_size=batch_size,
            sampler=sampler,
            shuffle=False,
            **loader_kwargs_i,
        )
    return DataLoader(train_dataset, batch_size=batch_size, shuffle=True, **loader_kwargs_i)


def _shutdown_dataloader(loader) -> None:
    if loader is None:
        return
    it = getattr(loader, "_iterator", None)
    if it is None:
        return
    shutdown = getattr(it, "_shutdown_workers", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            pass


def _close_dataset_handles(dataset) -> None:
    if dataset is None:
        return
    close_fn = getattr(dataset, "close", None)
    if callable(close_fn):
        try:
            close_fn()
        except Exception:
            pass
    child_sets = getattr(dataset, "datasets", None)
    if isinstance(child_sets, (list, tuple)):
        for child in child_sets:
            _close_dataset_handles(child)


def _sanitize_tag(text: str) -> str:
    out = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(text))
    return out.strip("_") or "run"


def _load_checkpoint_if_requested(model: nn.Module, checkpoint_path: str, strict: bool) -> dict:
    path = str(checkpoint_path or "").strip()
    if not path:
        return {"requested": False, "loaded": False, "path": None}
    if not os.path.exists(path):
        raise FileNotFoundError(f"checkpoint not found: {path}")
    payload = torch.load(path, map_location=config.DEVICE)
    state_dict = payload
    if isinstance(payload, dict) and not all(torch.is_tensor(v) for v in payload.values()):
        for key in ("state_dict", "model_state_dict", "model", "weights"):
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                state_dict = candidate
                break
    if bool(strict):
        load_ret = model.load_state_dict(state_dict, strict=True)
        skipped_shape_mismatch = []
    else:
        # In non-strict mode, skip keys whose tensor shape no longer matches
        # the current model (common during router architecture evolution).
        model_state = model.state_dict()
        filtered_state = {}
        skipped_shape_mismatch = []
        for key, value in state_dict.items():
            if key not in model_state:
                continue
            ref_val = model_state[key]
            if torch.is_tensor(value) and torch.is_tensor(ref_val):
                if tuple(value.shape) != tuple(ref_val.shape):
                    skipped_shape_mismatch.append(str(key))
                    continue
            filtered_state[key] = value
        load_ret = model.load_state_dict(filtered_state, strict=False)
    return {
        "requested": True,
        "loaded": True,
        "path": os.path.abspath(path),
        "strict": bool(strict),
        "missing_keys_count": int(len(getattr(load_ret, "missing_keys", []))),
        "unexpected_keys_count": int(len(getattr(load_ret, "unexpected_keys", []))),
        "skipped_shape_mismatch_count": int(len(skipped_shape_mismatch)),
        "skipped_shape_mismatch_keys": skipped_shape_mismatch[:64],
    }


def _safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def _write_rows_csv(rows, path: str) -> None:
    rows = list(rows or [])
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _aggregate_curriculum(rows):
    rows = list(rows or [])
    if not rows:
        return {"targets": 0}
    rmse_vals = [_safe_float(row.get("test_rmse"), default=None) for row in rows]
    rmse_vals = [x for x in rmse_vals if x is not None]
    mae_vals = [_safe_float(row.get("test_mae"), default=None) for row in rows]
    mae_vals = [x for x in mae_vals if x is not None]
    val_vals = [_safe_float(row.get("best_val_loss"), default=None) for row in rows]
    val_vals = [x for x in val_vals if x is not None]
    return {
        "targets": int(len(rows)),
        "mean_test_rmse": float(sum(rmse_vals) / len(rmse_vals)) if rmse_vals else None,
        "mean_test_mae": float(sum(mae_vals) / len(mae_vals)) if mae_vals else None,
        "mean_best_val_loss": float(sum(val_vals) / len(val_vals)) if val_vals else None,
        "checkpoint_loaded_count": int(sum(1 for row in rows if row.get("checkpoint_loaded"))),
    }


def _run_single_target_training(
    *,
    target: str,
    data_source: str,
    distilled_manifest: str,
    distilled_split_col: str,
    distilled_min_quality,
    distilled_max_samples_per_shard,
    distilled_sample_weight_col: str,
    distilled_default_shard_weight: float,
    distilled_quality_weight_alpha: float,
    distilled_min_sampling_weight: float,
    distilled_use_weighted_sampler: bool,
    distilled_weighted_sampler_replacement: bool,
    initial_checkpoint: str,
    checkpoint_strict: bool,
    checkpoint_path: str,
    early_stop_patience: int,
    use_hp_search: bool,
):
    device = config.DEVICE
    loader_kwargs = _build_dataloader_kwargs()

    if use_hp_search:
        if optuna is None:
            raise ImportError("optuna is required for --hp_search. Install optuna or disable hp search.")
        study = optuna.create_study(direction='minimize')
        study.optimize(
            lambda trial: objective(
                trial,
                target=target,
                data_source=data_source,
                distilled_manifest=distilled_manifest,
                distilled_split_col=distilled_split_col,
                distilled_min_quality=distilled_min_quality,
                distilled_max_samples_per_shard=distilled_max_samples_per_shard,
                distilled_sample_weight_col=distilled_sample_weight_col,
                distilled_default_shard_weight=distilled_default_shard_weight,
                distilled_quality_weight_alpha=distilled_quality_weight_alpha,
                distilled_min_sampling_weight=distilled_min_sampling_weight,
                distilled_use_weighted_sampler=distilled_use_weighted_sampler,
                distilled_weighted_sampler_replacement=distilled_weighted_sampler_replacement,
            ),
            n_trials=50,
        )
        best_params = study.best_trial.params
        return {
            "target": target,
            "mode": "hp_search",
            "best_trial": int(study.best_trial.number),
            "best_val_rmse": float(study.best_value),
            "best_params": best_params,
            "checkpoint_loaded": False,
            "checkpoint_load_meta": {"requested": False, "loaded": False, "path": None},
            "best_checkpoint_path": None,
        }

    # Standard training path
    train_dataset = None
    val_dataset = None
    test_dataset = None
    train_loader = None
    val_loader = None
    test_loader = None
    model = None
    tracker = None
    tracker_open = False
    checkpoint_load_meta = {"requested": False, "loaded": False, "path": None}
    batch_size_i = _resolve_batch_size(config.BATCH_SIZE)
    try:
        train_dataset = build_split_dataset(
            target=target,
            split='train',
            data_source=data_source,
            configured_hdf5_path=config.get('training.train_data_path'),
            distilled_manifest=distilled_manifest,
            distilled_split_col=distilled_split_col,
            distilled_min_quality=distilled_min_quality,
            distilled_max_samples_per_shard=distilled_max_samples_per_shard,
            distilled_sample_weight_col=distilled_sample_weight_col,
            distilled_default_shard_weight=distilled_default_shard_weight,
            distilled_quality_weight_alpha=distilled_quality_weight_alpha,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
        )
        val_dataset = build_split_dataset(
            target=target,
            split='val',
            data_source=data_source,
            configured_hdf5_path=config.get('training.val_data_path'),
            distilled_manifest=distilled_manifest,
            distilled_split_col=distilled_split_col,
            distilled_min_quality=distilled_min_quality,
            distilled_max_samples_per_shard=distilled_max_samples_per_shard,
            distilled_sample_weight_col=distilled_sample_weight_col,
            distilled_default_shard_weight=distilled_default_shard_weight,
            distilled_quality_weight_alpha=distilled_quality_weight_alpha,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
        )
        train_loader = _build_train_loader(
            train_dataset=train_dataset,
            batch_size=batch_size_i,
            data_source=data_source,
            distilled_use_weighted_sampler=distilled_use_weighted_sampler,
            distilled_weighted_sampler_replacement=distilled_weighted_sampler_replacement,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
            loader_kwargs=loader_kwargs,
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size_i, shuffle=False, **loader_kwargs)

        model = StrategicOrchestrator(device).to(device)
        checkpoint_load_meta = _load_checkpoint_if_requested(
            model=model,
            checkpoint_path=initial_checkpoint,
            strict=bool(checkpoint_strict),
        )
        optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
        from train_router import CompositeRouterLoss
        loss_fn = CompositeRouterLoss(
            mse_weight=config.get('training.loss_weights.mse', 1.0),
            div_weight=config.get('training.loss_weights.div_penalty', 0.05),
            clamp_weight=config.get('training.loss_weights.clamp_penalty', 0.001)
        )
        tracker = ExperimentTracker(experiment_name="AIRouter_Final_Training")
        tracker.start_run(run_name=f"final_train_{target}")
        tracker_open = True
        tracker.log_params({
            'target': target,
            'data_source': data_source,
            'distilled_manifest': distilled_manifest if data_source == 'distilled' else None,
            'distilled_split_col': distilled_split_col if data_source == 'distilled' else None,
            'distilled_min_quality': distilled_min_quality if data_source == 'distilled' else None,
            'distilled_max_samples_per_shard': distilled_max_samples_per_shard if data_source == 'distilled' else None,
            'distilled_sample_weight_col': distilled_sample_weight_col if data_source == 'distilled' else None,
            'distilled_default_shard_weight': distilled_default_shard_weight if data_source == 'distilled' else None,
            'distilled_quality_weight_alpha': distilled_quality_weight_alpha if data_source == 'distilled' else None,
            'distilled_min_sampling_weight': distilled_min_sampling_weight if data_source == 'distilled' else None,
            'distilled_use_weighted_sampler': distilled_use_weighted_sampler if data_source == 'distilled' else None,
            'distilled_weighted_sampler_replacement': distilled_weighted_sampler_replacement if data_source == 'distilled' else None,
            'checkpoint_loaded': checkpoint_load_meta.get("loaded", False),
            'checkpoint_path': checkpoint_load_meta.get("path"),
            'checkpoint_strict': checkpoint_load_meta.get("strict"),
            'checkpoint_missing_keys_count': checkpoint_load_meta.get("missing_keys_count", 0),
            'checkpoint_unexpected_keys_count': checkpoint_load_meta.get("unexpected_keys_count", 0),
            'batch_size': int(batch_size_i),
            'learning_rate': config.LEARNING_RATE,
            'epochs': config.get('training.epochs', 100),
        })

        trainer = AIRouterTrainer(
            model,
            train_loader,
            val_loader,
            optimizer,
            loss_fn,
            epochs=config.get('training.epochs', 100),
            device=device,
            tracker=tracker,
            checkpoint_path=checkpoint_path,
            early_stop_patience=int(early_stop_patience),
        )
        train_summary = trainer.train()

        test_dataset = build_split_dataset(
            target=target,
            split='test',
            data_source=data_source,
            configured_hdf5_path=config.get('training.test_data_path'),
            distilled_manifest=distilled_manifest,
            distilled_split_col=distilled_split_col,
            distilled_min_quality=distilled_min_quality,
            distilled_max_samples_per_shard=distilled_max_samples_per_shard,
            distilled_sample_weight_col=distilled_sample_weight_col,
            distilled_default_shard_weight=distilled_default_shard_weight,
            distilled_quality_weight_alpha=distilled_quality_weight_alpha,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
        )
        test_loader = DataLoader(test_dataset, batch_size=batch_size_i, shuffle=False, **loader_kwargs)
        test_metrics = evaluate_model(model, test_loader, device, metrics=['rmse', 'mae'])
        tracker.log_metrics(test_metrics)
        tracker.end_run()
        tracker_open = False

        return {
            "target": target,
            "mode": "default",
            "checkpoint_loaded": bool(checkpoint_load_meta.get("loaded", False)),
            "checkpoint_load_meta": checkpoint_load_meta,
            "best_checkpoint_path": train_summary.get("best_checkpoint_path"),
            "best_val_loss": _safe_float(train_summary.get("best_val_loss"), default=None),
            "epochs_trained": int(train_summary.get("epochs_trained", 0)),
            "test_rmse": _safe_float(test_metrics.get("rmse"), default=None),
            "test_mae": _safe_float(test_metrics.get("mae"), default=None),
        }
    finally:
        if tracker is not None and tracker_open:
            try:
                tracker.end_run()
            except Exception:
                pass
        _shutdown_dataloader(train_loader)
        _shutdown_dataloader(val_loader)
        _shutdown_dataloader(test_loader)
        _close_dataset_handles(train_dataset)
        _close_dataset_handles(val_dataset)
        _close_dataset_handles(test_dataset)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def objective(
    trial,
    target=None,
    data_source="hdf5",
    distilled_manifest="runs/distilled_residual_manifest.csv",
    distilled_split_col="split",
    distilled_min_quality=None,
    distilled_max_samples_per_shard=None,
    distilled_sample_weight_col="sampling_weight",
    distilled_default_shard_weight=1.0,
    distilled_quality_weight_alpha=0.0,
    distilled_min_sampling_weight=1e-6,
    distilled_use_weighted_sampler=False,
    distilled_weighted_sampler_replacement=True,
):
    """
    Objective function for Optuna hyperparameter search.
    """
    # Suggest hyperparameters
    lr = trial.suggest_float('lr', 1e-5, 1e-2, log=True)
    batch_size = trial.suggest_categorical('batch_size', [16, 32, 64, 128])
    hidden_dim = trial.suggest_categorical('hidden_dim', [128, 256, 512])

    loader_kwargs = _build_dataloader_kwargs()
    train_dataset = None
    val_dataset = None
    val_dataset_eval = None
    train_loader = None
    val_loader = None
    val_loader_eval = None
    tracker = None
    tracker_open = False
    device = config.DEVICE
    try:
        # Load data
        train_dataset = build_split_dataset(
            target=target,
            split='train',
            data_source=data_source,
            configured_hdf5_path=config.get('training.train_data_path'),
            distilled_manifest=distilled_manifest,
            distilled_split_col=distilled_split_col,
            distilled_min_quality=distilled_min_quality,
            distilled_max_samples_per_shard=distilled_max_samples_per_shard,
            distilled_sample_weight_col=distilled_sample_weight_col,
            distilled_default_shard_weight=distilled_default_shard_weight,
            distilled_quality_weight_alpha=distilled_quality_weight_alpha,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
        )
        val_dataset = build_split_dataset(
            target=target,
            split='val',
            data_source=data_source,
            configured_hdf5_path=config.get('training.val_data_path'),
            distilled_manifest=distilled_manifest,
            distilled_split_col=distilled_split_col,
            distilled_min_quality=distilled_min_quality,
            distilled_max_samples_per_shard=distilled_max_samples_per_shard,
            distilled_sample_weight_col=distilled_sample_weight_col,
            distilled_default_shard_weight=distilled_default_shard_weight,
            distilled_quality_weight_alpha=distilled_quality_weight_alpha,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
        )
        train_loader = _build_train_loader(
            train_dataset=train_dataset,
            batch_size=batch_size,
            data_source=data_source,
            distilled_use_weighted_sampler=distilled_use_weighted_sampler,
            distilled_weighted_sampler_replacement=distilled_weighted_sampler_replacement,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
            loader_kwargs=loader_kwargs,
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, **loader_kwargs)

        # Initialize model (with suggested hyperparams)
        # Note: StrategicOrchestrator needs to be modified to accept hidden_dim from trial if needed
        model = StrategicOrchestrator(device).to(device)

        # Initialize optimizer, loss, etc.
        optimizer = optim.Adam(model.parameters(), lr=lr)
        from train_router import CompositeRouterLoss # Assuming this is the loss
        loss_fn = CompositeRouterLoss(
            mse_weight=config.get('training.loss_weights.mse', 1.0),
            div_weight=config.get('training.loss_weights.div_penalty', 0.05),
            clamp_weight=config.get('training.loss_weights.clamp_penalty', 0.001)
        )

        # Initialize trainer
        tracker = ExperimentTracker(experiment_name="AIRouter_HP_Search")
        tracker.start_run(run_name=f"trial_{trial.number}")
        tracker_open = True
        # Log suggested hyperparams
        tracker.log_params(trial.params)

        trainer = AIRouterTrainer(model, train_loader, val_loader, optimizer, loss_fn, epochs=10, device=device, tracker=tracker)

        # Train for a few epochs (or until convergence/early stop)
        trainer.train()

        # Evaluate on validation set (return val loss for optimization)
        val_dataset_eval = build_split_dataset(
            target=target,
            split='val',
            data_source=data_source,
            configured_hdf5_path=config.get('training.val_data_path'),
            distilled_manifest=distilled_manifest,
            distilled_split_col=distilled_split_col,
            distilled_min_quality=distilled_min_quality,
            distilled_max_samples_per_shard=distilled_max_samples_per_shard,
            distilled_sample_weight_col=distilled_sample_weight_col,
            distilled_default_shard_weight=distilled_default_shard_weight,
            distilled_quality_weight_alpha=distilled_quality_weight_alpha,
            distilled_min_sampling_weight=distilled_min_sampling_weight,
        )
        val_loader_eval = DataLoader(val_dataset_eval, batch_size=batch_size, shuffle=False, **loader_kwargs)
        val_metrics = evaluate_model(model, val_loader_eval, device, metrics=['rmse'])
        val_rmse = val_metrics.get('rmse', float('inf'))

        tracker.log_metrics({'val_rmse': val_rmse})
        tracker.end_run()
        tracker_open = False

        return val_rmse # Minimize this value
    finally:
        if tracker is not None and tracker_open:
            try:
                tracker.end_run()
            except Exception:
                pass
        _shutdown_dataloader(train_loader)
        _shutdown_dataloader(val_loader)
        _shutdown_dataloader(val_loader_eval)
        _close_dataset_handles(train_dataset)
        _close_dataset_handles(val_dataset)
        _close_dataset_handles(val_dataset_eval)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def run_training_pipeline(
    target,
    use_hp_search=True,
    schedule='fold_balanced',
    seed=42,
    max_targets=None,
    data_source='hdf5',
    distilled_manifest='runs/distilled_residual_manifest.csv',
    distilled_split_col='split',
    distilled_min_quality=None,
    distilled_max_samples_per_shard=None,
    distilled_sample_weight_col='sampling_weight',
    distilled_default_shard_weight=1.0,
    distilled_quality_weight_alpha=0.0,
    distilled_min_sampling_weight=1e-6,
    distilled_use_weighted_sampler=False,
    distilled_weighted_sampler_replacement=True,
    initial_checkpoint='',
    checkpoint_strict=False,
    carry_over_checkpoint=True,
    checkpoint_dir='models/curriculum',
    early_stop_patience=10,
    curriculum_summary_json='',
    curriculum_summary_csv='',
    run_tag='',
):
    """
    Main pipeline to run training.
    """
    console = Console()
    run_tag_i = _sanitize_tag(run_tag) if str(run_tag).strip() else dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_initial_checkpoint = str(initial_checkpoint or "").strip()
    checkpoint_dir_i = str(checkpoint_dir or "models/curriculum")
    os.makedirs(checkpoint_dir_i, exist_ok=True)

    if isinstance(target, str) and target.lower() == 'all':
        selected_targets = resolve_targets(
            target='all',
            schedule=schedule,
            max_targets=max_targets,
            seed=seed,
        )
        console.print(
            f"[bold yellow]Starting multi-target training pipeline[/bold yellow] "
            f"(schedule={schedule}, targets={selected_targets})"
        )
        rows = []
        carry_ckpt = base_initial_checkpoint
        for idx, each_target in enumerate(selected_targets, start=1):
            console.print(f"[cyan]({idx}/{len(selected_targets)}) target={each_target}[/cyan]")
            this_init_ckpt = carry_ckpt if bool(carry_over_checkpoint) else base_initial_checkpoint
            this_ckpt_path = os.path.join(
                checkpoint_dir_i,
                f"best_airouter_curriculum_{idx:02d}_{_sanitize_tag(each_target)}_{run_tag_i}.pth",
            )
            result = _run_single_target_training(
                target=each_target,
                data_source=data_source,
                distilled_manifest=distilled_manifest,
                distilled_split_col=distilled_split_col,
                distilled_min_quality=distilled_min_quality,
                distilled_max_samples_per_shard=distilled_max_samples_per_shard,
                distilled_sample_weight_col=distilled_sample_weight_col,
                distilled_default_shard_weight=distilled_default_shard_weight,
                distilled_quality_weight_alpha=distilled_quality_weight_alpha,
                distilled_min_sampling_weight=distilled_min_sampling_weight,
                distilled_use_weighted_sampler=distilled_use_weighted_sampler,
                distilled_weighted_sampler_replacement=distilled_weighted_sampler_replacement,
                initial_checkpoint=this_init_ckpt,
                checkpoint_strict=bool(checkpoint_strict),
                checkpoint_path=this_ckpt_path,
                early_stop_patience=int(early_stop_patience),
                use_hp_search=bool(use_hp_search),
            )
            result.update({
                "order": int(idx),
                "schedule": schedule,
                "run_tag": run_tag_i,
                "init_checkpoint_used": this_init_ckpt if this_init_ckpt else None,
            })
            rows.append(result)
            best_ckpt = str(result.get("best_checkpoint_path") or "").strip()
            if bool(carry_over_checkpoint) and best_ckpt and os.path.exists(best_ckpt):
                carry_ckpt = best_ckpt

        payload = {
            "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "target_mode": "all",
            "schedule": str(schedule),
            "seed": int(seed),
            "max_targets": None if max_targets is None else int(max_targets),
            "selected_targets": selected_targets,
            "data_source": str(data_source),
            "distilled_manifest": str(distilled_manifest) if str(data_source).lower() == "distilled" else None,
            "distilled_split_col": str(distilled_split_col) if str(data_source).lower() == "distilled" else None,
            "run_tag": run_tag_i,
            "carry_over_checkpoint": bool(carry_over_checkpoint),
            "initial_checkpoint": os.path.abspath(base_initial_checkpoint) if base_initial_checkpoint else None,
            "checkpoint_strict": bool(checkpoint_strict),
            "checkpoint_dir": os.path.abspath(checkpoint_dir_i),
            "targets": rows,
            "summary": _aggregate_curriculum(rows),
        }
        if curriculum_summary_json:
            os.makedirs(os.path.dirname(curriculum_summary_json) or ".", exist_ok=True)
            with open(curriculum_summary_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        if curriculum_summary_csv:
            _write_rows_csv(rows, curriculum_summary_csv)
        console.print("[bold green]Multi-target pipeline completed[/bold green]")
        return payload

    console.print(f"[bold yellow]Starting training pipeline for {target}[/bold yellow]")
    if use_hp_search:
        console.print("[blue]Starting Hyperparameter Search with Optuna...[/blue]")
    else:
        console.print("[blue]Running training with default/configured hyperparameters...[/blue]")
    ckpt_path = os.path.join(
        checkpoint_dir_i,
        f"best_airouter_{_sanitize_tag(target)}_{run_tag_i}.pth",
    )
    result = _run_single_target_training(
        target=target,
        data_source=data_source,
        distilled_manifest=distilled_manifest,
        distilled_split_col=distilled_split_col,
        distilled_min_quality=distilled_min_quality,
        distilled_max_samples_per_shard=distilled_max_samples_per_shard,
        distilled_sample_weight_col=distilled_sample_weight_col,
        distilled_default_shard_weight=distilled_default_shard_weight,
        distilled_quality_weight_alpha=distilled_quality_weight_alpha,
        distilled_min_sampling_weight=distilled_min_sampling_weight,
        distilled_use_weighted_sampler=distilled_use_weighted_sampler,
        distilled_weighted_sampler_replacement=distilled_weighted_sampler_replacement,
        initial_checkpoint=base_initial_checkpoint,
        checkpoint_strict=bool(checkpoint_strict),
        checkpoint_path=ckpt_path,
        early_stop_patience=int(early_stop_patience),
        use_hp_search=bool(use_hp_search),
    )

    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "target_mode": "single",
        "target": target,
        "schedule": schedule,
        "seed": int(seed),
        "data_source": str(data_source),
        "distilled_manifest": str(distilled_manifest) if str(data_source).lower() == "distilled" else None,
        "distilled_split_col": str(distilled_split_col) if str(data_source).lower() == "distilled" else None,
        "run_tag": run_tag_i,
        "initial_checkpoint": os.path.abspath(base_initial_checkpoint) if base_initial_checkpoint else None,
        "checkpoint_strict": bool(checkpoint_strict),
        "checkpoint_dir": os.path.abspath(checkpoint_dir_i),
        "result": result,
    }
    if curriculum_summary_json:
        os.makedirs(os.path.dirname(curriculum_summary_json) or ".", exist_ok=True)
        with open(curriculum_summary_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    if curriculum_summary_csv:
        _write_rows_csv([result], curriculum_summary_csv)
    console.print(f"[bold green]Pipeline completed for {target}[/bold green]")
    return payload

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run the full AI Router training pipeline.')
    parser.add_argument('--target', type=str, required=True, help="Target name (e.g., Chignolin) or 'all'")
    parser.add_argument(
        '--schedule',
        type=str,
        default='fold_balanced',
        choices=['fold_balanced', 'round_robin', 'alphabetical', 'size_ascending', 'size_descending', 'defined'],
        help='Target scheduling strategy when --target all is used',
    )
    parser.add_argument('--seed', type=int, default=42, help='Random seed for target scheduler')
    parser.add_argument('--max_targets', type=int, default=None, help='Max number of targets when --target all is used')
    parser.add_argument('--hp_search', action='store_true', help='Enable hyperparameter search using Optuna')
    parser.add_argument(
        '--data_source',
        type=str,
        default='hdf5',
        choices=['hdf5', 'distilled'],
        help='Training data source type.',
    )
    parser.add_argument(
        '--distilled_manifest',
        type=str,
        default='runs/distilled_residual_manifest.csv',
        help='Manifest CSV for distilled dataset shards.',
    )
    parser.add_argument(
        '--distilled_split_col',
        type=str,
        default='split',
        help='Manifest split column name for distilled dataset source.',
    )
    parser.add_argument(
        '--distilled_min_quality',
        type=float,
        default=None,
        help='Optional minimum quality score filter for distilled shards.',
    )
    parser.add_argument(
        '--distilled_max_samples_per_shard',
        type=int,
        default=None,
        help='Optional max samples loaded per distilled shard.',
    )
    parser.add_argument(
        '--distilled_sample_weight_col',
        type=str,
        default='sampling_weight',
        help='Manifest column name for shard-level sampling weight.',
    )
    parser.add_argument(
        '--distilled_default_shard_weight',
        type=float,
        default=1.0,
        help='Fallback shard weight when manifest column is missing/invalid.',
    )
    parser.add_argument(
        '--distilled_quality_weight_alpha',
        type=float,
        default=0.0,
        help='Exponent for per-sample quality weighting (weight *= quality^alpha).',
    )
    parser.add_argument(
        '--distilled_min_sampling_weight',
        type=float,
        default=1e-6,
        help='Lower bound for per-sample sampling weights.',
    )
    parser.add_argument(
        '--distilled_use_weighted_sampler',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Use WeightedRandomSampler for distilled training split.',
    )
    parser.add_argument(
        '--distilled_weighted_sampler_replacement',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Replacement flag for distilled WeightedRandomSampler.',
    )
    parser.add_argument(
        '--initial_checkpoint',
        type=str,
        default='',
        help='Optional checkpoint path to warm-start model weights.',
    )
    parser.add_argument(
        '--checkpoint_strict',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Strict flag for model.load_state_dict when using --initial_checkpoint.',
    )
    parser.add_argument(
        '--carry_over_checkpoint',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='When --target all, reuse previous target best checkpoint as next target warm-start.',
    )
    parser.add_argument(
        '--checkpoint_dir',
        type=str,
        default='models/curriculum',
        help='Directory where best checkpoints are saved.',
    )
    parser.add_argument(
        '--early_stop_patience',
        type=int,
        default=10,
        help='Early stopping patience for trainer.',
    )
    parser.add_argument(
        '--curriculum_summary_json',
        type=str,
        default='',
        help='Optional output JSON path for training summary.',
    )
    parser.add_argument(
        '--curriculum_summary_csv',
        type=str,
        default='',
        help='Optional output CSV path for per-target summary.',
    )
    parser.add_argument(
        '--run_tag',
        type=str,
        default='',
        help='Optional tag used in checkpoint naming.',
    )

    args = parser.parse_args()

    run_training_pipeline(
        args.target,
        use_hp_search=args.hp_search,
        schedule=args.schedule,
        seed=args.seed,
        max_targets=args.max_targets,
        data_source=args.data_source,
        distilled_manifest=args.distilled_manifest,
        distilled_split_col=args.distilled_split_col,
        distilled_min_quality=args.distilled_min_quality,
        distilled_max_samples_per_shard=args.distilled_max_samples_per_shard,
        distilled_sample_weight_col=args.distilled_sample_weight_col,
        distilled_default_shard_weight=args.distilled_default_shard_weight,
        distilled_quality_weight_alpha=args.distilled_quality_weight_alpha,
        distilled_min_sampling_weight=args.distilled_min_sampling_weight,
        distilled_use_weighted_sampler=args.distilled_use_weighted_sampler,
        distilled_weighted_sampler_replacement=args.distilled_weighted_sampler_replacement,
        initial_checkpoint=args.initial_checkpoint,
        checkpoint_strict=args.checkpoint_strict,
        carry_over_checkpoint=args.carry_over_checkpoint,
        checkpoint_dir=args.checkpoint_dir,
        early_stop_patience=args.early_stop_patience,
        curriculum_summary_json=args.curriculum_summary_json,
        curriculum_summary_csv=args.curriculum_summary_csv,
        run_tag=args.run_tag,
    )

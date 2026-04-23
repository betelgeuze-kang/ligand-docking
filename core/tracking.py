import json
import shutil
import time
from pathlib import Path


class ExperimentTracker:
    """
    Lightweight local tracker.
    MLflow가 없는 환경에서도 동일한 호출 인터페이스를 유지합니다.
    """

    def __init__(self, experiment_name="default", base_dir="runs"):
        self.experiment_name = experiment_name
        self.base_dir = Path(base_dir)
        self.run_id = None
        self.run_name = None
        self.run_dir = None

    def _ensure_run(self):
        if self.run_id is None:
            self.start_run()

    @staticmethod
    def _json_default(obj):
        try:
            import numpy as np

            if isinstance(obj, np.generic):
                return obj.item()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except Exception:
            pass

        try:
            import torch

            if isinstance(obj, torch.Tensor):
                if obj.numel() == 1:
                    return obj.item()
                return obj.detach().cpu().tolist()
        except Exception:
            pass

        if hasattr(obj, "item"):
            try:
                return obj.item()
            except Exception:
                pass

        if isinstance(obj, Path):
            return str(obj)
        return str(obj)

    def _append_jsonl(self, filename, payload):
        self._ensure_run()
        path = self.run_dir / filename
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=self._json_default) + "\n")

    def start_run(self, run_name=None):
        ts = time.strftime("%Y%m%d-%H%M%S")
        self.run_name = run_name or "run"
        self.run_id = f"{self.run_name}_{ts}"
        self.run_dir = self.base_dir / self.experiment_name / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "experiment_name": self.experiment_name,
            "run_name": self.run_name,
            "run_id": self.run_id,
            "start_time": time.time(),
        }
        with open(self.run_dir / "run.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return self.run_id

    def log_params(self, params):
        payload = {"timestamp": time.time(), "params": params}
        self._append_jsonl("params.jsonl", payload)

    def log_metrics(self, metrics, step=None):
        payload = {"timestamp": time.time(), "metrics": metrics}
        if step is not None:
            payload["step"] = int(step)
        self._append_jsonl("metrics.jsonl", payload)

    def log_artifact(self, path):
        self._ensure_run()
        src = Path(path)
        dst_dir = self.run_dir / "artifacts"
        dst_dir.mkdir(parents=True, exist_ok=True)
        if src.exists() and src.is_file():
            shutil.copy2(src, dst_dir / src.name)
            recorded = str(dst_dir / src.name)
        else:
            recorded = str(src)
        self._append_jsonl("artifacts.jsonl", {"timestamp": time.time(), "path": recorded})

    def log_model(self, model, name="model"):
        self._ensure_run()
        try:
            import torch

            model_path = self.run_dir / "artifacts" / f"{name}.pth"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), model_path)
            self._append_jsonl("artifacts.jsonl", {"timestamp": time.time(), "path": str(model_path)})
        except Exception as exc:
            self._append_jsonl(
                "artifacts.jsonl",
                {"timestamp": time.time(), "path": name, "warning": f"model save skipped: {exc}"},
            )

    def end_run(self):
        if self.run_id is None:
            return
        run_json = self.run_dir / "run.json"
        metadata = {}
        if run_json.exists():
            with open(run_json, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        metadata["end_time"] = time.time()
        with open(run_json, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def get_run_id(self):
        return self.run_id

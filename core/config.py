# core/config.py

import yaml
import logging
import logging.handlers
import os
from pathlib import Path

class ConfigManager:
    """
    시스템 설정을 로드하고 관리하는 클래스.
    YAML 파일에서 설정을 읽어옴.
    """
    def __init__(self, config_path="config/settings.yaml"):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        self._load_config()
        self._setup_logging()

    def _load_config(self):
        """YAML 파일을 로드하여 인스턴스 변수로 저장."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    def get(self, key, default=None):
        """
        중첩된 키를 사용하여 설정 값을 가져옴.
        예: config.get('simulation.integrator.dt')
        """
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def _setup_logging(self):
        """logging 모듈을 설정."""
        log_level_str = self.get('logging.level', 'INFO')
        log_format_str = self.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)

        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        formatter = logging.Formatter(log_format_str)

        # 콘솔 핸들러
        if self.get('logging.console_handler.enabled', True):
            console_level_str = self.get('logging.console_handler.level', 'INFO')
            console_level = getattr(logging, console_level_str.upper(), logging.INFO)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # 파일 핸들러
        if self.get('logging.file_handler.enabled', True):
            log_filename = self.get('logging.file_handler.filename', 'logs/main.log')
            log_max_bytes = self.get('logging.file_handler.max_bytes', 10485760) # 10MB
            log_backup_count = self.get('logging.file_handler.backup_count', 5)
            log_file_path = Path(log_filename)
            log_file_path.parent.mkdir(parents=True, exist_ok=True) # 로그 디렉토리 생성

            file_handler = logging.handlers.RotatingFileHandler(
                log_file_path, maxBytes=log_max_bytes, backupCount=log_backup_count
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    @property
    def DEVICE(self):
        import torch

        device_type = self.get('device.type', 'cpu')
        device_id = self.get('device.id', 0)
        require_gpu = bool(self.get('device.require_gpu', False)) or (os.environ.get('MD_GPU_ONLY', '0') == '1')
        if device_type == 'cuda':
            if not torch.cuda.is_available():
                if require_gpu:
                    raise RuntimeError("GPU-only mode enabled but CUDA is unavailable.")
                return torch.device('cpu')
            return torch.device(f'cuda:{device_id}')
        elif device_type == 'mps': # For Apple Silicon
            if torch.backends.mps.is_available():
                return torch.device('mps')
            if require_gpu:
                raise RuntimeError("GPU-only mode enabled but MPS is unavailable.")
            return torch.device('cpu')
        else:
            if require_gpu:
                raise RuntimeError(f"GPU-only mode enabled but requested device.type='{device_type}'.")
            return torch.device('cpu')

    @property
    def BATCH_SIZE(self):
        return self.get('training.batch_size', 32)

    @property
    def LEARNING_RATE(self):
        return self.get('training.learning_rate', 2e-4)

    # 다른 설정 속성들을 필요한 만큼 추가...


# 전역 설정 인스턴스 생성
config = ConfigManager()

# 로거 인스턴스 생성
logger = logging.getLogger(__name__)

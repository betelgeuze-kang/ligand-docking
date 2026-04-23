# monitor/realtime_logger.py

import csv
import os
from datetime import datetime

class RealtimeLogger:
    def __init__(self, path="logs/history.csv"):
        self.path = path
        self.router_weights_path = path.replace("history.csv", "router_weights.csv") # 별도 파일
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # history.csv 초기화
        if not os.path.exists(self.path):
            with open(self.path, 'w', newline='') as f:
                writer = csv.writer(f)
                # 초기 칼럼 헤더 (필요한 칼럼들 포함, 가중치는 나중에 동적으로 추가 가능)
                writer.writerow(['timestamp', 'target', 'step', 'batch_idx', 'Rg', 'energy', 'ionic_strength'])
        # router_weights.csv 초기화
        if not os.path.exists(self.router_weights_path):
            with open(self.router_weights_path, 'w', newline='') as f:
                writer = csv.writer(f)
                # 첫 줄은 헤더 없이 생성 (가중치 칼럼이 동적으로 변경될 수 있음)
                pass # 헤더는 첫 로깅 시 결정

    def log(self, data):
        """기존 history 로깅 메서드"""
        with open(self.path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(data.keys()))
            # 첫 행일 경우 헤더 작성
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(data)

    def log_router_weights(self, weights_dict, step, batch_idx=0):
        """AI Router의 가중치를 로깅하는 메서드"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'step': step,
            'batch_idx': batch_idx,
        }
        log_entry.update(weights_dict) # weights_dict의 키-값 쌍을 log_entry에 추가

        with open(self.router_weights_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(log_entry.keys()))
            # 첫 행일 경우 헤더 작성
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(log_entry)

# 사용 예시 (run_refinement.py 내부):
# logger = RealtimeLogger()
# weights_dict = {'core_salt': 0.1, 'branch_idp_logic': 0.8, ...}
# logger.log_router_weights(weights_dict, step=100, batch_idx=0)

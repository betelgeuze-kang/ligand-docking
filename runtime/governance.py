# runtime/governance.py

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class AIControlModel(nn.Module):
    """
    Runtime Governance Layer에서 사용하는 AI 기반 제어 모델.
    입력: 시뮬레이션 상태, AIRouter 출력, PhysicsGuard 상태
    출력: AI intervention rate, correction strength, guard sensitivity 등 제어 파라미터
    """
    def __init__(self, input_dim, hidden_dim=256, output_dim=3): # 예: rate, strength, guard_sensitivity
        super(AIControlModel, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, output_dim)
        self.dropout = nn.Dropout(0.1)

    def forward(self, state_vector):
        """
        Args:
            state_vector (torch.Tensor): [B, input_dim] 입력 특징 벡터
        Returns:
            control_params (torch.Tensor): [B, output_dim] 제어 파라미터 벡터 (예: [rate, strength, sensitivity])
        """
        x = F.silu(self.fc1(state_vector))
        x = self.dropout(x)
        x = F.silu(self.fc2(x))
        x = self.dropout(x)
        x = self.fc3(x) # Raw logits
        # 각 파라미터에 맞는 활성화 함수 적용 (예: sigmoid for rate/strength, softplus for positive values)
        rate = torch.sigmoid(x[..., 0]).unsqueeze(-1) # 0 ~ 1
        strength = torch.sigmoid(x[..., 1]).unsqueeze(-1) # 0 ~ 1
        sensitivity_offset = torch.tanh(x[..., 2]).unsqueeze(-1) # -1 ~ 1 offset for sensitivity
        control_params = torch.cat([rate, strength, sensitivity_offset], dim=-1)
        return control_params

class RuntimeGovernanceLayer:
    """
    시뮬레이션 실행을 관리하고, AI intervention rate 등을 동적으로 조절합니다.
    AIControlModel을 사용하여 제어 결정을 수행합니다.
    """
    def __init__(self, ai_control_model, initial_intervention_rate=0.05, initial_correction_strength=0.1, initial_guard_sensitivity_offset=0.0):
        self.ai_ctrl_model = ai_control_model
        self.current_intervention_rate = initial_intervention_rate
        self.current_correction_strength = initial_correction_strength
        self.current_guard_sensitivity_offset = initial_guard_sensitivity_offset # base sensitivity에 대한 오프셋

        # 상태 수집용 버퍼 (필요시)
        self.state_history = []
        self.history_length = 5 # 예: 최근 5 스텝 상태 사용

        # [NEW] Previous state storage for reward calculation
        self.prev_state = None
        self.prev_action = None # e.g., AIRouter weights, intervention rate, etc.

    def _normalize_router_info(self, router_info):
        """
        router_info 호환 레이어.
        지원 형식:
        - (weights, names, was_explored)
        - (weights, names, was_explored, mixing_ratio, effective_ai_influence, active_mask)
        """
        if router_info is None:
            return None, None, None, None, None, None

        if len(router_info) == 3:
            weights, names, was_explored = router_info
            return weights, names, was_explored, None, None, None

        if len(router_info) >= 6:
            return router_info[:6]

        raise ValueError(
            "router_info must have length 3 or >=6: "
            "(weights, names, was_explored[, mixing_ratio, effective_ai_influence, active_mask])"
        )

    def update(self, sim_state_dict, router_info, guard_status):
        """
        시뮬레이션 상태, AIRouter 정보, PhysicsGuard 상태를 기반으로 제어 파라미터를 업데이트합니다.
        Args:
            sim_state_dict (dict): {'Rg': val, 'SASA': val, 'RMSD': val, 'energy': val, 'temp': val, 'ionic_strength': val, ...}
            router_info (tuple): (weights_tensor, names_list, was_explored_tensor, mixing_ratio, effective_ai_influence, active_mask) from orchestrator.get_last_router_info()
            guard_status (dict): {'violation_count': int, 'last_energy_drift': float, 'last_momentum_drift': float, ...}
        """
        # Store previous state and action for reward calculation
        self.prev_state = sim_state_dict.copy()
        self.prev_action = router_info[0] if router_info else None # Store previous weights

        # 1. 입력 특징 벡터 구성
        feature_vector = self._build_state_vector(sim_state_dict, router_info, guard_status)

        # 2. AI 제어 모델 실행
        with torch.no_grad(): # 제어는 일반적으로 학습 X, 추론만
            ctrl_params = self.ai_ctrl_model(feature_vector.unsqueeze(0)) # [1, output_dim]

        # 3. 제어 파라미터 추출 및 적용
        new_rate = ctrl_params[0, 0].item()
        new_strength = ctrl_params[0, 1].item()
        new_sensitivity_offset = ctrl_params[0, 2].item()

        # Clamp values to reasonable ranges
        self.current_intervention_rate = np.clip(new_rate, 0.0, 0.5) # 예: 0~50%
        self.current_correction_strength = np.clip(new_strength, 0.0, 1.0) # 예: 0~100%
        self.current_guard_sensitivity_offset = np.clip(new_sensitivity_offset, -0.01, 0.01) # 예: 민감도 +-1%

        print(f"  [RuntimeGov] Updated: Rate={self.current_intervention_rate:.3f}, "
              f"Strength={self.current_correction_strength:.3f}, "
              f"Guard_Sens_Offset={self.current_guard_sensitivity_offset:.5f}")

    def calculate_reward(self, sim_state_dict, router_info, guard_status):
        """
        현재 상태를 기반으로 보상을 계산합니다.
        Args:
            sim_state_dict (dict): 현재 시뮬레이션 상태
            router_info (tuple): 현재 AIRouter 정보 (weights, names, was_explored, mixing_ratio, effective_ai_influence, active_mask)
            guard_status (dict): 현재 PhysicsGuard 상태
        Returns:
            reward (float): 계산된 보상 값
        """
        # Define reward components
        # Example: Reward for RMSD improvement, energy decrease, fewer violations
        reward = 0.0

        # RMSD Improvement (compared to previous state)
        if self.prev_state and 'RMSD' in sim_state_dict and 'RMSD' in self.prev_state:
            current_rmsd = sim_state_dict['RMSD']
            prev_rmsd = self.prev_state['RMSD']
            if current_rmsd < prev_rmsd:
                reward += 1.0
            elif current_rmsd > prev_rmsd:
                reward -= 1.0
            # Penalty for high RMSD
            if current_rmsd > 5.0: # Example threshold
                reward -= 0.5

        # Energy Decrease
        if self.prev_state and 'energy' in sim_state_dict and 'energy' in self.prev_state:
            current_energy = sim_state_dict['energy']
            prev_energy = self.prev_state['energy']
            if current_energy < prev_energy:
                reward += 0.5
            elif current_energy > prev_energy:
                reward -= 0.5

        # Fewer Physics Violations
        if self.prev_state and 'violation_count' in guard_status:
            current_violations = guard_status['violation_count']
            prev_violations = self.prev_state.get('prev_violations', 0) # Need to store this in state or governance
            if current_violations < prev_violations:
                reward += 0.5
            elif current_violations > prev_violations:
                reward -= 1.0
            # Penalty for high violation count
            if current_violations > 5: # Example threshold
                reward -= 1.0

        # Exploration bonus (if action was exploratory)
        _, _, was_explored, _, _, _ = self._normalize_router_info(router_info)
        if was_explored is not None and torch.as_tensor(was_explored).any():
            reward += 0.1 # Small bonus for exploration

        # Structure stabilization bonus (e.g., based on Rg, SASA trends)
        # if self.prev_state and 'Rg' in sim_state_dict and 'Rg' in self.prev_state:
        #     # Add logic for Rg stability/reduction
        #     pass

        # Normalize or clip reward if necessary
        reward = np.clip(reward, -5.0, 5.0)

        print(f"  [RuntimeGov] Calculated Reward: {reward:.3f}")
        return reward


    def _build_state_vector(self, sim_state, router_info, guard_status):
        """
        다양한 입력 정보를 하나의 텐서로 결합합니다.
        """
        # Sim State Features
        rg = sim_state.get('Rg', 0.0)
        sasa = sim_state.get('SASA', 0.0)
        rmsd = sim_state.get('RMSD', 0.0)
        energy = sim_state.get('energy', 0.0)
        temp = sim_state.get('temp', 300.0)
        ionic_str = sim_state.get('ionic_strength', 0.1)

        # Router Info Features (예: 평균 가중치, 특정 모듈 가중치 등)
        router_weights, _, _, _, _, _ = self._normalize_router_info(router_info)
        if router_weights is not None and router_weights.numel() > 0:
            avg_weight = router_weights.mean().item()
            max_weight = router_weights.max().item()
            # 특정 모듈 가중치도 추가 가능 (예: core_salt, branch_idp_logic 등)
            # 이 정보는 router_info에서 직접 가져오거나, names를 이용해 인덱싱 필요
            # 예시 (가정): 'core_salt'는 0번째, 'branch_idp_logic'는 5번째
            # 특정_가중치 = router_weights[:, 0].mean().item() if router_weights.shape[1] > 0 else 0.0
        else:
            avg_weight = 0.0
            max_weight = 0.0

        # Guard Status Features
        violations = guard_status.get('violation_count', 0)
        last_energy_drift = guard_status.get('last_energy_drift', 0.0)
        last_momentum_drift = guard_status.get('last_momentum_drift', 0.0)

        # Combine into a single vector
        state_vec_np = np.array([
            rg, sasa, rmsd, energy, temp, ionic_str,
            avg_weight, max_weight,
            violations, last_energy_drift, last_momentum_drift
        ], dtype=np.float32)

        return torch.from_numpy(state_vec_np).to(self.ai_ctrl_model.fc1.weight.device)

    def get_current_control_settings(self):
        """현재 제어 설정을 반환합니다."""
        return {
            'intervention_rate': self.current_intervention_rate,
            'correction_strength': self.current_correction_strength,
            'guard_sensitivity_offset': self.current_guard_sensitivity_offset
        }

# core/attention_layers.py

import torch
import torch.nn as nn
import torch.nn.functional as F

class MultiHeadAttention(nn.Module):
    """
    Standard Multi-Head Attention module.
    Can be used to model interactions between different Specialist modules.
    """
    def __init__(self, d_model, num_heads, dropout=0.1):
        super(MultiHeadAttention, self).__init__()
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)

    def forward(self, query, key, value, mask=None):
        """
        Args:
            query: [B, N, d_model]
            key: [B, N, d_model]
            value: [B, N, d_model]
            mask: [B, N, N] or None
        Returns:
            output: [B, N, d_model]
        """
        B, N, _ = query.shape

        # Linear projections
        Q = self.W_q(query).view(B, N, self.num_heads, self.d_k).transpose(1, 2) # [B, H, N, d_k]
        K = self.W_k(key).view(B, N, self.num_heads, self.d_k).transpose(1, 2)   # [B, H, N, d_k]
        V = self.W_v(value).view(B, N, self.num_heads, self.d_k).transpose(1, 2) # [B, H, N, d_k]

        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / (self.d_k ** 0.5) # [B, H, N, N]
        if mask is not None:
            scores.masked_fill_(mask == 0, -1e9)
        attn_weights = F.softmax(scores, dim=-1) # [B, H, N, N]
        attn_weights = self.dropout(attn_weights)

        output = torch.matmul(attn_weights, V) # [B, H, N, d_k]
        output = output.transpose(1, 2).contiguous().view(B, N, self.d_model) # [B, N, d_model]

        # Final linear projection
        output = self.W_o(output)
        return output, attn_weights

class AIRouterAttention(nn.Module):
    """
    AIRouter 구조를 Attention 기반으로 재구성.
    모듈 간 상호작용을 모델링.
    """
    def __init__(self, num_modules, d_model=256, num_heads=8, hidden_dim=512, explore_prob=0.1):
        super(AIRouterAttention, self).__init__()
        self.num_modules = num_modules
        self.d_model = d_model
        self.explore_prob = nn.Parameter(torch.tensor(explore_prob), requires_grad=False)

        # 모듈 출력을 d_model 차원으로 매핑
        self.module_projector = nn.Linear(3, d_model) # 예: 각 모듈의 힘 벡터 [N, 3] -> [N, d_model]

        # Attention layer
        self.attention = MultiHeadAttention(d_model, num_heads)

        # Feed-forward network after attention
        self.ffn = nn.Sequential(
            nn.Linear(d_model, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, d_model),
            nn.Dropout(0.1)
        )

        # Output layer to produce weights
        self.output_proj = nn.Linear(d_model, 1) # 각 모듈에 대한 스칼라 점수

        # Layer norm
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

    def forward(self, c, top, aux_outputs, sim_params):
        """
        Args:
            c: Coordinates [B, N, 3]
            top: Topology object
            aux_outputs: Dict from StrategicOrchestrator.forward (key: module_name, value: info_dict)
            sim_params: Dict containing global params like temp, salt concentration etc.
        Returns:
            weights: [B, num_modules] tensor of weights for each specialist module.
            is_explored: Boolean indicating if exploration was used for this prediction.
        """
        B, N, _ = c.shape

        # 1. 모듈 출력 준비
        f_individual_list = []
        module_names = []
        for name, info in aux_outputs.items():
            if name.startswith('core_') or name.startswith('branch_'):
                # info가 힘 벡터 [B, N, 3]라고 가정
                f_module = info # 또는 info['force'] 등 실제 힘 벡터를 추출
                f_individual_list.append(f_module)
                module_names.append(name)

        if not f_individual_list:
            # 모듈이 없을 경우 처리
            weights = torch.zeros(B, self.num_modules, device=c.device)
            is_explored = torch.rand(B, device=c.device) < self.explore_prob
            return weights, is_explored, module_names

        # Stack module outputs along a new 'module' dimension
        # Shape: [B, N, num_modules, 3]
        f_modules_stacked = torch.stack(f_individual_list, dim=2)

        # Reshape to treat each (atom, module) pair as a node
        # Shape: [B, N * num_modules, 3]
        f_modules_flat = f_modules_stacked.view(B, N * len(f_individual_list), 3)

        # Project to d_model
        # Shape: [B, N * num_modules, d_model]
        f_modules_proj = self.module_projector(f_modules_flat)

        # 2. Attention 계산 (Self-Attention on the stacked/module-dim)
        # 이 부분은 모듈 간 상호작용을 모델링합니다.
        # 실제 구현에서는 모듈 간 관계를 나타내는 adjacency matrix나 edge features가 필요할 수 있습니다.
        # 여기서는 모든 모듈이 연결되어 있다고 가정 (Full Attention)
        # 또는, 모듈 타입(core vs branch)에 따라 다른 마스크를 적용할 수 있음
        attn_output, attn_weights = self.attention(f_modules_proj, f_modules_proj, f_modules_proj)

        # Add & Norm
        f_modules_attn = self.norm1(f_modules_proj + attn_output)

        # Feed Forward
        f_modules_ffn = self.ffn(f_modules_attn)

        # Add & Norm
        f_modules_out = self.norm2(f_modules_attn + f_modules_ffn) # [B, N * num_modules, d_model]

        # 3. Output layer to get weights per module
        # Reshape back to [B, N, num_modules, d_model]
        f_modules_out_reshaped = f_modules_out.view(B, N, len(f_individual_list), self.d_model)

        # Average over N dimension to get [B, num_modules, d_model]
        f_modules_avg = f_modules_out_reshaped.mean(dim=1)

        # Apply output projection to get scalar score per module
        scores = self.output_proj(f_modules_avg).squeeze(-1) # [B, num_modules]

        # Apply softmax to get weights
        weights = F.softmax(scores, dim=-1)

        # 4. 탐색 로직 (기존과 동일)
        is_explored = torch.rand(B, device=c.device) < self.explore_prob
        # 탐색 로직은 복잡할 수 있음 (예: attention weights에 노이즈 추가 후 재정규화)
        # 여기서는 간단화: 탐색 시 기존 weights에 노이즈를 추가
        if is_explored.any():
            exploration_noise = torch.randn_like(weights) * 0.1
            weights_explore = F.softmax(scores + exploration_noise, dim=-1)
            weights = torch.where(is_explored.unsqueeze(-1), weights_explore, weights)

        return weights, is_explored, module_names

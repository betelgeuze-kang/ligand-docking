# core/gnn_layers.py

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GCNConv, GATConv
    TORCH_GEOMETRIC_AVAILABLE = True
except ImportError:
    TORCH_GEOMETRIC_AVAILABLE = False

    class _MissingTorchGeometricLayer(nn.Module):
        pass

    GCNConv = _MissingTorchGeometricLayer
    GATConv = _MissingTorchGeometricLayer

# 예: 모듈 간 관계를 나타내는 그래프를 기반으로 동작하는 GNN
class AIRouterGNN(nn.Module):
    """
    GNN 기반 AIRouter.
    모듈 간 상호작용을 그래프 구조로 모델링.
    """
    def __init__(self, num_modules, d_module_feat=64, d_global_feat=4, d_hidden=256, d_output=1, num_layers=3, gnn_type='gcn'):
        super(AIRouterGNN, self).__init__()
        if not TORCH_GEOMETRIC_AVAILABLE:
            raise ImportError("torch_geometric is required to use AIRouterGNN. Install torch-geometric first.")

        self.num_modules = num_modules
        self.d_hidden = d_hidden
        self.gnn_type = gnn_type

        # 모듈 출력 특징을 매핑 (예: 힘의 평균/최대값 등을 특징으로 사용)
        # f_module: [B, N, 3] -> [B, d_module_feat] (global pooling 후)
        # 또는, f_module: [B, N, 3] -> [B*N, 3] -> [B*N, d_module_feat] (atom-level feature로 사용)
        # 여기서는 모듈 하나의 출력을 하나의 노드로 간주하고, 노드 특징으로 사용
        # 실제 모듈 출력은 [B, N, 3] 형태이므로, 이를 어떻게 요약할지 정의 필요
        # 예: 모듈별 힘 벡터의 norm 또는 mean을 특징으로 사용
        self.module_feat_encoder = nn.Linear(3, d_module_feat) # [N, 3] -> [N, d_module_feat]

        # Global condition (sim_params) 인코더
        self.global_feat_encoder = nn.Linear(d_global_feat, d_hidden)

        # GNN Layers
        gnn_layers = []
        for i in range(num_layers):
            if gnn_type == 'gcn':
                gnn_layers.append(GCNConv(d_hidden if i > 0 else d_module_feat, d_hidden))
            elif gnn_type == 'gat':
                gnn_layers.append(GATConv((d_hidden if i > 0 else d_module_feat, d_hidden), d_hidden, heads=4, concat=False))
            else:
                raise ValueError(f"Unsupported GNN type: {gnn_type}")
            gnn_layers.append(nn.ReLU())
            gnn_layers.append(nn.Dropout(0.1))
        self.gnn_layers = nn.Sequential(*gnn_layers)

        # Global pooling (예: mean pooling)
        # self.pool = global_mean_pool # 이는 batch index가 필요함

        # Output layer
        # GNN output + global condition -> weights
        self.output_proj = nn.Linear(d_hidden + d_hidden, d_output) # d_hidden (GNN) + d_hidden (Global) -> d_output (e.g., 1 for score per module)

    def forward(self, module_outputs_list, module_edge_index, global_cond):
        """
        Args:
            module_outputs_list: List of [B, N, 3] tensors for each module (length = num_modules)
            module_edge_index: [2, num_edges] tensor representing module connections
            global_cond: [B, d_global_feat] tensor (e.g., [temp, salt, pH, ionic_strength])
        Returns:
            weights: [B, num_modules] tensor of weights for each specialist module.
        """
        B = module_outputs_list[0].shape[0]
        N = module_outputs_list[0].shape[1]

        # 1. Prepare Node Features (Per Module)
        # module_outputs_list: [f_mod1, f_mod2, ...] where f_modX is [B, N, 3]
        # Concatenate along module dimension: [B, num_modules, N, 3]
        f_modules_cat = torch.stack(module_outputs_list, dim=1) # [B, num_modules, N, 3]

        # Global pooling on atom dimension (N) to get per-module features
        # Example: Mean pooling
        f_modules_pooled = f_modules_cat.mean(dim=2) # [B, num_modules, 3]
        # Example: Max pooling
        # f_modules_pooled, _ = f_modules_cat.max(dim=2) # [B, num_modules, 3]

        # Encode pooled features
        x = self.module_feat_encoder(f_modules_pooled) # [B, num_modules, d_module_feat]

        # Repeat for batch processing
        # GNN은 일반적으로 하나의 그래프에 대해 작동하므로, 배치 처리가 필요하면
        # Batch index와 함께 처리해야 함 (torch_geometric의 Batch 사용)
        # 또는, 배치 차원을 분리하여 각각 처리
        # 여기서는 간단화를 위해 배치 차원을 무시하고, 첫 번째 배치만 처리하는 방식으로 가정
        # 실제 구현에서는 torch_geometric의 Batch 클래스를 사용해야 함
        # 예:
        # batch_data_list = []
        # for b in range(B):
        #     x_b = x[b] # [num_modules, d_module_feat]
        #     edge_index_b = module_edge_index # 모듈 간 관계는 배치 내에서 동일하다고 가정
        #     data_b = Data(x=x_b, edge_index=edge_index_b)
        #     batch_data_list.append(data_b)
        # batch = Batch.from_data_list(batch_data_list)
        # x_batch = self.gnn_layers(batch.x, batch.edge_index)
        # pooled_batch = global_mean_pool(x_batch, batch.batch)
        # ...

        # For simplicity, assume B=1 or process one sample at a time within the batch loop in the caller
        # This is a simplified representation
        x = x[0] # Take first sample in batch: [num_modules, d_module_feat]
        edge_index = module_edge_index # [2, num_edges]

        # 2. GNN Forward Pass
        for layer in self.gnn_layers:
            if isinstance(layer, (GCNConv, GATConv)):
                x = layer(x, edge_index)
            else:
                x = layer(x) # ReLU, Dropout, etc.

        # 3. Global Pooling
        # x is now [num_modules, d_hidden]
        # Global pooling to get graph-level representation
        gnn_output = x.mean(dim=0, keepdim=True) # [1, d_hidden] # Example: mean pooling

        # 4. Concatenate with Global Condition
        global_cond_encoded = self.global_feat_encoder(global_cond[0].unsqueeze(0)) # [1, d_hidden]
        combined_repr = torch.cat([gnn_output, global_cond_encoded], dim=-1) # [1, d_hidden * 2]

        # 5. Output Projection
        scores_per_module = self.output_proj(combined_repr) # [1, d_output=1]
        # Repeat for each module to get [num_modules, 1]
        scores = scores_per_module.repeat(self.num_modules, 1) # [num_modules, 1]
        scores = scores.squeeze(-1) # [num_modules]

        # 6. Apply Softmax to get weights
        weights = F.softmax(scores, dim=-1) # [num_modules]

        # Repeat for batch size
        weights_batch = weights.unsqueeze(0).repeat(B, 1) # [B, num_modules]

        return weights_batch


# Note: 실제 사용 시, module_edge_index는 모듈 타입에 따라 정적으로 정의하거나,
# 동적으로 생성하는 로직이 필요합니다. 예: core_XXX와 branch_YYY는 연결 안 함 등.

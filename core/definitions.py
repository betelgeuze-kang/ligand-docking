# core/definitions.py

# 기존 내용을 대체하거나 확장
# from .config import config, logger # 또는 config 인스턴스 직접 import

# 기존 Config 클래스가 있다면, 이걸 대체
# class Config:
#     DEVICE = config.DEVICE
#     BATCH_SIZE = config.BATCH_SIZE
#     LEARNING_RATE = config.LEARNING_RATE
#     # ... 다른 설정들

# 또는 단순히 config 인스턴스를 재할당
from .config import config as Config
from .config import logger

class StrategyType:
    DIRECT_PERTURBATION_NO_MIN = "DIRECT_PERTURBATION_NO_MIN"
    CA_ONLY = "CA_ONLY"
    ADRESS = "ADRESS"
    # Add more types as needed

class ResearchConstants:
    CHALLENGES = {
        # Small-protein target set (10 total) for structural diversity learning.
        # Fold coverage: beta-hairpin, all-alpha, all-beta, alpha/beta, disulfide-rich compact.
        'Chignolin': {'n_res': 10, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'beta_hairpin'},
        'Trp_Cage': {'n_res': 20, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'mini_alpha_beta'},
        'Villin_HP35': {'n_res': 35, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'all_alpha'},
        'BBA5': {'n_res': 23, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'alpha_beta_mini'},
        'FSD_1': {'n_res': 28, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'alpha_beta_mini'},
        'WW_Domain_FiP35': {'n_res': 35, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'all_beta'},
        'Crambin': {'n_res': 46, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'compact_disulfide_rich'},
        'Protein_A_Bdomain': {'n_res': 60, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'all_alpha'},
        'GB1_Mini': {'n_res': 56, 'type': 'protein', 'box': [100.0, 100.0, 100.0], 'fold_class': 'alpha_beta'},
        'Ubiquitin_Mini': {'n_res': 76, 'type': 'protein', 'box': [120.0, 120.0, 120.0], 'fold_class': 'alpha_beta'},
        # PDB 3V94 canonical observed chain B: 334 CA rows, 345 SEQRES residues, 11 missing residues.
        'T. cruzi PDE': {
            'n_res': 334,
            'type': 'protein',
            'box': [200.0, 200.0, 200.0],
            'fold_class': 'phosphodiesterase',
            'native_pdb_path': 'data/public_structures/selected_allatom_native_v1/t_cruzi_pde_pdb_3V94.pdb',
            'canonical_chain': 'B',
        },
    }

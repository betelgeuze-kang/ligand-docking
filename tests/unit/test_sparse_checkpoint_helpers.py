import math

import torch

from tools import report_sparse_checkpoints as sparse


def test_parse_checkpoints_adds_zero_and_sorts():
    pts = sparse._parse_checkpoints("30,10,30", steps=60)
    assert pts == [0, 10, 30]


def test_parse_checkpoints_rejects_out_of_range():
    try:
        sparse._parse_checkpoints("0,80", steps=60)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_rmsd_aligned_translation_rotation_invariant():
    a = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
    )
    theta = math.pi / 2.0
    r = torch.tensor(
        [
            [math.cos(theta), -math.sin(theta), 0.0],
            [math.sin(theta), math.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
    )
    b = (a @ r.T) + torch.tensor([10.0, -3.0, 2.0], dtype=torch.float32)
    assert sparse._rmsd_raw(a, b) > 1.0
    assert sparse._rmsd_aligned(a, b) < 1e-5


def test_clash_pairs_excludes_bonded_neighbors():
    # 0-1 and 1-2 are bonded neighbors, so only 0-2 counts as nonbond pair.
    c = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
            [0.9, 0.0, 0.0],
        ],
        dtype=torch.float32,
    )
    assert sparse._clash_pairs(c, clash_cutoff=1.1) == 1


def test_clash_pairs_provider_overflow_blocks_claim_unsafe_diagnostics():
    c = torch.zeros(4, 3, dtype=torch.float32)
    try:
        sparse._clash_pairs(c, clash_cutoff=1.1, max_neighbors=1)
        assert False, "expected neighbor provider overflow"
    except ValueError as exc:
        assert "sparse_checkpoint_clash_pairs neighbor provider overflow" in str(exc)

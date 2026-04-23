import os
import tempfile

import h5py
import torch

from core.definitions import Config, StrategyType
from core.forcefield import ForceField
from core.spatial import GridSpatialHash
from core.topology import TopologyFactory
from tools.generate_perturbed_data import DataGenerator


def test_topology_default_is_ca_sc():
    top = TopologyFactory(10, "protein", [100.0, 100.0, 100.0], Config.DEVICE, target_name="Chignolin")
    assert top.strategy_type == StrategyType.CA_ONLY
    assert top.use_virtual_sc is True


def test_expand_residue_types_for_virtual_sc():
    n_res = 7
    top = TopologyFactory(n_res, "protein", [30.0, 30.0, 30.0], Config.DEVICE, target_name="test")
    expanded = top.expand_residue_types_for_virtual_sc()
    assert expanded.shape[0] == n_res * 2


def test_forcefield_shapes_for_implicit_and_explicit_2bead():
    n_res = 10
    top = TopologyFactory(n_res, "protein", [100.0, 100.0, 100.0], Config.DEVICE, target_name="Chignolin")
    ff = ForceField(top)

    c_ca = torch.linspace(0, n_res - 1, n_res, device=Config.DEVICE).view(1, n_res, 1).repeat(1, 1, 3)
    sh = GridSpatialHash([100.0, 100.0, 100.0], 12.0, Config.DEVICE)
    nb_ca = sh.get_neighbor_data(c_ca)
    f_ca, pe_ca = ff.compute(c_ca, nb_ca)
    assert f_ca.shape == c_ca.shape
    assert pe_ca.shape == (1, 1)

    c_sc = top.compute_virtual_sc_coords(c_ca)
    c_explicit = torch.cat([c_ca, c_sc], dim=1)
    nb_explicit = sh.get_neighbor_data(c_explicit)
    f_explicit, pe_explicit = ff.compute(c_explicit, nb_explicit)
    assert f_explicit.shape == c_explicit.shape
    assert pe_explicit.shape == (1, 1)


def test_data_generator_explicit_2bead_writes_2n_shape():
    with tempfile.TemporaryDirectory(prefix="ca_sc_explicit_") as tmpdir:
        gen = DataGenerator(
            target="Chignolin",
            total_samples=8,
            noise=0.02,
            output_dir=tmpdir,
            train_ratio=0.75,
            val_ratio=0.125,
            fast_mode=True,
            explicit_2bead=True,
        )
        ok = gen.generate()
        assert ok is True

        train_path = os.path.join(tmpdir, "chignolin_airouter_train_data.h5")
        assert os.path.exists(train_path)
        with h5py.File(train_path, "r") as f:
            coords = f["coords"]
            target_forces = f["target_forces"]
            residue_types = f["residue_types"]
            assert coords.shape[1] == 20  # 2 * Chignolin n_res(10)
            assert target_forces.shape[1] == 20
            assert residue_types.shape[1] == 20
            assert f.attrs["representation"] == "ca_sc_explicit"
            assert int(f.attrs["n_beads_per_residue"]) == 2

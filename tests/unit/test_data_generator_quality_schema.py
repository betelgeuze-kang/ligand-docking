import h5py

from tools.generate_perturbed_data import DataGenerator


def test_data_generator_writes_quality_schema(tmp_path):
    out_dir = str(tmp_path)
    gen = DataGenerator(
        target="Chignolin",
        total_samples=12,
        noise=0.05,
        output_dir=out_dir,
        train_ratio=0.5,
        val_ratio=0.25,
        fast_mode=True,
    )
    ok = gen.generate()
    assert ok

    train_fp = tmp_path / "chignolin_airouter_train_data.h5"
    assert train_fp.exists()

    for split in ("train", "val", "test"):
        fp = tmp_path / f"chignolin_airouter_{split}_data.h5"
        if not fp.exists():
            continue
        with h5py.File(fp, "r") as f:
            n = int(f["coords"].shape[0])
            assert "quality_score" in f
            assert "reject_reason" in f
            assert "source" in f
            assert int(f["quality_score"].shape[0]) == n
            assert int(f["reject_reason"].shape[0]) == n
            assert int(f["source"].shape[0]) == n
            assert "source_tag" in f.attrs
            assert "reject_stats_json" in f.attrs

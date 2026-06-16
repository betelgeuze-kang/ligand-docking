from tools.accounting import build_product_gpu_return_post_regeneration_chain as mod


def _step_index(step_id: str, *, last: bool = False) -> int:
    step_ids = [command.rsplit("/", 1)[-1].removesuffix(".py") for command, _ in mod.POST_RETURN_STEPS]
    if not last:
        return step_ids.index(step_id)
    return len(step_ids) - 1 - list(reversed(step_ids)).index(step_id)


def test_post_regeneration_chain_reruns_receipt_after_force_derivation() -> None:
    first_receipt = _step_index("build_residual_force_gpu_worker_return_receipt")
    force_derivation = _step_index("build_residual_force_derivation_validation")
    final_receipt = _step_index("build_residual_force_gpu_worker_return_receipt", last=True)
    energy_validation = _step_index("build_residual_energy_force_label_validation")

    assert first_receipt < force_derivation < final_receipt < energy_validation

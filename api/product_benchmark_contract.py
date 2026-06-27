from __future__ import annotations

from fastapi import APIRouter

from betelgeuze_product.benchmark_contract import benchmark_contract_packet

router = APIRouter(prefix="/product", tags=["product-benchmark-contract"])


@router.get("/benchmark-contract")
async def get_product_benchmark_contract() -> dict:
    """Return the fail-closed scientific benchmark contract.

    The endpoint exposes required benchmark lanes and metrics for GUI/operator
    planning. It does not run any benchmark or promote a scientific claim.
    """

    return benchmark_contract_packet()

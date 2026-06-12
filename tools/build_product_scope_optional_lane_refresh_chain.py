"""Compatibility wrapper for tools.product.build_product_scope_optional_lane_refresh_chain."""
from tools.product.build_product_scope_optional_lane_refresh_chain import *  # noqa: F401,F403

try:
    from tools.product.build_product_scope_optional_lane_refresh_chain import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.build_product_scope_optional_lane_refresh_chain")
    raise SystemExit(_main())

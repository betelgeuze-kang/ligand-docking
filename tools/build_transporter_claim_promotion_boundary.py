"""Compatibility wrapper for tools.product.build_transporter_claim_promotion_boundary."""
from tools.product.build_transporter_claim_promotion_boundary import *  # noqa: F401,F403

try:
    from tools.product.build_transporter_claim_promotion_boundary import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.build_transporter_claim_promotion_boundary")
    raise SystemExit(_main())

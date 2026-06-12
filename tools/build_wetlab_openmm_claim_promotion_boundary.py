"""Compatibility wrapper for tools.wetlab.build_wetlab_openmm_claim_promotion_boundary."""
from tools.wetlab.build_wetlab_openmm_claim_promotion_boundary import *  # noqa: F401,F403

try:
    from tools.wetlab.build_wetlab_openmm_claim_promotion_boundary import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.wetlab.build_wetlab_openmm_claim_promotion_boundary")
    raise SystemExit(_main())

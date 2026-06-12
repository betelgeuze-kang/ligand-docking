"""Compatibility wrapper for tools.product.build_ca2_conflict_replacement_shortlist."""
from tools.product.build_ca2_conflict_replacement_shortlist import *  # noqa: F401,F403

try:
    from tools.product.build_ca2_conflict_replacement_shortlist import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.build_ca2_conflict_replacement_shortlist")
    raise SystemExit(_main())

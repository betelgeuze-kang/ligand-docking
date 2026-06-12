"""Compatibility wrapper for tools.product.run_ligand_htvs_nightly."""
from tools.product.run_ligand_htvs_nightly import *  # noqa: F401,F403

try:
    from tools.product.run_ligand_htvs_nightly import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.run_ligand_htvs_nightly")
    raise SystemExit(_main())

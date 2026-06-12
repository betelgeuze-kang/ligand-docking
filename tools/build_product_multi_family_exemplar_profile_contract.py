"""Compatibility wrapper for tools.product.build_product_multi_family_exemplar_profile_contract."""
from tools.product.build_product_multi_family_exemplar_profile_contract import *  # noqa: F401,F403

try:
    from tools.product.build_product_multi_family_exemplar_profile_contract import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.build_product_multi_family_exemplar_profile_contract")
    raise SystemExit(_main())

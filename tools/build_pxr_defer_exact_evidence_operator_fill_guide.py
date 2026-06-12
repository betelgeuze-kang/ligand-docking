"""Compatibility wrapper for tools.product.build_pxr_defer_exact_evidence_operator_fill_guide."""
from tools.product.build_pxr_defer_exact_evidence_operator_fill_guide import *  # noqa: F401,F403

try:
    from tools.product.build_pxr_defer_exact_evidence_operator_fill_guide import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.build_pxr_defer_exact_evidence_operator_fill_guide")
    raise SystemExit(_main())

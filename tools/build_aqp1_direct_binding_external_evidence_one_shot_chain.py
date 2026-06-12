"""Compatibility wrapper for tools.product.build_aqp1_direct_binding_external_evidence_one_shot_chain."""
from tools.product.build_aqp1_direct_binding_external_evidence_one_shot_chain import *  # noqa: F401,F403

try:
    from tools.product.build_aqp1_direct_binding_external_evidence_one_shot_chain import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.product.build_aqp1_direct_binding_external_evidence_one_shot_chain")
    raise SystemExit(_main())

"""Compatibility wrapper for tools.wetlab.build_wetlab_cathepsin_k_promoted_top4_review_packet."""
from tools.wetlab.build_wetlab_cathepsin_k_promoted_top4_review_packet import *  # noqa: F401,F403

try:
    from tools.wetlab.build_wetlab_cathepsin_k_promoted_top4_review_packet import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.wetlab.build_wetlab_cathepsin_k_promoted_top4_review_packet")
    raise SystemExit(_main())

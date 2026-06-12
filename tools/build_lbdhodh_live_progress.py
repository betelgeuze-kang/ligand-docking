"""Compatibility wrapper for tools.wetlab.build_lbdhodh_live_progress."""
from tools.wetlab.build_lbdhodh_live_progress import *  # noqa: F401,F403

try:
    from tools.wetlab.build_lbdhodh_live_progress import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.wetlab.build_lbdhodh_live_progress")
    raise SystemExit(_main())

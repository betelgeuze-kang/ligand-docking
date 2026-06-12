"""Compatibility wrapper for tools.wetlab.build_stk17b_result_summary."""
from tools.wetlab.build_stk17b_result_summary import *  # noqa: F401,F403

try:
    from tools.wetlab.build_stk17b_result_summary import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.wetlab.build_stk17b_result_summary")
    raise SystemExit(_main())

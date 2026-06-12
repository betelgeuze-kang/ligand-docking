"""Compatibility wrapper for tools.wetlab.build_wetlab_next3_gate_refresh."""
from tools.wetlab.build_wetlab_next3_gate_refresh import *  # noqa: F401,F403

try:
    from tools.wetlab.build_wetlab_next3_gate_refresh import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.wetlab.build_wetlab_next3_gate_refresh")
    raise SystemExit(_main())

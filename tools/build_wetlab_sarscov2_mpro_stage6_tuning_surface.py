"""Compatibility wrapper for tools.wetlab.build_wetlab_sarscov2_mpro_stage6_tuning_surface."""
from tools.wetlab.build_wetlab_sarscov2_mpro_stage6_tuning_surface import *  # noqa: F401,F403

try:
    from tools.wetlab.build_wetlab_sarscov2_mpro_stage6_tuning_surface import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.wetlab.build_wetlab_sarscov2_mpro_stage6_tuning_surface")
    raise SystemExit(_main())

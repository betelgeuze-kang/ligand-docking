"""Compatibility wrapper for tools.gpcr_replay.run_tier_alpha_adrb2_dispatch_smoke."""
from tools.gpcr_replay.run_tier_alpha_adrb2_dispatch_smoke import *  # noqa: F401,F403

try:
    from tools.gpcr_replay.run_tier_alpha_adrb2_dispatch_smoke import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.gpcr_replay.run_tier_alpha_adrb2_dispatch_smoke")
    raise SystemExit(_main())

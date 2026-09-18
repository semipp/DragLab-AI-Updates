JLRP DragLab v0.3.1 - Setup Scanner Retry Fix

- Fixes the R35 setup scanner getting stuck at 0-2 generic variables after startup.
- BeamNG bridge now resends a lightweight setup hello every second.
- As soon as the full JBeam variable table becomes available, JLRP receives it automatically without requiring a vehicle reset.
- Auto-Tune remains blocked until usable whitelisted tuning variables are present.
- Keeps BeamNG official 1/4-mile ET as the Auto-Tune KEEP/REVERT decision source.
- Wheel-slip telemetry remains excluded from tuning decisions.
- Updates dashboard/version branding to v0.3.1.

Target: restore the full R35 tuning-variable set before starting Auto-Tune.

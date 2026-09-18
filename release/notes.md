JLRP DragLab v0.3.4 - Safe One-Variable Auto-Tune Fix

- IMPORTANT: fixes BeamNG resetting omitted JBeam variables to defaults when Auto-Tune changed only one variable.
- Every Auto-Tune apply now resends the complete captured setup and overrides exactly one target variable.
- Revert and Restore Best Setup now restore the complete captured setup, not just managed candidate values.
- Auto-Tune will not enter WAITING FOR OFFICIAL PASS until the entire expected setup is verified after the reload.
- Baseline selection now uses the fastest BeamNG OFFICIAL pass matching the current vehicle + exact setup hash.
- This means the R35's stored 6.224 PB is used when its setup matches, instead of simply using the latest 6.247 pass.
- Keeps the v0.3.2/0.3.3 39-variable scanner and command-channel fixes.
- Wheel-slip telemetry remains excluded from tuning decisions.

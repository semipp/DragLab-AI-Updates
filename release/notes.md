JLRP DragLab v0.3.2 - Full Setup Payload Sync Fix

- Fixes the dashboard showing "Tunable variables: 39" while the Setup Scanner table remains empty.
- BeamNG bridge now forces the complete setup payload on retry instead of sending only a hash/status hello.
- Keeps the 1-second retry loop until the desktop receives the full JBeam tuning table.
- Setup Scanner placeholder now correctly says it is waiting for the full payload.
- Auto-Tune remains blocked until actual whitelisted variables are loaded.
- Official BeamNG timing remains the KEEP/REVERT decision source.
- Wheel-slip telemetry remains excluded from Auto-Tune decisions.

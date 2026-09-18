JLRP DragLab v0.3.0 - Auto-Tune MVP

- Adds START AUTO-TUNE, STOP and RESTORE BEST SETUP controls.
- Uses BeamNG official quarter-mile ET as the decision source.
- Changes one whitelisted tuning variable at a time.
- Starts with rear tyre pressure, then selected safe suspension settings.
- Faster official ET = KEEP; slower/noise-range = REVERT.
- Preserves the best known setup and Auto-Tune history locally.
- Ignores the current unreliable wheel-slip channel for tuning decisions.
- Rejects junk setup variables such as parked wheel radius/body offsets.
- Adds command rejection handling and a 20-second apply/verification timeout.

First test target: Nissan GTR R35 at West Coast, USA Sportsman Tree.

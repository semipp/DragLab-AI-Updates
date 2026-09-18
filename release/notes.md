JLRP DragLab v0.3.6 - Reset-Gated Closed-Loop Auto-Tune

- First live Auto-Tune test succeeded: rear tire pressure 28.0 -> 27.5 psi produced a new BeamNG OFFICIAL PB of 6.220 from the 6.224 baseline.
- Fixes the next tune being fired immediately after the official slip while the car is still at the finish line / RESET REQUIRED.
- After KEEP, JLRP now waits for you to reset/recover the vehicle, then automatically applies the next controlled experiment.
- After REVERT, JLRP also waits for reset/recover, restores the full best setup, verifies it, then continues.
- Verification timeout increased from 20 to 45 seconds for heavy modded vehicles.
- Keeps v0.3.5 reversed-bound validation and v0.3.4 full-setup preservation.
- BeamNG OFFICIAL quarter-mile ET remains the KEEP/REVERT judge.

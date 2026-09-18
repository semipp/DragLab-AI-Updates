JLRP DragLab v0.3.5 - Reversed JBeam Bounds Fix

- Fixes Auto-Tune failing with "$toe_FR: below minimum" while restoring or applying the full setup.
- Some BeamNG JBeam variables publish their two bounds in descending order, e.g. 1.02 -> 0.98.
- The bridge now normalizes those endpoints before validating a value.
- Keeps v0.3.4 full-setup preservation so changing rear tire pressure does not reset power, gearing, suspension, alignment, or other tune values.
- Keeps the fastest matching BeamNG OFFICIAL baseline logic, so the matching 6.224 PB remains the benchmark.
- Official BeamNG quarter-mile ET remains the KEEP/REVERT judge.

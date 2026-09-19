# JLRP DragLab v0.3.14

## Stage 3 — post-gearing chassis refinement

Adds a new controlled Auto-Tune stage after the completed Stage 2 sweep.

- Stage 3 starts **only when START AUTO-TUNE is pressed after Stage 2 is complete**.
- Uses the currently verified Auto-Tune best OFFICIAL result and its complete captured setup as the Stage 3 foundation.
- For the current R35 session that foundation is **6.101 OFFICIAL @ 238.7 mph** with **2nd gear 1.435**.
- Archives the completed Stage 2 candidate states before Stage 3 replaces the active candidate list.
- Preserves the existing decision history and records stage=3 on new decisions.
- Keeps the historical baselineRunId unchanged.
- Stage 3 tests only performance-relevant chassis variables, one at a time:
  - rear tyre pressure
  - rear anti-roll spring rate
  - rear spring rate
  - front rebound damping
  - front bump damping
- Uses the existing strict KEEP rule: BeamNG OFFICIAL quarter-mile ET must improve by more than **0.003 s**.
- Every apply/revert still sends and verifies the **FULL captured setup**.
- Existing v0.3.13 completed-PB promotion, v0.3.12 OFFICIAL recovery, and v0.3.10 player-vehicle routing remain intact.

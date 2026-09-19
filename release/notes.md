# JLRP DragLab v0.3.11

## OFFICIAL PB foundation promotion

This release corrects the stored Stage 2 baseline for an existing v0.3.10 session **without deleting or rebasing run history**.

- Before an unstarted Stage 2 resumes, JLRP checks the current player vehicle's saved runs.
- Only **BeamNG OFFICIAL** runs with a **complete captured setup matching the live scanner count** are eligible.
- The fastest eligible run becomes `bestRunId`, `bestEt`, `bestSetup`, and the Stage 2 baseline.
- The migration is allowed only when Stage 2 is at candidate index 0 with no Stage 2 decision history or pending experiment.
- Once a normal Stage 2 foundation exists, the migration is permanently marked complete so later tuning progress is never rewritten.
- **Restore Best Setup**, **Start Auto-Tune**, and the Auto-Tune status path all use the promoted PB.
- Full captured setup restore is preserved; Auto-Tune still changes one variable at a time and BeamNG OFFICIAL quarter-mile ET remains the KEEP/REVERT judge.
- v0.3.10 player-vehicle routing remains unchanged.

For the current Nissan GTR R35 data this promotes the recorded **6.207 OFFICIAL** PB and its complete 39-variable setup.

# JLRP DragLab v0.3.9

## Stage 2 foundation continuity fix

v0.3.8 could begin Stage 2 from whatever setup happened to be live when **Start Auto-Tune** was pressed. That meant Stage 2 could accidentally lose the Stage 1 gains.

v0.3.9 fixes this properly:

- Detects an affected v0.3.8 Stage 2 session automatically.
- Finds the fastest **BeamNG OFFICIAL** run from before Stage 2 began.
- Restores that complete Stage 1 setup, not just a few individual values.
- Discards the invalid v0.3.8 Stage 2 KEEP/REVERT history because those tests were made on the wrong foundation.
- Restarts Stage 2 from candidate #1 on the proven Stage 1 best.
- Future Stage 1 → Stage 2 handoffs always restore and verify the Stage 1 best first.
- If JLRP is restarted during Stage 2, it restores the current Stage 2 best before resuming.
- Private Run Sync now exposes whether the Stage 2 foundation has been repaired.

For the current R35 session, this is intended to recover the pre-Stage-2 foundation (27.5 psi rear tyre / 18,000 N/m rear anti-roll) before Stage 2 testing restarts.

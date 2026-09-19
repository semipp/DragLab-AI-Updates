# JLRP DragLab v0.3.12

## Auto-Tune OFFICIAL decision recovery

Fixes the case where a BeamNG OFFICIAL pass is visible in JLRP but Auto-Tune remains stuck on **WAITING FOR OFFICIAL PASS**.

- Normalizes persisted Auto-Tune decision history back to a mutable ArrayList after JSON reload.
- Safely preserves an already-verified experiment that is waiting only for its OFFICIAL timeslip across a desktop restart/update.
- Recovers the **first matching OFFICIAL full-setup run recorded after the experiment started**, so a pass already made does not need to be repeated.
- Recovery requires the exact full setup expected for the one-variable experiment.
- Keeps the 6.207 PB foundation unchanged when a slower recovered pass is judged.
- Wraps the Auto-Tune judge so an Auto-Tune bookkeeping error can never again prevent a valid OFFICIAL pass from being saved/private-synced.
- Preserves all run history, Stage 2 progress, full-setup restore behavior, and v0.3.10 player-vehicle routing.

For the current R35 session, the saved **6.319 OFFICIAL** pass at front tyre **28.0 psi** will be recovered and judged against the **6.207** PB foundation. It should REVERT, not become the new best.

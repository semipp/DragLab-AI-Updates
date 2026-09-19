# JLRP DragLab v0.3.13

## Completed-sweep OFFICIAL PB promotion

Keeps a finished Stage 2 sweep closed while allowing later normal repeat passes on the exact completed best setup to update Auto-Tune's stored best OFFICIAL result.

- Preserves the **COMPLETE** Auto-Tune state across an app update/restart.
- When Auto-Tune is COMPLETE and inactive, scans only **BeamNG OFFICIAL** runs for the same vehicle.
- Requires the candidate run to contain the same complete captured setup count and to match every stored best-setup value.
- Promotes only a strictly faster OFFICIAL ET on that exact completed best setup.
- Updates only `bestRunId`, `bestEt`, split references, and the identical `bestSetup` snapshot.
- Does **not** change `baselineRunId`, Stage 2 history, candidate states/index, run history, or reopen Auto-Tune.
- Existing v0.3.12 OFFICIAL-pass recovery, full-setup safety, and v0.3.10 player-vehicle routing remain intact.

For the current R35 session this is designed to promote the verified **6.101 OFFICIAL @ 238.7 mph** run on the completed setup with **2nd gear 1.435**, while leaving the Stage 2 sweep and historical baseline checkpoint untouched.

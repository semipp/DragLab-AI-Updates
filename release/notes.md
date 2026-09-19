# JLRP DragLab v0.3.10

## Player vehicle routing lock

BeamNG loads JLRP's vehicle telemetry extension in **every spawned vehicle**, including AI traffic. In v0.3.9, the desktop server accepted whichever vehicle packet arrived last, so a Simple Traffic Vehicle could overwrite the R35 dashboard state and even steal the outbound Auto-Tune command endpoint.

v0.3.10 fixes that at the routing layer:

- The GE-side bridge sends the authoritative **player 0 vehicle ID** twice per second.
- Desktop JLRP ignores telemetry, setup, run, and command-ack packets from non-player vehicles.
- Only the actual player vehicle can update Vehicle / Setup Scanner / Auto-Tune verification.
- Only the actual player vehicle's UDP endpoint can receive tune commands.
- AI traffic can remain enabled and spawned without contaminating JLRP.
- Player vehicle changes and respawns automatically reacquire the correct endpoint.
- Stage 2 foundation state from v0.3.9 is preserved; after updating, Start Auto-Tune restores the 6.212 Stage 1 foundation and resumes cleanly.

This directly fixes the Simple Traffic Vehicle / 2 tunable variables issue while the R35 is still open.

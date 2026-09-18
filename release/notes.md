JLRP DragLab v0.3.7 - Automatic Private Run Sync

- Stops the manual copy/paste workflow: JLRP can now automatically sync run data to the PRIVATE semipp/DragLab-AI GitHub repository.
- Adds a Setup Run Sync button to the dashboard. One-time setup installs/signs in GitHub CLI if needed; JLRP never stores a GitHub password or token.
- After setup, every official pass and Auto-Tune state change updates run-data/latest.json automatically.
- The private snapshot includes the latest run, best official run, current Auto-Tune experiment/decision, current 39-variable setup, and recent run history.
- ChatGPT can then read the private repo directly when James says "check the latest JLRP run".
- Official BeamNG slip capture now also stores Reaction Time, 330 ft and 1000 ft when exposed, in addition to 60 ft, 1/8 ET + MPH, and 1/4 ET + MPH.
- Telemetry sample spam is excluded from the GitHub snapshot to keep it compact; the full local runs.json remains unchanged.
- Keeps v0.3.6 reset-gated closed-loop Auto-Tune, v0.3.5 reversed-bound handling, and full-setup preservation.

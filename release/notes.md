# JLRP DragLab v0.3.8

## Stage 2 Auto-Tune

- Continues from a completed v0.3.7 Stage 1 sweep without throwing away the proven best setup.
- Stage 2 tests **front tyre pressure, front anti-roll, front spring rate, final drive, 1st gear, 2nd gear and 3rd gear**.
- Still changes **one variable at a time**.
- BeamNG's **official quarter-mile ET** remains the KEEP / REVERT judge.
- Full captured setup is preserved for every test and restored after a slower or neutral result.
- Stage and candidate state are included in Private Run Sync so ChatGPT can follow the tuning session remotely.

## Run Sync reliability

- Fixes the Windows PowerShell 5.1 first-login issue where `gh auth status` stderr could stop the setup script before browser authentication.
- No GitHub password or token is stored by JLRP.

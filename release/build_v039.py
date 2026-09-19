from pathlib import Path
import json, zipfile, shutil, sys, re

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
app = root / "app"

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"{label} not found")
    return text.replace(old, new, 1)

# Version metadata
p = app / "version.json"
d = json.loads(p.read_text())
d["version"] = "0.3.9"
d["bridgeVersion"] = "0.3.9"
p.write_text(json.dumps(d, indent=2) + "\n")

# Server
p = app / "DragLab_Server.ps1"
s = p.read_text().replace("0.3.8", "0.3.9")

# v0.3.9 remembers whether Stage 2 has been anchored to the real Stage 1 best.
s = replace_once(
    s,
    "    stage = 1\n    baselineRunId = $null",
    "    stage = 1\n    foundationRepaired = $false\n    baselineRunId = $null",
    "foundation state"
)

s = replace_once(
    s,
    "foreach ($name in @('stage','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision'))",
    "foreach ($name in @('stage','foundationRepaired','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision'))",
    "foundation persistence"
)

# Give foundation/resume restores their own visible phase instead of calling them a revert.
s = replace_once(
    s,
    """    $autoTune.phase = if ($mode -eq 'experiment') { 'APPLYING CHANGE' } elseif ($mode -eq 'restore') { 'RESTORING BEST' } else { 'REVERTING' }""",
    """    $autoTune.phase = if ($mode -eq 'experiment') { 'APPLYING CHANGE' } elseif ($mode -eq 'restore') { 'RESTORING BEST' } elseif ($mode -eq 'stage2-foundation') { 'RESTORING STAGE 1 FOUNDATION' } elseif ($mode -eq 'stage2-resume') { 'RESTORING STAGE 2 BEST' } else { 'REVERTING' }""",
    "foundation send phase"
)

# When a Stage 2 foundation/best restore is verified, immediately continue to the next clean experiment.
s = replace_once(
    s,
    """    } elseif ($mode -eq 'restore') {
        $autoTune.active = $false
        $autoTune.phase = 'BEST SETUP RESTORED'
        $autoTune.lastDecision = 'Best known Auto-Tune values have been restored and verified.'
    }
    Save-AutoTune""",
    """    } elseif ($mode -eq 'stage2-foundation') {
        $autoTune.phase = 'STAGE 2 FOUNDATION RESTORED'
        $autoTune.lastDecision = 'Correct Stage 1 best setup restored and verified. Restarting Stage 2 from a clean foundation.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
        return
    } elseif ($mode -eq 'stage2-resume') {
        $autoTune.phase = 'STAGE 2 BEST RESTORED'
        $autoTune.lastDecision = 'Stage 2 best setup restored and verified. Resuming the next controlled test.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
        return
    } elseif ($mode -eq 'restore') {
        $autoTune.active = $false
        $autoTune.phase = 'BEST SETUP RESTORED'
        $autoTune.lastDecision = 'Best known Auto-Tune values have been restored and verified.'
    }
    Save-AutoTune""",
    "foundation verification modes"
)

helpers = r'''
function Get-RunUtc($run) {
    foreach ($name in @('officialCapturedAt','completedAt','receivedAt','startedAt')) {
        try {
            if (($run.PSObject.Properties.Name -contains $name) -and $run.$name) {
                return [DateTime]::Parse([string]$run.$name).ToUniversalTime()
            }
        } catch {}
    }
    return $null
}

function Get-Stage1FoundationRun {
    # v0.3.8 could start Stage 2 from whatever setup happened to be live.
    # Recover the fastest OFFICIAL pass that existed before the first Stage 2 test.
    $historyItems = @($autoTune.history)
    if ($historyItems.Count -eq 0) { return $null }

    $firstStage2At = $null
    foreach ($h in $historyItems) {
        try {
            $dt = [DateTime]::Parse([string]$h.at).ToUniversalTime()
            if ($null -eq $firstStage2At -or $dt -lt $firstStage2At) { $firstStage2At = $dt }
        } catch {}
    }
    if ($null -eq $firstStage2At) { return $null }

    $eligible = New-Object System.Collections.ArrayList
    foreach ($r in @($runs)) {
        if ([string]$r.timingSource -ne 'beamng-official') { continue }
        if ($null -eq $r.setup -or @($r.setup).Count -eq 0) { continue }
        if ($state.vehicleKey -and $r.vehicleKey -and ([string]$state.vehicleKey -ne [string]$r.vehicleKey)) { continue }
        $runUtc = Get-RunUtc $r
        if ($null -eq $runUtc -or $runUtc -ge $firstStage2At) { continue }
        [void]$eligible.Add($r)
    }
    if ($eligible.Count -eq 0) { return $null }
    return @($eligible | Sort-Object { [double]$_.et })[0]
}

function Begin-Stage2FromFoundation($foundationRun, [string]$reason) {
    if ($null -eq $foundationRun) { throw 'Could not recover the Stage 1 best run.' }
    if ($null -eq $foundationRun.setup -or @($foundationRun.setup).Count -eq 0) { throw 'Stage 1 foundation setup is empty.' }

    $candidates = @(Get-AutoTuneCandidates $foundationRun.setup 2)
    if ($candidates.Count -eq 0) { throw 'No Stage 2 tuning candidates were found.' }

    $autoTune.active = $true
    $autoTune.stage = 2
    $autoTune.foundationRepaired = $true
    $autoTune.phase = 'RESTORING STAGE 1 FOUNDATION'
    $autoTune.baselineRunId = $foundationRun.id
    $autoTune.bestRunId = $foundationRun.id
    $autoTune.bestEt = [double]$foundationRun.et
    try { $autoTune.bestSixty = [double]$foundationRun.sixty } catch { $autoTune.bestSixty = $null }
    try { $autoTune.bestEighth = [double]$foundationRun.eighth } catch { $autoTune.bestEighth = $null }
    $autoTune.bestSetup = @($foundationRun.setup)
    $autoTune.candidateStates = @($candidates)
    $autoTune.candidateIndex = 0
    $autoTune.currentExperiment = $null
    $autoTune.pendingApply = $null
    $autoTune.history = New-Object System.Collections.ArrayList
    $autoTune.lastError = $null
    $autoTune.lastDecision = $reason
    Save-AutoTune

    $vals = Convert-SetupToValues $autoTune.bestSetup $null $null
    if ($vals.PSObject.Properties.Count -eq 0) { throw 'Stage 1 foundation values are empty.' }
    if (Test-SetupMatchesValues $state.setup $vals) {
        $autoTune.phase = 'STAGE 2 FOUNDATION RESTORED'
        $autoTune.lastDecision = 'Correct Stage 1 best setup already matches the car. Starting Stage 2 from a clean foundation.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
    } else {
        Send-AutoTuneValues $vals 'stage2-foundation' 'Restoring the proven Stage 1 best setup before Stage 2 restarts.'
    }
}

function Resume-Stage2FromBest {
    if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0) { throw 'No Stage 2 best setup is available to resume.' }
    $count = @($autoTune.candidateStates).Count
    if ($count -eq 0) {
        $autoTune.candidateStates = @(Get-AutoTuneCandidates $autoTune.bestSetup 2)
        $autoTune.candidateIndex = 0
        $count = @($autoTune.candidateStates).Count
    }
    if ($count -eq 0) { throw 'No Stage 2 tuning candidates were found.' }
    if ([int]$autoTune.candidateIndex -ge $count) { throw 'Stage 2 Auto-Tune is already complete. Best setup is preserved.' }

    $autoTune.active = $true
    $autoTune.stage = 2
    $autoTune.currentExperiment = $null
    $autoTune.pendingApply = $null
    $autoTune.lastError = $null
    $autoTune.lastDecision = 'Restoring the Stage 2 best setup before resuming the next controlled test.'
    Save-AutoTune

    $vals = Convert-SetupToValues $autoTune.bestSetup $null $null
    if ($vals.PSObject.Properties.Count -eq 0) { throw 'Stage 2 best setup values are empty.' }
    if (Test-SetupMatchesValues $state.setup $vals) {
        $autoTune.phase = 'STAGE 2 BEST RESTORED'
        Save-AutoTune
        Start-NextAutoTuneExperiment
    } else {
        Send-AutoTuneValues $vals 'stage2-resume' 'Restoring the Stage 2 best setup before resuming.'
    }
}
'''

marker = "function Start-AutoTune {"
idx = s.find(marker)
if idx < 0:
    raise RuntimeError("Start-AutoTune marker not found")
s = s[:idx] + helpers + "\n" + s[idx:]

start_func = r'''function Start-AutoTune {
    if ($autoTune.active) { return }
    if ($runs.Count -lt 1) { throw 'Make one baseline pass first.' }

    $existingCount = @($autoTune.candidateStates).Count
    $stageNow = [int]$autoTune.stage

    # Clean Stage 1 -> Stage 2 handoff: never use the current live setup as the new baseline.
    if ($stageNow -eq 1 -and $existingCount -gt 0 -and [int]$autoTune.candidateIndex -ge $existingCount) {
        if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0 -or $null -eq $autoTune.bestEt) {
            throw 'Stage 1 completed but its best setup could not be recovered.'
        }
        $foundation = [pscustomobject]@{
            id=$autoTune.bestRunId; et=$autoTune.bestEt; sixty=$autoTune.bestSixty; eighth=$autoTune.bestEighth;
            setup=@($autoTune.bestSetup)
        }
        Begin-Stage2FromFoundation $foundation 'Stage 1 complete. Restoring the proven Stage 1 best before Stage 2 starts.'
        return
    }

    if ($stageNow -eq 2) {
        # Migration repair for v0.3.8: its Stage 2 history was generated from the wrong live foundation.
        if (-not [bool]$autoTune.foundationRepaired) {
            $foundation = Get-Stage1FoundationRun
            if ($null -eq $foundation) {
                throw 'v0.3.9 could not automatically recover the pre-Stage-2 foundation. Do not continue tuning until the Stage 1 best setup is restored.'
            }
            Begin-Stage2FromFoundation $foundation 'v0.3.9 detected the v0.3.8 foundation bug. Invalid Stage 2 decisions were discarded; restoring the fastest OFFICIAL pre-Stage-2 setup and restarting Stage 2 cleanly.'
            return
        }

        Resume-Stage2FromBest
        return
    }

    # Fresh Stage 1 session: lock an OFFICIAL run that matches the exact live setup.
    $baseline = $null
    $eligible = New-Object System.Collections.ArrayList
    foreach ($r in @($runs)) {
        if ([string]$r.timingSource -ne 'beamng-official') { continue }
        if ($null -eq $r.setup -or @($r.setup).Count -eq 0) { continue }
        if ($state.vehicleKey -and $r.vehicleKey -and ([string]$state.vehicleKey -ne [string]$r.vehicleKey)) { continue }
        if ($state.setupHash -and $r.setupHash -and ([string]$state.setupHash -ne [string]$r.setupHash)) { continue }
        [void]$eligible.Add($r)
    }
    if ($eligible.Count -gt 0) {
        $baseline = @($eligible | Sort-Object { [double]$_.et })[0]
    }
    if ($null -eq $baseline) { throw 'Auto-Tune needs a BeamNG OFFICIAL baseline pass first.' }
    if ($state.vehicleKey -and $baseline.vehicleKey -and ([string]$state.vehicleKey -ne [string]$baseline.vehicleKey)) {
        throw 'The current vehicle does not match the latest OFFICIAL baseline. Make a fresh official pass in this car first.'
    }
    if ($state.setupHash -and $baseline.setupHash -and ([string]$state.setupHash -ne [string]$baseline.setupHash)) {
        throw 'The current setup changed after the baseline pass. Make a fresh OFFICIAL pass before starting Auto-Tune.'
    }

    $candidates = @(Get-AutoTuneCandidates $baseline.setup 1)
    if ($candidates.Count -eq 0) { throw 'No Stage 1 tuning candidates were found. Wait for the full setup scanner to load.' }

    $autoTune.active = $true
    $autoTune.stage = 1
    $autoTune.foundationRepaired = $false
    $autoTune.phase = 'STARTING'
    $autoTune.baselineRunId = $baseline.id
    $autoTune.bestRunId = $baseline.id
    $autoTune.bestEt = [double]$baseline.et
    try { $autoTune.bestSixty = [double]$baseline.sixty } catch { $autoTune.bestSixty=$null }
    try { $autoTune.bestEighth = [double]$baseline.eighth } catch { $autoTune.bestEighth=$null }
    $autoTune.bestSetup = @($baseline.setup)
    $autoTune.candidateStates = @($candidates)
    $autoTune.candidateIndex = 0
    $autoTune.currentExperiment = $null
    $autoTune.pendingApply = $null
    $autoTune.history = New-Object System.Collections.ArrayList
    $autoTune.lastDecision = ("Stage 1 baseline locked at {0:N3}s OFFICIAL. Starting launch chassis tuning one variable at a time." -f [double]$baseline.et)
    $autoTune.lastError = $null
    Save-AutoTune
    Start-NextAutoTuneExperiment
}'''

pattern = r"function Start-AutoTune \{.*?\n\}\n\nfunction Stop-AutoTune"
m = re.search(pattern, s, flags=re.S)
if not m:
    raise RuntimeError("Start-AutoTune function block not found")
s = s[:m.start()] + start_func + "\n\nfunction Stop-AutoTune" + s[m.end():]

# Expose repair state in status/private sync.
s = replace_once(
    s,
    """        active=[bool]$autoTune.active; phase=[string]$autoTune.phase; stage=[int]$autoTune.stage;
        stageName=$(if([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});""",
    """        active=[bool]$autoTune.active; phase=[string]$autoTune.phase; stage=[int]$autoTune.stage;
        foundationRepaired=[bool]$autoTune.foundationRepaired;
        stageName=$(if([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});""",
    "status foundation flag"
)

p.write_text(s)

# Dashboard text/version
p = app / "www" / "index.html"
h = p.read_text().replace("0.3.8", "0.3.9")
h = h.replace(
    "Stage 1 tunes launch/chassis. Stage 2 continues into front chassis and gearing. One variable at a time; BeamNG OFFICIAL quarter-mile ET decides KEEP or REVERT.",
    "Stage 1 tunes launch/chassis. Stage 2 is now anchored to the proven Stage 1 best before front chassis and gearing begin. One variable at a time; BeamNG OFFICIAL quarter-mile ET decides KEEP or REVERT."
)
p.write_text(h)

# Helpers are already auth-safe in v0.3.8; only bump visible version text if present.
for helper in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    p = app / helper
    t = p.read_text().replace("0.3.8", "0.3.9")
    p.write_text(t)

# Bridge version bump; behavior unchanged.
bridge_zip = app / "BeamNG_Mod" / "draglab_bridge_v0.2.zip"
work = Path("bridge_work_v039")
if work.exists():
    shutil.rmtree(work)
work.mkdir()
with zipfile.ZipFile(bridge_zip, "r") as z:
    z.extractall(work)

for fp in work.rglob("*"):
    if not fp.is_file():
        continue
    if fp.suffix.lower() in (".lua", ".json", ".txt"):
        txt = fp.read_text().replace("0.3.8", "0.3.9")
        fp.write_text(txt)

info = work / "info.json"
idata = json.loads(info.read_text())
idata["version"] = "0.3.9"
info.write_text(json.dumps(idata, indent=2) + "\n")

with zipfile.ZipFile(bridge_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for fp in sorted(work.rglob("*")):
        if fp.is_file():
            z.write(fp, fp.relative_to(work).as_posix())

print("Built JLRP v0.3.9 Stage 2 foundation continuity repair")

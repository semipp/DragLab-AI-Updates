from pathlib import Path
import json, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
app = root / "app"

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"{label} not found")
    return text.replace(old, new, 1)

p = app / "version.json"
d = json.loads(p.read_text())
d["version"] = "0.3.12"
d["bridgeVersion"] = "0.3.10"
p.write_text(json.dumps(d, indent=2) + "\n")

p = app / "DragLab_Server.ps1"
s = p.read_text().replace("0.3.11", "0.3.12")

old_load = r'''if (Test-Path -LiteralPath $AutoTuneFile -PathType Leaf) {
    try {
        $savedAuto = Get-Content -LiteralPath $AutoTuneFile -Raw | ConvertFrom-Json
        foreach ($name in @('stage','foundationRepaired','pbFoundationPromoted','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision')) {
            if ($savedAuto.PSObject.Properties.Name -contains $name) { $autoTune[$name] = $savedAuto.$name }
        }
        $autoTune.active = $false
        $autoTune.phase = 'IDLE'
        $autoTune.currentExperiment = $null
        $autoTune.pendingApply = $null
        $autoTune.lastError = $null
    } catch {}
}'''

new_load = r'''if (Test-Path -LiteralPath $AutoTuneFile -PathType Leaf) {
    try {
        $savedAuto = Get-Content -LiteralPath $AutoTuneFile -Raw | ConvertFrom-Json
        $resumeWaitingForOfficial = $false
        try {
            $resumeWaitingForOfficial = [bool]$savedAuto.active -and ([string]$savedAuto.phase -eq 'WAITING FOR OFFICIAL PASS') -and ($null -ne $savedAuto.currentExperiment)
        } catch {}

        foreach ($name in @('stage','foundationRepaired','pbFoundationPromoted','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision','active','phase','currentExperiment','pendingApply','lastError')) {
            if ($savedAuto.PSObject.Properties.Name -contains $name) { $autoTune[$name] = $savedAuto.$name }
        }

        # ConvertFrom-Json reloads history as a fixed Object[]; the judge needs a mutable
        # ArrayList because each OFFICIAL decision is appended with .Add().
        $historyList = New-Object System.Collections.ArrayList
        foreach ($h in @($autoTune.history)) {
            if ($null -ne $h) { [void]$historyList.Add($h) }
        }
        $autoTune.history = $historyList

        # A verified experiment waiting only for the OFFICIAL timeslip is safe to resume.
        # Other interrupted phases still restart idle so stale apply/revert commands cannot fire.
        if ($resumeWaitingForOfficial -and $null -ne $autoTune.currentExperiment) {
            $autoTune.active = $true
            $autoTune.phase = 'WAITING FOR OFFICIAL PASS'
            $autoTune.pendingApply = $null
            $autoTune.lastError = $null
        } else {
            $autoTune.active = $false
            $autoTune.phase = 'IDLE'
            $autoTune.currentExperiment = $null
            $autoTune.pendingApply = $null
            $autoTune.lastError = $null
        }
    } catch {}
}'''

s = replace_once(s, old_load, new_load, "mutable history / waiting-pass resume")

recover = r'''
function Recover-MissedOfficialAutoTunePass {
    # v0.3.11 could save the OFFICIAL run, then fail while appending the decision
    # to a fixed JSON-loaded history array. Recover exactly the first matching
    # OFFICIAL pass made after this verified experiment began.
    if (-not $autoTune.active) { return $false }
    if ([string]$autoTune.phase -ne 'WAITING FOR OFFICIAL PASS') { return $false }
    if ($null -eq $autoTune.currentExperiment) { return $false }

    $started = $null
    try { $started = [DateTime]::Parse([string]$autoTune.currentExperiment.startedAt).ToUniversalTime() } catch {}
    if ($null -eq $started) { return $false }

    $candidateName = [string]$autoTune.currentExperiment.candidateName
    if (-not $candidateName) { return $false }
    try { $candidateValue = [double]$autoTune.currentExperiment.to } catch { return $false }

    $expected = Convert-SetupToValues $autoTune.bestSetup $candidateName $candidateValue
    if ($expected.PSObject.Properties.Count -eq 0) { return $false }

    $vehicleKey = $null
    foreach ($baseRun in @($runs)) {
        if ([string]$baseRun.id -eq [string]$autoTune.bestRunId) {
            $vehicleKey = [string]$baseRun.vehicleKey
            break
        }
    }

    $eligible = New-Object System.Collections.ArrayList
    foreach ($r in @($runs)) {
        if ([string]$r.timingSource -ne 'beamng-official') { continue }
        if ($vehicleKey -and $r.vehicleKey -and ([string]$r.vehicleKey -ne $vehicleKey)) { continue }
        if ($null -eq $r.setup -or @($r.setup).Count -eq 0) { continue }

        $runUtc = Get-RunUtc $r
        if ($null -eq $runUtc -or $runUtc -le $started) { continue }
        if (-not (Test-SetupMatchesValues $r.setup $expected)) { continue }

        $alreadyJudged = $false
        foreach ($h in @($autoTune.history)) {
            if ($null -ne $h -and [string]$h.runId -eq [string]$r.id) { $alreadyJudged = $true; break }
        }
        if ($alreadyJudged) { continue }
        [void]$eligible.Add($r)
    }

    if ($eligible.Count -eq 0) { return $false }

    # Judge the first full pass after the experiment started. Later passes, if any,
    # must never skip over the one-variable-at-a-time decision boundary.
    $missed = @($eligible | Sort-Object { Get-RunUtc $_ })[0]
    On-OfficialRunFinalizedForAutoTune $missed
    return $true
}
'''

marker = "function Get-Stage1FoundationRun {"
idx = s.find(marker)
if idx < 0:
    raise RuntimeError("Get-Stage1FoundationRun marker not found")
s = s[:idx] + recover + "\n" + s[idx:]

old_status = r'''function Get-AutoTuneStatus {
    [void](Promote-FastestOfficialPbIfEligible)
    return [pscustomobject]@{'''

new_status = r'''function Get-AutoTuneStatus {
    try {
        [void](Recover-MissedOfficialAutoTunePass)
    } catch {
        $autoTune.active = $false
        $autoTune.phase = 'ERROR'
        $autoTune.lastError = "Missed OFFICIAL pass recovery failed: $($_.Exception.Message)"
        $autoTune.lastDecision = 'AUTO-TUNE ERROR: the saved OFFICIAL pass could not be recovered safely. Do not make another pass until repaired.'
        Save-AutoTune
    }
    [void](Promote-FastestOfficialPbIfEligible)
    return [pscustomobject]@{'''

s = replace_once(s, old_status, new_status, "status missed-pass recovery")

old_official = r'''    Write-Host ("OFFICIAL SYNC  {0:N3} @ {1}  |  replaced DragLab ground ET {2:N3}" -f $et, $(if($run.officialMph){('{0:N1} mph' -f [double]$run.officialMph)}else{'telemetry mph'}), [double]$run.measuredEt) -ForegroundColor Cyan
    On-OfficialRunFinalizedForAutoTune $run
    Request-RunSync 'official-pass'
    return $true'''

new_official = r'''    Write-Host ("OFFICIAL SYNC  {0:N3} @ {1}  |  replaced DragLab ground ET {2:N3}" -f $et, $(if($run.officialMph){('{0:N1} mph' -f [double]$run.officialMph)}else{'telemetry mph'}), [double]$run.measuredEt) -ForegroundColor Cyan
    try {
        On-OfficialRunFinalizedForAutoTune $run
    } catch {
        # Never let Auto-Tune bookkeeping prevent a valid OFFICIAL pass from being
        # saved/synced. Stop safely and surface the exact judge error instead.
        $autoTune.active = $false
        $autoTune.phase = 'ERROR'
        $autoTune.lastError = "Auto-Tune OFFICIAL judge failed: $($_.Exception.Message)"
        $autoTune.lastDecision = 'AUTO-TUNE ERROR: the OFFICIAL pass was saved, but its tuning decision failed. Do not make another pass until repaired.'
        Save-AutoTune
        $state.lastError = $autoTune.lastError
    }
    Request-RunSync 'official-pass'
    return $true'''

s = replace_once(s, old_official, new_official, "official judge isolation")

p.write_text(s)

p = app / "www" / "index.html"
h = p.read_text().replace("0.3.11", "0.3.12")
h = h.replace(
    "Before an unstarted Stage 2 resumes, JLRP can promote the fastest verified OFFICIAL full-setup PB as its foundation; player-vehicle routing remains locked.",
    "Stage 2 uses the verified OFFICIAL PB foundation, safely resumes a verified experiment waiting for its timeslip, and recovers any saved OFFICIAL pass that was missed by the decision logger."
)
p.write_text(h)

for helper_name in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    hp = app / helper_name
    hp.write_text(hp.read_text().replace("0.3.11", "0.3.12"))

print("Built JLRP v0.3.12 Auto-Tune OFFICIAL decision recovery")

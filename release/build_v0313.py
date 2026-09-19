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
d["version"] = "0.3.13"
d["bridgeVersion"] = "0.3.10"
p.write_text(json.dumps(d, indent=2) + "\n")

p = app / "DragLab_Server.ps1"
s = p.read_text().replace("0.3.12", "0.3.13")

old_load = r'''if (Test-Path -LiteralPath $AutoTuneFile -PathType Leaf) {
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

new_load = r'''if (Test-Path -LiteralPath $AutoTuneFile -PathType Leaf) {
    try {
        $savedAuto = Get-Content -LiteralPath $AutoTuneFile -Raw | ConvertFrom-Json
        $resumeWaitingForOfficial = $false
        $resumeComplete = $false
        try {
            $resumeWaitingForOfficial = [bool]$savedAuto.active -and ([string]$savedAuto.phase -eq 'WAITING FOR OFFICIAL PASS') -and ($null -ne $savedAuto.currentExperiment)
            $resumeComplete = (-not [bool]$savedAuto.active) -and ([string]$savedAuto.phase -eq 'COMPLETE') -and ($null -eq $savedAuto.currentExperiment) -and ($null -eq $savedAuto.pendingApply)
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
        # COMPLETE is also a terminal/safe state and must survive an app update/restart.
        # Other interrupted phases still restart idle so stale apply/revert commands cannot fire.
        if ($resumeWaitingForOfficial -and $null -ne $autoTune.currentExperiment) {
            $autoTune.active = $true
            $autoTune.phase = 'WAITING FOR OFFICIAL PASS'
            $autoTune.pendingApply = $null
            $autoTune.lastError = $null
        } elseif ($resumeComplete) {
            $autoTune.active = $false
            $autoTune.phase = 'COMPLETE'
            $autoTune.currentExperiment = $null
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

s = replace_once(s, old_load, new_load, "preserve COMPLETE across restart")

promote_completed = r'''
function Promote-CompletedAutoTunePbIfEligible {
    # After a sweep is COMPLETE, normal repeat passes on the exact preserved best
    # setup may establish a faster OFFICIAL PB. Promote only that result pointer/ET.
    # Never reopen Stage 2, rewrite history, reset candidates, or rebase baselineRunId.
    if ([bool]$autoTune.active) { return $false }
    if ([string]$autoTune.phase -ne 'COMPLETE') { return $false }
    if ($null -ne $autoTune.currentExperiment -or $null -ne $autoTune.pendingApply) { return $false }
    if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0) { return $false }

    $expectedCount = @($autoTune.bestSetup).Count
    $expectedValues = [ordered]@{}
    foreach ($item in @($autoTune.bestSetup)) {
        if ($null -eq $item) { return $false }
        $name = [string]$item.name
        if (-not $name) { return $false }
        try { $expectedValues[$name] = [double]$item.value } catch { return $false }
    }
    if ($expectedValues.Count -ne $expectedCount) { return $false }
    $expected = [pscustomobject]$expectedValues

    # Anchor vehicle identity to the existing Auto-Tune best run. If that run cannot
    # be found, do nothing rather than risk promoting a different vehicle's pass.
    $vehicleKey = $null
    foreach ($baseRun in @($runs)) {
        if ([string]$baseRun.id -eq [string]$autoTune.bestRunId) {
            $vehicleKey = [string]$baseRun.vehicleKey
            break
        }
    }
    if (-not $vehicleKey) { return $false }

    $eligible = New-Object System.Collections.ArrayList
    foreach ($r in @($runs)) {
        if ([string]$r.timingSource -ne 'beamng-official') { continue }
        if ([string]$r.vehicleKey -ne $vehicleKey) { continue }
        if ($null -eq $r.setup -or @($r.setup).Count -ne $expectedCount) { continue }
        if (-not (Test-SetupMatchesValues $r.setup $expected)) { continue }

        try { $runEt = [double]$r.et } catch { continue }
        if ($runEt -le 0) { continue }
        [void]$eligible.Add($r)
    }
    if ($eligible.Count -eq 0) { return $false }

    $pb = @($eligible | Sort-Object { [double]$_.et })[0]
    try {
        $pbEt = [double]$pb.et
        $oldEt = [double]$autoTune.bestEt
    } catch { return $false }

    # This is bookkeeping for repeated passes on an already-proven identical setup,
    # not a tuning KEEP/REVERT decision, so any strictly faster OFFICIAL ET is valid.
    if ($pbEt -ge $oldEt) { return $false }

    $autoTune.bestRunId = [string]$pb.id
    $autoTune.bestEt = $pbEt
    if ($null -ne $pb.sixty) { $autoTune.bestSixty = [double]$pb.sixty }
    if ($null -ne $pb.eighth) { $autoTune.bestEighth = [double]$pb.eighth }
    $autoTune.bestSetup = @($pb.setup)
    $autoTune.lastDecision = ("COMPLETE PB PROMOTED: exact completed best setup ran {0:N3}s, improving stored Auto-Tune best from {1:N3}s. Stage 2 history/candidates and baseline checkpoint preserved." -f $pbEt, $oldEt)
    Save-AutoTune
    return $true
}
'''

marker = "function Get-Stage1FoundationRun {"
idx = s.find(marker)
if idx < 0:
    raise RuntimeError("Get-Stage1FoundationRun marker not found")
s = s[:idx] + promote_completed + "\n" + s[idx:]

old_status_tail = r'''    [void](Promote-FastestOfficialPbIfEligible)
    return [pscustomobject]@{'''

new_status_tail = r'''    [void](Promote-FastestOfficialPbIfEligible)
    try {
        $completedPbPromoted = [bool](Promote-CompletedAutoTunePbIfEligible)
        if ($completedPbPromoted) { Request-RunSync 'autotune-complete-pb' }
    } catch {
        $state.lastError = "Completed Auto-Tune PB promotion failed: $($_.Exception.Message)"
    }
    return [pscustomobject]@{'''

s = replace_once(s, old_status_tail, new_status_tail, "status completed-PB promotion")

old_official_tail = r'''    }
    Request-RunSync 'official-pass'
    return $true'''

new_official_tail = r'''    }
    try {
        [void](Promote-CompletedAutoTunePbIfEligible)
    } catch {
        $state.lastError = "Completed Auto-Tune PB promotion failed: $($_.Exception.Message)"
    }
    Request-RunSync 'official-pass'
    return $true'''

s = replace_once(s, old_official_tail, new_official_tail, "official completed-PB promotion")

p.write_text(s)

p = app / "www" / "index.html"
h = p.read_text().replace("0.3.12", "0.3.13")
h = h.replace(
    "Stage 2 uses the verified OFFICIAL PB foundation, safely resumes a verified experiment waiting for its timeslip, and recovers any saved OFFICIAL pass that was missed by the decision logger.",
    "Stage 2 preserves its COMPLETE state across restarts and promotes a later faster OFFICIAL pass only when its full captured setup exactly matches the completed best setup."
)
p.write_text(h)

for helper_name in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    hp = app / helper_name
    hp.write_text(hp.read_text().replace("0.3.12", "0.3.13"))

print("Built JLRP v0.3.13 completed-sweep PB promotion")

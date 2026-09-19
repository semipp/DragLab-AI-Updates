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
d["version"] = "0.3.14"
d["bridgeVersion"] = "0.3.10"
p.write_text(json.dumps(d, indent=2) + "\n")

p = app / "DragLab_Server.ps1"
s = p.read_text().replace("0.3.13", "0.3.14")

s = replace_once(
    s,
    """    pbFoundationPromoted = $false
    baselineRunId = $null""",
    """    pbFoundationPromoted = $false
    stage2CandidateStates = @()
    stage2HistoryCount = 0
    stage2CompletedBestRunId = $null
    stage2CompletedBestEt = $null
    stage3BaselineRunId = $null
    stage3BaselineEt = $null
    baselineRunId = $null""",
    "Stage 3 archive/default fields"
)

s = replace_once(
    s,
    "foreach ($name in @('stage','foundationRepaired','pbFoundationPromoted','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision','active','phase','currentExperiment','pendingApply','lastError'))",
    "foreach ($name in @('stage','foundationRepaired','pbFoundationPromoted','stage2CandidateStates','stage2HistoryCount','stage2CompletedBestRunId','stage2CompletedBestEt','stage3BaselineRunId','stage3BaselineEt','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision','active','phase','currentExperiment','pendingApply','lastError'))",
    "persist Stage 3 fields"
)

s = replace_once(
    s,
    """            else { continue }
        } else {
            continue
        }

        $step = $null""",
    """            else { continue }
        } elseif ($stage -eq 3) {
            # Post-gearing chassis refinement. Revisit traction-sensitive variables
            # now that the proven gearing has changed, and add the previously
            # untouched rear anti-roll bar. Keep the list narrow and performance-relevant.
            if (($name -eq '$tirepressure_R') -or (($text -match 'rear') -and ($text -match 'tire|tyre') -and ($text -match 'pressure|psi'))) {
                $priority = 10; $direction = -1
            }
            elseif (($name -eq '$arb_spring_R') -or (($text -match 'rear') -and ($text -match 'anti[- ]?roll'))) {
                $priority = 20; $direction = -1
            }
            elseif (($name -eq '$spring_R') -or (($text -match 'rear') -and ($text -match 'spring') -and ($text -match 'rate') -and ($text -notmatch 'anti[- ]?roll'))) {
                $priority = 30; $direction = -1
            }
            elseif (($name -eq '$damp_rebound_F') -or (($text -match 'front') -and ($text -match 'rebound'))) {
                $priority = 40; $direction = -1
            }
            elseif (($name -eq '$damp_bump_F') -or (($text -match 'front') -and ($text -match 'bump|compression') -and ($text -match 'damp'))) {
                $priority = 50; $direction = -1
            }
            else { continue }
        } else {
            continue
        }

        $step = $null""",
    "Stage 3 candidate map"
)

s = replace_once(
    s,
    "$autoTune.phase = if ($mode -eq 'experiment') { 'APPLYING CHANGE' } elseif ($mode -eq 'restore') { 'RESTORING BEST' } elseif ($mode -eq 'stage2-foundation') { 'RESTORING STAGE 1 FOUNDATION' } elseif ($mode -eq 'stage2-resume') { 'RESTORING STAGE 2 BEST' } else { 'REVERTING' }",
    "$autoTune.phase = if ($mode -eq 'experiment') { 'APPLYING CHANGE' } elseif ($mode -eq 'restore') { 'RESTORING BEST' } elseif ($mode -eq 'stage2-foundation') { 'RESTORING STAGE 1 FOUNDATION' } elseif ($mode -eq 'stage2-resume') { 'RESTORING STAGE 2 BEST' } elseif ($mode -eq 'stage3-foundation') { 'RESTORING STAGE 3 FOUNDATION' } elseif ($mode -eq 'stage3-resume') { 'RESTORING STAGE 3 BEST' } else { 'REVERTING' }",
    "Stage 3 apply modes"
)

s = replace_once(
    s,
    """            $autoTune.lastDecision = if ([int]$autoTune.stage -eq 1) {
                'Stage 1 launch/chassis sweep is complete. Best setup preserved. Click START AUTO-TUNE again to begin Stage 2 chassis + gearing.'
            } else {
                'Stage 2 chassis + gearing sweep is complete. Best setup preserved.'
            }""",
    """            $stageDone = [int]$autoTune.stage
            $autoTune.lastDecision = if ($stageDone -eq 1) {
                'Stage 1 launch/chassis sweep is complete. Best setup preserved. Click START AUTO-TUNE again to begin Stage 2 chassis + gearing.'
            } elseif ($stageDone -eq 2) {
                'Stage 2 chassis + gearing sweep is complete. Best setup preserved. Click START AUTO-TUNE again to begin Stage 3 post-gearing chassis refinement.'
            } else {
                'Stage 3 post-gearing chassis refinement is complete. Best setup preserved.'
            }""",
    "Stage completion messages"
)

s = replace_once(
    s,
    """    } elseif ($mode -eq 'stage2-resume') {
        $autoTune.phase = 'STAGE 2 BEST RESTORED'
        $autoTune.lastDecision = 'Stage 2 best setup restored and verified. Resuming the next controlled test.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
        return
    } elseif ($mode -eq 'restore') {""",
    """    } elseif ($mode -eq 'stage2-resume') {
        $autoTune.phase = 'STAGE 2 BEST RESTORED'
        $autoTune.lastDecision = 'Stage 2 best setup restored and verified. Resuming the next controlled test.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
        return
    } elseif ($mode -eq 'stage3-foundation') {
        $autoTune.phase = 'STAGE 3 FOUNDATION RESTORED'
        $autoTune.lastDecision = 'Stage 3 foundation restored and FULL SETUP verified. Starting post-gearing chassis refinement.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
        return
    } elseif ($mode -eq 'stage3-resume') {
        $autoTune.phase = 'STAGE 3 BEST RESTORED'
        $autoTune.lastDecision = 'Stage 3 best setup restored and FULL SETUP verified. Resuming the next controlled test.'
        Save-AutoTune
        Start-NextAutoTuneExperiment
        return
    } elseif ($mode -eq 'restore') {""",
    "Stage 3 setup verification modes"
)

s = replace_once(
    s,
    "at=[DateTime]::UtcNow.ToString('o'); runId=$run.id; variable=$c.name; title=$c.title;",
    "at=[DateTime]::UtcNow.ToString('o'); stage=[int]$autoTune.stage; runId=$run.id; variable=$c.name; title=$c.title;",
    "record stage in Auto-Tune history"
)

stage3_functions = r'''
function Begin-Stage3FromBest([string]$reason) {
    if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0 -or $null -eq $autoTune.bestEt) {
        throw 'Stage 3 cannot start because the completed Stage 2 best setup/result is missing.'
    }

    $candidates = @(Get-AutoTuneCandidates $autoTune.bestSetup 3)
    if ($candidates.Count -eq 0) { throw 'No Stage 3 post-gearing chassis candidates were found.' }

    # Archive the completed Stage 2 candidate states before replacing the active list.
    # History remains one continuous append-only list; stage2HistoryCount marks the boundary.
    if (@($autoTune.stage2CandidateStates).Count -eq 0) {
        $autoTune.stage2CandidateStates = @($autoTune.candidateStates)
        $autoTune.stage2HistoryCount = @($autoTune.history).Count
        $autoTune.stage2CompletedBestRunId = [string]$autoTune.bestRunId
        try { $autoTune.stage2CompletedBestEt = [double]$autoTune.bestEt } catch { $autoTune.stage2CompletedBestEt = $null }
    }

    $autoTune.stage3BaselineRunId = [string]$autoTune.bestRunId
    $autoTune.stage3BaselineEt = [double]$autoTune.bestEt
    $autoTune.active = $true
    $autoTune.stage = 3
    $autoTune.phase = 'RESTORING STAGE 3 FOUNDATION'
    $autoTune.candidateStates = @($candidates)
    $autoTune.candidateIndex = 0
    $autoTune.currentExperiment = $null
    $autoTune.pendingApply = $null
    $autoTune.lastError = $null
    $autoTune.lastDecision = $reason
    Save-AutoTune

    # Stage 3 must begin from the exact FULL captured best setup; never from whatever
    # happens to be live after racing or a respawn.
    $vals = Convert-SetupToValues $autoTune.bestSetup $null $null
    if ($vals.PSObject.Properties.Count -eq 0) { throw 'Stage 3 best setup values are empty.' }

    if (Test-SetupMatchesValues $state.setup $vals) {
        $autoTune.phase = 'STAGE 3 FOUNDATION RESTORED'
        $autoTune.lastDecision = ("Stage 3 foundation already matches the car. Starting from {0:N3}s OFFICIAL with the full best setup." -f [double]$autoTune.bestEt)
        Save-AutoTune
        Start-NextAutoTuneExperiment
    } else {
        Send-AutoTuneValues $vals 'stage3-foundation' ("Restoring the full Stage 3 foundation ({0:N3}s OFFICIAL) before refinement starts." -f [double]$autoTune.bestEt)
    }
}

function Resume-Stage3FromBest {
    if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0) { throw 'No Stage 3 best setup is available to resume.' }

    $count = @($autoTune.candidateStates).Count
    if ($count -eq 0) {
        $autoTune.candidateStates = @(Get-AutoTuneCandidates $autoTune.bestSetup 3)
        $autoTune.candidateIndex = 0
        $count = @($autoTune.candidateStates).Count
    }
    if ($count -eq 0) { throw 'No Stage 3 tuning candidates were found.' }
    if ([int]$autoTune.candidateIndex -ge $count) { throw 'Stage 3 Auto-Tune is already complete. Best setup is preserved.' }

    $autoTune.active = $true
    $autoTune.stage = 3
    $autoTune.currentExperiment = $null
    $autoTune.pendingApply = $null
    $autoTune.lastError = $null
    $autoTune.lastDecision = 'Restoring the Stage 3 best setup before resuming the next controlled test.'
    Save-AutoTune

    $vals = Convert-SetupToValues $autoTune.bestSetup $null $null
    if ($vals.PSObject.Properties.Count -eq 0) { throw 'Stage 3 best setup values are empty.' }
    if (Test-SetupMatchesValues $state.setup $vals) {
        $autoTune.phase = 'STAGE 3 BEST RESTORED'
        Save-AutoTune
        Start-NextAutoTuneExperiment
    } else {
        Send-AutoTuneValues $vals 'stage3-resume' 'Restoring the Stage 3 best setup before resuming.'
    }
}
'''

marker = "function Start-AutoTune {"
idx = s.find(marker)
if idx < 0:
    raise RuntimeError("Start-AutoTune marker not found")
s = s[:idx] + stage3_functions + "\n" + s[idx:]

s = replace_once(
    s,
    """    [void](Promote-FastestOfficialPbIfEligible)

    $existingCount = @($autoTune.candidateStates).Count""",
    """    [void](Promote-FastestOfficialPbIfEligible)
    try { [void](Promote-CompletedAutoTunePbIfEligible) } catch {}

    $existingCount = @($autoTune.candidateStates).Count""",
    "promote completed exact-setup PB before Stage 3 start"
)

s = replace_once(
    s,
    """        Resume-Stage2FromBest
        return
    }

    # Fresh Stage 1 session: lock an OFFICIAL run that matches the exact live setup.""",
    """        # A completed Stage 2 sweep transitions to Stage 3 only when the user
        # explicitly presses START AUTO-TUNE. No Stage 2 state/history is reset.
        if ($existingCount -gt 0 -and [int]$autoTune.candidateIndex -ge $existingCount) {
            Begin-Stage3FromBest 'Stage 2 is complete. Archiving its candidate states and starting Stage 3 from the verified OFFICIAL best setup.'
            return
        }

        Resume-Stage2FromBest
        return
    }

    if ($stageNow -eq 3) {
        Resume-Stage3FromBest
        return
    }

    # Fresh Stage 1 session: lock an OFFICIAL run that matches the exact live setup.""",
    "Stage 2 complete to Stage 3 handoff"
)

s = replace_once(
    s,
    """        pbFoundationPromoted=[bool]$autoTune.pbFoundationPromoted;
        stageName=$(if([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});
        baselineRunId=$autoTune.baselineRunId;""",
    """        pbFoundationPromoted=[bool]$autoTune.pbFoundationPromoted;
        stage2HistoryCount=[int]$autoTune.stage2HistoryCount;
        stage2CompletedBestRunId=$autoTune.stage2CompletedBestRunId; stage2CompletedBestEt=$autoTune.stage2CompletedBestEt;
        stage3BaselineRunId=$autoTune.stage3BaselineRunId; stage3BaselineEt=$autoTune.stage3BaselineEt;
        stageName=$(if([int]$autoTune.stage -eq 3){'Post-Gearing Chassis Refinement'}elseif([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});
        baselineRunId=$autoTune.baselineRunId;""",
    "Stage 3 status metadata"
)

s = replace_once(
    s,
    """        candidates=@($autoTune.candidateStates); history=@($autoTune.history)""",
    """        candidates=@($autoTune.candidateStates); stage2Candidates=@($autoTune.stage2CandidateStates); history=@($autoTune.history)""",
    "expose archived Stage 2 candidates"
)

s = s.replace(
    "COMPLETE PB PROMOTED: exact completed best setup ran {0:N3}s, improving stored Auto-Tune best from {1:N3}s. Stage 2 history/candidates and baseline checkpoint preserved.",
    "COMPLETE PB PROMOTED: exact completed best setup ran {0:N3}s, improving stored Auto-Tune best from {1:N3}s. Completed-stage history/candidates and baseline checkpoint preserved."
)

p.write_text(s)

p = app / "www" / "index.html"
h = p.read_text().replace("0.3.13", "0.3.14")
h = h.replace(
    "Stage 2 preserves its COMPLETE state across restarts and promotes a later faster OFFICIAL pass only when its full captured setup exactly matches the completed best setup.",
    "Stage 3 starts only after completed Stage 2, restores the verified OFFICIAL best full setup, archives Stage 2 candidates, and refines rear tyre/ARB/spring plus front damping one variable at a time."
)
p.write_text(h)

for helper_name in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    hp = app / helper_name
    hp.write_text(hp.read_text().replace("0.3.13", "0.3.14"))

print("Built JLRP v0.3.14 Stage 3 post-gearing chassis refinement")

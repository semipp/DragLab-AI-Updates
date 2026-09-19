from pathlib import Path
import json, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
app = root / "app"

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"{label} not found")
    return text.replace(old, new, 1)

# Desktop version only. BeamNG bridge behavior remains v0.3.10.
p = app / "version.json"
d = json.loads(p.read_text())
d["version"] = "0.3.11"
d["bridgeVersion"] = "0.3.10"
p.write_text(json.dumps(d, indent=2) + "\n")

p = app / "DragLab_Server.ps1"
s = p.read_text().replace("0.3.10", "0.3.11")

s = replace_once(
    s,
    """    foundationRepaired = $false
    baselineRunId = $null""",
    """    foundationRepaired = $false
    pbFoundationPromoted = $false
    baselineRunId = $null""",
    "PB promotion state"
)

s = replace_once(
    s,
    "foreach ($name in @('stage','foundationRepaired','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision'))",
    "foreach ($name in @('stage','foundationRepaired','pbFoundationPromoted','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision'))",
    "PB promotion persistence"
)

# Any normal Stage 1 -> Stage 2 transition is already canonical and must not run this migration.
s = replace_once(
    s,
    """    $autoTune.foundationRepaired = $true
    $autoTune.phase = 'RESTORING STAGE 1 FOUNDATION'""",
    """    $autoTune.foundationRepaired = $true
    $autoTune.pbFoundationPromoted = $true
    $autoTune.phase = 'RESTORING STAGE 1 FOUNDATION'""",
    "new Stage 2 migration guard"
)

helper = r'''
function Get-FastestOfficialFullSetupPb {
    # The v0.3.11 migration is deliberately strict: same live player vehicle,
    # BeamNG OFFICIAL timing, and a complete setup matching the scanner count.
    if (-not $state.vehicleKey) { return $null }
    $expectedCount = [int]$state.tunableCount
    if ($expectedCount -le 0) { return $null }

    $eligible = New-Object System.Collections.ArrayList
    foreach ($r in @($runs)) {
        if ([string]$r.timingSource -ne 'beamng-official') { continue }
        if (-not $r.vehicleKey -or [string]$r.vehicleKey -ne [string]$state.vehicleKey) { continue }
        if ($null -eq $r.setup -or @($r.setup).Count -ne $expectedCount) { continue }
        try {
            $et = [double]$r.et
            if ($et -le 1.0 -or $et -ge 30.0) { continue }
        } catch { continue }
        [void]$eligible.Add($r)
    }
    if ($eligible.Count -eq 0) { return $null }
    return @($eligible | Sort-Object { [double]$_.et })[0]
}

function Promote-FastestOfficialPbIfEligible {
    # One-time migration for the v0.3.10 session that reached Stage 2 but had not
    # completed a valid Stage 2 decision. Never rewrite an in-progress tune.
    if ([bool]$autoTune.pbFoundationPromoted) { return $false }
    if ([int]$autoTune.stage -ne 2) { return $false }
    if (-not [bool]$autoTune.foundationRepaired) { return $false }
    if ([int]$autoTune.candidateIndex -ne 0) { return $false }
    if (@($autoTune.history).Count -ne 0) { return $false }
    if ($null -ne $autoTune.currentExperiment -or $null -ne $autoTune.pendingApply) { return $false }

    $pb = Get-FastestOfficialFullSetupPb
    if ($null -eq $pb) { return $false }

    $pbEt = [double]$pb.et
    if ($null -ne $autoTune.bestEt -and $pbEt -ge ([double]$autoTune.bestEt - 0.000001)) {
        $autoTune.pbFoundationPromoted = $true
        $autoTune.lastDecision = 'v0.3.11 checked the fastest OFFICIAL full-setup PB; the existing Stage 2 foundation is already current.'
        Save-AutoTune
        return $false
    }

    $candidates = @(Get-AutoTuneCandidates $pb.setup 2)
    if ($candidates.Count -eq 0) { return $false }

    $autoTune.baselineRunId = $pb.id
    $autoTune.bestRunId = $pb.id
    $autoTune.bestEt = $pbEt
    try { $autoTune.bestSixty = [double]$pb.sixty } catch { $autoTune.bestSixty = $null }
    try { $autoTune.bestEighth = [double]$pb.eighth } catch { $autoTune.bestEighth = $null }
    $autoTune.bestSetup = @($pb.setup)
    $autoTune.candidateStates = @($candidates)
    $autoTune.candidateIndex = 0
    $autoTune.currentExperiment = $null
    $autoTune.pendingApply = $null
    $autoTune.phase = 'IDLE'
    $autoTune.lastError = $null
    $autoTune.pbFoundationPromoted = $true
    $autoTune.lastDecision = ("v0.3.11 promoted the fastest BeamNG OFFICIAL full-setup PB ({0:N3}s) to the Stage 2 foundation. Run history was preserved." -f $pbEt)
    Save-AutoTune
    return $true
}
'''

marker = "function Resume-Stage2FromBest {"
idx = s.find(marker)
if idx < 0:
    raise RuntimeError("Resume-Stage2FromBest marker not found")
s = s[:idx] + helper + "\n" + s[idx:]

s = replace_once(
    s,
    """function Start-AutoTune {
    if ($autoTune.active) { return }
    if ($runs.Count -lt 1) { throw 'Make one baseline pass first.' }""",
    """function Start-AutoTune {
    if ($autoTune.active) { return }
    if ($runs.Count -lt 1) { throw 'Make one baseline pass first.' }
    [void](Promote-FastestOfficialPbIfEligible)""",
    "Start Auto-Tune PB promotion"
)

s = replace_once(
    s,
    """function Restore-AutoTuneBest {
    if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0) { throw 'No Auto-Tune best setup has been captured yet.' }""",
    """function Restore-AutoTuneBest {
    [void](Promote-FastestOfficialPbIfEligible)
    if ($null -eq $autoTune.bestSetup -or @($autoTune.bestSetup).Count -eq 0) { throw 'No Auto-Tune best setup has been captured yet.' }""",
    "Restore Best PB promotion"
)

s = replace_once(
    s,
    """function Get-AutoTuneStatus {
    return [pscustomobject]@{""",
    """function Get-AutoTuneStatus {
    [void](Promote-FastestOfficialPbIfEligible)
    return [pscustomobject]@{""",
    "status PB promotion"
)

s = replace_once(
    s,
    """        foundationRepaired=[bool]$autoTune.foundationRepaired;
        stageName=$(if([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});""",
    """        foundationRepaired=[bool]$autoTune.foundationRepaired;
        pbFoundationPromoted=[bool]$autoTune.pbFoundationPromoted;
        stageName=$(if([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});""",
    "status PB promotion flag"
)

s = replace_once(
    s,
    """    $autoTune.stage = 1
    $autoTune.foundationRepaired = $false
    $autoTune.phase = 'STARTING'""",
    """    $autoTune.stage = 1
    $autoTune.foundationRepaired = $false
    $autoTune.pbFoundationPromoted = $false
    $autoTune.phase = 'STARTING'""",
    "fresh Stage 1 PB state"
)

p.write_text(s)

# Dashboard text/version. No BeamNG Lua behavior changes in this release.
p = app / "www" / "index.html"
h = p.read_text().replace("0.3.10", "0.3.11")
h = h.replace(
    "Stage 1 tunes launch/chassis. Stage 2 is anchored to the proven Stage 1 best, and JLRP now locks telemetry/tune commands to the actual player vehicle.",
    "Stage 1 tunes launch/chassis. Before an unstarted Stage 2 resumes, JLRP can promote the fastest verified OFFICIAL full-setup PB as its foundation; player-vehicle routing remains locked."
)
p.write_text(h)

for helper_name in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    hp = app / helper_name
    hp.write_text(hp.read_text().replace("0.3.10", "0.3.11"))

print("Built JLRP v0.3.11 OFFICIAL PB foundation promotion")

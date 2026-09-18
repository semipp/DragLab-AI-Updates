from pathlib import Path
import json, zipfile, shutil, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
app = root / "app"

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"{label} not found")
    return text.replace(old, new, 1)

p = app / "version.json"
d = json.loads(p.read_text())
d["version"] = "0.3.7"
d["bridgeVersion"] = "0.3.7"
p.write_text(json.dumps(d, indent=2) + "\n")

p = app / "DragLab_Server.ps1"
s = p.read_text().replace("v0.3.6", "v0.3.7")
s = s.replace("serverVersion = '0.3.0'", "serverVersion = '0.3.7'")
s = s.replace("version='0.3.0'", "version='0.3.7'")

s = replace_once(s,
"$AutoTuneFile = Join-Path $DataDir 'autotune.json'\n$UdpPort = 48220",
"""$AutoTuneFile = Join-Path $DataDir 'autotune.json'
$RunSyncConfigFile = Join-Path $DataDir 'run_sync.json'
$RunSyncStatusFile = Join-Path $DataDir 'run_sync_status.json'
$RunSyncSnapshotFile = Join-Path $DataDir 'run_sync_latest.json'
$RunSyncScript = Join-Path $Root 'Sync_JLRP_RunData.ps1'
$RunSyncSetupScript = Join-Path $Root 'Setup_JLRP_Run_Sync.ps1'
$UdpPort = 48220""",
"sync path insertion")

old = """function Save-Runs {
    try {
        $json = @($runs) | ConvertTo-Json -Depth 30
        [System.IO.File]::WriteAllText($RunsFile, $json, [System.Text.UTF8Encoding]::new($false))
    } catch {
        $state.lastError = "Save failed: $($_.Exception.Message)"
    }
}

function Normalize-Run($msg) {"""
new = r"""function Save-Runs {
    try {
        $json = @($runs) | ConvertTo-Json -Depth 30
        [System.IO.File]::WriteAllText($RunsFile, $json, [System.Text.UTF8Encoding]::new($false))
    } catch {
        $state.lastError = "Save failed: $($_.Exception.Message)"
    }
}

# v0.3.7 private run sync. No GitHub token is stored by JLRP; the helper uses
# the user's GitHub CLI login and writes only to the private semipp/DragLab-AI repo.
$runSyncConfig = [ordered]@{
    enabled = $false
    repo = 'semipp/DragLab-AI'
    path = 'run-data/latest.json'
}
if (Test-Path -LiteralPath $RunSyncConfigFile -PathType Leaf) {
    try {
        $loadedSync = Get-Content -LiteralPath $RunSyncConfigFile -Raw | ConvertFrom-Json
        if ($loadedSync.PSObject.Properties.Name -contains 'enabled') { $runSyncConfig.enabled = [bool]$loadedSync.enabled }
        if ($loadedSync.repo) { $runSyncConfig.repo = [string]$loadedSync.repo }
        if ($loadedSync.path) { $runSyncConfig.path = [string]$loadedSync.path }
    } catch {}
}
function Save-RunSyncConfig {
    try {
        [System.IO.File]::WriteAllText($RunSyncConfigFile, ($runSyncConfig | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
    } catch {}
}
Save-RunSyncConfig

function Convert-RunForSync($r) {
    if ($null -eq $r) { return $null }
    $o = [ordered]@{}
    foreach ($prop in $r.PSObject.Properties) {
        if ($prop.Name -eq 'samples') { continue }
        $o[$prop.Name] = $prop.Value
    }
    return [pscustomobject]$o
}

function Get-RunSyncStatus {
    $o = [ordered]@{
        configured = [bool]$runSyncConfig.enabled
        repo = [string]$runSyncConfig.repo
        path = [string]$runSyncConfig.path
        lastAttempt = $null
        lastSuccess = $null
        lastError = $null
    }
    if (Test-Path -LiteralPath $RunSyncStatusFile -PathType Leaf) {
        try {
            $saved = Get-Content -LiteralPath $RunSyncStatusFile -Raw | ConvertFrom-Json
            foreach ($name in @('lastAttempt','lastSuccess','lastError')) {
                if ($saved.PSObject.Properties.Name -contains $name) { $o[$name] = $saved.$name }
            }
        } catch {}
    }
    return [pscustomobject]$o
}

function Write-RunSyncSnapshot([string]$reason = 'state-change') {
    try {
        $latest = $null
        if ($runs.Count -gt 0) { $latest = Convert-RunForSync $runs[$runs.Count - 1] }
        $recent = New-Object System.Collections.ArrayList
        $start = [Math]::Max(0, $runs.Count - 30)
        for ($i = $start; $i -lt $runs.Count; $i++) { [void]$recent.Add((Convert-RunForSync $runs[$i])) }
        $best = $null
        $official = @($runs | Where-Object { $_.timingSource -eq 'beamng-official' -and $null -ne $_.et } | Sort-Object { [double]$_.et })
        if ($official.Count -gt 0) { $best = Convert-RunForSync $official[0] }

        $snapshot = [ordered]@{
            schemaVersion = 2
            appVersion = '0.3.7'
            updatedAt = [DateTime]::UtcNow.ToString('o')
            reason = $reason
            vehicle = [ordered]@{
                name = $state.vehicleName
                key = $state.vehicleKey
                status = $state.status
                tunableCount = $state.tunableCount
                setupHash = $state.setupHash
            }
            officialTiming = [ordered]@{
                syncStatus = $state.officialSyncStatus
                lastEvent = $state.officialLastEvent
                lastResult = $state.officialLastResult
            }
            latestRun = $latest
            bestOfficialRun = $best
            autoTune = $autoTune
            currentSetup = @($state.setup)
            recentRuns = @($recent)
        }
        [System.IO.File]::WriteAllText($RunSyncSnapshotFile, ($snapshot | ConvertTo-Json -Depth 40), [System.Text.UTF8Encoding]::new($false))
    } catch {
        try { $state.lastError = "Run sync snapshot failed: $($_.Exception.Message)" } catch {}
    }
}

function Request-RunSync([string]$reason = 'state-change') {
    Write-RunSyncSnapshot $reason
    if (-not [bool]$runSyncConfig.enabled) { return }
    if (-not (Test-Path -LiteralPath $RunSyncScript -PathType Leaf)) { return }
    try {
        $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$RunSyncScript,'-DataDir',$DataDir,'-DelayMs','900')
        Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WindowStyle Hidden | Out-Null
    } catch {}
}

function Normalize-Run($msg) {"""
s = replace_once(s, old, new, "run sync function insertion")

s = replace_once(s,
"""function Save-AutoTune {
    try {
        $json = $autoTune | ConvertTo-Json -Depth 30
        [System.IO.File]::WriteAllText($AutoTuneFile, $json, [System.Text.UTF8Encoding]::new($false))
    } catch {}
}""",
"""function Save-AutoTune {
    try {
        $json = $autoTune | ConvertTo-Json -Depth 30
        [System.IO.File]::WriteAllText($AutoTuneFile, $json, [System.Text.UTF8Encoding]::new($false))
    } catch {}
    Request-RunSync 'autotune-state'
}""",
"Save-AutoTune sync hook")

s = replace_once(s,
"""    if ($official.PSObject.Properties.Name -contains 'eighthMph' -and $null -ne $official.eighthMph) {
        try {
            $v = [double]$official.eighthMph
            if ($v -gt 20 -and $v -lt 500) {
                Add-OrSetProperty $run 'officialEighthMph' $v
                Add-OrSetProperty $run 'eighthMph' $v
            }
        } catch {}
    }

    $state.officialLastResult = [pscustomobject]@{et=$et; mph=$official.mph; sixty=$official.sixty; eighth=$official.eighth; event=$eventName; matchedRunId=$run.id}""",
"""    if ($official.PSObject.Properties.Name -contains 'eighthMph' -and $null -ne $official.eighthMph) {
        try {
            $v = [double]$official.eighthMph
            if ($v -gt 20 -and $v -lt 500) {
                Add-OrSetProperty $run 'officialEighthMph' $v
                Add-OrSetProperty $run 'eighthMph' $v
            }
        } catch {}
    }
    if ($official.PSObject.Properties.Name -contains 'threeThirty' -and $null -ne $official.threeThirty) {
        try {
            $v = [double]$official.threeThirty
            if ($v -gt 0.5 -and $v -lt 15) {
                Add-OrSetProperty $run 'officialThreeThirty' $v
                Add-OrSetProperty $run 'threeThirty' $v
            }
        } catch {}
    }
    if ($official.PSObject.Properties.Name -contains 'thousand' -and $null -ne $official.thousand) {
        try {
            $v = [double]$official.thousand
            if ($v -gt 1.0 -and $v -lt 30) {
                Add-OrSetProperty $run 'officialThousand' $v
                Add-OrSetProperty $run 'thousand' $v
            }
        } catch {}
    }
    if ($official.PSObject.Properties.Name -contains 'reaction' -and $null -ne $official.reaction) {
        try {
            $v = [double]$official.reaction
            if ($v -ge 0 -and $v -lt 10) {
                Add-OrSetProperty $run 'officialReaction' $v
                Add-OrSetProperty $run 'reaction' $v
            }
        } catch {}
    }

    $state.officialLastResult = [pscustomobject]@{et=$et; mph=$official.mph; reaction=$official.reaction; sixty=$official.sixty; threeThirty=$official.threeThirty; eighth=$official.eighth; thousand=$official.thousand; event=$eventName; matchedRunId=$run.id}""",
"official extra split storage")

s = replace_once(s,
"""    On-OfficialRunFinalizedForAutoTune $run
    return $true""",
"""    On-OfficialRunFinalizedForAutoTune $run
    Request-RunSync 'official-pass'
    return $true""",
"official sync trigger")

s = replace_once(s,
"""        fallbackCorrectionSec = [double]$config.fallbackCorrectionSec
        autoTune = (Get-AutoTuneStatus)
    }""",
"""        fallbackCorrectionSec = [double]$config.fallbackCorrectionSec
        autoTune = (Get-AutoTuneStatus)
        runSync = (Get-RunSyncStatus)
    }""",
"run sync status object")

s = replace_once(s,
"""        if ($path -eq '/api/autotune/status' -and $method -eq 'GET') { Send-Json $client (Get-AutoTuneStatus); return }
        if ($path -eq '/api/autotune/start' -and $method -eq 'POST') {""",
"""        if ($path -eq '/api/sync/status' -and $method -eq 'GET') { Send-Json $client (Get-RunSyncStatus); return }
        if ($path -eq '/api/sync/now' -and $method -eq 'POST') {
            Request-RunSync 'manual'
            Send-Json $client @{ok=$true;runSync=(Get-RunSyncStatus)}; return
        }
        if ($path -eq '/api/sync/setup' -and $method -eq 'POST') {
            if (-not (Test-Path -LiteralPath $RunSyncSetupScript -PathType Leaf)) { Send-Json $client @{error='Run Sync setup helper is missing.'} 400; return }
            try {
                $args = @('-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File',$RunSyncSetupScript,'-DataDir',$DataDir)
                Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WindowStyle Normal | Out-Null
                Send-Json $client @{ok=$true}; return
            } catch { Send-Json $client @{error=$_.Exception.Message} 400; return }
        }
        if ($path -eq '/api/autotune/status' -and $method -eq 'GET') { Send-Json $client (Get-AutoTuneStatus); return }
        if ($path -eq '/api/autotune/start' -and $method -eq 'POST') {""",
"sync API routes")

p.write_text(s)

p = app / "www" / "index.html"
h = p.read_text().replace("v0.3.6", "v0.3.7")
h = h.replace("Official Timing + Closed-Loop Auto-Tune", "Official Timing + Closed-Loop Auto-Tune + Private Run Sync")
h = replace_once(h,
'<div class="actions"><button class="btn" id="demoBtn">Diagnostic Test Pass</button><button class="btn" id="exportBtn">Export Runs</button><button class="btn" id="diagBtn">Export Diagnostics</button><button class="btn danger" id="clearBtn">Clear History</button></div>',
'<div class="actions"><button class="btn" id="demoBtn">Diagnostic Test Pass</button><button class="btn" id="exportBtn">Export Runs</button><button class="btn" id="diagBtn">Export Diagnostics</button><button class="btn" id="syncSetupBtn">Setup Run Sync</button><button class="btn danger" id="clearBtn">Clear History</button></div>',
"dashboard sync button")
h = replace_once(h,
"renderSetup(status.setup||[]);renderLast();}",
"const sy=status.runSync||{};const sb=$('syncSetupBtn');if(sb){sb.textContent=sy.configured?(sy.lastError?'Run Sync Error':'Run Sync ON'):'Setup Run Sync';}renderSetup(status.setup||[]);renderLast();}",
"dashboard sync status render")
h = replace_once(h,
"$('clearBtn').onclick=async()=>{if(!confirm('Delete every recorded DragLab pass on this PC?'))return;",
"""$('syncSetupBtn').onclick=async()=>{try{const sy=status?.runSync||{};if(sy.configured){await api('/api/sync/now',{method:'POST'});alert('Run Sync queued to the private DragLab-AI repo.');}else{await api('/api/sync/setup',{method:'POST'});alert('One-time GitHub setup opened in PowerShell. Complete it once, then Run Sync stays automatic.');}}catch(e){alert('Run Sync: '+e.message)}};
$('clearBtn').onclick=async()=>{if(!confirm('Delete every recorded DragLab pass on this PC?'))return;""",
"dashboard sync handler")
h = h.replace("JLRP_DragLab_v0.3.6_Runs.json", "JLRP_DragLab_v0.3.7_Runs.json")
h = h.replace("JLRP_DragLab_v0.3.6_Diagnostics.json", "JLRP_DragLab_v0.3.7_Diagnostics.json")
p.write_text(h)

sync_ps1 = r'''param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [int]$DelayMs = 900
)
$ErrorActionPreference = 'Stop'
$ConfigFile = Join-Path $DataDir 'run_sync.json'
$StatusFile = Join-Path $DataDir 'run_sync_status.json'
$SnapshotFile = Join-Path $DataDir 'run_sync_latest.json'
function Write-SyncStatus([string]$errorMessage = $null, [bool]$success = $false) {
    try {
        $old = $null
        if (Test-Path -LiteralPath $StatusFile -PathType Leaf) { try { $old = Get-Content -LiteralPath $StatusFile -Raw | ConvertFrom-Json } catch {} }
        $o = [ordered]@{
            lastAttempt = [DateTime]::UtcNow.ToString('o')
            lastSuccess = if ($success) { [DateTime]::UtcNow.ToString('o') } elseif ($old -and $old.lastSuccess) { $old.lastSuccess } else { $null }
            lastError = $errorMessage
        }
        [IO.File]::WriteAllText($StatusFile, ($o | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    } catch {}
}
function Find-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}
$hashBytes = [Text.Encoding]::UTF8.GetBytes($DataDir.ToLowerInvariant())
$sha1 = [Security.Cryptography.SHA1]::Create()
$mutexSuffix = ([BitConverter]::ToString($sha1.ComputeHash($hashBytes))).Replace('-','')
$mutex = New-Object Threading.Mutex($false, "Local\JLRP_RunSync_$mutexSuffix")
if (-not $mutex.WaitOne(0)) { exit 0 }
try {
    if ($DelayMs -gt 0) { Start-Sleep -Milliseconds $DelayMs }
    if (-not (Test-Path -LiteralPath $ConfigFile -PathType Leaf)) { exit 0 }
    if (-not (Test-Path -LiteralPath $SnapshotFile -PathType Leaf)) { exit 0 }
    $cfg = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
    if (-not [bool]$cfg.enabled) { exit 0 }
    $gh = Find-Gh
    if (-not $gh) { Write-SyncStatus 'GitHub CLI is not installed. Click Setup Run Sync in JLRP.' $false; exit 0 }
    & $gh auth status --hostname github.com *> $null
    if ($LASTEXITCODE -ne 0) { Write-SyncStatus 'GitHub CLI is not signed in. Click Setup Run Sync in JLRP.' $false; exit 0 }
    $repo = [string]$cfg.repo
    $remotePath = [string]$cfg.path
    if ([string]::IsNullOrWhiteSpace($repo) -or [string]::IsNullOrWhiteSpace($remotePath)) { Write-SyncStatus 'Run Sync configuration is incomplete.' $false; exit 0 }
    $snapshotText = Get-Content -LiteralPath $SnapshotFile -Raw
    $contentB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($snapshotText))
    $currentSha = $null
    try {
        $currentSha = (& $gh api "repos/$repo/contents/$remotePath" --jq '.sha' 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -ne 0) { $currentSha = $null }
    } catch { $currentSha = $null }
    $latest = $null
    try { $latest = $snapshotText | ConvertFrom-Json } catch {}
    $runLabel = if ($latest -and $latest.latestRun -and $latest.latestRun.et) { ('{0:N3}' -f [double]$latest.latestRun.et) } else { 'state' }
    $body = [ordered]@{ message = "JLRP auto sync $runLabel"; content = $contentB64; branch = 'main' }
    if ($currentSha) { $body.sha = [string]$currentSha }
    $response = ($body | ConvertTo-Json -Depth 6 -Compress) | & $gh api --method PUT "repos/$repo/contents/$remotePath" --input - 2>&1
    if ($LASTEXITCODE -ne 0) {
        $msg = ($response | Out-String).Trim()
        if ($msg.Length -gt 400) { $msg = $msg.Substring(0,400) }
        Write-SyncStatus ("GitHub upload failed: " + $msg) $false
        exit 0
    }
    Write-SyncStatus $null $true
} catch {
    Write-SyncStatus $_.Exception.Message $false
} finally {
    try { $mutex.ReleaseMutex() } catch {}
    try { $mutex.Dispose() } catch {}
}
'''
(app / "Sync_JLRP_RunData.ps1").write_text(sync_ps1)

setup_ps1 = r'''param([string]$DataDir = $null)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($DataDir)) { $DataDir = if ($env:DRAGLAB_DATA_DIR) { $env:DRAGLAB_DATA_DIR } else { Join-Path $Root 'data' } }
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
$ConfigFile = Join-Path $DataDir 'run_sync.json'
function Find-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}
Write-Host ''
Write-Host '========================================================' -ForegroundColor DarkGray
Write-Host '  James & Lucas Rosa Performance - Private Run Sync' -ForegroundColor Cyan
Write-Host '========================================================' -ForegroundColor DarkGray
Write-Host ''
Write-Host 'One-time setup. Game telemetry syncs only to PRIVATE repo semipp/DragLab-AI.' -ForegroundColor White
Write-Host 'JLRP does not store your GitHub password or token.' -ForegroundColor Green
Write-Host ''
$gh = Find-Gh
if (-not $gh) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'GitHub CLI is not installed and winget was not found.' }
    Write-Host 'Installing GitHub CLI...' -ForegroundColor Yellow
    & winget install --id GitHub.cli --exact --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI installation failed.' }
    $env:Path += ";$env:ProgramFiles\GitHub CLI"
    $gh = Find-Gh
    if (-not $gh) { throw 'GitHub CLI installed but could not be found. Reopen JLRP and run setup again.' }
}
& $gh auth status --hostname github.com *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'A browser sign-in will open. Sign in to GitHub account semipp.' -ForegroundColor Yellow
    & $gh auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) { throw 'GitHub sign-in was not completed.' }
}
Write-Host 'Checking private repository access...' -ForegroundColor Yellow
$repoText = & $gh repo view semipp/DragLab-AI --json nameWithOwner,isPrivate 2>&1
if ($LASTEXITCODE -ne 0) { throw ('Could not access semipp/DragLab-AI: ' + ($repoText | Out-String)) }
$repo = $repoText | ConvertFrom-Json
if (-not [bool]$repo.isPrivate) { throw 'Safety stop: semipp/DragLab-AI is not private.' }
$cfg = [ordered]@{ enabled=$true; repo='semipp/DragLab-AI'; path='run-data/latest.json'; configuredAt=[DateTime]::UtcNow.ToString('o') }
[IO.File]::WriteAllText($ConfigFile, ($cfg | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
Write-Host ''
Write-Host 'PRIVATE RUN SYNC ENABLED.' -ForegroundColor Green
Write-Host 'From now on, official passes and Auto-Tune state changes sync automatically.' -ForegroundColor Green
Write-Host 'In ChatGPT just say: check the latest JLRP run' -ForegroundColor Cyan
Write-Host ''
try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:48221/api/sync/now' -Method Post -TimeoutSec 3 | Out-Null
    Write-Host 'Initial sync queued.' -ForegroundColor Green
} catch {
    Write-Host 'The next JLRP state change will sync automatically.' -ForegroundColor Yellow
}
Write-Host ''
Write-Host 'You can close this window.' -ForegroundColor DarkGray
'''
(app / "Setup_JLRP_Run_Sync.ps1").write_text(setup_ps1)
(app / "Setup_JLRP_Run_Sync.bat").write_text('@echo off\npowershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup_JLRP_Run_Sync.ps1"\n')

bridge_zip = app / "BeamNG_Mod" / "draglab_bridge_v0.2.zip"
work = Path("bridge_work_v037")
if work.exists(): shutil.rmtree(work)
work.mkdir()
with zipfile.ZipFile(bridge_zip, "r") as z: z.extractall(work)

info = work / "info.json"
idata = json.loads(info.read_text()); idata["version"] = "0.3.7"; info.write_text(json.dumps(idata, indent=2) + "\n")

tele = work / "lua" / "vehicle" / "extensions" / "auto" / "draglabTelemetry.lua"
ts = tele.read_text()
for oldver in ("0.3.2","0.3.3","0.3.4","0.3.5","0.3.6"):
    ts = ts.replace(f"payload.version = '{oldver}'", "payload.version = '0.3.7'")
ts = ts.replace("JLRP DragLab v0.3.2 telemetry bridge loaded", "JLRP DragLab v0.3.7 telemetry bridge loaded")
tele.write_text(ts)

official = work / "lua" / "ge" / "extensions" / "draglabOfficialSync.lua"
os = official.read_text().replace("payload.version = '0.2.9'", "payload.version = '0.3.7'")
os = replace_once(os,
"""local TIME_IDS = {
  time60='sixty',
  time330='threeThirty',
  time18='eighth',
  time1000='thousand',
  time14='quarter'
}""",
"""local TIME_IDS = {
  reactiontime='reaction',
  time60='sixty',
  time330='threeThirty',
  time18='eighth',
  time1000='thousand',
  time14='quarter'
}""","reaction timer id")
os = replace_once(os,
"""  if field == 'sixty' then return n > 0.3 and n < 8 end
  if field == 'eighth' then return n > 1.0 and n < 25 end""",
"""  if field == 'reaction' then return n >= 0 and n < 10 end
  if field == 'sixty' then return n > 0.3 and n < 8 end
  if field == 'eighth' then return n > 1.0 and n < 25 end""","reaction sane time")
os = replace_once(os,
"""    quarter=nil, eighth=nil, sixty=nil, threeThirty=nil, thousand=nil,
    mph=nil, eighthMph=nil, score=0, support=0""",
"""    reaction=nil, quarter=nil, eighth=nil, sixty=nil, threeThirty=nil, thousand=nil,
    mph=nil, eighthMph=nil, score=0, support=0""","reaction output")
os = replace_once(os,
"  local fields = {'quarter','eighth','sixty','threeThirty','thousand','mph','eighthMph'}",
"  local fields = {'reaction','quarter','eighth','sixty','threeThirty','thousand','mph','eighthMph'}",
"aggregate fields")
os = replace_once(os,
"""  local merged = {
    quarter=aggregate.quarter,
    eighth=aggregate.eighth,
    sixty=aggregate.sixty,""",
"""  local merged = {
    reaction=aggregate.reaction,
    quarter=aggregate.quarter,
    eighth=aggregate.eighth,
    sixty=aggregate.sixty,""","merged reaction")
os = replace_once(os,
"""  return {
    et = slip.quarter.value,
    mph = slip.mph and slip.mph.value or nil,
    sixty = slip.sixty and slip.sixty.value or nil,
    eighth = slip.eighth and slip.eighth.value or nil,
    eighthMph = slip.eighthMph and slip.eighthMph.value or nil,""",
"""  return {
    et = slip.quarter.value,
    mph = slip.mph and slip.mph.value or nil,
    reaction = slip.reaction and slip.reaction.value or nil,
    sixty = slip.sixty and slip.sixty.value or nil,
    threeThirty = slip.threeThirty and slip.threeThirty.value or nil,
    eighth = slip.eighth and slip.eighth.value or nil,
    eighthMph = slip.eighthMph and slip.eighthMph.value or nil,
    thousand = slip.thousand and slip.thousand.value or nil,""","slip payload")
os = replace_once(os,
"""      quarter = slip.quarter and slip.quarter.path or nil,
      sixty = slip.sixty and slip.sixty.path or nil,
      eighth = slip.eighth and slip.eighth.path or nil,
      mph = slip.mph and slip.mph.path or nil,""",
"""      reaction = slip.reaction and slip.reaction.path or nil,
      quarter = slip.quarter and slip.quarter.path or nil,
      sixty = slip.sixty and slip.sixty.path or nil,
      threeThirty = slip.threeThirty and slip.threeThirty.path or nil,
      eighth = slip.eighth and slip.eighth.path or nil,
      thousand = slip.thousand and slip.thousand.path or nil,
      mph = slip.mph and slip.mph.path or nil,""","slip paths")
official.write_text(os)

with zipfile.ZipFile(bridge_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for fp in sorted(work.rglob("*")):
        if fp.is_file(): z.write(fp, fp.relative_to(work).as_posix())

print("Built JLRP v0.3.7 automatic private run sync patch")

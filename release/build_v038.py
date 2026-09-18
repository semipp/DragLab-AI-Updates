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
d["version"] = "0.3.8"
d["bridgeVersion"] = "0.3.8"
p.write_text(json.dumps(d, indent=2) + "\n")

# Server: Stage 2 Auto-Tune + version bump
p = app / "DragLab_Server.ps1"
s = p.read_text()
s = s.replace("0.3.7", "0.3.8")
s = s.replace("Add-OrSetProperty $payload 'version' '0.3.3'", "Add-OrSetProperty $payload 'version' '0.3.8'")

s = replace_once(
    s,
    "    phase = 'IDLE'\n    baselineRunId = $null",
    "    phase = 'IDLE'\n    stage = 1\n    baselineRunId = $null",
    "autotune stage state"
)

s = replace_once(
    s,
    "foreach ($name in @('baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision'))",
    "foreach ($name in @('stage','baselineRunId','bestRunId','bestEt','bestSixty','bestEighth','bestSetup','candidateStates','candidateIndex','history','lastDecision'))",
    "autotune stage persistence"
)

candidate_func = r'''function Get-AutoTuneCandidates($setup, [int]$stage = 1) {
    $list = New-Object System.Collections.ArrayList
    foreach ($v in @($setup)) {
        $name = [string]$v.name
        $title = [string]$v.title
        $cat = [string]$v.category
        $sub = [string]$v.subCategory
        $text = ($name + ' ' + $title + ' ' + $cat + ' ' + $sub).ToLowerInvariant()
        if ($text -match 'parked|bumper|body length|wheel radius|tire radius|tyre radius|pickup.*offset|reverse gear') { continue }

        $priority = 999
        $direction = -1

        if ($stage -eq 1) {
            if (($text -match 'rear') -and ($text -match 'tire|tyre') -and ($text -match 'pressure|psi')) { $priority = 10; $direction = -1 }
            elseif (($text -match 'rear') -and ($text -match 'rebound')) { $priority = 20; $direction = -1 }
            elseif (($text -match 'rear') -and ($text -match 'bump|compression') -and ($text -match 'damp')) { $priority = 30; $direction = -1 }
            elseif (($text -match 'rear') -and ($text -match 'spring') -and ($text -match 'rate')) { $priority = 40; $direction = -1 }
            elseif (($text -match 'front') -and ($text -match 'rebound')) { $priority = 50; $direction = -1 }
            elseif (($text -match 'front') -and ($text -match 'bump|compression') -and ($text -match 'damp')) { $priority = 60; $direction = -1 }
            else { continue }
        } elseif ($stage -eq 2) {
            if (($name -eq '$tirepressure_F') -or (($text -match 'front') -and ($text -match 'tire|tyre') -and ($text -match 'pressure|psi'))) {
                $priority = 10; $direction = -1
            }
            elseif (($name -eq '$arb_spring_F') -or (($text -match 'front') -and ($text -match 'anti[- ]?roll'))) {
                $priority = 20; $direction = -1
            }
            elseif (($name -eq '$spring_F') -or (($text -match 'front') -and ($text -match 'spring') -and ($text -match 'rate') -and ($text -notmatch 'anti[- ]?roll'))) {
                $priority = 30; $direction = -1
            }
            elseif (($name -eq '$finaldrive_F') -or ($text -match 'final drive')) {
                $priority = 40; $direction = -1
            }
            elseif (($name -eq '$gear_1') -or ($title -match '^1st gear ratio$')) {
                $priority = 50; $direction = -1
            }
            elseif (($name -eq '$gear_2') -or ($title -match '^2nd gear ratio$')) {
                $priority = 60; $direction = -1
            }
            elseif (($name -eq '$gear_3') -or ($title -match '^3rd gear ratio$')) {
                $priority = 70; $direction = -1
            }
            else { continue }
        } else {
            continue
        }

        $step = $null
        try { if ($null -ne $v.step) { $step = [Math]::Abs([double]$v.step) } } catch {}
        if ($null -eq $step -or $step -le 0) {
            if ($text -match 'pressure|psi') { $step = 0.5 }
            elseif ($text -match 'final drive') { $step = 0.01 }
            elseif ($text -match 'gear ratio') { $step = 0.05 }
            elseif ($text -match 'spring|damp|rebound|bump|anti[- ]?roll') { $step = 100.0 }
            else { $step = 0.1 }
        }

        $min = $null; $max = $null
        try { if ($null -ne $v.min) { $min = [double]$v.min } } catch {}
        try { if ($null -ne $v.max) { $max = [double]$v.max } } catch {}
        if ($null -ne $min -and $null -ne $max -and $min -gt $max) {
            $tmp = $min; $min = $max; $max = $tmp
        }

        [void]$list.Add([pscustomobject]@{
            name=$name; title=$(if($title){$title}else{$name}); unit=[string]$v.unit;
            stage=$stage; priority=$priority; initialDirection=$direction; step=$step; min=$min; max=$max;
            improvements=0; direction=$direction; downTried=$false; upTried=$false; complete=$false
        })
    }
    return @($list | Sort-Object priority,title)
}'''

pattern = r"function Get-AutoTuneCandidates\(\$setup\) \{.*?\n\}\n\nfunction Send-BeamCommand"
m = re.search(pattern, s, flags=re.S)
if not m:
    raise RuntimeError("Get-AutoTuneCandidates block not found")
s = s[:m.start()] + candidate_func + "\n\nfunction Send-BeamCommand" + s[m.end():]

s = replace_once(
    s,
    "            $autoTune.lastDecision = 'Safe v0.3 candidate sweep is complete. Best setup preserved.'",
    """            $autoTune.lastDecision = if ([int]$autoTune.stage -eq 1) {
                'Stage 1 launch/chassis sweep is complete. Best setup preserved. Click START AUTO-TUNE again to begin Stage 2 chassis + gearing.'
            } else {
                'Stage 2 chassis + gearing sweep is complete. Best setup preserved.'
            }""",
    "stage completion message"
)

s = replace_once(
    s,
    """    $candidates = @(Get-AutoTuneCandidates $baseline.setup)
    if ($candidates.Count -eq 0) { throw 'No safe v0.3 tuning candidates were found. Wait for the full setup scanner to load.' }
    $autoTune.active = $true""",
    """    $startStage = 1
    $existingCount = @($autoTune.candidateStates).Count
    if ([int]$autoTune.stage -eq 1 -and $existingCount -gt 0 -and [int]$autoTune.candidateIndex -ge $existingCount) {
        # v0.3.7 completed Stage 1. Continue from the preserved best setup into Stage 2.
        $startStage = 2
    } elseif ([int]$autoTune.stage -ge 2) {
        if ($existingCount -gt 0 -and [int]$autoTune.candidateIndex -ge $existingCount) {
            throw 'Stage 2 Auto-Tune is already complete. Best setup is preserved.'
        }
        $startStage = 2
    }

    $candidates = @(Get-AutoTuneCandidates $baseline.setup $startStage)
    if ($candidates.Count -eq 0) { throw ("No Stage {0} tuning candidates were found. Wait for the full setup scanner to load." -f $startStage) }
    $autoTune.active = $true
    $autoTune.stage = $startStage""",
    "stage selection"
)

s = replace_once(
    s,
    """    $autoTune.lastDecision = ("Baseline locked at {0:N3}s OFFICIAL. Starting one-variable-at-a-time tuning." -f [double]$baseline.et)""",
    """    $stageLabel = if ([int]$autoTune.stage -eq 2) { 'front chassis + gearing' } else { 'launch chassis' }
    $autoTune.lastDecision = ("Stage {0} baseline locked at {1:N3}s OFFICIAL. Starting {2} tuning one variable at a time." -f [int]$autoTune.stage,[double]$baseline.et,$stageLabel)""",
    "stage baseline message"
)

s = replace_once(
    s,
    """        token=$null; candidateName=$c.name; title=$c.title; unit=$c.unit;
        from=[double]$baseValue; to=[double]$target; direction=$direction;""",
    """        token=$null; stage=[int]$autoTune.stage; candidateName=$c.name; title=$c.title; unit=$c.unit;
        from=[double]$baseValue; to=[double]$target; direction=$direction;""",
    "experiment stage field"
)

s = replace_once(
    s,
    """        active=[bool]$autoTune.active; phase=[string]$autoTune.phase; baselineRunId=$autoTune.baselineRunId;""",
    """        active=[bool]$autoTune.active; phase=[string]$autoTune.phase; stage=[int]$autoTune.stage;
        stageName=$(if([int]$autoTune.stage -eq 2){'Front Chassis + Gearing'}else{'Launch Chassis'});
        baselineRunId=$autoTune.baselineRunId;""",
    "status stage fields"
)

p.write_text(s)

# Dashboard version + clearer Stage 2 wording.
p = app / "www" / "index.html"
h = p.read_text().replace("0.3.7", "0.3.8")
h = h.replace("JLRP Auto-Tune v0.3", "JLRP Auto-Tune v0.3.8")
h = h.replace(
    "One variable at a time. BeamNG OFFICIAL quarter-mile ET decides KEEP or REVERT. Wheel-slip is ignored as a tuning signal for now.",
    "Stage 1 tunes launch/chassis. Stage 2 continues into front chassis and gearing. One variable at a time; BeamNG OFFICIAL quarter-mile ET decides KEEP or REVERT."
)
p.write_text(h)

# Fix the Windows PowerShell 5.1 GitHub CLI auth-status stderr issue in both helpers.
for helper in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    p = app / helper
    t = p.read_text().replace("0.3.7", "0.3.8")
    auth_pattern = re.compile(r"(?m)^(\\s*)& \\$gh auth status --hostname github\\.com \\*> \\$null\\n\\1if \\(\\$LASTEXITCODE -ne 0\\) \\{")
    m = auth_pattern.search(t)
    if not m:
        raise RuntimeError(helper + " auth status not found")
    indent = m.group(1)
    replacement = (
        indent + "$oldEap = $ErrorActionPreference\\n" +
        indent + "$ErrorActionPreference = 'SilentlyContinue'\\n" +
        indent + "& $gh auth status --hostname github.com *> $null\\n" +
        indent + "$authExit = $LASTEXITCODE\\n" +
        indent + "$ErrorActionPreference = $oldEap\\n" +
        indent + "if ($authExit -ne 0) {"
    )
    t = t[:m.start()] + replacement + t[m.end():]
    p.write_text(t)

# Bridge version bump; functionality stays the same.
bridge_zip = app / "BeamNG_Mod" / "draglab_bridge_v0.2.zip"
work = Path("bridge_work_v038")
if work.exists():
    shutil.rmtree(work)
work.mkdir()
with zipfile.ZipFile(bridge_zip, "r") as z:
    z.extractall(work)

for fp in work.rglob("*"):
    if not fp.is_file():
        continue
    if fp.suffix.lower() in (".lua", ".json", ".txt"):
        txt = fp.read_text()
        txt = txt.replace("0.3.7", "0.3.8")
        fp.write_text(txt)

info = work / "info.json"
idata = json.loads(info.read_text())
idata["version"] = "0.3.8"
info.write_text(json.dumps(idata, indent=2) + "\n")

with zipfile.ZipFile(bridge_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for fp in sorted(work.rglob("*")):
        if fp.is_file():
            z.write(fp, fp.relative_to(work).as_posix())

print("Built JLRP v0.3.8 Stage 2 chassis + gearing Auto-Tune")

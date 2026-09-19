from pathlib import Path
import json, zipfile, shutil, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build")
app = root / "app"

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"{label} not found")
    return text.replace(old, new, 1)

# Version metadata
p = app / "version.json"
d = json.loads(p.read_text())
d["version"] = "0.3.10"
d["bridgeVersion"] = "0.3.10"
p.write_text(json.dumps(d, indent=2) + "\n")

# ---------------- Server: player-vehicle routing ----------------
p = app / "DragLab_Server.ps1"
s = p.read_text().replace("0.3.9", "0.3.10")

s = replace_once(
    s,
    """$script:beamRemote = $null
$script:beamRemoteSeenUtc = $null""",
    """$script:beamRemote = $null
$script:beamRemoteSeenUtc = $null
$script:playerVehicleId = $null
$script:playerVehicleSeenUtc = $null
$script:ignoredVehiclePackets = 0""",
    "player routing state"
)

s = replace_once(
    s,
    "function Handle-UdpMessage([string]$text) {",
    "function Handle-UdpMessage([string]$text, $senderRemote) {",
    "udp handler signature"
)

old_head = """        $msg = $text | ConvertFrom-Json
        $state.packetCount++
        $state.lastSeenUtc = [DateTime]::UtcNow.ToString('o')
        if (($msg.PSObject.Properties.Name -contains 'vehicleName') -and $null -ne $msg.vehicleName) { $state.vehicleName = $msg.vehicleName }
        if (($msg.PSObject.Properties.Name -contains 'vehicleKey') -and $null -ne $msg.vehicleKey) { $state.vehicleKey = $msg.vehicleKey }
        $state.lastMessageType = $msg.type
        $state.lastError = $null

        if ($msg.PSObject.Properties.Name -contains 'setup' -and $null -ne $msg.setup) {"""

new_head = """        $msg = $text | ConvertFrom-Json
        $state.packetCount++

        # The vehicle extension auto-loads in every BeamNG vehicle, including AI traffic.
        # The GE extension is authoritative about which object is the actual player car.
        if (($msg.PSObject.Properties.Name -contains 'playerVehicleId') -and $null -ne $msg.playerVehicleId) {
            $newPlayerId = [string]$msg.playerVehicleId
            if ($newPlayerId) {
                if ($null -eq $script:playerVehicleId -or [string]$script:playerVehicleId -ne $newPlayerId) {
                    $script:playerVehicleId = $newPlayerId
                    # A player vehicle change/respawn must reacquire the matching vehicle UDP endpoint.
                    $script:beamRemote = $null
                    $script:beamRemoteSeenUtc = $null
                }
                $script:playerVehicleSeenUtc = [DateTime]::UtcNow.ToString('o')
            }
        }

        if ($msg.type -eq 'player_vehicle_status') {
            return
        }

        $isVehiclePacket = (($msg.PSObject.Properties.Name -contains 'vehicleId') -and $null -ne $msg.vehicleId)
        if ($isVehiclePacket) {
            # Do not let traffic or parked AI cars steal dashboard state, setup verification,
            # pass recording, or the outbound tune command channel.
            if ($null -eq $script:playerVehicleId) {
                $script:ignoredVehiclePackets++
                return
            }
            if ([string]$msg.vehicleId -ne [string]$script:playerVehicleId) {
                $script:ignoredVehiclePackets++
                return
            }

            if ($null -ne $senderRemote) {
                $script:beamRemote = [System.Net.IPEndPoint]::new($senderRemote.Address, $senderRemote.Port)
                $script:beamRemoteSeenUtc = [DateTime]::UtcNow.ToString('o')
            }

            $state.lastSeenUtc = [DateTime]::UtcNow.ToString('o')
            if (($msg.PSObject.Properties.Name -contains 'vehicleName') -and $null -ne $msg.vehicleName) { $state.vehicleName = $msg.vehicleName }
            if (($msg.PSObject.Properties.Name -contains 'vehicleKey') -and $null -ne $msg.vehicleKey) { $state.vehicleKey = $msg.vehicleKey }
        }

        $state.lastMessageType = $msg.type
        $state.lastError = $null

        if ($msg.PSObject.Properties.Name -contains 'setup' -and $null -ne $msg.setup) {"""

s = replace_once(s, old_head, new_head, "player packet filter")

old_loop = """            $bytes = $udp.Receive([ref]$remote)
            $script:beamRemote = [System.Net.IPEndPoint]::new($remote.Address, $remote.Port)
            $script:beamRemoteSeenUtc = [DateTime]::UtcNow.ToString('o')
            $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            Handle-UdpMessage $text"""

new_loop = """            $bytes = $udp.Receive([ref]$remote)
            $senderRemote = [System.Net.IPEndPoint]::new($remote.Address, $remote.Port)
            $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            Handle-UdpMessage $text $senderRemote"""

s = replace_once(s, old_loop, new_loop, "main udp routing")

# Surface routing diagnostics.
s = replace_once(
    s,
    """        vehicleName = $state.vehicleName
        vehicleKey = $state.vehicleKey
        status = if ($connected) { $state.status } else { 'WAITING' }""",
    """        vehicleName = $state.vehicleName
        vehicleKey = $state.vehicleKey
        playerVehicleId = $script:playerVehicleId
        ignoredVehiclePackets = [int]$script:ignoredVehiclePackets
        status = if ($connected) { $state.status } else { 'WAITING' }""",
    "routing diagnostics status"
)

p.write_text(s)

# ---------------- Bridge: authoritative player ID heartbeat ----------------
bridge_zip = app / "BeamNG_Mod" / "draglab_bridge_v0.2.zip"
work = Path("bridge_work_v0310")
if work.exists():
    shutil.rmtree(work)
work.mkdir()
with zipfile.ZipFile(bridge_zip, "r") as z:
    z.extractall(work)

ge = work / "lua" / "ge" / "extensions" / "draglabOfficialSync.lua"
g = ge.read_text().replace("0.3.9", "0.3.10")

g = replace_once(
    g,
    "local modulePollTimer = 0",
    "local modulePollTimer = 0\nlocal playerHeartbeatTimer = 0",
    "player heartbeat timer"
)

g = replace_once(
    g,
    """  send({type='official_sync_status',status='LISTENING - STRICT',method='exact timer IDs + coherence guards'})""",
    """  send({type='official_sync_status',status='LISTENING - STRICT',method='exact timer IDs + coherence guards',playerVehicleId=getPlayerVehicleId()})""",
    "status player id"
)

old_update = """  modulePollTimer = modulePollTimer + dt
  if modulePollTimer >= 0.25 then
    modulePollTimer = 0
    pcall(pollDragModules)
  end
end"""

new_update = """  modulePollTimer = modulePollTimer + dt
  if modulePollTimer >= 0.25 then
    modulePollTimer = 0
    pcall(pollDragModules)
  end

  -- The vehicle extension runs in every spawned vehicle. Tell the desktop server
  -- which BeamNG object is actually controlled by player 0 so AI traffic is ignored.
  playerHeartbeatTimer = playerHeartbeatTimer + dt
  if playerHeartbeatTimer >= 0.5 then
    playerHeartbeatTimer = 0
    send({type='player_vehicle_status',playerVehicleId=getPlayerVehicleId()})
  end
end"""

g = replace_once(g, old_update, new_update, "player heartbeat update")

g = replace_once(
    g,
    """  installHooks()
  pcall(pollDragModules)
end""",
    """  installHooks()
  pcall(pollDragModules)
  send({type='player_vehicle_status',playerVehicleId=getPlayerVehicleId()})
end""",
    "initial player heartbeat"
)

ge.write_text(g)

# Bump bridge package metadata / any text references.
for fp in work.rglob("*"):
    if not fp.is_file() or fp == ge:
        continue
    if fp.suffix.lower() in (".lua", ".json", ".txt"):
        txt = fp.read_text().replace("0.3.9", "0.3.10")
        fp.write_text(txt)

info = work / "info.json"
idata = json.loads(info.read_text())
idata["version"] = "0.3.10"
info.write_text(json.dumps(idata, indent=2) + "\n")

with zipfile.ZipFile(bridge_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for fp in sorted(work.rglob("*")):
        if fp.is_file():
            z.write(fp, fp.relative_to(work).as_posix())

# Dashboard text/version
p = app / "www" / "index.html"
h = p.read_text().replace("0.3.9", "0.3.10")
h = h.replace(
    "Stage 1 tunes launch/chassis. Stage 2 is now anchored to the proven Stage 1 best before front chassis and gearing begin.",
    "Stage 1 tunes launch/chassis. Stage 2 is anchored to the proven Stage 1 best, and JLRP now locks telemetry/tune commands to the actual player vehicle."
)
p.write_text(h)

# Helper visible versions if present.
for helper in ("Setup_JLRP_Run_Sync.ps1", "Sync_JLRP_RunData.ps1"):
    p = app / helper
    t = p.read_text().replace("0.3.9", "0.3.10")
    p.write_text(t)

print("Built JLRP v0.3.10 player-vehicle routing lock")

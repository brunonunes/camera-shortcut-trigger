# camera-shortcut-trigger

Runs a macOS Shortcut when a camera starts being used, and another one when it stops.

Typical use: switch on a key light when you join a call, and switch it off when you leave.

## Why this exists

macOS Shortcuts has no camera trigger. Personal automations on macOS 26 cover time of day,
alarms, folder contents and external drives — nothing for camera or microphone activity.
There is also no try/catch in Shortcuts, so an action that errors aborts the whole run.

This project fills only the missing piece: a tiny launch agent that watches for camera
activity and invokes a Shortcut, exactly as if you had run it by hand. All the actual
behaviour lives in your Shortcuts, where you can see and edit it.

## How it works

macOS logs camera power transitions to the unified log. The agent streams:

```
subsystem == "com.apple.UVCExtension" AND composedMessage CONTAINS "Post PowerLog"
```

Each event carries a device GUID and a power state:

```
Post PowerLog {
    "VDCAssistant_Device_GUID" = "...";
    "VDCAssistant_Power_State" = On;
}
```

The agent keeps the set of currently active cameras, so it runs `Camera On` when the first
camera activates and `Camera Off` only when the last one deactivates. Opening a second
camera while one is already live does not fire a duplicate.

## Requirements

- macOS with the Shortcuts CLI at `/usr/bin/shortcuts`
- Verified on macOS 26. The log predicate has changed between macOS releases — if nothing
  fires, see *Verifying the predicate* below.

## Install

```bash
mkdir -p ~/.local/bin
cp camera_shortcut_trigger.py ~/.local/bin/
chmod +x ~/.local/bin/camera_shortcut_trigger.py

sed "s|USERNAME|$USER|" com.example.camera-shortcut-trigger.plist \
  > ~/Library/LaunchAgents/com.example.camera-shortcut-trigger.plist

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.camera-shortcut-trigger.plist
```

It starts at login, not at boot — a LaunchAgent needs your user session, which is also what
`shortcuts run` requires. `KeepAlive` restarts it if it dies.

Check it:

```bash
launchctl print gui/$(id -u)/com.example.camera-shortcut-trigger | grep -E "state|pid"
```

Logs go to `/tmp/camera-shortcut-trigger.log` and `.err`.

## Shortcuts setup

Create two shortcuts named `Camera On` and `Camera Off` (or change the names at the top of
the script).

For network-controlled lights, a resilient shape is a **List** of endpoints, a **Repeat with
Each**, and a **Run Shell Script** inside the loop with input set to *Repeat Item*, passed
**as arguments**:

```bash
curl -s --max-time 3 -X PUT "$1" \
  -H 'Content-Type: application/json' \
  -d '{"lights":[{"on":1}]}' >/dev/null || true
exit 0
```

Use `"on":0` in the `Camera Off` shortcut.

The `|| true` and `exit 0` matter: Shortcuts aborts the entire run on any action error, so a
device that is offline or whose hostname does not resolve would otherwise stop the loop
before reaching the remaining ones. Swallowing the error keeps every endpoint independent.

Example list:

```
http://light1.local:9123/elgato/lights
http://light2.local:9123/elgato/lights
```

Sending only `on` preserves whatever brightness and colour temperature the device already
has. Note that some firmware accepts a string (`"on": "1"`) with HTTP 200 and silently does
nothing — keep the value a number.

## Restricting to one camera

Set `ONLY_DEVICE_GUID` in the script. To find the GUID of a specific camera, use it once and
read the log:

```bash
/usr/bin/log show --last 15m --style compact \
  --predicate 'subsystem == "com.apple.UVCExtension" AND composedMessage CONTAINS "Post PowerLog"'
```

Match the GUID against the device's Unique ID from `system_profiler SPCameraDataType`; the
vendor and product bytes appear in both.

## Verifying the predicate

If no shortcut fires, confirm the log actually emits the events on your macOS version:

```bash
/usr/bin/log stream --style compact \
  --predicate 'subsystem == "com.apple.UVCExtension" AND composedMessage CONTAINS "Post PowerLog"'
```

Then turn a camera on. If nothing appears, the subsystem changed and the predicate needs
updating. Note that `log` may be shadowed by a shell function — call `/usr/bin/log` directly.

## Known limitations

- A camera disconnected without emitting an `Off` event stays in the active set, leaving the
  lights on. Not observed in practice: physical disconnects do emit `Off`.
- Runs per user, on login. Nothing fires at the login window.
- The launch agent references an absolute path; moving the script breaks it, and the agent
  retries every 10 seconds with the error going to `/tmp/camera-shortcut-trigger.err`.

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.example.camera-shortcut-trigger
rm ~/Library/LaunchAgents/com.example.camera-shortcut-trigger.plist
rm ~/.local/bin/camera_shortcut_trigger.py
```

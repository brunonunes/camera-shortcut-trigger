#!/usr/bin/env python3
"""Run a macOS Shortcut when a camera starts being used, and another when it stops.

Watches the unified log for UVC power events. Runs SHORTCUT_ON when the first
camera becomes active and SHORTCUT_OFF when the last one goes inactive, so
overlapping cameras do not trigger twice.
"""

import json
import re
import subprocess
import sys

SHORTCUT_ON = "Camera On"
SHORTCUT_OFF = "Camera Off"

# Optional: restrict to a single camera by its device GUID. Leave as None to
# react to any camera. See README for how to find the GUID of a given device.
ONLY_DEVICE_GUID = None

PREDICATE = (
    'subsystem == "com.apple.UVCExtension" '
    'AND composedMessage CONTAINS "Post PowerLog"'
)

GUID_RE = re.compile(r'VDCAssistant_Device_GUID" = "([^"]+)"')
STATE_RE = re.compile(r'VDCAssistant_Power_State" = (\w+)')


def run_shortcut(name):
    result = subprocess.run(
        ["/usr/bin/shortcuts", "run", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"shortcut '{name}' failed: {result.stderr.strip()}",
            file=sys.stderr,
            flush=True,
        )
        return
    print(f"shortcut '{name}' ran", flush=True)


def main():
    stream = subprocess.Popen(
        ["/usr/bin/log", "stream", "--style", "ndjson", "--predicate", PREDICATE],
        stdout=subprocess.PIPE,
        text=True,
    )
    active = set()
    for line in stream.stdout:
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            message = json.loads(line).get("eventMessage", "")
        except ValueError:
            continue
        guid = GUID_RE.search(message)
        state = STATE_RE.search(message)
        if not guid or not state:
            continue
        if ONLY_DEVICE_GUID and guid.group(1) != ONLY_DEVICE_GUID:
            continue
        was_active = bool(active)
        if state.group(1) == "On":
            active.add(guid.group(1))
        else:
            active.discard(guid.group(1))
        if not was_active and active:
            run_shortcut(SHORTCUT_ON)
        elif was_active and not active:
            run_shortcut(SHORTCUT_OFF)
    return stream.wait()


if __name__ == "__main__":
    sys.exit(main())

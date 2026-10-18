#!/bin/bash
# Read-only Mac preflight. Never creates, boots, modifies or installs a VM.
set -eu
if [ "$(uname -s)" != "Darwin" ]; then
  printf '%s\n' 'Run this read-only preflight on the authorised Mac, not this container.' >&2
  exit 2
fi
printf 'Host architecture: '; /usr/bin/uname -m
printf 'macOS version: '; /usr/bin/sw_vers -productVersion
printf 'Physical RAM bytes: '; /usr/sbin/sysctl -n hw.memsize
printf 'Logical CPU count: '; /usr/sbin/sysctl -n hw.ncpu
printf '%s\n' 'Disk capacity (KiB; read-only observation):'
/bin/df -k /
UTM_PLIST='/Applications/UTM.app/Contents/Info.plist'
if [ -f "$UTM_PLIST" ]; then
  printf 'UTM version: '
  /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$UTM_PLIST"
else
  printf '%s\n' 'UTM not found at /Applications/UTM.app; inspect the user-selected installation path.'
fi
printf '%s\n' 'No VM configuration, license, system setting or file was modified.'
printf '%s\n' 'Select the existing VM explicitly before any further inspection or changes.'

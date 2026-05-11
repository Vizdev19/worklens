#!/usr/bin/env bash
# Build the EmployeeMonitor launcher for all supported targets.
#
# Output layout (under dist/):
#   EmployeeMonitor-darwin-arm64
#   EmployeeMonitor-darwin-amd64
#   EmployeeMonitor-windows-amd64.exe
#   EmployeeMonitor-linux-amd64
#
# The CI release workflow (Phase 6) will:
#   - run this script
#   - on macOS: wrap each binary into EmployeeMonitor.app bundles for
#     the LaunchAgent to target (Phase 5 ships the bundle layout)
#   - compute SHA-256 of each artifact
#   - upload to GitHub Release `agent-v<version>`
#
# We deliberately do NOT sign here. Phase-level decision: ship unsigned
# for v1. Add codesign/notarize/Authenticode hooks later — see brainstorm.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

OUT="$HERE/dist"
mkdir -p "$OUT"
rm -f "$OUT"/EmployeeMonitor-*

# Static-ish builds. -trimpath strips local paths from the binary;
# -ldflags '-s -w' drops debug+symbol tables (~30% size reduction).
LDFLAGS='-s -w'
COMMON_FLAGS=(-trimpath -ldflags "$LDFLAGS")

build() {
  local goos="$1" goarch="$2" ext="${3:-}"
  local out="$OUT/EmployeeMonitor-${goos}-${goarch}${ext}"
  echo "→ ${goos}/${goarch}"
  GOOS="$goos" GOARCH="$goarch" CGO_ENABLED=0 \
    go build "${COMMON_FLAGS[@]}" -o "$out" .
}

build darwin  arm64
build darwin  amd64
build windows amd64 .exe
build linux   amd64

echo
echo "Built artifacts:"
ls -lh "$OUT"
echo
echo "SHA-256:"
( cd "$OUT" && shasum -a 256 EmployeeMonitor-* )

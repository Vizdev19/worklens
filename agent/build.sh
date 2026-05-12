#!/usr/bin/env bash
# Build the Employee Monitor agent PyInstaller bundle and package it
# into a platform-specific archive consumable by:
#   - the in-agent updater (which downloads + verifies SHA-256 of the
#     archive listed in /agent/version manifest)
#   - the launcher (which extracts into bin/<version>/ and execs the
#     binary it expects to find inside)
#
# Layout produced (under dist/):
#
#   macOS    EmployeeMonitorAgent-<version>-darwin-<arch>.tar.gz
#              └─ contains EmployeeMonitorAgent.app/Contents/MacOS/...
#
#   Linux    EmployeeMonitorAgent-<version>-linux-amd64.tar.gz
#              └─ contains EmployeeMonitorAgent + _internal/ at the root
#                 (PyInstaller onedir layout, flattened)
#
#   Windows  EmployeeMonitorAgent-<version>-windows-amd64.zip
#              └─ contains EmployeeMonitorAgent.exe + _internal/ at root
#
# The "flattened" layout for Linux/Windows means the archive root contains
# the agent binary directly — when extracted into bin/<version>/, the
# launcher finds it at bin/<version>/EmployeeMonitorAgent[.exe]. (See
# launcher/main.go : agentBinaryInside.)
#
# This script does NOT sign or notarize anything. v1 ships unsigned per
# the auto-update brainstorm; CI (Phase 6) will run this and then layer
# signing on top once the cert budget is approved.

set -euo pipefail

APP_NAME="EmployeeMonitorAgent"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Pull the version from config.py so it stays in lockstep with what the
# agent reports to the backend. Single source of truth.
VERSION=$(python3 -c "
import re, pathlib
m = re.search(r'__version__\s*=\s*[\"\\']([^\"\\']+)', pathlib.Path('config.py').read_text())
print(m.group(1))
")
echo "📦 Building $APP_NAME v$VERSION"

echo "🧹 Cleaning previous builds..."
rm -rf build dist __pycache__

# Resolve a usable Python interpreter (prefer active venv, then python3)
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python &>/dev/null; then PY=python
  elif command -v python3 &>/dev/null; then PY=python3
  else echo "❌ No Python interpreter found"; exit 1
  fi
fi
echo "🐍 Using Python: $($PY --version)"

echo "📦 Installing build deps..."
"$PY" -m pip install --quiet pyinstaller

echo "🔨 Building executable..."
"$PY" -m PyInstaller "EmployeeMonitor.spec" --clean --noconfirm

# Resolve arch ("arm64" / "amd64") in the GOOS-GOARCH convention the
# launcher and manifest use. uname -m returns x86_64 on Intel.
RAW_ARCH="$(uname -m)"
case "$RAW_ARCH" in
  x86_64|amd64) ARCH="amd64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) ARCH="$RAW_ARCH" ;;
esac

OS_KIND="$(uname -s)"
case "$OS_KIND" in
  Darwin)
    PLATFORM="darwin-$ARCH"
    APP_PATH="dist/${APP_NAME}.app"
    if [ ! -d "$APP_PATH" ]; then
      echo "❌ Build failed: $APP_PATH not found"
      exit 1
    fi
    ARCHIVE="dist/${APP_NAME}-${VERSION}-${PLATFORM}.tar.gz"
    echo "🗜  Packaging $ARCHIVE"
    # -C dist so the archive contains "EmployeeMonitorAgent.app/" at
    # the root, not "dist/EmployeeMonitorAgent.app/".
    tar -czf "$ARCHIVE" -C dist "${APP_NAME}.app"
    ;;

  Linux)
    PLATFORM="linux-$ARCH"
    BUNDLE_DIR="dist/${APP_NAME}"
    if [ ! -d "$BUNDLE_DIR" ]; then
      echo "❌ Build failed: $BUNDLE_DIR not found"
      exit 1
    fi
    ARCHIVE="dist/${APP_NAME}-${VERSION}-${PLATFORM}.tar.gz"
    echo "🗜  Packaging $ARCHIVE"
    # -C bundle_dir so the archive contains "EmployeeMonitorAgent" + "_internal/"
    # at the root (the launcher's agentBinaryInside expects this).
    tar -czf "$ARCHIVE" -C "$BUNDLE_DIR" .
    ;;

  MINGW*|CYGWIN*|MSYS*)
    PLATFORM="windows-amd64"
    BUNDLE_DIR="dist/${APP_NAME}"
    if [ ! -d "$BUNDLE_DIR" ]; then
      echo "❌ Build failed: $BUNDLE_DIR not found"
      exit 1
    fi
    ARCHIVE="dist/${APP_NAME}-${VERSION}-${PLATFORM}.zip"
    echo "🗜  Packaging $ARCHIVE"
    # PowerShell available even on minimal Windows runners; -CompressionLevel
    # Optimal gives ~30% smaller archives than the default Fastest.
    #
    # Single-line invocation deliberately: the PowerShell line-continuation
    # backtick (`) collides with bash's command-substitution syntax — even
    # though only the MINGW branch ever runs this code, bash's *tokenizer*
    # scans the whole script and would die with "unexpected EOF while looking
    # for matching backtick" on every platform.
    powershell -NoProfile -Command "Compress-Archive -Force -CompressionLevel Optimal -Path 'dist/${APP_NAME}/*' -DestinationPath '${ARCHIVE}'"
    ;;

  *)
    echo "❌ Unsupported OS: $OS_KIND"
    exit 1
    ;;
esac

# Compute SHA-256 for the manifest. The updater compares this exact
# digest before extracting, so what we print here is what goes into
# POST /agent/version's platforms.<key>.sha256 field.
if command -v shasum &>/dev/null; then
  SHA=$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')
elif command -v sha256sum &>/dev/null; then
  SHA=$(sha256sum "$ARCHIVE" | awk '{print $1}')
else
  echo "⚠️  No shasum/sha256sum found; skipping hash"
  SHA="(unknown)"
fi
SIZE=$(wc -c < "$ARCHIVE" | tr -d ' ')

echo
echo "✅ Built $ARCHIVE"
echo "   platform: $PLATFORM"
echo "   version:  $VERSION"
echo "   size:     $SIZE bytes"
echo "   sha256:   $SHA"
echo
echo "Manifest snippet for POST /agent/version:"
echo "  \"$PLATFORM\": {"
echo "    \"url\": \"<github-release-url>/${APP_NAME}-${VERSION}-${PLATFORM}.${ARCHIVE##*.}\","
echo "    \"sha256\": \"$SHA\","
echo "    \"size\": $SIZE"
echo "  }"

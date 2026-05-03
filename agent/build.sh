#!/usr/bin/env bash
# Build the Employee Monitor agent into a native executable.
#
# Usage:
#   ./build.sh
#
# Output (macOS):
#   dist/EmployeeMonitor.app          ← drag to /Applications
#   dist/EmployeeMonitor-1.0.0.dmg    ← shareable installer

set -euo pipefail

APP_NAME="EmployeeMonitor"
VERSION="1.0.0"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "🧹 Cleaning previous builds..."
rm -rf build dist __pycache__

echo "📦 Installing build deps..."
pip install --quiet pyinstaller

echo "🔨 Building executable..."
pyinstaller "$APP_NAME.spec" --clean --noconfirm

OS_KIND="$(uname -s)"
case "$OS_KIND" in
  Darwin)
    APP_PATH="dist/${APP_NAME}.app"
    if [ ! -d "$APP_PATH" ]; then
      echo "❌ Build failed: $APP_PATH not found"
      exit 1
    fi
    echo "✅ App built: $APP_PATH"

    # Build a DMG if create-dmg is installed
    if command -v create-dmg &>/dev/null; then
      DMG_PATH="dist/${APP_NAME}-${VERSION}.dmg"
      rm -f "$DMG_PATH"
      echo "📀 Building DMG..."
      create-dmg \
        --volname "${APP_NAME} Installer" \
        --window-size 500 300 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 130 130 \
        --app-drop-link 370 130 \
        "$DMG_PATH" \
        "dist/${APP_NAME}.app"
      echo "✅ DMG built: $DMG_PATH"
    else
      echo "ℹ️  Skipping DMG (install with: brew install create-dmg)"
    fi
    ;;

  Linux)
    BIN_PATH="dist/${APP_NAME}/${APP_NAME}"
    [ -f "$BIN_PATH" ] || { echo "❌ Build failed"; exit 1; }
    echo "✅ Binary built: $BIN_PATH"
    ;;

  MINGW*|CYGWIN*|MSYS*)
    EXE_PATH="dist/${APP_NAME}/${APP_NAME}.exe"
    [ -f "$EXE_PATH" ] || { echo "❌ Build failed"; exit 1; }
    echo "✅ Executable built: $EXE_PATH"
    ;;
esac

echo "🎉 Done."

#!/usr/bin/env bash
# Bootstrap installer for the launcher-managed Employee Monitor agent.
#
# Designed for local testing and the "manual install" path documented in
# our onboarding (download launcher + agent archive, run this). Future
# work: wrap into a .pkg / .deb / NSIS .exe so the user doesn't have to
# touch a shell.
#
# Usage:
#   ./install.sh \
#     --launcher /path/to/EmployeeMonitor-darwin-arm64 \
#     --agent    /path/to/EmployeeMonitorAgent-1.2.0-darwin-arm64.tar.gz \
#     --version  1.2.0
#
# Lays out:
#   <install_dir>/
#     EmployeeMonitor                  (launcher binary, executable)
#     bin/<version>/...                (agent archive extracted here)
#
# Then launches the launcher once. The agent on first run prompts for
# login; after a successful login it writes the OS autostart entry
# (pointing at the launcher, see agent/autostart.py).

set -euo pipefail

LAUNCHER=""
AGENT_ARCHIVE=""
VERSION=""

usage() {
  cat <<EOF
Usage: $0 --launcher PATH --agent PATH --version SEMVER

Required:
  --launcher PATH    Cross-compiled launcher binary for this platform.
                     e.g. EmployeeMonitor-darwin-arm64 (from launcher/dist).
  --agent PATH       Agent archive matching this platform.
                     e.g. EmployeeMonitorAgent-1.2.0-darwin-arm64.tar.gz.
  --version SEMVER   Version string the archive corresponds to (must
                     match the bin/<version>/ subdirectory name).

Behavior:
  - Detects install_dir per OS (matches agent/paths.py and Go launcher).
  - Replaces any existing launcher binary.
  - Extracts the agent archive into bin/<version>/.
  - Verifies the agent binary is present at the path the launcher
    expects (agentBinaryInside in launcher/main.go).
  - Starts the launcher in the foreground for first-time setup.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --launcher) LAUNCHER="$2"; shift 2 ;;
    --agent)    AGENT_ARCHIVE="$2"; shift 2 ;;
    --version)  VERSION="$2"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [ -z "$LAUNCHER" ] || [ -z "$AGENT_ARCHIVE" ] || [ -z "$VERSION" ]; then
  usage
  exit 1
fi
if [ ! -f "$LAUNCHER" ]; then
  echo "❌ Launcher not found: $LAUNCHER"; exit 1
fi
if [ ! -f "$AGENT_ARCHIVE" ]; then
  echo "❌ Agent archive not found: $AGENT_ARCHIVE"; exit 1
fi

OS_KIND="$(uname -s)"
case "$OS_KIND" in
  Darwin)
    INSTALL_DIR="$HOME/Library/Application Support/EmployeeMonitor"
    LAUNCHER_DST="$INSTALL_DIR/EmployeeMonitor"
    EXPECTED_AGENT="bin/$VERSION/EmployeeMonitorAgent.app/Contents/MacOS/EmployeeMonitorAgent"
    ;;
  Linux)
    INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/EmployeeMonitor"
    LAUNCHER_DST="$INSTALL_DIR/EmployeeMonitor"
    EXPECTED_AGENT="bin/$VERSION/EmployeeMonitorAgent"
    ;;
  *)
    echo "❌ Unsupported OS: $OS_KIND (use install.ps1 on Windows)"
    exit 1
    ;;
esac

# Allow EMPLOYEE_MONITOR_HOME to redirect everything to a test location.
if [ -n "${EMPLOYEE_MONITOR_HOME:-}" ]; then
  INSTALL_DIR="$EMPLOYEE_MONITOR_HOME"
  LAUNCHER_DST="$INSTALL_DIR/EmployeeMonitor"
fi

BIN_DIR="$INSTALL_DIR/bin/$VERSION"
echo "📁 install_dir: $INSTALL_DIR"

mkdir -p "$BIN_DIR"

echo "📋 Installing launcher → $LAUNCHER_DST"
cp "$LAUNCHER" "$LAUNCHER_DST"
chmod +x "$LAUNCHER_DST"

echo "📦 Extracting agent → $BIN_DIR"
# The archive's root must contain the agent binary tree directly
# (see agent/build.sh). We extract on top of an empty directory so a
# malformed archive can't bleed into a sibling version's tree.
tar -xzf "$AGENT_ARCHIVE" -C "$BIN_DIR"

AGENT_BIN="$INSTALL_DIR/$EXPECTED_AGENT"
if [ ! -x "$AGENT_BIN" ]; then
  echo "❌ Agent binary missing or not executable: $AGENT_BIN"
  echo "   (the archive should contain the binary at:"
  echo "    $EXPECTED_AGENT — relative to the archive root)"
  exit 1
fi

echo "✅ Installed v$VERSION at $INSTALL_DIR"
echo
echo "📂 Layout:"
( cd "$INSTALL_DIR" && find . -maxdepth 4 -type d | head -20 )
echo
echo "🚀 Launching the agent for first-time setup..."
echo "   (The launcher will exec the agent; first run will prompt for login.)"
exec "$LAUNCHER_DST"

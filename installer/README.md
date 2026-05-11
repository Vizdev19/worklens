# Installer

Bootstrap scripts that lay down the launcher-managed install layout
expected by everything downstream (Go launcher, Python updater, the
agent's own paths.py). These are the artifacts the onboarding flow
should hand the user — or that a future packaged installer (.pkg /
.msi / .deb) will eventually wrap.

## What gets installed

```
<install_dir>/
  EmployeeMonitor[.exe]              ← Go launcher (autostart target)
  bin/<version>/                     ← agent payload, exec'd by launcher
    EmployeeMonitorAgent.app/...     ← macOS .app bundle
    EmployeeMonitorAgent.exe         ← Windows PyInstaller onedir root
    EmployeeMonitorAgent             ← Linux PyInstaller onedir root
    _internal/                       ← (Windows + Linux) PyInstaller libs
  updates/                           ← created later by the updater
```

Per-OS `<install_dir>`:

| OS      | Path                                            |
| ------- | ----------------------------------------------- |
| macOS   | `~/Library/Application Support/EmployeeMonitor` |
| Linux   | `${XDG_DATA_HOME:-~/.local/share}/EmployeeMonitor` |
| Windows | `%LOCALAPPDATA%\EmployeeMonitor`                |

Set `EMPLOYEE_MONITOR_HOME` to override both scripts' install root for
testing — matches what the agent and launcher honour.

## Usage

### macOS / Linux

```bash
./installer/install.sh \
  --launcher launcher/dist/EmployeeMonitor-darwin-arm64 \
  --agent    agent/dist/EmployeeMonitorAgent-1.2.0-darwin-arm64.tar.gz \
  --version  1.2.0
```

### Windows (PowerShell)

```powershell
.\installer\install.ps1 `
  -Launcher 'launcher\dist\EmployeeMonitor-windows-amd64.exe' `
  -Agent    'agent\dist\EmployeeMonitorAgent-1.2.0-windows-amd64.zip' `
  -Version  '1.2.0'
```

Both scripts:

1. Copy the launcher binary to `<install_dir>/EmployeeMonitor[.exe]`.
2. Extract the agent archive into `<install_dir>/bin/<version>/`.
3. Verify the agent binary exists at the path the launcher expects
   (`agentBinaryInside` in `launcher/main.go`).
4. Launch the launcher in the foreground for first-run login.

After the user signs in, the agent writes the OS autostart entry
pointing at the launcher binary (see `agent/autostart.py`). From then
on the launcher runs on every login, promotes any pending update, and
exec's the highest-version agent under `bin/`.

## Producing the inputs

The launcher and agent archives are built in their respective
subdirectories:

```bash
# Launcher (cross-compiles all four OS/arch combos)
cd launcher && ./build.sh

# Agent (builds for the host OS — CI matrix builds all platforms)
cd agent && ./build.sh
```

Phase 6 will move both of these into a single GitHub Actions workflow
that runs on tag `agent-v*`, uploads artifacts to the Release, computes
SHA-256 of each archive, and POSTs the new manifest to `/agent/version`.

## Limitations of v1

* **No code signing.** macOS Gatekeeper will show "damaged" on first
  launch; right-click → Open or `xattr -d com.apple.quarantine` to get
  past it. Windows SmartScreen will warn on the launcher.
* **No uninstaller.** Removing the install requires manually deleting
  `<install_dir>` and the OS autostart entry (the agent's
  `autostart.uninstall()` handles that path, called from "Sign out" in
  the local UI).
* **First-launch UX is a terminal command.** A real .pkg / .msi / .deb
  is on the post-launch roadmap; until then onboarding hands users
  these scripts.

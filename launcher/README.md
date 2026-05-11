# EmployeeMonitor launcher

Tiny Go binary (~300 lines, no deps beyond stdlib) that bootstraps the
agent on every login. It's the thing the LaunchAgent / Run-key /
`.desktop` entry actually points at, so it must change as rarely as
possible — a breaking launcher change requires every install to be
manually reinstalled, since there is no meta-launcher to update it.

## Responsibilities

1. **Promote pending updates.** If the updater (Phase 4) has staged a
   new build at `updates/<version>.ready/`, rename it into
   `bin/<version>/` before launching anything.
2. **Pick the highest installed version** under `bin/` and exec it.
3. **Get out of the way.** On POSIX, `syscall.Exec` replaces the
   launcher's process image so nothing lingers. On Windows, spawn the
   agent detached and exit.

That's the whole feature set. No network, no auth, no manifest parsing.
The launcher cannot know the manifest is wrong because the launcher
never reads the manifest — that's the agent's job.

## Install layout

```
<install_dir>/
  EmployeeMonitor[.exe]            ← this binary (the autostart target)
  bin/
    1.2.0/EmployeeMonitorAgent...  ← actual PyInstaller agent
    1.2.1/EmployeeMonitorAgent...
  updates/
    1.2.2.pending/                 ← updater writes here, untouched by launcher
    1.2.2.ready/                   ← updater renames .pending → .ready when verified
```

Per-OS install root:

| OS      | install_dir                                          | state_dir                              |
| ------- | ---------------------------------------------------- | -------------------------------------- |
| macOS   | `~/Library/Application Support/EmployeeMonitor`      | same                                   |
| Windows | `%LOCALAPPDATA%\EmployeeMonitor`                     | same                                   |
| Linux   | `$XDG_DATA_HOME/EmployeeMonitor` (XDG split)         | `$XDG_STATE_HOME/EmployeeMonitor`      |

Override both with `EMPLOYEE_MONITOR_HOME` for tests and CI.

## Version selection

* "Highest semver directory wins" — no pointer file, no symlink, no DB.
  Rollback = delete the bad version directory.
* Comparison is numeric per-component (`1.10.0 > 1.9.0`); short forms
  match (`1.2 == 1.2.0`); non-numeric components coerce to zero so we
  never panic on garbage.
* A version directory with a `.broken` marker file is skipped. This is
  reserved for a future crash-loop guard; today the marker has to be
  written manually.

## Update promotion is atomic

`os.Rename(updates/<v>.ready, bin/<v>)` is a single syscall:

* POSIX: atomic on the same filesystem.
* Windows: atomic for an empty target on the same volume.

A crash mid-promotion therefore leaves either the old tree or the new
tree in place — never a half-merged one.

## Build

Local one-platform build:

```bash
go build -trimpath -ldflags '-s -w' -o EmployeeMonitor .
```

Cross-compile all four targets:

```bash
./build.sh
```

Output lands in `dist/` with `EmployeeMonitor-<goos>-<goarch>[.exe]`
naming. The release CI workflow (Phase 6) consumes those artifacts.

## Test

```bash
go test ./...
```

Coverage spans the parts most likely to silently regress: version
parsing/comparison, `.broken` handling, non-version directory filtering,
update promotion (including the "already installed" dedupe path), and
the "no `updates/` dir at all" no-op case.

## Not in scope (yet)

* **Crash-loop guard.** A bad build can keep getting picked. v1: user
  removes the bad version directory manually.
* **Launcher self-update.** We don't update the launcher itself. A
  launcher-breaking change is a forced-reinstall event.
* **Signing.** Per the brainstorm, v1 ships unsigned. Add codesign
  + notarize + Authenticode hooks when the budget is approved.
* **Multi-channel.** Only `stable`. The `ChannelName` constant is
  reserved for the day beta/canary arrive.

# Releasing the agent

This is the operator runbook for cutting a new agent release. The
mechanics are automated by `.github/workflows/agent-release.yml`; this
file documents the four-step ritual humans drive around it.

## Prerequisites (one-time)

Both secrets are configured in the repo's GitHub Actions secrets (Settings → Secrets and variables → Actions):

| Secret                | Used for                                                |
| --------------------- | ------------------------------------------------------- |
| `API_URL`             | Backend base URL we POST the manifest to.               |
| `AGENT_RELEASE_KEY`   | Bearer key compared against `settings.agent_release_key`. |

If either is missing the workflow still uploads release assets to the GitHub
Release — it just skips the manifest POST. That lets you test the build
pipeline on a fork without leaking production secrets.

## Cutting a release

1. **Bump the version.** Edit `agent/config.py`:

   ```python
   __version__ = "1.2.1"   # was 1.2.0
   ```

2. **Decide `min_supported`.** Edit `agent/MIN_SUPPORTED` to the lowest
   version still allowed to upload. If you're patching a bug,
   `min_supported` stays where it was. If you're shipping a breaking
   change (API contract, security CVE, schema migration), bump it to
   the new version — every older agent will hit HTTP 426 on its next
   upload and force-update itself.

   ```text
   1.2.0
   ```

3. **Commit and tag.** The tag must match `agent/config.py`'s
   `__version__` exactly or the workflow fails the pre-flight check.

   ```bash
   git add agent/config.py agent/MIN_SUPPORTED
   git commit -m "Bump agent to 1.2.1"
   git tag agent-v1.2.1
   git push origin main agent-v1.2.1
   ```

4. **Watch the workflow.** Actions tab → "Agent release". The pipeline:

   - `resolve-version` (≤30s): validates tag ↔ `config.py` ↔ `MIN_SUPPORTED`.
   - `build-launcher` (~1 min): cross-compiles all four launcher binaries from one Linux runner.
   - `build-agent` matrix (~5–15 min each, in parallel): native PyInstaller builds on macOS-arm64, macOS-amd64, Windows, Linux.
   - `release`: creates / updates the GitHub Release `agent-v1.2.1`,
     uploads every artifact, then POSTs the assembled manifest to
     `${API_URL}/agent/version`.

   When the workflow finishes:
   - Existing 1.2.0+ agents will see the new version on their next
     hourly poll (or immediately if they get a 426 because
     `min_supported` moved past them).
   - The GitHub Release page has all the artifacts for manual install via `installer/install.sh` / `install.ps1`.

## What to do if a release fails partway

The workflow is idempotent — re-running it (`workflow_dispatch` with
the same version) re-uploads the same artifacts with `--clobber` and
re-POSTs the manifest. Safe to retry.

If you need to **roll back** to the previous version:

```bash
# Delete the bad tag + release on GitHub
git push --delete origin agent-v1.2.1
gh release delete agent-v1.2.1

# Re-POST the previous manifest manually (or re-run the OLD tag's workflow)
curl -X POST "$API_URL/agent/version" \
  -H "X-Release-Key: $AGENT_RELEASE_KEY" \
  -H "Content-Type: application/json" \
  -d @path/to/previous-manifest.json
```

In-field agents that already downloaded 1.2.1 into
`<install_dir>/updates/1.2.1.ready/` won't auto-roll-back — they'll
apply that staged update on next restart. To force them back, ship a
1.2.2 with the contents of 1.2.0 (or bump `min_supported` to a version
the bad build can't satisfy).

## What's in a release

Each release has 8 assets:

```
EmployeeMonitor-darwin-arm64                 Launcher (mac M-series)
EmployeeMonitor-darwin-amd64                 Launcher (mac Intel)
EmployeeMonitor-windows-amd64.exe            Launcher (Windows)
EmployeeMonitor-linux-amd64                  Launcher (Linux)
EmployeeMonitorAgent-<v>-darwin-arm64.tar.gz Agent payload (mac M-series)
EmployeeMonitorAgent-<v>-darwin-amd64.tar.gz Agent payload (mac Intel)
EmployeeMonitorAgent-<v>-windows-amd64.zip   Agent payload (Windows)
EmployeeMonitorAgent-<v>-linux-amd64.tar.gz  Agent payload (Linux)
```

The manifest only references the agent archives (the launcher is rarely
updated — when it is, distribute a fresh `installer/install.sh` run, not
through the auto-update channel).

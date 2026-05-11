// EmployeeMonitor launcher.
//
// This is the bootstrapper binary that auto-start registers (LaunchAgent
// on macOS, Run key on Windows, .desktop on Linux). It does three things
// in order:
//
//  1. Promote any pending update from ./updates/<v>.ready/  into  ./bin/<v>/
//  2. Find the highest installed agent version under ./bin/
//  3. Transfer control to that agent (exec on POSIX, spawn-and-exit on Windows)
//
// The launcher is intentionally tiny — it has no network, no auth, no
// keychain. Everything mutable lives in the per-user state directory.
// A breaking change here means a forced reinstall, so we keep the
// surface area minimal: change rarely, audit closely.
//
// "Highest semver directory wins" means there's no pointer file or
// symlink to keep in sync. Rollback = delete the bad version directory.
package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
)

// LauncherVersion is bumped manually when the launcher itself changes.
// Treated as effectively-frozen — the launcher has no auto-update path
// for itself (it would have to be replaced by some meta-launcher we
// don't want to maintain). Breaking changes here = forced reinstall.
const LauncherVersion = "1.0.0"

// ChannelName reserved for future beta/canary channels in the manifest.
// Phase 1 only supports "stable"; this constant is unused today but
// reserved so the launcher and updater agree on naming when channels land.
const ChannelName = "stable"

// EnvHomeOverride lets tests and CI redirect the install dir to a temp
// location without touching the user's real ~/Library or %LOCALAPPDATA%.
const EnvHomeOverride = "EMPLOYEE_MONITOR_HOME"

func main() {
	var showVersion bool
	flag.BoolVar(&showVersion, "version", false, "print launcher version and exit")
	flag.Parse()
	if showVersion {
		fmt.Printf("EmployeeMonitor launcher %s (%s/%s)\n",
			LauncherVersion, runtime.GOOS, runtime.GOARCH)
		os.Exit(0)
	}

	if err := setupLogging(); err != nil {
		fmt.Fprintf(os.Stderr, "[launcher] log setup failed: %v\n", err)
	}
	log.Printf("starting launcher v%s on %s/%s",
		LauncherVersion, runtime.GOOS, runtime.GOARCH)

	install, err := installDir()
	if err != nil {
		log.Fatalf("cannot resolve install dir: %v", err)
	}
	log.Printf("install dir: %s", install)

	// Step 1 — promote any update the updater (Phase 4) staged for us.
	// Failure here is logged but non-fatal: we still want to launch the
	// previous version rather than refuse to start.
	if promoted, err := applyPendingUpdates(install); err != nil {
		log.Printf("WARN update promotion failed: %v", err)
	} else if promoted != "" {
		log.Printf("applied pending update -> v%s", promoted)
	}

	// Step 2 — find the agent we should launch.
	target, err := findLatestVersion(filepath.Join(install, "bin"))
	if err != nil {
		log.Fatalf("no installed agent: %v", err)
	}
	log.Printf("running agent v%s from %s", target.Version, target.AgentBinary)

	// Step 3 — hand off. runAgent never returns on POSIX (syscall.Exec
	// replaces the process image); on Windows it spawns the agent and
	// returns immediately so we exit cleanly.
	if err := runAgent(target.AgentBinary); err != nil {
		log.Fatalf("agent launch failed: %v", err)
	}
}

// ─── Install / state directory resolution ─────────────────────────────────────

// installDir returns the user-writable directory that holds the
// launcher and all versioned agent builds. Honours EMPLOYEE_MONITOR_HOME
// for testing.
//
// Layout:
//
//	<installDir>/
//	  EmployeeMonitor[.exe]      ← this binary
//	  bin/<version>/...          ← versioned agent installs
//	  updates/<version>.ready/   ← staged updates, promoted on next launch
//
// On Linux this is split from the state dir per XDG conventions:
// binaries in $XDG_DATA_HOME, mutable state/logs in $XDG_STATE_HOME.
// On macOS and Windows we keep both under one tree because the
// platform conventions don't make a distinction.
func installDir() (string, error) {
	if override := os.Getenv(EnvHomeOverride); override != "" {
		if err := os.MkdirAll(override, 0o755); err != nil {
			return "", fmt.Errorf("create override dir: %w", err)
		}
		return override, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	var d string
	switch runtime.GOOS {
	case "darwin":
		d = filepath.Join(home, "Library", "Application Support", "EmployeeMonitor")
	case "windows":
		base := os.Getenv("LOCALAPPDATA")
		if base == "" {
			base = home
		}
		d = filepath.Join(base, "EmployeeMonitor")
	case "linux":
		base := os.Getenv("XDG_DATA_HOME")
		if base == "" {
			base = filepath.Join(home, ".local", "share")
		}
		d = filepath.Join(base, "EmployeeMonitor")
	default:
		return "", fmt.Errorf("unsupported OS: %s", runtime.GOOS)
	}
	if err := os.MkdirAll(d, 0o755); err != nil {
		return "", err
	}
	return d, nil
}

// stateDir matches agent/paths.py state_dir() exactly so the launcher
// log lands next to the agent's logs. Linux follows XDG_STATE_HOME;
// Mac/Windows reuse the install location.
func stateDir() (string, error) {
	if override := os.Getenv(EnvHomeOverride); override != "" {
		if err := os.MkdirAll(override, 0o755); err != nil {
			return "", fmt.Errorf("create override dir: %w", err)
		}
		return override, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	var d string
	switch runtime.GOOS {
	case "darwin":
		d = filepath.Join(home, "Library", "Application Support", "EmployeeMonitor")
	case "windows":
		base := os.Getenv("LOCALAPPDATA")
		if base == "" {
			base = home
		}
		d = filepath.Join(base, "EmployeeMonitor")
	case "linux":
		base := os.Getenv("XDG_STATE_HOME")
		if base == "" {
			base = filepath.Join(home, ".local", "state")
		}
		d = filepath.Join(base, "EmployeeMonitor")
	default:
		return "", fmt.Errorf("unsupported OS: %s", runtime.GOOS)
	}
	if err := os.MkdirAll(d, 0o755); err != nil {
		return "", err
	}
	return d, nil
}

// ─── Version discovery ────────────────────────────────────────────────────────

// versionDir is one candidate agent installation found under bin/.
type versionDir struct {
	Version     string // "1.2.0"
	Path        string // bin/1.2.0
	AgentBinary string // the actual executable path inside Path
}

// agentBinaryInside returns the per-OS path the launcher should exec
// from inside a versioned install directory. The agent's PyInstaller
// output name is "EmployeeMonitorAgent" to keep it distinguishable
// from the launcher in process listings.
func agentBinaryInside(versionPath string) string {
	switch runtime.GOOS {
	case "darwin":
		// PyInstaller .app bundle layout.
		return filepath.Join(versionPath,
			"EmployeeMonitorAgent.app", "Contents", "MacOS", "EmployeeMonitorAgent")
	case "windows":
		return filepath.Join(versionPath, "EmployeeMonitorAgent.exe")
	default:
		return filepath.Join(versionPath, "EmployeeMonitorAgent")
	}
}

// parseVersion splits "1.10.2" into [1,10,2] for numeric comparison.
// Non-numeric components coerce to 0 so a garbage directory name in
// bin/ can never panic us.
func parseVersion(s string) []int {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ".")
	out := make([]int, len(parts))
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil {
			n = 0
		}
		out[i] = n
	}
	return out
}

// compareVersions returns -1/0/1 like strcmp. "1.2" and "1.2.0" compare
// equal; "1.10.0" > "1.9.0" (the bug we'd hit if we used lexicographic).
func compareVersions(a, b string) int {
	va, vb := parseVersion(a), parseVersion(b)
	n := len(va)
	if len(vb) > n {
		n = len(vb)
	}
	for len(va) < n {
		va = append(va, 0)
	}
	for len(vb) < n {
		vb = append(vb, 0)
	}
	for i := 0; i < n; i++ {
		if va[i] < vb[i] {
			return -1
		}
		if va[i] > vb[i] {
			return 1
		}
	}
	return 0
}

// looksLikeVersion is a soft filter: only directories whose name parses
// to at least one non-zero numeric component are considered. Catches
// stray dirs like "tmp", "cache", README files, etc.
func looksLikeVersion(name string) bool {
	v := parseVersion(name)
	if len(v) == 0 {
		return false
	}
	for _, n := range v {
		if n > 0 {
			return true
		}
	}
	return false
}

// findLatestVersion scans bin/ and returns the highest-numbered version
// whose agent binary actually exists on disk and isn't marked .broken.
//
// `.broken` is reserved for a future crash-loop guard (not implemented
// in this phase) — if a version directory contains a file named
// `.broken`, we skip it. For v1 the only way to mark something broken
// is manual: `touch bin/1.2.0/.broken && launch again`.
func findLatestVersion(binDir string) (*versionDir, error) {
	entries, err := os.ReadDir(binDir)
	if errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("no bin/ directory at %s", binDir)
	}
	if err != nil {
		return nil, fmt.Errorf("scan %s: %w", binDir, err)
	}

	var candidates []versionDir
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		name := e.Name()
		if strings.HasPrefix(name, ".") || strings.HasSuffix(name, ".tmp") {
			continue
		}
		if !looksLikeVersion(name) {
			continue
		}
		dir := filepath.Join(binDir, name)
		if _, err := os.Stat(filepath.Join(dir, ".broken")); err == nil {
			log.Printf("skipping %s (marked .broken)", name)
			continue
		}
		binary := agentBinaryInside(dir)
		if _, err := os.Stat(binary); err != nil {
			log.Printf("skipping %s (missing %s)", name, filepath.Base(binary))
			continue
		}
		candidates = append(candidates, versionDir{
			Version:     name,
			Path:        dir,
			AgentBinary: binary,
		})
	}
	if len(candidates) == 0 {
		return nil, errors.New("no valid agent installation found in " + binDir)
	}
	sort.Slice(candidates, func(i, j int) bool {
		return compareVersions(candidates[i].Version, candidates[j].Version) > 0
	})
	chosen := candidates[0]
	return &chosen, nil
}

// ─── Update promotion ─────────────────────────────────────────────────────────

// applyPendingUpdates promotes any directory named updates/<version>.ready/
// into bin/<version>/. The updater module in the agent (Phase 4) is
// responsible for downloading into updates/<version>.pending/, verifying
// the SHA256 of every file, and atomically renaming the dir to .ready as
// a tombstone. We don't touch .pending/ — only .ready/.
//
// The promotion itself is a single os.Rename, which is atomic on POSIX
// and atomic-for-empty-target on Windows on the same volume. A crash
// mid-promotion leaves either the old or new tree in place, never both.
//
// Returns the version of the promoted update (or "" if none), and any
// error encountered. Errors are non-fatal at the call site — the
// launcher continues with whatever's already in bin/.
func applyPendingUpdates(install string) (string, error) {
	updates := filepath.Join(install, "updates")
	entries, err := os.ReadDir(updates)
	if errors.Is(err, os.ErrNotExist) {
		return "", nil
	}
	if err != nil {
		return "", err
	}

	var promoted string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		name := e.Name()
		if !strings.HasSuffix(name, ".ready") {
			continue
		}
		version := strings.TrimSuffix(name, ".ready")
		if !looksLikeVersion(version) {
			log.Printf("ignoring update with non-version name: %s", name)
			continue
		}

		src := filepath.Join(updates, name)
		dst := filepath.Join(install, "bin", version)

		if _, err := os.Stat(dst); err == nil {
			// Same version already installed (race or repeated launch).
			// Drop the staged copy.
			log.Printf("update %s already installed; cleaning staging dir", version)
			if rmErr := os.RemoveAll(src); rmErr != nil {
				log.Printf("WARN cleanup of %s failed: %v", src, rmErr)
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			return promoted, fmt.Errorf("mkdir bin/: %w", err)
		}
		if err := os.Rename(src, dst); err != nil {
			return promoted, fmt.Errorf("promote %s -> %s: %w", src, dst, err)
		}
		promoted = version
	}
	return promoted, nil
}

// ─── Logging ─────────────────────────────────────────────────────────────────

// setupLogging tees launcher logs to a file in the state dir AND to
// stderr (so launchd / Windows Event Viewer / journalctl pick them up).
func setupLogging() error {
	state, err := stateDir()
	if err != nil {
		return err
	}
	p := filepath.Join(state, "launcher.log")
	f, err := os.OpenFile(p, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	log.SetOutput(io.MultiWriter(f, os.Stderr))
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.SetPrefix("[launcher] ")
	return nil
}

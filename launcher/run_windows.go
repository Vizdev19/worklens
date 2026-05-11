//go:build windows

package main

import (
	"fmt"
	"log"
	"os"
	"os/exec"
)

// runAgent on Windows spawns the agent as a detached child and returns
// immediately. There is no exec()-style image replacement on Windows,
// so we accept that the launcher process exits cleanly after starting
// the agent — the autostart entry is "satisfied" by the launcher having
// run, and the agent continues independently.
//
// The agent is responsible for its own single-instance lock and for
// surviving the launcher's exit; we do not pass any pipes, so the
// agent's stdout/stderr go wherever Windows routes them by default
// (they're already redirected to the agent's own log file inside the
// PyInstaller bundle — see agent/main.py:_redirect_std_to_log).
func runAgent(path string) error {
	if _, err := os.Stat(path); err != nil {
		return fmt.Errorf("agent binary missing at %s: %w", path, err)
	}
	cmd := exec.Command(path)
	// Inherit env so SUPABASE_URL, EMPLOYEE_MONITOR_HOME, etc. flow through.
	cmd.Env = os.Environ()
	// Important: do NOT wire Stdout/Stderr to the launcher's pipes —
	// when the launcher exits the agent would get EPIPE on its first
	// log write. Letting them default to nil drops them to the void;
	// the agent re-attaches its own log file at startup.
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("spawn agent: %w", err)
	}
	log.Printf("spawned agent pid=%d (detached)", cmd.Process.Pid)
	// Release immediately so we don't hold the child's handle open.
	if err := cmd.Process.Release(); err != nil {
		log.Printf("WARN process.Release failed: %v", err)
	}
	return nil
}

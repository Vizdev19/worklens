//go:build !windows

package main

import (
	"fmt"
	"os"
	"syscall"
)

// runAgent on POSIX uses syscall.Exec to replace the launcher's process
// image with the agent. The launcher process disappears entirely — no
// parent lingers in `ps` / Activity Monitor, no second resident-set is
// charged to the user. If exec succeeds it does not return; an error
// only comes back when the call itself fails (missing binary, permission
// denied, etc.).
func runAgent(path string) error {
	if _, err := os.Stat(path); err != nil {
		return fmt.Errorf("agent binary missing at %s: %w", path, err)
	}
	// argv[0] = path so the agent sees a sensible value in its own argv.
	return syscall.Exec(path, []string{path}, os.Environ())
}

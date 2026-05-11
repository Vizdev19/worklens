package main

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestCompareVersions(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{
		{"1.0.0", "1.0.0", 0},
		{"1.0.0", "1.0.1", -1},
		{"1.0.1", "1.0.0", 1},
		// Lexicographic-vs-numeric guard.
		{"1.10.0", "1.9.0", 1},
		{"1.9.0", "1.10.0", -1},
		// Short-form equivalence.
		{"1.2", "1.2.0", 0},
		{"1", "1.0.0", 0},
		// Default-zero behavior on garbage components.
		{"1.0.0-rc", "1.0.0", 0},
		{"garbage", "0.0.1", -1},
		// Reasonable upgrade jumps.
		{"1.1.3", "1.2.0", -1},
		{"2.0.0", "1.99.99", 1},
	}
	for _, c := range cases {
		got := compareVersions(c.a, c.b)
		if got != c.want {
			t.Errorf("compareVersions(%q, %q) = %d, want %d", c.a, c.b, got, c.want)
		}
	}
}

func TestLooksLikeVersion(t *testing.T) {
	yes := []string{"1.0.0", "1.2.3", "0.1.0", "1"}
	no := []string{"", "0.0.0", "tmp", "cache", "README"}
	for _, s := range yes {
		if !looksLikeVersion(s) {
			t.Errorf("looksLikeVersion(%q) = false, want true", s)
		}
	}
	for _, s := range no {
		if looksLikeVersion(s) {
			t.Errorf("looksLikeVersion(%q) = true, want false", s)
		}
	}
}

// makeFakeVersion writes a minimal "agent binary" inside the per-OS
// path that agentBinaryInside expects, so findLatestVersion accepts it.
func makeFakeVersion(t *testing.T, binDir, version string) {
	t.Helper()
	versionPath := filepath.Join(binDir, version)
	binary := agentBinaryInside(versionPath)
	if err := os.MkdirAll(filepath.Dir(binary), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	// 0o755 so we could in theory exec it (we don't, but it's tidy).
	if err := os.WriteFile(binary, []byte("#!/bin/sh\necho ok\n"), 0o755); err != nil {
		t.Fatalf("write binary: %v", err)
	}
}

func TestFindLatestVersion_HighestWins(t *testing.T) {
	tmp := t.TempDir()
	binDir := filepath.Join(tmp, "bin")
	for _, v := range []string{"1.2.0", "1.10.0", "1.9.0"} {
		makeFakeVersion(t, binDir, v)
	}
	got, err := findLatestVersion(binDir)
	if err != nil {
		t.Fatalf("findLatestVersion: %v", err)
	}
	if got.Version != "1.10.0" {
		t.Errorf("got %q, want 1.10.0", got.Version)
	}
}

func TestFindLatestVersion_SkipsBroken(t *testing.T) {
	tmp := t.TempDir()
	binDir := filepath.Join(tmp, "bin")
	for _, v := range []string{"1.0.0", "1.1.0"} {
		makeFakeVersion(t, binDir, v)
	}
	// Mark the higher version as broken — launcher should fall back.
	if err := os.WriteFile(filepath.Join(binDir, "1.1.0", ".broken"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := findLatestVersion(binDir)
	if err != nil {
		t.Fatalf("findLatestVersion: %v", err)
	}
	if got.Version != "1.0.0" {
		t.Errorf("got %q, want 1.0.0 (1.1.0 is .broken)", got.Version)
	}
}

func TestFindLatestVersion_IgnoresNonVersionDirs(t *testing.T) {
	tmp := t.TempDir()
	binDir := filepath.Join(tmp, "bin")
	for _, name := range []string{"cache", "tmp", ".hidden", "README"} {
		if err := os.MkdirAll(filepath.Join(binDir, name), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	makeFakeVersion(t, binDir, "1.0.0")
	got, err := findLatestVersion(binDir)
	if err != nil {
		t.Fatalf("findLatestVersion: %v", err)
	}
	if got.Version != "1.0.0" {
		t.Errorf("got %q, want 1.0.0", got.Version)
	}
}

func TestFindLatestVersion_MissingBinaryRejected(t *testing.T) {
	tmp := t.TempDir()
	binDir := filepath.Join(tmp, "bin")
	// Create a version directory but no agent binary inside it.
	if err := os.MkdirAll(filepath.Join(binDir, "1.0.0"), 0o755); err != nil {
		t.Fatal(err)
	}
	if _, err := findLatestVersion(binDir); err == nil {
		t.Error("expected error when version dir has no agent binary")
	}
}

func TestApplyPendingUpdates_PromotesReady(t *testing.T) {
	// Skip on Windows — os.Rename of a directory across the staging
	// area works there too, but we'd need to mock the agent binary
	// differently, and the logic under test is platform-independent.
	if runtime.GOOS == "windows" {
		t.Skip("symlink/rename quirks on Windows handled by integration test")
	}
	tmp := t.TempDir()
	updates := filepath.Join(tmp, "updates")
	if err := os.MkdirAll(filepath.Join(updates, "1.2.0.ready"), 0o755); err != nil {
		t.Fatal(err)
	}
	// Drop a marker file in the staging dir we can grep for after promotion.
	marker := filepath.Join(updates, "1.2.0.ready", "marker.txt")
	if err := os.WriteFile(marker, []byte("hello"), 0o644); err != nil {
		t.Fatal(err)
	}

	promoted, err := applyPendingUpdates(tmp)
	if err != nil {
		t.Fatalf("apply: %v", err)
	}
	if promoted != "1.2.0" {
		t.Errorf("promoted = %q, want 1.2.0", promoted)
	}
	// Source should be gone, target should hold the marker.
	if _, err := os.Stat(filepath.Join(updates, "1.2.0.ready")); !os.IsNotExist(err) {
		t.Errorf("staging dir still present: err=%v", err)
	}
	moved := filepath.Join(tmp, "bin", "1.2.0", "marker.txt")
	if _, err := os.Stat(moved); err != nil {
		t.Errorf("promoted file missing: %v", err)
	}
}

func TestApplyPendingUpdates_DropsDuplicate(t *testing.T) {
	tmp := t.TempDir()
	binDir := filepath.Join(tmp, "bin")
	if err := os.MkdirAll(filepath.Join(binDir, "1.0.0"), 0o755); err != nil {
		t.Fatal(err)
	}
	staging := filepath.Join(tmp, "updates", "1.0.0.ready")
	if err := os.MkdirAll(staging, 0o755); err != nil {
		t.Fatal(err)
	}

	promoted, err := applyPendingUpdates(tmp)
	if err != nil {
		t.Fatalf("apply: %v", err)
	}
	if promoted != "" {
		t.Errorf("expected no promotion (already installed), got %q", promoted)
	}
	// Staging dir should be cleaned up.
	if _, err := os.Stat(staging); !os.IsNotExist(err) {
		t.Errorf("staging dir survived dedupe: err=%v", err)
	}
}

func TestApplyPendingUpdates_NoUpdatesDir(t *testing.T) {
	tmp := t.TempDir()
	promoted, err := applyPendingUpdates(tmp)
	if err != nil {
		t.Errorf("missing updates/ should be silent, got: %v", err)
	}
	if promoted != "" {
		t.Errorf("got promotion %q from empty install", promoted)
	}
}

func TestApplyPendingUpdates_IgnoresNonReadyDirs(t *testing.T) {
	tmp := t.TempDir()
	for _, name := range []string{"1.2.0.pending", "1.2.0.tmp", "random"} {
		if err := os.MkdirAll(filepath.Join(tmp, "updates", name), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	promoted, err := applyPendingUpdates(tmp)
	if err != nil {
		t.Errorf("apply: %v", err)
	}
	if promoted != "" {
		t.Errorf("got promotion %q from non-.ready dirs", promoted)
	}
}

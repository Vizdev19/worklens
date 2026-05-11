#!/usr/bin/env python3
"""
Assemble the /agent/version manifest payload from per-platform build
fragments and POST it to the backend.

Each agent build job writes a small JSON fragment beside its archive
identifying the filename, SHA-256, and byte size for its platform.
This script reads all of them, constructs the predictable GitHub
Release asset URLs, and submits the assembled manifest.

Inputs are passed positionally — one path per fragment file:

    publish_manifest.py \\
        artifacts/agent-darwin-arm64/fragment/darwin-arm64.json \\
        artifacts/agent-darwin-amd64/fragment/darwin-amd64.json \\
        artifacts/agent-windows-amd64/fragment/windows-amd64.json \\
        artifacts/agent-linux-amd64/fragment/linux-amd64.json

Environment:
    VERSION             — semver of the release (e.g. "1.2.0")
    TAG                 — full git tag (e.g. "agent-v1.2.0")
    REPO                — "owner/repo" used to build asset URLs
    MIN_SUPPORTED       — semver floor for the force-update gate
    API_URL             — backend base URL (e.g. https://api.example.com)
    AGENT_RELEASE_KEY   — bearer token compared against settings.agent_release_key

If API_URL or AGENT_RELEASE_KEY is unset the script prints the manifest
and exits 0 without publishing. This makes the workflow runnable on
forks and in dry-run mode without leaking secrets or failing the build.
"""

import json
import os
import sys
import urllib.error
import urllib.request


def required(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f"::error::missing required env var {name}")
        sys.exit(1)
    return v


def main() -> int:
    fragments = sys.argv[1:]
    if not fragments:
        print("::error::no fragment files supplied")
        return 1

    version = required("VERSION")
    tag = required("TAG")
    repo = required("REPO")
    min_supported = required("MIN_SUPPORTED")

    api_url = (os.environ.get("API_URL") or "").rstrip("/")
    release_key = os.environ.get("AGENT_RELEASE_KEY") or ""

    platforms: dict = {}
    for path in fragments:
        try:
            data = json.load(open(path))
        except OSError as e:
            print(f"::error::cannot read fragment {path}: {e}")
            return 1
        # Each fragment is {"<platform-key>": {filename, sha256, size}}.
        for key, info in data.items():
            url = (
                f"https://github.com/{repo}/releases/download/"
                f"{tag}/{info['filename']}"
            )
            platforms[key] = {
                "url": url,
                "sha256": info["sha256"],
                "size": int(info["size"]),
            }

    payload = {
        "version": version,
        "min_supported": min_supported,
        "platforms": platforms,
        "notes": f"Released via {tag}",
    }

    print("─" * 60)
    print("Assembled manifest:")
    print(json.dumps(payload, indent=2))
    print("─" * 60)

    if not api_url or not release_key:
        print(
            "API_URL / AGENT_RELEASE_KEY unset → skipping publish "
            "(release assets still uploaded; POST manually if needed)."
        )
        return 0

    req = urllib.request.Request(
        f"{api_url}/agent/version",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Release-Key": release_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"POST {api_url}/agent/version → {resp.status}")
            print(body)
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"::error::publish failed: HTTP {e.code}")
        print(body)
        return 1
    except urllib.error.URLError as e:
        print(f"::error::publish failed: {e.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

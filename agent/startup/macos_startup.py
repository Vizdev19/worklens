"""Run this script once during installation to add agent to macOS LaunchAgents."""
import os
import subprocess
import sys

PLIST_LABEL = "com.company.employeemonitor"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_out}</string>
    <key>StandardErrorPath</key>
    <string>{log_err}</string>
</dict>
</plist>
"""

def install(exe_path: str):
    log_dir = os.path.expanduser("~/Library/Logs/EmployeeMonitor")
    os.makedirs(log_dir, exist_ok=True)

    plist = PLIST_TEMPLATE.format(
        label=PLIST_LABEL,
        exe=exe_path,
        log_out=f"{log_dir}/stdout.log",
        log_err=f"{log_dir}/stderr.log",
    )
    with open(PLIST_PATH, "w") as f:
        f.write(plist)

    subprocess.run(["launchctl", "load", PLIST_PATH], check=True)
    print(f"✅ LaunchAgent installed: {PLIST_PATH}")

def uninstall():
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH])
        os.remove(PLIST_PATH)
        print("✅ LaunchAgent removed")
    else:
        print("LaunchAgent not found")

if __name__ == "__main__":
    exe = sys.argv[1] if len(sys.argv) > 1 else sys.executable
    install(exe)

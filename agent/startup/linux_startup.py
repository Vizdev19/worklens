"""Run this script once during installation to add agent as a systemd user service."""
import os
import subprocess
import sys

SERVICE_NAME = "employee-monitor"
SERVICE_PATH = os.path.expanduser(f"~/.config/systemd/user/{SERVICE_NAME}.service")

SERVICE_TEMPLATE = """[Unit]
Description=Employee Monitor Agent
After=network.target graphical-session.target

[Service]
Type=simple
ExecStart={exe}
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0
Environment=XAUTHORITY={xauth}

[Install]
WantedBy=default.target
"""

def install(exe_path: str):
    os.makedirs(os.path.dirname(SERVICE_PATH), exist_ok=True)
    xauth = os.path.expanduser("~/.Xauthority")

    service = SERVICE_TEMPLATE.format(exe=exe_path, xauth=xauth)
    with open(SERVICE_PATH, "w") as f:
        f.write(service)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", SERVICE_NAME], check=True)
    subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=True)
    print(f"✅ systemd user service installed: {SERVICE_PATH}")

def uninstall():
    subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME])
    subprocess.run(["systemctl", "--user", "disable", SERVICE_NAME])
    if os.path.exists(SERVICE_PATH):
        os.remove(SERVICE_PATH)
    subprocess.run(["systemctl", "--user", "daemon-reload"])
    print("✅ systemd service removed")

if __name__ == "__main__":
    exe = sys.argv[1] if len(sys.argv) > 1 else sys.executable
    install(exe)

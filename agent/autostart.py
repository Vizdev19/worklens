"""
Self-installation: register the agent to auto-start on login.

Called once after the first successful login so the employee doesn't
have to run anything extra. Cross-platform (macOS / Windows / Linux).
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

OS = platform.system()


def _executable_path() -> str:
    """Path the OS should launch on login.

    On macOS we always point at the binary inside Contents/MacOS — NOT
    at the .app via `open -a`. The `open` command exits immediately,
    which causes launchd to thrash if KeepAlive is on.
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    # Dev mode — Python interpreter + script (used for local testing)
    return f"{sys.executable} {Path(__file__).parent / 'main.py'}"


def is_installed() -> bool:
    if OS == "Darwin":
        return Path(
            "~/Library/LaunchAgents/com.employeemonitor.agent.plist"
        ).expanduser().exists()
    if OS == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
            ) as k:
                winreg.QueryValueEx(k, "EmployeeMonitor")
            return True
        except Exception:
            return False
    if OS == "Linux":
        return Path(
            "~/.config/autostart/employee-monitor.desktop"
        ).expanduser().exists()
    return False


def install():
    if is_installed():
        return
    try:
        if OS == "Darwin":
            _install_macos()
        elif OS == "Windows":
            _install_windows()
        elif OS == "Linux":
            _install_linux()
        print("[autostart] Installed — agent will start on login")
    except Exception as e:
        print(f"[autostart] Could not install ({e}); skipping")


def _install_macos():
    label = "com.employeemonitor.agent"
    plist_path = Path(f"~/Library/LaunchAgents/{label}.plist").expanduser()
    log_dir = Path("~/Library/Logs/EmployeeMonitor").expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    exe = _executable_path()

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
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
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>StandardOutPath</key>
    <string>{log_dir}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/stderr.log</string>
</dict>
</plist>
"""
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist)
    # Unload first in case an old plist is already running
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
    subprocess.run(["launchctl", "load", str(plist_path)], check=False)


def _install_windows():
    import winreg
    exe = _executable_path()
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    ) as k:
        winreg.SetValueEx(k, "EmployeeMonitor", 0, winreg.REG_SZ, exe)

    # Drop a Start Menu shortcut so the user can find the app even
    # after they forget where they extracted the ZIP.
    _create_windows_start_menu_shortcut(exe)


def _create_windows_start_menu_shortcut(exe: str):
    """
    Drop a clickable shortcut in the user's Start Menu so they can find
    EmployeeMonitor without remembering where they unzipped it.

    Uses the .url InternetShortcut format because it doesn't require
    pywin32 / pythoncom — pure text file. Windows Explorer renders the
    file as a clickable item with our exe's icon.
    """
    try:
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return
        start_menu = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        start_menu.mkdir(parents=True, exist_ok=True)
        shortcut = start_menu / "Employee Monitor.url"
        shortcut.write_text(
            "[InternetShortcut]\n"
            f"URL=file:///{exe.replace(chr(92), '/')}\n"
            f"IconFile={exe}\n"
            "IconIndex=0\n"
        )
        print(f"[autostart] Start Menu shortcut: {shortcut}")
    except Exception as e:
        print(f"[autostart] Could not create Start Menu shortcut ({e})")


def _install_linux():
    autostart_dir = Path("~/.config/autostart").expanduser()
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = autostart_dir / "employee-monitor.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Employee Monitor\n"
        f"Exec={_executable_path()}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Hidden=false\n"
        "NoDisplay=false\n"
    )


def uninstall():
    """Remove the auto-start entry — used on sign-out."""
    try:
        if OS == "Darwin":
            plist = Path(
                "~/Library/LaunchAgents/com.employeemonitor.agent.plist"
            ).expanduser()
            if plist.exists():
                subprocess.run(["launchctl", "unload", str(plist)], check=False)
                plist.unlink()
        elif OS == "Windows":
            import winreg
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE,
                ) as k:
                    winreg.DeleteValue(k, "EmployeeMonitor")
            except FileNotFoundError:
                pass
            # Remove the Start Menu shortcut too
            appdata = os.environ.get("APPDATA")
            if appdata:
                shortcut = (Path(appdata) / "Microsoft" / "Windows" /
                            "Start Menu" / "Programs" / "Employee Monitor.url")
                if shortcut.exists():
                    try:
                        shortcut.unlink()
                    except Exception:
                        pass
        elif OS == "Linux":
            f = Path("~/.config/autostart/employee-monitor.desktop").expanduser()
            if f.exists():
                f.unlink()
        print("[autostart] Uninstalled")
    except Exception as e:
        print(f"[autostart] Uninstall failed ({e})")

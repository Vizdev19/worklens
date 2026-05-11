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

    For 1.2.0+ launcher-managed installs this returns the Go launcher
    binary, NOT the agent's PyInstaller bundle. The launcher is what's
    stable across agent updates — every released agent binary lives
    under bin/<version>/, but the launcher path never changes, so the
    autostart entry written here keeps working as the agent updates
    itself in place.

    Fallback order:
      1. paths.launcher_path()           — frozen launcher-managed install
      2. sys.executable                  — frozen install without launcher
                                           (legacy 1.1.3-style or broken
                                            layout we shouldn't write to)
      3. python interpreter + main.py    — running from source (dev mode)

    On macOS we always point at a plain binary path, NOT at the .app via
    `open -a`. `open` exits immediately, which causes launchd to thrash
    if KeepAlive is on.
    """
    if getattr(sys, "frozen", False):
        # Prefer the launcher when it exists alongside us. paths is
        # imported lazily so any path-resolution failure (no XDG home,
        # unusual filesystem) falls through to the next branch instead
        # of crashing autostart entirely.
        try:
            from paths import launcher_path
            lp = launcher_path()
            if lp.exists():
                return str(lp)
        except Exception as e:
            print(f"[autostart] launcher lookup failed: {e}")
        return sys.executable

    # Dev / source mode — Python interpreter + script. The single-string
    # form below is fine for the Windows Run key but not for launchd
    # (which doesn't parse spaces inside one <string>). Dev users don't
    # typically enable autostart, so we don't bother splitting here.
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
    Drop a real .lnk shortcut in the user's Start Menu so they can
    re-launch the app from anywhere — including after sign-out.

    We use PowerShell's built-in WScript.Shell COM to write a proper
    .lnk file, since pywin32 isn't a dependency. No new pip packages
    needed; PowerShell ships with every modern Windows.
    """
    try:
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return
        start_menu = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        start_menu.mkdir(parents=True, exist_ok=True)
        shortcut = start_menu / "Employee Monitor.lnk"

        # Escape backslashes and quotes for PowerShell single-quoted strings
        def _ps(s: str) -> str:
            return s.replace("'", "''")

        ps = (
            "$ws = New-Object -ComObject WScript.Shell;"
            f"$s = $ws.CreateShortcut('{_ps(str(shortcut))}');"
            f"$s.TargetPath = '{_ps(exe)}';"
            f"$s.WorkingDirectory = '{_ps(str(Path(exe).parent))}';"
            f"$s.IconLocation = '{_ps(exe)}';"
            "$s.Description = 'Employee Monitor';"
            "$s.Save();"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
            timeout=15,
        )
        if shortcut.exists():
            print(f"[autostart] Start Menu shortcut created: {shortcut}")
        else:
            print(f"[autostart] PowerShell ran but shortcut not found at {shortcut}")
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
            # Remove the Start Menu shortcut too (.lnk now, .url for older builds)
            appdata = os.environ.get("APPDATA")
            if appdata:
                start_menu = (Path(appdata) / "Microsoft" / "Windows" /
                              "Start Menu" / "Programs")
                for name in ("Employee Monitor.lnk", "Employee Monitor.url"):
                    f = start_menu / name
                    if f.exists():
                        try:
                            f.unlink()
                        except Exception:
                            pass
        elif OS == "Linux":
            f = Path("~/.config/autostart/employee-monitor.desktop").expanduser()
            if f.exists():
                f.unlink()
        print("[autostart] Uninstalled")
    except Exception as e:
        print(f"[autostart] Uninstall failed ({e})")

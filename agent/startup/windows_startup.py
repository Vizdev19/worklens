"""Run this script once during installation to add agent to Windows startup."""
import winreg
import sys
import os

APP_NAME = "EmployeeMonitor"

def add_to_startup(exe_path: str):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
    winreg.CloseKey(key)
    print(f"✅ Added to Windows startup: {exe_path}")

def remove_from_startup():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("✅ Removed from Windows startup")
    except FileNotFoundError:
        print("Not in startup")

if __name__ == "__main__":
    exe = sys.argv[1] if len(sys.argv) > 1 else sys.executable
    add_to_startup(exe)

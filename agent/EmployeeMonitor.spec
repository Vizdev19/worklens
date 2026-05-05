# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Employee Monitor Agent.

Build:
    pyinstaller EmployeeMonitor.spec --clean

Output:
    macOS    → dist/EmployeeMonitor.app
    Windows  → dist/EmployeeMonitor.exe
    Linux    → dist/EmployeeMonitor   (single binary)

Notes:
- Bundles a hidden console on macOS/Windows (windowed app)
- Includes the bundled .env, icon, and any data files
"""

import sys
from pathlib import Path

block_cipher = None
APP_NAME = "EmployeeMonitor"
HERE = Path(".").resolve()

# Collect runtime data files
datas = []

# Bundle the .env if present (so the SERVER_URL is baked in)
env_file = HERE / ".env"
if env_file.exists():
    datas.append((str(env_file), "."))

# Bundle the icon if present (used for the tray and app icon)
icon_path = None
if (HERE / "icon.icns").exists():
    icon_path = str(HERE / "icon.icns")     # macOS
elif (HERE / "icon.ico").exists():
    icon_path = str(HERE / "icon.ico")      # Windows

# Hidden imports — pystray + plugins
hidden_imports = [
    "pystray._darwin",
    "pystray._win32",
    "pystray._gtk",
    "pystray._appindicator",
    # pywebview backends
    "webview.platforms.cocoa",
    "webview.platforms.winforms",
    "webview.platforms.gtk",
    "webview.platforms.qt",
]

a = Analysis(
    ["main.py"],
    pathex=[str(HERE)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,        # windowed (no terminal)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_path,
        bundle_identifier="com.employeemonitor.agent",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": "Employee Monitor",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "LSUIElement": True,                        # hide from Dock — runs as menubar app
            "NSHighResolutionCapable": True,
            "NSScreenCaptureUsageDescription":
                "Employee Monitor captures periodic screenshots to log workplace activity.",
            "NSAppleEventsUsageDescription":
                "Employee Monitor uses Apple Events to detect when the system is idle.",
        },
    )

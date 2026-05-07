# Employee Monitor Agent — Install Guide

## macOS (Apple Silicon)

1. Download `EmployeeMonitor-mac-arm64.dmg`
2. Open the DMG, drag **EmployeeMonitor** into your Applications folder
3. Eject the DMG

### First Launch

1. Open **Applications** → double-click **EmployeeMonitor**
2. macOS will say *"Apple could not verify EmployeeMonitor"* — click **Done**
3. Open **System Settings → Privacy & Security**
4. Scroll down to *"EmployeeMonitor was blocked..."* → click **Open Anyway**
5. Authenticate with Touch ID / password → click **Open**

### Grant Permissions

You'll be asked twice (once each):

**Input Monitoring**
- macOS prompt → click **Open System Settings** → toggle **EmployeeMonitor** on
- The app will close — that's expected

**Screen Recording**
- Reopen EmployeeMonitor → prompt appears → toggle on in System Settings
- The app will close again — relaunch one more time

### Sign In

- The status window opens with two prompts: enter your work email + password (provided by your admin)
- If asked about keychain → click **Always Allow**
- Done. The app runs silently in the background and starts automatically every login.

---

## Windows 10 / 11

1. Download `EmployeeMonitor-windows.zip`
2. Extract the ZIP — you get an `EmployeeMonitor` folder with `EmployeeMonitor.exe` inside
3. Move the entire folder to `C:\Program Files\EmployeeMonitor\` (recommended) or any folder you prefer

### First Launch

1. Double-click **EmployeeMonitor.exe**
2. Windows SmartScreen will say *"Windows protected your PC"*
3. Click **More info** → **Run anyway**

### WebView2 Runtime

The status window uses Microsoft Edge WebView2. The agent bundles the
WebView2 Evergreen Bootstrapper (~150 KB) and auto-installs the runtime
silently on first launch if it isn't already present. No manual step
needed.

If the auto-install fails (locked-down corporate machine, no internet at
first launch, etc.), download and run the bootstrapper manually:
[https://go.microsoft.com/fwlink/p/?LinkId=2124703](https://go.microsoft.com/fwlink/p/?LinkId=2124703)

### Sign In

- The status window opens with two prompts: enter your work email + password (provided by your admin)
- Done. The app starts automatically on every login (added to `HKCU\...\Run`).

---

## Where Things Live

| OS | Auto-start | Logs |
|---|---|---|
| macOS | `~/Library/LaunchAgents/com.employeemonitor.agent.plist` | `~/Library/Logs/EmployeeMonitor/stderr.log` |
| Windows | Registry: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\EmployeeMonitor` | (writes to console; no log file by default) |
| Linux | `~/.config/autostart/employee-monitor.desktop` | (writes to console) |

---

## Sign Out

Open the status window:
- macOS: open Applications → EmployeeMonitor
- Windows: Start menu → EmployeeMonitor (or wherever you placed it)

Click **Sign out & quit**. This:
- Stops monitoring
- Clears your saved login from the system credential store
- Removes the auto-start entry
- Exits the app

---

## Troubleshooting

### "Only my desktop wallpaper is in the screenshots"
Screen Recording permission isn't fully granted. On macOS:
1. System Settings → Privacy & Security → Screen Recording
2. Remove any **EmployeeMonitor** entry, click **+** to re-add `/Applications/EmployeeMonitor.app`
3. Toggle on
4. Restart your Mac

### "Login dialog never appears" (Windows)
Make sure WebView2 runtime is installed. See the link above.

### "The app keeps crashing on macOS"
Run the binary directly to see the error:
```bash
/Applications/EmployeeMonitor.app/Contents/MacOS/EmployeeMonitor
```
Send the output to your admin.

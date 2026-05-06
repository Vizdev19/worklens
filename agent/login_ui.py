"""
Cross-platform login on first launch.

Strategy by OS:
  macOS    → native AppleScript dialog (osascript) — no deps, never crashes
  Windows  → tkinter fallback
  Linux    → zenity (if available) → tkinter → CLI

If running in a real terminal (no GUI), falls back to CLI prompt.
"""

import getpass
import platform
import shutil
import subprocess
import sys

import auth

OS = platform.system()


def show_login() -> bool:
    """Show login UI. Return True on success, False on cancel/failure."""
    # On windowed (no-console) PyInstaller builds, sys.stdin is None — guard.
    try:
        has_tty = bool(sys.stdin and sys.stdin.isatty())
    except (AttributeError, ValueError):
        has_tty = False

    # OS-specific GUI first
    try:
        if OS == "Darwin":
            return _login_macos()
        if OS == "Linux" and shutil.which("zenity"):
            return _login_zenity()
        # Windows or fallback
        return _login_tkinter()
    except Exception as e:
        print(f"[login] GUI failed ({e}); falling back to CLI")

    # Last resort
    if has_tty:
        return _login_cli()
    print("[login] No GUI available and no terminal — cannot prompt.")
    return False


# ── macOS: native AppleScript dialog ────────────────────────────────────────

def _osascript(script: str) -> str:
    """Run an AppleScript and return its stdout. Raises on cancel."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # User clicked Cancel or osascript failed
        raise RuntimeError(result.stderr.strip() or "cancelled")
    return result.stdout.strip()


def _login_macos() -> bool:
    for _ in range(3):
        try:
            email = _osascript(
                'tell application "System Events" to display dialog '
                '"Sign in to Employee Monitor\\n\\nEnter your work email:" '
                'default answer "" with title "Employee Monitor" '
                'buttons {"Cancel", "Next"} default button "Next"'
            )
            # Output looks like: "button returned:Next, text returned:foo@bar.com"
            email = _parse_text_returned(email)

            password = _osascript(
                'tell application "System Events" to display dialog '
                '"Enter your password:" '
                'default answer "" with hidden answer with title "Employee Monitor" '
                'buttons {"Cancel", "Sign In"} default button "Sign In"'
            )
            password = _parse_text_returned(password)
        except RuntimeError:
            print("[login] User cancelled")
            return False

        if not email or not password:
            _macos_alert("Email and password are required.")
            continue

        if auth.login(email, password):
            return True
        _macos_alert("Login failed. Please check your credentials and try again.")

    return False


def _macos_alert(message: str):
    msg = message.replace('"', "'")
    try:
        _osascript(
            f'tell application "System Events" to display dialog '
            f'"{msg}" with title "Employee Monitor" buttons {{"OK"}}'
        )
    except Exception:
        pass


def _parse_text_returned(output: str) -> str:
    """osascript returns 'button returned:X, text returned:Y' — extract Y."""
    if "text returned:" in output:
        return output.split("text returned:", 1)[1].strip()
    return output.strip()


# ── Linux: zenity ───────────────────────────────────────────────────────────

def _login_zenity() -> bool:
    for _ in range(3):
        email = subprocess.run(
            ["zenity", "--entry",
             "--title=Employee Monitor",
             "--text=Sign in — enter your work email:"],
            capture_output=True, text=True,
        )
        if email.returncode != 0:
            return False

        password = subprocess.run(
            ["zenity", "--password", "--title=Employee Monitor"],
            capture_output=True, text=True,
        )
        if password.returncode != 0:
            return False

        if auth.login(email.stdout.strip(), password.stdout.strip()):
            return True

        subprocess.run([
            "zenity", "--error",
            "--title=Employee Monitor",
            "--text=Invalid credentials. Please try again.",
        ])
    return False


# ── Tkinter (Windows / fallback) ────────────────────────────────────────────

def _login_tkinter() -> bool:
    import tkinter as tk

    result = {"success": False}

    root = tk.Tk()
    root.title("Employee Monitor — Login")
    root.geometry("360x240")
    root.resizable(False, False)
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Employee Monitor", font=("Helvetica", 16, "bold")).pack(pady=(20, 4))
    tk.Label(root, text="Sign in with your company account", font=("Helvetica", 10)).pack(pady=(0, 16))

    tk.Label(root, text="Email", anchor="w").pack(fill="x", padx=40)
    email_var = tk.StringVar()
    tk.Entry(root, textvariable=email_var, width=36).pack(padx=40, pady=(2, 8))

    tk.Label(root, text="Password", anchor="w").pack(fill="x", padx=40)
    password_var = tk.StringVar()
    tk.Entry(root, textvariable=password_var, show="*", width=36).pack(padx=40, pady=(2, 12))

    status_var = tk.StringVar()
    tk.Label(root, textvariable=status_var, fg="red", font=("Helvetica", 9)).pack()

    def on_login():
        email = email_var.get().strip()
        password = password_var.get()
        if not email or not password:
            status_var.set("Please enter email and password")
            return
        status_var.set("Signing in...")
        root.update()
        if auth.login(email, password):
            result["success"] = True
            root.destroy()
        else:
            status_var.set("Invalid credentials. Please try again.")

    tk.Button(root, text="Sign In", command=on_login, bg="#4F46E5", fg="white",
              relief="flat", padx=16, pady=6).pack(pady=4)
    root.bind("<Return>", lambda _: on_login())

    root.mainloop()
    return result["success"]


# ── CLI fallback ────────────────────────────────────────────────────────────

def _login_cli() -> bool:
    print("\n=== Employee Monitor — Sign In ===")
    for _ in range(3):
        try:
            email = input("Email: ").strip()
            password = getpass.getpass("Password: ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return False

        if not email or not password:
            print("Please enter email and password.")
            continue

        print("Signing in...")
        if auth.login(email, password):
            print(f"✅ Logged in as {auth.get_full_name()}\n")
            return True
        print("❌ Invalid credentials. Try again.")

    print("Too many failed attempts. Exiting.")
    return False

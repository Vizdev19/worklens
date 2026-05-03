"""
Login on first launch.
Uses tkinter GUI when available; falls back to CLI prompt if tkinter
can't start (e.g. macOS Tk framework mismatch, headless system).
Returns True if login succeeded, False if user cancelled.
"""

import getpass
import auth


def show_login() -> bool:
    # Try GUI first
    try:
        return _show_login_gui()
    except Exception as e:
        print(f"[login] GUI unavailable ({e}); falling back to CLI prompt")
        return _show_login_cli()


def _show_login_cli() -> bool:
    print("\n=== Employee Monitor — Sign In ===")
    for _ in range(3):  # 3 attempts
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


def _show_login_gui() -> bool:
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

"""
Simple tkinter login window shown on first launch.
Returns True if login succeeded, False if user closed the window.
"""

import tkinter as tk
from tkinter import messagebox
import auth


def show_login() -> bool:
    result = {"success": False}

    root = tk.Tk()
    root.title("Employee Monitor — Login")
    root.geometry("360x240")
    root.resizable(False, False)
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Employee Monitor", font=("Helvetica", 16, "bold")).pack(pady=(20, 4))
    tk.Label(root, text="Sign in with your company account", font=("Helvetica", 10)).pack(pady=(0, 16))

    # Email
    tk.Label(root, text="Email", anchor="w").pack(fill="x", padx=40)
    email_var = tk.StringVar()
    tk.Entry(root, textvariable=email_var, width=36).pack(padx=40, pady=(2, 8))

    # Password
    tk.Label(root, text="Password", anchor="w").pack(fill="x", padx=40)
    password_var = tk.StringVar()
    tk.Entry(root, textvariable=password_var, show="*", width=36).pack(padx=40, pady=(2, 12))

    status_var = tk.StringVar()
    status_label = tk.Label(root, textvariable=status_var, fg="red", font=("Helvetica", 9))
    status_label.pack()

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

    btn = tk.Button(root, text="Sign In", command=on_login, bg="#4F46E5", fg="white",
                    relief="flat", padx=16, pady=6)
    btn.pack(pady=4)

    # Allow pressing Enter to submit
    root.bind("<Return>", lambda _: on_login())

    root.mainloop()
    return result["success"]

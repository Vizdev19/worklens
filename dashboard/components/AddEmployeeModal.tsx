"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Loader2, UserPlus, Copy, Check } from "lucide-react";
import { employeesApi } from "@/lib/api";

export function AddEmployeeModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [created, setCreated] = useState<{
    email: string;
    password: string;
    full_name: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      employeesApi.create({ email, full_name: fullName, password }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      setCreated({ email, password, full_name: fullName });
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to create employee");
    },
  });

  function generatePassword() {
    const chars =
      "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
    let p = "";
    for (let i = 0; i < 12; i++)
      p += chars[Math.floor(Math.random() * chars.length)];
    setPassword(p);
  }

  function copyCredentials() {
    if (!created) return;
    const text = `Email: ${created.email}\nPassword: ${created.password}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    mutation.mutate();
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b">
          <div className="flex items-center gap-2">
            <UserPlus size={20} className="text-brand-600" />
            <h2 className="font-semibold text-lg">
              {created ? "Employee Created" : "Add Employee"}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-100 rounded-lg"
          >
            <X size={20} />
          </button>
        </div>

        {created ? (
          <div className="p-5 space-y-4">
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 text-sm">
              <p className="font-medium text-emerald-900">
                ✅ {created.full_name} created successfully
              </p>
              <p className="text-emerald-800 mt-1">
                Share these credentials securely. They won't be shown again.
              </p>
            </div>

            <div className="bg-slate-50 rounded-lg p-4 space-y-2 font-mono text-sm">
              <div>
                <span className="text-slate-500">Email:</span>{" "}
                <span>{created.email}</span>
              </div>
              <div>
                <span className="text-slate-500">Password:</span>{" "}
                <span>{created.password}</span>
              </div>
            </div>

            <button
              onClick={copyCredentials}
              className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-medium flex items-center justify-center gap-2"
            >
              {copied ? (
                <>
                  <Check size={16} /> Copied
                </>
              ) : (
                <>
                  <Copy size={16} /> Copy credentials
                </>
              )}
            </button>

            <button
              onClick={onClose}
              className="w-full py-2 border rounded-lg hover:bg-slate-50"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="p-5 space-y-4">
            <div>
              <label className="text-sm font-medium block mb-1">
                Full name
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500 focus:outline-none"
                placeholder="Alice Johnson"
              />
            </div>

            <div>
              <label className="text-sm font-medium block mb-1">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500 focus:outline-none"
                placeholder="alice@company.com"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium">Password</label>
                <button
                  type="button"
                  onClick={generatePassword}
                  className="text-xs text-brand-600 hover:underline"
                >
                  Generate
                </button>
              </div>
              <input
                type="text"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500 focus:outline-none font-mono"
                placeholder="At least 8 characters"
              />
              <p className="text-xs text-slate-500 mt-1">
                Share this with the employee — they'll use it to log into the
                agent.
              </p>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-2.5 border rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="flex-1 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-lg font-medium flex items-center justify-center gap-2"
              >
                {mutation.isPending && (
                  <Loader2 size={16} className="animate-spin" />
                )}
                Create Employee
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

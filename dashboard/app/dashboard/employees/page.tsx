"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { employeesApi } from "@/lib/api";
import Link from "next/link";
import { ChevronRight, UserPlus, Search, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { AddEmployeeModal } from "@/components/AddEmployeeModal";

export default function EmployeesPage() {
  const [showAdd, setShowAdd] = useState(false);
  const [query, setQuery] = useState("");

  const { data: employees, isLoading } = useQuery({
    queryKey: ["employees"],
    queryFn: employeesApi.list,
  });

  const filtered = useMemo(() => {
    if (!employees) return [];
    const q = query.trim().toLowerCase();
    if (!q) return employees;
    return employees.filter((e) =>
      e.full_name.toLowerCase().includes(q) ||
      e.email.toLowerCase().includes(q)
    );
  }, [employees, query]);

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">Employees</h1>
          <p className="text-slate-500 text-sm">
            {employees?.length ?? 0} team member(s)
            {query && filtered.length !== employees?.length &&
              ` · ${filtered.length} matching`}
          </p>
        </div>

        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-medium text-sm transition"
        >
          <UserPlus size={16} />
          Add Employee
        </button>
      </div>

      {/* Search bar */}
      {!!employees?.length && (
        <div className="relative max-w-md">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or email…"
            className="w-full pl-9 pr-9 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
            autoFocus
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-slate-100 text-slate-500"
            >
              <X size={14} />
            </button>
          )}
        </div>
      )}

      <div className="bg-white border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500">Loading...</div>
        ) : !employees?.length ? (
          <div className="p-8 text-center">
            <p className="text-slate-500 mb-3">No employees yet.</p>
            <button
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-medium text-sm"
            >
              <UserPlus size={16} />
              Add your first employee
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <p>No employees match "{query}"</p>
            <button
              onClick={() => setQuery("")}
              className="text-brand-600 hover:underline text-sm mt-2"
            >
              Clear search
            </button>
          </div>
        ) : (
          <ul className="divide-y">
            {filtered.map((e) => (
              <li key={e.id}>
                <Link
                  href={`/dashboard/employees/${e.id}`}
                  className="flex items-center justify-between p-4 hover:bg-slate-50 transition"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
                      {e.full_name
                        .split(" ")
                        .map((n) => n[0])
                        .join("")
                        .slice(0, 2)
                        .toUpperCase()}
                    </div>
                    <div>
                      <div className="font-medium">{e.full_name}</div>
                      <div className="text-sm text-slate-500">{e.email}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          e.is_active
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {e.is_active ? "Active" : "Disabled"}
                      </span>
                      <div className="text-xs text-slate-400 mt-1">
                        Joined{" "}
                        {formatDistanceToNow(new Date(e.created_at), {
                          addSuffix: true,
                        })}
                      </div>
                    </div>
                    <ChevronRight size={18} className="text-slate-400" />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showAdd && <AddEmployeeModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}

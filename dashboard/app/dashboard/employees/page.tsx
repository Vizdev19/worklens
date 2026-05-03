"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { employeesApi } from "@/lib/api";
import Link from "next/link";
import { ChevronRight, UserPlus } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { AddEmployeeModal } from "@/components/AddEmployeeModal";

export default function EmployeesPage() {
  const [showAdd, setShowAdd] = useState(false);
  const { data: employees, isLoading } = useQuery({
    queryKey: ["employees"],
    queryFn: employeesApi.list,
  });

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">Employees</h1>
          <p className="text-slate-500 text-sm">
            {employees?.length ?? 0} team member(s)
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
        ) : (
          <ul className="divide-y">
            {employees.map((e) => (
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

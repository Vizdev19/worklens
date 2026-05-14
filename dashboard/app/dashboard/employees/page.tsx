"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { employeesApi } from "@/lib/api";
import type { HeartbeatSummary } from "@/types/api";
import Link from "next/link";
import { ChevronRight, UserPlus, Search, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { AddEmployeeModal } from "@/components/AddEmployeeModal";

// Refresh heartbeats every 30 s so the list stays roughly live without
// hammering the API. Aligns with the agent's ~10 min heartbeat cadence —
// even if every employee pings precisely once per 10 min, the list still
// reflects "less than 30 s old" at all times.
const HEARTBEAT_REFRESH_MS = 30_000;

// How long after the last heartbeat we still consider an agent "online".
// Heartbeat cadence is 10 min with ±1 min jitter, so we add a generous
// 4-min grace before flipping to "offline" — avoids flapping when a
// pulse is late by a few seconds due to network or runner scheduling.
const ONLINE_THRESHOLD_MS = 15 * 60 * 1000;

type AgentVisualState =
  | "online"
  | "idle"
  | "paused"
  | "must_update"
  | "permission_denied"
  | "offline"
  | "never_seen"
  | "disabled";

interface AgentBadge {
  label: string;
  cls: string;
}

// Translate a HeartbeatSummary into the UX state we want to render.
// Order of checks matters: "disabled" wins over any agent state, because
// a deactivated user shouldn't show "Monitoring active".
function visualState(hb: HeartbeatSummary): AgentVisualState {
  if (!hb.is_active) return "disabled";
  if (!hb.last_seen) return "never_seen";
  const ageMs = Date.now() - new Date(hb.last_seen).getTime();
  if (ageMs > ONLINE_THRESHOLD_MS) return "offline";
  if (hb.status === "permission_denied") return "permission_denied";
  if (hb.status === "update_required") return "must_update";
  if (hb.status === "paused") return "paused";
  if (hb.status === "idle") return "idle";
  return "online";
}

const BADGES: Record<AgentVisualState, AgentBadge> = {
  online:             { label: "Monitoring", cls: "bg-emerald-100 text-emerald-700" },
  idle:               { label: "Idle",       cls: "bg-amber-100 text-amber-700"     },
  paused:             { label: "Paused",     cls: "bg-amber-100 text-amber-700"     },
  must_update:        { label: "Update required", cls: "bg-rose-100 text-rose-700"  },
  permission_denied:  { label: "Permission needed", cls: "bg-rose-100 text-rose-700" },
  offline:            { label: "Offline",    cls: "bg-slate-100 text-slate-500"     },
  never_seen:         { label: "Never seen", cls: "bg-slate-100 text-slate-500"     },
  disabled:           { label: "Disabled",   cls: "bg-slate-200 text-slate-500"     },
};

export default function EmployeesPage() {
  const [showAdd, setShowAdd] = useState(false);
  const [query, setQuery] = useState("");

  const { data: rows, isLoading } = useQuery({
    queryKey: ["employees", "heartbeats"],
    queryFn: employeesApi.heartbeats,
    refetchInterval: HEARTBEAT_REFRESH_MS,
  });

  const filtered = useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.full_name.toLowerCase().includes(q) ||
        r.email.toLowerCase().includes(q),
    );
  }, [rows, query]);

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">Employees</h1>
          <p className="text-slate-500 text-sm">
            {rows?.length ?? 0} team member(s)
            {query && filtered.length !== rows?.length &&
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
      {!!rows?.length && (
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
        ) : !rows?.length ? (
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
            <p>No employees match &quot;{query}&quot;</p>
            <button
              onClick={() => setQuery("")}
              className="text-brand-600 hover:underline text-sm mt-2"
            >
              Clear search
            </button>
          </div>
        ) : (
          <ul className="divide-y">
            {filtered.map((r) => {
              const state = visualState(r);
              const badge = BADGES[state];
              return (
                <li key={r.user_id}>
                  <Link
                    href={`/dashboard/employees/${r.user_id}`}
                    className="flex items-center justify-between p-4 hover:bg-slate-50 transition"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
                        {r.full_name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()}
                      </div>
                      <div>
                        <div className="font-medium">{r.full_name}</div>
                        <div className="text-sm text-slate-500">{r.email}</div>
                        {/* Agent fingerprint — only shown when we've seen them at least once. */}
                        {r.agent_version && (
                          <div className="text-xs text-slate-400 mt-0.5 font-mono">
                            v{r.agent_version}
                            {r.os_platform && ` · ${r.os_platform}`}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${badge.cls}`}
                        >
                          {badge.label}
                        </span>
                        <div className="text-xs text-slate-400 mt-1">
                          {r.last_seen
                            ? `Last seen ${formatDistanceToNow(
                                new Date(r.last_seen),
                                { addSuffix: true },
                              )}`
                            : "Awaiting first heartbeat"}
                        </div>
                      </div>
                      <ChevronRight size={18} className="text-slate-400" />
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {showAdd && <AddEmployeeModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}

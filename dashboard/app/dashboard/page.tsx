"use client";

import { useQuery } from "@tanstack/react-query";
import { employeesApi, screenshotsApi } from "@/lib/api";
import { Users, Camera, HardDrive, Activity } from "lucide-react";
import { formatBytes, thumbUrl } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";

export default function OverviewPage() {
  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: employeesApi.list,
  });

  const { data: recent } = useQuery({
    queryKey: ["recent-screenshots"],
    queryFn: () => screenshotsApi.list({ page: 1, page_size: 12 }),
  });

  const totalSize = recent?.items.reduce((s, x) => s + (x.file_size || 0), 0) ?? 0;
  const activeCount = employees?.filter((e) => e.is_active).length ?? 0;

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Overview</h1>
        <p className="text-slate-500 text-sm">Snapshot of your team's activity</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          label="Active Employees"
          value={activeCount}
          color="text-blue-600 bg-blue-50"
        />
        <StatCard
          icon={Camera}
          label="Recent Screenshots"
          value={recent?.total ?? 0}
          color="text-emerald-600 bg-emerald-50"
        />
        <StatCard
          icon={HardDrive}
          label="Storage (recent)"
          value={formatBytes(totalSize)}
          color="text-amber-600 bg-amber-50"
        />
        <StatCard
          icon={Activity}
          label="Status"
          value="Operational"
          color="text-violet-600 bg-violet-50"
        />
      </div>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Recent screenshots</h2>
          <Link
            href="/dashboard/screenshots"
            className="text-sm text-brand-600 hover:underline"
          >
            View all →
          </Link>
        </div>

        {!recent?.items.length ? (
          <p className="text-sm text-slate-500">No screenshots yet.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {recent.items.map((s) => (
              <div
                key={s.id}
                className="bg-white rounded-lg overflow-hidden border hover:shadow-md transition"
              >
                <img
                  src={thumbUrl(s.file_url)}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="w-full h-32 object-cover bg-slate-100"
                />
                <div className="p-2 text-xs">
                  <div className="font-medium">
                    {employees?.find((e) => e.id === s.user_id)?.full_name ??
                      "Unknown"}
                  </div>
                  <div className="text-slate-500">
                    {formatDistanceToNow(new Date(s.captured_at), {
                      addSuffix: true,
                    })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: any;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl p-5 border">
      <div className={`inline-flex p-2 rounded-lg mb-3 ${color}`}>
        <Icon size={18} />
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  );
}

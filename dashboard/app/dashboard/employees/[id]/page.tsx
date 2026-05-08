"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { format, startOfDay, endOfDay, subDays } from "date-fns";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { employeesApi, screenshotsApi } from "@/lib/api";
import { ScreenshotModal } from "@/components/ScreenshotModal";
import { thumbUrl } from "@/lib/utils";

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [date, setDate] = useState(new Date());
  const [modalIdx, setModalIdx] = useState<number | null>(null);

  const { data: employee } = useQuery({
    queryKey: ["employee", id],
    queryFn: () => employeesApi.get(id),
    enabled: !!id,
  });

  const dateFrom = useMemo(() => startOfDay(date).toISOString(), [date]);
  const dateTo = useMemo(() => endOfDay(date).toISOString(), [date]);

  const { data: screenshots, isLoading } = useQuery({
    queryKey: ["screenshots", id, dateFrom, dateTo],
    queryFn: () =>
      screenshotsApi.list({
        employee_id: id,
        date_from: dateFrom,
        date_to: dateTo,
        page_size: 200,
      }),
    enabled: !!id,
  });

  const items = screenshots?.items ?? [];

  return (
    <div className="p-8 space-y-6">
      <Link
        href="/dashboard/employees"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft size={14} /> Back to employees
      </Link>

      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            {employee?.full_name || "Loading..."}
          </h1>
          <p className="text-slate-500 text-sm">{employee?.email}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setDate(subDays(date, 1))}
            className="px-3 py-1.5 border rounded-lg text-sm hover:bg-slate-50"
          >
            ← Prev day
          </button>
          <input
            type="date"
            value={format(date, "yyyy-MM-dd")}
            onChange={(e) => setDate(new Date(e.target.value))}
            className="px-3 py-1.5 border rounded-lg text-sm"
          />
          <button
            onClick={() => setDate(new Date())}
            className="px-3 py-1.5 border rounded-lg text-sm hover:bg-slate-50"
          >
            Today
          </button>
        </div>
      </div>

      <div className="bg-white border rounded-xl p-6">
        <h2 className="font-semibold mb-4">
          {format(date, "PPP")} — {items.length} screenshot(s)
        </h2>

        {isLoading ? (
          <p className="text-slate-500 text-sm">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-slate-500 text-sm">No screenshots for this day.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {items.map((s, idx) => (
              <button
                key={s.id}
                onClick={() => setModalIdx(idx)}
                className="bg-slate-50 rounded-lg overflow-hidden border hover:shadow-md hover:border-brand-300 transition group"
              >
                <img
                  src={thumbUrl(s.file_url, s.thumbnail_url)}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="w-full h-24 object-cover"
                />
                <div className="p-1.5 text-[11px] text-slate-600 group-hover:text-brand-700">
                  {format(new Date(s.captured_at), "HH:mm:ss")}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {modalIdx !== null && (
        <ScreenshotModal
          screenshots={items}
          index={modalIdx}
          onClose={() => setModalIdx(null)}
          onPrev={() => setModalIdx(Math.max(0, modalIdx - 1))}
          onNext={() => setModalIdx(Math.min(items.length - 1, modalIdx + 1))}
        />
      )}
    </div>
  );
}

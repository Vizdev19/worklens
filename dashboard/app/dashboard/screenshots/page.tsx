"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { format } from "date-fns";
import { employeesApi, screenshotsApi } from "@/lib/api";
import { ScreenshotModal } from "@/components/ScreenshotModal";
import { thumbUrl } from "@/lib/utils";

export default function AllScreenshotsPage() {
  const [employeeId, setEmployeeId] = useState<string>("");
  const [page, setPage] = useState(1);
  const [modalIdx, setModalIdx] = useState<number | null>(null);

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: employeesApi.list,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["all-screenshots", employeeId, page],
    queryFn: () =>
      screenshotsApi.list({
        employee_id: employeeId || undefined,
        page,
        page_size: 60,
      }),
  });

  const items = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 60);

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">All Screenshots</h1>
        <p className="text-slate-500 text-sm">
          {data?.total ?? 0} screenshot(s) total
        </p>
      </div>

      <div className="flex items-center gap-3">
        <select
          value={employeeId}
          onChange={(e) => {
            setEmployeeId(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 border rounded-lg text-sm"
        >
          <option value="">All employees</option>
          {employees?.map((e) => (
            <option key={e.id} value={e.id}>
              {e.full_name}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-slate-500 text-sm">Loading...</p>
      ) : items.length === 0 ? (
        <p className="text-slate-500 text-sm">No screenshots found.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {items.map((s, idx) => {
              const emp = employees?.find((e) => e.id === s.user_id);
              return (
                <button
                  key={s.id}
                  onClick={() => setModalIdx(idx)}
                  className="bg-white rounded-lg overflow-hidden border hover:shadow-md transition text-left"
                >
                  <img
                    src={thumbUrl(s.file_url, s.thumbnail_url)}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="w-full h-28 object-cover"
                  />
                  <div className="p-2 text-xs">
                    <div className="font-medium truncate">
                      {emp?.full_name || "—"}
                    </div>
                    <div className="text-slate-500">
                      {format(new Date(s.captured_at), "PP HH:mm")}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 border rounded-lg text-sm disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-sm text-slate-500">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 border rounded-lg text-sm disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

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

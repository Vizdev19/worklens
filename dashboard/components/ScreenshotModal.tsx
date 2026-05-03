"use client";

import { useEffect } from "react";
import { X, ChevronLeft, ChevronRight, Download } from "lucide-react";
import { format } from "date-fns";
import type { Screenshot } from "@/types/api";

export function ScreenshotModal({
  screenshots,
  index,
  onClose,
  onPrev,
  onNext,
}: {
  screenshots: Screenshot[];
  index: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}) {
  const current = screenshots[index];

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onPrev();
      if (e.key === "ArrowRight") onNext();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, onPrev, onNext]);

  if (!current) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center">
      <button
        onClick={onClose}
        className="absolute top-4 right-4 text-white p-2 hover:bg-white/10 rounded-full"
      >
        <X size={24} />
      </button>

      <button
        onClick={onPrev}
        disabled={index === 0}
        className="absolute left-4 text-white p-3 hover:bg-white/10 rounded-full disabled:opacity-30"
      >
        <ChevronLeft size={28} />
      </button>

      <div className="max-w-6xl max-h-[90vh] flex flex-col items-center gap-4 px-16">
        <img
          src={current.file_url}
          alt=""
          className="max-h-[80vh] rounded-lg shadow-2xl"
        />
        <div className="flex items-center gap-4 text-white text-sm">
          <span>{format(new Date(current.captured_at), "PPpp")}</span>
          <span className="text-white/50">•</span>
          <span>Monitor {current.monitor_index + 1}</span>
          <span className="text-white/50">•</span>
          <span className="capitalize">{current.os_platform || "—"}</span>
          <a
            href={current.file_url}
            download
            target="_blank"
            rel="noreferrer"
            className="ml-2 flex items-center gap-1 text-white/80 hover:text-white"
          >
            <Download size={14} /> Download
          </a>
        </div>
        <div className="text-white/60 text-xs">
          {index + 1} of {screenshots.length}
        </div>
      </div>

      <button
        onClick={onNext}
        disabled={index >= screenshots.length - 1}
        className="absolute right-4 text-white p-3 hover:bg-white/10 rounded-full disabled:opacity-30"
      >
        <ChevronRight size={28} />
      </button>
    </div>
  );
}

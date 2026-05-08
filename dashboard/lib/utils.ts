import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number | null) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Returns the pre-generated 400px thumbnail URL when available,
 * falling back to the full-resolution URL for older screenshots
 * that were captured before thumbnail generation was added.
 */
export function thumbUrl(fileUrl: string, thumbnailUrl?: string | null): string {
  return thumbnailUrl || fileUrl;
}

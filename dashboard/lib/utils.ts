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
 * Append Supabase Image Transformation params to a signed URL so we
 * fetch a small thumbnail instead of the full 1920px screenshot.
 *
 * Requires Supabase Pro plan or self-hosted. On free tier, the params
 * are silently ignored — the full image is still served. In that case
 * the only real fix is to generate thumbnails at upload time.
 *
 * Docs: https://supabase.com/docs/guides/storage/serving/image-transformations
 */
export function thumbUrl(url: string, width = 320): string {
  if (!url) return url;
  // Insert /render/image/sign/ for the transform endpoint
  // Supabase signed URLs look like:
  //   https://xxx.supabase.co/storage/v1/object/sign/<bucket>/<path>?token=...
  // Transform variant:
  //   https://xxx.supabase.co/storage/v1/render/image/sign/<bucket>/<path>?token=...&width=...
  try {
    const u = new URL(url);
    u.pathname = u.pathname.replace(
      "/storage/v1/object/sign/",
      "/storage/v1/render/image/sign/"
    );
    u.searchParams.set("width", String(width));
    u.searchParams.set("quality", "60");
    u.searchParams.set("resize", "contain");
    return u.toString();
  } catch {
    return url;
  }
}

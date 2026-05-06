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
 * Append Supabase Image Transformation params if the project is on a
 * plan that supports them. Currently we just return the original URL
 * — image transforms are a Pro-plan feature on Supabase, and silently
 * fail (400/404) on the free tier, leaving the dashboard with broken
 * thumbnails.
 *
 * Once you upgrade to Supabase Pro (or implement server-side thumbnail
 * generation in storage.py), flip ENABLE_TRANSFORMS to true.
 *
 * Docs: https://supabase.com/docs/guides/storage/serving/image-transformations
 */
const ENABLE_TRANSFORMS = false;

export function thumbUrl(url: string, width = 320): string {
  if (!url) return url;
  if (!ENABLE_TRANSFORMS) return url;

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

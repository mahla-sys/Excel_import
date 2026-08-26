import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * shadcn/ui helper for composing conditional class names with Tailwind
 * conflict resolution.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format an integer with Persian digits for display. */
export function toPersianDigits(value: number | string): string {
  const id = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
  return String(value).replace(/[0-9]/g, (d) => id[Number(d)]);
}

/** Format a numeric byte count as a human-readable Persian label. */
export function formatBytes(bytes: number): string {
  if (!bytes) return "۰ بایت";
  const units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const value = bytes / Math.pow(1024, i);
  return `${toPersianDigits(value.toFixed(value < 10 && i > 0 ? 1 : 0))} ${units[i]}`;
}

/** Mask a national ID for list views: show first 3 and last 2 digits. */
export function maskNationalId(value: string | null | undefined): string {
  if (!value) return "—";
  const digits = value.replace(/\D/g, "");
  if (digits.length < 6) return "••••";
  return `${digits.slice(0, 3)}•${"•".repeat(digits.length - 5)}${digits.slice(-2)}`;
}

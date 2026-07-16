import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind class merger. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format ISO date to vi-VN locale string. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const now = Date.now();
  const diff = d.getTime() - now;
  const abs = Math.abs(diff);
  const sign = diff < 0 ? -1 : 1;
  const rtf = new Intl.RelativeTimeFormat("vi", { numeric: "auto" });
  if (abs < 60_000) return rtf.format(sign * Math.round(diff / 1000), "second");
  if (abs < 3_600_000) return rtf.format(sign * Math.round(diff / 60_000), "minute");
  if (abs < 86_400_000) return rtf.format(sign * Math.round(diff / 3_600_000), "hour");
  return rtf.format(sign * Math.round(diff / 86_400_000), "day");
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return "0";
  return n.toLocaleString("vi-VN");
}

export function formatBytes(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
}

export function truncate(s: string | null | undefined, n = 80): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export const trunc = truncate;

export function uuid(): string {
  return crypto.randomUUID();
}
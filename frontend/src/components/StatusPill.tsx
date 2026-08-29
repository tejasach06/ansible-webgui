import type { JobStatus } from "../lib/types";

type Tier = "inflight" | "success" | "attention" | "bad" | "neutral";
const TIER: Record<JobStatus | "pending", Tier> = { pending: "neutral", queued: "inflight", running: "inflight", successful: "success", pending_approval: "attention", approved: "attention", failed: "bad", rejected: "bad", timed_out: "bad", canceled: "neutral" };
const LABEL: Record<JobStatus | "pending", string> = {
  pending: "Pending",
  queued: "Queued",
  running: "Running",
  successful: "Successful",
  pending_approval: "Awaiting approval",
  approved: "Approved",
  failed: "Failed",
  rejected: "Rejected",
  timed_out: "Timed out",
  canceled: "Canceled",
};
const cls: Record<Tier, string> = {
  inflight: "bg-sky-100 text-sky-900 dark:bg-sky-500/15 dark:text-sky-300",
  success: "bg-emerald-100 text-emerald-900 dark:bg-emerald-500/15 dark:text-emerald-300",
  attention: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300",
  bad: "bg-red-100 text-red-900 dark:bg-red-500/15 dark:text-red-300",
  neutral: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};
export function StatusPill({ status }: { status: JobStatus | "pending" }) { return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${cls[TIER[status]]}`}>{status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}{LABEL[status]}</span>; }

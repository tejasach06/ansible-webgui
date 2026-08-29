import type { JobDetail } from "./types";

export function runSummary(job: JobDetail | undefined): string {
  if (!job) return "";

  const snap = (job.params_snapshot ?? {}) as Record<string, unknown>;
  const ctx = job.context;

  const playbook = ctx?.playbook_rel_path || ctx?.playbook_name || "an unknown playbook";
  const target = snap.limit !== undefined && snap.limit !== null && String(snap.limit) !== "" ? String(snap.limit) : "all hosts";
  const inventory = ctx?.inventory_rel_path || ctx?.inventory_name || null;
  const mode = job.mode === "check" ? "check mode, nothing is changed" : "live mode, changes are applied";

  let res = `Runs ${playbook} against ${target}${inventory ? ` in ${inventory}` : ""} in ${mode}.`;

  if (snap.become) {
    res += ` Escalates privileges${snap.become_user ? ` as ${String(snap.become_user)}` : ""}.`;
  }

  if (typeof snap.tags === "string" && snap.tags.trim() !== "") {
    res += ` Limited to tags: ${snap.tags.trim()}.`;
  }

  return res;
}

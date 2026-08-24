import { useState } from "react";
import { useAudit } from "../api/audit";
import { DataTable } from "../components/DataTable";
import { TextInput } from "../components/Field";
import { Dialog } from "../components/Dialog";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Pagination } from "../components/Pagination";
import { KeyValueTable } from "../components/KeyValueTable";
import type { AuditItem } from "../lib/types";

const empty = { action: "", actor: "", object_type: "" };

function humanize(str?: string | null): string {
  if (!str) return "";
  return str
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function getActionBadgeClass(action: string): string {
  const act = action.toLowerCase();
  if (
    act.includes("delete") ||
    act.includes("reject") ||
    act.includes("fail") ||
    act.includes("cancel") ||
    act.includes("deactivate") ||
    act.includes("revoke")
  ) {
    return "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:border-rose-800/40";
  }
  if (
    act.includes("create") ||
    act.includes("register") ||
    act.includes("grant") ||
    act.includes("login_success")
  ) {
    return "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-800/40";
  }
  if (
    act.includes("update") ||
    act.includes("save") ||
    act.includes("approve") ||
    act.includes("rename") ||
    act.includes("rotate") ||
    act.includes("refresh")
  ) {
    return "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-800/40";
  }
  if (act.includes("request") || act.includes("relaunch") || act.includes("test")) {
    return "bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:border-sky-800/40";
  }
  return "bg-zinc-100 text-zinc-800 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700";
}

function formatObject(type?: string | null, id?: string | null): string {
  if (!type && !id) return "—";
  if (type && !id) return humanize(type);
  const map: Record<string, string> = {
    job_run: "Job Run",
    job_template: "Template",
    project: "Project",
    inventory: "Inventory",
    playbook: "Playbook",
    credential: "Credential",
    user: "User",
    notification: "Notification",
    schedule: "Schedule",
    pipeline: "Pipeline",
    pipeline_run: "Pipeline Run",
    project_membership: "Membership",
  };
  const label = map[type ?? ""] ?? humanize(type);
  return `${label} #${id}`;
}

function formatTimestamp(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function AuditPage() {
  const limit = 50;
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState(empty);
  const setFilter = (next: typeof empty) => {
    setFilters(next);
    setOffset(0);
  };
  const audit = useAudit({ ...filters, limit, offset });
  const [selectedItem, setSelectedItem] = useState<AuditItem | null>(null);

  return (
    <section className="grid gap-4">
      <PageHeader title="Audit" subtitle="Immutable record of every mutating action and security event." />
      <div className="grid gap-2 md:grid-cols-4">
        <TextInput
          id="actor"
          label="Actor"
          placeholder="Username, email, or ID..."
          value={filters.actor}
          onChange={(e) => setFilter({ ...filters, actor: e.target.value })}
        />
        <TextInput
          id="action"
          label="Action"
          placeholder="e.g. login, saved, created..."
          value={filters.action}
          onChange={(e) => setFilter({ ...filters, action: e.target.value })}
        />
        <TextInput
          id="obj"
          label="Object type"
          placeholder="e.g. project, inventory..."
          value={filters.object_type}
          onChange={(e) => setFilter({ ...filters, object_type: e.target.value })}
        />
        <div className="flex items-end">
          <Button variant="secondary" onClick={() => setFilter(empty)}>
            Clear filters
          </Button>
        </div>
      </div>
      <DataTable
        rows={audit.data?.items ?? []}
        loading={audit.isLoading}
        empty="No audit events found"
        columns={[
          {
            key: "created",
            header: "Timestamp",
            render: (r) => (
              <span title={r.created_at ?? ""} className="whitespace-nowrap text-xs text-zinc-600 dark:text-zinc-400">
                {formatTimestamp(r.created_at)}
              </span>
            ),
          },
          {
            key: "actor",
            header: "Actor",
            render: (r) => {
              if (r.actor_username) {
                return (
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-800 dark:bg-sky-900/60 dark:text-sky-200">
                      {r.actor_username.charAt(0).toUpperCase()}
                    </span>
                    <div className="flex flex-col min-w-0">
                      <span className="font-medium text-zinc-900 dark:text-zinc-100 truncate">
                        {r.actor_username}
                      </span>
                      {r.actor_email && (
                        <span className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                          {r.actor_email}
                        </span>
                      )}
                    </div>
                  </div>
                );
              }
              if (r.actor_user_id) {
                return (
                  <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                    User #{r.actor_user_id}
                  </span>
                );
              }
              return (
                <span className="inline-flex items-center rounded bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                  System
                </span>
              );
            },
          },
          {
            key: "action",
            header: "Action",
            render: (r) => (
              <span
                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${getActionBadgeClass(
                  r.action
                )}`}
              >
                {humanize(r.action)}
              </span>
            ),
          },
          {
            key: "object",
            header: "Target",
            render: (r) => (
              <span className="text-xs font-mono text-zinc-700 dark:text-zinc-300">
                {formatObject(r.object_type, r.object_id)}
              </span>
            ),
          },
          {
            key: "ip",
            header: "IP",
            render: (r) => (
              <span className="text-xs font-mono text-zinc-500 dark:text-zinc-400">
                {r.ip || "—"}
              </span>
            ),
          },
          {
            key: "detail",
            header: "Detail",
            render: (r) => (
              <Button size="sm" variant="secondary" onClick={() => setSelectedItem(r)}>
                View
              </Button>
            ),
          },
        ]}
      />
      {audit.data && <Pagination offset={offset} limit={limit} total={audit.data.total} onChange={setOffset} />}
      <Dialog open={!!selectedItem} onClose={() => setSelectedItem(null)} title="Audit Event Detail">
        {selectedItem && (
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900/50">
              <div>
                <span className="text-zinc-500 dark:text-zinc-400">Actor:</span>{" "}
                <span className="font-medium text-zinc-900 dark:text-zinc-100">
                  {selectedItem.actor_username
                    ? `${selectedItem.actor_username} (${selectedItem.actor_email ?? `ID: ${selectedItem.actor_user_id}`})`
                    : selectedItem.actor_user_id
                    ? `User #${selectedItem.actor_user_id}`
                    : "System"}
                </span>
              </div>
              <div>
                <span className="text-zinc-500 dark:text-zinc-400">Action:</span>{" "}
                <span className="font-medium text-zinc-900 dark:text-zinc-100">{humanize(selectedItem.action)}</span>
              </div>
              <div>
                <span className="text-zinc-500 dark:text-zinc-400">Target:</span>{" "}
                <span className="font-mono text-zinc-900 dark:text-zinc-100">
                  {formatObject(selectedItem.object_type, selectedItem.object_id)}
                </span>
              </div>
              <div>
                <span className="text-zinc-500 dark:text-zinc-400">IP Address:</span>{" "}
                <span className="font-mono text-zinc-900 dark:text-zinc-100">{selectedItem.ip || "—"}</span>
              </div>
              <div className="col-span-2">
                <span className="text-zinc-500 dark:text-zinc-400">Timestamp:</span>{" "}
                <span className="font-mono text-zinc-900 dark:text-zinc-100">{selectedItem.created_at || "—"}</span>
              </div>
            </div>
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                Payload & Metadata
              </h4>
              <KeyValueTable data={selectedItem.detail} empty="No additional payload recorded for this event." />
            </div>
          </div>
        )}
      </Dialog>
    </section>
  );
}

export default AuditPage;

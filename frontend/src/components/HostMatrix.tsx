import { DataTable } from "./DataTable";
import { StatusPill } from "./StatusPill";
import type { HostSummaryRow, JobStatus } from "../lib/types";

export interface HostMatrixData { hosts: HostSummaryRow[]; totals: Record<string, number> }

export function HostMatrix({ data, onJump }: { data?: HostMatrixData; onJump?: (counter: number) => void }) {
  const rows = [...(data?.hosts ?? [])].sort((a, b) => {
    const aBad = a.status === "failed" || a.status === "unreachable";
    const bBad = b.status === "failed" || b.status === "unreachable";
    return Number(bBad) - Number(aBad) || a.host.localeCompare(b.host);
  });
  const totals = data?.totals ?? {};

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap gap-2">
        {["ok", "changed", "failed", "unreachable", "skipped"].map((key) => (
          <span key={key} className="rounded bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800">
            {key}: {totals[key] ?? 0}
          </span>
        ))}
      </div>
      <DataTable
        rows={rows}
        empty="No host results yet"
        columns={[
          { key: "host", header: "Host", render: (r) => r.host },
          { key: "ok", header: "ok", render: (r) => r.ok },
          { key: "changed", header: "changed", render: (r) => r.changed },
          { key: "failed", header: "failed", render: (r) => r.failed },
          { key: "unreachable", header: "unreachable", render: (r) => r.unreachable },
          { key: "skipped", header: "skipped", render: (r) => r.skipped },
          { key: "status", header: "Status", render: (r) => <StatusPill status={(r.status === "unreachable" ? "failed" : r.status) as JobStatus} /> },
          { key: "jump", header: "Output", render: (r) => r.first_failure_counter && onJump ? <button className="text-xs underline" onClick={() => onJump(r.first_failure_counter!)}>first failure</button> : "—" },
        ]}
      />
    </div>
  );
}

export default HostMatrix;

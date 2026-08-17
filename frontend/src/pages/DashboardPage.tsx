import { Link } from "react-router-dom";
import { useJobAction, useJobSummary } from "../api/jobs";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { useAuth } from "../lib/auth";
import { linkClass } from "../lib/cn";
import type { JobListItem } from "../lib/types";

function ApproveButton({ id }: { id: number }) {
  const approve = useJobAction(id, "approve");
  return <Button size="sm" loading={approve.isPending} onClick={() => approve.mutate({ approval_note: "" })}>Approve</Button>;
}

export function DashboardPage() {
  const { canAny } = useAuth();
  const summary = useJobSummary();
  const data = summary.data;
  const counts = data?.last_7_days ?? { successful: 0, failed: 0, canceled: 0 };
  const tiles = [
    { label: "Running / queued", value: data?.running ?? 0 },
    { label: "Successful last 7 days", value: counts.successful ?? 0 },
    { label: "Failed last 7 days", value: counts.failed ?? 0 },
    { label: "Canceled last 7 days", value: counts.canceled ?? 0 },
  ];

  return (
    <section className="grid gap-6">
      <PageHeader title="Dashboard" subtitle="Live run activity and the approvals waiting on you." />
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-4 dark:bg-zinc-800">
        {tiles.map(({ label, value }) => (
          <div key={label} className="bg-white p-4 dark:bg-zinc-950">
            <dt className="text-sm text-zinc-500 dark:text-zinc-400">{label}</dt>
            <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <Section title="Needs approval">
        <DataTable
          rows={data?.pending_approval ?? []}
          loading={summary.isLoading}
          empty={<EmptyState>No runs need approval.</EmptyState>}
          columns={[
            { key: "id", header: "Run", render: (r: JobListItem) => <Link className={linkClass} to={`/jobs/${r.id}`}>#{r.id}</Link> },
            { key: "mode", header: "Mode", render: (r) => r.mode },
            { key: "requested", header: "Requested by", render: (r) => r.requested_by },
            { key: "created", header: "Created", render: (r) => r.created_at },
            { key: "actions", header: "Actions", render: (r) => canAny("job.approve") && <ApproveButton id={r.id} /> },
          ]}
        />
      </Section>
      <Section title="Recent runs">
        <DataTable
          rows={data?.recent ?? []}
          loading={summary.isLoading}
          empty={<EmptyState>No recent runs.</EmptyState>}
          columns={[
            { key: "id", header: "Run", render: (r: JobListItem) => <Link className={linkClass} to={`/jobs/${r.id}`}>#{r.id}</Link> },
            { key: "status", header: "Status", render: (r: JobListItem) => <StatusPill status={r.status} /> },
            { key: "mode", header: "Mode", render: (r) => r.mode },
            { key: "finished", header: "Finished", render: (r) => r.finished_at ?? "-" },
          ]}
        />
      </Section>
    </section>
  );
}

export default DashboardPage;

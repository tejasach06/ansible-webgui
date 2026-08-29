import { Link } from "react-router-dom";
import { useJobSummary } from "../api/jobs";
import { ErrorBanner } from "../components/ErrorBanner";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusPill } from "../components/StatusPill";
import { ModeBadge } from "../components/ModeBadge";
import { useAuth } from "../lib/auth";
import { linkClass } from "../lib/cn";
import type { JobListItem } from "../lib/types";
import { formatTimestamp } from "../lib/time";

export function DashboardPage() {
  const { canAny } = useAuth();
  const summary = useJobSummary();
  const data = summary.data;
  const failed = !!summary.error;
  const counts = data?.last_7_days ?? { successful: 0, failed: 0, canceled: 0 };
  const tiles = [
    { label: "Running / queued", value: failed ? null : data?.running ?? 0 },
    { label: "Successful last 7 days", value: failed ? null : counts.successful ?? 0 },
    { label: "Failed last 7 days", value: failed ? null : counts.failed ?? 0 },
    { label: "Canceled last 7 days", value: failed ? null : counts.canceled ?? 0 },
  ];

  return (
    <section className="grid gap-6">
      <PageHeader title="Dashboard" subtitle="Live run activity and the approvals waiting on you." />
      {summary.error && <ErrorBanner error={summary.error} />}
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-4 dark:bg-zinc-800">
        {tiles.map(({ label, value }) => (
          <div key={label} className="bg-white p-4 dark:bg-zinc-950">
            <dt className="text-sm text-zinc-500 dark:text-zinc-400">{label}</dt>
            <dd className="mt-2 font-mono text-2xl font-semibold tabular-nums">{value ?? "—"}</dd>
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
            { key: "mode", header: "Mode", render: (r) => <ModeBadge mode={r.mode} /> },
            { key: "requested", header: "Requested by", render: (r) => r.requested_by },
            { key: "created", header: "Created", render: (r) => <span title={r.created_at ?? undefined}>{formatTimestamp(r.created_at)}</span> },
            { key: "actions", header: "Actions", render: (r: JobListItem) =>
                canAny("job.approve")
                  ? <Link className={linkClass} to={`/approvals/${r.id}`}>Review</Link>
                  : <span className="text-fg-muted" title="Your role cannot approve runs.">—</span> },
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
            { key: "mode", header: "Mode", render: (r) => <ModeBadge mode={r.mode} /> },
            { key: "finished", header: "Finished", render: (r: JobListItem) => <span title={r.finished_at ?? undefined}>{formatTimestamp(r.finished_at)}</span> },
          ]}
        />
      </Section>
    </section>
  );
}

export default DashboardPage;

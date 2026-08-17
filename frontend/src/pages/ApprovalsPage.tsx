import { Link } from "react-router-dom";
import { useJobs } from "../api/jobs";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { ErrorBanner } from "../components/ErrorBanner";
import { StatusPill } from "../components/StatusPill";
import { linkClass } from "../lib/cn";
import type { JobListItem } from "../lib/types";

export function ApprovalsPage() {
  const jobs = useJobs(50, 0, "pending_approval");

  return (
    <section className="grid gap-4">
      <PageHeader title="Approvals" subtitle="Review pending live job requests before execution." />
      {jobs.error && <ErrorBanner error={jobs.error} />}
      <DataTable<JobListItem>
        rows={jobs.data?.items ?? []}
        loading={jobs.isLoading}
        empty="No pending approvals"
        columns={[
          { key: "id", header: "Job", render: (r) => <Link className={linkClass} to={`/jobs/${r.id}`}>#{r.id}</Link> },
          { key: "status", header: "Status", render: (r) => <StatusPill status={r.status} /> },
          { key: "mode", header: "Mode", render: (r) => r.mode },
          { key: "requested_by", header: "Requested by", render: (r) => r.requested_by },
          { key: "created_at", header: "Created", render: (r) => r.created_at ?? "-" },
          { key: "review", header: "", render: (r) => <Link className={linkClass} to={`/approvals/${r.id}`}>Review</Link> },
        ]}
      />
    </section>
  );
}

export default ApprovalsPage;

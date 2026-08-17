import { Link } from "react-router-dom";
import { useJob, useJobAction, useJobs } from "../api/jobs";
import { Button } from "../components/Button";
import { DataTable } from "../components/DataTable";
import { ErrorBanner } from "../components/ErrorBanner";
import { OverrideDiff } from "../components/OverrideDiff";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { useAuth } from "../lib/auth";
import type { JobListItem } from "../lib/types";

function ApprovalActions({ job }: { job: JobListItem }) {
  const { user, can } = useAuth();
  const { toast } = useToast();
  const detail = useJob(job.id);
  const approve = useJobAction(job.id, "approve");
  const reject = useJobAction(job.id, "reject");
  const selfApproval = user?.id === job.requested_by;

  return (
    <div className="grid min-w-[360px] gap-3">
      {detail.error && <ErrorBanner error={detail.error} />}
      {(approve.error || reject.error) && <ErrorBanner error={approve.error || reject.error} />}
      <OverrideDiff overrides={detail.data?.overrides} />
      {selfApproval && <p className="text-xs text-zinc-500 dark:text-zinc-400">You cannot approve your own request.</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!can("job.approve") || selfApproval}
          loading={approve.isPending}
          onClick={() => approve.mutate({ approval_note: null }, { onSuccess: () => toast(`Approved job #${job.id}`) })}
        >
          Approve
        </Button>
        <Button
          size="sm"
          variant="danger"
          disabled={!can("job.approve")}
          loading={reject.isPending}
          onClick={() => reject.mutate(undefined, { onSuccess: () => toast(`Rejected job #${job.id}`) })}
        >
          Reject
        </Button>
      </div>
    </div>
  );
}

export function ApprovalsPage() {
  const jobs = useJobs(50, 0, "pending_approval");

  return (
    <section className="grid gap-4">
      <div>
        <h1 className="text-xl font-semibold">Approvals</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Review pending live job requests before execution.</p>
      </div>
      {jobs.error && <ErrorBanner error={jobs.error} />}
      <DataTable<JobListItem>
        rows={jobs.data?.items ?? []}
        loading={jobs.isLoading}
        empty="No pending approvals"
        columns={[
          { key: "id", header: "Job", render: (r) => <Link className="underline" to={`/jobs/${r.id}`}>#{r.id}</Link> },
          { key: "status", header: "Status", render: (r) => <StatusPill status={r.status} /> },
          { key: "mode", header: "Mode", render: (r) => r.mode },
          { key: "requested_by", header: "Requested by", render: (r) => r.requested_by },
          { key: "created_at", header: "Created", render: (r) => r.created_at ?? "—" },
          { key: "overrides", header: "Overrides / Decision", render: (r) => <ApprovalActions job={r} /> },
        ]}
      />
    </section>
  );
}

export default ApprovalsPage;

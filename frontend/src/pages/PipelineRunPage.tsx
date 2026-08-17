import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { JobStatus, PipelineRunDetail, PipelineStatus } from "../lib/types";
import { Button } from "../components/Button";
import { ErrorBanner } from "../components/ErrorBanner";

const statusClass: Record<PipelineStatus | JobStatus | "pending", string> = {
  pending: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  pending_approval: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300",
  approved: "bg-teal-100 text-teal-900 dark:bg-teal-500/15 dark:text-teal-300",
  queued: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  running: "bg-blue-100 text-blue-900 dark:bg-blue-500/15 dark:text-blue-300",
  successful: "bg-emerald-100 text-emerald-900 dark:bg-emerald-500/15 dark:text-emerald-300",
  failed: "bg-red-100 text-red-900 dark:bg-red-500/15 dark:text-red-300",
  rejected: "bg-rose-100 text-rose-900 dark:bg-rose-500/15 dark:text-rose-300",
  canceled: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  timed_out: "bg-orange-100 text-orange-900 dark:bg-orange-500/15 dark:text-orange-300",
};

function Pill({ status }: { status: PipelineStatus | JobStatus | "pending" }) {
  return <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${statusClass[status]}`}>{status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}{status}</span>;
}

export function PipelineRunPage() {
  const runId = Number(useParams().runId);
  const queryClient = useQueryClient();
  const run = useQuery({
    queryKey: ["pipeline-run", runId],
    queryFn: () => apiFetch<PipelineRunDetail>(`/api/pipelines/runs/${runId}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["successful", "failed", "canceled"].includes(status) ? false : 3000;
    },
  });
  const approve = useMutation({
    mutationFn: (jobId: number) => apiFetch(`/api/jobs/${jobId}/approve`, { method: "POST", body: JSON.stringify({ approval_note: "" }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pipeline-run", runId] }),
  });
  const cancel = useMutation({
    mutationFn: () => apiFetch(`/api/pipelines/runs/${runId}/cancel`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pipeline-run", runId] }),
  });

  const data = run.data;
  const canCancel = data && ["pending_approval", "queued", "running"].includes(data.status);

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Pipeline run {runId} {data && <Pill status={data.status} />}</h1>
        {canCancel && <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</Button>}
      </div>
      {run.error && <ErrorBanner error={run.error} />}
      {approve.error && <ErrorBanner error={approve.error} />}
      {cancel.error && <ErrorBanner error={cancel.error} />}
      {data && (
        <>
          <div className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
            <dl className="grid gap-2 md:grid-cols-2">
              <div className="flex gap-2"><dt className="font-medium">Pipeline:</dt><dd>{data.pipeline_id ? `#${data.pipeline_id}` : "—"}</dd></div>
              <div className="flex gap-2"><dt className="font-medium">Requested by:</dt><dd>{data.requested_by}</dd></div>
              <div className="flex gap-2"><dt className="font-medium">Current step:</dt><dd>{data.current_position + 1}</dd></div>
              <div className="flex gap-2"><dt className="font-medium">Created:</dt><dd>{data.created_at ?? "—"}</dd></div>
              <div className="flex gap-2"><dt className="font-medium">Started:</dt><dd>{data.started_at ?? "—"}</dd></div>
              <div className="flex gap-2"><dt className="font-medium">Finished:</dt><dd>{data.finished_at ?? "—"}</dd></div>
            </dl>
          </div>
          <div className="grid gap-2">
            {data.steps.map((step) => (
              <div key={step.position} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <div className="min-w-0">
                  <div className="text-xs text-zinc-500">Step {step.position + 1}</div>
                  <div className="font-medium">{step.template_name}</div>
                  {step.job_run_id ? <Link className="text-sm underline" to={`/jobs/${step.job_run_id}`}>Job #{step.job_run_id}</Link> : <div className="text-sm text-zinc-500">No child job yet</div>}
                </div>
                <div className="flex items-center gap-2">
                  <Pill status={step.status} />
                  {step.status === "pending_approval" && step.job_run_id && <Button size="sm" loading={approve.isPending} onClick={() => approve.mutate(step.job_run_id!)}>Approve</Button>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export default PipelineRunPage;

import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { PipelineRunDetail } from "../lib/types";
import { StatusPill } from "../components/StatusPill";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { linkClass } from "../lib/cn";

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
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({ queryKey: ["pipeline-run", runId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
  const cancel = useMutation({
    mutationFn: () => apiFetch(`/api/pipelines/runs/${runId}/cancel`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline-run", runId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job"] });
    },
  });

  const data = run.data;
  const canCancel = data && ["pending_approval", "queued", "running"].includes(data.status);
  const rows = [
    ["Pipeline", data?.pipeline_id ? `#${data.pipeline_id}` : "-"],
    ["Requested by", data?.requested_by ?? "-"],
    ["Current step", data ? `${data.current_position + 1}` : "-"],
    ["Created", data?.created_at ?? "-"],
    ["Started", data?.started_at ?? "-"],
    ["Finished", data?.finished_at ?? "-"],
  ];

  return (
    <section className="grid gap-4">
      <PageHeader
        title={`Pipeline run ${runId}`}
        subtitle="Step-by-step execution of a pipeline definition."
        status={data && <StatusPill status={data.status} />}
        actions={canCancel && <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>Cancel</Button>}
      />
      {run.error && <ErrorBanner error={run.error} />}
      {approve.error && <ErrorBanner error={approve.error} />}
      {cancel.error && <ErrorBanner error={cancel.error} />}
      {data && (
        <>
          <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">
            {rows.map(([key, value]) => (
              <div key={key} className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">{key}</dt>
                <dd className="mt-0.5 font-mono">{String(value)}</dd>
              </div>
            ))}
          </dl>
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {data.steps.map((step) => (
              <div key={step.position} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">Step {step.position + 1}</div>
                  <div className="font-medium">{step.template_name}</div>
                  {step.job_run_id ? <Link className={`text-sm ${linkClass}`} to={`/jobs/${step.job_run_id}`}>Job #{step.job_run_id}</Link> : <div className="text-sm text-zinc-500 dark:text-zinc-400">No child job yet</div>}
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={step.status} />
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

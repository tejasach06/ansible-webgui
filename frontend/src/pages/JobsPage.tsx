import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCancelJob, useJob, useJobs, useLaunchJob } from "../api/jobs";
import { usePlaybooks } from "../api/playbooks";
import { useTemplates } from "../api/templates";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { Drawer } from "../components/Drawer";
import { ErrorBanner } from "../components/ErrorBanner";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { buildLaunchBody, init, JobLaunchForm, surveyComplete } from "../components/JobLaunchForm";
import { Pagination } from "../components/Pagination";
import { Select } from "../components/Field";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { useAuth } from "../lib/auth";
import { linkClass } from "../lib/cn";
import type { JobListItem, JobMode, JobStatus } from "../lib/types";
import { TERMINAL_JOB_STATUSES } from "../lib/types";

const statuses: JobStatus[] = ["pending_approval", "approved", "rejected", "queued", "running", "successful", "failed", "canceled", "timed_out"];

export function JobsPage() {
  const { canAny, canInProject } = useAuth();
  const { toast } = useToast();
  const nav = useNavigate();
  const limit = 50;
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<JobStatus | "">("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(init);
  const [extraError, setExtraError] = useState("");
  const [relaunchId, setRelaunchId] = useState<number>();
  const [cancelTarget, setCancelTarget] = useState<JobListItem>();
  const first = useRef<HTMLSelectElement>(null);
  const jobs = useJobs(limit, offset, status || undefined);
  const templates = useTemplates();
  const playbooks = usePlaybooks();
  const launch = useLaunchJob();
  const cancelJob = useCancelJob();
  const relaunch = useJob(relaunchId ?? 0, !!relaunchId);

  useEffect(() => {
    if (relaunch.data?.params_snapshot) {
      const p = relaunch.data.params_snapshot;
      setForm({
        ...init,
        template_id: String(relaunch.data.template_id ?? ""),
        playbook_id: String(relaunch.data.playbook_id),
        inventory_id: String(relaunch.data.inventory_id),
        mode: (p.mode as JobMode) ?? "check",
        limit: String(p.limit ?? ""),
        tags: String(p.tags ?? ""),
        skip_tags: String(p.skip_tags ?? ""),
        verbosity: Number(p.verbosity ?? 0),
        forks: Number(p.forks ?? 5),
        become: Boolean(p.become),
        become_user: String(p.become_user ?? ""),
        become_method: String(p.become_method ?? ""),
        credential_ids: Array.isArray(p.credential_ids) ? (p.credential_ids as number[]) : [],
        extra_vars: JSON.stringify(p.extra_vars ?? {}, null, 2),
        diff: Boolean(p.diff),
        survey_answers: {},
      });
      setOpen(true);
    }
  }, [relaunch.data]);

  const close = () => {
    setOpen(false);
    setForm(init);
    setExtraError("");
    setRelaunchId(undefined);
  };

  const pickTemplate = (id: string) => {
    const t = templates.data?.find((x) => String(x.id) === id);
    setForm({
      ...form,
      template_id: id,
      playbook_id: t ? String(t.playbook_id) : form.playbook_id,
      inventory_id: t ? String(t.inventory_id) : form.inventory_id,
      mode: t ? "live" : form.mode,
      limit: t?.limit_pattern ?? "",
      tags: t?.tags ?? "",
      skip_tags: t?.skip_tags ?? "",
      verbosity: t?.verbosity ?? form.verbosity,
      forks: t?.forks ?? form.forks,
      credential_ids: t ? t.credential_ids : form.credential_ids,
      extra_vars: JSON.stringify(t?.extra_vars ?? {}, null, 2),
      diff: t?.diff_mode ?? form.diff,
      survey_answers: {},
    });
  };

  const submit = () => {
    const body = buildLaunchBody(form);
    if (!body) {
      setExtraError("Extra vars must be a JSON object, for example {}");
      return;
    }
    launch.mutate(body, {
      onSuccess: (r) => {
        close();
        nav(`/jobs/${r.id}`);
      },
    });
  };

  const selectedTemplate = templates.data?.find((x) => String(x.id) === form.template_id);
  const selectedPlaybook = playbooks.data?.find((p) => String(p.id) === form.playbook_id);
  const adHocAllowed = !!selectedTemplate || !selectedPlaybook || canInProject(selectedPlaybook.project_id, "project.admin");
  const valid = !!form.playbook_id && adHocAllowed && surveyComplete(form, selectedTemplate?.survey_spec);

  return (
    <section className="grid gap-4">
      <PageHeader
        title="Jobs"
        subtitle="Every run, filtered by status."
        actions={canAny("job.request") && <Button onClick={() => setOpen(true)}>Launch job</Button>}
      />
      <Select
        id="status"
        label="Status filter"
        value={status}
        onChange={(e) => {
          setStatus(e.target.value as JobStatus | "");
          setOffset(0);
        }}
      >
        <option value="">All</option>
        {statuses.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </Select>
      {(jobs.error || launch.error || cancelJob.error) && <ErrorBanner error={jobs.error || launch.error || cancelJob.error} />}
      <DataTable<JobListItem>
        rows={jobs.data?.items ?? []}
        loading={jobs.isLoading}
        empty="No jobs"
        columns={[
          { key: "id", header: "ID", render: (r) => <Link className={linkClass} to={`/jobs/${r.id}`}>#{r.id}</Link> },
          { key: "status", header: "Status", render: (r) => <StatusPill status={r.status} /> },
          { key: "mode", header: "Mode", render: (r) => r.mode },
          { key: "created", header: "Created", render: (r) => r.created_at },
          {
            key: "actions",
            header: "Actions",
            render: (r) => (
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => nav(`/jobs/${r.id}`)}>
                  Open
                </Button>
                {canAny("job.cancel") && !TERMINAL_JOB_STATUSES.includes(r.status) && (
                  <Button size="sm" variant="danger" onClick={() => setCancelTarget(r)}>
                    Cancel
                  </Button>
                )}
                {TERMINAL_JOB_STATUSES.includes(r.status) && (
                  <Button size="sm" variant="secondary" onClick={() => setRelaunchId(r.id)}>
                    Relaunch
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />
      {jobs.data && <Pagination offset={offset} limit={limit} total={jobs.data.total} onChange={setOffset} />}
      <ConfirmDialog
        open={!!cancelTarget}
        title="Cancel job"
        name={`#${cancelTarget?.id}`}
        loading={cancelJob.isPending}
        onClose={() => setCancelTarget(undefined)}
        onConfirm={() =>
          cancelTarget &&
          cancelJob.mutate(cancelTarget.id, {
            onSuccess: () => {
              setCancelTarget(undefined);
              toast("Job canceled");
            },
          })
        }
      />
      <Drawer
        open={open}
        onClose={close}
        title={relaunchId ? "Relaunch job" : "Launch job"}
        initialFocusRef={first}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button disabled={!valid} loading={launch.isPending} onClick={submit}>
              Launch
            </Button>
          </div>
        }
      >
        <JobLaunchForm
          form={form}
          setForm={setForm}
          extraError={extraError}
          setExtraError={setExtraError}
          firstRef={first}
          onTemplateChange={pickTemplate}
          onNewInventory={() => undefined}
        />
      </Drawer>
    </section>
  );
}

export default JobsPage;

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLaunchJob } from "../api/jobs";
import { usePlaybooks } from "../api/playbooks";
import { useProjects } from "../api/projects";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { EmptyState } from "./EmptyState";
import { ErrorBanner } from "./ErrorBanner";
import { Select } from "./Field";
import { buildLaunchBody, init, JobLaunchForm, type LaunchForm } from "./JobLaunchForm";
import { useAuth } from "../lib/auth";
import { useToast } from "./Toast";

export function RunJobDialog({ open, onClose, playbookId, projectId, extraVarsText }: { open: boolean; onClose: () => void; playbookId?: number; projectId?: number; extraVarsText?: string }) {
  const nav = useNavigate();
  const { toast } = useToast();
  const { canInProject } = useAuth();
  const first = useRef<HTMLSelectElement>(null);
  const [form, setForm] = useState<LaunchForm>({ ...init, credential_ids: [] });
  const [extraError, setExtraError] = useState("");
  const [selectedPlaybook, setSelectedPlaybook] = useState("");
  const playbooks = usePlaybooks(projectId);
  const projects = useProjects();
  const currentProject = projects.data?.find((p) => p.id === projectId);
  const launch = useLaunchJob();
  const needsPlaybookSelection = !!projectId && !playbookId;
  const ready = !needsPlaybookSelection || !!selectedPlaybook;
  const adHocAllowed = projectId ? canInProject(projectId, "project.admin") : false;
  const valid = ready && !!form.playbook_id && adHocAllowed;

  useEffect(() => {
    if (!open) return;
    const fixed = playbookId ? String(playbookId) : "";
    setSelectedPlaybook(fixed);
    const defaultInv = currentProject?.default_inventory_id ? String(currentProject.default_inventory_id) : "";
    const initialVars = extraVarsText !== undefined ? extraVarsText : init.extra_vars;
    setForm({ ...init, extra_vars: initialVars, credential_ids: [], playbook_id: fixed, inventory_id: defaultInv });
    setExtraError("");
    launch.reset();
  }, [open, playbookId, projectId, currentProject, extraVarsText]);

  const close = () => {
    onClose();
    setForm({ ...init, credential_ids: [] });
    setSelectedPlaybook("");
    setExtraError("");
    launch.reset();
  };

  const choosePlaybook = (id: string) => {
    setSelectedPlaybook(id);
    setForm((f) => ({ ...f, playbook_id: id }));
  };

  const submit = () => {
    const body = buildLaunchBody(form);
    if (!body) {
      setExtraError("Extra vars must be a JSON object, for example {}");
      return;
    }
    launch.mutate(body, {
      onSuccess: (job) => {
        toast(`Job #${job.id} ${job.status}`);
        close();
        nav(`/jobs/${job.id}`);
      },
    });
  };

  return (
    <Dialog open={open} onClose={close} title="Run playbook" size="full" initialFocusRef={first}>
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        {(playbooks.error || launch.error) && <ErrorBanner error={playbooks.error || launch.error} />}
        {!adHocAllowed && <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">Ad-hoc launches without a template are restricted to project admins.</p>}
        {needsPlaybookSelection && !selectedPlaybook ? (
          <div className="grid max-w-2xl gap-4">
            {(playbooks.data?.length ?? 0) === 0 && !playbooks.isLoading ? <EmptyState>No playbooks registered.</EmptyState> : null}
            <Select ref={first} id="run-playbook" label="Playbook" value={selectedPlaybook} onChange={(e) => choosePlaybook(e.target.value)}>
              <option value="">Select playbook</option>
              {playbooks.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-auto pr-1">
            <JobLaunchForm form={form} setForm={setForm} extraError={extraError} setExtraError={setExtraError} lockPlaybook firstRef={first} onNewInventory={() => undefined} />
          </div>
        )}
        <div className="flex shrink-0 justify-end gap-2">
          <Button variant="secondary" onClick={close}>Cancel</Button>
          <Button disabled={!valid} loading={launch.isPending} onClick={submit}>Launch</Button>
        </div>
      </div>
    </Dialog>
  );
}

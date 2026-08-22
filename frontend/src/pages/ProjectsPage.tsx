import { useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { Link, useNavigate } from "react-router-dom";
import { linkClass } from "../lib/cn";
import { Pencil, Play, Plus } from "lucide-react";
import { useCreatePlaybooks, usePlaybooks } from "../api/playbooks";
import { useCreateProjects, useDeleteProjects, useProjects, useUpdateProject } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { useToast } from "../components/Toast";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { Drawer } from "../components/Drawer";
import { Dialog } from "../components/Dialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Checkbox, TextInput } from "../components/Field";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState } from "../components/EmptyState";
import { PLAYBOOK_STARTERS, playbookEditorOptions, slugPath } from "../components/PlaybookStarter";
import { RunJobDialog } from "../components/RunJobDialog";
import type { ApiError } from "../lib/api";
import type { Playbook, Project } from "../lib/types";

type ProjectStep = 0 | 1 | 2;

const PROJECT_NAME_RE = /^[A-Za-z0-9._-]{1,64}$/;
const PROJECT_NAME_ERROR = "1-64 chars of letters, digits, dot, dash or underscore";
export function ProjectsPage() {
  const nav = useNavigate();
  const { can, canInProject } = useAuth();
  const { toast } = useToast();
  const { effectiveTheme } = useTheme();
  const list = useProjects();
  const playbooks = usePlaybooks();
  const create = useCreateProjects();
  const createPlaybook = useCreatePlaybooks();
  const del = useDeleteProjects();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<ProjectStep>(0);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<Project>();
  const [addFirst, setAddFirst] = useState(true);
  const [firstPlaybook, setFirstPlaybook] = useState({ name: "", rel_path: "" });
  const [pathTouched, setPathTouched] = useState(false);
  const [contentTouched, setContentTouched] = useState(false);
  const [starter, setStarter] = useState("ping");
  const [content, setContent] = useState("");
  const [createdPlaybook, setCreatedPlaybook] = useState<Playbook>();
  const [target, setTarget] = useState<Project>();
  const [runProject, setRunProject] = useState<Project>();
  const [edit, setEdit] = useState<Project>();
  const [editForm, setEditForm] = useState({ name: "", default_branch: "" });
  const updateEdit = useUpdateProject(edit?.id ?? 0);
  const first = useRef<HTMLInputElement>(null);
  const editFirst = useRef<HTMLInputElement>(null);
  const nameError = name && !PROJECT_NAME_RE.test(name) ? PROJECT_NAME_ERROR : "";
  const validName = PROJECT_NAME_RE.test(name);
  const validFirstPlaybook = Boolean(firstPlaybook.name.trim() && firstPlaybook.rel_path.trim());
  const lintError = (createPlaybook.error as ApiError | undefined)?.code === "lint_error" ? String((createPlaybook.error as ApiError).detail?.stderr ?? "") : "";
  const projectPlaybookCounts = new Map<number, number>();
  (playbooks.data ?? []).forEach(pb => projectPlaybookCounts.set(pb.project_id, (projectPlaybookCounts.get(pb.project_id) ?? 0) + 1));
  const resetWizard = () => {
    setStep(0);
    setName("");
    setCreated(undefined);
    setAddFirst(true);
    setFirstPlaybook({ name: "", rel_path: "" });
    setPathTouched(false);
    setContentTouched(false);
    setStarter("ping");
    setContent("");
    setCreatedPlaybook(undefined);
    create.reset();
    createPlaybook.reset();
  };
  const close = () => { setOpen(false); resetWizard(); };
  const openCreate = () => { resetWizard(); setOpen(true); };
  const primeFirstPlaybook = () => {
    const initial = "site";
    setFirstPlaybook({ name: initial, rel_path: slugPath(initial) });
    setPathTouched(false);
    setContentTouched(false);
    setContent((PLAYBOOK_STARTERS.find(s => s.id === starter) ?? PLAYBOOK_STARTERS[0]).build(initial));
  };
  const createProject = async () => {
    if (!validName) return;
    try {
      const project = await create.mutateAsync({ name });
      setCreated(project);
      primeFirstPlaybook();
      setStep(1);
    } catch {
      /* ErrorBanner renders mutation error. */
    }
  };
  const setFirstPlaybookName = (nextName: string) => {
    setFirstPlaybook(f => ({ ...f, name: nextName, rel_path: pathTouched ? f.rel_path : slugPath(nextName) }));
    if (!contentTouched) setContent((PLAYBOOK_STARTERS.find(s => s.id === starter) ?? PLAYBOOK_STARTERS[0]).build(nextName));
  };
  const setFirstPlaybookPath = (rel_path: string) => {
    setPathTouched(true);
    setFirstPlaybook(f => ({ ...f, rel_path }));
  };
  const setStarterId = (id: string) => {
    setStarter(id);
    if (!contentTouched) setContent((PLAYBOOK_STARTERS.find(s => s.id === id) ?? PLAYBOOK_STARTERS[0]).build(firstPlaybook.name));
  };
  const submitFirstPlaybook = async () => {
    if (!created || !validFirstPlaybook) return;
    createPlaybook.reset();
    try {
      const playbook = await createPlaybook.mutateAsync({
        project_id: created.id,
        name: firstPlaybook.name,
        rel_path: firstPlaybook.rel_path,
        content,
        message: `Create playbook ${firstPlaybook.name}`,
      });
      setCreatedPlaybook(playbook);
      toast("Playbook created");
      setStep(2);
    } catch {
      /* Project is kept; ErrorBanner renders mutation error. */
    }
  };
  const openEdit = (p: Project) => { setEdit(p); setEditForm({ name: p.name, default_branch: p.default_branch }); };
  const closeEdit = () => setEdit(undefined);
  return <section className="grid gap-4">
    <PageHeader
      title="Projects"
      subtitle="Git-backed content repositories for playbooks, roles, and inventories."
      actions={can("project.create") && <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={openCreate}>Create project</Button>}
    />
    {(list.error || playbooks.error || del.error || updateEdit.error) && <ErrorBanner error={list.error || playbooks.error || del.error || updateEdit.error} />}
    <DataTable<Project> rows={list.data?.filter(p => !p.is_inventory_repo) ?? []} loading={list.isLoading} empty={<EmptyState>No projects yet. Create a project to sync content.</EmptyState>} columns={[
      { key: "name", header: "Name", render: r => <Link className={`font-medium ${linkClass}`} to={`/projects/${r.id}`}>{r.name}</Link> },
      { key: "git_path", header: "Git path", render: r => r.git_path },
      { key: "default_branch", header: "Default branch", render: r => r.default_branch },
      { key: "actions", header: "Actions", render: r => { const runTitle = (projectPlaybookCounts.get(r.id) ?? 0) === 0 ? "No playbooks registered" : undefined; const canRunJob = canInProject(r.id, "job.request") || canInProject(r.id, "job.run_check"); return <div className="flex gap-2">{canRunJob && <Button size="sm" variant="secondary" icon={<Play size={14} />} disabled={!!runTitle} title={runTitle} onClick={() => setRunProject(r)}>Run</Button>}{canInProject(r.id, "project.admin") && <><Button size="sm" variant="secondary" icon={<Pencil size={14} />} onClick={() => openEdit(r)}>Edit</Button><Button size="sm" variant="danger" onClick={() => setTarget(r)}>Delete</Button></>}</div>; } }
    ]} />
    <RunJobDialog open={!!runProject} onClose={() => setRunProject(undefined)} projectId={runProject?.id} />
    <Dialog open={open} size="full" onClose={close} title="Create project" initialFocusRef={first}>
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <ol className="flex shrink-0 flex-wrap gap-2 text-sm">
          {["Name", "First playbook", "Done"].map((label, index) => <li key={label} className={`rounded-full px-3 py-1 ${step === index ? "bg-sky-600 text-white dark:bg-sky-500 dark:text-white" : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"}`}>{index + 1}. {label}</li>)}
        </ol>
        {step === 0 && <div className="grid max-w-2xl gap-4">
          {create.error && <ErrorBanner error={create.error} />}
          <TextInput ref={first} id="project-name" label="Name" value={name} error={nameError} onChange={e => setName(e.target.value)} />
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={close}>Cancel</Button><Button disabled={!validName} loading={create.isPending} onClick={createProject}>Next</Button></div>
        </div>}
        {step === 1 && created && <div className="flex min-h-0 flex-1 flex-col gap-4">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-100">Project <span className="font-medium">{created.name}</span> created.</div>
          <Checkbox id="add-first-playbook" label="Add a first playbook" checked={addFirst} onChange={e => setAddFirst(e.target.checked)} />
          {addFirst && <>
            <fieldset className="grid shrink-0 gap-2"><legend className="text-sm font-medium">Starter template</legend><div className="grid gap-2 md:grid-cols-2">{PLAYBOOK_STARTERS.map(s => <label key={s.id} className={`rounded-lg border p-3 text-sm ${starter === s.id ? "border-sky-600 bg-sky-50 dark:border-sky-400 dark:bg-sky-950/30" : "border-zinc-200 dark:border-zinc-800"}`}><input className="mr-2" type="radio" name="first-playbook-starter" checked={starter === s.id} onChange={() => setStarterId(s.id)} /><span className="font-medium">{s.label}</span><p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{s.description}</p></label>)}</div></fieldset>
            <div className="grid shrink-0 gap-3 md:grid-cols-2">
              <TextInput id="first-playbook-name" label="Name" value={firstPlaybook.name} onChange={e => setFirstPlaybookName(e.target.value)} />
              <TextInput id="first-playbook-path" label="Rel path" value={firstPlaybook.rel_path} onChange={e => setFirstPlaybookPath(e.target.value)} />
            </div>
            <div className="grid shrink-0 gap-3">{createPlaybook.error && <ErrorBanner error={createPlaybook.error} />}{lintError && <pre className="max-h-40 overflow-auto rounded-md bg-red-950 p-3 text-xs text-red-50">{lintError}</pre>}</div>
            <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800"><Editor height="100%" language="yaml" theme={effectiveTheme === "dark" ? "vs-dark" : "light"} value={content} onChange={v => { setContent(v ?? ""); setContentTouched(true); }} options={playbookEditorOptions(false)} /></div>
          </>}
          <div className="flex shrink-0 justify-end gap-2"><Button variant="secondary" onClick={() => setStep(2)}>Skip</Button>{addFirst && <Button disabled={!validFirstPlaybook} loading={createPlaybook.isPending} onClick={submitFirstPlaybook}>Create playbook</Button>}</div>
        </div>}
        {step === 2 && created && <div className="grid max-w-2xl gap-4">
          <dl className="grid gap-3 rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
            <div><dt className="font-medium text-zinc-500 dark:text-zinc-400">Project</dt><dd><Link className={linkClass} to={`/projects/${created.id}?tab=playbooks`}>{created.name}</Link></dd></div>
            {createdPlaybook && <div><dt className="font-medium text-zinc-500 dark:text-zinc-400">Playbook</dt><dd><Link className={linkClass} to={`/projects/${created.id}?tab=playbooks`}>Project playbooks</Link></dd></div>}
          </dl>
          <div className="flex justify-end"><Button onClick={() => { const id = created.id; close(); nav(`/projects/${id}?tab=playbooks`); }}>Finish</Button></div>
        </div>}
      </div>
    </Dialog>
    <Drawer open={!!edit} onClose={closeEdit} title="Edit project" initialFocusRef={editFirst} footer={<div className="flex justify-end gap-2"><Button variant="secondary" onClick={closeEdit}>Cancel</Button><Button disabled={!editForm.name.trim() || !editForm.default_branch.trim()} loading={updateEdit.isPending} onClick={() => updateEdit.mutate(editForm, { onSuccess: () => { closeEdit(); toast("Project updated"); } })}>Save</Button></div>}><div className="grid gap-3"><TextInput ref={editFirst} id="edit-project-name" label="Name" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /><TextInput id="edit-project-default-branch" label="Default branch" value={editForm.default_branch} onChange={e => setEditForm({ ...editForm, default_branch: e.target.value })} /></div></Drawer>
    <ConfirmDialog open={!!target} title="Delete project?" name={target?.name ?? ""} onClose={() => setTarget(undefined)} onConfirm={() => target && del.mutate(target.id, { onSuccess: () => { setTarget(undefined); toast("Project deleted"); } })} />
  </section>;
}
export default ProjectsPage;

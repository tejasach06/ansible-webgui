import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Pencil, Plus } from "lucide-react";
import { useCreateProjects, useDeleteProjects, useProjects, useUpdateProject } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useToast } from "../components/Toast";
import { Button } from "../components/Button";
import { DataTable } from "../components/DataTable";
import { Drawer } from "../components/Drawer";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { TextInput } from "../components/Field";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState } from "../components/EmptyState";
import type { Project } from "../lib/types";

export function ProjectsPage() {
  const { can } = useAuth(); const { toast } = useToast();
  const list = useProjects(); const create = useCreateProjects(); const del = useDeleteProjects();
  const [open, setOpen] = useState(false); const [name, setName] = useState(""); const [target, setTarget] = useState<Project>();
  const [edit, setEdit] = useState<Project>(); const [editForm, setEditForm] = useState({ name: "", default_branch: "" }); const update = useUpdateProject(edit?.id ?? 0);
  const first = useRef<HTMLInputElement>(null); const editFirst = useRef<HTMLInputElement>(null);
  const close = () => { setOpen(false); setName(""); };
  const openEdit = (p: Project) => { setEdit(p); setEditForm({ name: p.name, default_branch: p.default_branch }); };
  const closeEdit = () => setEdit(undefined);
  return <section className="grid gap-4"><div className="flex items-center justify-between"><h1 className="text-xl font-semibold">Projects</h1>{can("content.write") && <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>Create project</Button>}</div>
    {(list.error || create.error || del.error || update.error) && <ErrorBanner error={list.error || create.error || del.error || update.error} />}
    <DataTable<Project> rows={list.data ?? []} loading={list.isLoading} empty={<EmptyState>No projects yet. Create a project to sync content.</EmptyState>} columns={[
      { key: "name", header: "Name", render: r => <Link className="font-medium underline" to={`/projects/${r.id}`}>{r.name}</Link> },
      { key: "git_path", header: "Git path", render: r => r.git_path },
      { key: "default_branch", header: "Default branch", render: r => r.default_branch },
      { key: "actions", header: "Actions", render: r => can("content.write") && <div className="flex gap-2">{!r.is_inventory_repo && <Button size="sm" variant="secondary" icon={<Pencil size={14} />} onClick={() => openEdit(r)}>Edit</Button>}<Button size="sm" variant="danger" onClick={() => setTarget(r)}>Delete</Button></div> }
    ]} />
    <Drawer open={open} onClose={close} title="Create project" initialFocusRef={first} footer={<div className="flex justify-end gap-2"><Button variant="secondary" onClick={close}>Cancel</Button><Button disabled={!name.trim()} loading={create.isPending} onClick={() => create.mutate({ name }, { onSuccess: () => { close(); toast("Project created"); } })}>Create</Button></div>}><TextInput ref={first} id="project-name" label="Name" value={name} onChange={e => setName(e.target.value)} /></Drawer>
    <Drawer open={!!edit} onClose={closeEdit} title="Edit project" initialFocusRef={editFirst} footer={<div className="flex justify-end gap-2"><Button variant="secondary" onClick={closeEdit}>Cancel</Button><Button disabled={!editForm.name.trim() || !editForm.default_branch.trim()} loading={update.isPending} onClick={() => update.mutate(editForm, { onSuccess: () => { closeEdit(); toast("Project updated"); } })}>Save</Button></div>}><div className="grid gap-3"><TextInput ref={editFirst} id="edit-project-name" label="Name" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /><TextInput id="edit-project-default-branch" label="Default branch" value={editForm.default_branch} onChange={e => setEditForm({ ...editForm, default_branch: e.target.value })} /></div></Drawer>
    <ConfirmDialog open={!!target} title="Delete project?" name={target?.name ?? ""} onClose={() => setTarget(undefined)} onConfirm={() => target && del.mutate(target.id, { onSuccess: () => { setTarget(undefined); toast("Project deleted"); } })} />
  </section>;
}
export default ProjectsPage;

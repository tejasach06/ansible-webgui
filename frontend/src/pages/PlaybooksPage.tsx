import { useEffect, useRef, useState, type SyntheticEvent } from "react";
import Editor from "@monaco-editor/react";
import { Pencil, Plus } from "lucide-react";
import { useCreatePlaybooks, useDeletePlaybooks, usePlaybookFile, usePlaybooks, useSavePlaybookFile, useUpdatePlaybook } from "../api/playbooks";
import { useProjects } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { useToast } from "../components/Toast";
import { Button } from "../components/Button";
import { DataTable } from "../components/DataTable";
import { Drawer } from "../components/Drawer";
import { Dialog } from "../components/Dialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { TextInput, Select } from "../components/Field";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState } from "../components/EmptyState";
import type { ApiError } from "../lib/api";
import type { Playbook } from "../lib/types";

export function PlaybooksPage() {
  const { can } = useAuth(); const { toast } = useToast(); const { effectiveTheme } = useTheme();
  const list = usePlaybooks(); const projects = useProjects(); const selectableProjects = projects.data?.filter(p => !p.is_inventory_repo);
  const create = useCreatePlaybooks(); const del = useDeletePlaybooks();
  const [open, setOpen] = useState(false); const [form, setForm] = useState({ project_id: "", name: "", rel_path: "" });
  const [edit, setEdit] = useState<Playbook>(); const file = usePlaybookFile(edit?.id); const saveFile = useSavePlaybookFile(edit?.id ?? 0); const update = useUpdatePlaybook(edit?.id ?? 0);
  const [editForm, setEditForm] = useState({ name: "", rel_path: "" }); const [content, setContent] = useState(""); const [message, setMessage] = useState(""); const [stale, setStale] = useState<{ content: string; sha: string }>();
  const [target, setTarget] = useState<Playbook>(); const [confirmDiscard, setConfirmDiscard] = useState(false); const first = useRef<HTMLSelectElement>(null);
  const names = new Map((projects.data ?? []).map(p => [p.id, p.name]));
  const close = () => { setOpen(false); setForm({ project_id: "", name: "", rel_path: "" }); };
  const closeEdit = () => { setEdit(undefined); setContent(""); setMessage(""); setStale(undefined); };
  useEffect(() => { if (edit) setEditForm({ name: edit.name, rel_path: edit.rel_path }); }, [edit]);
  useEffect(() => { if (file.data) setContent(file.data.content); }, [file.data]);
  const valid = form.project_id && form.name.trim() && form.rel_path.trim();
  const missing = (file.error as ApiError | undefined)?.code === "file_not_found";
  const lintError = (saveFile.error as ApiError | undefined)?.code === "lint_error" ? String((saveFile.error as ApiError).detail?.stderr ?? "") : "";
  const dirtyFile = !!file.data && content !== file.data.content; const dirtyMeta = !!edit && (editForm.name !== edit.name || editForm.rel_path !== edit.rel_path);
  const requestClose = () => { if (dirtyFile || dirtyMeta) setConfirmDiscard(true); else closeEdit(); };
  const onCancelEdit = (e: SyntheticEvent<HTMLDialogElement>) => { if (dirtyFile || dirtyMeta) { e.preventDefault(); setConfirmDiscard(true); } };
  const save = () => {
    if (!edit || !can("content.write")) return;
    const saveMeta = () => dirtyMeta ? update.mutate({ name: editForm.name, rel_path: editForm.rel_path }, { onSuccess: r => { setEdit(r); toast("Playbook updated"); } }) : undefined;
    if (dirtyFile) saveFile.mutate({ content, message, base_sha: file.data?.sha }, { onSuccess: r => { toast(`Committed ${r.sha.slice(0, 8)}`); setMessage(""); saveMeta(); }, onError: e => { const err = e as ApiError; if (err.code === "stale_write") setStale({ content: String(err.detail?.current_content ?? ""), sha: String(err.detail?.current_sha ?? "") }); } });
    else saveMeta();
  };
  return <section className="grid gap-4"><div className="flex items-center justify-between"><h1 className="text-xl font-semibold">Playbooks</h1>{can("content.write") && <Button icon={<Plus size={16} />} onClick={() => setOpen(true)}>Register playbook</Button>}</div>
    {(list.error || projects.error || create.error || del.error || update.error) && <ErrorBanner error={list.error || projects.error || create.error || del.error || update.error} />}
    <DataTable<Playbook> rows={list.data ?? []} loading={list.isLoading} empty={<EmptyState>No playbooks yet. Register a playbook from a project.</EmptyState>} columns={[{ key: "name", header: "Name", render: r => r.name }, { key: "project", header: "Project", render: r => names.get(r.project_id) ?? r.project_id }, { key: "path", header: "Path", render: r => r.rel_path }, { key: "actions", header: "Actions", render: r => <div className="flex gap-2"><Button size="sm" variant="secondary" icon={<Pencil size={14} />} onClick={() => setEdit(r)}>Edit</Button>{can("content.write") && <Button size="sm" variant="danger" onClick={() => setTarget(r)}>Delete</Button>}</div> }]} />
    <Drawer open={open} onClose={close} title="Register playbook" initialFocusRef={first} footer={(selectableProjects?.length ?? 0) > 0 && <div className="flex justify-end gap-2"><Button variant="secondary" onClick={close}>Cancel</Button><Button disabled={!valid} loading={create.isPending} onClick={() => create.mutate({ project_id: Number(form.project_id), name: form.name, rel_path: form.rel_path }, { onSuccess: () => { close(); toast("Playbook created"); } })}>Register</Button></div>}>{(selectableProjects?.length ?? 0) === 0 ? <EmptyState>No projects. Create a project before registering playbooks.</EmptyState> : <div className="grid gap-3"><Select ref={first} id="playbook-project" label="Project" value={form.project_id} onChange={e => setForm({ ...form, project_id: e.target.value })}><option value="">Select project</option>{selectableProjects?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</Select><TextInput id="playbook-name" label="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /><TextInput id="playbook-path" label="Rel path" value={form.rel_path} onChange={e => setForm({ ...form, rel_path: e.target.value })} /></div>}</Drawer>
    <Dialog open={!!edit} size="full" onClose={requestClose} onCancel={onCancelEdit} title={edit ? `Edit ${edit.name}` : "Edit playbook"}><div className="grid min-h-0 flex-1 gap-4"><div className="grid shrink-0 gap-3">{file.error && !missing && <ErrorBanner error={file.error} />} {missing && <EmptyState>Playbook file missing from git repo.</EmptyState>}<div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"><TextInput id="edit-playbook-name" label="Name" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /><TextInput id="edit-playbook-path" label="Rel path" value={editForm.rel_path} onChange={e => setEditForm({ ...editForm, rel_path: e.target.value })} />{can("content.write") && <Button className="self-end" loading={saveFile.isPending || update.isPending} disabled={!dirtyFile && !dirtyMeta} onClick={save}>Save</Button>}</div>{stale && <div className="grid gap-2"><ErrorBanner error={new Error("File changed on disk")} /><div><Button variant="secondary" onClick={() => { setContent(stale.content); setStale(undefined); void file.refetch(); }}>Reload server copy</Button></div></div>}</div><div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800"><Editor height="100%" language="yaml" theme={effectiveTheme === "dark" ? "vs-dark" : "light"} value={content} onChange={v => setContent(v ?? "")} options={{ readOnly: !can("content.write"), minimap: { enabled: false }, wordWrap: "off", lineNumbers: "on", renderLineHighlight: "all", stickyScroll: { enabled: true }, scrollBeyondLastLine: false, automaticLayout: true, tabSize: 2, insertSpaces: true }} /></div><div className="grid shrink-0 gap-3"><TextInput id="playbook-commit-message" label="Commit message" value={message} onChange={e => setMessage(e.target.value)} />{saveFile.error && <ErrorBanner error={saveFile.error} />} {lintError && <pre className="max-h-40 overflow-auto rounded bg-red-950 p-3 text-xs text-red-50">{lintError}</pre>}</div></div></Dialog>
    <ConfirmDialog open={confirmDiscard} title="Discard unsaved changes?" name={edit?.name ?? ""} onClose={() => setConfirmDiscard(false)} onConfirm={() => { setConfirmDiscard(false); closeEdit(); }} />
    <ConfirmDialog open={!!target} title="Delete playbook?" name={target?.name ?? ""} onClose={() => setTarget(undefined)} onConfirm={() => target && del.mutate(target.id, { onSuccess: () => { setTarget(undefined); toast("Playbook deleted"); } })} />
  </section>;
}
export default PlaybooksPage;

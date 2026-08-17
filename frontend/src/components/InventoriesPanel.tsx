import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from "react";
import Editor from "@monaco-editor/react";
import { Plus, Pencil, CheckCircle2 } from "lucide-react";
import { useInventories, useCreateInventories, useDeleteInventories, useInventoryFile, useSaveInventoryFile, useUpdateInventory, useVerifyInventory } from "../api/inventories";
import { useProjects, useUpdateProject } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { DataTable } from "./DataTable";
import { Drawer } from "./Drawer";
import { Dialog } from "./Dialog";
import { ConfirmDialog } from "./ConfirmDialog";
import { TextInput, Select, TextArea } from "./Field";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";
import { InventoryHostsWizard, buildInventory } from "./InventoryHostsWizard";
import type { ApiError } from "../lib/api";
import type { Inventory, InventoryFormat } from "../lib/types";

export function InventoriesPanel({ projectId, autoOpenCreate, onAutoOpenHandled }: { projectId?: number; autoOpenCreate?: boolean; onAutoOpenHandled?: () => void }) {
  const { canInventoryWrite, canInProject } = useAuth();
  const { toast } = useToast();
  const { effectiveTheme } = useTheme();
  const list = useInventories(projectId);
  const create = useCreateInventories();
  const del = useDeleteInventories();
  const projects = useProjects();
  const currentProject = projects.data?.find((p) => p.id === projectId);
  const updateProject = useUpdateProject(projectId ?? 0);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"hosts" | "paste">("hosts");
  const [wizardContent, setWizardContent] = useState(buildInventory({ format: "yaml", group: "all", hosts: [] }));
  const [wizardValid, setWizardValid] = useState(false);
  const [edit, setEdit] = useState<Inventory>();
  const file = useInventoryFile(edit?.id);
  const saveFile = useSaveInventoryFile(edit?.id ?? 0);
  const update = useUpdateInventory(edit?.id ?? 0);
  const verify = useVerifyInventory(edit?.id ?? 0);
  const [verifyResult, setVerifyResult] = useState<{ hosts: string[]; groups: Record<string, string[]> } | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [scope, setScope] = useState<string>(projectId ? String(projectId) : "");
  const [form, setForm] = useState({ name: "", filename: "", format: "yaml" as InventoryFormat, content: "" });
  const [editForm, setEditForm] = useState({ name: "", format: "yaml" as InventoryFormat });
  const [content, setContent] = useState("");
  const [message, setMessage] = useState("");
  const [stale, setStale] = useState<{ content: string; sha: string }>();
  const [target, setTarget] = useState<Inventory>();
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const first = useRef<HTMLInputElement>(null);

  const close = () => {
    setOpen(false);
    setMode("hosts");
    setForm({ name: "", filename: "", format: "yaml", content: "" });
    setScope(projectId ? String(projectId) : "");
    setWizardValid(false);
  };
  const openCreate = () => {
    setScope(projectId ? String(projectId) : "");
    setOpen(true);
  };
  useEffect(() => { if (autoOpenCreate) { openCreate(); onAutoOpenHandled?.(); } }, [autoOpenCreate]);

  const closeEdit = () => {
    setEdit(undefined);
    setContent("");
    setMessage("");
    setStale(undefined);
    setVerifyResult(null);
    setVerifyError(null);
  };
  useEffect(() => { if (edit) setEditForm({ name: edit.name, format: edit.format }); }, [edit]);
  useEffect(() => { if (file.data) { setContent(file.data.content); setEditForm(f => ({ ...f, format: file.data.format })); } }, [file.data]);

  const valid = form.name.trim() && form.filename.trim() && (mode === "paste" || wizardValid);
  const saveApiError = saveFile.error as ApiError | undefined;
  const createApiError = create.error as ApiError | undefined;
  const yamlError = saveApiError?.code === "invalid_yaml" ? String(saveApiError.detail?.stderr ?? "") : "";
  const saveInvInvalid = saveApiError?.code === "inventory_invalid" ? String(saveApiError.detail?.stderr ?? saveApiError.detail?.message ?? "") : "";
  const createInvInvalid = createApiError?.code === "inventory_invalid" ? String(createApiError.detail?.stderr ?? createApiError.detail?.message ?? "") : "";
  const createYamlError = createApiError?.code === "invalid_yaml" ? String(createApiError.detail?.stderr ?? "") : "";
  const missing = (file.error as ApiError | undefined)?.code === "file_not_found";
  const dirty = !!file.data && content !== file.data.content;
  const requestClose = () => { if (dirty) setConfirmDiscard(true); else closeEdit(); };
  const onCancelEdit = (e: SyntheticEvent<HTMLDialogElement>) => { if (dirty) { e.preventDefault(); setConfirmDiscard(true); } };

  const commit = () => {
    if (!canInventoryWrite || !dirty || saveFile.isPending) return;
    saveFile.mutate({ content, message, base_sha: file.data?.sha }, {
      onSuccess: r => {
        toast(`Committed ${r.sha.slice(0, 8)}`);
        setMessage("");
      },
      onError: e => {
        const err = e as ApiError;
        if (err.code === "stale_write") setStale({ content: String(err.detail?.current_content ?? ""), sha: String(err.detail?.current_sha ?? "") });
      }
    });
  };
  const commitRef = useRef(commit);
  commitRef.current = commit;
  useEffect(() => {
    if (!edit) return;
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        commitRef.current();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [edit]);

  const onWizardChange = useCallback((next: string, nextValid: boolean) => {
    setWizardContent(next);
    setWizardValid(nextValid);
  }, []);

  const createBody = () => ({
    name: form.name,
    filename: form.filename,
    format: form.format,
    project_id: scope ? Number(scope) : null,
    content: mode === "hosts" ? wizardContent : form.content,
    message: `Create inventory ${form.name}`,
  });

  const runVerify = () => {
    setVerifyError(null);
    setVerifyResult(null);
    verify.mutate(undefined, {
      onSuccess: res => {
        setVerifyResult({ hosts: res.hosts, groups: res.groups });
      },
      onError: err => {
        const apiErr = err as ApiError;
        setVerifyError(String(apiErr.detail?.stderr ?? apiErr.detail?.message ?? "Inventory verification failed"));
      }
    });
  };

  return (
    <section className="grid gap-4">
      {projectId && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
          <Select
            id="project-default-inventory"
            label="Default inventory for this project"
            value={currentProject?.default_inventory_id ? String(currentProject.default_inventory_id) : ""}
            disabled={!canInProject(projectId, "project.admin") || updateProject.isPending}
            onChange={(e) => {
              const val = e.target.value;
              updateProject.mutate(
                { default_inventory_id: val ? Number(val) : 0 },
                {
                  onSuccess: () => toast("Default inventory updated"),
                }
              );
            }}
          >
            <option value="">None</option>
            {list.data?.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} {i.project_id ? "(Project)" : "(Shared)"}
              </option>
            ))}
          </Select>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Inventories</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {projectId ? "Host inventories available to this project." : "Inventories are shared across all projects or owned by one."}
          </p>
        </div>
        {canInventoryWrite && (
          <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={openCreate}>
            Register inventory
          </Button>
        )}
      </div>
      {(list.error || create.error || del.error || update.error || updateProject.error) && (
        <ErrorBanner error={list.error || create.error || del.error || update.error || updateProject.error} />
      )}
      <DataTable<Inventory>
        rows={list.data ?? []}
        loading={list.isLoading}
        empty={<EmptyState>No inventories yet. Register an inventory from the shared inventory repo.</EmptyState>}
        columns={[
          { key: "name", header: "Name", render: r => r.name },
          {
            key: "scope",
            header: "Scope",
            render: r => (
              <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                {r.project_id ? "Project" : "Shared"}
              </span>
            ),
          },
          { key: "path", header: "Path", render: r => r.rel_path },
          { key: "format", header: "Format", render: r => r.format },
          {
            key: "actions",
            header: "Actions",
            render: r => (
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" icon={<Pencil size={14} />} onClick={() => setEdit(r)}>
                  Edit
                </Button>
                {canInventoryWrite && (
                  <Button size="sm" variant="danger" onClick={() => setTarget(r)}>
                    Delete
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />
      <Drawer
        open={open}
        onClose={close}
        title="Register inventory"
        initialFocusRef={first}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>Cancel</Button>
            <Button disabled={!valid} loading={create.isPending} onClick={() => create.mutate(createBody(), { onSuccess: () => { close(); toast("Inventory created"); } })}>
              Register
            </Button>
          </div>
        }
      >
        <div className="grid gap-3">
          <div className="flex gap-2">
            <Button size="sm" variant={mode === "hosts" ? "primary" : "secondary"} onClick={() => setMode("hosts")}>From host list</Button>
            <Button size="sm" variant={mode === "paste" ? "primary" : "secondary"} onClick={() => setMode("paste")}>Paste file</Button>
          </div>
          <Select
            id="inventory-scope"
            label="Scope"
            value={scope}
            onChange={e => setScope(e.target.value)}
          >
            <option value="">Shared (all projects)</option>
            {projectId && <option value={String(projectId)}>{currentProject?.name ?? `Project #${projectId}`}</option>}
          </Select>
          <TextInput ref={first} id="inventory-name" label="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <TextInput id="inventory-filename" label="File name" value={form.filename} onChange={e => setForm({ ...form, filename: e.target.value })} />
          <Select id="inventory-format" label="Format" value={form.format} onChange={e => setForm({ ...form, format: e.target.value as InventoryFormat })}>
            <option value="yaml">yaml</option>
            <option value="ini">ini</option>
          </Select>
          {createYamlError && <pre className="max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 dark:bg-zinc-900">{createYamlError}</pre>}
          {createInvInvalid && <pre className="max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 dark:bg-zinc-900">{createInvInvalid}</pre>}
          {mode === "hosts" ? <InventoryHostsWizard format={form.format} onChange={onWizardChange} /> : <TextArea id="inventory-content" label="Content" value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} />}
        </div>
      </Drawer>
      <Dialog open={!!edit} size="full" onClose={requestClose} onCancel={onCancelEdit} title={edit ? `Edit ${edit.name}` : "Edit inventory"}>
        <div className="grid min-h-0 flex-1 gap-4">
          <div className="grid shrink-0 gap-3">
            {file.error && !missing && <ErrorBanner error={file.error} />}
            {missing && <EmptyState>Inventory file missing from git repo.</EmptyState>}
            <div className="grid gap-3 md:grid-cols-[1fr_160px_auto]">
              <TextInput id="edit-inventory-name" label="Name" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
              <Select id="edit-inventory-format" label="Format" value={editForm.format} onChange={e => setEditForm({ ...editForm, format: e.target.value as InventoryFormat })}>
                <option value="yaml">yaml</option>
                <option value="ini">ini</option>
              </Select>
              {canInventoryWrite && (
                <Button className="self-end" loading={update.isPending} onClick={() => update.mutate(editForm, { onSuccess: r => { setEdit(r); toast("Inventory updated"); } })}>
                  Save metadata
                </Button>
              )}
            </div>
            <div className="flex items-center justify-between">
              <div className="text-sm font-mono text-zinc-600 dark:text-zinc-400">{edit?.rel_path}</div>
              <div className="flex gap-2">
                {canInventoryWrite && (
                  <Button size="sm" variant="secondary" icon={<CheckCircle2 size={14} />} loading={verify.isPending} onClick={runVerify}>
                    Verify
                  </Button>
                )}
              </div>
            </div>
            {verifyResult && (
              <div className="rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
                <div className="font-semibold text-zinc-800 dark:text-zinc-200 mb-1">
                  {verifyResult.hosts.length} {verifyResult.hosts.length === 1 ? "host" : "hosts"} resolved
                </div>
                {verifyResult.hosts.length === 0 ? (
                  <p className="text-zinc-500">No hosts resolved.</p>
                ) : (
                  <div className="grid gap-1">
                    {Object.entries(verifyResult.groups).map(([grp, hsts]) => (
                      <div key={grp} className="font-mono text-zinc-700 dark:text-zinc-300">
                        <span className="font-semibold">{grp}:</span> {hsts.length > 0 ? hsts.join(", ") : "-"}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {verifyError && (
              <pre className="max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 dark:bg-zinc-900">
                {verifyError}
              </pre>
            )}
            {stale && (
              <div className="grid gap-2">
                <ErrorBanner error={new Error("File changed on disk")} />
                <div>
                  <Button variant="secondary" onClick={() => { setContent(stale.content); setStale(undefined); void file.refetch(); }}>
                    Reload
                  </Button>
                </div>
              </div>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
            <Editor
              height="100%"
              language={editForm.format === "yaml" ? "yaml" : "ini"}
              theme={effectiveTheme === "dark" ? "vs-dark" : "light"}
              value={content}
              onChange={v => setContent(v ?? "")}
              options={{
                readOnly: !canInventoryWrite,
                minimap: { enabled: false },
                wordWrap: "off",
                lineNumbers: "on",
                renderLineHighlight: "all",
                stickyScroll: { enabled: true },
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 2,
                insertSpaces: true,
              }}
            />
          </div>
          <div className="grid shrink-0 gap-3">
            <div className="flex flex-wrap gap-2">
              <TextInput id="inventory-commit-message" label="Commit message" value={message} onChange={e => setMessage(e.target.value)} />
              {canInventoryWrite && (
                <Button loading={saveFile.isPending} disabled={!dirty} onClick={commit}>
                  Save and commit
                </Button>
              )}
            </div>
            {saveFile.error && <ErrorBanner error={saveFile.error} />}
            {yamlError && <pre className="max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 dark:bg-zinc-900">{yamlError}</pre>}
            {saveInvInvalid && <pre className="max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 dark:bg-zinc-900">{saveInvInvalid}</pre>}
          </div>
        </div>
      </Dialog>
      <ConfirmDialog open={confirmDiscard} title="Discard unsaved changes?" name={edit?.name ?? ""} onClose={() => setConfirmDiscard(false)} onConfirm={() => { setConfirmDiscard(false); closeEdit(); }} />
      <ConfirmDialog open={!!target} title="Delete inventory?" name={target?.name ?? ""} onClose={() => setTarget(undefined)} onConfirm={() => target && del.mutate(target.id, { onSuccess: () => { setTarget(undefined); toast("Inventory deleted"); } })} />
    </section>
  );
}

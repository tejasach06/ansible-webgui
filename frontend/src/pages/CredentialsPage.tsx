import { useRef, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { useCreateCredentials, useCredentials, useDeleteCredentials, useUpdateCredential } from "../api/credentials";
import { useProjects } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useToast } from "../components/Toast";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { Drawer } from "../components/Drawer";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { TextInput, TextArea, Select, Checkbox } from "../components/Field";
import { ErrorBanner } from "../components/ErrorBanner";
import { EmptyState } from "../components/EmptyState";
import type { Credential, CredentialKind } from "../lib/types";

const kinds: CredentialKind[] = ["ssh_key", "ssh_password", "vault_password", "become_password"];

export function CredentialsPage() {
  const { user, canAny, canInProject } = useAuth();
  const { toast } = useToast();
  const list = useCredentials();
  const projects = useProjects();
  const create = useCreateCredentials();
  const del = useDeleteCredentials();

  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    project_id: "",
    name: "",
    kind: "ssh_key" as CredentialKind,
    username: "",
    payload: "",
    become_same_as_ssh: false,
  });
  const [edit, setEdit] = useState<Credential>();
  const [editForm, setEditForm] = useState({
    name: "",
    username: "",
    payload: "",
    become_same_as_ssh: false,
  });
  const update = useUpdateCredential(edit?.id ?? 0);
  const [target, setTarget] = useState<Credential>();
  const first = useRef<HTMLInputElement>(null);
  const editFirst = useRef<HTMLInputElement>(null);

  const projectName = (id: number) => projects.data?.find((p) => p.id === id)?.name ?? String(id);

  const close = () => {
    setOpen(false);
    setForm({ project_id: "", name: "", kind: "ssh_key", username: "", payload: "", become_same_as_ssh: false });
  };
  const openEdit = (c: Credential) => {
    setEdit(c);
    setEditForm({ name: c.name, username: c.username ?? "", payload: "", become_same_as_ssh: c.become_same_as_ssh ?? false });
  };
  const closeEdit = () => setEdit(undefined);

  const canCreate = canAny("credential.write") || Object.keys(user?.project_perms ?? {}).length > 0;
  const valid = !!form.project_id && form.name.trim() && form.payload.trim();
  const formProjectIdNum = Number(form.project_id);
  const canSubmitCreate = !isNaN(formProjectIdNum) && formProjectIdNum > 0 && canInProject(formProjectIdNum, "credential.write");

  const saveEdit = () => {
    const body: Record<string, unknown> = { name: editForm.name, username: editForm.username };
    if (edit?.kind === "ssh_password") {
      body.become_same_as_ssh = editForm.become_same_as_ssh;
    }
    if (editForm.payload.trim()) body.payload = editForm.payload;
    update.mutate(body, {
      onSuccess: () => {
        closeEdit();
        toast("Credential updated");
      },
    });
  };

  const allRows = list.data ?? [];
  const filteredRows = selectedProjectId
    ? allRows.filter((r) => String(r.project_id) === selectedProjectId)
    : allRows;

  return (
    <section className="grid gap-4">
      <PageHeader
        title="Credentials"
        subtitle="Encrypted secrets materialised only inside the worker for a run."
        actions={
          canCreate && (
            <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>
              Create credential
            </Button>
          )
        }
      />
      {(list.error || create.error || del.error || update.error) && (
        <ErrorBanner error={list.error || create.error || del.error || update.error} />
      )}

      <div className="w-64">
        <Select
          id="credential-project-filter"
          label="Filter by project"
          value={selectedProjectId}
          onChange={(e) => setSelectedProjectId(e.target.value)}
        >
          <option value="">All projects</option>
          {projects.data?.filter((p) => !p.is_inventory_repo).map((p) => (
            <option key={p.id} value={String(p.id)}>
              {p.name}
            </option>
          ))}
        </Select>
      </div>

      <DataTable<Credential>
        rows={filteredRows}
        loading={list.isLoading}
        empty={<EmptyState>No credentials yet. Create a credential for job runs.</EmptyState>}
        columns={[
          { key: "project", header: "Project", render: (r) => projectName(r.project_id) },
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "kind", header: "Kind", render: (r) => r.kind },
          { key: "username", header: "Username", render: (r) => r.username || "-" },
          { key: "created_by", header: "Created by", render: (r) => r.created_by },
          {
            key: "actions",
            header: "Actions",
            render: (r) =>
              canInProject(r.project_id, "credential.write") && (
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" icon={<Pencil size={14} />} onClick={() => openEdit(r)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => setTarget(r)}>
                    Delete
                  </Button>
                </div>
              ),
          },
        ]}
      />

      <Drawer
        open={open}
        onClose={close}
        title="Create credential"
        initialFocusRef={first}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button
              disabled={!valid || !canSubmitCreate}
              loading={create.isPending}
              onClick={() =>
                create.mutate(
                  {
                    ...form,
                    project_id: Number(form.project_id),
                  },
                  {
                    onSuccess: () => {
                      close();
                      toast("Credential created");
                    },
                  }
                )
              }
            >
              Create
            </Button>
          </div>
        }
      >
        <div className="grid gap-3">
          <Select
            id="credential-project"
            label="Project"
            value={form.project_id}
            onChange={(e) => setForm({ ...form, project_id: e.target.value })}
          >
            <option value="">Select a project...</option>
            {projects.data?.filter((p) => !p.is_inventory_repo).map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </Select>
          <TextInput ref={first} id="credential-name" label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Select
            id="credential-kind"
            label="Kind"
            value={form.kind}
            onChange={(e) => {
              const nextKind = e.target.value as CredentialKind;
              setForm({
                ...form,
                kind: nextKind,
                become_same_as_ssh: nextKind === "ssh_password" ? form.become_same_as_ssh : false,
              });
            }}
          >
            {kinds.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </Select>
          <TextInput id="credential-username" label="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <TextArea id="credential-payload" label="Payload" value={form.payload} autoComplete="off" spellCheck={false} onChange={(e) => setForm({ ...form, payload: e.target.value })} />
          {form.kind === "ssh_password" && (
            <Checkbox
              id="credential-become-same"
              label="Sudo (become) uses this same password"
              checked={form.become_same_as_ssh}
              onChange={(e) => setForm({ ...form, become_same_as_ssh: e.target.checked })}
            />
          )}
        </div>
      </Drawer>

      <Drawer
        open={!!edit}
        onClose={closeEdit}
        title="Edit credential"
        initialFocusRef={editFirst}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeEdit}>
              Cancel
            </Button>
            <Button disabled={!editForm.name.trim()} loading={update.isPending} onClick={saveEdit}>
              Save
            </Button>
          </div>
        }
      >
        <div className="grid gap-3">
          <TextInput ref={editFirst} id="edit-credential-name" label="Name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
          <TextInput id="edit-credential-username" label="Username" value={editForm.username} onChange={(e) => setEditForm({ ...editForm, username: e.target.value })} />
          <div className="text-sm">
            <span className="font-medium">Kind</span>
            <div className="mt-1 rounded-lg border border-zinc-300 px-3 py-2 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300">{edit?.kind}</div>
          </div>
          <TextArea id="edit-credential-payload" label="New secret (leave blank to keep current)" value={editForm.payload} autoComplete="off" spellCheck={false} onChange={(e) => setEditForm({ ...editForm, payload: e.target.value })} />
          {edit?.kind === "ssh_password" && (
            <Checkbox
              id="edit-credential-become-same"
              label="Sudo (become) uses this same password"
              checked={editForm.become_same_as_ssh}
              onChange={(e) => setEditForm({ ...editForm, become_same_as_ssh: e.target.checked })}
            />
          )}
        </div>
      </Drawer>

      <ConfirmDialog
        open={!!target}
        title="Delete credential?"
        name={target?.name ?? ""}
        onClose={() => setTarget(undefined)}
        onConfirm={() =>
          target &&
          del.mutate(target.id, {
            onSuccess: () => {
              setTarget(undefined);
              toast("Credential deleted");
            },
          })
        }
      />
    </section>
  );
}
export default CredentialsPage;

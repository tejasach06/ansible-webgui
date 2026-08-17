import { useRef, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { useCreateCredentials, useCredentials, useDeleteCredentials, useUpdateCredential } from "../api/credentials";
import { useAuth } from "../lib/auth";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { DataTable } from "./DataTable";
import { Drawer } from "./Drawer";
import { ConfirmDialog } from "./ConfirmDialog";
import { TextInput, TextArea, Select } from "./Field";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";
import type { Credential, CredentialKind } from "../lib/types";

const kinds: CredentialKind[] = ["ssh_key", "ssh_password", "vault_password", "become_password"];

export function CredentialsPanel({ projectId }: { projectId: number }) {
  const { canInProject } = useAuth();
  const canWrite = canInProject(projectId, "credential.write");
  const { toast } = useToast();
  const list = useCredentials(projectId);
  const create = useCreateCredentials();
  const del = useDeleteCredentials();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", kind: "ssh_key" as CredentialKind, username: "", payload: "" });
  const [edit, setEdit] = useState<Credential>();
  const [editForm, setEditForm] = useState({ name: "", username: "", payload: "" });
  const update = useUpdateCredential(edit?.id ?? 0);
  const [target, setTarget] = useState<Credential>();
  const first = useRef<HTMLInputElement>(null);
  const editFirst = useRef<HTMLInputElement>(null);

  const close = () => {
    setOpen(false);
    setForm({ name: "", kind: "ssh_key", username: "", payload: "" });
  };

  const openEdit = (c: Credential) => {
    setEdit(c);
    setEditForm({ name: c.name, username: c.username ?? "", payload: "" });
  };

  const closeEdit = () => setEdit(undefined);
  const valid = form.name.trim() && form.payload.trim();

  const saveEdit = () => {
    const body: Record<string, string> = { name: editForm.name, username: editForm.username };
    if (editForm.payload.trim()) body.payload = editForm.payload;
    update.mutate(body, {
      onSuccess: () => {
        closeEdit();
        toast("Credential updated");
      },
    });
  };

  return (
    <section className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Credentials</h2>
        {canWrite && (
          <Button icon={<Plus size={16} />} onClick={() => setOpen(true)}>
            Create credential
          </Button>
        )}
      </div>

      {(list.error || create.error || del.error || update.error) && (
        <ErrorBanner error={list.error || create.error || del.error || update.error} />
      )}

      <DataTable<Credential>
        rows={list.data ?? []}
        loading={list.isLoading}
        empty={<EmptyState>No credentials yet for this project.</EmptyState>}
        columns={[
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "kind", header: "Kind", render: (r) => r.kind },
          { key: "username", header: "Username", render: (r) => r.username || "—" },
          { key: "created_by", header: "Created by", render: (r) => r.created_by },
          {
            key: "actions",
            header: "Actions",
            render: (r) =>
              canWrite && (
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
              disabled={!valid}
              loading={create.isPending}
              onClick={() =>
                create.mutate(
                  { ...form, project_id: projectId },
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
          <TextInput ref={first} id="credential-name" label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Select id="credential-kind" label="Kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as CredentialKind })}>
            {kinds.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </Select>
          <TextInput id="credential-username" label="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <TextArea id="credential-payload" label="Payload (Secret / Private Key)" value={form.payload} onChange={(e) => setForm({ ...form, payload: e.target.value })} />
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
          <TextArea id="edit-credential-payload" label="Payload (Leave empty to keep existing secret)" value={editForm.payload} onChange={(e) => setEditForm({ ...editForm, payload: e.target.value })} />
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

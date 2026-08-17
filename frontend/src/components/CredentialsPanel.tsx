import { useRef, useState } from "react";
import { KeyRound, Pencil, Plus, Rocket } from "lucide-react";
import {
  useBootstrapPlaybook,
  useCreateCredentials,
  useCredentials,
  useDeleteCredentials,
  useGenerateCredential,
  useUpdateCredential,
} from "../api/credentials";
import { useAuth } from "../lib/auth";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { Section } from "./Section";
import { DataTable } from "./DataTable";
import { Drawer } from "./Drawer";
import { ConfirmDialog } from "./ConfirmDialog";
import { TextInput, TextArea, Select, Checkbox } from "./Field";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";
import { RunJobDialog } from "./RunJobDialog";
import type { Credential, CredentialKind } from "../lib/types";

const kinds: CredentialKind[] = ["ssh_key", "ssh_password", "vault_password", "become_password"];

export function CredentialsPanel({ projectId }: { projectId: number }) {
  const { canInProject } = useAuth();
  const canWrite = canInProject(projectId, "credential.write");
  const { toast } = useToast();
  const list = useCredentials(projectId);
  const create = useCreateCredentials();
  const generate = useGenerateCredential();
  const bootstrap = useBootstrapPlaybook();
  const del = useDeleteCredentials();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", kind: "ssh_key" as CredentialKind, username: "", payload: "", become_same_as_ssh: false });

  const [genOpen, setGenOpen] = useState(false);
  const [genForm, setGenForm] = useState({ name: "", username: "", key_type: "ed25519" as "ed25519" | "rsa4096" });

  const [viewKey, setViewKey] = useState<Credential>();
  const [deploy, setDeploy] = useState<{ playbookId: number; publicKey: string }>();

  const [edit, setEdit] = useState<Credential>();
  const [editForm, setEditForm] = useState({ name: "", username: "", payload: "", become_same_as_ssh: false });
  const update = useUpdateCredential(edit?.id ?? 0);
  const [target, setTarget] = useState<Credential>();

  const first = useRef<HTMLInputElement>(null);
  const genFirst = useRef<HTMLInputElement>(null);
  const editFirst = useRef<HTMLInputElement>(null);

  const close = () => {
    setOpen(false);
    setForm({ name: "", kind: "ssh_key", username: "", payload: "", become_same_as_ssh: false });
  };

  const closeGen = () => {
    setGenOpen(false);
    setGenForm({ name: "", username: "", key_type: "ed25519" });
  };

  const openEdit = (c: Credential) => {
    setEdit(c);
    setEditForm({ name: c.name, username: c.username ?? "", payload: "", become_same_as_ssh: c.become_same_as_ssh ?? false });
  };

  const closeEdit = () => setEdit(undefined);
  const valid = form.name.trim() && form.payload.trim();

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

  const handleGenerate = () => {
    generate.mutate(
      {
        project_id: projectId,
        name: genForm.name.trim(),
        username: genForm.username.trim() || undefined,
        key_type: genForm.key_type,
      },
      {
        onSuccess: (created) => {
          closeGen();
          toast("SSH key generated");
          setViewKey(created);
        },
      }
    );
  };

  const handleDeploy = (c: Credential) => {
    bootstrap.mutate(c.id, {
      onSuccess: (data) => {
        setDeploy({ playbookId: data.playbook_id, publicKey: data.public_key });
      },
    });
  };

  const copyPublicKey = (keyText: string) => {
    navigator.clipboard.writeText(keyText);
    toast("Public key copied");
  };

  return (
    <Section
      title="Credentials"
      divider={false}
      actions={
        canWrite && (
          <div className="flex gap-2">
            <Button variant="secondary" icon={<KeyRound size={16} strokeWidth={1.5} />} onClick={() => setGenOpen(true)}>
              Generate SSH key
            </Button>
            <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>
              Create credential
            </Button>
          </div>
        )
      }
    >
      {(list.error || create.error || generate.error || bootstrap.error || del.error || update.error) && (
        <ErrorBanner error={list.error || create.error || generate.error || bootstrap.error || del.error || update.error} />
      )}

      <DataTable<Credential>
        rows={list.data ?? []}
        loading={list.isLoading}
        empty={<EmptyState>No credentials yet for this project.</EmptyState>}
        columns={[
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "kind", header: "Kind", render: (r) => r.kind },
          { key: "username", header: "Username", render: (r) => r.username || "-" },
          { key: "created_by", header: "Created by", render: (r) => r.created_by },
          {
            key: "actions",
            header: "Actions",
            render: (r) =>
              canWrite && (
                <div className="flex gap-2">
                  {r.kind === "ssh_key" && (
                    <>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={!r.public_key}
                        title={r.public_key ? "View public key" : "Public key available for generated keys only"}
                        onClick={() => setViewKey(r)}
                      >
                        Public key
                      </Button>
                      {r.public_key && (
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={<Rocket size={14} />}
                          loading={bootstrap.isPending && bootstrap.variables === r.id}
                          onClick={() => handleDeploy(r)}
                        >
                          Deploy key
                        </Button>
                      )}
                    </>
                  )}
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
          <TextArea id="credential-payload" label="Payload (Secret / Private Key)" value={form.payload} onChange={(e) => setForm({ ...form, payload: e.target.value })} />
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
        open={genOpen}
        onClose={closeGen}
        title="Generate SSH key"
        initialFocusRef={genFirst}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeGen}>
              Cancel
            </Button>
            <Button disabled={!genForm.name.trim()} loading={generate.isPending} onClick={handleGenerate}>
              Generate
            </Button>
          </div>
        }
      >
        <div className="grid gap-3">
          <TextInput
            ref={genFirst}
            id="gen-credential-name"
            label="Name"
            value={genForm.name}
            onChange={(e) => setGenForm({ ...genForm, name: e.target.value })}
          />
          <TextInput
            id="gen-credential-username"
            label="Username"
            value={genForm.username}
            onChange={(e) => setGenForm({ ...genForm, username: e.target.value })}
          />
          <Select
            id="gen-credential-key-type"
            label="Key type"
            value={genForm.key_type}
            onChange={(e) => setGenForm({ ...genForm, key_type: e.target.value as "ed25519" | "rsa4096" })}
          >
            <option value="ed25519">ed25519 (recommended)</option>
            <option value="rsa4096">rsa-4096 (legacy hosts)</option>
          </Select>
        </div>
      </Drawer>

      <Drawer
        open={!!viewKey}
        onClose={() => setViewKey(undefined)}
        title="Public key"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setViewKey(undefined)}>
              Close
            </Button>
            {viewKey?.public_key && (
              <Button onClick={() => copyPublicKey(viewKey.public_key!)}>
                Copy
              </Button>
            )}
          </div>
        }
      >
        <div className="grid gap-3">
          <div className="text-sm text-zinc-600 dark:text-zinc-400">
            Paste into <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-xs dark:bg-zinc-800">~/.ssh/authorized_keys</code> on your managed hosts, or use Deploy key to install it automatically.
          </div>
          {viewKey?.public_key ? (
            <pre className="overflow-x-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs whitespace-pre-wrap break-all text-zinc-900 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100">
              {viewKey.public_key}
            </pre>
          ) : (
            <p className="text-sm text-zinc-500">Public key unavailable — generated keys only.</p>
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
          <TextArea id="edit-credential-payload" label="Payload (Leave empty to keep existing secret)" value={editForm.payload} onChange={(e) => setEditForm({ ...editForm, payload: e.target.value })} />
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

      <RunJobDialog
        open={!!deploy}
        onClose={() => setDeploy(undefined)}
        projectId={projectId}
        playbookId={deploy?.playbookId}
        extraVarsText={deploy ? JSON.stringify({ webgui_public_key: deploy.publicKey }, null, 2) : undefined}
      />
    </Section>
  );
}

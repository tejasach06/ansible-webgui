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
import { useProjects } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { Section } from "./Section";
import { PageHeader } from "./PageHeader";
import { DataTable } from "./DataTable";
import { Drawer } from "./Drawer";
import { ConfirmDialog } from "./ConfirmDialog";
import { TextInput, TextArea, Select, Checkbox } from "./Field";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";
import { RunJobDialog } from "./RunJobDialog";
import type { Credential, CredentialKind } from "../lib/types";
import { KIND_LABEL } from "../lib/credentialSlots";

const kinds: CredentialKind[] = ["ssh_key", "ssh_password", "vault_password", "become_password"];

export function CredentialsPanel({ projectId }: { projectId?: number }) {
  const { user, canAny, canInProject } = useAuth();
  const canWrite = projectId ? canInProject(projectId, "credential.write") : canAny("credential.write") || Object.keys(user?.project_perms ?? {}).length > 0;
  const { toast } = useToast();
  const list = useCredentials(projectId);
  const projects = useProjects();
  const create = useCreateCredentials();
  const generate = useGenerateCredential();
  const bootstrap = useBootstrapPlaybook();
  const del = useDeleteCredentials();

  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ project_id: projectId ? String(projectId) : "", name: "", kind: "ssh_key" as CredentialKind, username: "", payload: "", become_same_as_ssh: false });

  const [genOpen, setGenOpen] = useState(false);
  const [genForm, setGenForm] = useState({ project_id: projectId ? String(projectId) : "", name: "", username: "", key_type: "ed25519" as "ed25519" | "rsa4096" });

  const [viewKey, setViewKey] = useState<Credential>();
  const [deploy, setDeploy] = useState<{ playbookId: number; publicKey: string }>();

  const [edit, setEdit] = useState<Credential>();
  const [editForm, setEditForm] = useState({ name: "", username: "", payload: "", become_same_as_ssh: false });
  const update = useUpdateCredential(edit?.id ?? 0);
  const [target, setTarget] = useState<Credential>();

  const first = useRef<HTMLInputElement>(null);
  const genFirst = useRef<HTMLInputElement>(null);
  const editFirst = useRef<HTMLInputElement>(null);

  const projectName = (id: number) => projects.data?.find((p) => p.id === id)?.name ?? String(id);

  const close = () => {
    setOpen(false);
    setForm({ project_id: projectId ? String(projectId) : "", name: "", kind: "ssh_key", username: "", payload: "", become_same_as_ssh: false });
  };

  const closeGen = () => {
    setGenOpen(false);
    setGenForm({ project_id: projectId ? String(projectId) : "", name: "", username: "", key_type: "ed25519" });
  };

  const openEdit = (c: Credential) => {
    setEdit(c);
    setEditForm({ name: c.name, username: c.username ?? "", payload: "", become_same_as_ssh: c.become_same_as_ssh });
  };

  const closeEdit = () => setEdit(undefined);
  const targetProjectId = projectId ?? Number(form.project_id);
  const valid = (projectId ? true : !!form.project_id) && form.name.trim() && form.payload.trim();

  const saveEdit = () => {
    const body: Record<string, unknown> = { name: editForm.name, username: editForm.username };
    if (edit?.kind === "ssh_password") {
      body.become_same_as_ssh = editForm.become_same_as_ssh;
    }
    if (editForm.payload.trim()) {
      body.payload = editForm.payload;
    }
    update.mutate(body, {
      onSuccess: () => {
        closeEdit();
        toast("Credential updated");
      },
    });
  };

  const handleGenerate = () => {
    const genTargetProjectId = projectId ?? Number(genForm.project_id);
    if (!genTargetProjectId) return;
    generate.mutate(
      {
        project_id: genTargetProjectId,
        name: genForm.name,
        username: genForm.username || undefined,
        key_type: genForm.key_type,
      },
      {
        onSuccess: (created) => {
          closeGen();
          toast("Key generated");
          if (created.public_key) {
            setViewKey(created);
          }
        },
      }
    );
  };

  const handleDeploy = (c: Credential) => {
    bootstrap.mutate(c.id, {
      onSuccess: (res) => {
        setDeploy({ playbookId: res.playbook_id, publicKey: c.public_key! });
      },
    });
  };

  const copyPublicKey = (keyText: string) => {
    navigator.clipboard.writeText(keyText);
    toast("Public key copied");
  };

  const allRows = list.data ?? [];
  const filteredRows = selectedProjectId
    ? allRows.filter((r) => String(r.project_id) === selectedProjectId)
    : allRows;

  const writeActions = canWrite && (
    <div className="flex gap-2">
      <Button variant="secondary" icon={<KeyRound size={16} strokeWidth={1.5} />} onClick={() => setGenOpen(true)}>
        Generate SSH key
      </Button>
      <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>
        Create credential
      </Button>
    </div>
  );

  const headerActions = (
    <div className="flex flex-wrap items-center gap-2">
      {!projectId && (
        <select
          id="filter-project"
          aria-label="Filter by project"
          value={selectedProjectId}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          className="h-9 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
        >
          <option value="">All projects</option>
          {projects.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      )}
      {canWrite && (
        <>
          <Button variant="secondary" icon={<KeyRound size={16} strokeWidth={1.5} />} onClick={() => setGenOpen(true)}>
            Generate SSH key
          </Button>
          <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>
            Create credential
          </Button>
        </>
      )}
    </div>
  );

  const emptyNode = selectedProjectId && allRows.length ? (
    <EmptyState>No credentials in {projectName(Number(selectedProjectId))}. Clear the project filter to see all credentials.</EmptyState>
  ) : (
    <EmptyState>No credentials yet. Create a credential or generate an SSH key to get started.</EmptyState>
  );

  const body = (
    <>
      {(list.error || create.error || generate.error || bootstrap.error || del.error || update.error) && (
        <ErrorBanner error={list.error || create.error || generate.error || bootstrap.error || del.error || update.error} />
      )}

      <DataTable<Credential>
        rows={filteredRows}
        loading={list.isLoading}
        empty={emptyNode}
        columns={[
          ...(!projectId ? [{ key: "project", header: "Project", render: (r: Credential) => projectName(r.project_id) }] : []),
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "kind", header: "Kind", render: (r) => KIND_LABEL[r.kind] },
          { key: "username", header: "Username", render: (r) => r.username || "-" },
          { key: "created_by", header: "Created by", render: (r) => r.created_by },
          {
            key: "actions",
            header: "Actions",
            render: (r) => {
              const canEditThis = projectId ? canWrite : canInProject(r.project_id, "credential.write");
              return canEditThis ? (
                <div className="flex flex-wrap items-center gap-2">
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
              ) : null;
            },
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
                  { ...form, project_id: targetProjectId },
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
          {!projectId && (
            <Select id="credential-project" label="Project" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
              <option value="">Select project</option>
              {projects.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          )}
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
                {KIND_LABEL[k]}
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
            <Button disabled={!genForm.name.trim() || (!projectId && !genForm.project_id)} loading={generate.isPending} onClick={handleGenerate}>
              Generate
            </Button>
          </div>
        }
      >
        <div className="grid gap-3">
          {!projectId && (
            <Select id="gen-credential-project" label="Project" value={genForm.project_id} onChange={(e) => setGenForm({ ...genForm, project_id: e.target.value })}>
              <option value="">Select project</option>
              {projects.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          )}
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
          <div className="text-sm text-fg-muted">
            Paste into <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-xs dark:bg-zinc-800">~/.ssh/authorized_keys</code> on your managed hosts, or use Deploy key to install it automatically.
          </div>
          {viewKey?.public_key ? (
            <pre className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs whitespace-pre-wrap break-all text-fg dark:border-zinc-800 dark:bg-zinc-900">
              {viewKey.public_key}
            </pre>
          ) : (
            <p className="text-sm text-fg-muted">Public key unavailable — generated keys only.</p>
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
          <div className="grid gap-1 text-sm">
            <span className="font-medium">Kind</span>
            <div className="rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-fg-muted dark:border-zinc-700 dark:bg-zinc-950">
              {edit ? KIND_LABEL[edit.kind] : ""}
            </div>
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
    </>
  );

  if (!projectId) {
    return (
      <section className="grid gap-4">
        <PageHeader
          title="Credentials"
          subtitle="Secrets used by job runs — SSH keys, passwords, and vault passwords, scoped per project."
          actions={headerActions}
        />
        {body}
      </section>
    );
  }

  return (
    <Section title="Credentials" divider={false} actions={writeActions}>
      {body}
    </Section>
  );
}

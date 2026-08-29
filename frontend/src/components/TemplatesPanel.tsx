import { useEffect, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { useTemplates, useCreateTemplates, useUpdateTemplates, useDeleteTemplates } from "../api/templates";
import { useProjects } from "../api/projects";
import { usePlaybooks } from "../api/playbooks";
import { useInventories } from "../api/inventories";
import { useCredentials } from "../api/credentials";
import { parseExtra, type JobTemplate, type SurveyField } from "../lib/types";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { Section } from "./Section";
import { Drawer } from "./Drawer";
import { DataTable } from "./DataTable";
import { TextArea, TextInput, Checkbox, Select, NumberInput } from "./Field";
import { ErrorBanner } from "./ErrorBanner";
import { CredentialSlots } from "./CredentialSlots";

const init = {
  name: "",
  description: "",
  project_id: "",
  playbook_id: "",
  inventory_id: "",
  limit_pattern: "",
  tags: "",
  skip_tags: "",
  verbosity: 0,
  forks: 5,
  credential_ids: [] as number[],
  extra_vars: "{}",
  requires_approval: true,
  diff_mode: false,
  survey_spec: [] as SurveyField[],
  ask_limit: false,
  ask_tags: false,
  ask_skip_tags: false,
  ask_extra_vars: false,
  ask_verbosity: false,
  ask_diff: false,
  ask_credentials: false,
  ask_inventory: false,
  ask_mode: false,
};


export function TemplatesPanel({ projectId }: { projectId?: number }) {
  const { toast } = useToast();
  const list = useTemplates(projectId);
  const projects = useProjects();
  const selectableProjects = projects.data?.filter((p) => !p.is_inventory_repo);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<JobTemplate>();
  const [form, setForm] = useState(init);
  const [extraError, setExtraError] = useState("");
  const first = useRef<HTMLInputElement>(null);

  const effectiveProjectId = Number(form.project_id) || projectId || 0;
  const playbooks = usePlaybooks(effectiveProjectId || undefined);
  const inventories = useInventories();
  const credentials = useCredentials(effectiveProjectId || undefined);

  const create = useCreateTemplates();
  const update = useUpdateTemplates();
  const del = useDeleteTemplates();

  useEffect(() => {
    if (editing) {
      setForm({
        ...init,
        ...editing,
        description: editing.description ?? "",
        limit_pattern: editing.limit_pattern ?? "",
        tags: editing.tags ?? "",
        skip_tags: editing.skip_tags ?? "",
        project_id: String(editing.project_id),
        playbook_id: String(editing.playbook_id),
        inventory_id: String(editing.inventory_id),
        extra_vars: JSON.stringify(editing.extra_vars || {}, null, 2),
        ask_limit: editing.ask_limit,
        ask_tags: editing.ask_tags,
        ask_skip_tags: editing.ask_skip_tags,
        ask_extra_vars: editing.ask_extra_vars,
        ask_verbosity: editing.ask_verbosity,
        ask_diff: editing.ask_diff,
        ask_credentials: editing.ask_credentials,
        ask_inventory: editing.ask_inventory,
        ask_mode: editing.ask_mode,
      });
    } else {
      setForm({ ...init, project_id: projectId ? String(projectId) : "" });
    }
  }, [editing, projectId]);

  const close = () => {
    setOpen(false);
    setEditing(undefined);
    setForm(init);
    setExtraError("");
  };

  const submit = () => {
    const parsed = parseExtra(form.extra_vars);
    if (!parsed) {
      setExtraError("Invalid JSON dictionary");
      return;
    }
    const payload = {
      name: form.name,
      description: form.description || null,
      project_id: Number(form.project_id),
      playbook_id: Number(form.playbook_id),
      inventory_id: Number(form.inventory_id),
      limit_pattern: form.limit_pattern || null,
      tags: form.tags || null,
      skip_tags: form.skip_tags || null,
      verbosity: form.verbosity,
      forks: form.forks,
      credential_ids: form.credential_ids,
      extra_vars: parsed,
      requires_approval: form.requires_approval,
      diff_mode: form.diff_mode,
      survey_spec: form.survey_spec,
      ask_limit: form.ask_limit,
      ask_tags: form.ask_tags,
      ask_skip_tags: form.ask_skip_tags,
      ask_extra_vars: form.ask_extra_vars,
      ask_verbosity: form.ask_verbosity,
      ask_diff: form.ask_diff,
      ask_credentials: form.ask_credentials,
      ask_inventory: form.ask_inventory,
      ask_mode: form.ask_mode,
    };

    if (editing) {
      update.mutate(
        { id: editing.id, body: payload },
        {
          onSuccess: () => {
            close();
            toast("Template updated");
          },
        }
      );
    } else {
      create.mutate(payload, {
        onSuccess: () => {
          close();
          toast("Template created");
        },
      });
    }
  };

  return (
    <Section
      title="Job Templates"
      divider={false}
      actions={
        <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>
          Create template
        </Button>
      }
    >
      {(list.error || create.error || update.error || del.error) && (
        <ErrorBanner error={list.error || create.error || update.error || del.error} />
      )}

      <DataTable<JobTemplate>
        rows={list.data ?? []}
        loading={list.isLoading}
        empty={<p className="p-4 text-sm text-zinc-500">No job templates created yet.</p>}
        columns={[
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "desc", header: "Description", render: (r) => r.description || "-" },
          { key: "approval", header: "Requires approval", render: (r) => (r.requires_approval ? "Yes" : "No") },
          {
            key: "actions",
            header: "Actions",
            render: (r) => (
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => { setEditing(r); setOpen(true); }}>
                  Edit
                </Button>
                <Button size="sm" variant="danger" onClick={() => del.mutate(r.id)}>
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
        title={editing ? "Edit Template" : "Create Template"}
        initialFocusRef={first}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button onClick={submit} loading={create.isPending || update.isPending}>
              Save
            </Button>
          </div>
        }
      >
        <div className="grid gap-4">
          <TextInput ref={first} id="template-name" label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <TextInput id="template-description" label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

          {!projectId && (
            <Select id="template-project" label="Project" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
              <option value="">Select project</option>
              {(selectableProjects || []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
          )}

          <Select id="template-playbook" label="Playbook" value={form.playbook_id} onChange={(e) => setForm({ ...form, playbook_id: e.target.value })}>
            <option value="">Select playbook</option>
            {(playbooks.data || []).map((pb) => (
              <option key={pb.id} value={pb.id}>{pb.name} ({pb.rel_path})</option>
            ))}
          </Select>

          <Select id="template-inventory" label="Inventory" value={form.inventory_id} onChange={(e) => setForm({ ...form, inventory_id: e.target.value })}>
            <option value="">Select inventory</option>
            {(inventories.data || []).map((inv) => (
              <option key={inv.id} value={inv.id}>{inv.name}</option>
            ))}
          </Select>

          <TextInput id="template-limit" label="Limit pattern" value={form.limit_pattern} onChange={(e) => setForm({ ...form, limit_pattern: e.target.value })} />
          <TextInput id="template-tags" label="Tags" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
          <TextInput id="template-skip-tags" label="Skip tags" value={form.skip_tags} onChange={(e) => setForm({ ...form, skip_tags: e.target.value })} />

          <TextArea id="template-extravars" label="Extra Vars (JSON)" value={form.extra_vars} onChange={(e) => { setForm({ ...form, extra_vars: e.target.value }); setExtraError(""); }} />
          {extraError && <p className="text-xs text-red-500">{extraError}</p>}

          <div className="grid grid-cols-2 gap-3">
            <NumberInput id="template-verbosity" label="Verbosity" value={form.verbosity} onChange={(e) => setForm({ ...form, verbosity: Number(e.target.value) })} />
            <NumberInput id="template-forks" label="Forks" value={form.forks} onChange={(e) => setForm({ ...form, forks: Number(e.target.value) })} />
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-medium">Credentials</label>
            <CredentialSlots
              credentials={credentials.data}
              value={form.credential_ids}
              onChange={(ids) => setForm({ ...form, credential_ids: ids })}
              idPrefix="cred"
            />
          </div>

          <Checkbox id="template-approval" label="Requires approval" checked={form.requires_approval} onChange={(e) => setForm({ ...form, requires_approval: e.target.checked })} />
          <Checkbox id="template-diff" label="Diff mode" checked={form.diff_mode} onChange={(e) => setForm({ ...form, diff_mode: e.target.checked })} />

          {/* Fieldset: Prompt on Launch */}
          <fieldset className="space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <legend className="px-1 text-xs font-semibold">Prompt on Launch (allow requester overrides)</legend>
            <div className="grid grid-cols-2 gap-2">
              <Checkbox id="ask-limit" label="Limit" checked={form.ask_limit} onChange={(e) => setForm({ ...form, ask_limit: e.target.checked })} />
              <Checkbox id="ask-tags" label="Tags" checked={form.ask_tags} onChange={(e) => setForm({ ...form, ask_tags: e.target.checked })} />
              <Checkbox id="ask-skip-tags" label="Skip tags" checked={form.ask_skip_tags} onChange={(e) => setForm({ ...form, ask_skip_tags: e.target.checked })} />
              <Checkbox id="ask-extra-vars" label="Extra vars" checked={form.ask_extra_vars} onChange={(e) => setForm({ ...form, ask_extra_vars: e.target.checked })} />
              <Checkbox id="ask-verbosity" label="Verbosity" checked={form.ask_verbosity} onChange={(e) => setForm({ ...form, ask_verbosity: e.target.checked })} />
              <Checkbox id="ask-diff" label="Diff mode" checked={form.ask_diff} onChange={(e) => setForm({ ...form, ask_diff: e.target.checked })} />
              <Checkbox id="ask-credentials" label="Credentials" checked={form.ask_credentials} onChange={(e) => setForm({ ...form, ask_credentials: e.target.checked })} />
              <Checkbox id="ask-inventory" label="Inventory" checked={form.ask_inventory} onChange={(e) => setForm({ ...form, ask_inventory: e.target.checked })} />
              <Checkbox id="ask-mode" label="Execution mode" checked={form.ask_mode} onChange={(e) => setForm({ ...form, ask_mode: e.target.checked })} />
            </div>
          </fieldset>
        </div>
      </Drawer>
    </Section>
  );
}

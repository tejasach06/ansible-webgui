import { useEffect, useRef, useState, type Dispatch, type Ref, type SetStateAction } from "react";
import { useCredentials } from "../api/credentials";
import { useCreateInventories, useInventories } from "../api/inventories";
import { usePlaybooks } from "../api/playbooks";
import { useTemplates } from "../api/templates";
import type { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { parseExtra, type InventoryFormat, type JobMode, type JobTemplate, type SurveyField } from "../lib/types";
import { Button } from "./Button";
import { ErrorBanner } from "./ErrorBanner";
import { Checkbox, NumberInput, Select, TextArea, TextInput } from "./Field";
import { useToast } from "./Toast";
import { buildInventory } from "./InventoryHostsWizard";
import { fromSlots, toSlots } from "../lib/credentialSlots";
import { CredentialSlots } from "./CredentialSlots";
import { ModeBadge } from "./ModeBadge";

const slotMemoryKey = (projectId: number) => `awg.credSlots.v1.${projectId}`;

export function readSlotMemory(projectId: number): number[] {
  try {
    const raw = localStorage.getItem(slotMemoryKey(projectId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.every((x) => typeof x === "number")) {
      return parsed;
    }
    return [];
  } catch {
    return [];
  }
}

export function writeSlotMemory(projectId: number, ids: number[]): void {
  try {
    localStorage.setItem(slotMemoryKey(projectId), JSON.stringify(ids));
  } catch {
    // localStorage quota/private mode errors must not break launch
  }
}

const inventoryStarters: Record<InventoryFormat, string> = { yaml: buildInventory({ format: "yaml", group: "all", hosts: ["host1.example.com"] }), ini: buildInventory({ format: "ini", group: "all", hosts: ["host1.example.com"] }) };
function freshNewInventory() { return { name: "", filename: "", format: "yaml" as InventoryFormat, content: inventoryStarters.yaml }; }
export const init = { template_id: "", playbook_id: "", inventory_id: "", mode: "check" as JobMode, limit: "", tags: "", skip_tags: "", verbosity: 0, forks: 5, become: false, become_user: "", become_method: "", credential_ids: [] as number[], extra_vars: "{}", diff: false, survey_answers: {} as Record<string, unknown> };
export type LaunchForm = typeof init;
export function surveyComplete(form: LaunchForm, spec?: SurveyField[]) { return !(spec ?? []).some((f) => f.required && (form.survey_answers[f.var] === undefined || form.survey_answers[f.var] === "")); }
export function buildLaunchBody(form: LaunchForm) { const extra_vars = parseExtra(form.extra_vars); if (!extra_vars) return null; return { template_id: form.template_id ? Number(form.template_id) : null, playbook_id: Number(form.playbook_id), inventory_id: form.inventory_id ? Number(form.inventory_id) : null, mode: form.mode, limit: form.limit || null, tags: form.tags || null, skip_tags: form.skip_tags || null, extra_vars, survey_answers: form.survey_answers, verbosity: Number(form.verbosity), forks: Number(form.forks), become: form.become, become_user: form.become_user || null, become_method: form.become_method || null, credential_ids: form.credential_ids, diff: form.diff }; }

export function formFromTemplate(form: LaunchForm, t: JobTemplate | undefined, id: string): LaunchForm {
  return {
    ...form,
    template_id: id,
    playbook_id: t ? String(t.playbook_id) : form.playbook_id,
    inventory_id: t?.inventory_id ? String(t.inventory_id) : form.inventory_id,
    mode: t ? "live" : form.mode,
    limit: t?.limit_pattern ?? "",
    tags: t?.tags ?? "",
    skip_tags: t?.skip_tags ?? "",
    verbosity: t?.verbosity ?? form.verbosity,
    forks: t?.forks ?? form.forks,
    credential_ids: t ? t.credential_ids : form.credential_ids,
    extra_vars: JSON.stringify(t?.extra_vars ?? {}, null, 2),
    diff: t?.diff_mode ?? form.diff,
    survey_answers: {},
  };
}

function LockedHint({ show }: { show: boolean }) { return show ? <p className="-mt-2 text-xs text-zinc-500 dark:text-zinc-400">Locked by template</p> : null; }

export function JobLaunchForm({ form, setForm, extraError, setExtraError, lockPlaybook = false, firstRef, onTemplateChange }: { form: LaunchForm; setForm: Dispatch<SetStateAction<LaunchForm>>; extraError?: string; setExtraError?: Dispatch<SetStateAction<string>>; lockPlaybook?: boolean; firstRef?: Ref<HTMLSelectElement>; onTemplateChange?: (id: string) => void; }) {
  const { canAny, canInventoryWrite, canInProject } = useAuth();
  const { toast } = useToast();
  const templates = useTemplates();
  const selectedTemplate = templates.data?.find((x) => String(x.id) === form.template_id);
  const survey = selectedTemplate?.survey_spec ?? [];
  const playbooks = usePlaybooks();
  const selectedPlaybook = playbooks.data?.find((p) => String(p.id) === form.playbook_id);
  const launchProjectId = selectedPlaybook?.project_id ?? selectedTemplate?.project_id;
  const inventories = useInventories();
  const credentials = useCredentials(launchProjectId);
  const memoryAppliedProjectRef = useRef<number | null>(null);

  useEffect(() => {
    if (
      launchProjectId &&
      !selectedTemplate &&
      form.credential_ids.length === 0 &&
      credentials.data &&
      memoryAppliedProjectRef.current !== launchProjectId
    ) {
      memoryAppliedProjectRef.current = launchProjectId;
      const remembered = fromSlots(toSlots(credentials.data, readSlotMemory(launchProjectId)));
      if (remembered.length > 0) {
        setForm((f) => ({ ...f, credential_ids: remembered }));
      }
    }
  }, [launchProjectId, selectedTemplate, form.credential_ids.length, credentials.data, setForm]);
  const createInventory = useCreateInventories();
  const [newInventoryOpen, setNewInventoryOpen] = useState(false);
  const [newInventory, setNewInventory] = useState(freshNewInventory);
  const createError = createInventory.error as ApiError | undefined;
  const invalidYaml = createError?.code === "invalid_yaml" ? String(createError.detail?.stderr ?? "") : "";
  const newInventoryValid = newInventory.name.trim() && newInventory.filename.trim();
  const adHocForbidden = !selectedTemplate && !!selectedPlaybook && !canInProject(selectedPlaybook.project_id, "project.admin");
  const locked = (flag?: boolean) => !!selectedTemplate && !flag;

  const setTemplate = (id: string) => {
    const t = templates.data?.find((x) => String(x.id) === id);
    if (onTemplateChange) onTemplateChange(id);
    else setForm(formFromTemplate(form, t, id));
  };
  const openNewInventory = () => { if (!canInventoryWrite) return; createInventory.reset(); setNewInventoryOpen(true); };
  const setInventory = (id: string) => { if (id === "__new") { openNewInventory(); return; } setForm({ ...form, inventory_id: id }); };
  const setNewInventoryFormat = (format: InventoryFormat) => setNewInventory((current) => ({ ...current, format, content: current.content === inventoryStarters[current.format] ? inventoryStarters[format] : current.content }));
  const cancelNewInventory = () => { createInventory.reset(); setNewInventory(freshNewInventory()); setNewInventoryOpen(false); };
  const createNewInventory = async () => { try { const created = await createInventory.mutateAsync({ name: newInventory.name, filename: newInventory.filename, format: newInventory.format, content: newInventory.content }); setForm((current) => ({ ...current, inventory_id: String(created.id) })); setNewInventory(freshNewInventory()); setNewInventoryOpen(false); toast("Inventory created"); } catch { /* mutation state feeds ErrorBanner */ } };
  const answer = (key: string, value: unknown) => setForm({ ...form, survey_answers: { ...form.survey_answers, [key]: value } });

  return <div className="grid gap-3">
    {!lockPlaybook && <Select ref={firstRef} id="job-template" label="Template" value={form.template_id} onChange={(e) => setTemplate(e.target.value)}><option value="">No template</option>{templates.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</Select>}
    {!lockPlaybook && <Select id="job-playbook" label="Playbook" value={form.playbook_id} disabled={!!form.template_id} onChange={(e) => {
      const nextPbId = e.target.value;
      const nextPb = playbooks.data?.find((p) => String(p.id) === nextPbId);
      const nextProjectId = nextPb?.project_id ?? selectedTemplate?.project_id;
      const shouldResetCreds = nextProjectId !== launchProjectId;
      setForm({
        ...form,
        playbook_id: nextPbId,
        credential_ids: shouldResetCreds ? [] : form.credential_ids,
      });
    }}><option value="">Select playbook</option>{playbooks.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>}
    {adHocForbidden && <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">Ad-hoc launches without a template are restricted to project admins.</p>}

    <Select ref={lockPlaybook ? firstRef : undefined} id="job-inventory" label="Inventory" value={form.inventory_id} disabled={locked(selectedTemplate?.ask_inventory)} onChange={(e) => setInventory(e.target.value)}><option value="">Select inventory</option>{inventories.data?.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}{canInventoryWrite && !locked(selectedTemplate?.ask_inventory) && <option value="__new">+ New inventory…</option>}</Select>
    <LockedHint show={locked(selectedTemplate?.ask_inventory)} />

    {newInventoryOpen && canInventoryWrite && <div className="grid gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60"><div><div className="text-sm font-medium">New inventory</div><p className="text-xs text-zinc-500 dark:text-zinc-400">Create a global inventory and select it for this launch.</p></div>{createInventory.error && <ErrorBanner error={createInventory.error} />}{invalidYaml && <pre className="max-h-40 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 dark:bg-zinc-900">{invalidYaml}</pre>}<TextInput id="job-new-inventory-name" label="Name" value={newInventory.name} onChange={(e) => setNewInventory({ ...newInventory, name: e.target.value })} /><TextInput id="job-new-inventory-filename" label="File name (e.g. hosts.yml)" value={newInventory.filename} onChange={(e) => setNewInventory({ ...newInventory, filename: e.target.value })} /><Select id="job-new-inventory-format" label="Format" value={newInventory.format} onChange={(e) => setNewInventoryFormat(e.target.value as InventoryFormat)}><option value="yaml">YAML</option><option value="ini">INI</option></Select><TextArea id="job-new-inventory-content" label="Inventory content" value={newInventory.content} onChange={(e) => setNewInventory({ ...newInventory, content: e.target.value })} rows={5} spellCheck={false} /><div className="flex justify-end gap-2"><Button size="sm" variant="secondary" onClick={cancelNewInventory}>Cancel</Button><Button size="sm" disabled={!newInventoryValid} loading={createInventory.isPending} onClick={createNewInventory}>Create & select</Button></div></div>}

    <div className="flex items-end gap-2">
      <div className="flex-1">
        <Select id="job-mode" label="Mode" value={form.mode} disabled={(canAny("job.run_check") && !canAny("job.request")) || locked(selectedTemplate?.ask_mode)} onChange={(e) => setForm({ ...form, mode: e.target.value as JobMode })}><option value="check">check</option><option value="live">live</option></Select>
      </div>
      <div className="pb-2">
        <ModeBadge mode={form.mode} />
      </div>
    </div>
    <LockedHint show={locked(selectedTemplate?.ask_mode)} />
    <TextInput id="job-limit" label="Limit" value={form.limit} disabled={locked(selectedTemplate?.ask_limit)} onChange={(e) => setForm({ ...form, limit: e.target.value })} />
    <LockedHint show={locked(selectedTemplate?.ask_limit)} />
    <TextInput id="job-tags" label="Tags" value={form.tags} disabled={locked(selectedTemplate?.ask_tags)} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
    <LockedHint show={locked(selectedTemplate?.ask_tags)} />
    <TextInput id="job-skip" label="Skip tags" value={form.skip_tags} disabled={locked(selectedTemplate?.ask_skip_tags)} onChange={(e) => setForm({ ...form, skip_tags: e.target.value })} />
    <LockedHint show={locked(selectedTemplate?.ask_skip_tags)} />
    <NumberInput id="job-verbosity" label="Verbosity" min={0} max={4} value={form.verbosity} disabled={locked(selectedTemplate?.ask_verbosity)} onChange={(e) => setForm({ ...form, verbosity: Number(e.target.value) })} />
    <LockedHint show={locked(selectedTemplate?.ask_verbosity)} />
    <NumberInput id="job-forks" label="Forks" value={form.forks} onChange={(e) => setForm({ ...form, forks: Number(e.target.value) })} />
    <Checkbox id="job-become" label="Become" checked={form.become} onChange={(e) => setForm({ ...form, become: e.target.checked })} />
    <Checkbox id="job-diff" label="Diff" checked={form.diff} disabled={locked(selectedTemplate?.ask_diff)} onChange={(e) => setForm({ ...form, diff: e.target.checked })} />
    <LockedHint show={locked(selectedTemplate?.ask_diff)} />
    <TextInput id="job-become-user" label="Become user" value={form.become_user} onChange={(e) => setForm({ ...form, become_user: e.target.value })} />
    <TextInput id="job-become-method" label="Become method" value={form.become_method} onChange={(e) => setForm({ ...form, become_method: e.target.value })} />

    {survey.length > 0 && <div className="grid gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/60"><div><div className="text-sm font-medium">Survey</div><p className="text-xs text-zinc-500 dark:text-zinc-400">Answer launch prompts for this template.</p></div>{survey.map((f) => f.type === "textarea" ? <TextArea key={f.var} id={`survey-${f.var}`} label={f.label} value={String(form.survey_answers[f.var] ?? f.default ?? "")} onChange={(e) => answer(f.var, e.target.value)} /> : f.type === "boolean" ? <Checkbox key={f.var} id={`survey-${f.var}`} label={f.label} checked={Boolean(form.survey_answers[f.var] ?? f.default)} onChange={(e) => answer(f.var, e.target.checked)} /> : f.type === "choice" ? <Select key={f.var} id={`survey-${f.var}`} label={f.label} value={String(form.survey_answers[f.var] ?? f.default ?? "")} onChange={(e) => answer(f.var, e.target.value)}><option value="">Select</option>{f.choices.map((c) => <option key={c} value={c}>{c}</option>)}</Select> : f.type === "integer" ? <NumberInput key={f.var} id={`survey-${f.var}`} label={f.label} min={f.min ?? undefined} max={f.max ?? undefined} value={String(form.survey_answers[f.var] ?? f.default ?? "")} onChange={(e) => answer(f.var, e.target.value)} /> : <TextInput key={f.var} id={`survey-${f.var}`} label={f.label} type={f.type === "password" ? "password" : "text"} value={String(form.survey_answers[f.var] ?? f.default ?? "")} onChange={(e) => answer(f.var, e.target.value)} />)}</div>}

    <div className="grid gap-1">
      <span className="text-sm font-medium">Credentials</span>
      {launchProjectId ? (
        <CredentialSlots
          credentials={credentials.data}
          value={form.credential_ids}
          onChange={(ids) => setForm({ ...form, credential_ids: ids })}
          disabled={locked(selectedTemplate?.ask_credentials)}
          idPrefix="job-cred"
          autoSelectMachine
          emptyCta
        />
      ) : (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">Select a playbook to choose credentials.</p>
      )}
      <LockedHint show={locked(selectedTemplate?.ask_credentials)} />
      {form.become &&
        !credentials.data
          ?.filter((c) => form.credential_ids.includes(c.id))
          .some((c) => c.kind === "become_password" || c.become_same_as_ssh || c.kind === "ssh_key") && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            Become is enabled but no selected credential provides a sudo password. Enable "Sudo uses this same password" on the SSH password credential, or select a become password credential.
          </p>
        )}
    </div>
    <TextArea id="job-extra" label="Extra vars" value={form.extra_vars} error={extraError} disabled={locked(selectedTemplate?.ask_extra_vars)} onChange={(e) => { setExtraError?.(""); setForm({ ...form, extra_vars: e.target.value }); }} />
    <LockedHint show={locked(selectedTemplate?.ask_extra_vars)} />
  </div>;
}

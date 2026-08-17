import { useRef, useState } from "react";
import { Plus } from "lucide-react";
import { useSchedules, useCreateSchedules, useUpdateSchedules, useDeleteSchedules } from "../api/schedules";
import { useTemplates } from "../api/templates";
import { useAuth } from "../lib/auth";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { Section } from "./Section";
import { DataTable } from "./DataTable";
import { Drawer } from "./Drawer";
import { ConfirmDialog } from "./ConfirmDialog";
import { TextInput, Select, Checkbox } from "./Field";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";
import type { Schedule } from "../lib/types";

const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function SchedulesPanel({ projectId }: { projectId: number }) {
  const { canInProject } = useAuth();
  const canWrite = canInProject(projectId, "schedule.write");
  const { toast } = useToast();

  const list = useSchedules();
  const templates = useTemplates(projectId);
  const create = useCreateSchedules();
  const update = useUpdateSchedules();
  const del = useDeleteSchedules();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ template_id: "", name: "", cron_expr: "", timezone: tz });
  const [target, setTarget] = useState<Schedule>();
  const first = useRef<HTMLSelectElement>(null);

  const tmplMap = new Map((templates.data ?? []).map((t) => [t.id, t.name]));
  const projectSchedules = (list.data ?? []).filter((s) => tmplMap.has(s.template_id));

  const close = () => {
    setOpen(false);
    setForm({ template_id: "", name: "", cron_expr: "", timezone: tz });
  };

  const valid = form.template_id && form.name.trim() && form.cron_expr.trim() && form.timezone.trim();

  return (
    <Section
      title="Schedules"
      divider={false}
      actions={
        canWrite && (
          <Button icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => setOpen(true)}>
            Create schedule
          </Button>
        )
      }
    >
      {(list.error || create.error || update.error || del.error) && (
        <ErrorBanner error={list.error || create.error || update.error || del.error} />
      )}

      <DataTable<Schedule>
        rows={projectSchedules}
        loading={list.isLoading || templates.isLoading}
        empty={<EmptyState>No schedules yet for this project.</EmptyState>}
        columns={[
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "template", header: "Template", render: (r) => tmplMap.get(r.template_id) || r.template_id },
          { key: "cron", header: "Cron", render: (r) => <span className="font-mono">{r.cron_expr}</span> },
          { key: "tz", header: "Timezone", render: (r) => r.timezone },
          {
            key: "enabled",
            header: "Status",
            render: (r) => (
              <Checkbox
                id={`schedule-${r.id}-enabled`}
                label=""
                aria-label={`Toggle schedule ${r.name}`}
                disabled={!canWrite}
                checked={r.enabled}
                onChange={(e) =>
                  update.mutate(
                    { id: r.id, body: { enabled: e.target.checked } },
                    { onSuccess: () => toast(e.target.checked ? "Schedule enabled" : "Schedule disabled") }
                  )
                }
              />
            ),
          },
          {
            key: "actions",
            header: "Actions",
            render: (r) =>
              canWrite && (
                <Button size="sm" variant="danger" onClick={() => setTarget(r)}>
                  Delete
                </Button>
              ),
          },
        ]}
      />

      <Drawer
        open={open}
        onClose={close}
        title="Create schedule"
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
                  { ...form, template_id: Number(form.template_id) },
                  {
                    onSuccess: () => {
                      close();
                      toast("Schedule created");
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
            ref={first}
            id="schedule-template"
            label="Template"
            value={form.template_id}
            onChange={(e) => setForm({ ...form, template_id: e.target.value })}
          >
            <option value="">Select template</option>
            {(templates.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
          <TextInput id="schedule-name" label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <TextInput id="schedule-cron" label="Cron expression (e.g. 0 0 * * *)" value={form.cron_expr} onChange={(e) => setForm({ ...form, cron_expr: e.target.value })} />
          <TextInput id="schedule-tz" label="Timezone" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
        </div>
      </Drawer>

      <ConfirmDialog
        open={!!target}
        title="Delete schedule?"
        name={target?.name ?? ""}
        onClose={() => setTarget(undefined)}
        onConfirm={() =>
          target &&
          del.mutate(target.id, {
            onSuccess: () => {
              setTarget(undefined);
              toast("Schedule deleted");
            },
          })
        }
      />
    </Section>
  );
}

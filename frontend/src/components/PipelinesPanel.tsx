import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import type { Pipeline, PipelineStepInput, JobTemplate } from "../lib/types";
import { useAuth } from "../lib/auth";
import { Button } from "./Button";
import { Section } from "./Section";
import { TextInput, Checkbox } from "./Field";
import { DataTable } from "./DataTable";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";
import { Dialog } from "./Dialog";

export function PipelinesPanel({ projectId }: { projectId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { canInProject } = useAuth();
  const canWrite = canInProject(projectId, "pipeline.write");
  const canRun = canInProject(projectId, "job.request");

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<PipelineStepInput[]>([]);

  const { data: pipelines, isLoading, error } = useQuery({
    queryKey: ["pipelines", projectId],
    queryFn: () => apiFetch<Pipeline[]>(`/api/pipelines?project_id=${projectId}`),
  });

  const { data: templates } = useQuery({
    queryKey: ["templates", projectId],
    queryFn: () => apiFetch<JobTemplate[]>(`/api/job_templates?project_id=${projectId}`),
  });

  const createMutation = useMutation({
    mutationFn: (body: unknown) =>
      apiFetch<{ id: number }>("/api/pipelines", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines", projectId] });
      setOpen(false);
      setName("");
      setDescription("");
      setSteps([]);
    },
  });

  const runMutation = useMutation({
    mutationFn: (pipelineId: number) =>
      apiFetch<{ id: number }>(`/api/pipelines/${pipelineId}/run`, { method: "POST" }),
    onSuccess: (data) => navigate(`/pipelines/runs/${data.id}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (pipelineId: number) =>
      apiFetch(`/api/pipelines/${pipelineId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines", projectId] });
    },
  });

  const handleAddStep = () => {
    if (!templates || templates.length === 0) return;
    const newStep: PipelineStepInput = {
      template_id: templates[0].id,
      requires_approval: false,
      continue_on_failure: false,
    };
    setSteps([...steps, newStep]);
  };

  const handleRemoveStep = (index: number) => setSteps(steps.filter((_, i) => i !== index));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || steps.length === 0) return;
    createMutation.mutate({
      project_id: projectId,
      name,
      description,
      steps,
    });
  };

  return (
    <Section
      title="Pipelines"
      divider={false}
      actions={canWrite && <Button onClick={() => setOpen(true)}>Create pipeline</Button>}
    >
      {(error || createMutation.error || runMutation.error || deleteMutation.error) && <ErrorBanner error={error || createMutation.error || runMutation.error || deleteMutation.error} />}

      <DataTable<Pipeline>
        rows={pipelines ?? []}
        loading={isLoading}
        empty={<EmptyState>No pipelines created yet.</EmptyState>}
        columns={[
          { key: "name", header: "Name", render: (p) => <span className="font-medium">{p.name}</span> },
          { key: "description", header: "Description", render: (p) => p.description || "-" },
          {
            key: "actions",
            header: "Actions",
            render: (p) => (
              <div className="flex gap-2">
                {canRun && <Button size="sm" onClick={() => runMutation.mutate(p.id)} loading={runMutation.isPending}>Run</Button>}
                {canWrite && <Button variant="danger" size="sm" onClick={() => deleteMutation.mutate(p.id)} loading={deleteMutation.isPending}>Delete</Button>}
              </div>
            ),
          },
        ]}
      />

      <Dialog open={open} onClose={() => setOpen(false)} title="Create pipeline">
        <form onSubmit={handleSubmit} className="space-y-4">
          <TextInput id="pipeline-name" label="Pipeline name" type="text" value={name} onChange={(e) => setName(e.target.value)} required />
          <TextInput id="pipeline-description" label="Description" type="text" value={description} onChange={(e) => setDescription(e.target.value)} />

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">Ordered steps</span>
              <Button type="button" size="sm" variant="secondary" onClick={handleAddStep} disabled={!templates?.length}>+ Add step</Button>
            </div>
            {steps.map((step, index) => (
              <div key={index} className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <span className="text-xs font-bold">{index + 1}.</span>
                <select value={step.template_id} onChange={(e) => setSteps(steps.map((s, i) => (i === index ? { ...s, template_id: Number(e.target.value) } : s)))} className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-950">
                  {(templates ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <Checkbox id={`step-approval-${index}`} label="Requires approval" checked={step.requires_approval} onChange={(e) => setSteps(steps.map((s, i) => (i === index ? { ...s, requires_approval: e.target.checked } : s)))} />
                <Checkbox id={`step-continue-${index}`} label="Continue on failure" checked={step.continue_on_failure} onChange={(e) => setSteps(steps.map((s, i) => (i === index ? { ...s, continue_on_failure: e.target.checked } : s)))} />
                <Button type="button" size="sm" variant="danger" onClick={() => handleRemoveStep(index)}>Remove</Button>
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={!name.trim() || createMutation.isPending || steps.length === 0}>Create pipeline</Button>
          </div>
        </form>
      </Dialog>
    </Section>
  );
}

export default PipelinesPanel;

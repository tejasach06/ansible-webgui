import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { JobTemplate } from "../lib/types";
export function useTemplates(projectId?: number) { const qs=projectId?`?project_id=${projectId}`:""; return useQuery({ queryKey: ["templates", projectId], queryFn: () => apiFetch<JobTemplate[]>("/api/job_templates"+qs) }); }
export function useCreateTemplates() { const qc=useQueryClient(); return useMutation({ mutationFn: (body: unknown) => apiFetch<JobTemplate>("/api/job_templates", { method:"POST", body: JSON.stringify(body) }), onSuccess: () => qc.invalidateQueries({ queryKey:["templates"] }) }); }
export function useUpdateTemplates() { const qc=useQueryClient(); return useMutation({ mutationFn: (v: {id:number; body:unknown}) => apiFetch<JobTemplate>(`/api/job_templates/${v.id}`, { method:"PATCH", body: JSON.stringify(v.body) }), onSuccess: () => qc.invalidateQueries({ queryKey:["templates"] }) }); }
export function useDeleteTemplates() { const qc=useQueryClient(); return useMutation({ mutationFn: (id:number) => apiFetch(`/api/job_templates/${id}`, { method:"DELETE" }), onSuccess: () => qc.invalidateQueries({ queryKey:["templates"] }) }); }

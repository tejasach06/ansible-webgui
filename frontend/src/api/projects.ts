import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { Project } from "../lib/types";
export function useProjects(projectId?: number) { const qs=projectId?`?project_id=${projectId}`:""; return useQuery({ queryKey: ["projects", projectId], queryFn: () => apiFetch<Project[]>("/api/projects"+qs) }); }
export function useCreateProjects() { const qc=useQueryClient(); return useMutation({ mutationFn: (body: unknown) => apiFetch<Project>("/api/projects", { method:"POST", body: JSON.stringify(body) }), onSuccess: () => qc.invalidateQueries({ queryKey:["projects"] }) }); }
export function useDeleteProjects() { const qc=useQueryClient(); return useMutation({ mutationFn: (id:number) => apiFetch(`/api/projects/${id}`, { method:"DELETE" }), onSuccess: () => qc.invalidateQueries({ queryKey:["projects"] }) }); }
export function useUpdateProject(id:number) { const qc=useQueryClient(); return useMutation({ mutationFn:(body:unknown)=>apiFetch<Project>(`/api/projects/${id}`, { method:"PATCH", body: JSON.stringify(body) }), onSuccess:()=>qc.invalidateQueries({ queryKey:["projects"] }) }); }

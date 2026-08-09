import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { Credential } from "../lib/types";
export function useCredentials(projectId?: number) { const qs=projectId?`?project_id=${projectId}`:""; return useQuery({ queryKey: ["credentials", projectId], queryFn: () => apiFetch<Credential[]>("/api/credentials"+qs) }); }
export function useCreateCredentials() { const qc=useQueryClient(); return useMutation({ mutationFn: (body: unknown) => apiFetch<Credential>("/api/credentials", { method:"POST", body: JSON.stringify(body) }), onSuccess: () => qc.invalidateQueries({ queryKey:["credentials"] }) }); }
export function useDeleteCredentials() { const qc=useQueryClient(); return useMutation({ mutationFn: (id:number) => apiFetch(`/api/credentials/${id}`, { method:"DELETE" }), onSuccess: () => qc.invalidateQueries({ queryKey:["credentials"] }) }); }
export function useUpdateCredential(id:number) { const qc=useQueryClient(); return useMutation({ mutationFn:(body:unknown)=>apiFetch<Credential>(`/api/credentials/${id}`, { method:"PATCH", body: JSON.stringify(body) }), onSuccess:()=>qc.invalidateQueries({ queryKey:["credentials"] }) }); }

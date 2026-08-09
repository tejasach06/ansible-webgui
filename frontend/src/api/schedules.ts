import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { Schedule } from "../lib/types";
export function useSchedules(projectId?: number) { const qs=projectId?`?project_id=${projectId}`:""; return useQuery({ queryKey: ["schedules", projectId], queryFn: () => apiFetch<Schedule[]>("/api/schedules"+qs) }); }
export function useCreateSchedules() { const qc=useQueryClient(); return useMutation({ mutationFn: (body: unknown) => apiFetch<Schedule>("/api/schedules", { method:"POST", body: JSON.stringify(body) }), onSuccess: () => qc.invalidateQueries({ queryKey:["schedules"] }) }); }
export function useUpdateSchedules() { const qc=useQueryClient(); return useMutation({ mutationFn: (v: {id:number; body:unknown}) => apiFetch<Schedule>(`/api/schedules/${v.id}`, { method:"PATCH", body: JSON.stringify(v.body) }), onSuccess: () => qc.invalidateQueries({ queryKey:["schedules"] }) }); }
export function useDeleteSchedules() { const qc=useQueryClient(); return useMutation({ mutationFn: (id:number) => apiFetch(`/api/schedules/${id}`, { method:"DELETE" }), onSuccess: () => qc.invalidateQueries({ queryKey:["schedules"] }) }); }

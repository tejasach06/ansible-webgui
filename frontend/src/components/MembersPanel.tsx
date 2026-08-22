import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { ProjectMember } from "../lib/types";
import { useAuth } from "../lib/auth";
import { Button } from "./Button";
import { Section } from "./Section";
import { TextInput, Select } from "./Field";
import { DataTable } from "./DataTable";
import { ErrorBanner } from "./ErrorBanner";
import { EmptyState } from "./EmptyState";

export function MembersPanel({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const { canInProject } = useAuth();
  const canAdmin = canInProject(projectId, "project.admin");

  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState<ProjectMember["role"]>("developer");

  const { data: members, isLoading, error } = useQuery({
    queryKey: ["project_members", projectId],
    queryFn: () => apiFetch<ProjectMember[]>(`/api/projects/${projectId}/members`),
  });

  const upsertMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: ProjectMember["role"] }) =>
      apiFetch(`/api/projects/${projectId}/members/${userId}`, {
        method: "PUT",
        body: JSON.stringify({ role }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project_members", projectId] });
      setNewUserId("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (userId: number) =>
      apiFetch(`/api/projects/${projectId}/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project_members", projectId] });
    },
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    const uid = parseInt(newUserId, 10);
    if (Number.isNaN(uid) || uid <= 0) return;
    upsertMutation.mutate({ userId: uid, role: newRole });
  };

  return (
    <Section title="Members" divider={false}>
      {canAdmin && (
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3 rounded-lg bg-zinc-50 p-4 dark:bg-zinc-900">
          <TextInput id="member-user-id" label="User ID" type="number" value={newUserId} onChange={(e) => setNewUserId(e.target.value)} placeholder="e.g. 2" required />
          <Select id="member-role" label="Role" value={newRole} onChange={(e) => setNewRole(e.target.value as ProjectMember["role"])}>
            <option value="owner">Owner</option>
            <option value="maintainer">Maintainer</option>
            <option value="developer">Developer</option>
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
          </Select>
          <Button type="submit" size="sm" loading={upsertMutation.isPending}>Add / Update member</Button>
        </form>
      )}

      {(error || upsertMutation.error || deleteMutation.error) && <ErrorBanner error={error || upsertMutation.error || deleteMutation.error} />}

      <DataTable<ProjectMember>
        rows={members ?? []}
        loading={isLoading}
        empty={<EmptyState>No members in this project.</EmptyState>}
        columns={[
          { key: "user_id", header: "User ID", render: (m) => m.user_id },
          { key: "username", header: "Username", render: (m) => m.username },
          {
            key: "role",
            header: "Role",
            render: (m) =>
              canAdmin ? (
                <select value={m.role} onChange={(e) => upsertMutation.mutate({ userId: m.user_id, role: e.target.value as ProjectMember["role"] })} className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
                  <option value="owner">Owner</option>
                  <option value="maintainer">Maintainer</option>
                  <option value="developer">Developer</option>
                  <option value="operator">Operator</option>
                  <option value="viewer">Viewer</option>
                </select>
              ) : (
                <span className="capitalize">{m.role}</span>
              ),
          },
          {
            key: "actions",
            header: "Actions",
            render: (m) => canAdmin && <Button variant="danger" size="sm" onClick={() => deleteMutation.mutate(m.user_id)} loading={deleteMutation.isPending}>Remove</Button>,
          },
        ]}
      />
    </Section>
  );
}


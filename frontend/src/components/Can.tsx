import type { ReactNode } from "react";
import { useAuth } from "../lib/auth";
export function Can({ perm, projectId, children }: { perm: string; projectId?: number; children: ReactNode }) {
  const { can, canInProject } = useAuth();
  return (projectId ? canInProject(projectId, perm) : can(perm)) ? <>{children}</> : null;
}

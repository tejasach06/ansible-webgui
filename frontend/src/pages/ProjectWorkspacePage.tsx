import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { InventoriesPanel } from "../components/InventoriesPanel";
import { PlaybooksPanel } from "../components/PlaybooksPanel";
import { ProjectFilesPanel } from "../components/ProjectFilesPanel";
import { RunJobDialog } from "../components/RunJobDialog";
import { TemplatesPanel } from "../components/TemplatesPanel";
import { CredentialsPanel } from "../components/CredentialsPanel";
import { SchedulesPanel } from "../components/SchedulesPanel";
import { MembersPanel } from "../components/MembersPanel";
import { PipelinesPanel } from "../components/PipelinesPanel";
import { useProjects } from "../api/projects";
import { useAuth } from "../lib/auth";
import { useState } from "react";

const tabs = ["files", "playbooks", "inventories", "credentials", "templates", "pipelines", "schedules", "members"] as const;
type Tab = (typeof tabs)[number];
const tabLabels: Record<Tab, string> = {
  files: "Files",
  playbooks: "Playbooks",
  inventories: "Inventories",
  credentials: "Credentials",
  templates: "Templates",
  pipelines: "Pipelines",
  schedules: "Schedules",
  members: "Members",
};

export function ProjectWorkspacePage() {
  const projectId = Number(useParams().projectId);
  const { canInProject } = useAuth();
  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab");
  const tab: Tab = tabs.includes(rawTab as Tab) ? (rawTab as Tab) : "files";
  const setTab = (next: Tab) => setParams(next === "files" ? {} : { tab: next });

  const projects = useProjects();
  const project = projects.data?.find((p) => p.id === projectId);
  const [run, setRun] = useState(false);
  const canRun = canInProject(projectId, "job.request") || canInProject(projectId, "job.run_check");

  if (projects.error) return <ErrorBanner error={projects.error} />;
  if (!projects.isLoading && !project)
    return (
      <EmptyState action={<Link className="underline" to="/projects">Back to projects</Link>}>
        Project not found.
      </EmptyState>
    );

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <Link className="text-sm underline" to="/projects">
            ← Projects
          </Link>
          <h1 className="text-xl font-semibold">{project?.name ?? "Project"}</h1>
          <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-500 dark:text-zinc-400">
            <div>
              <dt className="inline font-medium">Git path: </dt>
              <dd className="inline font-mono">{project?.git_path ?? "—"}</dd>
            </div>
            <div>
              <dt className="inline font-medium">Branch: </dt>
              <dd className="inline font-mono">{project?.default_branch ?? "—"}</dd>
            </div>
          </dl>
        </div>
        {canRun && <Button onClick={() => setRun(true)}>Run playbook</Button>}
      </div>

      <RunJobDialog open={run} onClose={() => setRun(false)} projectId={projectId} />

      <div className="border-b border-zinc-200 dark:border-zinc-800">
        <nav className="-mb-px flex gap-4 overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`border-b-2 py-2 text-sm font-medium transition-colors ${
                tab === t
                  ? "border-zinc-900 text-zinc-900 dark:border-zinc-50 dark:text-zinc-50"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
            >
              {tabLabels[t]}
            </button>
          ))}
        </nav>
      </div>

      {tab === "files" && <ProjectFilesPanel projectId={projectId} />}
      {tab === "playbooks" && <PlaybooksPanel projectId={projectId} />}
      {tab === "inventories" && <InventoriesPanel />}
      {tab === "credentials" && <CredentialsPanel projectId={projectId} />}
      {tab === "templates" && <TemplatesPanel projectId={projectId} />}
      {tab === "pipelines" && <PipelinesPanel projectId={projectId} />}
      {tab === "schedules" && <SchedulesPanel projectId={projectId} />}
      {tab === "members" && <MembersPanel projectId={projectId} />}
    </section>
  );
}

export default ProjectWorkspacePage;

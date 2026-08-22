import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Tabs } from "../components/Tabs";
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
import { cn, linkClass } from "../lib/cn";
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
  if (!projects.isLoading && (!project || project.is_inventory_repo))
    return (
      <EmptyState action={<Link className={linkClass} to="/projects">Back to projects</Link>}>
        Project not found.
      </EmptyState>
    );

  return (
    <section className="grid gap-4">
      <div className="grid gap-2">
        <Link className={cn("inline-flex items-center gap-1 text-sm", linkClass)} to="/projects">
          <ArrowLeft size={14} strokeWidth={1.5} />Projects
        </Link>
        <PageHeader
          title={project?.name ?? "Project"}
          actions={canRun && <Button onClick={() => setRun(true)}>Run playbook</Button>}
        />
        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-500 dark:text-zinc-400">
          <div>
            <dt className="inline font-medium">Git path: </dt>
            <dd className="inline font-mono">{project?.git_path ?? "-"}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Branch: </dt>
            <dd className="inline font-mono">{project?.default_branch ?? "-"}</dd>
          </div>
        </dl>
      </div>

      <RunJobDialog open={run} onClose={() => setRun(false)} projectId={projectId} />

      <Tabs tabs={tabs} value={tab} onChange={setTab} labels={tabLabels} />
      {tab === "files" && <ProjectFilesPanel projectId={projectId} />}
      {tab === "playbooks" && <PlaybooksPanel projectId={projectId} />}
      {tab === "inventories" && <InventoriesPanel projectId={projectId} />}
      {tab === "credentials" && <CredentialsPanel projectId={projectId} />}
      {tab === "templates" && <TemplatesPanel projectId={projectId} />}
      {tab === "pipelines" && <PipelinesPanel projectId={projectId} />}
      {tab === "schedules" && <SchedulesPanel projectId={projectId} />}
      {tab === "members" && <MembersPanel projectId={projectId} />}
    </section>
  );
}

export default ProjectWorkspacePage;

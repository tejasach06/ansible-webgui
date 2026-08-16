import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useInventories } from "../api/inventories";
import { usePlaybooks } from "../api/playbooks";
import { useProjects } from "../api/projects";
import { useTemplates } from "../api/templates";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { InventoriesPanel } from "../components/InventoriesPanel";
import { PlaybooksPanel } from "../components/PlaybooksPanel";
import { ProjectFilesPanel } from "../components/ProjectFilesPanel";
import { RunJobDialog } from "../components/RunJobDialog";
import { TemplatesPanel } from "../components/TemplatesPanel";
import { useAuth } from "../lib/auth";

const tabs = ["overview", "playbooks", "inventories", "files", "templates"] as const;
type Tab = typeof tabs[number];
const tabLabels: Record<Tab, string> = { overview: "Overview", playbooks: "Playbooks", inventories: "Inventories", files: "Files", templates: "Templates" };

export function ProjectWorkspacePage() {
  const projectId = Number(useParams().projectId); const { can } = useAuth(); const [params, setParams] = useSearchParams(); const rawTab = params.get("tab"); const tab: Tab = tabs.includes(rawTab as Tab) ? rawTab as Tab : "overview"; const setTab = (next: Tab) => setParams(next === "overview" ? {} : { tab: next }); const projects = useProjects(); const project = projects.data?.find(p => p.id === projectId); const playbooks = usePlaybooks(projectId); const inventories = useInventories(); const templates = useTemplates(projectId); const [run, setRun] = useState(false); const [openCreate, setOpenCreate] = useState<"playbook" | "inventory" | null>(null); const canRun = can("job.request") || can("job.run_check");
  if (projects.error) return <ErrorBanner error={projects.error} />;
  if (!projects.isLoading && !project) return <EmptyState action={<Link className="underline" to="/projects">Back to projects</Link>}>Project not found.</EmptyState>;
  return <section className="grid gap-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="grid gap-1"><Link className="text-sm underline" to="/projects">← Projects</Link><h1 className="text-xl font-semibold">{project?.name ?? "Project"}</h1><dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-500 dark:text-zinc-400"><div><dt className="inline font-medium">Git path: </dt><dd className="inline font-mono">{project?.git_path ?? "—"}</dd></div><div><dt className="inline font-medium">Branch: </dt><dd className="inline font-mono">{project?.default_branch ?? "—"}</dd></div></dl></div>{canRun && <Button onClick={() => setRun(true)}>Run playbook</Button>}</div><RunJobDialog open={run} onClose={() => setRun(false)} projectId={projectId} /><div role="tablist" className="flex flex-wrap gap-2">{tabs.map(t => <Button key={t} size="sm" variant={tab === t ? "primary" : "secondary"} onClick={() => setTab(t)}>{tabLabels[t]}</Button>)}</div>{tab === "overview" && <div className="grid gap-4"><div className="grid gap-3 md:grid-cols-3">{[{ key: "playbooks" as Tab, label: "Playbooks", count: playbooks.data?.length ?? 0 }, { key: "inventories" as Tab, label: "Inventories (shared)", count: inventories.data?.length ?? 0 }, { key: "templates" as Tab, label: "Templates", count: templates.data?.length ?? 0 }].map(card => <button key={card.key} className="rounded-lg border border-zinc-200 p-4 text-left hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900" onClick={() => setTab(card.key)}><div className="text-sm text-zinc-500 dark:text-zinc-400">{card.label}</div><div className="mt-2 text-3xl font-semibold">{card.count}</div></button>)}</div><div className="flex flex-wrap gap-2">{can("content.write") && <><Button variant="secondary" onClick={() => { setOpenCreate("playbook"); setTab("playbooks"); }}>New playbook</Button><Button variant="secondary" onClick={() => { setOpenCreate("inventory"); setTab("inventories"); }}>New inventory</Button></>}{canRun && <Button onClick={() => setRun(true)}>Run playbook</Button>}</div></div>}{tab === "playbooks" && <PlaybooksPanel projectId={projectId} autoOpenCreate={openCreate === "playbook"} onAutoOpenHandled={() => setOpenCreate(null)} />}{tab === "inventories" && <InventoriesPanel autoOpenCreate={openCreate === "inventory"} onAutoOpenHandled={() => setOpenCreate(null)} />}{tab === "files" && <ProjectFilesPanel projectId={projectId} />}{tab === "templates" && <TemplatesPanel projectId={projectId} />}</section>;
}
export default ProjectWorkspacePage;

import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { RequirePerm } from "./components/RequirePerm";
import { PanelSkeleton } from "./components/Skeleton";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ProjectsPage from "./pages/ProjectsPage";
import JobsPage from "./pages/JobsPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import UsersPage from "./pages/UsersPage";
import AuditPage from "./pages/AuditPage";
import NotificationsPage from "./pages/NotificationsPage";
import NotFoundPage from "./pages/NotFoundPage";

const ProjectWorkspacePage = lazy(() => import("./pages/ProjectWorkspacePage"));
const InventoriesPage = lazy(() => import("./pages/InventoriesPage"));
const CredentialsPage = lazy(() => import("./pages/CredentialsPage"));
const JobTemplatesPage = lazy(() => import("./pages/JobTemplatesPage"));
const ApprovalReviewPage = lazy(() => import("./pages/ApprovalReviewPage"));
const JobDetailPage = lazy(() => import("./pages/JobDetailPage"));
const SchedulesPage = lazy(() => import("./pages/SchedulesPage"));
const PipelineRunPage = lazy(() => import("./pages/PipelineRunPage"));

export function App() {
  return (
    <Suspense fallback={<PanelSkeleton />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequirePerm perm="read" />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectWorkspacePage />} />
          <Route path="/playbooks" element={<Navigate to="/projects" replace />} />
          <Route path="/inventories" element={<InventoriesPage />} />
          <Route path="/credentials" element={<CredentialsPage />} />
          <Route path="/templates" element={<JobTemplatesPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/approvals/:jobId" element={<ApprovalReviewPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/pipelines/runs/:runId" element={<PipelineRunPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        <Route element={<RequirePerm perm="user.manage" />}>
          <Route path="/users" element={<UsersPage />} />
        </Route>
        <Route element={<RequirePerm perm="audit.read" />}>
          <Route path="/audit" element={<AuditPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Suspense>
  );
}
export default App;

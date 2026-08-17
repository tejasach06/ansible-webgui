import { Navigate, Route, Routes } from "react-router-dom";
import { RequirePerm } from "./components/RequirePerm";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ProjectsPage from "./pages/ProjectsPage";
import ProjectWorkspacePage from "./pages/ProjectWorkspacePage";
import InventoriesPage from "./pages/InventoriesPage";
import CredentialsPage from "./pages/CredentialsPage";
import JobTemplatesPage from "./pages/JobTemplatesPage";
import JobsPage from "./pages/JobsPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import ApprovalReviewPage from "./pages/ApprovalReviewPage";
import JobDetailPage from "./pages/JobDetailPage";
import SchedulesPage from "./pages/SchedulesPage";
import UsersPage from "./pages/UsersPage";
import AuditPage from "./pages/AuditPage";
import NotificationsPage from "./pages/NotificationsPage";
import PipelineRunPage from "./pages/PipelineRunPage";
import NotFoundPage from "./pages/NotFoundPage";

export function App() {
  return (
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
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;

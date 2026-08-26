import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import AppShell from "./components/AppShell";
import FullPageSpinner from "./components/FullPageSpinner";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import BatchesPage from "./pages/BatchesPage";
import UploadWizardPage from "./pages/UploadWizardPage";
import BatchDetailPage from "./pages/BatchDetailPage";
import MappingPage from "./pages/MappingPage";
import BatchStudentsPage from "./pages/BatchStudentsPage";
import ReviewPage from "./pages/ReviewPage";
import ExportsPage from "./pages/ExportsPage";
import AdminOperatorsPage from "./pages/AdminOperatorsPage";
import AuditLogPage from "./pages/AuditLogPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function RedirectIfAuthed({ children }: { children: JSX.Element }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return children;
}

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  // A school operator has `school` set; a system admin does not.
  if (user.school) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <LoginPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/admin/operators" element={
          <RequireAdmin>
            <AdminOperatorsPage />
          </RequireAdmin>
        } />
        <Route path="/admin/audit" element={
          <RequireAdmin>
            <AuditLogPage />
          </RequireAdmin>
        } />
        <Route path="/batches" element={<BatchesPage />} />
        <Route path="/batches/new" element={<UploadWizardPage />} />
        <Route path="/batches/:id" element={<BatchDetailPage />} />
        <Route path="/batches/:id/mapping" element={<MappingPage />} />
        <Route path="/batches/:id/students" element={<BatchStudentsPage />} />
        <Route path="/batches/:id/review" element={<ReviewPage />} />
        <Route path="/batches/:id/exports" element={<ExportsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

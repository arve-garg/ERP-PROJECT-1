import { Navigate, Outlet, createBrowserRouter } from "react-router-dom";
import { useAuth } from "./auth-context";
import { AppShell } from "../components/layout/app-shell";
import { ActivityPage } from "../features/core/activity-page";
import { AuditPage } from "../features/core/audit-page";
import { NotificationsPage } from "../features/core/notifications-page";
import { SecurityPage } from "../features/core/security-page";
import { SettingsPage } from "../features/core/settings-page";
import { UsersPage } from "../features/core/users-page";
import { ForgotPasswordPage } from "../features/auth/forgot-password-page";
import { LoginPage } from "../features/auth/login-page";
import { ResetPasswordPage } from "../features/auth/reset-password-page";
import { DashboardPage } from "../features/dashboard/dashboard-page";
import { HrPage } from "../features/hr/hr-page";
import { ProjectsPage } from "../features/projects/projects-page";

function RequireAuth() {
  const { user, accessToken } = useAuth();
  return user && accessToken ? <Outlet /> : <Navigate to="/login" replace />;
}

function RequireAdmin() {
  const { user } = useAuth();
  return user?.roles.includes("Admin") ? (
    <Outlet />
  ) : (
    <Navigate to="/" replace />
  );
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <DashboardPage /> },
          { path: "/hr", element: <HrPage /> },
          { path: "/delivery", element: <ProjectsPage /> },
          { path: "/notifications", element: <NotificationsPage /> },
          { path: "/activity", element: <ActivityPage /> },
          { path: "/security", element: <SecurityPage /> },
          {
            element: <RequireAdmin />,
            children: [
              { path: "/settings", element: <SettingsPage /> },
              { path: "/audit-log", element: <AuditPage /> },
              { path: "/users", element: <UsersPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

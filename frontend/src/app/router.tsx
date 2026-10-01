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
import { CrmPage } from "../features/crm/crm-page";
import { ROUTE_CONTRACT } from "./route-contract";

function RequireAuth() {
  const { user, accessToken } = useAuth();
  return user && accessToken ? <Outlet /> : <Navigate to={ROUTE_CONTRACT.LOGIN} replace />;
}

function RequireAdmin() {
  const { user } = useAuth();
  return user?.roles.includes("Admin") ? (
    <Outlet />
  ) : (
    <Navigate to={ROUTE_CONTRACT.DASHBOARD} replace />
  );
}

export const router = createBrowserRouter([
  { path: ROUTE_CONTRACT.LOGIN, element: <LoginPage /> },
  { path: ROUTE_CONTRACT.FORGOT_PASSWORD, element: <ForgotPasswordPage /> },
  { path: ROUTE_CONTRACT.RESET_PASSWORD, element: <ResetPasswordPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: ROUTE_CONTRACT.DASHBOARD, element: <DashboardPage /> },
          { path: ROUTE_CONTRACT.CRM, element: <CrmPage /> },
          { path: ROUTE_CONTRACT.HR, element: <HrPage /> },
          { path: ROUTE_CONTRACT.DELIVERY, element: <ProjectsPage /> },
          { path: ROUTE_CONTRACT.NOTIFICATIONS, element: <NotificationsPage /> },
          { path: ROUTE_CONTRACT.ACTIVITY, element: <ActivityPage /> },
          { path: ROUTE_CONTRACT.SECURITY, element: <SecurityPage /> },
          {
            element: <RequireAdmin />,
            children: [
              { path: ROUTE_CONTRACT.SETTINGS, element: <SettingsPage /> },
              { path: ROUTE_CONTRACT.AUDIT_LOG, element: <AuditPage /> },
              { path: ROUTE_CONTRACT.ACCESS, element: <UsersPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: ROUTE_CONTRACT.NOT_FOUND, element: <Navigate to={ROUTE_CONTRACT.DASHBOARD} replace /> },
]);

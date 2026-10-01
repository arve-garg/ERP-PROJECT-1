export const ROUTE_CONTRACT = {
  ACCESS: "/access",
  ACTIVITY: "/activity",
  AUDIT_LOG: "/audit-log",
  CRM: "/crm",
  DASHBOARD: "/",
  DELIVERY: "/delivery",
  FORGOT_PASSWORD: "/forgot-password",
  HR: "/hr",
  LOGIN: "/login",
  NOTIFICATIONS: "/notifications",
  RESET_PASSWORD: "/reset-password",
  REGISTER: "/register",
  APPLICATION_STATUS: "/application-status",
  SECURITY: "/security",
  SETTINGS: "/settings",
  NOT_FOUND: "*",
} as const;

export const ROUTES = Object.values(ROUTE_CONTRACT);

import {
  Bell,
  BriefcaseBusiness,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileClock,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  ShieldCheck,
  Settings,
  Sun,
  Target,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../app/auth-context";
import { ROUTE_CONTRACT } from "../../app/route-contract";
import { useTheme } from "../../app/theme-context";
import { GlobalSearch } from "./global-search";
import { Button } from "../ui/button";

const navigation = [
  { to: ROUTE_CONTRACT.DASHBOARD, label: "Overview", icon: LayoutDashboard, end: true },
  { to: ROUTE_CONTRACT.CRM, label: "CRM & Sales", icon: Target },
  { to: ROUTE_CONTRACT.HR, label: "Human resources", icon: Users },
  { to: ROUTE_CONTRACT.DELIVERY, label: "Delivery", icon: BriefcaseBusiness },
  { to: ROUTE_CONTRACT.NOTIFICATIONS, label: "Notifications", icon: Bell },
  { to: ROUTE_CONTRACT.ACTIVITY, label: "Activity", icon: ClipboardList },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  async function signOut() {
    try {
      await logout();
      navigate(ROUTE_CONTRACT.LOGIN, { replace: true });
    } catch {
      navigate(ROUTE_CONTRACT.LOGIN, {
        replace: true,
        state: {
          message:
            "You were signed out locally, but the server could not revoke the refresh token.",
        },
      });
    } finally {
      setMobileOpen(false);
    }
  }

  const initials =
    `${user?.first_name?.[0] ?? ""}${user?.last_name?.[0] ?? ""}` ||
    user?.email[0] ||
    "U";
  return (
    <div className="app-layout">
      {mobileOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`sidebar ${collapsed ? "sidebar-collapsed" : ""} ${mobileOpen ? "sidebar-mobile-open" : ""}`}
      >
        <div className="sidebar-brand">
          <span className="brand-mark small">
            <Building2 size={19} aria-hidden="true" />
          </span>
          {!collapsed && <span className="brand-name">DevERP</span>}
          <button
            className="icon-button desktop-collapse"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
          <button
            className="icon-button mobile-close"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
        {!collapsed && <p className="nav-section-title">WORKSPACE</p>}
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `nav-link ${isActive ? "nav-link-active" : ""}`
              }
              onClick={() => setMobileOpen(false)}
            >
              <Icon size={19} aria-hidden="true" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
          {user?.roles.includes("Admin") && (
            <>
              <NavLink
                to={ROUTE_CONTRACT.ACCESS}
                title={collapsed ? "Users and roles" : undefined}
                className={({ isActive }) =>
                  `nav-link ${isActive ? "nav-link-active" : ""}`
                }
                onClick={() => setMobileOpen(false)}
              >
                <Users size={19} aria-hidden="true" />
                {!collapsed && <span>Users & roles</span>}
              </NavLink>
              <NavLink
                to={ROUTE_CONTRACT.AUDIT_LOG}
                title={collapsed ? "Audit log" : undefined}
                className={({ isActive }) =>
                  `nav-link ${isActive ? "nav-link-active" : ""}`
                }
                onClick={() => setMobileOpen(false)}
              >
                <FileClock size={19} aria-hidden="true" />
                {!collapsed && <span>Audit log</span>}
              </NavLink>
              <NavLink
                to={ROUTE_CONTRACT.SETTINGS}
                title={collapsed ? "Company settings" : undefined}
                className={({ isActive }) =>
                  `nav-link ${isActive ? "nav-link-active" : ""}`
                }
                onClick={() => setMobileOpen(false)}
              >
                <Settings size={19} aria-hidden="true" />
                {!collapsed && <span>Company settings</span>}
              </NavLink>
            </>
          )}
          <NavLink
            to={ROUTE_CONTRACT.SECURITY}
            title={collapsed ? "Sign-in security" : undefined}
            className={({ isActive }) =>
              `nav-link ${isActive ? "nav-link-active" : ""}`
            }
            onClick={() => setMobileOpen(false)}
          >
            <ShieldCheck size={19} aria-hidden="true" />
            {!collapsed && <span>Sign-in security</span>}
          </NavLink>
        </nav>
        {!collapsed && (
          <div className="sidebar-later">
            <p className="nav-section-title">YOUR WORKSPACE</p>
            <div>
              <Users size={16} /> <span>People</span>
            </div>
            <div>
              <BriefcaseBusiness size={16} /> <span>Delivery</span>
            </div>
            <small>Manage people and team operations.</small>
          </div>
        )}
        <div className="sidebar-bottom">
          <button
            className="nav-link theme-button"
            onClick={toggle}
            title={
              collapsed
                ? `Switch to ${theme === "dark" ? "light" : "dark"} mode`
                : undefined
            }
          >
            {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
            {!collapsed && (
              <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
            )}
          </button>
          <button
            className="nav-link signout-button"
            onClick={signOut}
            title={collapsed ? "Sign out" : undefined}
          >
            <LogOut size={19} />
            {!collapsed && <span>Sign out</span>}
          </button>
          <div className="profile-block">
            <span className="avatar">{initials.toUpperCase()}</span>
            {!collapsed && (
              <span className="profile-copy">
                <strong>{user?.first_name || user?.email}</strong>
                <small>{user?.roles.join(" · ") || "Team member"}</small>
              </span>
            )}
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <Button
            variant="ghost"
            size="sm"
            className="mobile-menu-button"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={20} />
          </Button>
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>DevERP</strong>
          </div>
          <div className="topbar-search">
            <GlobalSearch />
          </div>
          <div className="topbar-actions">{user?.email}</div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

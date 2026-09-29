import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Bell, Clock3, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../../app/auth-context";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";
import type { ActivityItem, Paginated } from "../../lib/types";

function relativeDate(value: string) {
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function DashboardPage() {
  const { user, accessToken } = useAuth();
  const activity = useQuery({
    queryKey: ["activity-feed"],
    queryFn: () =>
      apiRequest<Paginated<ActivityItem>>(
        "/activity-feed/?page_size=5",
        {},
        accessToken,
      ),
  });
  const notifications = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () =>
      apiRequest<{ unread_count: number }>(
        "/notifications/unread-count/",
        {},
        accessToken,
      ),
  });

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {new Intl.DateTimeFormat(undefined, { weekday: "long" })
              .format(new Date())
              .toUpperCase()}{" "}
            · YOUR WORKSPACE
          </p>
          <h1>
            Good to see you, {user?.first_name || user?.email.split("@")[0]}
          </h1>
          <p className="muted-text">
            Here’s what’s happening across your DevERP workspace.
          </p>
        </div>
        <span className="date-chip">
          <Clock3 size={15} />{" "}
          {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
            new Date(),
          )}
        </span>
      </div>
      <div className="summary-grid">
        <Card className="summary-card">
          <div className="summary-icon icon-blue">
            <ShieldCheck size={19} />
          </div>
          <p>YOUR ACCESS</p>
          <strong>{user?.roles.join(", ") || "Team member"}</strong>
          <small>Role-based workspace access</small>
        </Card>
        <Card className="summary-card">
          <div className="summary-icon icon-violet">
            <Bell size={19} />
          </div>
          <p>UNREAD NOTIFICATIONS</p>
          {notifications.isPending ? (
            <strong className="skeleton-text">Loading</strong>
          ) : notifications.isError ? (
            <strong className="error-number">Unavailable</strong>
          ) : (
            <strong>{notifications.data.unread_count}</strong>
          )}
          <small>
            <Link to="/notifications">
              Review notifications <ArrowUpRight size={13} />
            </Link>
          </small>
        </Card>
        <Card className="summary-card">
          <div className="summary-icon icon-green">
            <Clock3 size={19} />
          </div>
          <p>CORE SERVICES</p>
          <strong>
            {activity.isPending || notifications.isPending
              ? "Checking…"
              : activity.isError || notifications.isError
                ? "Needs attention"
                : "Connected"}
          </strong>
          <small>Live API status</small>
        </Card>
      </div>
      <Card className="activity-card">
        <div className="section-heading">
          <div>
            <h2>Recent activity</h2>
            <p className="muted-text">Latest updates from your workspace</p>
          </div>
          <Link to="/activity" className="text-link">
            View all <ArrowUpRight size={15} />
          </Link>
        </div>
        {activity.isPending && (
          <div className="loading-state" role="status">
            Loading activity…
          </div>
        )}
        {activity.isError && (
          <div className="error-state" role="alert">
            Activity could not be loaded.{" "}
            <button onClick={() => void activity.refetch()}>Try again</button>
          </div>
        )}
        {activity.isSuccess && activity.data.results.length === 0 && (
          <div className="empty-state">
            <span className="empty-icon">
              <Clock3 size={20} />
            </span>
            <strong>No activity yet</strong>
            <p>
              Changes and updates will appear here as your team uses DevERP.
            </p>
          </div>
        )}
        {activity.isSuccess && activity.data.results.length > 0 && (
          <div className="activity-list">
            {activity.data.results.map((item) => (
              <div className="activity-row" key={item.id}>
                <span className="activity-dot" />
                <div className="activity-copy">
                  <strong>{item.actor_email ?? "System"}</strong> {item.verb}
                  {item.target_type && (
                    <>
                      {" "}
                      <span className="muted-text">{item.target_type}</span>
                    </>
                  )}
                  <small>{relativeDate(item.created_at)}</small>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

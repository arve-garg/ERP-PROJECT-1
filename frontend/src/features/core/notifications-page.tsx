import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";
import type { Notification, Paginated } from "../../lib/types";

export function NotificationsPage() {
  const { accessToken } = useAuth();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: () =>
      apiRequest<Paginated<Notification>>(
        "/notifications/?page_size=50",
        {},
        accessToken,
      ),
  });
  const markRead = useMutation({
    mutationFn: (id: number) =>
      apiRequest<Notification>(
        `/notifications/${id}/read/`,
        { method: "POST" },
        accessToken,
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const markAll = useMutation({
    mutationFn: () =>
      apiRequest<void>(
        "/notifications/read-all/",
        { method: "POST" },
        accessToken,
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR INBOX</p>
          <h1>Notifications</h1>
          <p className="muted-text">
            Stay up to date with changes in your workspace.
          </p>
        </div>
        {query.data?.results.some((item) => !item.is_read) && (
          <Button
            variant="outline"
            size="sm"
            disabled={markAll.isPending}
            onClick={() => markAll.mutate()}
          >
            <CheckCheck size={15} /> Mark all read
          </Button>
        )}
      </div>
      <Card className="list-card">
        {query.isPending && (
          <div className="loading-state" role="status">
            Loading notifications…
          </div>
        )}
        {query.isError && (
          <div className="error-state" role="alert">
            Notifications could not be loaded.{" "}
            <button onClick={() => void query.refetch()}>Try again</button>
          </div>
        )}
        {query.isSuccess && query.data.results.length === 0 && (
          <div className="empty-state">
            <span className="empty-icon">
              <Bell size={20} />
            </span>
            <strong>You’re all caught up</strong>
            <p>Notifications will appear here when there’s something new.</p>
          </div>
        )}
        {query.isSuccess &&
          query.data.results.map((item) => (
            <article
              className={`notification-row ${item.is_read ? "" : "notification-unread"}`}
              key={item.id}
            >
              <span
                className={`notification-indicator ${item.is_read ? "read-indicator" : ""}`}
              />
              <div className="notification-copy">
                <div>
                  <strong>{item.title}</strong>
                  <span className="category-chip">{item.category}</span>
                </div>
                <p>{item.body || "No additional details."}</p>
                <small>
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(item.created_at))}
                </small>
              </div>
              {!item.is_read && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={markRead.isPending}
                  onClick={() => markRead.mutate(item.id)}
                >
                  Mark read
                </Button>
              )}
            </article>
          ))}
        {markRead.isError || markAll.isError ? (
          <div role="alert" className="form-error">
            Unable to update notification status. Please retry.
          </div>
        ) : null}
      </Card>
    </div>
  );
}

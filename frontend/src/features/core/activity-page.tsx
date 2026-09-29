import { useQuery } from "@tanstack/react-query";
import { Clock3 } from "lucide-react";
import { useAuth } from "../../app/auth-context";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";
import type { ActivityItem, Paginated } from "../../lib/types";

export function ActivityPage() {
  const { accessToken } = useAuth();
  const query = useQuery({
    queryKey: ["activity-feed", "all"],
    queryFn: () =>
      apiRequest<Paginated<ActivityItem>>("/activity-feed/", {}, accessToken),
  });
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE HISTORY</p>
          <h1>Activity</h1>
          <p className="muted-text">A timeline of recent workspace activity.</p>
        </div>
      </div>
      <Card className="list-card">
        {query.isPending && (
          <div className="loading-state" role="status">
            Loading activity…
          </div>
        )}
        {query.isError && (
          <div className="error-state" role="alert">
            Activity could not be loaded.{" "}
            <button onClick={() => void query.refetch()}>Try again</button>
          </div>
        )}
        {query.isSuccess && query.data.results.length === 0 && (
          <div className="empty-state">
            <span className="empty-icon">
              <Clock3 size={20} />
            </span>
            <strong>No activity yet</strong>
            <p>Workspace updates will show up here.</p>
          </div>
        )}
        {query.isSuccess &&
          query.data.results.map((item) => (
            <article className="activity-row activity-full-row" key={item.id}>
              <span className="activity-dot" />
              <div className="activity-copy">
                <strong>{item.actor_email ?? "System"}</strong> {item.verb}
                {item.target_type && (
                  <>
                    {" "}
                    <span className="muted-text">{item.target_type}</span>
                  </>
                )}
                <small>
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(item.created_at))}
                </small>
              </div>
            </article>
          ))}
      </Card>
    </div>
  );
}

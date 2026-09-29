import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../../app/auth-context";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";

interface AuditLog {
  id: number;
  actor_email: string | null;
  action: string;
  model_label: string;
  object_id: string;
  changes: Record<string, unknown>;
  occurred_at: string;
}

export function AuditPage() {
  const { accessToken } = useAuth();
  const query = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () =>
      apiRequest<Paginated<AuditLog>>(
        "/audit-logs/?page_size=50",
        {},
        accessToken,
      ),
  });
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SECURITY</p>
          <h1>Audit log</h1>
          <p className="muted-text">
            Administrative history of changes made in DevERP.
          </p>
        </div>
      </div>
      <Card className="list-card">
        {query.isPending && (
          <div className="loading-state" role="status">
            Loading audit history…
          </div>
        )}
        {query.isError && (
          <div className="error-state" role="alert">
            Audit history could not be loaded.{" "}
            <button onClick={() => void query.refetch()}>Try again</button>
          </div>
        )}
        {query.isSuccess && query.data.results.length === 0 && (
          <div className="empty-state">
            <span className="empty-icon">
              <ShieldCheck size={20} />
            </span>
            <strong>No audited changes yet</strong>
            <p>Changes to platform records will be listed here.</p>
          </div>
        )}
        {query.isSuccess &&
          query.data.results.map((item) => (
            <article className="audit-row" key={item.id}>
              <span className={`audit-action audit-${item.action}`}>
                {item.action}
              </span>
              <div className="audit-copy">
                <strong>{item.model_label}</strong>
                <small>
                  Record {item.object_id} · {item.actor_email ?? "System"}
                </small>
              </div>
              <time>
                {new Intl.DateTimeFormat(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(item.occurred_at))}
              </time>
            </article>
          ))}
      </Card>
    </div>
  );
}

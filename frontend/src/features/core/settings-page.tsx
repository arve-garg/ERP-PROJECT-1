import { useQuery } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import { useAuth } from "../../app/auth-context";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";

interface CompanySetting {
  id: number;
  key: string;
  value: unknown;
  description: string;
  updated_at: string;
}

export function SettingsPage() {
  const { accessToken } = useAuth();
  const query = useQuery({
    queryKey: ["company-settings"],
    queryFn: () =>
      apiRequest<Paginated<CompanySetting>>(
        "/company-settings/",
        {},
        accessToken,
      ),
  });
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1>Company settings</h1>
          <p className="muted-text">
            Configuration shared across your DevERP workspace.
          </p>
        </div>
      </div>
      <Card className="list-card">
        {query.isPending && (
          <div className="loading-state" role="status">
            Loading settings…
          </div>
        )}
        {query.isError && (
          <div className="error-state" role="alert">
            Company settings could not be loaded.{" "}
            <button onClick={() => void query.refetch()}>Try again</button>
          </div>
        )}
        {query.isSuccess && query.data.results.length === 0 && (
          <div className="empty-state">
            <span className="empty-icon">
              <Settings2 size={20} />
            </span>
            <strong>No company settings configured</strong>
            <p>
              Settings will be available here as company preferences are added.
            </p>
          </div>
        )}
        {query.isSuccess &&
          query.data.results.map((setting) => (
            <article className="setting-row" key={setting.id}>
              <div>
                <strong>{setting.key.replaceAll("_", " ")}</strong>
                <p>{setting.description || "Company preference"}</p>
              </div>
              <code>
                {typeof setting.value === "string"
                  ? setting.value
                  : JSON.stringify(setting.value)}
              </code>
            </article>
          ))}
      </Card>
    </div>
  );
}

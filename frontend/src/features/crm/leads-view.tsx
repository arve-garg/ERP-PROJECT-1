import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Edit2, Plus, Search, Sparkles } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";
import type { Lead } from "./types";

interface LeadsViewProps {
  leads: Lead[];
  isLoading: boolean;
  onAddLead: () => void;
  onEditLead: (lead: Lead) => void;
}

export function LeadsView({ leads, isLoading, onAddLead, onEditLead }: LeadsViewProps) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const qualifyMutation = useMutation({
    mutationFn: async (leadId: number) => {
      return apiRequest<Lead & { created_deal_id?: number }>(
        `/crm/leads/${leadId}/qualify/`,
        {
          method: "POST",
          body: JSON.stringify({ create_deal: true }),
        },
        accessToken,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-leads"] });
      queryClient.invalidateQueries({ queryKey: ["crm-deals"] });
      queryClient.invalidateQueries({ queryKey: ["crm-pipeline-summary"] });
    },
  });

  const filtered = leads.filter((l) => {
    const matchSearch =
      l.company_name.toLowerCase().includes(search.toLowerCase()) ||
      l.contact_name.toLowerCase().includes(search.toLowerCase()) ||
      l.email.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || l.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const statusColors: Record<string, string> = {
    new: "bg-blue-500/10 text-blue-600 border-blue-500/30",
    contacted: "bg-amber-500/10 text-amber-600 border-amber-500/30",
    qualified: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
    unqualified: "bg-zinc-500/10 text-zinc-600 border-zinc-500/30",
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-64">
            <Search size={15} className="absolute left-2.5 top-2.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search leads..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded border border-border bg-surface pl-8 pr-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-border bg-surface px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">All Statuses</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="unqualified">Unqualified</option>
          </select>
        </div>

        <Button onClick={onAddLead} size="sm" className="w-full sm:w-auto">
          <Plus size={14} className="mr-1.5" /> Add Lead
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border bg-muted/40 text-muted-foreground uppercase font-medium">
              <tr>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Est. Value</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground animate-pulse">
                    Loading sales leads...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No leads found matching criteria.
                  </td>
                </tr>
              ) : (
                filtered.map((lead) => (
                  <tr key={lead.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium text-foreground">
                      {lead.company_name}
                      {lead.notes && (
                        <p className="text-[11px] text-muted-foreground line-clamp-1">{lead.notes}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div>{lead.contact_name || "—"}</div>
                      <div className="text-[11px] text-muted-foreground">{lead.email || lead.phone}</div>
                    </td>
                    <td className="px-4 py-3 capitalize text-muted-foreground">
                      {lead.source.replace("_", " ")}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full border text-[11px] capitalize font-medium ${statusColors[lead.status] || ""}`}>
                        {lead.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono">
                      ${parseFloat(lead.estimated_value).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right space-x-1">
                      {lead.status !== "qualified" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => qualifyMutation.mutate(lead.id)}
                          disabled={qualifyMutation.isPending}
                          className="h-7 px-2 text-[11px]"
                          title="Qualify & create opportunity deal"
                        >
                          <Sparkles size={11} className="mr-1 text-primary" />
                          Qualify
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onEditLead(lead)}
                        className="h-7 w-7 p-0"
                        title="Edit lead"
                      >
                        <Edit2 size={13} />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

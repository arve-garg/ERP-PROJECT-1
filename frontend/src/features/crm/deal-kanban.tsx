import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, DollarSign, Edit2, XCircle } from "lucide-react";
import { useAuth } from "../../app/auth-context";
import { apiRequest } from "../../lib/api";
import type { Deal, DealStage } from "./types";

const STAGES: { key: DealStage; label: string; color: string }[] = [
  { key: "new", label: "New", color: "border-blue-500/40 bg-blue-500/5 text-blue-600 dark:text-blue-400" },
  { key: "qualified", label: "Qualified", color: "border-purple-500/40 bg-purple-500/5 text-purple-600 dark:text-purple-400" },
  { key: "proposal", label: "Proposal", color: "border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400" },
  { key: "won", label: "Won", color: "border-emerald-500/40 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400" },
  { key: "lost", label: "Lost", color: "border-rose-500/40 bg-rose-500/5 text-rose-600 dark:text-rose-400" },
];

const NEXT_STAGE_MAP: Partial<Record<DealStage, DealStage>> = {
  new: "qualified",
  qualified: "proposal",
  proposal: "won",
};

interface DealKanbanProps {
  deals: Deal[];
  isLoading: boolean;
  onEditDeal: (deal: Deal) => void;
}

export function DealKanban({ deals, isLoading, onEditDeal }: DealKanbanProps) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const stageMutation = useMutation({
    mutationFn: async ({ dealId, stage, lostReason }: { dealId: number; stage: DealStage; lostReason?: string }) => {
      return apiRequest<Deal>(`/crm/deals/${dealId}/stage/`, {
        method: "POST",
        body: JSON.stringify({ stage, lost_reason: lostReason || "" }),
      }, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-deals"] });
      queryClient.invalidateQueries({ queryKey: ["crm-pipeline-summary"] });
    },
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {STAGES.map((s) => (
          <div key={s.key} className="h-96 rounded-lg bg-surface/50 border border-border animate-pulse p-4" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-5 gap-4 overflow-x-auto pb-4">
      {STAGES.map((stage) => {
        const stageDeals = deals.filter((d) => d.stage === stage.key);
        const stageTotal = stageDeals.reduce((sum, d) => sum + (parseFloat(d.expected_value) || 0), 0);
        const nextStage = NEXT_STAGE_MAP[stage.key];

        return (
          <div
            key={stage.key}
            data-testid={`kanban-column-${stage.key}`}
            className="flex flex-col min-w-[220px] rounded-lg bg-surface/60 border border-border p-3"
          >
            {/* Column Header */}
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${stage.color}`}>
                  {stage.label}
                </span>
                <span className="text-xs text-muted-foreground">({stageDeals.length})</span>
              </div>
              <span className="text-xs font-medium text-foreground">
                ${stageTotal.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </span>
            </div>

            {/* Cards */}
            <div className="space-y-3 flex-1 overflow-y-auto max-h-[600px] pr-1">
              {stageDeals.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted-foreground">
                  No deals in this stage
                </div>
              ) : (
                stageDeals.map((deal) => (
                  <div
                    key={deal.id}
                    data-testid={`deal-card-${deal.id}`}
                    className="rounded-md border border-border bg-surface p-3 shadow-sm hover:border-primary/50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <h4 className="text-xs font-semibold text-foreground line-clamp-1">{deal.title}</h4>
                      <button
                        onClick={() => onEditDeal(deal)}
                        className="text-muted-foreground hover:text-foreground p-0.5"
                        title="Edit deal"
                        aria-label="Edit deal"
                      >
                        <Edit2 size={13} />
                      </button>
                    </div>

                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{deal.company_name}</p>

                    <div className="mt-2 flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground flex items-center gap-0.5">
                        <DollarSign size={12} className="text-muted-foreground" />
                        {parseFloat(deal.expected_value).toLocaleString()} {deal.currency}
                      </span>
                      <span className="text-[11px] text-muted-foreground font-mono">
                        {deal.probability}%
                      </span>
                    </div>

                    {deal.expected_close_date && (
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        Close: {deal.expected_close_date}
                      </p>
                    )}

                    {/* Quick stage transition buttons */}
                    <div className="mt-3 pt-2 border-t border-border flex items-center justify-between gap-1">
                      {nextStage && (
                        <button
                          onClick={() => stageMutation.mutate({ dealId: deal.id, stage: nextStage })}
                          disabled={stageMutation.isPending}
                          className="flex items-center gap-1 text-[11px] text-primary hover:underline"
                          title={`Move to ${nextStage}`}
                        >
                          Next <ArrowRight size={11} />
                        </button>
                      )}
                      {stage.key !== "won" && (
                        <button
                          onClick={() => stageMutation.mutate({ dealId: deal.id, stage: "won" })}
                          disabled={stageMutation.isPending}
                          className="text-emerald-600 hover:text-emerald-500 p-0.5"
                          title="Mark as Won"
                          aria-label="Mark as Won"
                        >
                          <CheckCircle2 size={14} />
                        </button>
                      )}
                      {stage.key !== "lost" && (
                        <button
                          onClick={() => stageMutation.mutate({ dealId: deal.id, stage: "lost" })}
                          disabled={stageMutation.isPending}
                          className="text-rose-600 hover:text-rose-500 p-0.5"
                          title="Mark as Lost"
                          aria-label="Mark as Lost"
                        >
                          <XCircle size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

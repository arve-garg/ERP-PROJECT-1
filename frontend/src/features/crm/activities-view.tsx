import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Calendar,
  CheckCircle2,
  Edit2,
  Mail,
  MessageSquare,
  PhoneCall,
  Plus,
  Users,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";
import type { Activity, ActivityType } from "./types";

interface ActivitiesViewProps {
  activities: Activity[];
  isLoading: boolean;
  onAddActivity: () => void;
  onEditActivity: (activity: Activity) => void;
}

export function ActivitiesView({
  activities,
  isLoading,
  onAddActivity,
  onEditActivity,
}: ActivitiesViewProps) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"all" | "open" | "completed">("open");

  const completeMutation = useMutation({
    mutationFn: async (activityId: number) => {
      return apiRequest<Activity>(
        `/crm/activities/${activityId}/complete/`,
        { method: "POST" },
        accessToken,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-activities"] });
    },
  });

  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);

  const filtered = activities.filter((a) => {
    if (filter === "open") return !a.completed;
    if (filter === "completed") return a.completed;
    return true;
  });

  const getDueStatus = (act: Activity) => {
    if (act.completed) return { label: "Completed", style: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30" };
    if (!act.due_date) return { label: "No date", style: "bg-muted text-muted-foreground border-border" };

    const dueStr = act.due_date.slice(0, 10);

    if (dueStr < todayStr) {
      return { label: "Overdue", style: "bg-rose-500/10 text-rose-600 border-rose-500/30" };
    }
    if (dueStr === todayStr) {
      return { label: "Due Today", style: "bg-amber-500/10 text-amber-600 border-amber-500/30" };
    }
    return { label: "Upcoming", style: "bg-blue-500/10 text-blue-600 border-blue-500/30" };
  };

  const getIcon = (type: ActivityType) => {
    switch (type) {
      case "call":
        return <PhoneCall size={14} className="text-blue-500" />;
      case "meeting":
        return <Users size={14} className="text-purple-500" />;
      case "email":
        return <Mail size={14} className="text-amber-500" />;
      case "task":
        return <CheckCircle2 size={14} className="text-emerald-500" />;
      default:
        return <MessageSquare size={14} className="text-slate-500" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {(["open", "all", "completed"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3 py-1.5 text-xs rounded-md font-medium capitalize transition-colors ${
                filter === tab
                  ? "bg-primary text-primary-foreground"
                  : "bg-surface text-muted-foreground hover:bg-muted"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <Button onClick={onAddActivity} size="sm" className="w-full sm:w-auto">
          <Plus size={14} className="mr-1.5" /> Log Activity
        </Button>
      </div>

      {/* Activities List */}
      <div className="space-y-2">
        {isLoading ? (
          <div className="py-8 text-center text-xs text-muted-foreground animate-pulse">
            Loading CRM activities...
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center text-xs text-muted-foreground">
            No activities recorded in this view.
          </div>
        ) : (
          filtered.map((act) => {
            const statusInfo = getDueStatus(act);
            return (
              <div
                key={act.id}
                className="flex items-center justify-between p-3.5 rounded-lg border border-border bg-surface hover:border-primary/40 transition-colors shadow-sm gap-3"
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div className="mt-0.5 p-2 rounded-md bg-muted/60">
                    {getIcon(act.activity_type)}
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4
                        className={`text-xs font-semibold text-foreground ${
                          act.completed ? "line-through text-muted-foreground" : ""
                        }`}
                      >
                        {act.title}
                      </h4>
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${statusInfo.style}`}>
                        {statusInfo.label}
                      </span>
                    </div>

                    {act.description && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                        {act.description}
                      </p>
                    )}

                    <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted-foreground">
                      {act.due_date && (
                        <span className="flex items-center gap-1">
                          <Calendar size={11} /> {new Date(act.due_date).toLocaleString()}
                        </span>
                      )}
                      {act.deal_title && (
                        <span className="font-medium text-foreground">Deal: {act.deal_title}</span>
                      )}
                      {act.lead_name && <span>Lead: {act.lead_name}</span>}
                      {act.contact_name && <span>Contact: {act.contact_name}</span>}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {!act.completed && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => completeMutation.mutate(act.id)}
                      disabled={completeMutation.isPending}
                      className="h-7 px-2 text-[11px] text-emerald-600 hover:text-emerald-500"
                      title="Mark activity completed"
                    >
                      <CheckCircle2 size={13} className="mr-1" /> Complete
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onEditActivity(act)}
                    className="h-7 w-7 p-0"
                    title="Edit activity"
                  >
                    <Edit2 size={13} />
                  </Button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

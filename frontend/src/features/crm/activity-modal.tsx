import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";
import type { Activity, Contact, Deal, Lead } from "./types";

const activitySchema = z.object({
  title: z.string().trim().min(1, "Title is required."),
  activity_type: z.enum(["call", "meeting", "email", "note", "task"]),
  description: z.string().optional(),
  due_date: z.string().optional(),
  deal: z.coerce.number().optional().nullable(),
  lead: z.coerce.number().optional().nullable(),
  contact: z.coerce.number().optional().nullable(),
});

type ActivityFormValues = z.infer<typeof activitySchema>;

interface ActivityModalProps {
  activity?: Activity | null;
  deals?: Deal[];
  leads?: Lead[];
  contacts?: Contact[];
  onClose: () => void;
}

export function ActivityModal({
  activity,
  deals = [],
  leads = [],
  contacts = [],
  onClose,
}: ActivityModalProps) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ActivityFormValues>({
    resolver: zodResolver(activitySchema),
    defaultValues: {
      title: activity?.title ?? "",
      activity_type: activity?.activity_type ?? "call",
      description: activity?.description ?? "",
      due_date: activity?.due_date ? activity.due_date.slice(0, 16) : "",
      deal: activity?.deal ?? undefined,
      lead: activity?.lead ?? undefined,
      contact: activity?.contact ?? undefined,
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (values: ActivityFormValues) => {
      const payload = {
        ...values,
        due_date: values.due_date ? new Date(values.due_date).toISOString() : null,
        deal: values.deal || null,
        lead: values.lead || null,
        contact: values.contact || null,
      };
      if (activity) {
        return apiRequest<Activity>(`/crm/activities/${activity.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        }, accessToken);
      }
      return apiRequest<Activity>("/crm/activities/", {
        method: "POST",
        body: JSON.stringify(payload),
      }, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-activities"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-surface p-6 shadow-xl border border-border">
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {activity ? "Edit Activity" : "Log CRM Activity"}
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit((data) => saveMutation.mutate(data))}
          className="mt-4 space-y-4"
        >
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Activity Title *
            </label>
            <input
              type="text"
              {...register("title")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="e.g. Follow-up demo call"
            />
            {errors.title && (
              <p className="mt-1 text-xs text-destructive">{errors.title.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Activity Type
              </label>
              <select
                {...register("activity_type")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="call">Call</option>
                <option value="meeting">Meeting</option>
                <option value="email">Email</option>
                <option value="note">Note</option>
                <option value="task">Task</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Scheduled / Due Date
              </label>
              <input
                type="datetime-local"
                {...register("due_date")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Link Deal
              </label>
              <select
                {...register("deal")}
                className="w-full rounded border border-border bg-background px-2 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">None</option>
                {deals.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.title}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Link Lead
              </label>
              <select
                {...register("lead")}
                className="w-full rounded border border-border bg-background px-2 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">None</option>
                {leads.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.company_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Link Contact
              </label>
              <select
                {...register("contact")}
                className="w-full rounded border border-border bg-background px-2 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">None</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.full_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Notes / Description
            </label>
            <textarea
              {...register("description")}
              rows={3}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Action items, meeting summary, follow-up requirements..."
            />
          </div>

          {saveMutation.isError && (
            <p className="text-xs text-destructive">
              {saveMutation.error instanceof Error
                ? saveMutation.error.message
                : "Failed to save activity."}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-border">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || saveMutation.isPending}>
              {saveMutation.isPending ? "Saving..." : activity ? "Update Activity" : "Log Activity"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

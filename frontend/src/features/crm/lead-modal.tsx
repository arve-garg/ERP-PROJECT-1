import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";
import type { Lead } from "./types";

const leadSchema = z.object({
  company_name: z.string().trim().min(1, "Company name is required."),
  contact_name: z.string().trim().optional(),
  email: z.string().email("Valid email required.").or(z.literal("")),
  phone: z.string().optional(),
  source: z.enum(["website", "referral", "cold_outreach", "event", "other"]),
  status: z.enum(["new", "contacted", "qualified", "unqualified"]),
  estimated_value: z.string().regex(/^\d+(\.\d{1,2})?$/, "Valid decimal amount required."),
  notes: z.string().optional(),
});

type LeadFormValues = z.infer<typeof leadSchema>;

interface LeadModalProps {
  lead?: Lead | null;
  onClose: () => void;
}

export function LeadModal({ lead, onClose }: LeadModalProps) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LeadFormValues>({
    resolver: zodResolver(leadSchema),
    defaultValues: {
      company_name: lead?.company_name ?? "",
      contact_name: lead?.contact_name ?? "",
      email: lead?.email ?? "",
      phone: lead?.phone ?? "",
      source: lead?.source ?? "website",
      status: lead?.status ?? "new",
      estimated_value: lead?.estimated_value ?? "0.00",
      notes: lead?.notes ?? "",
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (values: LeadFormValues) => {
      if (lead) {
        return apiRequest<Lead>(`/crm/leads/${lead.id}/`, {
          method: "PATCH",
          body: JSON.stringify(values),
        }, accessToken);
      }
      return apiRequest<Lead>("/crm/leads/", {
        method: "POST",
        body: JSON.stringify(values),
      }, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-leads"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-surface p-6 shadow-xl border border-border">
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {lead ? "Edit Lead" : "New Sales Lead"}
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
              Company Name *
            </label>
            <input
              type="text"
              {...register("company_name")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="e.g. Acme Innovations"
            />
            {errors.company_name && (
              <p className="mt-1 text-xs text-destructive">{errors.company_name.message}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Contact Person
            </label>
            <input
              type="text"
              {...register("contact_name")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="John Doe"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Email
              </label>
              <input
                type="email"
                {...register("email")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="contact@company.com"
              />
              {errors.email && (
                <p className="mt-1 text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Phone
              </label>
              <input
                type="tel"
                {...register("phone")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="+1..."
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Lead Source
              </label>
              <select
                {...register("source")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="website">Website</option>
                <option value="referral">Referral</option>
                <option value="cold_outreach">Cold Outreach</option>
                <option value="event">Event</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Status
              </label>
              <select
                {...register("status")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="new">New</option>
                <option value="contacted">Contacted</option>
                <option value="qualified">Qualified</option>
                <option value="unqualified">Unqualified</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Estimated Value ($)
            </label>
            <input
              type="text"
              {...register("estimated_value")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="10000.00"
            />
            {errors.estimated_value && (
              <p className="mt-1 text-xs text-destructive">{errors.estimated_value.message}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Notes
            </label>
            <textarea
              {...register("notes")}
              rows={3}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Requirements, context, next actions..."
            />
          </div>

          {saveMutation.isError && (
            <p className="text-xs text-destructive">
              {saveMutation.error instanceof Error
                ? saveMutation.error.message
                : "Failed to save lead."}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-border">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || saveMutation.isPending}>
              {saveMutation.isPending ? "Saving..." : lead ? "Update Lead" : "Create Lead"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

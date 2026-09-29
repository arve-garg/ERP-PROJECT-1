import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";
import type { Contact, Deal, Lead } from "./types";

const dealSchema = z.object({
  title: z.string().trim().min(1, "Title is required."),
  company_name: z.string().trim().min(1, "Company name is required."),
  expected_value: z.string().regex(/^\d+(\.\d{1,2})?$/, "Valid decimal amount required."),
  currency: z.string().length(3, "3-letter currency code.").toUpperCase(),
  stage: z.enum(["new", "qualified", "proposal", "won", "lost"]),
  probability: z.coerce.number().min(0).max(100),
  expected_close_date: z.string().optional().nullable(),
  lead: z.coerce.number().optional().nullable(),
  contact: z.coerce.number().optional().nullable(),
  lost_reason: z.string().optional(),
});

type DealFormValues = z.infer<typeof dealSchema>;

interface DealModalProps {
  deal?: Deal | null;
  leads?: Lead[];
  contacts?: Contact[];
  onClose: () => void;
}

export function DealModal({ deal, leads = [], contacts = [], onClose }: DealModalProps) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<DealFormValues>({
    resolver: zodResolver(dealSchema),
    defaultValues: {
      title: deal?.title ?? "",
      company_name: deal?.company_name ?? "",
      expected_value: deal?.expected_value ?? "0.00",
      currency: deal?.currency ?? "USD",
      stage: deal?.stage ?? "new",
      probability: deal?.probability ?? 10,
      expected_close_date: deal?.expected_close_date ?? "",
      lead: deal?.lead ?? undefined,
      contact: deal?.contact ?? undefined,
      lost_reason: deal?.lost_reason ?? "",
    },
  });

  const selectedStage = watch("stage");

  const saveMutation = useMutation({
    mutationFn: async (values: DealFormValues) => {
      const payload = {
        ...values,
        expected_close_date: values.expected_close_date || null,
        lead: values.lead || null,
        contact: values.contact || null,
      };
      if (deal) {
        return apiRequest<Deal>(`/crm/deals/${deal.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        }, accessToken);
      }
      return apiRequest<Deal>("/crm/deals/", {
        method: "POST",
        body: JSON.stringify(payload),
      }, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-deals"] });
      queryClient.invalidateQueries({ queryKey: ["crm-pipeline-summary"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-surface p-6 shadow-xl border border-border">
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {deal ? "Edit Deal" : "New Sales Deal"}
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
              Deal Title *
            </label>
            <input
              type="text"
              {...register("title")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="e.g. Cloud Infrastructure Setup"
            />
            {errors.title && (
              <p className="mt-1 text-xs text-destructive">{errors.title.message}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Company Name *
            </label>
            <input
              type="text"
              {...register("company_name")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Client / Prospect name"
            />
            {errors.company_name && (
              <p className="mt-1 text-xs text-destructive">{errors.company_name.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Expected Value *
              </label>
              <input
                type="text"
                {...register("expected_value")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="25000.00"
              />
              {errors.expected_value && (
                <p className="mt-1 text-xs text-destructive">{errors.expected_value.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Currency
              </label>
              <input
                type="text"
                {...register("currency")}
                maxLength={3}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {errors.currency && (
                <p className="mt-1 text-xs text-destructive">{errors.currency.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Stage
              </label>
              <select
                {...register("stage")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="new">New</option>
                <option value="qualified">Qualified</option>
                <option value="proposal">Proposal</option>
                <option value="won">Won</option>
                <option value="lost">Lost</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Win Probability (%)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                {...register("probability")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">
              Expected Close Date
            </label>
            <input
              type="date"
              {...register("expected_close_date")}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Linked Lead (Optional)
              </label>
              <select
                {...register("lead")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
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
                Contact Person (Optional)
              </label>
              <select
                {...register("contact")}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
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

          {selectedStage === "lost" && (
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">
                Lost Reason
              </label>
              <textarea
                {...register("lost_reason")}
                rows={2}
                className="w-full rounded border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Why was this deal lost?"
              />
            </div>
          )}

          {saveMutation.isError && (
            <p className="text-xs text-destructive">
              {saveMutation.error instanceof Error
                ? saveMutation.error.message
                : "Failed to save deal."}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-border">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || saveMutation.isPending}>
              {saveMutation.isPending ? "Saving..." : deal ? "Update Deal" : "Create Deal"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

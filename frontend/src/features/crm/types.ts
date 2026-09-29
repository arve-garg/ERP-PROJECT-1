export interface Lead {
  id: number;
  company_name: string;
  contact_name: string;
  email: string;
  phone: string;
  source: "website" | "referral" | "cold_outreach" | "event" | "other";
  status: "new" | "contacted" | "qualified" | "unqualified";
  estimated_value: string;
  notes: string;
  assigned_to: number | null;
  assigned_to_name: string;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  organization: string;
  title: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export type DealStage = "new" | "qualified" | "proposal" | "won" | "lost";

export interface Deal {
  id: number;
  title: string;
  lead: number | null;
  lead_name: string;
  contact: number | null;
  contact_name: string;
  company_name: string;
  stage: DealStage;
  expected_value: string;
  currency: string;
  probability: number;
  expected_close_date: string | null;
  assigned_to: number | null;
  assigned_to_name: string;
  lost_reason: string;
  created_at: string;
  updated_at: string;
}

export interface DealPipelineSummary {
  new: { count: number; total_value: string };
  qualified: { count: number; total_value: string };
  proposal: { count: number; total_value: string };
  won: { count: number; total_value: string };
  lost: { count: number; total_value: string };
}

export type ActivityType = "call" | "meeting" | "email" | "note" | "task";

export interface Activity {
  id: number;
  lead: number | null;
  lead_name: string;
  contact: number | null;
  contact_name: string;
  deal: number | null;
  deal_title: string;
  activity_type: ActivityType;
  title: string;
  description: string;
  due_date: string | null;
  completed: boolean;
  completed_at: string | null;
  completed_by: number | null;
  completed_by_name: string;
  created_at: string;
  updated_at: string;
}

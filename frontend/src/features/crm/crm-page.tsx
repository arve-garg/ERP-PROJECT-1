import { useQuery } from "@tanstack/react-query";
import {
  CalendarClock,
  DollarSign,
  Kanban,
  Target,
  UserCheck,
  Users,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../app/auth-context";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";
import { ActivitiesView } from "./activities-view";
import { ActivityModal } from "./activity-modal";
import { ContactModal } from "./contact-modal";
import { ContactsView } from "./contacts-view";
import { DealKanban } from "./deal-kanban";
import { DealModal } from "./deal-modal";
import { LeadModal } from "./lead-modal";
import { LeadsView } from "./leads-view";
import type { Activity, Contact, Deal, DealPipelineSummary, Lead } from "./types";

type CrmTab = "deals" | "leads" | "contacts" | "activities";

export function CrmPage() {
  const { accessToken } = useAuth();
  const [activeTab, setActiveTab] = useState<CrmTab>("deals");

  // Modal states
  const [dealModalOpen, setDealModalOpen] = useState(false);
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);

  const [leadModalOpen, setLeadModalOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);

  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);

  // Queries
  const dealsQuery = useQuery({
    queryKey: ["crm-deals"],
    queryFn: () =>
      apiRequest<Paginated<Deal>>("/crm/deals/?page_size=100", {}, accessToken),
  });

  useQuery({
    queryKey: ["crm-pipeline-summary"],
    queryFn: () =>
      apiRequest<DealPipelineSummary>("/crm/deals/pipeline-summary/", {}, accessToken),
  });

  const leadsQuery = useQuery({
    queryKey: ["crm-leads"],
    queryFn: () =>
      apiRequest<Paginated<Lead>>("/crm/leads/?page_size=100", {}, accessToken),
  });

  const contactsQuery = useQuery({
    queryKey: ["crm-contacts"],
    queryFn: () =>
      apiRequest<Paginated<Contact>>("/crm/contacts/?page_size=100", {}, accessToken),
  });

  const activitiesQuery = useQuery({
    queryKey: ["crm-activities"],
    queryFn: () =>
      apiRequest<Paginated<Activity>>("/crm/activities/?page_size=100", {}, accessToken),
  });

  const deals = dealsQuery.data?.results ?? [];
  const leads = leadsQuery.data?.results ?? [];
  const contacts = contactsQuery.data?.results ?? [];
  const activities = activitiesQuery.data?.results ?? [];

  // Summary computations
  const totalPipelineValue = deals
    .filter((d) => d.stage !== "lost")
    .reduce((sum, d) => sum + (parseFloat(d.expected_value) || 0), 0);
  const activeDealsCount = deals.filter((d) => !["won", "lost"].includes(d.stage)).length;
  const openLeadsCount = leads.filter((l) => l.status !== "qualified" && l.status !== "unqualified").length;
  const pendingActivitiesCount = activities.filter((a) => !a.completed).length;

  return (
    <div className="space-y-6 p-6">
      {/* Page Title & KPI Cards */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Target size={24} className="text-primary" />
              CRM & Sales Pipeline
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Manage prospective leads, contacts, sales opportunities, and customer interactions.
            </p>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
          <Card className="p-4 bg-surface border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Pipeline Value</p>
                <h3 className="text-xl font-bold text-foreground mt-1">
                  ${totalPipelineValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </h3>
              </div>
              <div className="p-2.5 rounded-full bg-emerald-500/10 text-emerald-600">
                <DollarSign size={20} />
              </div>
            </div>
          </Card>

          <Card className="p-4 bg-surface border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Active Deals</p>
                <h3 className="text-xl font-bold text-foreground mt-1">{activeDealsCount}</h3>
              </div>
              <div className="p-2.5 rounded-full bg-blue-500/10 text-blue-600">
                <Kanban size={20} />
              </div>
            </div>
          </Card>

          <Card className="p-4 bg-surface border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Open Leads</p>
                <h3 className="text-xl font-bold text-foreground mt-1">{openLeadsCount}</h3>
              </div>
              <div className="p-2.5 rounded-full bg-purple-500/10 text-purple-600">
                <Users size={20} />
              </div>
            </div>
          </Card>

          <Card className="p-4 bg-surface border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Pending Follow-ups</p>
                <h3 className="text-xl font-bold text-foreground mt-1">{pendingActivitiesCount}</h3>
              </div>
              <div className="p-2.5 rounded-full bg-amber-500/10 text-amber-600">
                <CalendarClock size={20} />
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border flex items-center gap-6 text-sm">
        <button
          onClick={() => setActiveTab("deals")}
          className={`pb-3 font-medium flex items-center gap-1.5 transition-colors ${
            activeTab === "deals"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Kanban size={16} /> Deals Pipeline
        </button>
        <button
          onClick={() => setActiveTab("leads")}
          className={`pb-3 font-medium flex items-center gap-1.5 transition-colors ${
            activeTab === "leads"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Users size={16} /> Leads ({leads.length})
        </button>
        <button
          onClick={() => setActiveTab("contacts")}
          className={`pb-3 font-medium flex items-center gap-1.5 transition-colors ${
            activeTab === "contacts"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <UserCheck size={16} /> Contacts ({contacts.length})
        </button>
        <button
          onClick={() => setActiveTab("activities")}
          className={`pb-3 font-medium flex items-center gap-1.5 transition-colors ${
            activeTab === "activities"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <CalendarClock size={16} /> Activities & Follow-ups ({pendingActivitiesCount})
        </button>
      </div>

      {/* Tab Panels */}
      <div>
        {activeTab === "deals" && (
          <div className="space-y-4">
            <div className="flex justify-end">
              <button
                onClick={() => {
                  setSelectedDeal(null);
                  setDealModalOpen(true);
                }}
                className="inline-flex items-center px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90"
              >
                + Add Deal
              </button>
            </div>
            <DealKanban
              deals={deals}
              isLoading={dealsQuery.isLoading}
              onEditDeal={(deal) => {
                setSelectedDeal(deal);
                setDealModalOpen(true);
              }}
            />
          </div>
        )}

        {activeTab === "leads" && (
          <LeadsView
            leads={leads}
            isLoading={leadsQuery.isLoading}
            onAddLead={() => {
              setSelectedLead(null);
              setLeadModalOpen(true);
            }}
            onEditLead={(lead) => {
              setSelectedLead(lead);
              setLeadModalOpen(true);
            }}
          />
        )}

        {activeTab === "contacts" && (
          <ContactsView
            contacts={contacts}
            isLoading={contactsQuery.isLoading}
            onAddContact={() => {
              setSelectedContact(null);
              setContactModalOpen(true);
            }}
            onEditContact={(contact) => {
              setSelectedContact(contact);
              setContactModalOpen(true);
            }}
          />
        )}

        {activeTab === "activities" && (
          <ActivitiesView
            activities={activities}
            isLoading={activitiesQuery.isLoading}
            onAddActivity={() => {
              setSelectedActivity(null);
              setActivityModalOpen(true);
            }}
            onEditActivity={(activity) => {
              setSelectedActivity(activity);
              setActivityModalOpen(true);
            }}
          />
        )}
      </div>

      {/* Modals */}
      {dealModalOpen && (
        <DealModal
          deal={selectedDeal}
          leads={leads}
          contacts={contacts}
          onClose={() => {
            setDealModalOpen(false);
            setSelectedDeal(null);
          }}
        />
      )}

      {leadModalOpen && (
        <LeadModal
          lead={selectedLead}
          onClose={() => {
            setLeadModalOpen(false);
            setSelectedLead(null);
          }}
        />
      )}

      {contactModalOpen && (
        <ContactModal
          contact={selectedContact}
          onClose={() => {
            setContactModalOpen(false);
            setSelectedContact(null);
          }}
        />
      )}

      {activityModalOpen && (
        <ActivityModal
          activity={selectedActivity}
          deals={deals}
          leads={leads}
          contacts={contacts}
          onClose={() => {
            setActivityModalOpen(false);
            setSelectedActivity(null);
          }}
        />
      )}
    </div>
  );
}

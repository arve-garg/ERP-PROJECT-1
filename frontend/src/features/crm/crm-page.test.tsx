import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CrmPage } from "./crm-page";

vi.mock("../../app/auth-context", () => ({
  useAuth: () => ({
    user: { email: "sales@example.com", roles: ["Sales", "Admin"] },
    accessToken: "fake-jwt-token",
  }),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
}));

describe("CrmPage", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
    mockApiRequest.mockImplementation((path: string) => {
      if (path.includes("/crm/deals/pipeline-summary/")) {
        return Promise.resolve({
          new: { count: 1, total_value: "10000.00" },
          qualified: { count: 0, total_value: "0.00" },
          proposal: { count: 1, total_value: "25000.00" },
          won: { count: 1, total_value: "50000.00" },
          lost: { count: 0, total_value: "0.00" },
        });
      }
      if (path.includes("/crm/deals/")) {
        return Promise.resolve({
          count: 3,
          results: [
            {
              id: 1,
              title: "Cloud Infrastructure Setup",
              company_name: "Acme Corp",
              stage: "new",
              expected_value: "10000.00",
              currency: "USD",
              probability: 10,
              expected_close_date: "2026-12-01",
              assigned_to_name: "Sam Sales",
            },
            {
              id: 2,
              title: "Mobile App Development",
              company_name: "Beta Inc",
              stage: "proposal",
              expected_value: "25000.00",
              currency: "USD",
              probability: 60,
              expected_close_date: "2026-11-15",
              assigned_to_name: "Sam Sales",
            },
            {
              id: 3,
              title: "Security Audit",
              company_name: "Delta LLC",
              stage: "won",
              expected_value: "50000.00",
              currency: "USD",
              probability: 100,
              expected_close_date: "2026-10-01",
              assigned_to_name: "Ada Admin",
            },
          ],
        });
      }
      if (path.includes("/crm/leads/")) {
        return Promise.resolve({
          count: 1,
          results: [
            {
              id: 10,
              company_name: "Omega Systems",
              contact_name: "Oliver Queen",
              email: "oliver@omega.com",
              phone: "1234567890",
              source: "referral",
              status: "new",
              estimated_value: "15000.00",
              notes: "Interested in retainer services.",
            },
          ],
        });
      }
      if (path.includes("/crm/contacts/")) {
        return Promise.resolve({
          count: 1,
          results: [
            {
              id: 20,
              first_name: "Diana",
              last_name: "Prince",
              full_name: "Diana Prince",
              email: "diana@themyscira.com",
              phone: "+1234567",
              organization: "Amazon Enterprises",
              title: "CEO",
              notes: "Key executive contact.",
            },
          ],
        });
      }
      if (path.includes("/crm/activities/")) {
        return Promise.resolve({
          count: 1,
          results: [
            {
              id: 30,
              activity_type: "call",
              title: "Initial Discovery Call",
              description: "Discuss scope and requirements.",
              due_date: "2026-10-05T10:00:00Z",
              completed: false,
              deal_title: "Cloud Infrastructure Setup",
            },
          ],
        });
      }
      return Promise.resolve({ count: 0, results: [] });
    });
  });

  function renderCrmPage() {
    return render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: { retry: false },
            },
          })
        }
      >
        <MemoryRouter>
          <CrmPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("renders page header and metric cards", async () => {
    renderCrmPage();
    expect(screen.getByText("CRM & Sales Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Pipeline Value")).toBeInTheDocument();
    expect(screen.getByText("Active Deals")).toBeInTheDocument();
    expect(screen.getByText("Open Leads")).toBeInTheDocument();
  });

  it("renders deals in the kanban view", async () => {
    renderCrmPage();
    expect(await screen.findByText("Cloud Infrastructure Setup")).toBeInTheDocument();
    expect(screen.getByText("Mobile App Development")).toBeInTheDocument();
    expect(screen.getByText("Security Audit")).toBeInTheDocument();
    expect(screen.getByTestId("kanban-column-new")).toBeInTheDocument();
    expect(screen.getByTestId("kanban-column-won")).toBeInTheDocument();
  });

  it("switches to leads tab and displays leads", async () => {
    renderCrmPage();
    const leadsTab = await screen.findByRole("button", { name: /Leads/i });
    fireEvent.click(leadsTab);

    expect(await screen.findByText("Omega Systems")).toBeInTheDocument();
    expect(screen.getByText("Oliver Queen")).toBeInTheDocument();
    expect(screen.getByText("Qualify")).toBeInTheDocument();
  });

  it("switches to contacts tab and displays contacts", async () => {
    renderCrmPage();
    const contactsTab = await screen.findByRole("button", { name: /Contacts/i });
    fireEvent.click(contactsTab);

    expect(await screen.findByText("Diana Prince")).toBeInTheDocument();
    expect(screen.getByText("Amazon Enterprises")).toBeInTheDocument();
  });

  it("switches to activities tab and displays follow-ups", async () => {
    renderCrmPage();
    const activitiesTab = await screen.findByRole("button", { name: /Activities/i });
    fireEvent.click(activitiesTab);

    expect(await screen.findByText("Initial Discovery Call")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("opens the Add Deal modal on button click", async () => {
    renderCrmPage();
    const addBtn = await screen.findByRole("button", { name: "+ Add Deal" });
    fireEvent.click(addBtn);

    expect(await screen.findByText("New Sales Deal")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g. Cloud Infrastructure Setup")).toBeInTheDocument();
  });
});

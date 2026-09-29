import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectsPage } from "./projects-page";
import { apiDownload, apiRequest } from "../../lib/api";

const mockUseAuth = vi.hoisted(() => vi.fn());

vi.mock("../../app/auth-context", () => ({
  useAuth: mockUseAuth,
}));

vi.mock("../../lib/api", () => ({
  apiRequest: vi.fn(),
  apiDownload: vi.fn(),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectsPage />
    </QueryClientProvider>,
  );
}

function page(results: unknown[]) {
  return { count: results.length, next: null, previous: null, results };
}

describe("ProjectsPage", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      accessToken: "test-token",
      user: {
        id: 1,
        email: "manager@example.test",
        first_name: "Delivery",
        last_name: "Manager",
        roles: ["Manager"],
        totp_required: false,
      },
    });
    vi.mocked(apiRequest).mockReset();
    vi.mocked(apiDownload).mockReset();
    vi.mocked(apiRequest).mockResolvedValue(page([]));
  });

  it("loads project records and shows an empty state", async () => {
    vi.mocked(apiRequest).mockResolvedValue(
      page([
        {
          id: 2,
          name: "ERP rollout",
          client_name: "Northwind",
          status: "active",
          budget: "25000.00",
        },
      ]),
    );
    renderPage();

    expect(await screen.findByText("ERP rollout")).toBeInTheDocument();
    expect(screen.getByText("Northwind")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith(
      "/projects/projects/?page=1&page_size=25",
      {},
      "test-token",
    );

    vi.mocked(apiRequest).mockResolvedValue(page([]));
    await userEvent.click(screen.getByRole("tab", { name: "Clients" }));
    expect(await screen.findByText("No records yet")).toBeInTheDocument();
  });

  it("supports list search and pagination", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      const currentPage = new URLSearchParams(path.split("?")[1]).get("page");
      return {
        count: 26,
        next: currentPage === "1" ? "?page=2" : null,
        previous: currentPage === "2" ? "?page=1" : null,
        results: [{ id: currentPage, name: `Project page ${currentPage}` }],
      };
    });
    renderPage();

    expect(await screen.findByText("Project page 1")).toBeInTheDocument();
    await user.type(
      screen.getByRole("searchbox", { name: "Search projects" }),
      "portal",
    );
    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/projects/projects/?page=1&page_size=25&search=portal",
        {},
        "test-token",
      );
    });
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Project page 2")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenLastCalledWith(
      "/projects/projects/?page=2&page_size=25&search=portal",
      {},
      "test-token",
    );
  });

  it("validates required fields and creates projects with typed data", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No records yet");
    await user.click(screen.getByRole("button", { name: "Create Project" }));
    expect(apiRequest).not.toHaveBeenCalledWith(
      "/projects/projects/",
      expect.objectContaining({ method: "POST" }),
      "test-token",
    );
    await user.type(screen.getByLabelText("Project name"), "ERP rollout");
    await user.type(screen.getByLabelText("Client ID"), "7");
    await user.type(screen.getByLabelText("Project code"), "ERP-1");
    await user.type(screen.getByLabelText("Manager profile ID"), "9");
    await user.type(screen.getByLabelText("Start date"), "2026-09-01");
    await user.type(screen.getByLabelText("Budget"), "25000.50");
    await user.click(screen.getByRole("button", { name: "Create Project" }));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/projects/",
        {
          method: "POST",
          body: JSON.stringify({
            name: "ERP rollout",
            client: 7,
            code: "ERP-1",
            manager: 9,
            start_date: "2026-09-01",
            budget: 25000.5,
          }),
        },
        "test-token",
      );
    });
  });

  it("updates task status through its explicit status endpoint", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      if (path === "/projects/tasks/?page=1&page_size=25") {
        return page([{ id: 12, title: "Implement API", status: "backlog" }]);
      }
      return page([]);
    });
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Tasks" }));
    const status = await screen.findByRole("combobox", {
      name: "Status for Implement API",
    });
    expect(
      Array.from((status as HTMLSelectElement).options).map(
        (option) => option.value,
      ),
    ).toEqual([
      "backlog",
      "ready",
      "in_progress",
      "blocked",
      "done",
      "cancelled",
    ]);
    await user.selectOptions(status, "in_progress");
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/tasks/12/status/",
        { method: "POST", body: JSON.stringify({ status: "in_progress" }) },
        "test-token",
      );
    });
  });

  it("supports moving task cards between Kanban status columns", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      if (path === "/projects/tasks/?page=1&page_size=25") {
        return page([
          {
            id: 44,
            title: "Ship Kanban board",
            project_name: "Delivery",
            assignee_name: "Taylor",
            status: "backlog",
          },
        ]);
      }
      return page([]);
    });
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Tasks" }));
    await screen.findByText("Ship Kanban board");
    await user.click(screen.getByRole("button", { name: "Board view" }));

    const task = screen.getByText("Ship Kanban board").closest("article");
    const readyColumn = screen.getByRole("region", { name: "ready tasks" });
    expect(task).toHaveAttribute("draggable", "true");
    fireEvent.dragStart(task!, {
      dataTransfer: {
        setData: vi.fn(),
        getData: () => "44",
      },
    });
    fireEvent.drop(readyColumn, {
      dataTransfer: {
        getData: () => "44",
      },
    });

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/tasks/44/status/",
        { method: "POST", body: JSON.stringify({ status: "ready" }) },
        "test-token",
      );
    });
    await user.click(screen.getByRole("button", { name: "List view" }));
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("transitions project statuses with POST and never patches project status", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockResolvedValue(
      page([{ id: 42, name: "Delivery", code: "DEL", status: "planned" }]),
    );
    renderPage();
    await screen.findByText("Delivery");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Status for Delivery" }),
      "active",
    );
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/projects/42/transition/",
        { method: "POST", body: JSON.stringify({ status: "active" }) },
        "test-token",
      );
    });
    expect(
      vi
        .mocked(apiRequest)
        .mock.calls.some(
          ([path, options]) =>
            path === "/projects/projects/42/" && options?.method === "PATCH",
        ),
    ).toBe(false);
  });

  it("creates time entries with task, work_date, and is_billable fields", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Timesheets" }));
    await user.type(screen.getByLabelText("Task ID"), "12");
    fireEvent.change(screen.getByLabelText("Work date"), {
      target: { value: "2026-09-28" },
    });
    await user.type(screen.getByLabelText("Hours"), "4");
    await user.type(screen.getByLabelText("Work summary"), "Feature work");
    await user.selectOptions(screen.getByLabelText("Billable"), "true");
    expect(screen.getByLabelText("Task ID")).toHaveValue(12);
    expect(screen.getByLabelText("Work date")).toHaveValue("2026-09-28");
    expect(screen.getByLabelText("Hours")).toHaveValue(4);
    expect(screen.getByLabelText("Work summary")).toHaveValue("Feature work");
    fireEvent.submit(screen.getByLabelText("Task ID").closest("form")!);
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/time-entries/",
        {
          method: "POST",
          body: JSON.stringify({
            task: 12,
            work_date: "2026-09-28",
            hours: 4,
            description: "Feature work",
            is_billable: true,
          }),
        },
        "test-token",
      );
    });
  });

  it("uses allocation_percent and treats allocation role as optional", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Resourcing" }));
    await user.type(screen.getByLabelText("Project ID"), "35");
    await user.type(screen.getByLabelText("Employee profile ID"), "16");
    fireEvent.change(screen.getAllByLabelText("Start date")[0], {
      target: { value: "2026-10-01" },
    });
    fireEvent.change(screen.getAllByLabelText("End date")[0], {
      target: { value: "2026-10-31" },
    });
    await user.type(screen.getByLabelText("Allocation (%)"), "60");
    fireEvent.submit(screen.getByLabelText("Project ID").closest("form")!);
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/resource-allocations/",
        {
          method: "POST",
          body: JSON.stringify({
            project: 35,
            employee: 16,
            start_date: "2026-10-01",
            end_date: "2026-10-31",
            allocation_percent: 60,
          }),
        },
        "test-token",
      );
    });
  });

  it("creates a daily time submission with entry IDs", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Time submissions" }));
    await user.selectOptions(screen.getByLabelText("Period"), "daily");
    fireEvent.change(screen.getByLabelText("Period start"), {
      target: { value: "2026-09-28" },
    });
    fireEvent.change(screen.getByLabelText("Period end"), {
      target: { value: "2026-09-28" },
    });
    await user.type(
      screen.getByLabelText("Time entry IDs (comma-separated)"),
      "10, 11",
    );
    fireEvent.submit(
      screen
        .getByLabelText("Time entry IDs (comma-separated)")
        .closest("form")!,
    );
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/time-submissions/",
        {
          method: "POST",
          body: JSON.stringify({
            period_type: "daily",
            period_start: "2026-09-28",
            period_end: "2026-09-28",
            entries: [10, 11],
          }),
        },
        "test-token",
      );
    });
  });

  it("submits draft time entries through the timesheet action", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      if (path === "/projects/time-entries/?page=1&page_size=25") {
        return page([
          {
            id: 31,
            project_name: "ERP rollout",
            employee_name: "Taylor",
            hours: "4.00",
            status: "draft",
          },
        ]);
      }
      return page([]);
    });
    renderPage();
    await user.click(screen.getByRole("tab", { name: "Timesheets" }));
    const row = await screen.findByText("Taylor");
    await user.click(
      within(row.closest("tr") as HTMLElement).getByRole("button", {
        name: "Submit",
      }),
    );
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/projects/time-entries/31/submit/",
        { method: "POST", body: JSON.stringify({}) },
        "test-token",
      );
    });
  });

  it("shows actionable API failures", async () => {
    vi.mocked(apiRequest).mockRejectedValue(
      new Error("Delivery API unavailable"),
    );
    renderPage();

    expect(
      await screen.findByText("Delivery API unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });
});

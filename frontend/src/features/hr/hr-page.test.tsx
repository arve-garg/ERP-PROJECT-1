import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HrPage } from "./hr-page";
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
      <HrPage />
    </QueryClientProvider>,
  );
}

describe("HR page", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      accessToken: "test-token",
      user: {
        id: 1,
        email: "hr@example.test",
        first_name: "HR",
        last_name: "User",
        roles: ["HR"],
        totp_required: false,
      },
    });
    vi.mocked(apiRequest).mockReset();
    vi.mocked(apiDownload).mockReset();
    vi.mocked(apiDownload).mockResolvedValue();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      const result = (results: unknown[]) => ({
        count: results.length,
        next: null,
        previous: null,
        results,
      });
      if (path === "/hr/employees/eligible-users/?page_size=100") {
        return result([
          {
            id: 12,
            email: "new.person@example.test",
            first_name: "New",
            last_name: "Person",
          },
        ]);
      }
      if (path === "/hr/departments/") {
        return result([
          { id: 4, name: "People Operations", description: "Team support" },
        ]);
      }
      if (path === "/hr/designations/?page_size=100") {
        return result([{ id: 9, title: "Analyst", department: 4 }]);
      }
      if (path === "/hr/employees/?page_size=100") return result([]);
      return result([]);
    });
  });

  it("loads departments from the paginated HR endpoint", async () => {
    renderPage();

    expect(await screen.findByText("People Operations")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith(
      "/hr/departments/",
      {},
      "test-token",
    );
  });

  it("validates department forms before submitting", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("People Operations");

    await user.click(screen.getByRole("button", { name: /add department/i }));
    await user.click(screen.getByRole("button", { name: /save department/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a department name.",
    );
    await waitFor(() => {
      expect(apiRequest).not.toHaveBeenCalledWith(
        "/hr/departments/",
        expect.objectContaining({ method: "POST" }),
        "test-token",
      );
    });
  });

  it("sends the required department code in the create payload", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("People Operations");
    await user.click(screen.getByRole("button", { name: /add department/i }));
    await user.type(screen.getByLabelText("Department name"), "Engineering");
    await user.type(screen.getByLabelText("Department code"), "eng");
    await user.click(screen.getByRole("button", { name: /save department/i }));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/hr/departments/",
        {
          method: "POST",
          body: JSON.stringify({
            name: "Engineering",
            code: "ENG",
            description: "",
          }),
        },
        "test-token",
      );
    });
  });

  it("creates an employee profile using selected backend IDs", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "People" }));
    await user.click(
      await screen.findByRole("button", { name: /add employee/i }),
    );

    const accountPicker = await screen.findByLabelText("User account");
    expect(
      await within(accountPicker).findByRole("option", {
        name: /New Person · new\.person@example\.test/,
      }),
    ).toHaveValue("12");
    expect(apiRequest).toHaveBeenCalledWith(
      "/hr/employees/eligible-users/?page_size=100",
      {},
      "test-token",
    );
    expect(
      vi
        .mocked(apiRequest)
        .mock.calls.some(([path]) => path === "/users/?page_size=100"),
    ).toBe(false);
    await user.selectOptions(accountPicker, "12");
    await user.type(screen.getByLabelText("Employee number"), "EMP-102");
    await user.selectOptions(screen.getByLabelText("Department"), "4");
    await user.selectOptions(screen.getByLabelText("Designation"), "9");
    await user.type(screen.getByLabelText("Hire date"), "2026-09-01");
    await user.click(screen.getByRole("button", { name: "Create profile" }));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/hr/employees/",
        {
          method: "POST",
          body: JSON.stringify({
            user: 12,
            employee_number: "EMP-102",
            department: "4",
            designation: "9",
            hire_date: "2026-09-01",
          }),
        },
        "test-token",
      );
    });
  });

  it("does not call the eligible-users API or expose profile creation to other roles", async () => {
    mockUseAuth.mockReturnValue({
      accessToken: "test-token",
      user: {
        id: 2,
        email: "staff@example.test",
        first_name: "Staff",
        last_name: "Member",
        roles: ["Employee"],
        totp_required: false,
      },
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "People" }));

    expect(
      screen.queryByRole("button", { name: /add employee/i }),
    ).not.toBeInTheDocument();
    expect(
      vi
        .mocked(apiRequest)
        .mock.calls.some(([path]) =>
          path.startsWith("/hr/employees/eligible-users/"),
        ),
    ).toBe(false);
  });

  it("lists documents and contacts for the selected employee and submits multipart uploads", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      const result = (results: unknown[]) => ({
        count: results.length,
        next: null,
        previous: null,
        results,
      });
      if (path === "/hr/employees/?page_size=100") {
        return result([
          {
            id: 42,
            full_name: "Employee Profile",
            department_name: "People Operations",
            designation_title: "Analyst",
          },
        ]);
      }
      if (path.startsWith("/hr/employee-documents/?employee=")) {
        return result([
          {
            id: 91,
            employee: 42,
            title: "Signed agreement",
            document_type: "contract",
            file_name: "private/agreement.pdf",
          },
        ]);
      }
      return result([]);
    });

    renderPage();
    await user.click(screen.getByRole("button", { name: "People" }));
    await user.click(await screen.findByRole("button", { name: /view/i }));
    expect(await screen.findByText("Signed agreement")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith(
      "/hr/employee-documents/?employee=42",
      {},
      "test-token",
    );
    expect(apiRequest).toHaveBeenCalledWith(
      "/hr/emergency-contacts/?employee=42",
      {},
      "test-token",
    );
    await user.click(await screen.findByRole("button", { name: /download/i }));
    expect(apiDownload).toHaveBeenCalledWith(
      "/hr/employee-documents/91/download/",
      "agreement.pdf",
      "test-token",
    );

    await user.type(screen.getByLabelText("Title"), "ID scan");
    await user.type(screen.getByLabelText("Document type"), "identity");
    await user.upload(
      screen.getByLabelText(/File \(PDF/),
      new File(["document"], "identity.pdf", { type: "application/pdf" }),
    );
    expect(screen.getByLabelText("Title")).toHaveValue("ID scan");
    expect(screen.getByLabelText("Document type")).toHaveValue("identity");
    expect(screen.getByLabelText(/File \(PDF/)).toHaveProperty(
      "files.0.name",
      "identity.pdf",
    );
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(
      screen.queryAllByRole("alert").map((notice) => notice.textContent),
    ).toEqual([]);
    expect(vi.mocked(apiRequest).mock.calls.map(([path]) => path)).toContain(
      "/hr/employee-documents/",
    );
    await waitFor(() => {
      const uploadCall = vi
        .mocked(apiRequest)
        .mock.calls.find(
          ([path, options]) =>
            path === "/hr/employee-documents/" && options?.method === "POST",
        );
      expect(uploadCall).toBeDefined();
      const body = uploadCall?.[1]?.body as FormData | undefined;
      expect(typeof body?.get).toBe("function");
      if (!body || typeof body.get !== "function") {
        throw new Error(
          "The document upload body should be multipart form data.",
        );
      }
      expect(body.get("employee")).toBe("42");
      expect(body.get("title")).toBe("ID scan");
      expect(body.get("document_type")).toBe("identity");
      expect(body.get("file")).toBeInstanceOf(File);
    });

    await user.type(screen.getByLabelText("Name"), "Alex Contact");
    await user.type(screen.getByLabelText("Relationship"), "Sibling");
    await user.type(screen.getByLabelText("Phone"), "+15551234567");
    await user.click(screen.getByRole("button", { name: "Add contact" }));
    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/hr/emergency-contacts/",
        {
          method: "POST",
          body: JSON.stringify({
            employee: 42,
            name: "Alex Contact",
            relationship: "Sibling",
            phone: "+15551234567",
            is_primary: false,
          }),
        },
        "test-token",
      );
    });
  });

  it("does not load private employee data for a manager viewing a report", async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      accessToken: "test-token",
      user: {
        id: 1,
        email: "manager@example.test",
        first_name: "Team",
        last_name: "Manager",
        roles: ["Manager"],
        totp_required: false,
      },
    });
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      const result = (results: unknown[]) => ({
        count: results.length,
        next: null,
        previous: null,
        results,
      });
      if (path === "/hr/employees/?page_size=100") {
        return result([
          {
            id: 42,
            user: 2,
            full_name: "Direct Report",
            department_name: "Engineering",
          },
        ]);
      }
      return result([]);
    });

    renderPage();
    await user.click(screen.getByRole("button", { name: "People" }));
    await user.click(await screen.findByRole("button", { name: /view/i }));

    expect(screen.queryByText("Documents")).not.toBeInTheDocument();
    expect(screen.queryByText("Emergency contacts")).not.toBeInTheDocument();
    expect(
      vi
        .mocked(apiRequest)
        .mock.calls.some(([path]) =>
          path.startsWith("/hr/employee-documents/"),
        ),
    ).toBe(false);
    expect(
      vi
        .mocked(apiRequest)
        .mock.calls.some(([path]) =>
          path.startsWith("/hr/emergency-contacts/"),
        ),
    ).toBe(false);
  });

  it("renders backend leave balance and requested-day fields", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      const result = (results: unknown[]) => ({
        count: results.length,
        next: null,
        previous: null,
        results,
      });
      if (path === "/hr/leave-types/") {
        return result([{ id: 5, name: "Annual leave" }]);
      }
      if (path === "/hr/leave-balances/") {
        return result([
          { id: 3, leave_type_name: "Annual leave", available_days: "22.50" },
        ]);
      }
      if (path === "/hr/leave-requests/?page_size=100") {
        return result([
          {
            id: 6,
            employee_name: "Morgan Employee",
            leave_type_name: "Annual leave",
            start_date: "2026-10-01",
            end_date: "2026-10-03",
            requested_days: "3.00",
            status: "approved",
          },
        ]);
      }
      return result([]);
    });

    renderPage();
    await user.click(screen.getByRole("button", { name: "Leave" }));

    expect(await screen.findByText("22.50")).toBeInTheDocument();
    expect(screen.getByText("3.00")).toBeInTheDocument();
  });

  it("loads and displays the paginated monthly attendance summary", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      if (path.startsWith("/hr/attendance/monthly-summary/")) {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              employee_id: 24,
              employee_number: "EMP-24",
              employee_name: "Taylor Staff",
              days_present: 19,
              late_days: 2,
              early_departure_days: 1,
            },
          ],
        };
      }
      return { count: 0, next: null, previous: null, results: [] };
    });

    renderPage();
    await user.click(screen.getByRole("button", { name: "Attendance" }));

    expect(
      await screen.findByRole("heading", {
        name: "Monthly attendance summary",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Taylor Staff")).toBeInTheDocument();
    expect(screen.getByText("EMP-24")).toBeInTheDocument();
    expect(screen.getByText("19")).toBeInTheDocument();
    const now = new Date();
    expect(apiRequest).toHaveBeenCalledWith(
      `/hr/attendance/monthly-summary/?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
      {},
      "test-token",
    );
  });

  it("loads a paginated scoped leave calendar and moves between months", async () => {
    const user = userEvent.setup();
    const now = new Date();
    const leaveDate = (day: number) =>
      `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    vi.mocked(apiRequest).mockImplementation(async (path) => {
      if (path.startsWith("/hr/leave-requests/calendar/")) {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 701,
              employee_name: "Jordan Team",
              start_date: leaveDate(14),
              end_date: leaveDate(16),
              status: "approved",
            },
          ],
        };
      }
      return { count: 0, next: null, previous: null, results: [] };
    });

    renderPage();
    await user.click(screen.getByRole("button", { name: "Leave" }));

    expect(
      await screen.findByRole("heading", { name: "Team leave calendar" }),
    ).toBeInTheDocument();
    const calendar = screen.getByRole("grid", { name: /team leave/i });
    expect(await within(calendar).findAllByText("Jordan Team")).toHaveLength(3);
    expect(apiRequest).toHaveBeenCalledWith(
      `/hr/leave-requests/calendar/?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
      {},
      "test-token",
    );

    await user.click(
      screen.getByRole("button", { name: "Previous report month" }),
    );
    const previous = new Date();
    previous.setMonth(previous.getMonth() - 1);
    expect(
      await screen.findByRole("grid", { name: /team leave/i }),
    ).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith(
      `/hr/leave-requests/calendar/?year=${previous.getFullYear()}&month=${previous.getMonth() + 1}`,
      {},
      "test-token",
    );
  });
});

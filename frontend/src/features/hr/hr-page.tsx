import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  FileUp,
  Network,
  Plus,
  Search,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { apiDownload, apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";

type Identifier = number | string;
type ListResponse<T> = Paginated<T> | T[];

interface Department {
  id: Identifier;
  name: string;
  code?: string;
  description?: string | null;
  manager_name?: string | null;
  head_name?: string | null;
  employee_count?: number;
}

interface Employee {
  id: Identifier;
  user?: Identifier;
  employee_number?: string;
  first_name?: string | null;
  last_name?: string | null;
  full_name?: string | null;
  name?: string | null;
  email?: string | null;
  job_title?: string | null;
  designation_title?: string | null;
  designation?: string | null;
  position?: string | null;
  title?: string | null;
  department?: Department | Identifier | null;
  department_name?: string | null;
  manager_name?: string | null;
  manager?: Employee | Identifier | string | null;
  phone?: string | null;
  hire_date?: string | null;
  employment_status?: string | null;
  is_active?: boolean;
  children?: OrgNode[];
}

interface OrgNode extends Employee {
  children?: OrgNode[];
}

interface Attendance {
  id: Identifier;
  employee_name?: string | null;
  employee?: Employee | string | null;
  date?: string | null;
  check_in?: string | null;
  check_out?: string | null;
  status?: string | null;
  hours_worked?: number | string | null;
}

interface AttendanceMonthlySummary {
  employee_id: Identifier;
  employee_number: string;
  employee_name: string;
  days_present: number;
  late_days: number;
  early_departure_days: number;
}

interface LeaveType {
  id: Identifier;
  name: string;
  description?: string | null;
}

interface LeaveBalance {
  id: Identifier;
  leave_type?: LeaveType | string | null;
  leave_type_name?: string | null;
  available_days?: number | string | null;
  balance?: number | string | null;
  remaining_days?: number | string | null;
  days_remaining?: number | string | null;
  used_days?: number | string | null;
}

interface UserOption {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
}

interface Designation {
  id: Identifier;
  title: string;
  department: Identifier;
}

interface EmployeeDocument {
  id: Identifier;
  employee: Identifier;
  title: string;
  document_type: string;
  file_name: string;
  expires_on?: string | null;
}

interface EmergencyContact {
  id: Identifier;
  employee: Identifier;
  name: string;
  relationship: string;
  phone: string;
  email?: string | null;
  is_primary: boolean;
}

interface LeaveRequest {
  id: Identifier;
  employee_name?: string | null;
  employee?: Employee | string | null;
  leave_type?: LeaveType | string | null;
  leave_type_name?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  reason?: string | null;
  status?: string | null;
  days?: number | string | null;
  requested_days?: number | string | null;
}

interface Holiday {
  id: Identifier;
  name: string;
  date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
}

const sections = [
  { id: "departments", label: "Departments", icon: Building2 },
  { id: "employees", label: "People", icon: Users },
  { id: "attendance", label: "Attendance", icon: Clock3 },
  { id: "leave", label: "Leave", icon: CalendarDays },
  { id: "holidays", label: "Holidays", icon: CalendarDays },
] as const;

type Section = (typeof sections)[number]["id"];

function records<T>(data: ListResponse<T> | undefined): T[] {
  if (Array.isArray(data)) return data;
  return data && Array.isArray(data.results) ? data.results : [];
}

function employeeName(
  employee: Employee | Identifier | string | null | undefined,
): string {
  if (typeof employee === "string") return employee;
  if (typeof employee === "number") return `Employee ${employee}`;
  if (!employee) return "—";
  return (
    employee.full_name ||
    employee.name ||
    [employee.first_name, employee.last_name].filter(Boolean).join(" ") ||
    employee.email ||
    `Employee ${employee.id}`
  );
}

function userName(user: UserOption): string {
  return (
    [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email
  );
}

function departmentName(department: Employee["department"]): string {
  if (typeof department === "string") return department;
  if (typeof department === "number") return `Department ${department}`;
  return department?.name ?? "—";
}

function displayDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
}

function displayTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
      });
}

function ErrorNotice({ error }: { error: unknown }) {
  return (
    <p className="hr-alert" role="alert">
      {typeof error === "string"
        ? error
        : error instanceof Error
          ? error.message
          : "Something went wrong. Please try again."}
    </p>
  );
}

function QueryState({
  loading,
  error,
  empty,
  children,
}: {
  loading: boolean;
  error: unknown;
  empty: boolean;
  children: ReactNode;
}) {
  if (loading)
    return (
      <p className="hr-state" role="status">
        Loading…
      </p>
    );
  if (error) return <ErrorNotice error={error} />;
  if (empty)
    return (
      <div className="empty-state">
        <span className="empty-icon">
          <Users size={20} />
        </span>
        <strong>Nothing to show yet</strong>
        <p>Records will appear here when they are available.</p>
      </div>
    );
  return <>{children}</>;
}

export function HrPage() {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const [section, setSection] = useState<Section>("departments");
  const [peopleView, setPeopleView] = useState<"directory" | "org">(
    "directory",
  );
  const [search, setSearch] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(
    null,
  );
  const [showDepartmentForm, setShowDepartmentForm] = useState(false);
  const [showEmployeeForm, setShowEmployeeForm] = useState(false);
  const [profileDepartment, setProfileDepartment] = useState("");
  const [profileError, setProfileError] = useState("");
  const [documentError, setDocumentError] = useState("");
  const [contactError, setContactError] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [leaveFormError, setLeaveFormError] = useState("");
  const [holidayMonthOffset, setHolidayMonthOffset] = useState(0);
  const [reportMonth, setReportMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const reportYear = reportMonth.getFullYear();
  const reportMonthNumber = reportMonth.getMonth() + 1;
  const reportPeriod = `year=${reportYear}&month=${reportMonthNumber}`;
  const canManageEmployees = Boolean(
    user?.roles.some((role) => role === "Admin" || role === "HR"),
  );
  const canViewPrivateEmployeeData = Boolean(
    selectedEmployee &&
    (canManageEmployees || String(selectedEmployee.user) === String(user?.id)),
  );

  const departments = useQuery({
    queryKey: ["hr", "departments"],
    queryFn: () =>
      apiRequest<ListResponse<Department>>("/hr/departments/", {}, accessToken),
    enabled:
      section === "departments" ||
      (section === "employees" && showEmployeeForm),
  });
  const employees = useQuery({
    queryKey: ["hr", "employees"],
    queryFn: () =>
      apiRequest<ListResponse<Employee>>(
        "/hr/employees/?page_size=100",
        {},
        accessToken,
      ),
    enabled: section === "employees",
  });
  const users = useQuery({
    queryKey: ["hr", "eligible-users"],
    queryFn: () =>
      apiRequest<ListResponse<UserOption>>(
        "/hr/employees/eligible-users/?page_size=100",
        {},
        accessToken,
      ),
    enabled: section === "employees" && showEmployeeForm && canManageEmployees,
  });
  const designations = useQuery({
    queryKey: ["hr", "designations"],
    queryFn: () =>
      apiRequest<ListResponse<Designation>>(
        "/hr/designations/?page_size=100",
        {},
        accessToken,
      ),
    enabled: section === "employees" && showEmployeeForm,
  });
  const employeeDocuments = useQuery({
    queryKey: ["hr", "employee-documents", selectedEmployee?.id],
    queryFn: () =>
      apiRequest<ListResponse<EmployeeDocument>>(
        `/hr/employee-documents/?employee=${encodeURIComponent(String(selectedEmployee?.id))}`,
        {},
        accessToken,
      ),
    enabled: section === "employees" && canViewPrivateEmployeeData,
  });
  const emergencyContacts = useQuery({
    queryKey: ["hr", "emergency-contacts", selectedEmployee?.id],
    queryFn: () =>
      apiRequest<ListResponse<EmergencyContact>>(
        `/hr/emergency-contacts/?employee=${encodeURIComponent(String(selectedEmployee?.id))}`,
        {},
        accessToken,
      ),
    enabled: section === "employees" && canViewPrivateEmployeeData,
  });
  const orgChart = useQuery({
    queryKey: ["hr", "org-chart"],
    queryFn: () =>
      apiRequest<ListResponse<OrgNode>>(
        "/hr/employees/org-chart/",
        {},
        accessToken,
      ),
    enabled: section === "employees" && peopleView === "org",
  });
  const attendance = useQuery({
    queryKey: ["hr", "attendance"],
    queryFn: () =>
      apiRequest<ListResponse<Attendance>>(
        "/hr/attendance/?page_size=100",
        {},
        accessToken,
      ),
    enabled: section === "attendance",
  });
  const attendanceSummary = useQuery({
    queryKey: [
      "hr",
      "attendance-monthly-summary",
      reportYear,
      reportMonthNumber,
    ],
    queryFn: () =>
      apiRequest<ListResponse<AttendanceMonthlySummary>>(
        `/hr/attendance/monthly-summary/?${reportPeriod}`,
        {},
        accessToken,
      ),
    enabled: section === "attendance",
  });
  const leaveTypes = useQuery({
    queryKey: ["hr", "leave-types"],
    queryFn: () =>
      apiRequest<ListResponse<LeaveType>>("/hr/leave-types/", {}, accessToken),
    enabled: section === "leave",
  });
  const leaveBalances = useQuery({
    queryKey: ["hr", "leave-balances"],
    queryFn: () =>
      apiRequest<ListResponse<LeaveBalance>>(
        "/hr/leave-balances/",
        {},
        accessToken,
      ),
    enabled: section === "leave",
  });
  const leaveRequests = useQuery({
    queryKey: ["hr", "leave-requests"],
    queryFn: () =>
      apiRequest<ListResponse<LeaveRequest>>(
        "/hr/leave-requests/?page_size=100",
        {},
        accessToken,
      ),
    enabled: section === "leave",
  });
  const leaveCalendar = useQuery({
    queryKey: ["hr", "leave-calendar", reportYear, reportMonthNumber],
    queryFn: () =>
      apiRequest<ListResponse<LeaveRequest>>(
        `/hr/leave-requests/calendar/?${reportPeriod}`,
        {},
        accessToken,
      ),
    enabled: section === "leave",
  });
  const holidays = useQuery({
    queryKey: ["hr", "holidays"],
    queryFn: () =>
      apiRequest<ListResponse<Holiday>>(
        "/hr/holidays/?page_size=100",
        {},
        accessToken,
      ),
    enabled: section === "holidays",
  });

  const createDepartment = useMutation({
    mutationFn: (values: { name: string; code: string; description: string }) =>
      apiRequest<Department>(
        "/hr/departments/",
        { method: "POST", body: JSON.stringify(values) },
        accessToken,
      ),
    onSuccess: async () => {
      setFormError("");
      setSuccess("Department added.");
      setShowDepartmentForm(false);
      await queryClient.invalidateQueries({ queryKey: ["hr", "departments"] });
    },
    onError: (error) =>
      setFormError(
        error instanceof Error ? error.message : "Unable to add department.",
      ),
  });
  const createEmployee = useMutation({
    mutationFn: (values: {
      user: number;
      employee_number: string;
      department: Identifier;
      designation: Identifier;
      manager?: Identifier;
      hire_date: string;
    }) =>
      apiRequest<Employee>(
        "/hr/employees/",
        { method: "POST", body: JSON.stringify(values) },
        accessToken,
      ),
    onSuccess: async () => {
      setProfileError("");
      setSuccess("Employee profile created.");
      setShowEmployeeForm(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["hr", "employees"] }),
        queryClient.invalidateQueries({ queryKey: ["hr", "org-chart"] }),
      ]);
    },
    onError: (error) =>
      setProfileError(
        error instanceof Error
          ? error.message
          : "Unable to create employee profile.",
      ),
  });
  const uploadDocument = useMutation({
    mutationFn: (formData: FormData) =>
      apiRequest<EmployeeDocument>(
        "/hr/employee-documents/",
        { method: "POST", body: formData },
        accessToken,
      ),
    onSuccess: async () => {
      setDocumentError("");
      setSuccess("Employee document uploaded.");
      await queryClient.invalidateQueries({
        queryKey: ["hr", "employee-documents", selectedEmployee?.id],
      });
    },
    onError: (error) =>
      setDocumentError(
        error instanceof Error ? error.message : "Unable to upload document.",
      ),
  });
  const createEmergencyContact = useMutation({
    mutationFn: (values: {
      employee: Identifier;
      name: string;
      relationship: string;
      phone: string;
      email?: string;
      is_primary: boolean;
    }) =>
      apiRequest<EmergencyContact>(
        "/hr/emergency-contacts/",
        { method: "POST", body: JSON.stringify(values) },
        accessToken,
      ),
    onSuccess: async () => {
      setContactError("");
      setSuccess("Emergency contact added.");
      await queryClient.invalidateQueries({
        queryKey: ["hr", "emergency-contacts", selectedEmployee?.id],
      });
    },
    onError: (error) =>
      setContactError(
        error instanceof Error
          ? error.message
          : "Unable to add emergency contact.",
      ),
  });
  const downloadDocument = useMutation({
    mutationFn: (document: EmployeeDocument) => {
      const storedName =
        document.file_name.split(/[\\/]/).filter(Boolean).pop() ||
        `${document.title}.download`;
      return apiDownload(
        `/hr/employee-documents/${encodeURIComponent(String(document.id))}/download/`,
        storedName,
        accessToken,
      );
    },
    onSuccess: () => setDownloadError(""),
    onError: (error) =>
      setDownloadError(
        error instanceof Error ? error.message : "Unable to download document.",
      ),
  });
  const attendanceAction = useMutation({
    mutationFn: (action: "check-in" | "check-out") =>
      apiRequest(
        `/hr/attendance/${action}/`,
        { method: "POST", body: JSON.stringify({}) },
        accessToken,
      ),
    onSuccess: async (_result, action) => {
      setFormError("");
      setSuccess(
        action === "check-in" ? "Check-in recorded." : "Check-out recorded.",
      );
      await queryClient.invalidateQueries({ queryKey: ["hr", "attendance"] });
    },
    onError: (error) =>
      setFormError(
        error instanceof Error ? error.message : "Attendance update failed.",
      ),
  });
  const createLeave = useMutation({
    mutationFn: (values: {
      leave_type: Identifier;
      start_date: string;
      end_date: string;
      reason: string;
    }) =>
      apiRequest<LeaveRequest>(
        "/hr/leave-requests/",
        { method: "POST", body: JSON.stringify(values) },
        accessToken,
      ),
    onSuccess: async () => {
      setLeaveFormError("");
      setSuccess("Leave request submitted.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["hr", "leave-requests"] }),
        queryClient.invalidateQueries({ queryKey: ["hr", "leave-balances"] }),
      ]);
    },
    onError: (error) =>
      setLeaveFormError(
        error instanceof Error
          ? error.message
          : "Unable to submit leave request.",
      ),
  });
  const reviewLeave = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: Identifier;
      action: "approve" | "reject";
    }) =>
      apiRequest(
        `/hr/leave-requests/${encodeURIComponent(String(id))}/${action}/`,
        { method: "POST", body: JSON.stringify({}) },
        accessToken,
      ),
    onSuccess: async (_result, variables) => {
      setFormError("");
      setSuccess(
        `Leave request ${variables.action === "approve" ? "approved" : "rejected"}.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["hr", "leave-requests"] }),
        queryClient.invalidateQueries({ queryKey: ["hr", "leave-balances"] }),
      ]);
    },
    onError: (error) =>
      setFormError(
        error instanceof Error
          ? error.message
          : "Unable to update leave request.",
      ),
  });

  const employeeRecords = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return records(employees.data).filter((employee) => {
      if (!needle) return true;
      const haystack = [
        employeeName(employee),
        employee.email,
        employee.job_title,
        employee.position,
        employee.title,
        departmentName(employee.department),
        employee.department_name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();
      return haystack.includes(needle);
    });
  }, [employees.data, search]);
  const availableUsers = records(users.data).filter(
    (account) =>
      !records(employees.data).some(
        (employee) => String(employee.user) === String(account.id),
      ),
  );
  const availableDesignations = records(designations.data).filter(
    (designation) =>
      !profileDepartment ||
      String(designation.department) === profileDepartment,
  );

  function selectSection(next: Section) {
    setSection(next);
    setFormError("");
    setSuccess("");
  }

  function submitDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const code = String(form.get("code") ?? "")
      .trim()
      .toUpperCase();
    const description = String(form.get("description") ?? "").trim();
    if (!name) {
      setFormError("Enter a department name.");
      return;
    }
    if (!/^[A-Z0-9_-]{2,20}$/.test(code)) {
      setFormError(
        "Use 2–20 letters, numbers, underscores, or hyphens for the code.",
      );
      return;
    }
    setFormError("");
    createDepartment.mutate({ name, code, description });
  }

  function submitEmployee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const userId = Number(form.get("user"));
    const employeeNumber = String(form.get("employee_number") ?? "").trim();
    const department = String(form.get("department") ?? "");
    const designation = String(form.get("designation") ?? "");
    const manager = String(form.get("manager") ?? "");
    const hireDate = String(form.get("hire_date") ?? "");
    if (
      !userId ||
      !employeeNumber ||
      !department ||
      !designation ||
      !hireDate
    ) {
      setProfileError("Complete all required employee fields.");
      return;
    }
    setProfileError("");
    createEmployee.mutate({
      user: userId,
      employee_number: employeeNumber,
      department,
      designation,
      ...(manager ? { manager } : {}),
      hire_date: hireDate,
    });
  }

  function submitDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEmployee) return;
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim();
    const documentType = String(form.get("document_type") ?? "").trim();
    const file =
      event.currentTarget.querySelector<HTMLInputElement>('input[name="file"]')
        ?.files?.[0];
    const expiresOn = String(form.get("expires_on") ?? "");
    if (!title || !documentType || !file || file.size === 0) {
      setDocumentError("Enter a title and type, then choose a file.");
      return;
    }
    const payload = new FormData();
    payload.set("employee", String(selectedEmployee.id));
    payload.set("title", title);
    payload.set("document_type", documentType);
    payload.set("file", file);
    if (expiresOn) payload.set("expires_on", expiresOn);
    setDocumentError("");
    uploadDocument.mutate(payload);
    event.currentTarget.reset();
  }

  function submitEmergencyContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEmployee) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const relationship = String(form.get("relationship") ?? "").trim();
    const phone = String(form.get("phone") ?? "").trim();
    const email = String(form.get("email") ?? "").trim();
    if (!name || !relationship || !phone) {
      setContactError("Enter a contact name, relationship, and phone number.");
      return;
    }
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setContactError("Enter a valid email address.");
      return;
    }
    setContactError("");
    createEmergencyContact.mutate({
      employee: selectedEmployee.id,
      name,
      relationship,
      phone,
      ...(email ? { email } : {}),
      is_primary: form.get("is_primary") === "on",
    });
    event.currentTarget.reset();
  }

  function submitLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const leaveType = String(form.get("leave_type") ?? "");
    const startDate = String(form.get("start_date") ?? "");
    const endDate = String(form.get("end_date") ?? "");
    const reason = String(form.get("reason") ?? "").trim();
    if (!leaveType || !startDate || !endDate || !reason) {
      setLeaveFormError("Complete every field before submitting.");
      return;
    }
    if (endDate < startDate) {
      setLeaveFormError("The end date must be on or after the start date.");
      return;
    }
    setLeaveFormError("");
    createLeave.mutate({
      leave_type: leaveType,
      start_date: startDate,
      end_date: endDate,
      reason,
    });
    event.currentTarget.reset();
  }

  const heading =
    sections.find((item) => item.id === section)?.label ?? "People";

  return (
    <div className="page-stack hr-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PEOPLE OPERATIONS</p>
          <h1>Human resources</h1>
          <p className="muted-text">
            Departments, employee records, time, leave and holidays.
          </p>
        </div>
        {section === "departments" && (
          <Button
            size="sm"
            onClick={() => {
              setShowDepartmentForm((show) => !show);
              setFormError("");
              setSuccess("");
            }}
          >
            <Plus size={15} /> Add department
          </Button>
        )}
        {section === "employees" &&
          peopleView === "directory" &&
          canManageEmployees && (
            <Button
              size="sm"
              onClick={() => {
                setShowEmployeeForm((show) => !show);
                setProfileError("");
                setSuccess("");
              }}
            >
              <Plus size={15} /> Add employee
            </Button>
          )}
      </div>
      <nav className="hr-tabs" aria-label="HR sections">
        {sections.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`hr-tab ${section === id ? "hr-tab-active" : ""}`}
            aria-current={section === id ? "page" : undefined}
            onClick={() => selectSection(id)}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </nav>
      {success && (
        <p className="success-message" role="status">
          {success}
        </p>
      )}
      {formError && (section !== "departments" || !showDepartmentForm) && (
        <ErrorNotice error={formError} />
      )}

      {section === "departments" && (
        <section className="page-stack">
          {showDepartmentForm && (
            <Card className="hr-form-card">
              <h2>Add a department</h2>
              <form
                className="hr-form-row"
                onSubmit={submitDepartment}
                noValidate
              >
                <label>
                  Department name
                  <input
                    name="name"
                    required
                    maxLength={120}
                    placeholder="e.g. Engineering"
                  />
                </label>
                <label>
                  Department code
                  <input
                    name="code"
                    required
                    minLength={2}
                    maxLength={20}
                    pattern="[A-Za-z0-9_-]{2,20}"
                    placeholder="e.g. ENG"
                  />
                </label>
                <label>
                  Description
                  <input
                    name="description"
                    maxLength={500}
                    placeholder="Optional description"
                  />
                </label>
                <Button
                  type="submit"
                  size="sm"
                  disabled={createDepartment.isPending}
                >
                  {createDepartment.isPending ? "Saving…" : "Save department"}
                </Button>
              </form>
              {formError && <ErrorNotice error={formError} />}
            </Card>
          )}
          <Card className="hr-panel">
            <div className="hr-panel-heading">
              <div>
                <h2>Departments</h2>
                <p className="muted-text">Teams and their reporting groups.</p>
              </div>
              <span className="hr-count">
                {records(departments.data).length}
              </span>
            </div>
            <QueryState
              loading={departments.isLoading}
              error={departments.error}
              empty={
                !departments.isLoading &&
                !departments.error &&
                records(departments.data).length === 0
              }
            >
              <div className="hr-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Department</th>
                      <th>Description</th>
                      <th>Department lead</th>
                      <th>Employees</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records(departments.data).map((department) => (
                      <tr key={department.id}>
                        <td>
                          <strong>{department.name}</strong>
                        </td>
                        <td>{department.description || "—"}</td>
                        <td>
                          {department.manager_name ||
                            department.head_name ||
                            "—"}
                        </td>
                        <td>{department.employee_count ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </QueryState>
          </Card>
        </section>
      )}

      {section === "employees" && (
        <section className="page-stack">
          <div className="hr-subtabs" aria-label="Employee views">
            <button
              type="button"
              className={peopleView === "directory" ? "selected" : ""}
              onClick={() => setPeopleView("directory")}
            >
              <Users size={15} /> Directory
            </button>
            <button
              type="button"
              className={peopleView === "org" ? "selected" : ""}
              onClick={() => setPeopleView("org")}
            >
              <Network size={15} /> Organization chart
            </button>
          </div>
          {peopleView === "directory" &&
            showEmployeeForm &&
            canManageEmployees && (
              <Card className="hr-form-card">
                <div className="hr-panel-heading">
                  <div>
                    <h2>Create employee profile</h2>
                    <p className="muted-text">
                      Link an existing account to a department and designation.
                    </p>
                  </div>
                </div>
                {profileError && <ErrorNotice error={profileError} />}
                {users.isError && <ErrorNotice error={users.error} />}
                {departments.isError && (
                  <ErrorNotice error={departments.error} />
                )}
                {designations.isError && (
                  <ErrorNotice error={designations.error} />
                )}
                <form
                  className="hr-employee-form"
                  onSubmit={submitEmployee}
                  noValidate
                >
                  <label>
                    User account
                    <select name="user" required defaultValue="">
                      <option value="" disabled>
                        Select an account
                      </option>
                      {availableUsers.map((account) => (
                        <option key={account.id} value={account.id}>
                          {userName(account)} · {account.email}
                        </option>
                      ))}
                    </select>
                    {!users.isLoading &&
                      !users.isError &&
                      availableUsers.length === 0 && (
                        <small className="hr-field-hint">
                          No unassigned user accounts are available.
                        </small>
                      )}
                  </label>
                  <label>
                    Employee number
                    <input
                      name="employee_number"
                      required
                      maxLength={30}
                      placeholder="e.g. EMP-1042"
                    />
                  </label>
                  <label>
                    Department
                    <select
                      name="department"
                      required
                      value={profileDepartment}
                      onChange={(event) =>
                        setProfileDepartment(event.target.value)
                      }
                    >
                      <option value="" disabled>
                        Select department
                      </option>
                      {records(departments.data).map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Designation
                    <select name="designation" required defaultValue="">
                      <option value="" disabled>
                        Select designation
                      </option>
                      {availableDesignations.map((designation) => (
                        <option key={designation.id} value={designation.id}>
                          {designation.title}
                        </option>
                      ))}
                    </select>
                    {!designations.isLoading &&
                      !designations.isError &&
                      availableDesignations.length === 0 && (
                        <small className="hr-field-hint">
                          No designations are available for this department.
                        </small>
                      )}
                  </label>
                  <label>
                    Manager (optional)
                    <select name="manager" defaultValue="">
                      <option value="">No manager</option>
                      {records(employees.data).map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employeeName(employee)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Hire date
                    <input name="hire_date" type="date" required />
                  </label>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={
                      createEmployee.isPending ||
                      users.isLoading ||
                      departments.isLoading ||
                      designations.isLoading
                    }
                  >
                    {createEmployee.isPending ? "Creating…" : "Create profile"}
                  </Button>
                </form>
              </Card>
            )}
          {peopleView === "directory" ? (
            <>
              <div className="hr-search">
                <Search size={16} aria-hidden="true" />
                <input
                  aria-label="Search employees"
                  placeholder="Search name, role, email or department"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              <Card className="hr-panel">
                <div className="hr-panel-heading">
                  <div>
                    <h2>Employee directory</h2>
                    <p className="muted-text">
                      Select a person to view their profile.
                    </p>
                  </div>
                  <span className="hr-count">{employeeRecords.length}</span>
                </div>
                <QueryState
                  loading={employees.isLoading}
                  error={employees.error}
                  empty={
                    !employees.isLoading &&
                    !employees.error &&
                    employeeRecords.length === 0
                  }
                >
                  <div className="hr-table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Employee</th>
                          <th>Position</th>
                          <th>Department</th>
                          <th>Status</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {employeeRecords.map((employee) => (
                          <tr key={employee.id}>
                            <td>
                              <strong>{employeeName(employee)}</strong>
                              <small className="hr-cell-subtitle">
                                {employee.email || ""}
                              </small>
                            </td>
                            <td>
                              {employee.job_title ||
                                employee.designation_title ||
                                employee.designation ||
                                employee.position ||
                                employee.title ||
                                "—"}
                            </td>
                            <td>
                              {employee.department_name ||
                                departmentName(employee.department)}
                            </td>
                            <td>
                              <span className="status-chip">
                                {employee.employment_status ||
                                  (employee.is_active === false
                                    ? "Inactive"
                                    : "Active")}
                              </span>
                            </td>
                            <td>
                              <button
                                type="button"
                                className="hr-link-button"
                                onClick={() => setSelectedEmployee(employee)}
                              >
                                View <ChevronRight size={14} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </QueryState>
              </Card>
              {selectedEmployee && (
                <Card className="hr-panel hr-profile">
                  <div className="hr-panel-heading">
                    <div className="hr-profile-title">
                      <span className="hr-avatar">
                        <UserRound size={20} />
                      </span>
                      <div>
                        <h2>{employeeName(selectedEmployee)}</h2>
                        <p className="muted-text">
                          {selectedEmployee.job_title ||
                            selectedEmployee.designation_title ||
                            selectedEmployee.designation ||
                            selectedEmployee.position ||
                            selectedEmployee.title ||
                            "Employee"}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Close employee details"
                      onClick={() => setSelectedEmployee(null)}
                    >
                      <X size={16} />
                    </Button>
                  </div>
                  <dl className="hr-details">
                    <div>
                      <dt>Email</dt>
                      <dd>{selectedEmployee.email || "—"}</dd>
                    </div>
                    <div>
                      <dt>Department</dt>
                      <dd>
                        {selectedEmployee.department_name ||
                          departmentName(selectedEmployee.department)}
                      </dd>
                    </div>
                    <div>
                      <dt>Manager</dt>
                      <dd>
                        {selectedEmployee.manager_name ||
                          employeeName(selectedEmployee.manager)}
                      </dd>
                    </div>
                    <div>
                      <dt>Phone</dt>
                      <dd>{selectedEmployee.phone || "—"}</dd>
                    </div>
                    <div>
                      <dt>Hire date</dt>
                      <dd>{displayDate(selectedEmployee.hire_date)}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>
                        {selectedEmployee.employment_status ||
                          (selectedEmployee.is_active === false
                            ? "Inactive"
                            : "Active")}
                      </dd>
                    </div>
                  </dl>
                  {canViewPrivateEmployeeData && (
                    <div className="hr-detail-sections">
                      <section className="hr-detail-section">
                        <div className="hr-panel-heading">
                          <div>
                            <h2>Documents</h2>
                            <p className="muted-text">
                              Private employee files; downloads require your
                              sign-in.
                            </p>
                          </div>
                        </div>
                        {documentError && <ErrorNotice error={documentError} />}
                        {downloadError && <ErrorNotice error={downloadError} />}
                        <form
                          className="hr-document-form"
                          onSubmit={submitDocument}
                          noValidate
                        >
                          <label>
                            Title
                            <input name="title" required maxLength={150} />
                          </label>
                          <label>
                            Document type
                            <input
                              name="document_type"
                              required
                              maxLength={40}
                              placeholder="e.g. identity"
                            />
                          </label>
                          <label>
                            Expires (optional)
                            <input name="expires_on" type="date" />
                          </label>
                          <label>
                            File (PDF, PNG, JPEG or DOCX)
                            <input
                              name="file"
                              type="file"
                              accept=".pdf,.png,.jpg,.jpeg,.docx"
                              required
                            />
                          </label>
                          <Button
                            type="submit"
                            size="sm"
                            disabled={uploadDocument.isPending}
                          >
                            <FileUp size={14} />
                            {uploadDocument.isPending ? "Uploading…" : "Upload"}
                          </Button>
                        </form>
                        <QueryState
                          loading={employeeDocuments.isLoading}
                          error={employeeDocuments.error}
                          empty={
                            !employeeDocuments.isLoading &&
                            !employeeDocuments.error &&
                            records(employeeDocuments.data).length === 0
                          }
                        >
                          <div className="hr-private-list">
                            {records(employeeDocuments.data).map((document) => (
                              <div className="hr-private-row" key={document.id}>
                                <div>
                                  <strong>{document.title}</strong>
                                  <small>
                                    {document.document_type}
                                    {document.expires_on
                                      ? ` · Expires ${displayDate(document.expires_on)}`
                                      : ""}
                                  </small>
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={downloadDocument.isPending}
                                  onClick={() =>
                                    downloadDocument.mutate(document)
                                  }
                                >
                                  <Download size={13} /> Download
                                </Button>
                              </div>
                            ))}
                          </div>
                        </QueryState>
                      </section>
                      <section className="hr-detail-section">
                        <div className="hr-panel-heading">
                          <div>
                            <h2>Emergency contacts</h2>
                            <p className="muted-text">
                              Contact details for urgent situations.
                            </p>
                          </div>
                        </div>
                        {contactError && <ErrorNotice error={contactError} />}
                        <QueryState
                          loading={emergencyContacts.isLoading}
                          error={emergencyContacts.error}
                          empty={
                            !emergencyContacts.isLoading &&
                            !emergencyContacts.error &&
                            records(emergencyContacts.data).length === 0
                          }
                        >
                          <div className="hr-private-list">
                            {records(emergencyContacts.data).map((contact) => (
                              <div className="hr-private-row" key={contact.id}>
                                <div>
                                  <strong>
                                    {contact.name}
                                    {contact.is_primary ? " · Primary" : ""}
                                  </strong>
                                  <small>
                                    {contact.relationship} · {contact.phone}
                                    {contact.email ? ` · ${contact.email}` : ""}
                                  </small>
                                </div>
                              </div>
                            ))}
                          </div>
                        </QueryState>
                        <form
                          className="hr-contact-form"
                          onSubmit={submitEmergencyContact}
                          noValidate
                        >
                          <label>
                            Name
                            <input name="name" required maxLength={120} />
                          </label>
                          <label>
                            Relationship
                            <input
                              name="relationship"
                              required
                              maxLength={60}
                              placeholder="e.g. Partner"
                            />
                          </label>
                          <label>
                            Phone
                            <input
                              name="phone"
                              required
                              type="tel"
                              maxLength={30}
                            />
                          </label>
                          <label>
                            Email (optional)
                            <input name="email" type="email" maxLength={254} />
                          </label>
                          <label className="hr-checkbox">
                            <input name="is_primary" type="checkbox" />
                            Primary contact
                          </label>
                          <Button
                            type="submit"
                            size="sm"
                            disabled={createEmergencyContact.isPending}
                          >
                            <Plus size={14} />
                            {createEmergencyContact.isPending
                              ? "Adding…"
                              : "Add contact"}
                          </Button>
                        </form>
                      </section>
                    </div>
                  )}
                </Card>
              )}
            </>
          ) : (
            <Card className="hr-panel">
              <div className="hr-panel-heading">
                <div>
                  <h2>Organization chart</h2>
                  <p className="muted-text">
                    Reporting relationships across your organization.
                  </p>
                </div>
              </div>
              <QueryState
                loading={orgChart.isLoading}
                error={orgChart.error}
                empty={
                  !orgChart.isLoading &&
                  !orgChart.error &&
                  records(orgChart.data).length === 0
                }
              >
                <div className="org-chart">
                  {records(orgChart.data).map((node) => (
                    <OrgTree key={node.id} node={node} depth={0} />
                  ))}
                </div>
              </QueryState>
            </Card>
          )}
        </section>
      )}

      {section === "attendance" && (
        <section className="page-stack">
          <div className="hr-attendance-actions">
            <div>
              <h2>{heading} records</h2>
              <p className="muted-text">Record your attendance for today.</p>
            </div>
            <div className="page-heading-actions">
              <Button
                size="sm"
                disabled={attendanceAction.isPending}
                onClick={() => attendanceAction.mutate("check-in")}
              >
                <Check size={15} />{" "}
                {attendanceAction.isPending ? "Saving…" : "Check in"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={attendanceAction.isPending}
                onClick={() => attendanceAction.mutate("check-out")}
              >
                <Clock3 size={15} /> Check out
              </Button>
            </div>
          </div>
          <Card className="hr-panel">
            <div className="hr-panel-heading hr-month-heading">
              <div>
                <h2>Monthly attendance summary</h2>
                <p className="muted-text">
                  Attendance totals for each employee in the selected month.
                </p>
              </div>
              <MonthPicker month={reportMonth} onChange={setReportMonth} />
            </div>
            <QueryState
              loading={attendanceSummary.isLoading}
              error={attendanceSummary.error}
              empty={
                !attendanceSummary.isLoading &&
                !attendanceSummary.error &&
                records(attendanceSummary.data).length === 0
              }
            >
              <div className="hr-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Employee number</th>
                      <th>Days present</th>
                      <th>Late days</th>
                      <th>Early departures</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records(attendanceSummary.data).map((summary) => (
                      <tr key={summary.employee_id}>
                        <td>
                          <strong>{summary.employee_name}</strong>
                        </td>
                        <td>{summary.employee_number}</td>
                        <td>{summary.days_present}</td>
                        <td>{summary.late_days}</td>
                        <td>{summary.early_departure_days}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </QueryState>
          </Card>
          <Card className="hr-panel">
            <div className="hr-panel-heading">
              <div>
                <h2>Attendance</h2>
                <p className="muted-text">Recent attendance records.</p>
              </div>
              <span className="hr-count">
                {records(attendance.data).length}
              </span>
            </div>
            <QueryState
              loading={attendance.isLoading}
              error={attendance.error}
              empty={
                !attendance.isLoading &&
                !attendance.error &&
                records(attendance.data).length === 0
              }
            >
              <div className="hr-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Date</th>
                      <th>Check in</th>
                      <th>Check out</th>
                      <th>Hours</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records(attendance.data).map((record) => (
                      <tr key={record.id}>
                        <td>
                          <strong>
                            {record.employee_name ||
                              employeeName(record.employee)}
                          </strong>
                        </td>
                        <td>{displayDate(record.date)}</td>
                        <td>{displayTime(record.check_in)}</td>
                        <td>{displayTime(record.check_out)}</td>
                        <td>{record.hours_worked ?? "—"}</td>
                        <td>
                          <span className="status-chip">
                            {record.status || "Recorded"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </QueryState>
          </Card>
        </section>
      )}

      {section === "leave" && (
        <section className="page-stack">
          <Card className="hr-panel">
            <div className="hr-panel-heading hr-month-heading">
              <div>
                <h2>Team leave calendar</h2>
                <p className="muted-text">
                  Pending and approved leave in your employee scope.
                </p>
              </div>
              <MonthPicker month={reportMonth} onChange={setReportMonth} />
            </div>
            <QueryState
              loading={leaveCalendar.isLoading}
              error={leaveCalendar.error}
              empty={
                !leaveCalendar.isLoading &&
                !leaveCalendar.error &&
                records(leaveCalendar.data).length === 0
              }
            >
              <LeaveMonthCalendar
                month={reportMonth}
                requests={records(leaveCalendar.data)}
              />
            </QueryState>
          </Card>
          <Card className="hr-form-card">
            <div className="hr-panel-heading">
              <div>
                <h2>Request leave</h2>
                <p className="muted-text">
                  Submit a request for manager review.
                </p>
              </div>
            </div>
            {leaveFormError && <ErrorNotice error={leaveFormError} />}
            {leaveTypes.isError && <ErrorNotice error={leaveTypes.error} />}
            <form className="hr-leave-form" onSubmit={submitLeave} noValidate>
              <label>
                Leave type
                <select name="leave_type" required defaultValue="">
                  <option value="" disabled>
                    Select type
                  </option>
                  {records(leaveTypes.data).map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                From
                <input name="start_date" type="date" required />
              </label>
              <label>
                To
                <input name="end_date" type="date" required />
              </label>
              <label className="hr-reason-field">
                Reason
                <textarea
                  name="reason"
                  required
                  maxLength={2000}
                  rows={2}
                  placeholder="Add context for your request"
                />
              </label>
              <Button
                type="submit"
                size="sm"
                disabled={
                  createLeave.isPending ||
                  leaveTypes.isLoading ||
                  records(leaveTypes.data).length === 0
                }
              >
                {createLeave.isPending ? "Submitting…" : "Submit request"}
              </Button>
            </form>
          </Card>
          <Card className="hr-panel">
            <div className="hr-panel-heading">
              <div>
                <h2>Leave balances</h2>
                <p className="muted-text">
                  Your available balance by leave type.
                </p>
              </div>
            </div>
            <QueryState
              loading={leaveBalances.isLoading}
              error={leaveBalances.error}
              empty={
                !leaveBalances.isLoading &&
                !leaveBalances.error &&
                records(leaveBalances.data).length === 0
              }
            >
              <div className="hr-balance-grid">
                {records(leaveBalances.data).map((balance) => (
                  <div className="hr-balance" key={balance.id}>
                    <span>
                      {balance.leave_type_name ||
                        (typeof balance.leave_type === "string"
                          ? balance.leave_type
                          : balance.leave_type?.name) ||
                        "Leave"}
                    </span>
                    <strong>
                      {balance.available_days ??
                        balance.remaining_days ??
                        balance.days_remaining ??
                        balance.balance ??
                        "—"}
                    </strong>
                    <small>days remaining</small>
                  </div>
                ))}
              </div>
            </QueryState>
          </Card>
          <Card className="hr-panel">
            <div className="hr-panel-heading">
              <div>
                <h2>Leave requests</h2>
                <p className="muted-text">
                  Review submitted requests and current status.
                </p>
              </div>
              <span className="hr-count">
                {records(leaveRequests.data).length}
              </span>
            </div>
            <QueryState
              loading={leaveRequests.isLoading}
              error={leaveRequests.error}
              empty={
                !leaveRequests.isLoading &&
                !leaveRequests.error &&
                records(leaveRequests.data).length === 0
              }
            >
              <div className="hr-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Type</th>
                      <th>Dates</th>
                      <th>Days</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records(leaveRequests.data).map((request) => {
                      const pending =
                        !request.status ||
                        request.status.toLowerCase() === "pending";
                      return (
                        <tr key={request.id}>
                          <td>
                            <strong>
                              {request.employee_name ||
                                employeeName(request.employee)}
                            </strong>
                          </td>
                          <td>
                            {request.leave_type_name ||
                              (typeof request.leave_type === "string"
                                ? request.leave_type
                                : request.leave_type?.name) ||
                              "—"}
                          </td>
                          <td>
                            {displayDate(request.start_date)} –{" "}
                            {displayDate(request.end_date)}
                          </td>
                          <td>
                            {request.requested_days ?? request.days ?? "—"}
                          </td>
                          <td className="hr-reason">{request.reason || "—"}</td>
                          <td>
                            <span className="status-chip">
                              {request.status || "Pending"}
                            </span>
                          </td>
                          <td>
                            {pending ? (
                              <div className="hr-actions">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={reviewLeave.isPending}
                                  aria-label={`Approve request ${request.id}`}
                                  onClick={() =>
                                    reviewLeave.mutate({
                                      id: request.id,
                                      action: "approve",
                                    })
                                  }
                                >
                                  <Check size={13} /> Approve
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  disabled={reviewLeave.isPending}
                                  aria-label={`Reject request ${request.id}`}
                                  onClick={() =>
                                    reviewLeave.mutate({
                                      id: request.id,
                                      action: "reject",
                                    })
                                  }
                                >
                                  <X size={13} /> Reject
                                </Button>
                              </div>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </QueryState>
          </Card>
        </section>
      )}

      {section === "holidays" && (
        <Card className="hr-panel">
          <div className="hr-panel-heading">
            <div>
              <h2>Holiday calendar</h2>
              <p className="muted-text">Upcoming company holidays.</p>
            </div>
            <CalendarDays size={18} className="muted-text" />
          </div>
          <QueryState
            loading={holidays.isLoading}
            error={holidays.error}
            empty={
              !holidays.isLoading &&
              !holidays.error &&
              records(holidays.data).length === 0
            }
          >
            <HolidayMonth
              holidays={records(holidays.data)}
              monthOffset={holidayMonthOffset}
              onMonthChange={setHolidayMonthOffset}
            />
            <div className="hr-holiday-list">
              {records(holidays.data).map((holiday) => {
                const date = holiday.date || holiday.start_date;
                return (
                  <article className="hr-holiday" key={holiday.id}>
                    <div className="hr-holiday-date">
                      <strong>
                        {date
                          ? new Date(
                              `${date.slice(0, 10)}T00:00:00`,
                            ).toLocaleDateString(undefined, { day: "2-digit" })
                          : "—"}
                      </strong>
                      <span>
                        {date
                          ? new Date(
                              `${date.slice(0, 10)}T00:00:00`,
                            ).toLocaleDateString(undefined, { month: "short" })
                          : ""}
                      </span>
                    </div>
                    <div>
                      <h3>{holiday.name}</h3>
                      <p>
                        {holiday.description || displayDate(date)}
                        {holiday.end_date && holiday.end_date !== date
                          ? ` – ${displayDate(holiday.end_date)}`
                          : ""}
                      </p>
                    </div>
                  </article>
                );
              })}
            </div>
          </QueryState>
        </Card>
      )}
    </div>
  );
}

function OrgTree({ node, depth }: { node: OrgNode; depth: number }) {
  return (
    <div
      className="org-tree-node"
      style={{ marginInlineStart: Math.min(depth, 6) * 24 }}
    >
      <div className="org-person">
        <span className="hr-avatar">
          <UserRound size={18} />
        </span>
        <div>
          <strong>{employeeName(node)}</strong>
          <small>
            {node.job_title ||
              node.designation_title ||
              node.designation ||
              node.position ||
              node.title ||
              departmentName(node.department)}
          </small>
        </div>
      </div>
      {node.children?.map((child) => (
        <OrgTree key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

function MonthPicker({
  month,
  onChange,
}: {
  month: Date;
  onChange: (month: Date) => void;
}) {
  const label = month.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
  return (
    <div className="hr-report-month">
      <Button
        variant="ghost"
        size="sm"
        aria-label="Previous report month"
        onClick={() =>
          onChange(new Date(month.getFullYear(), month.getMonth() - 1, 1))
        }
      >
        <ChevronLeft size={16} />
      </Button>
      <strong aria-live="polite">{label}</strong>
      <Button
        variant="ghost"
        size="sm"
        aria-label="Next report month"
        onClick={() =>
          onChange(new Date(month.getFullYear(), month.getMonth() + 1, 1))
        }
      >
        <ChevronRight size={16} />
      </Button>
    </div>
  );
}

function LeaveMonthCalendar({
  month,
  requests,
}: {
  month: Date;
  requests: LeaveRequest[];
}) {
  const leadingDays = month.getDay();
  const daysInMonth = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  ).getDate();
  const days = [
    ...Array.from({ length: leadingDays }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];
  const monthLabel = month.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  function dateKey(day: number): string {
    return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  function requestsForDay(day: number): LeaveRequest[] {
    const current = dateKey(day);
    return requests.filter((request) => {
      const start = request.start_date?.slice(0, 10);
      const end = request.end_date?.slice(0, 10);
      return Boolean(start && end && current >= start && current <= end);
    });
  }

  return (
    <div
      className="hr-team-calendar"
      role="grid"
      aria-label={`${monthLabel} team leave`}
    >
      {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
        <span className="hr-calendar-weekday" key={day} role="columnheader">
          {day}
        </span>
      ))}
      {days.map((day, index) => {
        const entries = day === null ? [] : requestsForDay(day);
        return (
          <div
            className={`hr-team-calendar-day ${entries.length ? "hr-team-calendar-busy" : ""}`}
            key={day === null ? `blank-${index}` : day}
            role="gridcell"
            aria-label={
              day === null
                ? undefined
                : `${dateKey(day)}${entries.length ? `: ${entries.map((request) => request.employee_name || employeeName(request.employee)).join(", ")}` : ""}`
            }
          >
            {day !== null && (
              <>
                <span className="hr-team-calendar-date">{day}</span>
                {entries.map((request) => (
                  <small
                    className={`hr-leave-event ${request.status?.toLowerCase() === "approved" ? "approved" : "pending"}`}
                    key={request.id}
                    title={`${request.employee_name || employeeName(request.employee)} · ${request.status || "Pending"}`}
                  >
                    {request.employee_name || employeeName(request.employee)}
                    <em>{request.status || "Pending"}</em>
                  </small>
                ))}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HolidayMonth({
  holidays,
  monthOffset,
  onMonthChange,
}: {
  holidays: Holiday[];
  monthOffset: number;
  onMonthChange: (offset: number) => void;
}) {
  const today = new Date();
  const month = new Date(
    today.getFullYear(),
    today.getMonth() + monthOffset,
    1,
  );
  const daysInMonth = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  ).getDate();
  const monthLabel = month.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
  const cells = [
    ...Array.from({ length: month.getDay() }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];

  function dayKey(day: number): string {
    return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  function holidaysForDay(day: number): Holiday[] {
    const key = dayKey(day);
    return holidays.filter((holiday) => {
      const start = holiday.date || holiday.start_date;
      const firstDay = start?.slice(0, 10);
      const lastDay = (holiday.end_date || start)?.slice(0, 10);
      return Boolean(firstDay && lastDay && key >= firstDay && key <= lastDay);
    });
  }

  return (
    <div className="hr-calendar">
      <div className="hr-calendar-heading">
        <h3>{monthLabel}</h3>
        <div>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Previous month"
            onClick={() => onMonthChange(monthOffset - 1)}
          >
            <ChevronLeft size={16} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Next month"
            onClick={() => onMonthChange(monthOffset + 1)}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      </div>
      <div className="hr-calendar-grid" role="grid" aria-label={monthLabel}>
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
          <span className="hr-calendar-weekday" key={day} role="columnheader">
            {day}
          </span>
        ))}
        {cells.map((day, index) => {
          const dayHolidays = day === null ? [] : holidaysForDay(day);
          return (
            <div
              className={`hr-calendar-day ${dayHolidays.length ? "hr-calendar-holiday" : ""}`}
              key={day === null ? `blank-${index}` : day}
              role="gridcell"
              aria-label={
                day === null
                  ? undefined
                  : `${dayKey(day)}${dayHolidays.length ? `: ${dayHolidays.map(({ name }) => name).join(", ")}` : ""}`
              }
              title={dayHolidays.map(({ name }) => name).join(", ")}
            >
              {day !== null && (
                <>
                  <span>{day}</span>
                  {dayHolidays.map((holiday) => (
                    <small key={holiday.id}>{holiday.name}</small>
                  ))}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

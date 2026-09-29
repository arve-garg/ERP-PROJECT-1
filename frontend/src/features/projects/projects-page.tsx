import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  CalendarDays,
  Check,
  CirclePlus,
  Clock3,
  Download,
  FileUp,
  ListTodo,
  Users,
} from "lucide-react";
import {
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  type ReactNode,
} from "react";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { apiDownload, apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";

type Identifier = number | string;
const deliveryApiPath = (path: string) => `/projects${path}`;

type Resource =
  | "clients"
  | "projects"
  | "milestones"
  | "tasks"
  | "sprints"
  | "time-entries"
  | "resource-allocations"
  | "task-labels"
  | "task-attachments"
  | "task-comments"
  | "time-submissions"
  | "bugs"
  | "release-notes"
  | "wiki-pages"
  | "documents"
  | "hourly-costs";

interface WorkItem {
  id: Identifier;
  name?: string;
  title?: string;
  status?: string;
  client_name?: string;
  project_name?: string;
  task_title?: string;
  employee_name?: string;
  assignee_name?: string;
  email?: string;
  start_date?: string | null;
  end_date?: string | null;
  due_date?: string | null;
  date?: string | null;
  hours?: string | number | null;
  budget?: string | number | null;
  estimate_hours?: string | number | null;
  priority?: string;
  billable?: boolean;
  is_billable?: boolean;
  work_date?: string | null;
  code?: string;
  manager_name?: string;
  allocation_percent?: number | string | null;
  labels?: Identifier[];
  file_name?: string;
  task?: Identifier;
  project?: Identifier;
  entries?: Identifier[];
  period_type?: string;
  period_start?: string;
  period_end?: string;
  remaining_estimate_hours?: number | string;
  completed_estimate_hours?: number | string;
  actual_cost?: number | string;
  remaining_budget?: number | string;
  approved_hours?: number | string;
  billable_hours?: number | string;
  unpriced_approved_hours?: number | string;
  author_name?: string;
  employee_number?: string;
  currency?: string;
  hourly_cost?: number | string;
  effective_from?: string;
  effective_to?: string | null;
  is_published?: boolean;
  client_visible?: boolean;
  color?: string;
  body?: string;
  [key: string]: unknown;
}

interface FieldSpec {
  name: string;
  label: string;
  type?: "text" | "email" | "date" | "number" | "textarea" | "select" | "file";
  required?: boolean;
  options?: readonly string[];
  min?: string;
  step?: string;
}

interface SectionSpec {
  id: Resource;
  label: string;
  description: string;
  icon: typeof BriefcaseBusiness;
  fields: readonly FieldSpec[];
  columns: readonly { key: string; label: string }[];
}

const sections: readonly SectionSpec[] = [
  {
    id: "clients",
    label: "Clients",
    description: "Client accounts and the projects delivered for them.",
    icon: Users,
    fields: [
      { name: "name", label: "Client name", required: true },
      { name: "email", label: "Contact email", type: "email" },
      { name: "phone", label: "Phone" },
      { name: "website", label: "Website" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    columns: [
      { key: "name", label: "Client" },
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
    ],
  },
  {
    id: "projects",
    label: "Projects",
    description: "Delivery plans, client commitments, and budget tracking.",
    icon: BriefcaseBusiness,
    fields: [
      { name: "name", label: "Project name", required: true },
      {
        name: "client",
        label: "Client ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "code", label: "Project code", required: true },
      {
        name: "manager",
        label: "Manager profile ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "description", label: "Description", type: "textarea" },
      { name: "start_date", label: "Start date", type: "date", required: true },
      { name: "end_date", label: "End date", type: "date" },
      {
        name: "budget",
        label: "Budget",
        type: "number",
        min: "0",
        step: "0.01",
      },
      { name: "budget_currency", label: "Budget currency (ISO code)" },
    ],
    columns: [
      { key: "name", label: "Project" },
      { key: "code", label: "Code" },
      { key: "client_name", label: "Client" },
      { key: "manager_name", label: "Manager" },
      { key: "status", label: "Status" },
      { key: "start_date", label: "Start" },
      { key: "end_date", label: "End" },
      { key: "budget", label: "Budget" },
    ],
  },
  {
    id: "milestones",
    label: "Milestones",
    description: "Track important delivery dates across client projects.",
    icon: CalendarDays,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "name", label: "Milestone", required: true },
      { name: "description", label: "Description", type: "textarea" },
      { name: "due_date", label: "Due date", type: "date", required: true },
    ],
    columns: [
      { key: "name", label: "Milestone" },
      { key: "project_name", label: "Project" },
      { key: "due_date", label: "Due date" },
      { key: "status", label: "Status" },
    ],
  },
  {
    id: "tasks",
    label: "Tasks",
    description: "Plan, assign, and track project work on a status board.",
    icon: ListTodo,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      {
        name: "assignee",
        label: "Assignee profile ID",
        type: "number",
        min: "1",
      },
      { name: "milestone", label: "Milestone ID", type: "number", min: "1" },
      { name: "sprint", label: "Sprint ID", type: "number", min: "1" },
      { name: "labels", label: "Label IDs (comma-separated)" },
      { name: "title", label: "Task title", required: true },
      { name: "description", label: "Description", type: "textarea" },
      {
        name: "priority",
        label: "Priority",
        type: "select",
        options: ["low", "medium", "high", "urgent"],
      },
      {
        name: "estimate_hours",
        label: "Estimate (hours)",
        type: "number",
        min: "0",
        step: "0.25",
      },
      { name: "due_date", label: "Due date", type: "date" },
    ],
    columns: [
      { key: "title", label: "Task" },
      { key: "project_name", label: "Project" },
      { key: "assignee_name", label: "Assignee" },
      { key: "priority", label: "Priority" },
      { key: "status", label: "Status" },
      { key: "estimate_hours", label: "Estimate (h)" },
      { key: "due_date", label: "Due date" },
    ],
  },
  {
    id: "sprints",
    label: "Sprints",
    description: "Organize project backlogs into time-boxed iterations.",
    icon: CalendarDays,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "name", label: "Sprint name", required: true },
      { name: "goal", label: "Sprint goal", type: "textarea" },
      { name: "start_date", label: "Start date", type: "date", required: true },
      { name: "end_date", label: "End date", type: "date", required: true },
    ],
    columns: [
      { key: "name", label: "Sprint" },
      { key: "project_name", label: "Project" },
      { key: "start_date", label: "Start" },
      { key: "end_date", label: "End" },
      { key: "status", label: "Status" },
    ],
  },
  {
    id: "time-entries",
    label: "Timesheets",
    description:
      "Log billable and non-billable effort, then submit for approval.",
    icon: Clock3,
    fields: [
      {
        name: "task",
        label: "Task ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "work_date", label: "Work date", type: "date", required: true },
      {
        name: "hours",
        label: "Hours",
        type: "number",
        required: true,
        min: "0.01",
        step: "0.25",
      },
      {
        name: "description",
        label: "Work summary",
        type: "textarea",
        required: true,
      },
      {
        name: "is_billable",
        label: "Billable",
        type: "select",
        options: ["true", "false"],
      },
    ],
    columns: [
      { key: "work_date", label: "Date" },
      { key: "project_name", label: "Project" },
      { key: "task_title", label: "Task" },
      { key: "employee_name", label: "Employee" },
      { key: "hours", label: "Hours" },
      { key: "is_billable", label: "Billable" },
      { key: "status", label: "Status" },
    ],
  },
  {
    id: "resource-allocations",
    label: "Resourcing",
    description: "Plan team capacity across project timelines.",
    icon: Users,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      {
        name: "employee",
        label: "Employee profile ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "start_date", label: "Start date", type: "date", required: true },
      { name: "end_date", label: "End date", type: "date", required: true },
      {
        name: "allocation_percent",
        label: "Allocation (%)",
        type: "number",
        required: true,
        min: "1",
        step: "1",
      },
      { name: "role", label: "Role (optional)" },
    ],
    columns: [
      { key: "project_name", label: "Project" },
      { key: "employee_name", label: "Employee" },
      { key: "start_date", label: "Start" },
      { key: "end_date", label: "End" },
      { key: "allocation_percent", label: "Capacity" },
    ],
  },
  {
    id: "task-labels",
    label: "Task labels",
    description: "Manage reusable labels for delivery tasks.",
    icon: ListTodo,
    fields: [
      { name: "name", label: "Label name", required: true },
      { name: "color", label: "Color", type: "text" },
    ],
    columns: [
      { key: "name", label: "Label" },
      { key: "color", label: "Color" },
    ],
  },
  {
    id: "task-comments",
    label: "Task comments",
    description: "Add discussion notes to a task.",
    icon: ListTodo,
    fields: [
      {
        name: "task",
        label: "Task ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "body", label: "Comment", type: "textarea", required: true },
    ],
    columns: [
      { key: "task", label: "Task ID" },
      { key: "author_name", label: "Author" },
      { key: "body", label: "Comment" },
    ],
  },
  {
    id: "task-attachments",
    label: "Task files",
    description: "Upload and securely download task attachments.",
    icon: FileUp,
    fields: [
      {
        name: "task",
        label: "Task ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "file", label: "File", type: "file", required: true },
    ],
    columns: [
      { key: "task", label: "Task ID" },
      { key: "file_name", label: "File" },
    ],
  },
  {
    id: "time-submissions",
    label: "Time submissions",
    description: "Submit daily or weekly time and review team submissions.",
    icon: Clock3,
    fields: [
      {
        name: "period_type",
        label: "Period",
        type: "select",
        required: true,
        options: ["daily", "weekly"],
      },
      {
        name: "period_start",
        label: "Period start",
        type: "date",
        required: true,
      },
      { name: "period_end", label: "Period end", type: "date", required: true },
      {
        name: "entries",
        label: "Time entry IDs (comma-separated)",
        required: true,
      },
    ],
    columns: [
      { key: "employee_number", label: "Employee" },
      { key: "period_type", label: "Period" },
      { key: "period_start", label: "From" },
      { key: "period_end", label: "To" },
      { key: "status", label: "Status" },
    ],
  },
  {
    id: "bugs",
    label: "Bugs",
    description: "Report, triage, and follow defects for internal projects.",
    icon: ListTodo,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "title", label: "Bug title", required: true },
      {
        name: "description",
        label: "Description",
        type: "textarea",
        required: true,
      },
      {
        name: "severity",
        label: "Severity",
        type: "select",
        options: ["low", "medium", "high", "critical"],
      },
    ],
    columns: [
      { key: "title", label: "Bug" },
      { key: "project_name", label: "Project" },
      { key: "severity", label: "Severity" },
      { key: "status", label: "Status" },
    ],
  },
  {
    id: "release-notes",
    label: "Release notes",
    description: "Draft and publish project release notes.",
    icon: BriefcaseBusiness,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "version", label: "Version", required: true },
      { name: "title", label: "Title", required: true },
      {
        name: "content",
        label: "Release details",
        type: "textarea",
        required: true,
      },
      {
        name: "release_date",
        label: "Release date",
        type: "date",
        required: true,
      },
      {
        name: "is_published",
        label: "Published",
        type: "select",
        options: ["true", "false"],
      },
    ],
    columns: [
      { key: "version", label: "Version" },
      { key: "title", label: "Title" },
      { key: "release_date", label: "Release date" },
      { key: "is_published", label: "Published" },
    ],
  },
  {
    id: "wiki-pages",
    label: "Wiki pages",
    description: "Maintain project knowledge and reference pages.",
    icon: BriefcaseBusiness,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "title", label: "Title", required: true },
      { name: "slug", label: "URL slug", required: true },
      { name: "content", label: "Content", type: "textarea", required: true },
    ],
    columns: [
      { key: "project_name", label: "Project" },
      { key: "title", label: "Page" },
      { key: "slug", label: "Slug" },
    ],
  },
  {
    id: "documents",
    label: "Project documents",
    description: "Upload and securely download project files.",
    icon: FileUp,
    fields: [
      {
        name: "project",
        label: "Project ID",
        type: "number",
        required: true,
        min: "1",
      },
      { name: "title", label: "Title", required: true },
      { name: "description", label: "Description" },
      { name: "file", label: "File", type: "file", required: true },
      {
        name: "client_visible",
        label: "Client visible",
        type: "select",
        options: ["true", "false"],
      },
    ],
    columns: [
      { key: "project_name", label: "Project" },
      { key: "title", label: "Document" },
      { key: "file_name", label: "File" },
      { key: "client_visible", label: "Client visible" },
    ],
  },
  {
    id: "hourly-costs",
    label: "Hourly costs",
    description: "Manage employee cost rates for project budgets.",
    icon: Clock3,
    fields: [
      {
        name: "employee",
        label: "Employee profile ID",
        type: "number",
        required: true,
        min: "1",
      },
      {
        name: "hourly_cost",
        label: "Hourly cost",
        type: "number",
        required: true,
        min: "0",
        step: "0.01",
      },
      { name: "currency", label: "Currency", required: true },
      {
        name: "effective_from",
        label: "Effective from",
        type: "date",
        required: true,
      },
      { name: "effective_to", label: "Effective to", type: "date" },
    ],
    columns: [
      { key: "employee_name", label: "Employee" },
      { key: "hourly_cost", label: "Hourly cost" },
      { key: "currency", label: "Currency" },
      { key: "effective_from", label: "Effective from" },
      { key: "effective_to", label: "Effective to" },
    ],
  },
];

function asRecords(value: Paginated<WorkItem> | WorkItem[]): WorkItem[] {
  return Array.isArray(value) ? value : value.results;
}

function shownValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" || typeof value === "string")
    return value === "" ? "—" : String(value);
  if (value && typeof value === "object" && "name" in value) {
    const name = value.name;
    if (typeof name === "string") return name;
  }
  return "—";
}

function Field({ spec }: { spec: FieldSpec }) {
  const common = {
    id: spec.name,
    name: spec.name,
    required: spec.required,
    min: spec.min,
    step: spec.step,
  };
  return (
    <label className="delivery-field" htmlFor={spec.name}>
      {spec.label}
      {spec.type === "textarea" ? (
        <textarea {...common} rows={3} />
      ) : spec.type === "select" ? (
        <select {...common}>
          <option value="">Select…</option>
          {spec.options?.map((option) => (
            <option value={option} key={option}>
              {option.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      ) : spec.type === "file" ? (
        <input {...common} type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" />
      ) : (
        <input {...common} type={spec.type ?? "text"} />
      )}
    </label>
  );
}

function PanelState({
  loading,
  error,
  empty,
  onRetry,
  children,
}: {
  loading: boolean;
  error: unknown;
  empty: boolean;
  onRetry: () => void;
  children: ReactNode;
}) {
  if (loading)
    return (
      <div className="loading-state" role="status">
        Loading delivery records…
      </div>
    );
  if (error)
    return (
      <div className="error-state" role="alert">
        {error instanceof Error ? error.message : "Could not load records."}{" "}
        <button onClick={onRetry}>Try again</button>
      </div>
    );
  if (empty)
    return (
      <div className="empty-state">
        <span className="empty-icon">
          <BriefcaseBusiness size={20} />
        </span>
        <strong>No records yet</strong>
        <p>Create the first record with the form.</p>
      </div>
    );
  return children;
}

export function ProjectsPage() {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Resource>("projects");
  const [taskView, setTaskView] = useState<"list" | "board">("list");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedProject, setSelectedProject] = useState<Identifier | null>(
    null,
  );
  const [selectedSprint, setSelectedSprint] = useState<Identifier | null>(null);
  const [formValidationError, setFormValidationError] = useState("");
  const [capacityWindow, setCapacityWindow] = useState({
    start: "",
    end: "",
  });
  const spec =
    sections.find((section) => section.id === selected) ?? sections[1];
  const recordsQuery = useQuery({
    queryKey: ["delivery", selected, page, search],
    queryFn: () =>
      apiRequest<Paginated<WorkItem> | WorkItem[]>(
        deliveryApiPath(
          `/${selected}/?page=${page}&page_size=25${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ),
        {},
        accessToken,
      ),
  });
  const projectBudget = useQuery({
    queryKey: ["delivery", "project-budget", selectedProject],
    queryFn: () =>
      apiRequest<WorkItem>(
        deliveryApiPath(`/projects/${selectedProject}/budget-summary/`),
        {},
        accessToken,
      ),
    enabled: selected === "projects" && selectedProject !== null,
  });
  const sprintBacklog = useQuery({
    queryKey: ["delivery", "sprint-backlog", selectedSprint],
    queryFn: () =>
      apiRequest<Paginated<WorkItem> | WorkItem[]>(
        deliveryApiPath(`/sprints/${selectedSprint}/backlog/`),
        {},
        accessToken,
      ),
    enabled: selected === "sprints" && selectedSprint !== null,
  });
  const sprintBurndown = useQuery({
    queryKey: ["delivery", "sprint-burndown", selectedSprint],
    queryFn: () =>
      apiRequest<WorkItem[]>(
        deliveryApiPath(`/sprints/${selectedSprint}/burndown/`),
        {},
        accessToken,
      ),
    enabled: selected === "sprints" && selectedSprint !== null,
  });
  const capacity = useQuery({
    queryKey: [
      "delivery",
      "capacity",
      capacityWindow.start,
      capacityWindow.end,
    ],
    queryFn: () =>
      apiRequest<WorkItem[]>(
        deliveryApiPath(
          `/resource-allocations/capacity/?start_date=${encodeURIComponent(capacityWindow.start)}&end_date=${encodeURIComponent(capacityWindow.end)}`,
        ),
        {},
        accessToken,
      ),
    enabled:
      selected === "resource-allocations" &&
      Boolean(capacityWindow.start && capacityWindow.end),
  });
  const createRecord = useMutation({
    mutationFn: (body: Record<string, unknown> | FormData) =>
      apiRequest<WorkItem>(
        deliveryApiPath(`/${selected}/`),
        {
          method: "POST",
          body: body instanceof FormData ? body : JSON.stringify(body),
        },
        accessToken,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["delivery", selected] });
    },
  });
  const updateStatus = useMutation({
    mutationFn: ({
      id,
      status,
      resource,
    }: {
      id: Identifier;
      status: string;
      resource: Resource;
    }) => {
      const route =
        resource === "tasks"
          ? deliveryApiPath(`/tasks/${encodeURIComponent(String(id))}/status/`)
          : resource === "bugs"
            ? deliveryApiPath(`/bugs/${encodeURIComponent(String(id))}/status/`)
            : deliveryApiPath(
                `/${resource}/${encodeURIComponent(String(id))}/transition/`,
              );
      return apiRequest<WorkItem>(
        route,
        { method: "POST", body: JSON.stringify({ status }) },
        accessToken,
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["delivery", selected] });
    },
  });
  const timeAction = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: Identifier;
      action: "submit" | "approve" | "reject";
    }) =>
      apiRequest<WorkItem>(
        deliveryApiPath(
          `/time-entries/${encodeURIComponent(String(id))}/${action}/`,
        ),
        { method: "POST", body: JSON.stringify({}) },
        accessToken,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["delivery", "time-entries"],
      });
    },
  });
  const submissionAction = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: Identifier;
      action: "approve" | "reject";
    }) =>
      apiRequest<WorkItem>(
        deliveryApiPath(
          `/time-submissions/${encodeURIComponent(String(id))}/${action}/`,
        ),
        { method: "POST", body: JSON.stringify({}) },
        accessToken,
      ),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["delivery", "time-submissions"],
      }),
  });
  const downloadFile = useMutation({
    mutationFn: ({ id, fileName }: { id: Identifier; fileName: string }) =>
      apiDownload(
        deliveryApiPath(`/${selected}/${id}/download/`),
        fileName.split(/[\\/]/).filter(Boolean).pop() || "download",
        accessToken,
      ),
  });

  function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload: Record<string, unknown> = {};
    if (selected === "time-submissions") {
      const start = String(data.get("period_start") ?? "");
      const end = String(data.get("period_end") ?? "");
      const entryIds = String(data.get("entries") ?? "")
        .split(",")
        .map((entry) => Number(entry.trim()))
        .filter((entry) => Number.isInteger(entry) && entry > 0);
      if (!start || !end || end < start || entryIds.length === 0) {
        setFormValidationError(
          "Enter a valid date range and at least one valid time entry ID.",
        );
        return;
      }
    }
    setFormValidationError("");
    for (const field of spec.fields) {
      const raw = data.get(field.name);
      if (raw === null || raw === "") continue;
      if (field.type === "file") {
        const file = form.querySelector<HTMLInputElement>(
          `input[name="${field.name}"]`,
        )?.files?.[0];
        if (file) payload[field.name] = file;
      } else if (field.type === "number") payload[field.name] = Number(raw);
      else if (field.name === "labels")
        payload[field.name] = String(raw)
          .split(",")
          .map((label) => Number(label.trim()))
          .filter((label) => Number.isInteger(label) && label > 0);
      else if (
        ["is_billable", "is_published", "client_visible"].includes(field.name)
      )
        payload[field.name] = raw === "true";
      else if (field.name === "entries")
        payload[field.name] = String(raw)
          .split(",")
          .map((entry) => Number(entry.trim()))
          .filter((entry) => Number.isInteger(entry) && entry > 0);
      else payload[field.name] = String(raw).trim();
    }
    const hasFile = spec.fields.some((field) => field.type === "file");
    const requestBody = hasFile ? new FormData() : null;
    if (requestBody) {
      for (const [key, value] of Object.entries(payload)) {
        if (value instanceof File) requestBody.set(key, value);
        else requestBody.set(key, String(value));
      }
    }
    createRecord.mutate(requestBody ?? payload, {
      onSuccess: () => form.reset(),
    });
  }

  const canApprove = Boolean(
    user?.roles.some((role) => ["Admin", "Manager", "HR"].includes(role)),
  );
  const rows = recordsQuery.data ? asRecords(recordsQuery.data) : [];
  const totalPages =
    recordsQuery.data && !Array.isArray(recordsQuery.data)
      ? Math.max(1, Math.ceil(recordsQuery.data.count / 25))
      : 1;
  const statusOptions: Partial<Record<Resource, readonly string[]>> = {
    projects: ["planned", "active", "on_hold", "completed", "cancelled"],
    milestones: ["planned", "in_progress", "completed", "blocked"],
    sprints: ["planned", "active", "completed", "cancelled"],
    tasks: ["backlog", "ready", "in_progress", "blocked", "done", "cancelled"],
    bugs: [
      "open",
      "triaged",
      "in_progress",
      "fixed",
      "verified",
      "closed",
      "wont_fix",
    ],
  };
  const visibleSections = sections.filter(
    (section) =>
      section.id !== "hourly-costs" ||
      user?.roles.some((role) => ["Admin", "HR", "Finance"].includes(role)),
  );

  function changeSearch(event: ChangeEvent<HTMLInputElement>) {
    setSearch(event.currentTarget.value);
    setPage(1);
  }

  function dropTask(event: DragEvent<HTMLElement>, status: string) {
    event.preventDefault();
    const taskId = event.dataTransfer.getData("text/task-id");
    if (taskId) {
      updateStatus.mutate({ id: taskId, status, resource: "tasks" });
    }
  }

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PROJECT DELIVERY</p>
          <h1>Projects & delivery</h1>
          <p className="muted-text">
            Coordinate clients, delivery plans, team tasks, and approved time.
          </p>
        </div>
      </div>
      <div className="delivery-tabs" role="tablist" aria-label="Delivery areas">
        {visibleSections.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={selected === id}
            className={
              selected === id
                ? "delivery-tab delivery-tab-active"
                : "delivery-tab"
            }
            onClick={() => {
              setSelected(id);
              setPage(1);
            }}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
      <div className="delivery-layout">
        <Card className="delivery-list-card">
          <div className="section-heading delivery-section-heading">
            <div>
              <h2>{spec.label}</h2>
              <p className="muted-text">{spec.description}</p>
            </div>
            {recordsQuery.data && !Array.isArray(recordsQuery.data) && (
              <span className="date-chip">{recordsQuery.data.count} total</span>
            )}
          </div>
          <label className="delivery-search">
            Search {spec.label.toLowerCase()}
            <input
              type="search"
              value={search}
              onChange={changeSearch}
              placeholder={`Search ${spec.label.toLowerCase()}…`}
            />
          </label>
          {selected === "tasks" && (
            <div className="delivery-view-toggle" aria-label="Task view">
              <Button
                type="button"
                size="sm"
                variant={taskView === "board" ? "primary" : "outline"}
                aria-pressed={taskView === "board"}
                onClick={() => setTaskView("board")}
              >
                Board view
              </Button>
              <Button
                type="button"
                size="sm"
                variant={taskView === "list" ? "primary" : "outline"}
                aria-pressed={taskView === "list"}
                onClick={() => setTaskView("list")}
              >
                List view
              </Button>
            </div>
          )}
          <PanelState
            loading={recordsQuery.isLoading}
            error={recordsQuery.error}
            empty={
              !recordsQuery.isLoading &&
              !recordsQuery.error &&
              rows.length === 0
            }
            onRetry={() => void recordsQuery.refetch()}
          >
            {selected === "tasks" && taskView === "board" ? (
              <div className="task-kanban">
                {statusOptions.tasks?.map((status) => {
                  const statusRows = rows.filter(
                    (row) => row.status === status,
                  );
                  return (
                    <section
                      className="task-kanban-column"
                      key={status}
                      aria-label={`${status.replaceAll("_", " ")} tasks`}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => dropTask(event, status)}
                    >
                      <h3>
                        {status.replaceAll("_", " ")}
                        <span>{statusRows.length}</span>
                      </h3>
                      <div className="task-kanban-cards">
                        {statusRows.map((task) => (
                          <article
                            className="task-kanban-card"
                            key={task.id}
                            draggable
                            onDragStart={(event) =>
                              event.dataTransfer.setData(
                                "text/task-id",
                                String(task.id),
                              )
                            }
                          >
                            <strong>{shownValue(task.title)}</strong>
                            <small>{shownValue(task.project_name)}</small>
                            <small>
                              {shownValue(task.assignee_name)} ·{" "}
                              {shownValue(task.priority)}
                            </small>
                          </article>
                        ))}
                        {statusRows.length === 0 && (
                          <p className="task-kanban-empty">Drop a task here</p>
                        )}
                      </div>
                    </section>
                  );
                })}
              </div>
            ) : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      {spec.columns.map((column) => (
                        <th key={column.key}>{column.label}</th>
                      ))}
                      {[
                        "projects",
                        "sprints",
                        "time-entries",
                        "time-submissions",
                        "task-attachments",
                        "documents",
                      ].includes(selected) && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        {spec.columns.map((column) => (
                          <td key={column.key}>
                            {column.key === "status" &&
                            statusOptions[selected] ? (
                              <select
                                aria-label={`Status for ${shownValue(row.title ?? row.name)}`}
                                value={
                                  row.status ?? statusOptions[selected]?.[0]
                                }
                                disabled={updateStatus.isPending}
                                onChange={(event) =>
                                  updateStatus.mutate({
                                    id: row.id,
                                    status: event.target.value,
                                    resource: selected,
                                  })
                                }
                              >
                                {statusOptions[selected]?.map((status) => (
                                  <option value={status} key={status}>
                                    {status.replaceAll("_", " ")}
                                  </option>
                                ))}
                              </select>
                            ) : selected === "projects" &&
                              column.key === "manager_name" ? (
                              shownValue(row.manager_name)
                            ) : (
                              shownValue(row[column.key])
                            )}
                          </td>
                        ))}
                        {[
                          "projects",
                          "sprints",
                          "time-entries",
                          "time-submissions",
                          "task-attachments",
                          "documents",
                        ].includes(selected) && (
                          <td className="delivery-actions">
                            {selected === "projects" && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setSelectedProject(row.id)}
                              >
                                Budget
                              </Button>
                            )}
                            {selected === "sprints" && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setSelectedSprint(row.id)}
                              >
                                Sprint data
                              </Button>
                            )}
                            {selected === "time-entries" &&
                              row.status === "draft" && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={timeAction.isPending}
                                  onClick={() =>
                                    timeAction.mutate({
                                      id: row.id,
                                      action: "submit",
                                    })
                                  }
                                >
                                  Submit
                                </Button>
                              )}
                            {selected === "time-entries" &&
                              canApprove &&
                              row.status === "submitted" && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={timeAction.isPending}
                                    onClick={() =>
                                      timeAction.mutate({
                                        id: row.id,
                                        action: "approve",
                                      })
                                    }
                                  >
                                    <Check size={13} /> Approve
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    disabled={timeAction.isPending}
                                    onClick={() =>
                                      timeAction.mutate({
                                        id: row.id,
                                        action: "reject",
                                      })
                                    }
                                  >
                                    Reject
                                  </Button>
                                </>
                              )}
                            {selected === "time-submissions" &&
                              canApprove &&
                              row.status === "submitted" && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={submissionAction.isPending}
                                    onClick={() =>
                                      submissionAction.mutate({
                                        id: row.id,
                                        action: "approve",
                                      })
                                    }
                                  >
                                    <Check size={13} /> Approve
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    disabled={submissionAction.isPending}
                                    onClick={() =>
                                      submissionAction.mutate({
                                        id: row.id,
                                        action: "reject",
                                      })
                                    }
                                  >
                                    Reject
                                  </Button>
                                </>
                              )}
                            {(selected === "task-attachments" ||
                              selected === "documents") && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={downloadFile.isPending}
                                onClick={() =>
                                  downloadFile.mutate({
                                    id: row.id,
                                    fileName:
                                      row.file_name ?? row.name ?? "download",
                                  })
                                }
                              >
                                <Download size={13} /> Download
                              </Button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {updateStatus.isError && (
              <p className="hr-alert" role="alert">
                {updateStatus.error.message}
              </p>
            )}
            {timeAction.isError && (
              <p className="hr-alert" role="alert">
                {timeAction.error.message}
              </p>
            )}
            {submissionAction.isError && (
              <p className="hr-alert" role="alert">
                {submissionAction.error.message}
              </p>
            )}
            {downloadFile.isError && (
              <p className="hr-alert" role="alert">
                {downloadFile.error.message}
              </p>
            )}
          </PanelState>
          {totalPages > 1 && (
            <div
              className="delivery-pagination"
              aria-label="Delivery pagination"
            >
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1 || recordsQuery.isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span>
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages || recordsQuery.isFetching}
                onClick={() =>
                  setPage((current) => Math.min(totalPages, current + 1))
                }
              >
                Next
              </Button>
            </div>
          )}
        </Card>
        <Card className="delivery-form-card">
          <div className="section-heading">
            <div>
              <h2>
                <CirclePlus size={17} /> Add{" "}
                {spec.label.toLowerCase().replace(/s$/, "")}
              </h2>
              <p className="muted-text">
                Fields marked required must be completed.
              </p>
            </div>
          </div>
          {createRecord.isError && (
            <p className="hr-alert" role="alert">
              {createRecord.error.message}
            </p>
          )}
          {formValidationError && (
            <p className="hr-alert" role="alert">
              {formValidationError}
            </p>
          )}
          <form className="delivery-form" onSubmit={submitForm}>
            {spec.fields.map((field) => (
              <Field key={field.name} spec={field} />
            ))}
            <Button type="submit" disabled={createRecord.isPending}>
              {createRecord.isPending
                ? "Saving…"
                : `Create ${spec.label.replace(/s$/, "")}`}
            </Button>
          </form>
        </Card>
      </div>
      {selected === "projects" && selectedProject !== null && (
        <Card className="delivery-list-card">
          <div className="section-heading delivery-section-heading">
            <div>
              <h2>Project budget summary</h2>
              <p className="muted-text">
                Approved time and actual cost for project {selectedProject}.
              </p>
            </div>
          </div>
          <PanelState
            loading={projectBudget.isLoading}
            error={projectBudget.error}
            empty={
              !projectBudget.isLoading &&
              !projectBudget.error &&
              !projectBudget.data
            }
            onRetry={() => void projectBudget.refetch()}
          >
            <div className="delivery-summary-grid">
              {[
                [
                  "Budget",
                  `${projectBudget.data?.currency ?? ""} ${projectBudget.data?.budget ?? ""}`,
                ],
                [
                  "Actual cost",
                  `${projectBudget.data?.currency ?? ""} ${projectBudget.data?.actual_cost ?? ""}`,
                ],
                [
                  "Remaining budget",
                  `${projectBudget.data?.currency ?? ""} ${projectBudget.data?.remaining_budget ?? ""}`,
                ],
                ["Approved hours", projectBudget.data?.approved_hours],
                ["Billable hours", projectBudget.data?.billable_hours],
                ["Unpriced hours", projectBudget.data?.unpriced_approved_hours],
              ].map(([label, value]) => (
                <div className="delivery-summary-item" key={label}>
                  <span>{label}</span>
                  <strong>{shownValue(value)}</strong>
                </div>
              ))}
            </div>
          </PanelState>
        </Card>
      )}
      {selected === "sprints" && selectedSprint !== null && (
        <div className="delivery-layout">
          <Card className="delivery-list-card">
            <div className="section-heading delivery-section-heading">
              <div>
                <h2>Sprint backlog</h2>
                <p className="muted-text">Tasks in sprint {selectedSprint}.</p>
              </div>
            </div>
            <PanelState
              loading={sprintBacklog.isLoading}
              error={sprintBacklog.error}
              empty={
                !sprintBacklog.isLoading &&
                !sprintBacklog.error &&
                (sprintBacklog.data
                  ? asRecords(sprintBacklog.data).length === 0
                  : true)
              }
              onRetry={() => void sprintBacklog.refetch()}
            >
              <ul className="delivery-detail-list">
                {sprintBacklog.data &&
                  asRecords(sprintBacklog.data).map((task) => (
                    <li key={task.id}>
                      <strong>{shownValue(task.title)}</strong>
                      <span>
                        {shownValue(task.status)} ·{" "}
                        {shownValue(task.estimate_hours)} h
                      </span>
                    </li>
                  ))}
              </ul>
            </PanelState>
          </Card>
          <Card className="delivery-list-card">
            <div className="section-heading delivery-section-heading">
              <div>
                <h2>Sprint burndown</h2>
                <p className="muted-text">Remaining estimated effort by day.</p>
              </div>
            </div>
            <PanelState
              loading={sprintBurndown.isLoading}
              error={sprintBurndown.error}
              empty={
                !sprintBurndown.isLoading &&
                !sprintBurndown.error &&
                (sprintBurndown.data?.length ?? 0) === 0
              }
              onRetry={() => void sprintBurndown.refetch()}
            >
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Remaining estimate (h)</th>
                      <th>Completed estimate (h)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sprintBurndown.data?.map((point, index) => (
                      <tr key={`${point.date ?? "point"}-${index}`}>
                        <td>{shownValue(point.date)}</td>
                        <td>{shownValue(point.remaining_estimate_hours)}</td>
                        <td>{shownValue(point.completed_estimate_hours)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </PanelState>
          </Card>
        </div>
      )}
      {selected === "resource-allocations" && (
        <Card className="delivery-list-card">
          <div className="section-heading delivery-section-heading">
            <div>
              <h2>Team capacity</h2>
              <p className="muted-text">
                Review weekday allocation by employee for up to 90 days.
              </p>
            </div>
          </div>
          <div className="delivery-capacity-filter">
            <label className="delivery-field">
              Start date
              <input
                type="date"
                value={capacityWindow.start}
                onChange={(event) =>
                  setCapacityWindow((value) => ({
                    ...value,
                    start: event.target.value,
                  }))
                }
              />
            </label>
            <label className="delivery-field">
              End date
              <input
                type="date"
                value={capacityWindow.end}
                onChange={(event) =>
                  setCapacityWindow((value) => ({
                    ...value,
                    end: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          {capacityWindow.start && capacityWindow.end ? (
            <PanelState
              loading={capacity.isLoading}
              error={capacity.error}
              empty={
                !capacity.isLoading &&
                !capacity.error &&
                (capacity.data?.length ?? 0) === 0
              }
              onRetry={() => void capacity.refetch()}
            >
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Date</th>
                      <th>Allocation</th>
                      <th>Capacity (h)</th>
                      <th>Overallocated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {capacity.data?.map((row, index) => (
                      <tr
                        key={`${row.employee_id ?? row.employee_number}-${row.date ?? index}`}
                      >
                        <td>{shownValue(row.employee_name)}</td>
                        <td>{shownValue(row.date)}</td>
                        <td>{shownValue(row.allocation_percent)}%</td>
                        <td>{shownValue(row.capacity_hours)}</td>
                        <td>{shownValue(row.overallocated)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </PanelState>
          ) : (
            <p className="muted-text">
              Choose a start and end date to load team capacity.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}

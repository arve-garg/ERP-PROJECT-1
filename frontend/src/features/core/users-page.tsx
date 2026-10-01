import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileUp, Plus, Search, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { apiDownload, apiRequest } from "../../lib/api";
import type { Paginated } from "../../lib/types";

interface UserRecord {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  roles: string[];
  date_joined: string;
  approval_status: "pending" | "approved" | "rejected";
  employee_number?: string | null;
  department_name?: string | null;
  designation_title?: string | null;
  phone?: string | null;
}

interface RoleRecord {
  id: number;
  name: string;
  description: string;
}

const createSchema = z.object({
  email: z.string().email("Enter a valid email."),
  first_name: z.string().trim().min(1, "Enter a first name."),
  last_name: z.string().trim().min(1, "Enter a last name."),
  password: z.string().min(12, "Use at least 12 characters."),
  roles: z.array(z.string()),
});
type CreateValues = z.infer<typeof createSchema>;

export function UsersPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState("");
  const [importError, setImportError] = useState("");
  const users = useQuery({
    queryKey: ["users", search],
    queryFn: () =>
      apiRequest<Paginated<UserRecord>>(
        `/users/?page_size=100${search.trim() ? `&search=${encodeURIComponent(search.trim())}` : ""}`,
        {},
        accessToken,
      ),
  });
  const pendingUsers = useQuery({
    queryKey: ["users", "pending"],
    queryFn: () =>
      apiRequest<Paginated<UserRecord>>(
        "/users/?page_size=100&approval_status=pending",
        {},
        accessToken,
      ),
  });
  const approval = useMutation({
    mutationFn: ({ userId, action }: { userId: number; action: "approve" | "reject" }) =>
      apiRequest<UserRecord>(
        `/users/${userId}/${action}/`,
        { method: "POST" },
        accessToken,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () =>
      apiRequest<Paginated<RoleRecord>>(
        "/roles/?page_size=100",
        {},
        accessToken,
      ),
  });
  const createForm = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      email: "",
      first_name: "",
      last_name: "",
      password: "",
      roles: [],
    },
  });
  const createUser = useMutation({
    mutationFn: (values: CreateValues) =>
      apiRequest<UserRecord>(
        "/users/",
        { method: "POST", body: JSON.stringify(values) },
        accessToken,
      ),
    onSuccess: async () => {
      setCreateError("");
      createForm.reset();
      setShowCreate(false);
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) =>
      setCreateError(
        error instanceof Error ? error.message : "Unable to create user.",
      ),
  });
  const assignRoles = useMutation({
    mutationFn: ({ userId, values }: { userId: number; values: string[] }) =>
      apiRequest(
        `/users/${userId}/roles/`,
        { method: "PUT", body: JSON.stringify({ roles: values }) },
        accessToken,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
  const importUsers = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.set("file", file);
      return apiRequest<{ created: number }>(
        "/users/import/",
        { method: "POST", body: formData },
        accessToken,
      );
    },
    onSuccess: async (result) => {
      setImportError(
        `${result.created} user${result.created === 1 ? "" : "s"} imported.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) =>
      setImportError(error instanceof Error ? error.message : "Import failed."),
  });
  const exportUsers = useMutation({
    mutationFn: (format: "csv" | "xlsx") =>
      apiDownload(
        `/users/export/?file_format=${format}`,
        format === "csv" ? "deverp-users.csv" : "deverp-users.xlsx",
        accessToken,
      ),
    onError: (error) =>
      setImportError(error instanceof Error ? error.message : "Export failed."),
  });
  const roleNames = useMemo(
    () => roles.data?.results.map((role) => role.name) ?? [],
    [roles.data],
  );

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1>Users & roles</h1>
          <p className="muted-text">
            Manage workspace accounts and their access.
          </p>
        </div>
        <div className="page-heading-actions">
          <Button
            variant="outline"
            size="sm"
            disabled={exportUsers.isPending}
            onClick={() => exportUsers.mutate("csv")}
          >
            <Download size={15} /> Export CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={exportUsers.isPending}
            onClick={() => exportUsers.mutate("xlsx")}
          >
            <Download size={15} /> Export Excel
          </Button>
          <label className="import-label" htmlFor="user-import">
            <FileUp size={15} />
            {importUsers.isPending ? "Importing…" : "Import users"}
            <input
              id="user-import"
              type="file"
              accept=".csv,.xlsx"
              disabled={importUsers.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  setImportError("");
                  importUsers.mutate(file);
                }
                event.target.value = "";
              }}
            />
          </label>
          <Button size="sm" onClick={() => setShowCreate((show) => !show)}>
            <Plus size={15} /> Add user
          </Button>
        </div>
      </div>
      <Card className="list-card">
        <div className="section-heading">
          <div>
            <h2>Pending access requests</h2>
            <p className="muted-text">Review new employee registrations before activating workspace access.</p>
          </div>
          <span className="result-count">{pendingUsers.data?.count ?? 0} pending</span>
        </div>
        {pendingUsers.isPending && <div className="loading-state">Loading requests…</div>}
        {pendingUsers.isError && <div className="error-state">Requests could not be loaded.</div>}
        {pendingUsers.isSuccess && pendingUsers.data.results.length === 0 && (
          <div className="empty-state"><strong>No pending requests</strong><p>New registrations will appear here.</p></div>
        )}
        {pendingUsers.isSuccess && pendingUsers.data.results.length > 0 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Employee</th><th>Department</th><th>Designation</th><th>Actions</th></tr></thead>
              <tbody>
                {pendingUsers.data.results.map((pendingUser) => (
                  <tr key={pendingUser.id}>
                    <td><strong>{pendingUser.first_name} {pendingUser.last_name}</strong><small>{pendingUser.email} · {pendingUser.employee_number}</small></td>
                    <td>{pendingUser.department_name || "—"}</td>
                    <td>{pendingUser.designation_title || "—"}</td>
                    <td>
                      <div className="form-actions">
                        <Button size="sm" disabled={approval.isPending} onClick={() => approval.mutate({ userId: pendingUser.id, action: "approve" })}>Approve</Button>
                        <Button size="sm" variant="ghost" disabled={approval.isPending} onClick={() => approval.mutate({ userId: pendingUser.id, action: "reject" })}>Reject</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {importError && (
        <p
          className={importUsers.isError ? "form-error" : "success-message"}
          role={importUsers.isError ? "alert" : "status"}
        >
          {importError}
        </p>
      )}
      {showCreate && (
        <Card className="form-card">
          <div className="section-heading">
            <div>
              <h2>Create a user</h2>
              <p className="muted-text">
                The user can sign in immediately with this password.
              </p>
            </div>
          </div>
          <form
            className="user-create-form"
            onSubmit={createForm.handleSubmit((values) =>
              createUser.mutate(values),
            )}
            noValidate
          >
            <div className="form-field">
              <label htmlFor="new-user-email">Work email</label>
              <input
                id="new-user-email"
                type="email"
                autoComplete="email"
                {...createForm.register("email")}
              />
              {createForm.formState.errors.email && (
                <small className="field-error">
                  {createForm.formState.errors.email.message}
                </small>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="new-user-first">First name</label>
              <input
                id="new-user-first"
                {...createForm.register("first_name")}
              />
              {createForm.formState.errors.first_name && (
                <small className="field-error">
                  {createForm.formState.errors.first_name.message}
                </small>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="new-user-last">Last name</label>
              <input id="new-user-last" {...createForm.register("last_name")} />
              {createForm.formState.errors.last_name && (
                <small className="field-error">
                  {createForm.formState.errors.last_name.message}
                </small>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="new-user-password">Temporary password</label>
              <input
                id="new-user-password"
                type="password"
                autoComplete="new-password"
                {...createForm.register("password")}
              />
              {createForm.formState.errors.password && (
                <small className="field-error">
                  {createForm.formState.errors.password.message}
                </small>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="new-user-roles">Initial roles</label>
              <select
                id="new-user-roles"
                multiple
                size={Math.min(Math.max(roleNames.length, 2), 5)}
                {...createForm.register("roles")}
              >
                {roleNames.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              <small className="muted-text">
                Use Ctrl or Command to select multiple roles.
              </small>
            </div>
            {createError && (
              <p className="form-error" role="alert">
                {createError}
              </p>
            )}
            <div className="form-actions">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createUser.isPending}>
                {createUser.isPending ? "Creating…" : "Create user"}
              </Button>
            </div>
          </form>
        </Card>
      )}
      <Card className="list-card user-list-card">
        <div className="list-toolbar">
          <label className="search-input">
            <Search size={16} />
            <input
              aria-label="Search users"
              placeholder="Search names and email"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <span className="result-count">
            {users.data?.count ?? "—"} accounts
          </span>
        </div>
        {users.isPending && (
          <div className="loading-state" role="status">
            Loading users…
          </div>
        )}
        {users.isError && (
          <div className="error-state" role="alert">
            Users could not be loaded.{" "}
            <button onClick={() => void users.refetch()}>Try again</button>
          </div>
        )}
        {users.isSuccess && users.data.results.length === 0 && (
          <div className="empty-state">
            <span className="empty-icon">
              <Users size={20} />
            </span>
            <strong>No users found</strong>
            <p>Try another search or add a new workspace account.</p>
          </div>
        )}
        {users.isSuccess && users.data.results.length > 0 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Department</th>
                  <th>Roles</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.data.results.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    roleNames={roleNames}
                    saving={assignRoles.isPending}
                    onSave={(values) =>
                      assignRoles.mutate({ userId: user.id, values })
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(roles.isError || assignRoles.isError) && (
          <p role="alert" className="form-error">
            Role data could not be loaded or updated. Retry the request.
          </p>
        )}
      </Card>
    </div>
  );
}

function UserRow({
  user,
  roleNames,
  saving,
  onSave,
}: {
  user: UserRecord;
  roleNames: string[];
  saving: boolean;
  onSave: (values: string[]) => void;
}) {
  const [selected, setSelected] = useState(user.roles);
  const changed =
    selected.length !== user.roles.length ||
    selected.some((role) => !user.roles.includes(role));
  return (
    <tr>
      <td>
        <strong>
          {user.first_name} {user.last_name}
        </strong>
      </td>
      <td>{user.email}</td>
      <td>
        <div className="role-editor">
          <select
            aria-label={`Roles for ${user.email}`}
            multiple
            size={Math.min(Math.max(roleNames.length, 2), 4)}
            value={selected}
            onChange={(event) =>
              setSelected(
                Array.from(
                  event.currentTarget.selectedOptions,
                  (option) => option.value,
                ),
              )
            }
          >
            {roleNames.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          {changed && (
            <Button
              size="sm"
              disabled={saving}
              onClick={() => onSave(selected)}
            >
              Save
            </Button>
          )}
        </div>
      </td>
      <td>
        <span
          className={`status-chip ${user.approval_status === "approved" && user.is_active ? "status-active" : "status-inactive"}`}
        >
          {user.approval_status === "pending"
            ? "Pending approval"
            : user.approval_status === "rejected"
              ? "Rejected"
              : user.is_active
                ? "Active"
                : "Inactive"}
        </span>
      </td>
    </tr>
  );
}

import { CheckCircle2, Clock3, LogOut, XCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";

export function ApplicationStatusPage() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const pending = user?.approval_status === "pending";
  const rejected = user?.approval_status === "rejected";

  async function signOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="application-status-title">
        <div className="brand-mark">
          {pending ? <Clock3 size={22} /> : rejected ? <XCircle size={22} /> : <CheckCircle2 size={22} />}
        </div>
        <p className="eyebrow">DEV SERVICES ERP</p>
        <h1 id="application-status-title">
          {pending ? "Application under review" : "Access not approved"}
        </h1>
        <p className="muted-text">
          {pending
            ? "Your employee details have been submitted successfully."
            : "Your workspace access request was not approved."}
        </p>

        <div className="status-card">
          <strong>
            {pending
              ? "Please wait for administrator approval."
              : "Please contact your administrator for more information."}
          </strong>
          {pending && (
            <p className="muted-text">
              Once your application is approved, your department workspace and role-based modules will become available automatically.
            </p>
          )}
        </div>

        {user?.department_name && (
          <div className="status-details">
            <span>Department</span><strong>{user.department_name}</strong>
            <span>Designation</span><strong>{user.designation_title || "—"}</strong>
            <span>Employee code</span><strong>{user.employee_number || "—"}</strong>
          </div>
        )}

        {pending && (
          <Button type="button" onClick={() => void refreshUser().then(() => {
            if (sessionStorage.getItem("deverp.user")?.includes('"approval_status":"approved"')) {
              navigate("/", { replace: true });
            }
          })}>
            Check approval status
          </Button>
        )}
        <Button type="button" variant="ghost" onClick={() => void signOut()}>
          <LogOut size={16} /> Sign out
        </Button>
      </section>
      <p className="login-caption">Your account status is controlled by your administrator</p>
    </main>
  );
}

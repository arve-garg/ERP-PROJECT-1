import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setSaving(true);
    try {
      const result = await apiRequest<{ detail: string }>(
        "/auth/password/reset/confirm/",
        {
          method: "POST",
          body: JSON.stringify({
            uid: params.get("uid"),
            token: params.get("token"),
            new_password: password,
          }),
        },
      );
      setMessage(result.detail);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to reset password.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-card">
        <p className="eyebrow">ACCOUNT RECOVERY</p>
        <h1>Choose a new password</h1>
        <form onSubmit={submit}>
          <label htmlFor="password">New password</label>
          <input
            id="password"
            type="password"
            minLength={12}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <label htmlFor="confirmation">Confirm password</label>
          <input
            id="confirmation"
            type="password"
            required
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
          {message && (
            <p role="status" className="success-message">
              {message}
            </p>
          )}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <Button type="submit" disabled={saving} className="submit-button">
            {saving ? "Updating…" : "Update password"}
          </Button>
        </form>
        <div className="login-foot">
          <Link to="/login">Back to sign in</Link>
        </div>
      </section>
    </main>
  );
}

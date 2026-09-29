import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { apiRequest } from "../../lib/api";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSending(true);
    setError("");
    try {
      const result = await apiRequest<{ detail: string }>(
        "/auth/password/reset/",
        {
          method: "POST",
          body: JSON.stringify({ email }),
        },
      );
      setMessage(result.detail);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to submit the request.",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-card">
        <p className="eyebrow">ACCOUNT RECOVERY</p>
        <h1>Reset your password</h1>
        <p className="muted-text">
          Enter your work email and we’ll send a reset link if an account
          exists.
        </p>
        <form onSubmit={submit}>
          <label htmlFor="email">Work email</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
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
          <Button type="submit" disabled={sending} className="submit-button">
            {sending ? "Sending…" : "Send reset link"}
          </Button>
        </form>
        <div className="login-foot">
          <Link to="/login">Back to sign in</Link>
        </div>
      </section>
    </main>
  );
}

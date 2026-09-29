import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck, ShieldOff } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../app/auth-context";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { apiRequest } from "../../lib/api";

interface Profile {
  totp_required: boolean;
}

interface TOTPSetup {
  secret: string;
  provisioning_uri: string;
}

export function SecurityPage() {
  const { accessToken } = useAuth();
  const client = useQueryClient();
  const [setup, setSetup] = useState<TOTPSetup | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const profile = useQuery({
    queryKey: ["profile-security"],
    queryFn: () => apiRequest<Profile>("/users/me/", {}, accessToken),
  });
  const setupMutation = useMutation({
    mutationFn: () =>
      apiRequest<TOTPSetup>(
        "/auth/2fa/setup/",
        { method: "POST" },
        accessToken,
      ),
    onSuccess: (result) => {
      setSetup(result);
      setError("");
    },
    onError: (reason) =>
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not start two-factor setup.",
      ),
  });
  const confirmMutation = useMutation({
    mutationFn: () =>
      apiRequest(
        "/auth/2fa/confirm/",
        { method: "POST", body: JSON.stringify({ code }) },
        accessToken,
      ),
    onSuccess: async () => {
      setSetup(null);
      setCode("");
      setError("");
      await client.invalidateQueries({ queryKey: ["profile-security"] });
    },
    onError: (reason) =>
      setError(
        reason instanceof Error
          ? reason.message
          : "The authenticator code was not accepted.",
      ),
  });
  const disableMutation = useMutation({
    mutationFn: () =>
      apiRequest(
        "/auth/2fa/disable/",
        { method: "POST", body: JSON.stringify({ code }) },
        accessToken,
      ),
    onSuccess: async () => {
      setCode("");
      setError("");
      await client.invalidateQueries({ queryKey: ["profile-security"] });
    },
    onError: (reason) =>
      setError(
        reason instanceof Error
          ? reason.message
          : "The authenticator code was not accepted.",
      ),
  });
  const enabled = profile.data?.totp_required ?? false;
  const submitting = confirmMutation.isPending || disableMutation.isPending;

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ACCOUNT SECURITY</p>
          <h1>Sign-in security</h1>
          <p className="muted-text">
            Protect your DevERP account with an authenticator app.
          </p>
        </div>
      </div>
      <Card className="security-card">
        {profile.isPending && (
          <div className="loading-state" role="status">
            Loading security settings…
          </div>
        )}
        {profile.isError && (
          <div className="error-state" role="alert">
            Security settings could not be loaded.{" "}
            <button onClick={() => void profile.refetch()}>Try again</button>
          </div>
        )}
        {profile.isSuccess && (
          <>
            <div className="security-status">
              <span
                className={`security-icon ${enabled ? "security-enabled" : ""}`}
              >
                {enabled ? <ShieldCheck size={22} /> : <ShieldOff size={22} />}
              </span>
              <div>
                <strong>
                  Two-factor authentication is {enabled ? "on" : "off"}
                </strong>
                <p>
                  {enabled
                    ? "An authenticator code is required each time you sign in."
                    : "Add a second verification step to protect your account."}
                </p>
              </div>
            </div>
            {!enabled && !setup && (
              <Button
                disabled={setupMutation.isPending}
                onClick={() => setupMutation.mutate()}
              >
                <KeyRound size={16} />{" "}
                {setupMutation.isPending
                  ? "Preparing…"
                  : "Set up authenticator"}
              </Button>
            )}
            {setup && (
              <>
                <div className="setup-instructions">
                  <h2>Connect your authenticator</h2>
                  <p>
                    In your authenticator app, add a time-based account using
                    this secret key:
                  </p>
                  <code>{setup.secret}</code>
                  <details>
                    <summary>Manual setup details</summary>
                    <a href={setup.provisioning_uri}>
                      Open authenticator setup link
                    </a>
                    <p>{setup.provisioning_uri}</p>
                  </details>
                  <p>
                    Enter the current six-digit code from the app to finish
                    enabling two-factor authentication.
                  </p>
                </div>
                <label className="code-label" htmlFor="totp-code">
                  Authenticator code
                </label>
                <input
                  id="totp-code"
                  className="code-input"
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(event) =>
                    setCode(event.target.value.replace(/\D/g, ""))
                  }
                />
                <div className="form-actions">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setSetup(null);
                      setCode("");
                      setError("");
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    disabled={submitting || code.length !== 6}
                    onClick={() => confirmMutation.mutate()}
                  >
                    {confirmMutation.isPending
                      ? "Verifying…"
                      : "Enable two-factor"}
                  </Button>
                </div>
              </>
            )}
            {enabled && (
              <>
                <label className="code-label" htmlFor="totp-code">
                  Authenticator code to disable
                </label>
                <input
                  id="totp-code"
                  className="code-input"
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(event) =>
                    setCode(event.target.value.replace(/\D/g, ""))
                  }
                />
                <Button
                  variant="outline"
                  disabled={submitting || code.length !== 6}
                  onClick={() => disableMutation.mutate()}
                >
                  {disableMutation.isPending
                    ? "Verifying…"
                    : "Disable two-factor"}
                </Button>
              </>
            )}
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

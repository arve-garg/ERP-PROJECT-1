import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../../app/auth-context";
import { ApiRequestError } from "../../lib/api";
import { Button } from "../../components/ui/button";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [otpCode, setOtpCode] = useState("");
  const [requiresOtp, setRequiresOtp] = useState(false);
  const [serverError, setServerError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (user) return <Navigate to="/" replace />;

  const submit = handleSubmit(async ({ email, password }) => {
    setServerError("");
    try {
      await login(email, password, otpCode);
      navigate("/", { replace: true });
    } catch (error) {
      if (error instanceof ApiRequestError && error.data.otp_code)
        setRequiresOtp(true);
      setServerError(
        error instanceof Error
          ? error.message
          : "Unable to sign in. Please try again.",
      );
    }
  });

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand-mark">
          <Building2 size={22} aria-hidden="true" />
        </div>
        <p className="eyebrow">DEV SERVICES ERP</p>
        <h1 id="login-title">Welcome back</h1>
        <p className="muted-text">Sign in to continue to your workspace.</p>
        {typeof location.state?.message === "string" && (
          <p className="form-error" role="alert">
            {location.state.message}
          </p>
        )}
        <form onSubmit={submit} noValidate>
          <label htmlFor="email">Work email</label>
          <input
            id="email"
            autoComplete="username"
            type="email"
            {...register("email")}
          />
          {errors.email && (
            <span className="field-error">{errors.email.message}</span>
          )}
          <label htmlFor="password">Password</label>
          <input
            id="password"
            autoComplete="current-password"
            type="password"
            {...register("password")}
          />
          {errors.password && (
            <span className="field-error">{errors.password.message}</span>
          )}
          {requiresOtp && (
            <>
              <label htmlFor="otp">Authenticator code</label>
              <input
                id="otp"
                autoComplete="one-time-code"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(event) =>
                  setOtpCode(event.target.value.replace(/\D/g, ""))
                }
              />
            </>
          )}
          {serverError && (
            <p className="form-error" role="alert">
              {serverError}
            </p>
          )}
          <Button
            type="submit"
            disabled={isSubmitting}
            className="submit-button"
          >
            <LockKeyhole size={16} aria-hidden="true" />
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <div className="login-foot">
          <Link to="/forgot-password">Forgot password?</Link>
          <span> · </span>
          <Link to="/register">Create account</Link>
        </div>
      </section>
      <p className="login-caption">Secure access to your company workspace</p>
    </main>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, UserPlus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { apiRequest, ApiRequestError } from "../../lib/api";
import { Button } from "../../components/ui/button";

const schema = z.object({
  first_name: z.string().trim().min(1, "Enter your first name."),
  last_name: z.string().trim().optional(),
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(12, "Password must be at least 12 characters."),
  password_confirm: z.string().min(12, "Please confirm your password."),
}).refine((data) => data.password === data.password_confirm, {
  message: "Passwords do not match.",
  path: ["password_confirm"],
});

type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const submit = handleSubmit(async (values) => {
    setServerError("");
    try {
      await apiRequest("/auth/register/", {
        method: "POST",
        body: JSON.stringify(values),
      });
      navigate("/login", {
        replace: true,
        state: { message: "Account created successfully. You can now sign in." },
      });
    } catch (error) {
      if (error instanceof ApiRequestError && error.data) {
        const data = error.data as Record<string, unknown>;
        const first = Object.values(data).flatMap((v) => Array.isArray(v) ? v : [v]).find((v) => typeof v === "string");
        setServerError(typeof first === "string" ? first : error.message);
      } else {
        setServerError(error instanceof Error ? error.message : "Unable to create account.");
      }
    }
  });

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="register-title">
        <div className="brand-mark"><Building2 size={22} aria-hidden="true" /></div>
        <p className="eyebrow">DEV SERVICES ERP</p>
        <h1 id="register-title">Create your account</h1>
        <p className="muted-text">Sign up to access your workspace.</p>
        <form onSubmit={submit} noValidate>
          <label htmlFor="first_name">First name</label>
          <input id="first_name" autoComplete="given-name" {...register("first_name")} />
          {errors.first_name && <span className="field-error">{errors.first_name.message}</span>}

          <label htmlFor="last_name">Last name</label>
          <input id="last_name" autoComplete="family-name" {...register("last_name")} />

          <label htmlFor="email">Work email</label>
          <input id="email" autoComplete="email" type="email" {...register("email")} />
          {errors.email && <span className="field-error">{errors.email.message}</span>}

          <label htmlFor="password">Password</label>
          <input id="password" autoComplete="new-password" type="password" {...register("password")} />
          {errors.password && <span className="field-error">{errors.password.message}</span>}

          <label htmlFor="password_confirm">Confirm password</label>
          <input id="password_confirm" autoComplete="new-password" type="password" {...register("password_confirm")} />
          {errors.password_confirm && <span className="field-error">{errors.password_confirm.message}</span>}

          {serverError && <p className="form-error" role="alert">{serverError}</p>}

          <Button type="submit" disabled={isSubmitting} className="submit-button">
            <UserPlus size={16} aria-hidden="true" />
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        </form>
        <div className="login-foot">
          <span>Already have an account? </span><Link to="/login">Sign in</Link>
        </div>
      </section>
      <p className="login-caption">Secure access to your company workspace</p>
    </main>
  );
}

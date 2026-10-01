import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, UserPlus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { apiRequest, ApiRequestError } from "../../lib/api";
import { Button } from "../../components/ui/button";

interface DepartmentOption {
  id: number;
  name: string;
  code: string;
}

interface DesignationOption {
  id: number;
  title: string;
  department_id: number;
}

interface RegistrationOptions {
  departments: DepartmentOption[];
  designations: DesignationOption[];
}

const schema = z.object({
  first_name: z.string().trim().min(1, "Enter your first name."),
  last_name: z.string().trim().optional(),
  email: z.string().email("Enter a valid email address."),
  employee_number: z.string().trim().min(1, "Enter your employee code."),
  department: z.coerce.number().int().positive("Select a department."),
  designation: z.coerce.number().int().positive("Select a designation."),
  phone: z.string().trim().optional(),
  password: z.string().min(12, "Password must be at least 12 characters."),
  password_confirm: z.string().min(12, "Please confirm your password."),
}).refine((data) => data.password === data.password_confirm, {
  message: "Passwords do not match.",
  path: ["password_confirm"],
});

type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<RegistrationOptions | null>(null);
  const [optionsError, setOptionsError] = useState("");
  const [serverError, setServerError] = useState("");
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) });
  const departmentId = watch("department");

  useEffect(() => {
    apiRequest<RegistrationOptions>("/auth/registration-options/")
      .then(setOptions)
      .catch((error) => setOptionsError(error instanceof Error ? error.message : "Unable to load departments."));
  }, []);

  const designations = useMemo(
    () => options?.designations.filter((item) => item.department_id === Number(departmentId)) ?? [],
    [options, departmentId],
  );

  const submit = handleSubmit(async (values) => {
    setServerError("");
    try {
      await apiRequest("/auth/register/", {
        method: "POST",
        body: JSON.stringify(values),
      });
      navigate("/login", {
        replace: true,
        state: { message: "Application submitted. You can sign in to check your approval status." },
      });
    } catch (error) {
      if (error instanceof ApiRequestError && error.data) {
        const data = error.data as Record<string, unknown>;
        const first = Object.values(data)
          .flatMap((value) => Array.isArray(value) ? value : [value])
          .find((value) => typeof value === "string");
        setServerError(typeof first === "string" ? first : error.message);
      } else {
        setServerError(error instanceof Error ? error.message : "Unable to submit application.");
      }
    }
  });

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="register-title">
        <div className="brand-mark"><Building2 size={22} aria-hidden="true" /></div>
        <p className="eyebrow">DEV SERVICES ERP</p>
        <h1 id="register-title">Request workspace access</h1>
        <p className="muted-text">Submit your employee details. An administrator will review your application.</p>

        {optionsError && <p className="form-error" role="alert">{optionsError}</p>}

        <form onSubmit={submit} noValidate>
          <label htmlFor="first_name">First name</label>
          <input id="first_name" autoComplete="given-name" {...register("first_name")} />
          {errors.first_name && <span className="field-error">{errors.first_name.message}</span>}

          <label htmlFor="last_name">Last name</label>
          <input id="last_name" autoComplete="family-name" {...register("last_name")} />

          <label htmlFor="email">Work email</label>
          <input id="email" autoComplete="email" type="email" {...register("email")} />
          {errors.email && <span className="field-error">{errors.email.message}</span>}

          <label htmlFor="employee_number">Employee code</label>
          <input id="employee_number" autoComplete="off" {...register("employee_number")} />
          {errors.employee_number && <span className="field-error">{errors.employee_number.message}</span>}

          <label htmlFor="department">Department</label>
          <select id="department" {...register("department")}>
            <option value="">Select department</option>
            {options?.departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name} ({department.code})
              </option>
            ))}
          </select>
          {errors.department && <span className="field-error">{errors.department.message}</span>}

          <label htmlFor="designation">Designation</label>
          <select id="designation" {...register("designation")} disabled={!departmentId}>
            <option value="">Select designation</option>
            {designations.map((designation) => (
              <option key={designation.id} value={designation.id}>{designation.title}</option>
            ))}
          </select>
          {errors.designation && <span className="field-error">{errors.designation.message}</span>}

          <label htmlFor="phone">Phone</label>
          <input id="phone" autoComplete="tel" {...register("phone")} />

          <label htmlFor="password">Password</label>
          <input id="password" autoComplete="new-password" type="password" {...register("password")} />
          {errors.password && <span className="field-error">{errors.password.message}</span>}

          <label htmlFor="password_confirm">Confirm password</label>
          <input id="password_confirm" autoComplete="new-password" type="password" {...register("password_confirm")} />
          {errors.password_confirm && <span className="field-error">{errors.password_confirm.message}</span>}

          {serverError && <p className="form-error" role="alert">{serverError}</p>}

          <Button type="submit" disabled={isSubmitting || !options} className="submit-button">
            <UserPlus size={16} aria-hidden="true" />
            {isSubmitting ? "Submitting…" : "Submit application"}
          </Button>
        </form>

        <div className="login-foot">
          <span>Already have an account? </span><Link to="/login">Sign in</Link>
        </div>
      </section>
      <p className="login-caption">Access is activated after administrator approval</p>
    </main>
  );
}

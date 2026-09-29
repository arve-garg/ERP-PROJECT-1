import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "../../lib/api";
import { LoginPage } from "./login-page";

const loginMock = vi.fn();

vi.mock("../../app/auth-context", () => ({
  useAuth: () => ({ user: null, login: loginMock }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    loginMock.mockReset();
  });

  it("validates email and password before sending", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(
      await screen.findByText("Enter a valid email address."),
    ).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("offers an OTP field when the server requires two-factor verification", async () => {
    loginMock.mockRejectedValueOnce(
      new ApiRequestError("A valid code is required.", 400, {
        otp_code: ["required"],
      }),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Work email"), {
      target: { value: "employee@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "correct-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Authenticator code")).toBeInTheDocument(),
    );
  });
});

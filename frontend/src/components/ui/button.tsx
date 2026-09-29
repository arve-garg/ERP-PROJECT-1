import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline";
  size?: "default" | "sm";
};

export function Button({
  variant = "primary",
  size = "default",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`button button-${variant} button-${size} ${className}`}
      {...props}
    />
  );
}

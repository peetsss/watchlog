import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";

type Variant = "primary" | "secondary" | "ghost" | "quiet" | "danger";
type Size = "sm" | "md" | "lg";

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}) {
  return (
    <button className={cx("btn", `btn-${variant}`, `btn-${size}`, className)} {...props}>
      {children}
    </button>
  );
}

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra?: string) {
  return cx("btn", `btn-${variant}`, `btn-${size}`, extra);
}

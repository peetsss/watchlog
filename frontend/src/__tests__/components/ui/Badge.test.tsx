import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge from "@/components/ui/Badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Sci-Fi</Badge>);
    expect(screen.getByText("Sci-Fi")).toBeInTheDocument();
  });

  it("renders with data-testid", () => {
    render(<Badge>Test</Badge>);
    expect(screen.getByTestId("badge")).toBeInTheDocument();
  });

  it("applies default variant classes", () => {
    render(<Badge>Default</Badge>);
    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-black/70");
  });

  it("applies accent variant classes", () => {
    render(<Badge variant="accent">Accent</Badge>);
    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("text-accent-orange");
  });
});

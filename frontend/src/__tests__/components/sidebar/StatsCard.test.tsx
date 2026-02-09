import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatsCard from "@/components/sidebar/StatsCard";

const mockStats = [
  { label: "Watched", value: "247" },
  { label: "Rated", value: "189" },
];

describe("StatsCard", () => {
  it("renders YOUR STATS header", () => {
    render(<StatsCard stats={mockStats} />);
    expect(screen.getByText("YOUR STATS")).toBeInTheDocument();
  });

  it("renders all stat values", () => {
    render(<StatsCard stats={mockStats} />);
    expect(screen.getByText("247")).toBeInTheDocument();
    expect(screen.getByText("189")).toBeInTheDocument();
  });

  it("renders all stat labels", () => {
    render(<StatsCard stats={mockStats} />);
    expect(screen.getByText("Watched")).toBeInTheDocument();
    expect(screen.getByText("Rated")).toBeInTheDocument();
  });

  it("has data-testid stats-card", () => {
    render(<StatsCard stats={mockStats} />);
    expect(screen.getByTestId("stats-card")).toBeInTheDocument();
  });
});

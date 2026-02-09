import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Sidebar from "@/components/layout/Sidebar";

describe("Sidebar", () => {
  it("renders sidebar container", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });

  it("renders groups sidebar", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("groups-sidebar")).toBeInTheDocument();
  });

  it("renders stats card", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("stats-card")).toBeInTheDocument();
  });

  it("renders achievements grid", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("achievements-grid")).toBeInTheDocument();
  });
});

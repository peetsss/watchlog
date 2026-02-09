import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GroupsPage from "@/app/(main)/groups/page";

describe("GroupsPage", () => {
  it("renders GROUPS heading", () => {
    render(<GroupsPage />);
    expect(screen.getByText("GROUPS")).toBeInTheDocument();
  });

  it("renders subtitle", () => {
    render(<GroupsPage />);
    expect(
      screen.getByText("Watch together, discuss together")
    ).toBeInTheDocument();
  });

  it("renders CREATE GROUP button", () => {
    render(<GroupsPage />);
    expect(screen.getByText("CREATE GROUP")).toBeInTheDocument();
  });

  it("renders group cards", () => {
    render(<GroupsPage />);
    const cards = screen.getAllByTestId("groups-page-card");
    expect(cards.length).toBeGreaterThan(0);
  });
});

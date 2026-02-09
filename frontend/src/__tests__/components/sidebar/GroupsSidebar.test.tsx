import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GroupsSidebar from "@/components/sidebar/GroupsSidebar";

const mockGroups = [
  { name: "Criterion Crew", members: 12, active: true },
  { name: "Horror Heads", members: 8, active: false },
];

describe("GroupsSidebar", () => {
  it("renders MY GROUPS header", () => {
    render(<GroupsSidebar groups={mockGroups} />);
    expect(screen.getByText("MY GROUPS")).toBeInTheDocument();
  });

  it("renders correct number of group cards", () => {
    render(<GroupsSidebar groups={mockGroups} />);
    const cards = screen.getAllByTestId("group-card");
    expect(cards).toHaveLength(2);
  });

  it("renders CREATE NEW GROUP button", () => {
    render(<GroupsSidebar groups={mockGroups} />);
    expect(screen.getByText("CREATE NEW GROUP")).toBeInTheDocument();
  });

  it("has data-testid groups-sidebar", () => {
    render(<GroupsSidebar groups={mockGroups} />);
    expect(screen.getByTestId("groups-sidebar")).toBeInTheDocument();
  });
});

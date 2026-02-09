import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GroupCard from "@/components/sidebar/GroupCard";

const activeGroup = { name: "Criterion Crew", members: 12, active: true };
const inactiveGroup = { name: "Horror Heads", members: 8, active: false };

describe("GroupCard", () => {
  it("renders group name and member count", () => {
    render(<GroupCard group={activeGroup} />);
    expect(screen.getByText("Criterion Crew")).toBeInTheDocument();
    expect(screen.getByText("12 members")).toBeInTheDocument();
  });

  it("shows active indicator for active groups", () => {
    render(<GroupCard group={activeGroup} />);
    expect(screen.getByTestId("active-indicator")).toBeInTheDocument();
  });

  it("does not show active indicator for inactive groups", () => {
    render(<GroupCard group={inactiveGroup} />);
    expect(screen.queryByTestId("active-indicator")).not.toBeInTheDocument();
  });

  it("has data-testid group-card", () => {
    render(<GroupCard group={activeGroup} />);
    expect(screen.getByTestId("group-card")).toBeInTheDocument();
  });
});

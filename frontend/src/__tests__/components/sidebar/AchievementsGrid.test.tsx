import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AchievementsGrid from "@/components/sidebar/AchievementsGrid";

const mockAchievements = [
  { icon: "\u{1F3AC}", name: "Cinephile" },
  { icon: "\u{1F31F}", name: "Critic" },
  { icon: "\u{1F4DA}", name: "Curator" },
];

describe("AchievementsGrid", () => {
  it("renders ACHIEVEMENTS header", () => {
    render(<AchievementsGrid achievements={mockAchievements} />);
    expect(screen.getByText("ACHIEVEMENTS")).toBeInTheDocument();
  });

  it("renders correct number of badges", () => {
    render(<AchievementsGrid achievements={mockAchievements} />);
    const badges = screen.getAllByTestId("achievement-badge");
    expect(badges).toHaveLength(3);
  });

  it("has data-testid achievements-grid", () => {
    render(<AchievementsGrid achievements={mockAchievements} />);
    expect(screen.getByTestId("achievements-grid")).toBeInTheDocument();
  });
});

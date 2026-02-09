import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AchievementBadge from "@/components/sidebar/AchievementBadge";

const mockAchievement = { icon: "\u{1F3AC}", name: "Cinephile" };

describe("AchievementBadge", () => {
  it("renders achievement icon", () => {
    render(<AchievementBadge achievement={mockAchievement} />);
    expect(screen.getByText("\u{1F3AC}")).toBeInTheDocument();
  });

  it("renders achievement name", () => {
    render(<AchievementBadge achievement={mockAchievement} />);
    expect(screen.getByText("Cinephile")).toBeInTheDocument();
  });

  it("has data-testid achievement-badge", () => {
    render(<AchievementBadge achievement={mockAchievement} />);
    expect(screen.getByTestId("achievement-badge")).toBeInTheDocument();
  });
});

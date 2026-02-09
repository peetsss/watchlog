import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StarRating from "@/components/ui/StarRating";

describe("StarRating", () => {
  it("renders without crashing", () => {
    render(<StarRating rating={3} />);
    expect(screen.getByTestId("star-rating")).toBeInTheDocument();
  });

  it("renders 5 stars by default", () => {
    render(<StarRating rating={3} />);
    for (let i = 0; i < 5; i++) {
      expect(screen.getByTestId(`star-${i}`)).toBeInTheDocument();
    }
  });

  it("renders custom number of maxStars", () => {
    render(<StarRating rating={2} maxStars={3} />);
    expect(screen.getByTestId("star-0")).toBeInTheDocument();
    expect(screen.getByTestId("star-1")).toBeInTheDocument();
    expect(screen.getByTestId("star-2")).toBeInTheDocument();
    expect(screen.queryByTestId("star-3")).not.toBeInTheDocument();
  });

  it("fills correct number of stars based on rating", () => {
    render(<StarRating rating={3} />);
    const filledStars = [0, 1, 2];
    const emptyStars = [3, 4];

    filledStars.forEach((i) => {
      const star = screen.getByTestId(`star-${i}`);
      expect(star).toHaveAttribute("fill", "#FF6B35");
    });

    emptyStars.forEach((i) => {
      const star = screen.getByTestId(`star-${i}`);
      expect(star).toHaveAttribute("fill", "none");
    });
  });
});

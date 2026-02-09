import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import HeroSection from "@/components/feed/HeroSection";

const mockMovie = {
  id: 1,
  title: "Dune: Part Two",
  year: 2024,
  rating: 4.5,
  poster: "linear-gradient(135deg, #FF6B35 0%, #F7931E 100%)",
  genre: "Sci-Fi",
};

describe("HeroSection", () => {
  it("renders hero section container", () => {
    render(<HeroSection movie={mockMovie} />);
    expect(screen.getByTestId("hero-section")).toBeInTheDocument();
  });

  it("renders TRENDING THIS WEEK label", () => {
    render(<HeroSection movie={mockMovie} />);
    expect(screen.getByText("TRENDING THIS WEEK")).toBeInTheDocument();
  });

  it("renders movie title uppercased", () => {
    render(<HeroSection movie={mockMovie} />);
    expect(screen.getByText("DUNE: PART TWO")).toBeInTheDocument();
  });

  it("renders ADD TO WATCHLIST button", () => {
    render(<HeroSection movie={mockMovie} />);
    expect(screen.getByText("ADD TO WATCHLIST")).toBeInTheDocument();
  });

  it("renders star rating", () => {
    render(<HeroSection movie={mockMovie} />);
    expect(screen.getByTestId("star-rating")).toBeInTheDocument();
  });
});

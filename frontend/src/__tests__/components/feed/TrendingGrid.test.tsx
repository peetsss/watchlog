import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TrendingGrid from "@/components/feed/TrendingGrid";

const mockMovies = [
  { id: 1, title: "Movie One", year: 2024, rating: 4.5, poster: "grad1", genre: "Sci-Fi" },
  { id: 2, title: "Movie Two", year: 2023, rating: 4.0, poster: "grad2", genre: "Drama" },
];

describe("TrendingGrid", () => {
  it("renders TRENDING NOW header", () => {
    render(<TrendingGrid movies={mockMovies} />);
    expect(screen.getByText("TRENDING NOW")).toBeInTheDocument();
  });

  it("renders MOVIES and SERIES filter buttons", () => {
    render(<TrendingGrid movies={mockMovies} />);
    expect(screen.getByText("MOVIES")).toBeInTheDocument();
    expect(screen.getByText("SERIES")).toBeInTheDocument();
  });

  it("renders correct number of movie cards", () => {
    render(<TrendingGrid movies={mockMovies} />);
    const cards = screen.getAllByTestId("movie-card");
    expect(cards).toHaveLength(2);
  });

  it("has data-testid trending-grid", () => {
    render(<TrendingGrid movies={mockMovies} />);
    expect(screen.getByTestId("trending-grid")).toBeInTheDocument();
  });
});

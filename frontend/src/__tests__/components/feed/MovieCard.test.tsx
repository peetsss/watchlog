import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MovieCard from "@/components/feed/MovieCard";

const mockMovie = {
  id: 1,
  title: "Dune: Part Two",
  year: 2024,
  rating: 4.5,
  poster: "linear-gradient(135deg, #FF6B35 0%, #F7931E 100%)",
  genre: "Sci-Fi",
};

describe("MovieCard", () => {
  it("renders movie title", () => {
    render(<MovieCard movie={mockMovie} />);
    expect(screen.getByText("Dune: Part Two")).toBeInTheDocument();
  });

  it("renders movie year", () => {
    render(<MovieCard movie={mockMovie} />);
    expect(screen.getByText("2024")).toBeInTheDocument();
  });

  it("renders genre badge", () => {
    render(<MovieCard movie={mockMovie} />);
    expect(screen.getByText("Sci-Fi")).toBeInTheDocument();
  });

  it("renders rating", () => {
    render(<MovieCard movie={mockMovie} />);
    expect(screen.getByText("4.5")).toBeInTheDocument();
  });

  it("has data-testid movie-card", () => {
    render(<MovieCard movie={mockMovie} />);
    expect(screen.getByTestId("movie-card")).toBeInTheDocument();
  });
});

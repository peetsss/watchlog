import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DiscoverPage from "@/app/(main)/discover/page";

describe("DiscoverPage", () => {
  it("renders DISCOVER heading", () => {
    render(<DiscoverPage />);
    expect(screen.getByText("DISCOVER")).toBeInTheDocument();
  });

  it("renders subtitle", () => {
    render(<DiscoverPage />);
    expect(screen.getByText("Explore new films and series")).toBeInTheDocument();
  });

  it("renders genre filter buttons", () => {
    render(<DiscoverPage />);
    expect(screen.getByText("ALL")).toBeInTheDocument();
    expect(screen.getByText("DRAMA")).toBeInTheDocument();
    expect(screen.getByText("HORROR")).toBeInTheDocument();
  });

  it("renders movie cards", () => {
    render(<DiscoverPage />);
    const cards = screen.getAllByTestId("movie-card");
    expect(cards.length).toBeGreaterThan(0);
  });
});

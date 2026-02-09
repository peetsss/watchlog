import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ListsPage from "@/app/(main)/lists/page";

describe("ListsPage", () => {
  it("renders MY LISTS heading", () => {
    render(<ListsPage />);
    expect(screen.getByText("MY LISTS")).toBeInTheDocument();
  });

  it("renders subtitle", () => {
    render(<ListsPage />);
    expect(
      screen.getByText("Curate and share your collections")
    ).toBeInTheDocument();
  });

  it("renders CREATE LIST button", () => {
    render(<ListsPage />);
    expect(screen.getByText("CREATE LIST")).toBeInTheDocument();
  });

  it("renders list cards", () => {
    render(<ListsPage />);
    const cards = screen.getAllByTestId("list-card");
    expect(cards.length).toBeGreaterThan(0);
  });

  it("renders list names", () => {
    render(<ListsPage />);
    expect(screen.getByText("MUST WATCH 2024")).toBeInTheDocument();
    expect(screen.getByText("ALL-TIME FAVORITES")).toBeInTheDocument();
  });
});

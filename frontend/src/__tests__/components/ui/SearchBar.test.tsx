import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SearchBar from "@/components/ui/SearchBar";

describe("SearchBar", () => {
  it("renders search input with placeholder", () => {
    render(<SearchBar />);
    expect(
      screen.getByPlaceholderText("Search films, series, people...")
    ).toBeInTheDocument();
  });

  it("renders search icon", () => {
    render(<SearchBar />);
    expect(screen.getByTestId("search-icon")).toBeInTheDocument();
  });

  it("renders search input element", () => {
    render(<SearchBar />);
    expect(screen.getByTestId("search-input")).toBeInTheDocument();
  });
});

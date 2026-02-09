import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FeedPage from "@/app/(main)/feed/page";

describe("FeedPage", () => {
  it("renders hero section", () => {
    render(<FeedPage />);
    expect(screen.getByTestId("hero-section")).toBeInTheDocument();
  });

  it("renders trending grid", () => {
    render(<FeedPage />);
    expect(screen.getByTestId("trending-grid")).toBeInTheDocument();
  });

  it("renders friend activity feed", () => {
    render(<FeedPage />);
    expect(screen.getByTestId("friend-activity-feed")).toBeInTheDocument();
  });

  it("renders TRENDING NOW section", () => {
    render(<FeedPage />);
    expect(screen.getByText("TRENDING NOW")).toBeInTheDocument();
  });

  it("renders FRIEND ACTIVITY section", () => {
    render(<FeedPage />);
    expect(screen.getByText("FRIEND ACTIVITY")).toBeInTheDocument();
  });
});

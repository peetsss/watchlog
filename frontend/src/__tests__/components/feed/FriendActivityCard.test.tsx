import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FriendActivityCard from "@/components/feed/FriendActivityCard";
import type { FriendActivity } from "@/types";

const ratedActivity: FriendActivity = {
  user: "Sarah M.",
  action: "rated",
  title: "Poor Things",
  rating: 5,
  time: "2h ago",
};

const listActivity: FriendActivity = {
  user: "Alex K.",
  action: "added to list",
  title: "The Zone of Interest",
  list: "Must Watch 2024",
  time: "5h ago",
};

describe("FriendActivityCard", () => {
  it("renders user name", () => {
    render(<FriendActivityCard activity={ratedActivity} />);
    expect(screen.getByText("Sarah M.")).toBeInTheDocument();
  });

  it("renders action text", () => {
    render(<FriendActivityCard activity={ratedActivity} />);
    expect(screen.getByText("rated")).toBeInTheDocument();
  });

  it("renders movie title", () => {
    render(<FriendActivityCard activity={ratedActivity} />);
    expect(screen.getByText("Poor Things")).toBeInTheDocument();
  });

  it("renders time", () => {
    render(<FriendActivityCard activity={ratedActivity} />);
    expect(screen.getByText("2h ago")).toBeInTheDocument();
  });

  it("renders star rating when activity has rating", () => {
    render(<FriendActivityCard activity={ratedActivity} />);
    expect(screen.getByTestId("star-rating")).toBeInTheDocument();
  });

  it("renders list reference when activity has list", () => {
    render(<FriendActivityCard activity={listActivity} />);
    expect(screen.getByText(/Must Watch 2024/)).toBeInTheDocument();
  });

  it("has data-testid friend-activity-card", () => {
    render(<FriendActivityCard activity={ratedActivity} />);
    expect(screen.getByTestId("friend-activity-card")).toBeInTheDocument();
  });
});

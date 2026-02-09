import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FriendActivityFeed from "@/components/feed/FriendActivityFeed";
import type { FriendActivity } from "@/types";

const mockActivities: FriendActivity[] = [
  { user: "Sarah M.", action: "rated", title: "Poor Things", rating: 5, time: "2h ago" },
  { user: "Alex K.", action: "added to list", title: "The Zone of Interest", list: "Must Watch 2024", time: "5h ago" },
];

describe("FriendActivityFeed", () => {
  it("renders FRIEND ACTIVITY header", () => {
    render(<FriendActivityFeed activities={mockActivities} />);
    expect(screen.getByText("FRIEND ACTIVITY")).toBeInTheDocument();
  });

  it("renders correct number of activity cards", () => {
    render(<FriendActivityFeed activities={mockActivities} />);
    const cards = screen.getAllByTestId("friend-activity-card");
    expect(cards).toHaveLength(2);
  });

  it("has data-testid friend-activity-feed", () => {
    render(<FriendActivityFeed activities={mockActivities} />);
    expect(screen.getByTestId("friend-activity-feed")).toBeInTheDocument();
  });
});

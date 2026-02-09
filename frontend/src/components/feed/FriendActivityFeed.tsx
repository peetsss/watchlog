import type { FriendActivity } from "@/types";
import FriendActivityCard from "./FriendActivityCard";

interface FriendActivityFeedProps {
  activities: FriendActivity[];
}

export default function FriendActivityFeed({
  activities,
}: FriendActivityFeedProps) {
  return (
    <div data-testid="friend-activity-feed">
      <h3 className="mb-6 font-heading text-3xl tracking-[2px]">
        FRIEND ACTIVITY
      </h3>
      <div className="flex flex-col gap-4">
        {activities.map((activity, idx) => (
          <FriendActivityCard key={idx} activity={activity} index={idx} />
        ))}
      </div>
    </div>
  );
}

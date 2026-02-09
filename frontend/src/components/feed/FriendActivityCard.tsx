import type { FriendActivity } from "@/types";
import StarRating from "@/components/ui/StarRating";

interface FriendActivityCardProps {
  activity: FriendActivity;
  index?: number;
}

const delayClasses = ["", "delay-100", "delay-200", "delay-300"];

export default function FriendActivityCard({
  activity,
  index = 0,
}: FriendActivityCardProps) {
  return (
    <div
      className={`animate-fade-in-up flex items-center justify-between rounded-xl border border-border bg-surface p-5 transition-all duration-300 hover:border-border-hover hover:bg-surface-hover ${delayClasses[index % 4]}`}
      data-testid="friend-activity-card"
    >
      <div>
        <div className="mb-2">
          <span className="font-semibold text-accent-orange">
            {activity.user}
          </span>
          <span className="mx-2 text-text-muted">{activity.action}</span>
          <span className="italic">{activity.title}</span>
        </div>
        {activity.rating !== undefined && (
          <StarRating rating={activity.rating} size={14} />
        )}
        {activity.list && (
          <div className="mt-1 text-sm text-accent-teal">
            &rarr; {activity.list}
          </div>
        )}
      </div>
      <span className="text-sm text-text-dim">{activity.time}</span>
    </div>
  );
}

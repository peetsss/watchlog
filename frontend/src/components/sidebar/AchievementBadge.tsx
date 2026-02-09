import type { Achievement } from "@/types";

interface AchievementBadgeProps {
  achievement: Achievement;
}

export default function AchievementBadge({ achievement }: AchievementBadgeProps) {
  return (
    <div
      className="cursor-pointer rounded-lg border border-accent-orange/15 bg-accent-orange/5 px-2 py-4 text-center transition-all duration-300 hover:scale-105 hover:bg-accent-orange/10"
      data-testid="achievement-badge"
    >
      <div className="mb-2 text-2xl">{achievement.icon}</div>
      <div className="font-heading text-xs tracking-wider">{achievement.name}</div>
    </div>
  );
}

import { Award } from "lucide-react";
import type { Achievement } from "@/types";
import AchievementBadge from "./AchievementBadge";

interface AchievementsGridProps {
  achievements: Achievement[];
}

export default function AchievementsGrid({ achievements }: AchievementsGridProps) {
  return (
    <div
      className="rounded-xl border border-border bg-surface p-6"
      data-testid="achievements-grid"
    >
      <h3 className="mb-5 flex items-center gap-2 font-heading text-2xl tracking-[2px]">
        <Award size={20} />
        ACHIEVEMENTS
      </h3>
      <div className="grid grid-cols-3 gap-4">
        {achievements.map((achievement, idx) => (
          <AchievementBadge key={idx} achievement={achievement} />
        ))}
      </div>
    </div>
  );
}

import { TrendingUp } from "lucide-react";
import type { UserStat } from "@/types";

interface StatsCardProps {
  stats: UserStat[];
}

export default function StatsCard({ stats }: StatsCardProps) {
  return (
    <div
      className="rounded-xl border border-accent-teal/20 bg-gradient-to-br from-accent-teal/10 to-accent-teal-dark/10 p-6"
      data-testid="stats-card"
    >
      <h3 className="mb-5 flex items-center gap-2 font-heading text-2xl tracking-[2px]">
        <TrendingUp size={20} />
        YOUR STATS
      </h3>
      <div className="grid grid-cols-2 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="text-center">
            <div className="font-heading text-4xl leading-none text-accent-teal">
              {stat.value}
            </div>
            <div className="mt-1 font-heading text-sm uppercase tracking-wider text-text-muted">
              {stat.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

import GroupsSidebar from "@/components/sidebar/GroupsSidebar";
import StatsCard from "@/components/sidebar/StatsCard";
import AchievementsGrid from "@/components/sidebar/AchievementsGrid";
import { myGroups, userStats, achievements } from "@/data/mock-data";

export default function Sidebar() {
  return (
    <aside className="hidden flex-col gap-8 lg:flex" data-testid="sidebar">
      <GroupsSidebar groups={myGroups} />
      <StatsCard stats={userStats} />
      <AchievementsGrid achievements={achievements} />
    </aside>
  );
}

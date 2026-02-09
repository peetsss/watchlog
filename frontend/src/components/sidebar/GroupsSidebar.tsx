import { Users, Plus } from "lucide-react";
import type { Group } from "@/types";
import GroupCard from "./GroupCard";

interface GroupsSidebarProps {
  groups: Group[];
}

export default function GroupsSidebar({ groups }: GroupsSidebarProps) {
  return (
    <div
      className="rounded-xl border border-border bg-surface p-6"
      data-testid="groups-sidebar"
    >
      <h3 className="mb-5 flex items-center gap-2 font-heading text-2xl tracking-[2px]">
        <Users size={20} />
        MY GROUPS
      </h3>
      <div className="flex flex-col gap-3">
        {groups.map((group, idx) => (
          <GroupCard key={idx} group={group} />
        ))}
        <button className="mt-2 cursor-pointer rounded-lg border border-dashed border-border-dashed bg-transparent p-3 font-heading text-sm tracking-wider text-text-muted transition-all duration-300 hover:border-accent-orange/50 hover:text-accent-orange">
          <Plus size={16} className="mr-2 inline" />
          CREATE NEW GROUP
        </button>
      </div>
    </div>
  );
}

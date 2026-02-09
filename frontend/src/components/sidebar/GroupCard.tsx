import type { Group } from "@/types";

interface GroupCardProps {
  group: Group;
}

export default function GroupCard({ group }: GroupCardProps) {
  return (
    <div
      className={`cursor-pointer rounded-lg border p-4 transition-all duration-300 hover:bg-accent-orange/10 ${
        group.active
          ? "border-accent-orange/20 bg-accent-orange/[0.08]"
          : "border-text-primary/5 bg-surface"
      }`}
      data-testid="group-card"
    >
      <div className="flex items-center justify-between">
        <div>
          <div
            className={`mb-1 font-semibold ${
              group.active ? "text-accent-orange" : "text-text-primary"
            }`}
          >
            {group.name}
          </div>
          <div className="text-sm text-text-muted">{group.members} members</div>
        </div>
        {group.active && (
          <div
            className="h-2 w-2 rounded-full bg-accent-orange"
            data-testid="active-indicator"
          />
        )}
      </div>
    </div>
  );
}

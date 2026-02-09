import { Users, Plus } from "lucide-react";
import { allGroups } from "@/data/mock-data";

export default function GroupsPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="m-0 mb-2 font-heading text-4xl tracking-[3px]">
            GROUPS
          </h1>
          <p className="m-0 text-text-muted">
            Watch together, discuss together
          </p>
        </div>
        <button className="flex cursor-pointer items-center gap-2 rounded-full border border-accent-orange/30 bg-accent-orange/10 px-6 py-3 font-heading text-sm tracking-wider text-accent-orange transition-all duration-300 hover:bg-accent-orange/20">
          <Plus size={16} />
          CREATE GROUP
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {allGroups.map((group, idx) => (
          <div
            key={idx}
            className={`cursor-pointer rounded-xl border p-6 transition-all duration-300 hover:-translate-y-1 hover:bg-accent-orange/10 ${
              group.active
                ? "border-accent-orange/20 bg-accent-orange/[0.08]"
                : "border-border bg-surface"
            }`}
            data-testid="groups-page-card"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-orange/10">
                  <Users size={20} className="text-accent-orange" />
                </div>
                <div>
                  <div
                    className={`font-semibold ${
                      group.active ? "text-accent-orange" : "text-text-primary"
                    }`}
                  >
                    {group.name}
                  </div>
                  <div className="text-sm text-text-muted">
                    {group.members} members
                  </div>
                </div>
              </div>
              {group.active && (
                <div className="h-2.5 w-2.5 rounded-full bg-accent-orange" />
              )}
            </div>
            <div className="text-sm text-text-muted">
              Active community discussing the latest releases
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

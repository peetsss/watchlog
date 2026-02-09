import { List, Plus } from "lucide-react";
import { userLists } from "@/data/mock-data";

export default function ListsPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="m-0 mb-2 font-heading text-4xl tracking-[3px]">
            MY LISTS
          </h1>
          <p className="m-0 text-text-muted">
            Curate and share your collections
          </p>
        </div>
        <button className="flex cursor-pointer items-center gap-2 rounded-full border border-accent-orange/30 bg-accent-orange/10 px-6 py-3 font-heading text-sm tracking-wider text-accent-orange transition-all duration-300 hover:bg-accent-orange/20">
          <Plus size={16} />
          CREATE LIST
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {userLists.map((list) => (
          <div
            key={list.id}
            className="group cursor-pointer overflow-hidden rounded-xl border border-border transition-all duration-300 hover:-translate-y-1 hover:border-border-hover"
            data-testid="list-card"
          >
            <div
              className="flex h-32 items-end p-6"
              style={{ background: list.gradient }}
            >
              <h3 className="m-0 font-heading text-2xl tracking-[2px]">
                {list.name.toUpperCase()}
              </h3>
            </div>
            <div className="bg-surface p-6">
              <p className="m-0 mb-3 text-text-muted">{list.description}</p>
              <div className="flex items-center gap-2 text-sm text-text-dim">
                <List size={14} />
                <span>{list.movieCount} films</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

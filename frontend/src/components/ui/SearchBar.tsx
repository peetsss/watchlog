"use client";

import { Search } from "lucide-react";

export default function SearchBar() {
  return (
    <div className="relative flex items-center">
      <Search
        size={18}
        className="absolute left-3 text-text-dim"
        data-testid="search-icon"
      />
      <input
        type="text"
        placeholder="Search films, series, people..."
        className="w-[250px] rounded-full border border-border-light bg-text-primary/5 py-2.5 pr-4 pl-10 text-sm text-text-primary outline-none transition-all duration-300 placeholder:text-text-dim focus:border-accent-orange/30 focus:bg-text-primary/[0.08]"
        data-testid="search-input"
      />
    </div>
  );
}

import { Film, Tv } from "lucide-react";
import type { Movie } from "@/types";
import MovieCard from "./MovieCard";

interface TrendingGridProps {
  movies: Movie[];
}

export default function TrendingGrid({ movies }: TrendingGridProps) {
  return (
    <div data-testid="trending-grid">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="m-0 font-heading text-3xl tracking-[2px]">
          TRENDING NOW
        </h3>
        <div className="flex gap-4">
          <button className="cursor-pointer rounded-full border border-accent-orange/30 bg-accent-orange/10 px-4 py-2 font-heading text-xs tracking-wider text-accent-orange">
            <Film size={14} className="mr-2 inline" />
            MOVIES
          </button>
          <button className="cursor-pointer rounded-full border border-border-dashed bg-transparent px-4 py-2 font-heading text-xs tracking-wider text-text-muted">
            <Tv size={14} className="mr-2 inline" />
            SERIES
          </button>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {movies.map((movie, idx) => (
          <MovieCard key={movie.id} movie={movie} index={idx} />
        ))}
      </div>
    </div>
  );
}

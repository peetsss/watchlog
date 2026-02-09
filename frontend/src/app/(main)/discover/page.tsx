"use client";

import { useState } from "react";
import MovieCard from "@/components/feed/MovieCard";
import { discoverMovies } from "@/data/mock-data";

const genres = ["All", "Drama", "Horror", "Comedy", "Thriller", "Sci-Fi", "Musical"];

export default function DiscoverPage() {
  const [activeGenre, setActiveGenre] = useState("All");

  const filteredMovies =
    activeGenre === "All"
      ? discoverMovies
      : discoverMovies.filter((m) => m.genre === activeGenre);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="m-0 mb-2 font-heading text-4xl tracking-[3px]">
          DISCOVER
        </h1>
        <p className="m-0 text-text-muted">Explore new films and series</p>
      </div>

      <div className="flex flex-wrap gap-3">
        {genres.map((genre) => (
          <button
            key={genre}
            onClick={() => setActiveGenre(genre)}
            className={`cursor-pointer rounded-full px-4 py-2 font-heading text-xs tracking-wider transition-all duration-300 ${
              activeGenre === genre
                ? "border border-accent-orange/30 bg-accent-orange/10 text-accent-orange"
                : "border border-border-dashed bg-transparent text-text-muted hover:border-accent-orange/20 hover:text-text-primary"
            }`}
          >
            {genre.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {filteredMovies.map((movie, idx) => (
          <MovieCard key={movie.id} movie={movie} index={idx} />
        ))}
      </div>

      {filteredMovies.length === 0 && (
        <div className="py-12 text-center text-text-muted">
          No movies found for this genre.
        </div>
      )}
    </div>
  );
}

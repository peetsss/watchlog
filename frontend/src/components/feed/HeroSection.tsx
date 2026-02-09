import { Plus } from "lucide-react";
import type { Movie } from "@/types";
import StarRating from "@/components/ui/StarRating";

interface HeroSectionProps {
  movie: Movie;
}

export default function HeroSection({ movie }: HeroSectionProps) {
  return (
    <div
      className="relative flex h-[400px] flex-col justify-end overflow-hidden rounded-xl p-8 sm:p-12"
      style={{ background: movie.poster }}
      data-testid="hero-section"
    >
      {/* Pattern overlay */}
      <div
        className="absolute inset-0 opacity-15"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        }}
      />

      <div className="relative z-[1]">
        <div className="mb-2 font-heading text-sm tracking-[2px] opacity-90">
          TRENDING THIS WEEK
        </div>
        <h2 className="m-0 mb-4 font-heading text-5xl leading-none tracking-[2px] sm:text-7xl">
          {movie.title.toUpperCase()}
        </h2>
        <div className="mb-6 flex items-center gap-6">
          <StarRating rating={Math.floor(movie.rating)} />
          <span className="text-base">
            {movie.rating}/5 &bull; {movie.year} &bull; {movie.genre} Epic
          </span>
        </div>
        <button className="cursor-pointer rounded-full border border-white/20 bg-black/30 px-8 py-3 font-heading tracking-wider text-white backdrop-blur-[10px] transition-all duration-300 hover:-translate-y-0.5 hover:bg-black/50">
          <Plus size={16} className="mr-2 inline" />
          ADD TO WATCHLIST
        </button>
      </div>
    </div>
  );
}

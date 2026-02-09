import { Star } from "lucide-react";
import type { Movie } from "@/types";
import Badge from "@/components/ui/Badge";

interface MovieCardProps {
  movie: Movie;
  index?: number;
}

const delayClasses = ["", "delay-100", "delay-200", "delay-300"];

export default function MovieCard({ movie, index = 0 }: MovieCardProps) {
  return (
    <div
      className={`animate-fade-in-up cursor-pointer transition-transform duration-300 hover:-translate-y-2 ${delayClasses[index % 4]}`}
      data-testid="movie-card"
    >
      <div
        className="relative mb-3 h-[280px] overflow-hidden rounded-lg"
        style={{ background: movie.poster }}
      >
        <div className="absolute top-3 right-3">
          <Badge>{movie.genre}</Badge>
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex items-center gap-2 bg-gradient-to-t from-black/90 to-transparent px-4 pt-6 pb-4">
          <Star size={16} fill="#FF6B35" stroke="#FF6B35" />
          <span className="font-heading text-lg tracking-wider">
            {movie.rating}
          </span>
        </div>
      </div>
      <h4 className="m-0 mb-1 text-base font-semibold">{movie.title}</h4>
      <p className="m-0 text-sm text-text-muted">{movie.year}</p>
    </div>
  );
}

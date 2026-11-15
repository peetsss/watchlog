import { Film } from "lucide-react";
import type { Movie } from "../data";
import { cx } from "../lib/cx";

export function PosterStack({ movies, className }: { movies: Movie[]; className?: string }) {
  if (!movies.length) {
    return (
      <div className={cx("poster-stack poster-stack-empty", className)} aria-hidden="true">
        <Film size={22} />
      </div>
    );
  }

  return (
    <div className={cx("poster-stack", className)} aria-hidden="true">
      {movies.slice(0, 3).map((movie, index) => (
        <img
          key={movie.id}
          src={movie.poster}
          alt=""
          className={`poster-stack-img poster-stack-img-${index}`}
          loading="lazy"
        />
      ))}
    </div>
  );
}

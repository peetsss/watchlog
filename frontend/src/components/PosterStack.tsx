import { Film } from "lucide-react";
import { cx } from "../lib/cx";
import { MoviePoster } from "./MoviePoster";

export type PosterStackMovie = {
  id: string | number;
  title: string;
  poster?: string | null;
};

export function PosterStack({
  movies,
  className,
}: {
  movies: PosterStackMovie[];
  className?: string;
}) {
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
        <MoviePoster
          key={movie.id}
          src={movie.poster}
          title={movie.title}
          className={`poster-stack-img poster-stack-img-${index}`}
        />
      ))}
    </div>
  );
}

import { Check, Loader2, Plus, Star } from "lucide-react";
import { Button } from "./Button";
import { Modal } from "./Modal";
import { MoviePoster } from "./MoviePoster";
import type { GroupSummaryView, MovieSearchView } from "../lib/adapters";

export function SearchMovieDialog({
  movie,
  group,
  added,
  pending,
  open,
  onOpenChange,
  onAdd,
}: {
  movie: MovieSearchView | null;
  group: GroupSummaryView | null;
  added: boolean;
  pending: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: () => void;
}) {
  if (!movie) return null;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={movie.title}
      description={[movie.year, movie.mediaType === "series" ? "Series" : "Movie"]
        .filter(Boolean)
        .join(" · ")}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button onClick={onAdd} disabled={added || pending || !group}>
            {pending ? (
              <>
                <Loader2 className="spin" size={15} /> Adding…
              </>
            ) : added ? (
              <>
                <Check size={15} /> Added
              </>
            ) : (
              <>
                <Plus size={15} /> Add to {group?.name ?? "group"}
              </>
            )}
          </Button>
        </>
      }
    >
      <div className="search-detail">
        <div className="search-detail-poster">
          <MoviePoster src={movie.poster} title={movie.title} />
        </div>
        <div className="search-detail-copy">
          {movie.tmdbScore !== null ? (
            <p className="search-detail-rating">
              <Star size={12} fill="currentColor" aria-hidden="true" /> TMDB{" "}
              <strong>{movie.tmdbScore.toFixed(1)}</strong>
            </p>
          ) : null}
          <p className="search-detail-overview">
            {movie.overview || "No synopsis yet. Add it to a watchlist to load the full details."}
          </p>
        </div>
      </div>
    </Modal>
  );
}

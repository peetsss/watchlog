import { Dialog } from "@base-ui/react/dialog";
import { Film, Info, Loader2, Star, X } from "lucide-react";
import { useRef } from "react";
import { Button } from "./Button";
import { MoviePoster } from "./MoviePoster";
import { WhereToWatch } from "./WhereToWatch";
import type { LobbyView, MovieSummaryView } from "../lib/adapters";
import { useMovieDetail } from "../lib/api-movies";
import { useSheetSwipe } from "../lib/useSheetSwipe";

const VOTE_LABEL = {
  in: "I'm in",
  seen: "Seen it",
  out: "Not for me",
} as const;

export function MovieDetailSheet({
  movieId,
  lobby,
  open,
  onOpenChange,
}: {
  movieId: number | null;
  lobby: LobbyView | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const swipe = useSheetSwipe(open, () => onOpenChange(false));
  const closeRef = useRef<HTMLButtonElement>(null);
  const detailQuery = useMovieDetail(movieId, open);

  const finalist = lobby?.finalists.find((entry) => entry.movie.id === movieId);
  const summary: MovieSummaryView | null =
    (lobby?.currentMovie?.id === movieId ? lobby.currentMovie : null) ??
    finalist?.movie ??
    (lobby?.winner?.id === movieId ? lobby.winner : null);

  const movie = detailQuery.data ?? summary;
  if (!movieId || !movie) return null;

  const isCurrent = lobby?.status === "playing" && lobby?.currentMovie?.id === movie.id;
  const isWinner = lobby?.winner?.id === movie.id;
  const credits = detailQuery.data
    ? [
        { label: "Director", value: detailQuery.data.director },
        {
          label: "Writers",
          value: detailQuery.data.writers.length
            ? detailQuery.data.writers.join(", ")
            : null,
        },
        {
          label: "Cast",
          value: detailQuery.data.cast.length ? detailQuery.data.cast.join(", ") : null,
        },
        { label: "Language", value: detailQuery.data.language },
      ].filter((entry) => entry.value)
    : [];

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="detail-overlay" />
        <Dialog.Popup className="detail-sheet" initialFocus={closeRef}>
          <Dialog.Description className="sr-only">
            Film details for {movie.title} and its place in tonight's room.
          </Dialog.Description>

          <div className="detail-hero" {...swipe}>
            <div
              className="detail-backdrop"
              style={movie.backdrop ? { backgroundImage: `url(${movie.backdrop})` } : undefined}
              aria-hidden="true"
            />
            <div className="detail-hero-scrim" aria-hidden="true" />
            <Dialog.Close
              ref={closeRef}
              type="button"
              className="icon-button detail-close"
              aria-label="Close film details"
            >
              <X size={18} />
            </Dialog.Close>

            <div className="detail-heading">
              <div className="detail-poster">
                <MoviePoster src={movie.poster} title={movie.title} />
              </div>
              <div className="detail-heading-copy">
                <p className="eyebrow">
                  {isWinner ? (
                    <>
                      <Star size={13} fill="currentColor" aria-hidden="true" /> Tonight's pick
                    </>
                  ) : finalist ? (
                    <>
                      <Star size={13} aria-hidden="true" /> Finalist
                    </>
                  ) : isCurrent ? (
                    <>
                      <Film size={13} aria-hidden="true" /> On the table
                    </>
                  ) : (
                    "The room"
                  )}
                </p>
                <Dialog.Title className="detail-title">{movie.title}</Dialog.Title>
                <p className="detail-meta">
                  {[movie.year, movie.runtime ? `${movie.runtime} min` : null, movie.genres.join(", ")]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {detailQuery.data?.tagline ? (
                  <p className="detail-tagline">“{detailQuery.data.tagline}”</p>
                ) : null}
                {isWinner ? (
                  <span className="detail-chip is-positive">The room has spoken</span>
                ) : finalist && lobby?.picksRevealed ? (
                  <span className="detail-chip">
                    {finalist.pickCount ?? 0} {finalist.pickCount === 1 ? "pick" : "picks"}
                  </span>
                ) : null}
              </div>
            </div>
          </div>

          <div className="detail-body">
            {lobby ? (
              <section className="detail-section">
                <h3>In the room</h3>
                <div className="detail-club">
                  <div className="detail-club-head">
                    <strong>{lobby.groupName ?? "Open room"}</strong>
                    <span>{lobby.playerCount} in the room</span>
                  </div>
                  <div className="detail-club-row">
                    {isCurrent && !lobby.revealed ? (
                      <span className="detail-muted">
                        {lobby.viewerVote
                          ? `Your vote: ${VOTE_LABEL[lobby.viewerVote]}. Waiting for the room.`
                          : "You haven't voted on this one yet."}
                      </span>
                    ) : isCurrent && lobby.revealed && lobby.voteTally ? (
                      <span className="detail-muted">
                        {lobby.voteTally.interested} in · {lobby.voteTally.watched} seen ·{" "}
                        {lobby.voteTally.notInterested} out
                      </span>
                    ) : isWinner ? (
                      <span className="detail-muted">Tonight's pick for the room.</span>
                    ) : finalist ? (
                      <span className="detail-muted">In the final round.</span>
                    ) : (
                      <span className="detail-muted">Not on tonight's table.</span>
                    )}
                  </div>
                </div>
              </section>
            ) : null}

            <section className="detail-section">
              <h3>The story</h3>
              <p>{movie.description || "No synopsis yet."}</p>
            </section>

            {detailQuery.data ? <WhereToWatch watch={detailQuery.data.watch} /> : null}

            <section className="detail-section">
              <h3>The credits</h3>
              {detailQuery.isPending ? (
                <p className="detail-muted">
                  <Loader2 className="spin" size={13} aria-hidden="true" /> Loading credits…
                </p>
              ) : credits.length ? (
                <dl className="detail-credits">
                  {credits.map((entry) => (
                    <div key={entry.label}>
                      <dt>{entry.label}</dt>
                      <dd>{entry.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="detail-muted">No credits yet.</p>
              )}
            </section>
          </div>

          <div className="detail-footer">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            {lobby?.groupId ? (
              <span className="detail-muted">
                <Info size={13} aria-hidden="true" /> {lobby.groupName}
              </span>
            ) : null}
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

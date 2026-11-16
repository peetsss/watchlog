import { Dialog } from "@base-ui/react/dialog";
import { Check, Eye, Loader2, Star, X } from "lucide-react";
import { useRef } from "react";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { MoviePoster } from "../../components/MoviePoster";
import { formatDate, type GroupFilmView, type GroupSummaryView } from "../../lib/adapters";
import { useGroupFilmScores } from "../../lib/api-groups";
import { useMovieDetail } from "../../lib/api-movies";
import { cx } from "../../lib/cx";
import { useSheetSwipe } from "../../lib/useSheetSwipe";
import { useSession } from "../../state/Session";

export function GroupFilmSheet({
  group,
  film,
  open,
  onOpenChange,
  onScore,
}: {
  group: GroupSummaryView;
  film: GroupFilmView | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onScore: () => void;
}) {
  const swipe = useSheetSwipe(open, () => onOpenChange(false));
  const closeRef = useRef<HTMLButtonElement>(null);
  const { viewer } = useSession();
  const scoresQuery = useGroupFilmScores(group.id, film?.id ?? null, open);
  const detailQuery = useMovieDetail(film?.movie.id ?? null, open);

  if (!film) return null;

  const movie = film.movie;
  const detail = detailQuery.data;
  const scores = [...(scoresQuery.data ?? [])].sort(
    (a, b) => b.score - a.score || a.person.name.localeCompare(b.person.name),
  );
  const watched = film.status === "watched";
  const viewerId = viewer ? String(viewer.id) : null;
  const credits = [
    { label: "Director", value: movie.director },
    { label: "Writers", value: detail?.writers.length ? detail.writers.join(", ") : null },
    { label: "Cast", value: detail?.cast.length ? detail.cast.join(", ") : null },
    { label: "Language", value: detail?.language ?? null },
  ].filter((entry) => entry.value);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="detail-overlay" />
        <Dialog.Popup className="detail-sheet" initialFocus={closeRef}>
          <Dialog.Description className="sr-only">
            Film details for {movie.title}, the club's scores and watchlist status.
          </Dialog.Description>

          <div className="detail-hero" {...swipe}>
            <div
              className="detail-backdrop"
              style={
                movie.backdrop ? { backgroundImage: `url(${movie.backdrop})` } : undefined
              }
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
                  {watched ? (
                    <>
                      <Eye size={13} aria-hidden="true" /> Watched
                    </>
                  ) : (
                    <>
                      <Check size={13} aria-hidden="true" /> Up next
                    </>
                  )}
                </p>
                <Dialog.Title className="detail-title">{movie.title}</Dialog.Title>
                <p className="detail-meta">
                  {[movie.year, movie.runtime ? `${movie.runtime} min` : null, movie.genres.join(", ")]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {detail?.tagline ? <p className="detail-tagline">“{detail.tagline}”</p> : null}
                {film.clubScore !== null ? (
                  <span className="detail-chip is-positive group-detail-score-chip">
                    <Star size={11} fill="currentColor" aria-hidden="true" />{" "}
                    {film.clubScore.toFixed(1)} club score
                  </span>
                ) : (
                  <span className="detail-chip">Not scored yet</span>
                )}
              </div>
            </div>
          </div>

          <div className="detail-body">
            <section className="detail-section group-scores">
              <h3>The scores</h3>
              {scoresQuery.isPending ? (
                <p className="group-scores-empty">
                  <Loader2 className="spin" size={14} aria-hidden="true" /> Loading scores…
                </p>
              ) : scoresQuery.isError ? (
                <p className="group-scores-empty">Couldn't load the scores. Try again in a moment.</p>
              ) : scores.length ? (
                <>
                  <div className="group-score-summary">
                    <strong>{film.clubScore !== null ? film.clubScore.toFixed(1) : "—"}</strong>
                    <span>
                      from {film.scoreCount} {film.scoreCount === 1 ? "score" : "scores"}
                    </span>
                  </div>
                  <ul className="group-score-list">
                    {scores.map(({ person, score }) => (
                      <li key={person.id} className={cx(person.id === viewerId && "is-you")}>
                        <Avatar person={person} size={28} />
                        <span className="group-score-name">
                          {person.name}
                          {person.id === viewerId ? <em>You</em> : null}
                        </span>
                        <span className="group-score-bar" aria-hidden="true">
                          <span
                            style={{
                              transform: `scaleX(${Math.max(0.02, score / 10)})`,
                              background: person.color,
                            }}
                          />
                        </span>
                        <strong>{score.toFixed(1)}</strong>
                      </li>
                    ))}
                  </ul>
                  {film.yourScore === null ? (
                    <p className="group-scores-note">You haven't added your score yet.</p>
                  ) : null}
                </>
              ) : (
                <p className="group-scores-empty">
                  No one has scored this yet. Watch it, then add the club's first score.
                </p>
              )}
            </section>

            <section className="detail-section">
              <h3>The story</h3>
              <p>{movie.description || "No synopsis yet."}</p>
            </section>

            <section className="detail-section">
              <h3>The credits</h3>
              {credits.length ? (
                <dl className="detail-credits">
                  {credits.map((entry) => (
                    <div key={entry.label}>
                      <dt>{entry.label}</dt>
                      <dd>{entry.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="group-scores-empty">No credits yet.</p>
              )}
            </section>

            <section className="detail-section">
              <h3>In the club</h3>
              <div className="detail-club">
                <div className="detail-club-head">
                  <strong>{group.name}</strong>
                  <span>
                    {group.memberCount} {group.memberCount === 1 ? "member" : "members"}
                  </span>
                </div>
                <div className="detail-club-row">
                  {film.addedBy ? (
                    <span className="detail-muted">
                      Added by {film.addedBy} · {formatDate(film.addedAt)}
                    </span>
                  ) : null}
                  <span className="detail-chip">{watched ? "Watched" : "Up next"}</span>
                </div>
              </div>
            </section>
          </div>

          <div className="detail-footer">
            <Button onClick={onScore}>
              <Star size={15} />
              {watched
                ? film.yourScore === null
                  ? "Add your score"
                  : "Update your score"
                : "Mark watched"}
            </Button>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

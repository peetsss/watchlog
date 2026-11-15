import { Dialog } from "@base-ui/react/dialog";
import { Check, Eye, Star, X } from "lucide-react";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { YOU, type Group, type GroupFilm } from "../../data";
import { cx } from "../../lib/cx";
import { useSheetSwipe } from "../../lib/useSheetSwipe";
import { filmAverage, movieForFilm, scoredMembers } from "./score";

export function GroupFilmSheet({
  group,
  film,
  open,
  onOpenChange,
  onScore,
}: {
  group: Group;
  film: GroupFilm | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onScore: () => void;
}) {
  const swipe = useSheetSwipe(open, () => onOpenChange(false));
  const movie = movieForFilm(film);
  if (!film || !movie) return null;

  const scored = scoredMembers(group, film);
  const average = filmAverage(group, film);
  const yourScore = film.scores[YOU];
  const watched = film.status === "watched";
  const addedBy = group.members.find((person) => person.id === film.addedBy);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="detail-overlay" />
        <Dialog.Popup className="detail-sheet">
          <Dialog.Description className="sr-only">
            Film details for {movie.title}, the club's scores and watchlist status.
          </Dialog.Description>

          <div className="detail-hero" {...swipe}>
            <div
              className="detail-backdrop"
              style={{ backgroundImage: `url(${movie.backdrop})` }}
              aria-hidden="true"
            />
            <div className="detail-hero-scrim" aria-hidden="true" />
            <Dialog.Close type="button" className="icon-button detail-close" aria-label="Close film details">
              <X size={18} />
            </Dialog.Close>

            <div className="detail-heading">
              <div className="detail-poster">
                <img src={movie.poster} alt={`${movie.title} poster`} />
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
                  {movie.year} · {movie.runtime} min · {movie.genres.join(", ")}
                </p>
                {movie.tagline ? <p className="detail-tagline">“{movie.tagline}”</p> : null}
                {watched && average !== null ? (
                  <span className="detail-chip is-positive group-detail-score-chip">
                    <Star size={11} fill="currentColor" aria-hidden="true" /> {average.toFixed(1)} club
                    score
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
              {scored.length ? (
                <>
                  <div className="group-score-summary">
                    <strong>{average?.toFixed(1)}</strong>
                    <span>
                      from {scored.length} {scored.length === 1 ? "score" : "scores"}
                    </span>
                  </div>
                  <ul className="group-score-list">
                    {scored.map(({ person, score }) => (
                      <li key={person.id} className={cx(person.id === YOU && "is-you")}>
                        <Avatar person={person} size={28} />
                        <span className="group-score-name">
                          {person.name}
                          {person.id === YOU ? <em>You</em> : null}
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
                  {yourScore === undefined ? (
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
              <p>{movie.description}</p>
            </section>

            <section className="detail-section">
              <h3>The credits</h3>
              <dl className="detail-credits">
                <div>
                  <dt>Director</dt>
                  <dd>{movie.director}</dd>
                </div>
                <div>
                  <dt>Writers</dt>
                  <dd>{movie.writers.join(", ")}</dd>
                </div>
                <div>
                  <dt>Cast</dt>
                  <dd>{movie.cast.join(", ")}</dd>
                </div>
                <div>
                  <dt>Language</dt>
                  <dd>{movie.language}</dd>
                </div>
              </dl>
            </section>

            <section className="detail-section">
              <h3>In the club</h3>
              <div className="detail-club">
                <div className="detail-club-head">
                  <strong>{group.name}</strong>
                  <span>
                    {group.members.length} {group.members.length === 1 ? "member" : "members"}
                  </span>
                </div>
                <div className="detail-club-row">
                  {addedBy ? (
                    <span className="detail-muted">
                      Added by {addedBy.name} · {film.addedAt}
                    </span>
                  ) : null}
                  {film.watchedOn ? (
                    <span className="detail-muted">Watched {film.watchedOn}</span>
                  ) : (
                    <span className="detail-chip">Up next</span>
                  )}
                </div>
              </div>
            </section>
          </div>

          <div className="detail-footer">
            <Button onClick={onScore}>
              <Star size={15} />
              {watched
                ? yourScore === undefined
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

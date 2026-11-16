import { useEffect, useState } from "react";
import { ArrowRight, Check, Film, Info, Loader2, Sparkles } from "lucide-react";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { RoomBackdrop } from "../../components/RoomBackdrop";
import { movieById, type Movie } from "../../data";
import { cx } from "../../lib/cx";
import { useLobby } from "../../state/Lobby";
import "./premiere.css";

export function FinalRoom({
  onOpenFilm,
  onLeave,
}: {
  onOpenFilm: (movieId: string, trigger?: HTMLElement | null) => void;
  onLeave: () => void;
}) {
  const { lobby, pick, revealWinner, restartNight } = useLobby();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const myPick = lobby ? (lobby.picks[lobby.youId] ?? null) : null;
  const picksRevealed = Boolean(lobby?.picksRevealed);

  useEffect(() => {
    if (myPick) setSelectedId(myPick);
  }, [myPick]);

  if (!lobby) return null;

  const finalists = lobby.shortlist
    .map((id) => movieById(id))
    .filter((movie): movie is Movie => Boolean(movie));

  if (!finalists.length) {
    return (
      <section className="final-room is-empty">
        <RoomBackdrop image={movieById("grand-budapest")?.backdrop} />
        <div className="final-inner final-empty-inner">
          <EmptyState
            icon={<Film size={24} />}
            title="No film made the cut."
            body="Not one film got a unanimous yes tonight. That's allowed. Try again with a smaller pool, or call it a night."
            action={
              <div className="empty-actions">
                <Button onClick={restartNight}>Start over</Button>
                <Button variant="ghost" onClick={onLeave}>
                  Back home
                </Button>
              </div>
            }
          />
        </div>
      </section>
    );
  }

  const selectedMovie = selectedId ? movieById(selectedId) : null;

  return (
    <section className="premiere-final">
      <RoomBackdrop image={finalists[0]?.backdrop} />

      <div className="premiere-final-inner">
        <header className="premiere-final-head">
          <p className="eyebrow">
            Final round <span className="dot-sep">·</span> {lobby.groupName}
          </p>
          <h1 className="display">
            {finalists.length === 1 ? "One film." : "Two films."} <em>One stage.</em>
          </h1>
          <p className="lede">
            {finalists.length === 1
              ? "One film made it through. It still needs the room's pick."
              : `${finalists.length} films made it through. Choose the one you want to see; the room will do the rest.`}
          </p>
        </header>

        <div className="premiere-lineup">
          {finalists.map((movie, index) => {
            const selected = selectedId === movie.id;
            return (
              <article
                key={movie.id}
                className={cx("premiere-card", selected && "is-selected", myPick && "is-locked")}
              >
                <button
                  type="button"
                  className="premiere-select"
                  onClick={() => {
                    if (!myPick) setSelectedId(movie.id);
                  }}
                  aria-pressed={selected}
                  aria-label={`Select ${movie.title}`}
                  disabled={Boolean(myPick)}
                >
                  <span className="premiere-num">{String(index + 1).padStart(2, "0")}</span>
                  <span className="premiere-poster">
                    <img src={movie.poster} alt={`${movie.title} poster`} />
                    {selected ? (
                      <span className="premiere-check" aria-hidden="true">
                        <Check size={14} strokeWidth={2.8} />
                      </span>
                    ) : null}
                  </span>
                  <span className="premiere-card-copy">
                    <strong>{movie.title}</strong>
                    <span>
                      {movie.year} · {movie.runtime} min · {movie.genres.slice(0, 2).join(", ")}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="premiere-about"
                  onClick={(event) => onOpenFilm(movie.id, event.currentTarget)}
                  aria-label={`About ${movie.title}`}
                >
                  <Info size={13} /> About
                </button>
              </article>
            );
          })}
        </div>
      </div>

      <div className="premiere-bar">
        <div className="premiere-status" role="status" aria-live="polite">
          {!myPick ? (
            <>
              <Sparkles size={15} aria-hidden="true" />
              <span>{selectedId ? "Lock it in when you're ready." : "Pick a film to begin."}</span>
            </>
          ) : !picksRevealed ? (
            <>
              <Loader2 className="spin" size={15} aria-hidden="true" />
              <span>Locked in. The room is finishing its picks…</span>
            </>
          ) : (
            <>
              <Check size={15} aria-hidden="true" />
              <span>Everyone has picked. Roll the premiere.</span>
            </>
          )}
        </div>

        {!myPick ? (
          <Button onClick={() => selectedId && pick(selectedId)} disabled={!selectedId}>
            Lock in {selectedMovie?.title ?? "your film"} <ArrowRight size={15} />
          </Button>
        ) : (
          <Button onClick={revealWinner} disabled={!picksRevealed}>
            Roll the pick <ArrowRight size={15} />
          </Button>
        )}
      </div>
    </section>
  );
}

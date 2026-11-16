import { Check, Film, Home, Info, Loader2, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { RoomBackdrop } from "../../components/RoomBackdrop";
import type { LobbyView } from "../../lib/adapters";
import { cx } from "../../lib/cx";
import "./premiere.css";

export function WinnerRoom({
  lobby,
  onOpenFilm,
  onLeave,
  onRestart,
  pendingAction,
}: {
  lobby: LobbyView;
  onOpenFilm: (movieId: number, trigger?: HTMLElement | null) => void;
  onLeave: () => void;
  onRestart: () => void;
  pendingAction: string | null;
}) {
  const winner = lobby.winner;

  if (!winner) {
    return (
      <section className="winner-room is-empty">
        <RoomBackdrop />
        <div className="final-inner final-empty-inner">
          <EmptyState
            icon={<Film size={24} />}
            title="No pick tonight."
            body="The room didn't land on a film. Some nights are like that. The next one is still yours."
            action={
              <div className="empty-actions">
                {lobby.capabilities.canRestart ? (
                  <Button onClick={onRestart} disabled={pendingAction === "restart"}>
                    {pendingAction === "restart" ? (
                      <>
                        <Loader2 className="spin" size={15} /> Starting…
                      </>
                    ) : (
                      "Start over"
                    )}
                  </Button>
                ) : null}
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

  const winnerFinalist = lobby.finalists.find(
    (finalist) => finalist.movie.id === winner.id,
  );
  const winnerPicks = winnerFinalist?.pickCount ?? 0;

  return (
    <section className="premiere-winner">
      <RoomBackdrop image={winner.backdrop} className="is-winner" />

      <div className="premiere-winner-inner">
        <div className="premiere-winner-poster">
          {winner.poster ? (
            <img src={winner.poster} alt={`${winner.title} poster`} />
          ) : (
            <span className="movie-poster-fallback" aria-hidden="true">
              <Film size={28} />
            </span>
          )}
        </div>

        <div className="premiere-winner-copy">
          <p className="eyebrow">
            Tonight's pick · {lobby.groupName ?? "Open room"}
          </p>
          <h1 className="display premiere-title">{winner.title}</h1>
          <p className="premiere-meta">
            {[winner.year, winner.runtime ? `${winner.runtime} min` : null, winner.genres.join(", "), winner.director ? `Dir. ${winner.director}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="premiere-synopsis">{winner.description}</p>

          <button
            type="button"
            className="text-button premiere-about-film"
            onClick={(event) => onOpenFilm(winner.id, event.currentTarget)}
          >
            <Info size={14} /> About the film
          </button>

          <div className="premiere-picked">
            <Users size={15} aria-hidden="true" />
            <span>
              {winnerPicks} of {lobby.playerCount} picked it
            </span>
          </div>

          <div className="premiere-winner-actions">
            {lobby.groupId ? (
              <Link
                to={`/groups/${lobby.groupId}`}
                className="btn btn-secondary btn-md"
              >
                <Check size={16} /> On the watchlist
              </Link>
            ) : null}
            <Button variant="secondary" onClick={onLeave}>
              <Home size={16} /> Back home
            </Button>
          </div>

          {lobby.capabilities.canRestart ? (
            <button
              type="button"
              className="text-button premiere-again"
              onClick={onRestart}
              disabled={pendingAction === "restart"}
            >
              {pendingAction === "restart" ? "Starting another night…" : "Start another night"}
            </button>
          ) : null}

          {lobby.tie ? (
            <p className="premiere-tie">
              A tie. The shortlist order broke it — next time the room should settle it with one
              more vote.
            </p>
          ) : null}

          <div className="premiere-winner-tally" aria-label="How the shortlist finished">
            {lobby.finalists.map((finalist) => (
              <span
                key={finalist.movie.id}
                className={cx(
                  "premiere-chip",
                  finalist.movie.id === winner.id && "is-winner",
                )}
              >
                {finalist.movie.title} <strong>{finalist.pickCount ?? 0}</strong>
              </span>
            ))}
          </div>
        </div>
      </div>

      <p className="premiere-credit">The room has spoken.</p>
    </section>
  );
}

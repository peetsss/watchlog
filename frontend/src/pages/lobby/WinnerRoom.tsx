import { useState } from "react";
import { Check, Film, Home, Info, Plus } from "lucide-react";
import { AvatarStack } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { RoomBackdrop } from "../../components/RoomBackdrop";
import { movieById, movies, winnerCounts } from "../../data";
import { cx } from "../../lib/cx";
import { useGroups } from "../../state/Groups";
import { useLobby } from "../../state/Lobby";
import { useToast } from "../../state/Toast";
import "./premiere.css";

export function WinnerRoom({
  onOpenFilm,
  onLeave,
}: {
  onOpenFilm: (movieId: string, trigger?: HTMLElement | null) => void;
  onLeave: () => void;
}) {
  const { lobby, restartNight } = useLobby();
  const { groups, addMovieToGroup } = useGroups();
  const { showToast } = useToast();
  const [added, setAdded] = useState(false);

  if (!lobby) return null;

  const winner = movieById(lobby.winnerId);

  if (!winner) {
    return (
      <section className="winner-room is-empty">
        <RoomBackdrop image={movies["past-lives"].backdrop} />
        <div className="final-inner final-empty-inner">
          <EmptyState
            icon={<Film size={24} />}
            title="No pick tonight."
            body="The room didn't land on a film. Some nights are like that. The next one is still yours."
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

  const picksFor = lobby.players.filter((person) => lobby.picks[person.id] === winner.id);
  const counts = winnerCounts(lobby);
  const isHost = lobby.hostId === lobby.youId;
  const group = lobby.groupId ? groups.find((entry) => entry.id === lobby.groupId) : null;
  const isAdded = added || Boolean(group?.watchlist.some((entry) => entry.id === winner.id));

  const handleAdd = () => {
    if (group) addMovieToGroup(group.id, winner);
    setAdded(true);
    showToast(`${winner.title} added to ${lobby.groupName}.`);
  };

  return (
    <section className="premiere-winner">
      <RoomBackdrop image={winner.backdrop} className="is-winner" />

      <div className="premiere-winner-inner">
        <div className="premiere-winner-poster">
          <img src={winner.poster} alt={`${winner.title} poster`} />
        </div>

        <div className="premiere-winner-copy">
          <p className="eyebrow">Tonight's pick · {lobby.groupName}</p>
          <h1 className="display premiere-title">{winner.title}</h1>
          <p className="premiere-meta">
            {winner.year} · {winner.runtime} min · {winner.genres.join(", ")} · Dir.{" "}
            {winner.director}
          </p>
          <p className="premiere-synopsis">{winner.synopsis}</p>

          <button
            type="button"
            className="text-button premiere-about-film"
            onClick={(event) => onOpenFilm(winner.id, event.currentTarget)}
          >
            <Info size={14} /> About the film
          </button>

          <div className="premiere-picked">
            <AvatarStack people={picksFor} size={28} />
            <span>
              {picksFor.length} of {lobby.players.length} picked it
            </span>
          </div>

          <div className="premiere-winner-actions">
            {lobby.privacy === "group" ? (
              <Button onClick={handleAdd} disabled={isAdded}>
                {isAdded ? (
                  <>
                    <Check size={16} /> On the watchlist
                  </>
                ) : (
                  <>
                    <Plus size={16} /> Add to watchlist
                  </>
                )}
              </Button>
            ) : null}
            <Button variant="secondary" onClick={onLeave}>
              <Home size={16} /> Back home
            </Button>
          </div>

          {isHost ? (
            <button
              type="button"
              className="text-button premiere-again"
              onClick={() => {
                restartNight();
                showToast("Room reset. Ready when you are.");
              }}
            >
              Start another night
            </button>
          ) : null}

          {lobby.tie ? (
            <p className="premiere-tie">
              A tie. The shortlist order broke it — next time the room should settle it with one more
              vote.
            </p>
          ) : null}

          <div className="premiere-winner-tally" aria-label="How the shortlist finished">
            {counts.map(({ movieId, count }) => {
              const movie = movieById(movieId);
              if (!movie) return null;
              return (
                <span
                  key={movieId}
                  className={cx("premiere-chip", movieId === winner.id && "is-winner")}
                >
                  {movie.title} <strong>{count}</strong>
                </span>
              );
            })}
          </div>
        </div>
      </div>

      <p className="premiere-credit">The room has spoken.</p>
    </section>
  );
}

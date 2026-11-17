import { useEffect, useState } from "react";
import { ArrowRight, Check, Film, Info, Loader2, Sparkles } from "lucide-react";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { RoomBackdrop } from "../../components/RoomBackdrop";
import { WhereToWatch } from "../../components/WhereToWatch";
import type { LobbyView } from "../../lib/adapters";
import type { LobbyAction } from "../../lib/api-lobby";
import { cx } from "../../lib/cx";
import "./premiere.css";

export function FinalRoom({
  lobby,
  send,
  pendingAction,
  onOpenFilm,
  onLeave,
}: {
  lobby: LobbyView;
  send: (action: LobbyAction, payload?: Record<string, unknown>) => Promise<boolean>;
  pendingAction: string | null;
  onOpenFilm: (movieId: number, trigger?: HTMLElement | null) => void;
  onLeave: () => void;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(lobby.viewerPick);

  useEffect(() => {
    if (lobby.viewerPick !== null) setSelectedId(lobby.viewerPick);
  }, [lobby.viewerPick]);

  const finalists = lobby.finalists;
  const myPick = lobby.viewerPick;
  const picksRevealed = lobby.picksRevealed;
  const canFinalize = lobby.capabilities.canFinalize;
  const selectedFinalist = finalists.find((finalist) => finalist.movie.id === selectedId);

  if (!finalists.length) {
    return (
      <section className="final-room is-empty">
        <RoomBackdrop image={undefined} />
        <div className="final-inner final-empty-inner">
          <EmptyState
            icon={<Film size={24} />}
            title="No film made the cut."
            body="Not one film got a unanimous yes tonight. That's allowed. Call it a night and try again."
            action={
              <Button variant="ghost" onClick={onLeave}>
                Back home
              </Button>
            }
          />
        </div>
      </section>
    );
  }

  return (
    <section className="premiere-final">
      <RoomBackdrop image={finalists[0]?.movie.backdrop ?? undefined} />

      <div className="premiere-final-inner">
        <header className="premiere-final-head">
          <p className="eyebrow">
            Final round <span className="dot-sep">·</span>{" "}
            {lobby.groupName ?? "Open room"}
          </p>
          <h1 className="display">
            {finalists.length} {finalists.length === 1 ? "film" : "films"}. <em>One stage.</em>
          </h1>
          <p className="lede">
            {finalists.length === 1
              ? "One film made it through. It still needs the room's pick."
              : `${finalists.length} films made it through. Choose the one you want to see; the room will do the rest.`}
          </p>
        </header>

        <div className="premiere-lineup">
          {finalists.map((finalist, index) => {
            const movie = finalist.movie;
            const selected = selectedId === movie.id;
            return (
              <article
                key={movie.id}
                className={cx(
                  "premiere-card",
                  selected && "is-selected",
                  myPick !== null && "is-locked",
                )}
              >
                <button
                  type="button"
                  className="premiere-select"
                  onClick={() => {
                    if (myPick === null) setSelectedId(movie.id);
                  }}
                  aria-pressed={selected}
                  aria-label={`Select ${movie.title}`}
                  disabled={myPick !== null}
                >
                  <span className="premiere-num">{String(index + 1).padStart(2, "0")}</span>
                  <span className="premiere-poster">
                    {movie.poster ? (
                      <img src={movie.poster} alt={`${movie.title} poster`} />
                    ) : (
                      <span className="movie-poster-fallback" aria-hidden="true">
                        <Film size={22} />
                      </span>
                    )}
                    {selected ? (
                      <span className="premiere-check" aria-hidden="true">
                        <Check size={14} strokeWidth={2.8} />
                      </span>
                    ) : null}
                  </span>
                  <span className="premiere-card-copy">
                    <strong>{movie.title}</strong>
                    <span>
                      {[movie.year, movie.runtime ? `${movie.runtime} min` : null, movie.genres.slice(0, 2).join(", ")]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    {picksRevealed && finalist.pickCount !== null ? (
                      <span className="premiere-pick-count">
                        {finalist.pickCount} {finalist.pickCount === 1 ? "pick" : "picks"}
                      </span>
                    ) : null}
                  </span>
                </button>
                <WhereToWatch watch={finalist.watch} compact />
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
          {myPick === null ? (
            <>
              <Sparkles size={15} aria-hidden="true" />
              <span>
                {selectedId ? "Lock it in when you're ready." : "Pick a film to begin."}
              </span>
            </>
          ) : !picksRevealed ? (
            <>
              <Loader2 className="spin" size={15} aria-hidden="true" />
              <span>
                Locked in. {lobby.submittedCount} of {lobby.playerCount} picks are in
                {lobby.viewerIsHost ? " — you can roll when you're ready." : "."}
              </span>
            </>
          ) : (
            <>
              <Check size={15} aria-hidden="true" />
              <span>Everyone has picked. Roll the premiere.</span>
            </>
          )}
        </div>

        {myPick === null ? (
          <Button
            onClick={() =>
              selectedId !== null && void send("pick", { movie_id: selectedId })
            }
            disabled={selectedId === null || pendingAction === "pick"}
          >
            {pendingAction === "pick" ? (
              <>
                <Loader2 className="spin" size={15} /> Locking in…
              </>
            ) : (
              <>
                Lock in {selectedFinalist?.movie.title ?? "your film"} <ArrowRight size={15} />
              </>
            )}
          </Button>
        ) : canFinalize ? (
          <Button
            onClick={() => void send("finalize")}
            disabled={pendingAction === "finalize"}
          >
            {pendingAction === "finalize" ? (
              <>
                <Loader2 className="spin" size={15} /> Rolling…
              </>
            ) : picksRevealed ? (
              <>
                Roll the pick <ArrowRight size={15} />
              </>
            ) : (
              <>
                Roll with {lobby.submittedCount} of {lobby.playerCount} picks{" "}
                <ArrowRight size={15} />
              </>
            )}
          </Button>
        ) : (
          <Button disabled>Waiting for the room</Button>
        )}
      </div>
    </section>
  );
}

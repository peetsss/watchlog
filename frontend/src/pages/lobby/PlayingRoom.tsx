import { useEffect } from "react";
import { ArrowRight, Check, Eye, Info, Loader2, X } from "lucide-react";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import type { LobbyView, LobbyVote } from "../../lib/adapters";
import { VOTE_TO_API } from "../../lib/adapters";
import type { LobbyAction } from "../../lib/api-lobby";
import { cx } from "../../lib/cx";
import "./reel.css";

const VOTE_LABEL: Record<LobbyVote, string> = {
  in: "I'm in",
  seen: "Seen it",
  out: "Not for me",
};

const VOTE_OPTIONS: Array<{
  choice: LobbyVote;
  label: string;
  help: string;
  icon: typeof Check;
}> = [
  { choice: "in", label: "I'm in", help: "Put it on the shortlist", icon: Check },
  { choice: "seen", label: "Seen it", help: "Already watched", icon: Eye },
  { choice: "out", label: "Not for me", help: "Skip it tonight", icon: X },
];

function ballotMark(choice: LobbyVote) {
  if (choice === "in") return <Check size={9} strokeWidth={3.2} />;
  if (choice === "seen") return <Eye size={9} strokeWidth={2.8} />;
  return <X size={9} strokeWidth={3.2} />;
}

export function PlayingRoom({
  lobby,
  send,
  pendingAction,
  onOpenFilm,
}: {
  lobby: LobbyView;
  send: (action: LobbyAction, payload?: Record<string, unknown>) => Promise<boolean>;
  pendingAction: string | null;
  onOpenFilm: (movieId: number, trigger?: HTMLElement | null) => void;
}) {
  const movie = lobby.currentMovie;

  useEffect(() => {
    if (!movie || lobby.revealed || lobby.viewerVote) return;

    const handleKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
      if (document.querySelector('[role="dialog"]')) return;
      const option = VOTE_OPTIONS[Number(event.key) - 1];
      if (!option) return;
      void send("vote", {
        movie_id: movie.id,
        choice: VOTE_TO_API[option.choice],
      });
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [lobby.revealed, lobby.viewerVote, movie, send]);

  if (!movie) {
    return (
      <section className="reel-room">
        <div className="reel-scrim" aria-hidden="true" />
        <div className="reel-content">
          <p className="session-loading" role="status">
            <Loader2 className="spin" size={17} aria-hidden="true" />
            <span>Loading the next movie…</span>
          </p>
        </div>
      </section>
    );
  }

  const myVote = lobby.viewerVote;
  const reveal = lobby.revealed;
  const tally = lobby.voteTally;
  const segments = Math.min(Math.max(lobby.poolSize, 1), 12);
  const activeSegment = Math.min(
    segments - 1,
    Math.floor((lobby.poolIndex / Math.max(lobby.poolSize, 1)) * segments),
  );

  return (
    <section className="reel-room">
      <div
        className="reel-bg is-active"
        style={movie.backdrop ? { backgroundImage: `url(${movie.backdrop})` } : undefined}
        aria-hidden="true"
      />
      <div className="reel-scrim" aria-hidden="true" />

      <div className="reel-content">
        <header className="reel-head">
          <p className="eyebrow">
            Movie {lobby.roundNumber} of {lobby.poolSize} <span className="dot-sep">·</span>{" "}
            {lobby.playerCount} in the room
          </p>
          <h1 className="display">The reel.</h1>
          <p className="lede">One movie at a time. The next one is already waiting.</p>
        </header>

        <div className="reel-deck">
          <article className="reel-card is-current">
            <div className="reel-poster">
              {movie.poster ? (
                <img src={movie.poster} alt={`${movie.title} poster`} draggable={false} />
              ) : (
                <span className="movie-poster-fallback" aria-hidden="true">
                  <Info size={24} />
                </span>
              )}
              <button
                type="button"
                className="reel-info"
                onClick={(event) => onOpenFilm(movie.id, event.currentTarget)}
                aria-label={`About ${movie.title}`}
              >
                <Info size={14} />
              </button>

              {myVote && !reveal ? (
                <span className="reel-stamp is-waiting">
                  <Loader2 className="spin" size={14} /> Vote in — waiting
                </span>
              ) : null}

              {reveal ? (
                <span className={cx("reel-stamp", lobby.shortlisted ? "is-yes" : "is-no")}>
                  {lobby.shortlisted ? <Check size={14} /> : <X size={14} />}
                  {lobby.shortlisted ? "On the shortlist" : "Skipped tonight"}
                </span>
              ) : null}
            </div>

            <div className="reel-copy">
              <h2 className="display">{movie.title}</h2>
              <p>
                {[movie.year, movie.runtime ? `${movie.runtime} min` : null, movie.genres.join(", ")]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <button
                type="button"
                className="text-button reel-about"
                onClick={(event) => onOpenFilm(movie.id, event.currentTarget)}
              >
                <Info size={13} /> About the movie
              </button>
            </div>
          </article>
        </div>

        <div className="reel-progress" aria-hidden="true">
          {Array.from({ length: segments }, (_, index) => (
            <span
              key={index}
              className={cx(
                "reel-dot",
                index === activeSegment && "is-active",
                index < activeSegment && "is-past",
              )}
            />
          ))}
        </div>

        <div className="reel-panel">
          {!myVote && !reveal ? (
            <>
              <div className="reel-call">
                <span className="section-kicker">Your call</span>
                <p>Are you in?</p>
              </div>
              <div className="reel-choices">
                {VOTE_OPTIONS.map((option, index) => {
                  const Icon = option.icon;
                  return (
                    <button
                      key={option.choice}
                      type="button"
                      className={cx("reel-choice", option.choice === "in" && "is-in")}
                      onClick={() =>
                        void send("vote", {
                          movie_id: movie.id,
                          choice: VOTE_TO_API[option.choice],
                        })
                      }
                      disabled={pendingAction === "vote"}
                    >
                      <Icon size={17} strokeWidth={2.2} aria-hidden="true" />
                      <span>{option.label}</span>
                      <kbd>{index + 1}</kbd>
                    </button>
                  );
                })}
              </div>
              <p className="reel-hint">
                A unanimous yes puts it on the shortlist. Votes reveal together.
              </p>
            </>
          ) : myVote && !reveal ? (
            <div className="reel-wait" role="status" aria-live="polite">
              <Loader2 className="spin" size={18} aria-hidden="true" />
              <p>
                You chose <strong>{VOTE_LABEL[myVote]}</strong>. Waiting for the room…
              </p>
            </div>
          ) : (
            <div
              className={cx("reel-result", lobby.shortlisted ? "is-yes" : "is-no")}
              role="status"
              aria-live="polite"
            >
              <div className="reel-result-copy">
                <span className="section-kicker">
                  {lobby.shortlisted ? "On the shortlist" : "Skipped tonight"}
                </span>
                <h2 className="display">
                  {lobby.shortlisted ? "Everyone was in." : "Not everyone was in."}
                </h2>
                <p>
                  {lobby.shortlisted
                    ? `${movie.title} moves to the shortlist.`
                    : `${tally?.interested ?? 0} of ${tally?.total ?? lobby.playerCount} were in. A movie needs every vote.`}
                </p>
              </div>

              <div className="reel-ballot-strip" aria-label="How the room voted">
                {lobby.ballot.map(({ person, choice }) => (
                  <span
                    key={person.id}
                    className={cx("reel-ballot-line", `is-${choice}`)}
                    role="img"
                    aria-label={`${person.name}: ${VOTE_LABEL[choice]}`}
                    title={`${person.name}: ${VOTE_LABEL[choice]}`}
                  >
                    <Avatar person={person} size={26} />
                    <span className="reel-ballot-mark" aria-hidden="true">
                      {ballotMark(choice)}
                    </span>
                  </span>
                ))}
              </div>

              <Button
                onClick={() => void send("next-round")}
                disabled={pendingAction === "next-round"}
              >
                {pendingAction === "next-round" ? (
                  <>
                    <Loader2 className="spin" size={15} /> Moving on…
                  </>
                ) : (
                  <>
                    {lobby.remainingCount <= 1 ? "Finish the reel" : "Next movie"}{" "}
                    <ArrowRight size={16} />
                  </>
                )}
              </Button>
            </div>
          )}

          {lobby.capabilities.canAdvance && !reveal ? (
            <button
              type="button"
              className="text-button subtle"
              onClick={() => void send("advance")}
              disabled={pendingAction === "advance"}
            >
              {pendingAction === "advance" ? "Skipping…" : "Skip this movie"}
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

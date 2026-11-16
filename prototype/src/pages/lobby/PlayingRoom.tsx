import { useEffect, useRef } from "react";
import { ArrowRight, Check, Eye, Info, Loader2, X } from "lucide-react";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { crowdVote, movieById, PLAY_ORDER, type VoteChoice } from "../../data";
import { cx } from "../../lib/cx";
import { useLobby } from "../../state/Lobby";
import "./reel.css";

const VOTE_LABEL: Record<VoteChoice, string> = {
  in: "I'm in",
  seen: "Seen it",
  out: "Not for me",
};

const VOTE_OPTIONS: Array<{ choice: VoteChoice; label: string; help: string; icon: typeof Check }> = [
  { choice: "in", label: "I'm in", help: "Put it on the shortlist", icon: Check },
  { choice: "seen", label: "Seen it", help: "Already watched", icon: Eye },
  { choice: "out", label: "Not for me", help: "Skip it tonight", icon: X },
];

function ballotMark(choice: VoteChoice) {
  if (choice === "in") return <Check size={9} strokeWidth={3.2} />;
  if (choice === "seen") return <Eye size={9} strokeWidth={2.8} />;
  return <X size={9} strokeWidth={3.2} />;
}

export function PlayingRoom({
  onOpenFilm,
}: {
  onOpenFilm: (movieId: string, trigger?: HTMLElement | null) => void;
}) {
  const { lobby, vote, nextFilm } = useLobby();
  const deckRef = useRef<HTMLDivElement | null>(null);
  const drag = useRef({
    pointerId: null as number | null,
    startX: 0,
    startY: 0,
    lastX: 0,
    lastY: 0,
    lastT: 0,
    vx: 0,
    active: false,
    started: false,
  });

  const resetDrag = () => {
    const deck = deckRef.current;
    const state = drag.current;
    state.active = false;
    state.started = false;
    if (deck) {
      deck.classList.remove("is-dragging");
      deck.style.setProperty("--deck-drag-x", "0px");
      if (state.pointerId !== null && deck.hasPointerCapture(state.pointerId)) {
        deck.releasePointerCapture(state.pointerId);
      }
    }
    state.pointerId = null;
    state.vx = 0;
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if ((event.target as HTMLElement).closest("button, a, input, select, textarea")) return;
    if (drag.current.active) return;

    drag.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      lastT: performance.now(),
      vx: 0,
      active: true,
      started: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    const deck = deckRef.current;
    if (!state.active || !deck || state.pointerId !== event.pointerId) return;

    const dx = event.clientX - state.startX;
    const dy = event.clientY - state.startY;

    if (!state.started) {
      if (Math.abs(dx) < 8 || Math.abs(dx) < Math.abs(dy)) return;
      state.started = true;
      deck.classList.add("is-dragging");
    }

    const now = performance.now();
    const dt = now - state.lastT;
    if (dt > 0) {
      state.vx = ((event.clientX - state.lastX) / dt) * 1000;
    }
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    state.lastT = now;

    // Forward drag follows the finger; dragging backwards peeks and resists.
    const forward = dx < 0;
    const offset = lobby?.reveal ? (forward ? dx : dx * 0.25) : dx * 0.2;
    deck.style.setProperty("--deck-drag-x", `${offset}px`);
    event.preventDefault();
  };

  const handlePointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    const deck = deckRef.current;
    if (!state.active || state.pointerId !== event.pointerId) return;

    const started = state.started;
    const dx = state.lastX - state.startX;
    const vx = state.vx;
    const projected = dx + (vx / 1000) * (0.998 / (1 - 0.998));
    const advance =
      Boolean(lobby?.reveal) &&
      started &&
      (dx < -72 || (projected < -120 && vx < -300));

    resetDrag();
    if (advance) nextFilm();
  };

  const handlePointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
    if (drag.current.pointerId !== event.pointerId) return;
    resetDrag();
  };

  useEffect(() => {
    if (!lobby || lobby.stage !== "playing" || lobby.reveal) return;
    const movieId = PLAY_ORDER[lobby.roundIndex];
    if (!movieId || lobby.votes[movieId]) return;

    const handleKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
      if (document.querySelector('[role="dialog"]')) return;
      if (event.key === "1") vote("in");
      if (event.key === "2") vote("seen");
      if (event.key === "3") vote("out");
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [lobby, vote]);

  if (!lobby || lobby.stage !== "playing") return null;

  const movieId = PLAY_ORDER[lobby.roundIndex];
  const movie = movieById(movieId);
  if (!movie) return null;

  const myVote = lobby.votes[movieId];
  const reveal = lobby.reveal;
  const isLast = lobby.roundIndex === PLAY_ORDER.length - 1;
  const ballot = lobby.players.map((person) => ({
    person,
    choice: person.id === lobby.youId ? (myVote ?? "in") : crowdVote(person.id, movieId),
  }));

  return (
    <section className="reel-room">
      {PLAY_ORDER.map((id, index) => {
        const film = movieById(id);
        return (
          <div
            key={id}
            className={cx("reel-bg", index === lobby.roundIndex && "is-active")}
            style={{ backgroundImage: film ? `url(${film.backdrop})` : undefined }}
            aria-hidden="true"
          />
        );
      })}
      <div className="reel-scrim" aria-hidden="true" />

      <div className="reel-content">
        <header className="reel-head">
          <p className="eyebrow">
            Film {lobby.roundIndex + 1} of {PLAY_ORDER.length} <span className="dot-sep">·</span>{" "}
            {lobby.players.length} in the room
          </p>
          <h1 className="display">The reel.</h1>
          <p className="lede">One film at a time. The next one is already waiting.</p>
        </header>

        <div
          ref={deckRef}
          className="reel-deck"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerCancel}
          onLostPointerCapture={() => {
            if (drag.current.active) resetDrag();
          }}
        >
          {PLAY_ORDER.map((id, index) => {
            const film = movieById(id);
            if (!film) return null;
            const offset = index - lobby.roundIndex;
            const current = offset === 0;
            const state =
              offset === 0 ? "is-current" : offset < 0 ? "is-prev" : offset === 1 ? "is-next" : "is-hidden";

            return (
              <article key={id} className={cx("reel-card", state)} aria-hidden={!current}>
                <div className="reel-poster">
                  <img
                    src={film.poster}
                    alt={current ? ` poster` : ""}
                    loading="lazy"
                    draggable={false}
                  />
                  {current ? (
                    <button
                      type="button"
                      className="reel-info"
                      onClick={(event) => onOpenFilm(film.id, event.currentTarget)}
                      aria-label={`About ${film.title}`}
                    >
                      <Info size={14} />
                    </button>
                  ) : null}

                  {current && myVote && !reveal ? (
                    <span className="reel-stamp is-waiting">
                      <Loader2 className="spin" size={14} /> Vote in — waiting
                    </span>
                  ) : null}

                  {current && reveal ? (
                    <span className={cx("reel-stamp", reveal.shortlisted ? "is-yes" : "is-no")}>
                      {reveal.shortlisted ? <Check size={14} /> : <X size={14} />}
                      {reveal.shortlisted ? "On the shortlist" : "Skipped tonight"}
                    </span>
                  ) : null}
                </div>

                <div className="reel-copy">
                  <h2 className="display">{film.title}</h2>
                  <p>
                    {film.year} · {film.runtime} min · {film.genres.join(", ")}
                  </p>
                  {current ? (
                    <button
                      type="button"
                      className="text-button reel-about"
                      onClick={(event) => onOpenFilm(film.id, event.currentTarget)}
                    >
                      <Info size={13} /> About the film
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>

        <div className="reel-progress" aria-hidden="true">
          {PLAY_ORDER.map((id, index) => (
            <span
              key={id}
              className={cx(
                "reel-dot",
                index === lobby.roundIndex && "is-active",
                index < lobby.roundIndex && "is-past",
              )}
            />
          ))}
        </div>

        <div className="reel-panel">
          {!myVote ? (
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
                      onClick={() => vote(option.choice)}
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
          ) : !reveal ? (
            <div className="reel-wait" role="status" aria-live="polite">
              <Loader2 className="spin" size={18} aria-hidden="true" />
              <p>
                You chose <strong>{VOTE_LABEL[myVote]}</strong>. Waiting for the room…
              </p>
            </div>
          ) : (
            <div
              className={cx("reel-result", reveal.shortlisted ? "is-yes" : "is-no")}
              role="status"
              aria-live="polite"
            >
              <div className="reel-result-copy">
                <span className="section-kicker">
                  {reveal.shortlisted ? "On the shortlist" : "Skipped tonight"}
                </span>
                <h2 className="display">
                  {reveal.shortlisted ? "Everyone was in." : "Not everyone was in."}
                </h2>
                <p>
                  {reveal.shortlisted
                    ? `${movie.title} moves to the shortlist.`
                    : `${reveal.inCount} of ${reveal.total} were in. A film needs every vote.`}
                </p>
              </div>

              <div className="reel-ballot-strip" aria-label="How the room voted">
                {ballot.map(({ person, choice }) => (
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

              <Button onClick={nextFilm}>
                {isLast ? "See the shortlist" : "Next film"} <ArrowRight size={16} />
              </Button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

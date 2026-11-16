import { Dialog } from "@base-ui/react/dialog";
import { Check, Eye, Film, Info, Loader2, Plus, X } from "lucide-react";
import type { ReactNode } from "react";
import {
  PLAY_ORDER,
  crowdVote,
  movieById,
  type Lobby,
  type Movie,
  type VoteChoice,
} from "../data";
import { cx } from "../lib/cx";
import { useGroups } from "../state/Groups";
import { useLobby } from "../state/Lobby";
import { useToast } from "../state/Toast";
import { useSheetSwipe } from "../lib/useSheetSwipe";
import { Avatar, AvatarStack } from "./Avatar";
import { Button } from "./Button";

const VOTE_LABEL: Record<VoteChoice, string> = {
  in: "I'm in",
  seen: "Seen it",
  out: "Not for me",
};

type RoomTone = "live" | "waiting" | "yes" | "skip" | "final" | "winner" | "quiet";

type RoomState = {
  label: string;
  title: string;
  copy: string;
  tone: RoomTone;
  icon: ReactNode;
};

function getRoomState(lobby: Lobby | null, movie: Movie): RoomState {
  if (!lobby) {
    return {
      label: "The room",
      title: "No room open.",
      copy: "Start or join a movie night to see this film in context.",
      tone: "quiet",
      icon: <Info size={16} />,
    };
  }

  const currentId = lobby.stage === "playing" ? PLAY_ORDER[lobby.roundIndex] : null;
  const isCurrent = currentId === movie.id;
  const isFinalist = lobby.shortlist.includes(movie.id);
  const isWinner = lobby.winnerId === movie.id;
  const reveal = lobby.reveal?.movieId === movie.id ? lobby.reveal : null;
  const myVote = lobby.votes[movie.id];
  const picksFor = lobby.players.filter((person) => lobby.picks[person.id] === movie.id);
  const pickedByYou = lobby.picks[lobby.youId] === movie.id;

  if (isWinner) {
    return {
      label: "Tonight's pick",
      title: `${picksFor.length} of ${lobby.players.length} picked it.`,
      copy: "The room has spoken.",
      tone: "winner",
      icon: <Check size={16} />,
    };
  }

  if (isCurrent) {
    if (reveal?.shortlisted) {
      return {
        label: "On the shortlist",
        title: "Everyone was in.",
        copy: `${movie.title} moves to the shortlist.`,
        tone: "yes",
        icon: <Check size={16} />,
      };
    }
    if (reveal) {
      return {
        label: "Skipped tonight",
        title: "Not everyone was in.",
        copy: `${reveal.inCount} of ${reveal.total} were in. It takes a unanimous yes.`,
        tone: "skip",
        icon: <X size={16} />,
      };
    }
    if (myVote) {
      return {
        label: "Vote in",
        title: "Waiting for the room…",
        copy: `You chose ${VOTE_LABEL[myVote]}. Votes reveal together.`,
        tone: "waiting",
        icon: <Loader2 className="spin" size={16} />,
      };
    }
    return {
      label: `Voting now · Film ${lobby.roundIndex + 1} of ${PLAY_ORDER.length}`,
      title: "The room is deciding.",
      copy: "A unanimous yes puts it on the shortlist. Votes reveal together.",
      tone: "live",
      icon: <Info size={16} />,
    };
  }

  if (isFinalist) {
    if (lobby.picksRevealed) {
      return {
        label: "Finalist",
        title: `${picksFor.length} of ${lobby.players.length} picks.`,
        copy: pickedByYou ? "This was your pick." : "The room has finished picking.",
        tone: "final",
        icon: <Film size={16} />,
      };
    }
    return {
      label: "Finalist",
      title: pickedByYou ? "Your pick." : "Picks stay hidden.",
      copy: pickedByYou
        ? "Locked in. Waiting for the room."
        : "Everyone picks one. Counts appear when the room is done.",
      tone: "final",
      icon: <Film size={16} />,
    };
  }

  return {
    label: "Not in this room",
    title: "This film isn't part of tonight.",
    copy: "You can still read about it, but there's nothing to vote on here.",
    tone: "quiet",
    icon: <Info size={16} />,
  };
}

export function MovieDetailSheet({
  movieId,
  open,
  onOpenChange,
}: {
  movieId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { lobby, vote, pick } = useLobby();
  const { groups, addMovieToGroup } = useGroups();
  const { showToast } = useToast();
  const swipe = useSheetSwipe(open, () => onOpenChange(false));
  const movie = movieById(movieId);

  if (!movie) return null;

  const group = lobby?.groupId ? groups.find((entry) => entry.id === lobby.groupId) : null;
  const onWatchlist = Boolean(group?.watchlist.some((entry) => entry.id === movie.id));
  const state = getRoomState(lobby, movie);
  const currentId = lobby?.stage === "playing" ? PLAY_ORDER[lobby.roundIndex] : null;
  const isCurrent = currentId === movie.id;
  const myVote = lobby?.votes[movie.id];
  const isFinalist = Boolean(lobby?.shortlist.includes(movie.id));
  const isWinner = Boolean(lobby?.winnerId === movie.id);
  const canVote = Boolean(lobby && isCurrent && !myVote && !lobby.reveal);
  const canPick = Boolean(
    lobby &&
      lobby.stage === "final" &&
      isFinalist &&
      !lobby.picks[lobby.youId] &&
      !lobby.picksRevealed,
  );
  const canAdd = Boolean(lobby && lobby.stage === "winner" && isWinner && group && !onWatchlist);
  const reveal = lobby?.reveal?.movieId === movie.id ? lobby.reveal : null;
  const picksFor = lobby?.players.filter((person) => lobby.picks[person.id] === movie.id) ?? [];

  const handleVote = (choice: VoteChoice) => {
    vote(choice);
    onOpenChange(false);
  };

  const handlePick = () => {
    pick(movie.id);
    onOpenChange(false);
  };

  const handleAdd = () => {
    if (!group) return;
    addMovieToGroup(group.id, movie);
    showToast(`${movie.title} added to ${group.name}.`);
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="detail-overlay" />
        <Dialog.Popup className="detail-sheet">
          <Dialog.Description className="sr-only">
            Film details for {movie.title} and its status in this room.
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
                <p className="eyebrow">About the film</p>
                <Dialog.Title className="detail-title">{movie.title}</Dialog.Title>
                <p className="detail-meta">
                  {movie.year} · {movie.runtime} min · {movie.genres.join(", ")}
                </p>
                {movie.tagline ? <p className="detail-tagline">“{movie.tagline}”</p> : null}
              </div>
            </div>
          </div>

          <div className="detail-body">
            <div className={cx("detail-status", `is-${state.tone}`)} role="status" aria-live="polite">
              <span className="detail-status-icon" aria-hidden="true">
                {state.icon}
              </span>
              <div className="detail-status-copy">
                <p className="detail-status-label">{state.label}</p>
                <p className="detail-status-title">{state.title}</p>
                <p className="detail-status-text">{state.copy}</p>
              </div>
            </div>

            {reveal && lobby ? (
              <div className="detail-ballot" aria-label="How the room voted">
                {lobby.players.map((person) => {
                  const choice =
                    person.id === lobby.youId
                      ? (myVote as VoteChoice)
                      : crowdVote(person.id, movie.id);
                  return (
                    <span key={person.id} className={cx("detail-ballot-item", `is-${choice}`)}>
                      <Avatar person={person} size={22} />
                      <span className="detail-ballot-name">{person.name.split(" ")[0]}</span>
                      <span className="detail-ballot-choice">{VOTE_LABEL[choice]}</span>
                    </span>
                  );
                })}
              </div>
            ) : null}

            {lobby && (isWinner || (isFinalist && lobby.picksRevealed)) ? (
              <div className="detail-picks">
                {picksFor.length ? (
                  <AvatarStack people={picksFor} size={24} />
                ) : (
                  <span className="detail-muted">No picks</span>
                )}
                <span>
                  {picksFor.length} of {lobby.players.length} picked it
                </span>
              </div>
            ) : null}

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
              {group ? (
                <div className="detail-club">
                  <div className="detail-club-head">
                    <strong>{group.name}</strong>
                    <span>
                      {group.members.length} {group.members.length === 1 ? "member" : "members"}
                    </span>
                  </div>
                  <div className="detail-club-row">
                    {onWatchlist ? (
                      <span className="detail-chip is-positive">
                        <Check size={11} /> On the watchlist
                      </span>
                    ) : (
                      <span className="detail-chip">Not on the watchlist yet</span>
                    )}
                    {group.lastNight?.movie.id === movie.id ? (
                      <span className="detail-muted">Last night · {group.lastNight.date}</span>
                    ) : null}
                  </div>
                </div>
              ) : (
                <p className="detail-muted">Open room. No group history for this film.</p>
              )}
            </section>
          </div>

          <div className="detail-footer">
            {canVote ? (
              <div className="detail-vote-actions">
                <Button onClick={() => handleVote("in")}>
                  <Check size={15} /> I'm in
                </Button>
                <Button variant="secondary" onClick={() => handleVote("seen")}>
                  <Eye size={15} /> Seen it
                </Button>
                <Button variant="secondary" onClick={() => handleVote("out")}>
                  <X size={15} /> Not for me
                </Button>
              </div>
            ) : canPick ? (
              <>
                <Button onClick={handlePick}>Pick this film</Button>
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Back to the room
                </Button>
              </>
            ) : canAdd ? (
              <>
                <Button onClick={handleAdd}>
                  <Plus size={15} /> Add to watchlist
                </Button>
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Back to the room
                </Button>
              </>
            ) : isWinner && group && onWatchlist ? (
              <>
                <Button variant="secondary" disabled>
                  <Check size={15} /> On the watchlist
                </Button>
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Back to the room
                </Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Back to the room
              </Button>
            )}
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

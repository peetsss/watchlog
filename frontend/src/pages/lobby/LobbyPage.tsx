import { useEffect, useRef } from "react";
import { Film, X } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState } from "../../components/EmptyState";
import { Button } from "../../components/Button";
import { MovieDetailSheet } from "../../components/MovieDetailSheet";
import { Wordmark } from "../../components/Wordmark";
import { movieById, stageLabel } from "../../data";
import { usePageTitle } from "../../lib/usePageTitle";
import { cx } from "../../lib/cx";
import { useGuestGate } from "../../state/GuestGate";
import { useLobby } from "../../state/Lobby";
import { useViewer } from "../../state/Viewer";
import { FinalRoom } from "./FinalRoom";
import { PlayingRoom } from "./PlayingRoom";
import { WaitingRoom } from "./WaitingRoom";
import { WinnerRoom } from "./WinnerRoom";

function ClosedRoom() {
  const navigate = useNavigate();

  return (
    <main className="closed-room">
      <div className="closed-room-top">
        <Wordmark />
      </div>
      <EmptyState
        icon={<Film size={24} />}
        title="This room has closed."
        body="The link may have expired, or the night already ended. The next one is never far away."
        action={
          <Button onClick={() => navigate("/")}>
            Back home
          </Button>
        }
      />
    </main>
  );
}

export function LobbyPage() {
  const { lobby } = useLobby();
  const { isGuest, person } = useViewer();
  const { request: requestAccount } = useGuestGate();
  const { id } = useParams<{ id: string }>();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const lastTrigger = useRef<HTMLElement | null>(null);
  const detailMovie = movieById(params.get("film"));

  const leaveRoom = () => {
    requestAccount({
      reason: "leave",
      onProceed: () => navigate("/"),
    });
  };

  usePageTitle(
    detailMovie
      ? detailMovie.title
      : lobby
        ? lobby.stage === "winner"
          ? "Tonight's pick"
          : "Movie night"
        : "Room closed",
  );

  useEffect(() => {
    if (!params.has("stage")) return;
    const next = new URLSearchParams(params);
    next.delete("stage");
    setParams(next, { replace: true });
    // Only strip the demo deep-link parameter once, on entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [lobby?.stage]);

  const openFilm = (movieId: string, trigger?: HTMLElement | null) => {
    lastTrigger.current = trigger ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const next = new URLSearchParams(params);
    next.set("film", movieId);
    setParams(next);
  };

  const closeFilm = () => {
    const trigger = lastTrigger.current;
    const next = new URLSearchParams(params);
    next.delete("film");
    setParams(next, { replace: true });
    window.setTimeout(() => {
      if (trigger?.isConnected) trigger.focus();
    }, 50);
  };

  if (!lobby || lobby.id !== id) return <ClosedRoom />;

  return (
    <main className={cx("lobby-shell", `stage-${lobby.stage}`)}>
      <header className="lobby-top">
        <Wordmark />
        <div className="room-meta">
          <span className="room-name">{lobby.groupName}</span>
          {isGuest ? (
            <span className="tag" aria-label={`Playing as ${person?.name ?? "a guest"}`}>
              Guest
            </span>
          ) : null}
          <span className="room-stage">{stageLabel(lobby)}</span>
        </div>
        <button
          type="button"
          className="room-exit"
          onClick={leaveRoom}
          aria-label="Leave the room and go home"
        >
          <X size={16} />
          <span>{lobby.stage === "winner" ? "Home" : "Leave"}</span>
        </button>
      </header>

      <div className="room-scene" key={lobby.stage}>
        {lobby.stage === "waiting" ? <WaitingRoom /> : null}
        {lobby.stage === "playing" ? <PlayingRoom onOpenFilm={openFilm} /> : null}
        {lobby.stage === "final" ? <FinalRoom onOpenFilm={openFilm} onLeave={leaveRoom} /> : null}
        {lobby.stage === "winner" ? (
          <WinnerRoom onOpenFilm={openFilm} onLeave={leaveRoom} />
        ) : null}
      </div>

      <MovieDetailSheet
        movieId={detailMovie?.id ?? null}
        open={Boolean(detailMovie)}
        onOpenChange={(next) => {
          if (!next) closeFilm();
        }}
      />
    </main>
  );
}

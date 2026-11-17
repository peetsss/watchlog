import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Film, Loader2, X } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState } from "../../components/EmptyState";
import { Button } from "../../components/Button";
import { MovieDetailSheet } from "../../components/MovieDetailSheet";
import { Wordmark } from "../../components/Wordmark";
import type { LobbyView } from "../../lib/adapters";
import { ApiError } from "../../lib/api";
import { useLobbyRoom } from "../../lib/useLobbyRoom";
import { usePageTitle } from "../../lib/usePageTitle";
import { cx } from "../../lib/cx";
import { useSession } from "../../state/Session";
import { useToast } from "../../state/Toast";
import { FinalRoom } from "./FinalRoom";
import { PlayingRoom } from "./PlayingRoom";
import { WaitingRoom } from "./WaitingRoom";
import { WinnerRoom } from "./WinnerRoom";

function stageLabel(lobby: LobbyView): string {
  if (lobby.status === "ready") return "Waiting room";
  if (lobby.status === "playing") return `Film ${lobby.roundNumber} of ${lobby.poolSize}`;
  if (lobby.status === "final_round") return "Final round";
  return "The pick";
}

function ClosedRoom({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <main className="closed-room">
      <div className="closed-room-top">
        <Wordmark />
      </div>
      <EmptyState icon={<Film size={24} />} title={title} body={body} action={action} />
    </main>
  );
}

export function LobbyPage() {
  const { id } = useParams<{ id: string }>();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { status, person } = useSession();
  const { showToast } = useToast();
  const lastTrigger = useRef<HTMLElement | null>(null);
  const room = useLobbyRoom(id);
  const lobby = room.lobby;

  const rawMovie = params.get("film");
  const detailMovieId =
    rawMovie !== null && Number.isFinite(Number(rawMovie)) ? Number(rawMovie) : null;

  usePageTitle(
    detailMovieId
      ? lobby?.currentMovie?.id === detailMovieId
        ? lobby.currentMovie.title
        : "Film"
      : lobby
        ? lobby.stage === "winner"
          ? "Tonight's pick"
          : "Movie night"
        : "Room closed",
  );

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [lobby?.stage]);

  useEffect(() => {
    if (room.restartedTo) {
      navigate(`/lobby/${room.restartedTo}`, { replace: true });
    }
  }, [navigate, room.restartedTo]);

  useEffect(() => {
    if (room.closed === "left") {
      navigate("/", { replace: true });
    }
  }, [navigate, room.closed]);

  useEffect(() => {
    if (room.actionMessage) showToast(room.actionMessage);
  }, [room.actionMessage, showToast]);

  useEffect(() => {
    if (room.error instanceof ApiError && room.error.status === 401) {
      void queryClient.invalidateQueries({ queryKey: ["session", "me"] });
    }
  }, [queryClient, room.error]);

  const openFilm = (movieId: number, trigger?: HTMLElement | null) => {
    lastTrigger.current =
      trigger ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const next = new URLSearchParams(params);
    next.set("film", String(movieId));
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

  const exitRoom = async () => {
    if (!lobby) {
      navigate("/");
      return;
    }
    if (lobby.status === "finished") {
      navigate("/");
      return;
    }
    const ok = lobby.viewerIsHost ? await room.end() : await room.leave();
    if (ok) navigate("/");
  };

  if (!lobby) {
    if (room.error instanceof ApiError && [403, 404].includes(room.error.status)) {
      return (
        <ClosedRoom
          title={room.error.status === 403 ? "This room is private." : "This room has closed."}
          body={
            room.error.status === 403
              ? "Group rooms are only open to their members. Ask the host for a group invite."
              : "The link may have expired, or the night already ended. The next one is never far away."
          }
          action={
            <Button onClick={() => navigate("/")}>
              Back home
            </Button>
          }
        />
      );
    }

    if (room.closed === "removed" || room.closed === "forbidden") {
      return (
        <ClosedRoom
          title="You're out of the room."
          body="Everyone who wasn't ready was removed when the host started. The next one is still yours."
          action={<Button onClick={() => navigate("/")}>Back home</Button>}
        />
      );
    }

    if (room.closed === "not_found") {
      return (
        <ClosedRoom
          title="This room has closed."
          body="The link may have expired, or the night already ended."
          action={<Button onClick={() => navigate("/")}>Back home</Button>}
        />
      );
    }

    if (room.error) {
      return (
        <ClosedRoom
          title="The room didn't load."
          body={room.error.message}
          action={<Button onClick={() => void room.refetch()}>Try again</Button>}
        />
      );
    }

    return (
      <main className="closed-room">
        <div className="closed-room-top">
          <Wordmark />
        </div>
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Opening the room…</span>
        </p>
      </main>
    );
  }

  if (room.closed === "removed" || room.closed === "forbidden") {
    return (
      <ClosedRoom
        title="You're out of the room."
        body="Everyone who wasn't ready was removed when the host started. The next one is still yours."
        action={<Button onClick={() => navigate("/")}>Back home</Button>}
      />
    );
  }

  if (room.closed === "not_found") {
    return (
      <ClosedRoom
        title="This room has closed."
        body="The link may have expired, or the night already ended."
        action={<Button onClick={() => navigate("/")}>Back home</Button>}
      />
    );
  }

  return (
    <main className={cx("lobby-shell", `stage-${lobby.stage}`)}>
      <header className="lobby-top">
        <Wordmark />
        <div className="room-meta">
          <span className="room-name">
            {lobby.groupName ?? `Hosted by ${lobby.players.find((player) => player.isHost)?.name ?? "a member"}`}
          </span>
          {room.connection === "offline" ? <span className="tag">Reconnecting</span> : null}
          <span className="room-stage">{stageLabel(lobby)}</span>
        </div>
        <button
          type="button"
          className="room-exit"
          onClick={() => void exitRoom()}
          disabled={room.pendingAction === "leave" || room.pendingAction === "end"}
          aria-label={
            lobby.status === "finished"
              ? "Go home"
              : lobby.viewerIsHost
                ? "End the room and go home"
                : "Leave the room and go home"
          }
        >
          {room.pendingAction === "leave" || room.pendingAction === "end" ? (
            <Loader2 className="spin" size={16} />
          ) : (
            <X size={16} />
          )}
          <span>
            {lobby.status === "finished" ? "Home" : lobby.viewerIsHost ? "End" : "Leave"}
          </span>
        </button>
      </header>

      {status === "guest" ? (
        <div className="room-guest-bar">
          <span>Playing as {person?.name ?? "Guest"}</span>
          <Link to={`/auth?next=${encodeURIComponent(`/lobby/${lobby.uuid}`)}`}>
            Save this night
          </Link>
        </div>
      ) : null}

      <div className="room-scene" key={lobby.stage}>
        {lobby.stage === "waiting" ? (
          <WaitingRoom
            lobby={lobby}
            onReady={() => void room.send("ready")}
            onUnready={() => void room.send("unready")}
            onStart={() => void room.send("start")}
            pendingAction={room.pendingAction}
          />
        ) : null}
        {lobby.stage === "playing" ? (
          <PlayingRoom
            lobby={lobby}
            send={room.send}
            pendingAction={room.pendingAction}
            onOpenFilm={openFilm}
          />
        ) : null}
        {lobby.stage === "final" ? (
          <FinalRoom
            lobby={lobby}
            send={room.send}
            pendingAction={room.pendingAction}
            onOpenFilm={openFilm}
            onLeave={() => void exitRoom()}
          />
        ) : null}
        {lobby.stage === "winner" ? (
          <WinnerRoom
            lobby={lobby}
            onOpenFilm={openFilm}
            onLeave={() => navigate("/")}
            onRestart={() => void room.restart()}
            pendingAction={room.pendingAction}
          />
        ) : null}
      </div>

      <MovieDetailSheet
        movieId={detailMovieId}
        lobby={lobby}
        open={detailMovieId !== null}
        onOpenChange={(next) => {
          if (!next) closeFilm();
        }}
      />
    </main>
  );
}

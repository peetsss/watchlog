import { useState } from "react";
import { ArrowRight, Clock, Link2, Loader2, Lock, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { Wordmark } from "../components/Wordmark";
import { movies } from "../data";
import { joinLobby, useLobbyPreview } from "../lib/api-lobby";
import { ApiError } from "../lib/api";
import { usePageTitle } from "../lib/usePageTitle";

function statusLabel(status: string): string {
  if (status === "ready") return "Waiting to start";
  if (status === "playing") return "In progress";
  if (status === "final_round") return "Final round";
  return "Finished";
}

export function JoinPage() {
  usePageTitle("You're invited");
  const { lobbyId } = useParams<{ lobbyId: string }>();
  const preview = useLobbyPreview(lobbyId);
  const navigate = useNavigate();
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const room = preview.data ?? null;

  if (preview.isPending) {
    return (
      <main className="closed-room">
        <div className="closed-room-top">
          <Wordmark />
        </div>
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Opening the invite…</span>
        </p>
      </main>
    );
  }

  if (preview.isError || !room) {
    const privateRoom = preview.error instanceof ApiError && preview.error.status === 403;
    const missing = preview.error instanceof ApiError && [404, 422].includes(preview.error.status);
    return (
      <main className="join-page">
        <header className="join-top">
          <Wordmark />
          <Link to="/" className="text-link">
            Back home
          </Link>
        </header>
        <div className="join-invalid">
          <EmptyState
            icon={<Link2 size={24} />}
            title={
              privateRoom
                ? "This room is private."
                : missing
                  ? "This invite has expired."
                  : "The invite didn't load."
            }
            body={
              privateRoom
                ? "Group rooms are only open to their members. Ask the host for a group invite."
                : missing
                  ? "Room invites are unique to the night. Ask the host for a fresh one."
                  : preview.error instanceof Error
                    ? preview.error.message
                    : "Try again in a moment."
            }
            action={
              <div className="empty-actions">
                {!missing && !privateRoom ? (
                  <Button onClick={() => void preview.refetch()}>Try again</Button>
                ) : null}
                <Button variant="ghost" onClick={() => navigate("/")}>
                  Back home
                </Button>
              </div>
            }
          />
        </div>
      </main>
    );
  }

  const handleJoin = async () => {
    setError(null);
    setJoining(true);
    try {
      if (!room.isMember) await joinLobby(room.uuid);
      navigate(`/lobby/${room.uuid}`, { replace: true });
    } catch (joinError) {
      setError(
        joinError instanceof ApiError ? joinError.message : "Couldn't join the room. Try again.",
      );
    } finally {
      setJoining(false);
    }
  };

  const canEnter = room.isMember || room.canJoin;
  const host = room.hostUsername
    ? `${room.hostUsername.charAt(0).toUpperCase()}${room.hostUsername.slice(1)}`
    : null;

  return (
    <main className="join-page">
      <header className="join-top">
        <Wordmark />
        <Link to="/" className="text-link">
          Back home
        </Link>
      </header>

      <div className="join-layout">
        <section className="join-card">
          <p className="eyebrow">You're invited</p>
          <h1 className="display join-title">
            {host ? `${host} saved you a seat.` : "A seat is waiting."}
          </h1>
          <p className="lede join-lede">
            {room.groupName ?? "An open movie night"}. {room.playerCount}{" "}
            {room.playerCount === 1 ? "person is" : "people are"} already in the room.
          </p>

          <div className="join-host">
            <span className="side-anon-avatar" aria-hidden="true">
              <Users size={18} />
            </span>
            <div>
              <span>Hosted by</span>
              <strong>{host ?? "A member"}</strong>
            </div>
            <span className="tag tag-amber">Host</span>
          </div>

          <div className="join-rows">
            <div className="join-row">
              <Link2 size={17} aria-hidden="true" />
              <span>Room</span>
              <strong>{room.groupName ?? "Open lobby"}</strong>
            </div>
            <div className="join-row">
              <Users size={17} aria-hidden="true" />
              <span>In the room</span>
              <strong>
                {room.playerCount} {room.playerCount === 1 ? "person" : "people"}
              </strong>
            </div>
            <div className="join-row">
              <Clock size={17} aria-hidden="true" />
              <span>Status</span>
              <strong>{statusLabel(room.status)}</strong>
            </div>
          </div>

          {error ? (
            <p className="field-error" role="alert">
              {error}
            </p>
          ) : null}

          <div className="join-actions">
            {canEnter ? (
              <Button size="lg" onClick={handleJoin} disabled={joining}>
                {joining ? (
                  <>
                    <Loader2 className="spin" size={17} /> Joining…
                  </>
                ) : (
                  <>
                    {room.isMember ? "Rejoin the room" : "Join the room"}{" "}
                    <ArrowRight size={17} />
                  </>
                )}
              </Button>
            ) : (
              <Button size="lg" disabled>
                This room can't be joined
              </Button>
            )}
            <button type="button" className="text-button" onClick={() => navigate("/")}>
              Not tonight
            </button>
          </div>

          <p className="join-privacy">
            <Lock size={14} aria-hidden="true" />
            The link is the only key. This room never appears in a public list.
          </p>
        </section>

        <aside className="join-visual" aria-hidden="true">
          <div
            className="join-visual-image"
            style={{ backgroundImage: `url(${movies["past-lives"].backdrop})` }}
          />
          <div className="join-visual-scrim" />
          <div className="join-visual-copy">
            <span className="section-kicker">Tonight's plan</span>
            <p className="display">One room. Five people. One film.</p>
            <span className="join-visual-note">
              No group chat. No spreadsheet. Just the room.
            </span>
          </div>
          <div className="join-visual-poster">
            <img src={movies["past-lives"].poster} alt="" />
          </div>
        </aside>
      </div>
    </main>
  );
}

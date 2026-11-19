import { useMemo } from "react";
import { ArrowRight, Check, Copy, Info, Link2, Loader2, Users } from "lucide-react";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { movies } from "../../data";
import { copyText } from "../../lib/copy";
import { cx } from "../../lib/cx";
import { useToast } from "../../state/Toast";
import type { LobbyView } from "../../lib/adapters";

function listNames(names: string[]) {
  if (names.length <= 1) return names[0] ?? "";
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function waitingSentence(names: string[]) {
  if (!names.length) return "Everyone is in. The night can start.";
  if (names.length === 1) {
    return names[0] === "you" ? "You're still deciding." : `${names[0]} is still deciding.`;
  }
  if (names.includes("you")) {
    const others = names.filter((name) => name !== "you");
    const rest =
      others.length === 1
        ? others[0]
        : `${others.slice(0, -1).join(", ")} and ${others[others.length - 1]}`;
    return `You, ${rest} are still deciding.`;
  }
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]} are still deciding.`;
}

export function WaitingRoom({
  lobby,
  onReady,
  onUnready,
  onStart,
  pendingAction,
}: {
  lobby: LobbyView;
  onReady: () => void;
  onUnready: () => void;
  onStart: () => void;
  pendingAction: string | null;
}) {
  const { showToast } = useToast();
  const collage = useMemo(
    () => [movies["past-lives"], movies["grand-budapest"], movies["paddington-2"]],
    [],
  );

  const host = lobby.players.find((player) => player.isHost);
  const isHost = lobby.viewerIsHost;
  const meReady = lobby.viewerReady;
  const allReady = lobby.readyCount === lobby.playerCount;
  const waiting = lobby.players.filter((player) => !player.isReady);
  const waitingNames = waiting.map((player) =>
    player.id === lobby.viewerId ? "you" : player.name.split(" ")[0],
  );
  const displayUrl = `${window.location.origin.replace(/^https?:\/\//, "")}/join/${lobby.uuid}`;
  const inviteUrl = `${window.location.origin}/join/${lobby.uuid}`;

  const handleCopy = async () => {
    const copied = await copyText(inviteUrl);
    showToast(copied ? "Invite link copied." : "Couldn't copy the link — select it instead.");
  };

  let primary: React.ReactNode;

  if (isHost) {
    primary = (
      <Button onClick={onStart} disabled={pendingAction === "start"}>
        {pendingAction === "start" ? (
          <>
            <Loader2 className="spin" size={15} /> Starting…
          </>
        ) : allReady ? (
          <>
            Start the night <ArrowRight size={16} />
          </>
        ) : (
          <>
            Start with {Math.max(1, lobby.readyCount)} ready <ArrowRight size={16} />
          </>
        )}
      </Button>
    );
  } else if (!meReady) {
    primary = (
      <Button onClick={onReady} disabled={pendingAction === "ready"}>
        {pendingAction === "ready" ? (
          <>
            <Loader2 className="spin" size={15} /> Ready…
          </>
        ) : (
          <>
            I'm in <Check size={16} />
          </>
        )}
      </Button>
    );
  } else if (!allReady) {
    primary = (
      <span className="room-status-pill" role="status">
        <Check size={15} /> You're in. Waiting on {listNames(waitingNames)}.
      </span>
    );
  } else {
    primary = (
      <span className="room-status-pill is-starting" role="status">
        <Loader2 className="spin" size={15} /> {host?.name.split(" ")[0] ?? "The host"} is starting
        the night…
      </span>
    );
  }

  return (
    <section className="waiting-room">
      <div className="waiting-collage" aria-hidden="true">
        {collage.map((movie, index) => (
          <img
            key={movie.id}
            src={movie.poster}
            alt=""
            style={{ transform: `rotate(${index * 4 - 4}deg)` }}
          />
        ))}
      </div>

      <div className="waiting-inner">
        <div className="waiting-grid">
          <div className="waiting-copy">
            <p className="eyebrow">
              <span className="live-pill">
                <span className="live-dot" aria-hidden="true" /> Live
              </span>
              {lobby.groupName ?? "Open room"} · waiting room
            </p>
            <h1 className="display waiting-title">
              {allReady ? "Everyone's in." : "The room is filling up."}
            </h1>
            <p className="lede waiting-lede">
              {allReady && isHost
                ? "The room is ready. Start when you are."
                : allReady
                  ? `${host?.name.split(" ")[0] ?? "The host"} is starting the night.`
                  : lobby.type === "open"
                    ? "Share the link, ready up, and the host will start when everyone's in."
                    : "Everyone in the group is already here. Ready up and the host can start."}
            </p>

            <div className="players-rail" aria-label="Everyone in the room" data-no-pull>
              <ul className="players-rail-list">
                {lobby.players.map((player) => (
                  <li
                    key={player.id}
                    className={cx("players-rail-person", player.isReady && "is-ready")}
                  >
                    <Avatar person={player} size={26} />
                    <span className="players-rail-name">
                      {player.name}
                      {player.id === lobby.viewerId ? <em>You</em> : null}
                    </span>
                    <span className="players-rail-state">
                      {player.isReady ? "Ready" : "Waiting"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {lobby.type === "open" ? (
              <>
                <div className="invite-block">
                  <div className="invite-copy">
                    <span className="invite-label">Invite link</span>
                    <span className="invite-url mono">{displayUrl}</span>
                  </div>
                  <Button variant="secondary" size="sm" onClick={handleCopy}>
                    <Copy size={15} /> Copy
                  </Button>
                </div>
                <p className="invite-note">
                  <Link2 size={14} aria-hidden="true" /> Anyone with the link can join. The room
                  isn't listed publicly.
                </p>
              </>
            ) : (
              <div className="private-note">
                <span className="private-icon" aria-hidden="true">
                  <Users size={17} />
                </span>
                <div>
                  <strong>Private to {lobby.groupName}</strong>
                  <span>Everyone in the group is already in the room. No link needed.</span>
                </div>
              </div>
            )}

            <p className="room-rules">
              <Info size={15} aria-hidden="true" />
              Everyone votes on each movie. A unanimous yes puts it on the shortlist — then everyone
              picks one.
            </p>
            {isHost && !allReady ? (
              <p className="room-rules">
                <Info size={15} aria-hidden="true" />
                Starting now removes anyone who isn't ready.
              </p>
            ) : null}
          </div>

          <aside className="players-panel" aria-labelledby="players-title">
            <div className="players-head">
              <h2 id="players-title">In the room</h2>
              <span>
                {lobby.readyCount} of {lobby.playerCount} ready
              </span>
            </div>
            <ul className="players-list">
              {lobby.players.map((player) => {
                const ready = player.isReady;
                return (
                  <li
                    key={player.id}
                    className={cx(
                      "player-row",
                      player.id === lobby.viewerId && "is-you",
                      ready && "is-ready",
                    )}
                  >
                    <Avatar person={player} size={40} />
                    <div className="player-copy">
                      <span className="player-name">
                        {player.name}
                        {player.id === lobby.viewerId ? <span className="tag">You</span> : null}
                        {player.isGuest ? <span className="tag">Guest</span> : null}
                        {player.isHost ? <span className="tag tag-amber">Host</span> : null}
                      </span>
                      <span className="player-state">{ready ? "Ready" : "Still deciding"}</span>
                    </div>
                    <span
                      className={cx("ready-mark", ready && "is-ready")}
                      role="img"
                      aria-label={ready ? "Ready" : "Not ready yet"}
                    >
                      {ready ? <Check size={14} strokeWidth={2.8} /> : null}
                    </span>
                  </li>
                );
              })}
            </ul>
            <p className="players-foot">{waitingSentence(waitingNames)}</p>
          </aside>
        </div>

        <div className="room-actionbar">
          <div className="ready-summary">
            <div className="ready-dots" aria-hidden="true">
              {lobby.players.map((player) => (
                <span
                  key={player.id}
                  className={cx("ready-dot", player.isReady && "is-ready")}
                />
              ))}
            </div>
            <span>
              {lobby.readyCount} of {lobby.playerCount} ready
            </span>
          </div>
          <div className="room-actions">
            {meReady ? (
              <button
                type="button"
                className="text-button subtle"
                onClick={onUnready}
                disabled={pendingAction === "unready"}
              >
                {pendingAction === "unready" ? "Updating…" : "Not ready"}
              </button>
            ) : isHost ? (
              <button
                type="button"
                className="text-button subtle"
                onClick={onReady}
                disabled={pendingAction === "ready"}
              >
                {pendingAction === "ready" ? "Updating…" : "I'm in"}
              </button>
            ) : null}
            {primary}
            <span className="sr-only" role="status" aria-live="polite">
              {meReady ? "You're in." : "You're not ready yet."}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

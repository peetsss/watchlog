import { useMemo } from "react";
import { ArrowRight, Check, Copy, Info, Link2, Loader2, Users } from "lucide-react";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { INVITE_CODE, movies, people } from "../../data";
import { copyText, inviteUrl } from "../../lib/copy";
import { cx } from "../../lib/cx";
import { useLobby } from "../../state/Lobby";
import { useToast } from "../../state/Toast";

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
    return `You and ${names.filter((name) => name !== "you").join(" and ")} are still deciding.`;
  }
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]} are still deciding.`;
}

export function WaitingRoom() {
  const { lobby, setReady, startNight } = useLobby();
  const { showToast } = useToast();

  const collage = useMemo(
    () => [movies["past-lives"], movies["grand-budapest"], movies["paddington-2"]],
    [],
  );

  if (!lobby) return null;

  const host = lobby.players.find((person) => person.id === lobby.hostId) ?? people.maya;
  const isHost = lobby.hostId === lobby.youId;
  const meReady = lobby.ready.includes(lobby.youId);
  const readyCount = lobby.ready.length;
  const allReady = readyCount === lobby.players.length;
  const waiting = lobby.players.filter((person) => !lobby.ready.includes(person.id));
  const waitingNames = waiting.map((person) =>
    person.id === lobby.youId ? "you" : person.name.split(" ")[0],
  );
  const waitingText = listNames(waitingNames);
  const displayUrl = inviteUrl(INVITE_CODE).replace(/^https?:\/\//, "");

  const handleCopy = async () => {
    const copied = await copyText(inviteUrl(INVITE_CODE));
    showToast(copied ? "Invite link copied." : "Couldn't copy the link — select it instead.");
  };

  let primary: React.ReactNode;

  if (!meReady) {
    primary = (
      <Button onClick={() => setReady(lobby.youId, true)}>
        I'm in <Check size={16} />
      </Button>
    );
  } else if (isHost) {
    primary = (
      <Button onClick={startNight} disabled={!allReady}>
        {allReady ? (
          <>
            Start the night <ArrowRight size={16} />
          </>
        ) : (
          <>Waiting on {waitingText}</>
        )}
      </Button>
    );
  } else if (!allReady) {
    primary = (
      <span className="room-status-pill" role="status">
        <Check size={15} /> You're in. Waiting on {waitingText}.
      </span>
    );
  } else {
    primary = (
      <span className="room-status-pill is-starting" role="status">
        <Loader2 className="spin" size={15} /> {host.name.split(" ")[0]} is starting the night…
      </span>
    );
  }

  return (
    <section className="waiting-room">
      <div className="waiting-collage" aria-hidden="true">
        {collage.map((movie, index) => (
          <img key={movie.id} src={movie.poster} alt="" style={{ transform: `rotate(${index * 4 - 4}deg)` }} />
        ))}
      </div>

      <div className="waiting-inner">
        <div className="waiting-grid">
          <div className="waiting-copy">
            <p className="eyebrow">
              <span className="live-pill">
                <span className="live-dot" aria-hidden="true" /> Live
              </span>
              {lobby.groupName} · waiting room
            </p>
            <h1 className="display waiting-title">
              {allReady ? "Everyone's in." : "The room is filling up."}
            </h1>
            <p className="lede waiting-lede">
              {allReady
                ? isHost
                  ? "The room is ready. Start when you are."
                  : `${host.name.split(" ")[0]} is starting the night.`
                : lobby.privacy === "open"
                  ? "Share the link, ready up, and the host will start when everyone's in."
                  : "Everyone in the group is already here. Ready up and the host can start."}
            </p>

            {lobby.privacy === "open" ? (
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
                  <Link2 size={14} aria-hidden="true" /> Anyone with the link can join. The room isn't listed publicly.
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
              Everyone votes on each film. A unanimous yes puts it on the shortlist — then everyone picks one.
            </p>
          </div>

          <aside className="players-panel" aria-labelledby="players-title">
            <div className="players-head">
              <h2 id="players-title">In the room</h2>
              <span>
                {readyCount} of {lobby.players.length} ready
              </span>
            </div>
            <ul className="players-list">
              {lobby.players.map((person) => {
                const ready = lobby.ready.includes(person.id);
                return (
                  <li
                    key={person.id}
                    className={cx(
                      "player-row",
                      person.id === lobby.youId && "is-you",
                      ready && "is-ready",
                    )}
                  >
                    <Avatar person={person} size={40} />
                    <div className="player-copy">
                      <span className="player-name">
                        {person.name}
                        {person.id === lobby.youId ? (
                          <span className="tag">You</span>
                        ) : null}
                        {person.id === lobby.hostId ? <span className="tag tag-amber">Host</span> : null}
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
              {lobby.players.map((person) => (
                <span
                  key={person.id}
                  className={cx("ready-dot", lobby.ready.includes(person.id) && "is-ready")}
                />
              ))}
            </div>
            <span>
              {readyCount} of {lobby.players.length} ready
            </span>
          </div>
          <div className="room-actions">
            {meReady ? (
              <button
                type="button"
                className="text-button subtle"
                onClick={() => setReady(lobby.youId, false)}
              >
                Not ready after all
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

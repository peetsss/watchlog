import { ArrowRight, Clock, Link2, Lock, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Avatar, AvatarStack } from "../components/Avatar";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { Wordmark } from "../components/Wordmark";
import { INVITE_CODE, invitePreview, movies } from "../data";
import { cx } from "../lib/cx";
import { usePageTitle } from "../lib/usePageTitle";
import { useLobby } from "../state/Lobby";

export function JoinPage() {
  usePageTitle("You're invited");
  const { code } = useParams<{ code: string }>();
  const { lobby, joinOpenLobby } = useLobby();
  const navigate = useNavigate();

  const valid = code?.toLowerCase() === INVITE_CODE;
  const activeInvite = lobby && lobby.privacy === "open" && lobby.stage !== "winner";
  const names = invitePreview.players.map((person) => person.name.split(" ")[0]);

  const handleJoin = () => {
    if (!activeInvite) joinOpenLobby();
    navigate("/lobby/friday");
  };

  return (
    <main className="join-page">
      <header className="join-top">
        <Wordmark />
        <Link to="/" className="text-link">
          Back home
        </Link>
      </header>

      {!valid ? (
        <div className="join-invalid">
          <EmptyState
            icon={<Link2 size={24} />}
            title="This invite has expired."
            body="Invite links are unique to a room. Ask the host for a fresh one, or start a room of your own."
            action={
              <Button onClick={() => navigate("/")}>
                Back home
              </Button>
            }
          />
        </div>
      ) : (
        <div className="join-layout">
          <section className="join-card">
            <p className="eyebrow">You're invited</p>
            <h1 className="display join-title">Maya saved you a seat.</h1>
            <p className="lede join-lede">
              An open movie night. {names.length} people are already in the room, waiting on the host to start.
            </p>

            <div className="join-host">
              <Avatar person={invitePreview.host} size={44} />
              <div>
                <span>Hosted by</span>
                <strong>{invitePreview.host.name}</strong>
              </div>
              <span className="tag tag-amber">Host</span>
            </div>

            <div className="join-rows">
              <div className="join-row">
                <Link2 size={17} aria-hidden="true" />
                <span>Room</span>
                <strong>Link-only, not listed</strong>
              </div>
              <div className="join-row">
                <Users size={17} aria-hidden="true" />
                <span>In the room</span>
                <strong>{names.length} people</strong>
              </div>
              <div className="join-row">
                <Clock size={17} aria-hidden="true" />
                <span>Status</span>
                <strong>Waiting to start</strong>
              </div>
            </div>

            <div className="join-players">
              <AvatarStack people={invitePreview.players} size={30} />
              <span>{names.slice(0, -1).join(", ")} and {names[names.length - 1]} are in.</span>
            </div>

            <div className="join-actions">
              <Button size="lg" onClick={handleJoin}>
                {activeInvite ? "Rejoin the room" : "Join the room"}{" "}
                <ArrowRight size={17} />
              </Button>
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
              <p className="display">One link. Five people. One film.</p>
              <span className="join-visual-note">No group chat. No spreadsheet. Just the room.</span>
            </div>
            <div className={cx("join-visual-poster")}>
              <img src={movies["past-lives"].poster} alt="" />
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}

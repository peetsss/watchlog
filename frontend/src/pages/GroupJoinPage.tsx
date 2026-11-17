import { useState } from "react";
import { ArrowRight, Film, Link2, Loader2, Lock, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { LegalLinks } from "../components/LegalLinks";
import { Wordmark } from "../components/Wordmark";
import { movies } from "../data";
import { useGroupInvitePreview, useJoinGroupInvite } from "../lib/api-groups";
import { ApiError } from "../lib/api";
import { usePageTitle } from "../lib/usePageTitle";

export function GroupJoinPage() {
  usePageTitle("You're invited");
  const { token } = useParams<{ token: string }>();
  const preview = useGroupInvitePreview(token);
  const joinGroup = useJoinGroupInvite();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const group = preview.data ?? null;

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

  if (preview.isError || !group) {
    const missing =
      preview.error instanceof ApiError && [404, 422].includes(preview.error.status);
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
            title={missing ? "This invite has expired." : "The invite didn't load."}
            body={
              missing
                ? "Group invites are unique to the group. Ask for a fresh link, or start a crew of your own."
                : preview.error instanceof Error
                  ? preview.error.message
                  : "Try again in a moment."
            }
            action={
              <div className="empty-actions">
                {!missing ? (
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
    try {
      await joinGroup.mutateAsync(token as string);
      navigate(`/groups/${group.id}`, { replace: true });
    } catch (joinError) {
      setError(
        joinError instanceof ApiError ? joinError.message : "Couldn't join the group. Try again.",
      );
    }
  };

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
          <h1 className="display join-title">A seat in {group.name}.</h1>
          <p className="lede join-lede">
            {group.description || "A group for the films you keep between you."}
          </p>

          <div className="join-rows">
            <div className="join-row">
              <Film size={17} aria-hidden="true" />
              <span>Group</span>
              <strong>{group.name}</strong>
            </div>
            <div className="join-row">
              <Users size={17} aria-hidden="true" />
              <span>Members</span>
              <strong>
                {group.memberCount} {group.memberCount === 1 ? "person" : "people"}
              </strong>
            </div>
            <div className="join-row">
              <Link2 size={17} aria-hidden="true" />
              <span>Watchlist</span>
              <strong>
                {group.filmCount} {group.filmCount === 1 ? "film" : "films"}
              </strong>
            </div>
          </div>

          {error ? (
            <p className="field-error" role="alert">
              {error}
            </p>
          ) : null}

          <div className="join-actions">
            {group.isMember ? (
              <Button size="lg" onClick={() => navigate(`/groups/${group.id}`)}>
                Open the group <ArrowRight size={17} />
              </Button>
            ) : (
              <Button size="lg" onClick={handleJoin} disabled={joinGroup.isPending}>
                {joinGroup.isPending ? (
                  <>
                    <Loader2 className="spin" size={17} /> Joining…
                  </>
                ) : (
                  <>
                    Join {group.name} <ArrowRight size={17} />
                  </>
                )}
              </Button>
            )}
            <button type="button" className="text-button" onClick={() => navigate("/")}>
              Not tonight
            </button>
          </div>

          <p className="join-privacy">
            <Lock size={14} aria-hidden="true" />
            The link is the only key. This group never appears in a public list.
          </p>
        </section>

        <aside className="join-visual" aria-hidden="true">
          <div
            className="join-visual-image"
            style={{ backgroundImage: `url(${movies["past-lives"].backdrop})` }}
          />
          <div className="join-visual-scrim" />
          <div className="join-visual-copy">
            <span className="section-kicker">The crew</span>
            <p className="display">One link. Your people. One pick.</p>
            <span className="join-visual-note">
              No group chat. No spreadsheet. Just the room.
            </span>
          </div>
          <div className="join-visual-poster">
            <img src={movies["past-lives"].poster} alt="" />
          </div>
        </aside>
      </div>
      <LegalLinks className="join-legal" />
    </main>
  );
}

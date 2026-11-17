import { ArrowRight, Link2, Loader2, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../components/Button";
import { LegalLinks } from "../components/LegalLinks";
import { SessionError, SessionLoading } from "../components/RequireMember";
import { Wordmark } from "../components/Wordmark";
import { ApiError } from "../lib/api";
import { createLobby, useActiveLobby } from "../lib/api-lobby";
import { createGuest } from "../lib/api-session";
import { usePageTitle } from "../lib/usePageTitle";
import { SESSION_QUERY_KEY, useSession } from "../state/Session";
import "./auth.css";

export function GuestStartPage() {
  usePageTitle("Start a movie night");
  const { status, person } = useSession();
  const activeLobby = useActiveLobby(status === "guest");
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === "loading") return <SessionLoading />;
  if (status === "error") return <SessionError />;
  if (status === "member") return <Navigate to="/" replace />;

  const active = activeLobby.data;
  if (status === "guest" && active) {
    return <Navigate to={`/lobby/${active.uuid}`} replace />;
  }

  const startNight = async () => {
    setBusy(true);
    setError(null);
    try {
      if (status !== "guest") {
        await createGuest(displayName.trim());
        await queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
        await queryClient.refetchQueries({ queryKey: SESSION_QUERY_KEY });
      }
      const lobby = await createLobby();
      navigate(`/lobby/${lobby.uuid}`, { replace: true });
    } catch (startError) {
      setError(startError instanceof ApiError ? startError.message : "Couldn't open the room.");
      setBusy(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (status !== "guest" && displayName.trim().length < 2) {
      setError("Add a display name of at least 2 characters.");
      return;
    }
    void startNight();
  };

  return (
    <main className="auth-page">
      <header className="auth-top">
        <Wordmark />
        <Link to="/auth" className="text-link">
          Sign in instead
        </Link>
      </header>

      <section className="auth-card auth-utility" aria-labelledby="guest-start-title">
        <p className="eyebrow">No account needed</p>
        <h1 className="display auth-title" id="guest-start-title">
          Start a night, <em>just like that.</em>
        </h1>
        <p className="auth-lede">
          Open a room, send the link, and let everyone vote. You can keep the crew with an
          account when the credits roll.
        </p>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {status === "guest" ? (
            <div className="guest-start-identity">
              <Sparkles size={16} aria-hidden="true" />
              <span>
                Playing as <strong>{person?.name ?? "Guest"}</strong>
              </span>
            </div>
          ) : (
            <>
              <label className="field-label" htmlFor="guest-display-name">
                Display name
              </label>
              <input
                id="guest-display-name"
                className="text-input"
                type="text"
                autoComplete="nickname"
                value={displayName}
                onChange={(event) => {
                  setDisplayName(event.target.value);
                  if (error) setError(null);
                }}
              />
              <p className="field-help">This is what the room will see. No email yet.</p>
            </>
          )}

          {error ? (
            <p className="field-error auth-error" role="alert">
              {error}
            </p>
          ) : null}

          <Button type="submit" size="lg" disabled={busy}>
            {busy ? <Loader2 className="spin" size={17} /> : null}
            Open a room <ArrowRight size={17} />
          </Button>
        </form>

        <div className="guest-start-footer">
          <p>
            <Link2 size={14} aria-hidden="true" /> Already have an invite? Open the link
            your host sent you.
          </p>
          {status === "guest" ? (
            <p>
              Want to keep this crew?{" "}
              <Link to="/auth?next=/account" className="text-link">
                Create an account
              </Link>
            </p>
          ) : null}
        </div>
      </section>

      <footer className="auth-foot">
        <span className="foot-brand">
          watchlog<span>.</span>
        </span>
        <span>For the people who stay for the credits.</span>
        <LegalLinks className="auth-legal" />
      </footer>
    </main>
  );
}

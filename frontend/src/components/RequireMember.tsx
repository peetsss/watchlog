import type { ReactNode } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Loader2, WifiOff } from "lucide-react";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";
import { Wordmark } from "./Wordmark";
import { useSession } from "../state/Session";

export function SessionLoading() {
  return (
    <main className="closed-room">
      <div className="closed-room-top">
        <Wordmark />
      </div>
      <p className="session-loading" role="status">
        <Loader2 className="spin" size={17} aria-hidden="true" />
        <span>Finding your seat…</span>
      </p>
    </main>
  );
}

export function SessionError() {
  const { error, retry } = useSession();
  const navigate = useNavigate();

  return (
    <main className="closed-room">
      <div className="closed-room-top">
        <Wordmark />
      </div>
      <EmptyState
        icon={<WifiOff size={24} />}
        title="watchlog is out of reach."
        body={
          error?.message ??
          "The API did not answer. Check that it is running, then try again."
        }
        action={
          <div className="empty-actions">
            <Button onClick={retry}>Try again</Button>
            <Button variant="ghost" onClick={() => navigate("/auth")}>
              Go to sign in
            </Button>
          </div>
        }
      />
    </main>
  );
}

export function RequireMember({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const location = useLocation();

  if (status === "loading") return <SessionLoading />;
  if (status === "error") return <SessionError />;
  if (status === "guest") return <Navigate to="/start" replace />;
  if (status === "anonymous") {
    const next =
      location.pathname === "/"
        ? ""
        : `?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`;
    return <Navigate to={`/auth${next}`} replace />;
  }

  return <>{children}</>;
}

export function RequirePlayer({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const location = useLocation();

  if (status === "loading") return <SessionLoading />;
  if (status === "error") return <SessionError />;
  if (status === "anonymous") {
    return <Navigate to={`/auth?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`} replace />;
  }

  return <>{children}</>;
}

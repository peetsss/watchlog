import type { ReactNode } from "react";
import { Users } from "lucide-react";
import { Link } from "react-router-dom";
import { useGuestGate } from "../state/GuestGate";
import { useViewer } from "../state/Viewer";
import { Button, buttonClass } from "./Button";
import { EmptyState } from "./EmptyState";
import { Wordmark } from "./Wordmark";

export function MemberOnly({ children }: { children: ReactNode }) {
  const { isMember } = useViewer();
  const { openAccount } = useGuestGate();

  if (isMember) return <>{children}</>;

  return (
    <main className="closed-room">
      <div className="closed-room-top">
        <Wordmark />
      </div>
      <EmptyState
        icon={<Users size={24} />}
        title="Your clubs live here."
        body="Create an account to join a club, add films and keep your scores. You can still host or join an open room as a guest."
        action={
          <div className="empty-actions">
            <Button onClick={openAccount}>Create an account</Button>
            <Link to="/" className={buttonClass("ghost", "md")}>
              Back home
            </Link>
          </div>
        }
      />
    </main>
  );
}

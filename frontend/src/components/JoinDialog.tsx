import { useState, type FormEvent } from "react";
import { ArrowRight, Info } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "./Button";
import { Modal } from "./Modal";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Invite =
  | { kind: "group"; id: string }
  | { kind: "lobby"; id: string };

function parseInvite(value: string): Invite | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (UUID.test(trimmed)) return { kind: "lobby", id: trimmed };

  try {
    const url = new URL(trimmed, window.location.origin);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "join" && parts[1] === "group" && UUID.test(parts[2] ?? "")) {
      return { kind: "group", id: parts[2] };
    }
    if (parts[0] === "lobby" && UUID.test(parts[1] ?? "")) {
      return { kind: "lobby", id: parts[1] };
    }
    if (parts[0] === "join" && UUID.test(parts[1] ?? "")) {
      return { kind: "lobby", id: parts[1] };
    }
  } catch {
    // Not a URL; fall through to the error.
  }
  return null;
}

export function JoinDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setValue("");
      setError(null);
    }
    onOpenChange(next);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const invite = parseInvite(value);
    if (!invite) {
      setError("Paste a watchlog invite link or a room UUID.");
      return;
    }

    setError(null);
    setValue("");
    onOpenChange(false);
    navigate(
      invite.kind === "group" ? `/join/group/${invite.id}` : `/join/${invite.id}`,
    );
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title="Join a movie night"
      description="Paste the link the host sent you. The room stays link-only."
      footer={
        <>
          <Button variant="ghost" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="join-night-form">
            Continue <ArrowRight size={16} />
          </Button>
        </>
      }
    >
      <form id="join-night-form" onSubmit={handleSubmit} noValidate>
        <label className="field-label" htmlFor="invite-link">
          Invite link or room UUID
        </label>
        <input
          id="invite-link"
          className="text-input"
          type="text"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="watchlog.app/join/…"
          value={value}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "invite-error" : "invite-help"}
          onChange={(event) => {
            setValue(event.target.value);
            if (error) setError(null);
          }}
        />
        {error ? (
          <p className="field-error" id="invite-error" role="alert">
            {error}
          </p>
        ) : (
          <p className="field-help" id="invite-help">
            Room links look like <span className="mono">/join/&lt;room-uuid&gt;</span>. Group
            links use <span className="mono">/join/group/&lt;group-uuid&gt;</span>.
          </p>
        )}
      </form>

      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>Open rooms are link-only. The host decides who gets the link.</span>
      </div>
    </Modal>
  );
}

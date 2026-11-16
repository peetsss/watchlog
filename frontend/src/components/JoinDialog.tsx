import { useState, type FormEvent } from "react";
import { ArrowRight, Info } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { inviteUrl } from "../lib/copy";
import { Button } from "./Button";
import { Modal } from "./Modal";

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
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Paste the invite link first.");
      return;
    }

    const code = trimmed.split(/[/?#]/).filter(Boolean).pop() ?? "";
    if (!/^[a-z0-9]{4,10}$/i.test(code)) {
      setError("That doesn't look like an invite link.");
      return;
    }

    setError(null);
    setValue("");
    onOpenChange(false);
    navigate(`/join/${code.toLowerCase()}`);
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title="Join a movie night"
      description="Paste the link the host sent you. No account switcher, no group code to hunt for."
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
          Invite link or code
        </label>
        <input
          id="invite-link"
          className="text-input"
          type="text"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder={inviteUrl("7f3k2").replace(/^https?:\/\//, "")}
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
            It looks like <span className="mono">watchlog.app/join/7f3k2</span>.
          </p>
        )}
      </form>

      <button
        type="button"
        className="text-button demo-link"
        onClick={() => {
          setValue(inviteUrl("7f3k2"));
          setError(null);
        }}
      >
        Use the demo invite
      </button>

      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>Open rooms are link-only. The host decides who gets the link.</span>
      </div>
    </Modal>
  );
}

import { Check, Loader2, MailWarning } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../lib/api";
import { resendVerification } from "../lib/api-account";
import { useSession } from "../state/Session";
import { useToast } from "../state/Toast";

export function EmailVerificationBanner() {
  const { status, email, emailVerified } = useSession();
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  if (status !== "member" || emailVerified) return null;

  const handleResend = async () => {
    if (!email || busy) return;
    setBusy(true);
    try {
      await resendVerification(email);
      setSent(true);
      showToast("Confirmation email sent again.");
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : "Couldn't resend the email.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="verify-banner" role="status">
      <span className="verify-banner-icon" aria-hidden="true">
        <MailWarning size={15} />
      </span>
      <span className="verify-banner-copy">
        {email ? (
          <>
            Confirm <strong>{email}</strong> to unlock groups and invitations.
          </>
        ) : (
          <>
            Add an email in <Link to="/account">account settings</Link> to secure your account.
          </>
        )}
      </span>
      {email ? (
        <button type="button" className="verify-banner-action" onClick={handleResend} disabled={busy || sent}>
          {busy ? (
            <Loader2 className="spin" size={13} aria-hidden="true" />
          ) : sent ? (
            <Check size={13} aria-hidden="true" />
          ) : null}
          {sent ? "Sent" : "Resend"}
        </button>
      ) : null}
    </div>
  );
}

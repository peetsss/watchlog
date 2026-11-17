import { CheckCircle2, Download, Loader2, MailWarning } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { ApiError } from "../lib/api";
import {
  changeEmail,
  changePassword,
  downloadAccountExport,
  resendVerification,
  useAccount,
} from "../lib/api-account";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../state/Session";
import { useToast } from "../state/Toast";
import "./account.css";

export function AccountPage() {
  usePageTitle("Account");
  const accountQuery = useAccount();
  const { signOut } = useSession();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [resendBusy, setResendBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  const account = accountQuery.data;

  if (accountQuery.isPending) {
    return (
      <div className="page-inner account-page">
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Opening your account…</span>
        </p>
      </div>
    );
  }

  if (accountQuery.isError || !account) {
    return (
      <div className="page-inner account-page">
        <EmptyState
          icon={<MailWarning size={24} />}
          title="Account didn't load."
          body={accountQuery.error?.message ?? "Try again in a moment."}
          action={<Button onClick={() => accountQuery.refetch()}>Try again</Button>}
        />
      </div>
    );
  }

  const handleResend = async () => {
    if (!account.email || resendBusy) return;
    setResendBusy(true);
    try {
      await resendVerification(account.email);
      showToast("Confirmation email sent again.");
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : "Couldn't resend the email.");
    } finally {
      setResendBusy(false);
    }
  };

  const handleExport = async () => {
    if (exportBusy) return;
    setExportBusy(true);
    try {
      await downloadAccountExport();
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : "Couldn't prepare your export.");
    } finally {
      setExportBusy(false);
    }
  };

  const handleEmailChange = async (event: FormEvent) => {
    event.preventDefault();
    if (emailBusy) return;
    setEmailBusy(true);
    try {
      await changeEmail(newEmail.trim(), emailPassword);
      setNewEmail("");
      setEmailPassword("");
      await accountQuery.refetch();
      showToast("Check the new inbox to confirm the change.");
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : "Couldn't change the email.");
    } finally {
      setEmailBusy(false);
    }
  };

  const handlePasswordChange = async (event: FormEvent) => {
    event.preventDefault();
    if (passwordBusy) return;
    if (newPassword !== confirmPassword) {
      showToast("The new passwords don't match.");
      return;
    }
    setPasswordBusy(true);
    try {
      await changePassword(currentPassword, newPassword);
      showToast("Password changed. Sign in again.");
      await signOut();
      navigate("/auth", { replace: true });
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : "Couldn't change the password.");
      setPasswordBusy(false);
    }
  };

  return (
    <div className="page-inner account-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Your seat</p>
          <h1 className="display page-title">Account</h1>
          <p className="lede page-lede">The details behind your clubs, scores and invitations.</p>
        </div>
        <Button variant="secondary" onClick={() => void signOut().then(() => navigate("/auth", { replace: true }))}>
          Sign out
        </Button>
      </header>

      <div className="account-layout">
        <section className="account-card" aria-labelledby="account-identity">
          <div className="account-card-head">
            <div>
              <p className="section-kicker">Identity</p>
              <h2 className="display" id="account-identity">
                {account.username}
              </h2>
            </div>
            {account.email_verified ? (
              <span className="tag tag-sage account-status">
                <CheckCircle2 size={12} aria-hidden="true" /> Verified
              </span>
            ) : (
              <span className="tag tag-amber account-status">
                <MailWarning size={12} aria-hidden="true" /> Unverified
              </span>
            )}
          </div>

          <dl className="account-details">
            <div>
              <dt>Email</dt>
              <dd>{account.email ?? "No email yet"}</dd>
            </div>
            {account.pending_email ? (
              <div>
                <dt>Waiting for confirmation</dt>
                <dd>{account.pending_email}</dd>
              </div>
            ) : null}
          </dl>

          {!account.email_verified && account.email ? (
            <div className="account-inline-action">
              <p>Confirm your email to create groups and share invitations.</p>
              <Button variant="secondary" onClick={handleResend} disabled={resendBusy}>
                {resendBusy ? <Loader2 className="spin" size={15} /> : null}
                Resend confirmation
              </Button>
            </div>
          ) : null}

          <div className="account-export-row">
            <span>Download a copy of your profile, groups and scores.</span>
            <Button variant="secondary" onClick={handleExport} disabled={exportBusy}>
              {exportBusy ? <Loader2 className="spin" size={15} /> : <Download size={15} />}
              Download my data
            </Button>
          </div>
        </section>

        <section className="account-card" aria-labelledby="account-email">
          <p className="section-kicker">Email</p>
          <h2 className="display" id="account-email">
            Change email
          </h2>
          <p className="account-card-copy">
            We send a confirmation link to the new address. Your current email stays active
            until the new one is confirmed.
          </p>
          <form className="account-form" onSubmit={handleEmailChange} noValidate>
            <label className="field-label" htmlFor="account-new-email">
              New email
            </label>
            <input
              id="account-new-email"
              className="text-input"
              type="email"
              autoComplete="email"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
            />
            <label className="field-label field-label-spaced" htmlFor="account-email-password">
              Current password
            </label>
            <input
              id="account-email-password"
              className="text-input"
              type="password"
              autoComplete="current-password"
              value={emailPassword}
              onChange={(event) => setEmailPassword(event.target.value)}
            />
            <Button type="submit" disabled={emailBusy}>
              {emailBusy ? <Loader2 className="spin" size={15} /> : null}
              Send confirmation
            </Button>
          </form>
        </section>

        <section className="account-card" aria-labelledby="account-password">
          <p className="section-kicker">Security</p>
          <h2 className="display" id="account-password">
            Change password
          </h2>
          <p className="account-card-copy">
            Changing your password signs you out of every device.
          </p>
          <form className="account-form" onSubmit={handlePasswordChange} noValidate>
            <label className="field-label" htmlFor="account-current-password">
              Current password
            </label>
            <input
              id="account-current-password"
              className="text-input"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
            <label className="field-label field-label-spaced" htmlFor="account-new-password">
              New password
            </label>
            <input
              id="account-new-password"
              className="text-input"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <label className="field-label field-label-spaced" htmlFor="account-confirm-password">
              Confirm new password
            </label>
            <input
              id="account-confirm-password"
              className="text-input"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
            <Button type="submit" disabled={passwordBusy}>
              {passwordBusy ? <Loader2 className="spin" size={15} /> : null}
              Change password
            </Button>
          </form>
        </section>
      </div>
    </div>
  );
}

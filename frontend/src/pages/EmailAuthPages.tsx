import { ArrowRight, CheckCircle2, Loader2, MailWarning } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "../components/Button";
import { LegalLinks } from "../components/LegalLinks";
import { Wordmark } from "../components/Wordmark";
import { ApiError } from "../lib/api";
import { forgotPassword, resetPassword, verifyEmail } from "../lib/api-auth";
import { usePageTitle } from "../lib/usePageTitle";
import "./auth.css";

function UtilityLayout({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return (
    <main className="auth-page">
      <header className="auth-top">
        <Wordmark />
        <Link to="/auth" className="text-link">
          Back to sign in
        </Link>
      </header>
      <section className="auth-card auth-utility" aria-labelledby="utility-title">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="display auth-title" id="utility-title">
          {title}
        </h1>
        {children}
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

function UtilityMessage({
  tone,
  title,
  body,
  action,
}: {
  tone: "success" | "error";
  title: string;
  body: string;
  action: ReactNode;
}) {
  return (
    <div className={tone === "success" ? "utility-message is-success" : "utility-message is-error"} role="status">
      <span className="utility-message-icon" aria-hidden="true">
        {tone === "success" ? <CheckCircle2 size={22} /> : <MailWarning size={22} />}
      </span>
      <strong>{title}</strong>
      <p>{body}</p>
      {action}
    </div>
  );
}

export function VerifyEmailPage() {
  usePageTitle("Confirm email");
  const [params] = useSearchParams();
  const token = params.get("token");
  const started = useRef(false);
  const [state, setState] = useState<"working" | "success" | "error">("working");

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!token) {
      setState("error");
      return;
    }
    void verifyEmail(token)
      .then(() => setState("success"))
      .catch(() => setState("error"));
  }, [token]);

  return (
    <UtilityLayout eyebrow="Your account" title="Confirming your email.">
      {state === "working" ? (
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Checking the link…</span>
        </p>
      ) : state === "success" ? (
        <UtilityMessage
          tone="success"
          title="Email confirmed"
          body="Your watchlog account is ready. Groups and invitations are unlocked."
          action={
            <Link to="/" className="btn btn-primary btn-md">
              Back to watchlog <ArrowRight size={16} />
            </Link>
          }
        />
      ) : (
        <UtilityMessage
          tone="error"
          title="This link didn't work"
          body="The link may have expired or already been used. Sign in and request a fresh confirmation from your account page."
          action={
            <Link to="/auth" className="btn btn-secondary btn-md">
              Back to sign in
            </Link>
          }
        />
      )}
    </UtilityLayout>
  );
}

export function ForgotPasswordPage() {
  usePageTitle("Reset password");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (submitError) {
      setError(submitError instanceof ApiError ? submitError.message : "Couldn't send the reset email.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <UtilityLayout eyebrow="Your account" title="Forgot your password?">
      {sent ? (
        <UtilityMessage
          tone="success"
          title="Check your inbox"
          body="If that address belongs to a watchlog account, a reset link is on its way."
          action={
            <Link to="/auth" className="btn btn-secondary btn-md">
              Back to sign in
            </Link>
          }
        />
      ) : (
        <>
          <p className="auth-lede">
            Add the email on your account. We'll send a link that expires in one hour.
          </p>
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <label className="field-label" htmlFor="forgot-email">
              Email
            </label>
            <input
              id="forgot-email"
              className="text-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                if (error) setError(null);
              }}
            />
            {error ? (
              <p className="field-error auth-error" role="alert">
                {error}
              </p>
            ) : null}
            <Button type="submit" size="lg" disabled={busy}>
              {busy ? <Loader2 className="spin" size={17} /> : null}
              Send reset link
            </Button>
          </form>
        </>
      )}
    </UtilityLayout>
  );
}

export function ResetPasswordPage() {
  usePageTitle("Choose a new password");
  const [params] = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !token) return;
    if (password.length < 8) {
      setError("Use at least 8 characters for your password.");
      return;
    }
    if (password !== confirm) {
      setError("The passwords don't match yet.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (submitError) {
      setError(submitError instanceof ApiError ? submitError.message : "Couldn't reset the password.");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <UtilityLayout eyebrow="Your account" title="That link is incomplete.">
        <UtilityMessage
          tone="error"
          title="Missing reset token"
          body="Open the reset link from your email again, or request a fresh one."
          action={
            <Link to="/forgot-password" className="btn btn-secondary btn-md">
              Request a new link
            </Link>
          }
        />
      </UtilityLayout>
    );
  }

  return (
    <UtilityLayout eyebrow="Your account" title="Choose a new password.">
      {done ? (
        <UtilityMessage
          tone="success"
          title="Password changed"
          body="Your other sessions have been signed out. Use the new password to sign in."
          action={
            <Link to="/auth" className="btn btn-primary btn-md">
              Sign in <ArrowRight size={16} />
            </Link>
          }
        />
      ) : (
        <>
          <p className="auth-lede">Use at least 8 characters and a mix that isn't all numbers.</p>
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <label className="field-label" htmlFor="reset-password">
              New password
            </label>
            <input
              id="reset-password"
              className="text-input"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (error) setError(null);
              }}
            />
            <label className="field-label field-label-spaced" htmlFor="reset-confirm">
              Confirm new password
            </label>
            <input
              id="reset-confirm"
              className="text-input"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => {
                setConfirm(event.target.value);
                if (error) setError(null);
              }}
            />
            {error ? (
              <p className="field-error auth-error" role="alert">
                {error}
              </p>
            ) : null}
            <Button type="submit" size="lg" disabled={busy}>
              {busy ? <Loader2 className="spin" size={17} /> : null}
              Change password
            </Button>
          </form>
        </>
      )}
    </UtilityLayout>
  );
}

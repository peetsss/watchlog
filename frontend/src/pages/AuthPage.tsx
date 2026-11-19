import { useState, type FormEvent } from "react";
import { Eye, EyeOff, Loader2, ArrowRight } from "lucide-react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../components/Button";
import { LegalLinks } from "../components/LegalLinks";
import { SessionError, SessionLoading } from "../components/RequireMember";
import { Wordmark } from "../components/Wordmark";
import { movies } from "../data";
import { ApiError } from "../lib/api";
import { cx } from "../lib/cx";
import { usePageTitle } from "../lib/usePageTitle";
import { useSession } from "../state/Session";
import { useToast } from "../state/Toast";
import "./auth.css";

type Mode = "signin" | "register";

function readNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

function authMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "invalid_credentials":
        return "That login and password don't match.";
      case "username_taken":
        return "That username is taken. Try another.";
      case "username_not_allowed":
        return "That username isn't allowed. Pick another one.";
      case "email_taken":
        return "That email is already in use.";
      case "email_unverified":
        return "Verify your email before creating a group.";
      case "invalid_request":
        return "Check the details and try again.";
      case "csrf_failed":
        return "Your session expired. Reload the page and try again.";
      default:
        return error.message;
    }
  }
  return "Something went wrong. Try again.";
}

export function AuthPage() {
  usePageTitle("Sign in");
  const { status, signIn, register } = useSession();
  const { showToast } = useToast();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = readNext(params.get("next"));

  const [mode, setMode] = useState<Mode>("signin");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "loading") return <SessionLoading />;
  if (status === "error") return <SessionError />;
  if (status === "member") return <Navigate to={next} replace />;

  const switchMode = (nextMode: Mode) => {
    if (busy || nextMode === mode) return;
    if (nextMode === "register") {
      const identifier = username.trim();
      if (!email.trim() && identifier.includes("@")) {
        setEmail(identifier);
        setUsername("");
      }
    } else if (!username.trim() && email.trim()) {
      setUsername(email.trim());
      setEmail("");
    }
    setMode(nextMode);
    setPassword("");
    setConfirm("");
    setError(null);
    setShowPassword(false);
  };

  const validate = (): string | null => {
    const cleanUsername = username.trim();
    const cleanEmail = email.trim();
    if (!cleanUsername) return mode === "register" ? "Add your username." : "Add your username or email.";
    if (!password) return "Add your password.";

    if (mode === "register") {
      if (cleanUsername.length < 3) return "Use at least 3 characters for your username.";
      if (!/^[A-Za-z0-9_.-]+$/.test(cleanUsername)) {
        return "Usernames can use letters, numbers, dots, dashes and underscores.";
      }
      if (!cleanEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
        return "Add a valid email address.";
      }
      if (password.length < 8) return "Use at least 8 characters for your password.";
      if (password.toLowerCase() === cleanUsername.toLowerCase()) {
        return "Your password can't match your username.";
      }
      if (/^\d+$/.test(password)) return "Your password can't be only numbers.";
      if (password !== confirm) return "The passwords don't match yet.";
    }

    return null;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;

    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }

    setError(null);
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(username.trim(), password);
      } else {
        await register(username.trim(), email.trim(), password);
        showToast("Check your inbox to confirm your watchlog email.");
      }
      navigate(next, { replace: true });
    } catch (submitError) {
      setError(authMessage(submitError));
    } finally {
      setBusy(false);
    }
  };

  const isRegister = mode === "register";

  return (
    <main className="auth-page">
      <header className="auth-top">
        <Wordmark />
        <span className="auth-top-note">Members' entrance</span>
      </header>

      <div className="auth-layout">
        <section className="auth-card" aria-labelledby="auth-title">
          <p className="eyebrow">A quieter place for movie people</p>
          <h1 className="display auth-title" id="auth-title">
            {isRegister ? (
              <>
                Pull up a <em>chair</em>.
              </>
            ) : (
              <>
                Your seat is <em>waiting</em>.
              </>
            )}
          </h1>
          <p className="lede auth-lede">
            {isRegister
              ? "One account keeps every club, score and late-night pick in one place."
              : "Sign in to your clubs, watchlists and tonight's pick."}
          </p>

          <div className="auth-tabs" role="tablist" aria-label="Account">
            <button
              type="button"
              role="tab"
              aria-selected={!isRegister}
              className={cx("auth-tab", !isRegister && "is-active")}
              onClick={() => switchMode("signin")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={isRegister}
              className={cx("auth-tab", isRegister && "is-active")}
              onClick={() => switchMode("register")}
            >
              Create account
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <label className="field-label" htmlFor="auth-username">
              {isRegister ? "Username" : "Username or email"}
            </label>
            <input
              id="auth-username"
              className="text-input"
              type="text"
              autoComplete={isRegister ? "username" : "username email"}
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              aria-invalid={Boolean(error) && !username.trim()}
              onChange={(event) => {
                setUsername(event.target.value);
                if (error) setError(null);
              }}
            />
            {isRegister ? (
              <p className="field-help">
                3+ characters: letters, numbers, dots, dashes or underscores. This is what your
                clubs will see.
              </p>
            ) : null}

            {isRegister ? (
              <>
                <label className="field-label field-label-spaced" htmlFor="auth-email">
                  Email
                </label>
                <input
                  id="auth-email"
                  className="text-input"
                  type="email"
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={email}
                  aria-invalid={Boolean(error) && !email.trim()}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    if (error) setError(null);
                  }}
                />
                <p className="field-help">We'll send one confirmation link. No newsletters.</p>
              </>
            ) : null}

            <label className="field-label field-label-spaced" htmlFor="auth-password">
              Password
            </label>
            <div className="auth-password">
              <input
                id="auth-password"
                className="text-input"
                type={showPassword ? "text" : "password"}
                autoComplete={isRegister ? "new-password" : "current-password"}
                value={password}
                aria-invalid={Boolean(error) && !password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (error) setError(null);
                }}
              />
              <button
                type="button"
                className="auth-reveal"
                onClick={() => setShowPassword((shown) => !shown)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            {isRegister ? (
              <p className="field-help">At least 8 characters.</p>
            ) : (
              <p className="auth-forgot">
                <Link to="/forgot-password" className="text-link">
                  Forgot password?
                </Link>
              </p>
            )}

            {isRegister ? (
              <>
                <label className="field-label field-label-spaced" htmlFor="auth-confirm">
                  Confirm password
                </label>
                <input
                  id="auth-confirm"
                  className="text-input"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={confirm}
                  aria-invalid={Boolean(error) && password !== confirm}
                  onChange={(event) => {
                    setConfirm(event.target.value);
                    if (error) setError(null);
                  }}
                />
              </>
            ) : null}

            {error ? (
              <p className="field-error auth-error" role="alert">
                {error}
              </p>
            ) : !isRegister ? (
              <p className="field-help auth-help">
                Your browser keeps the session — no token to copy.
              </p>
            ) : null}

            <Button type="submit" size="lg" className="auth-submit" disabled={busy}>
              {busy ? (
                <>
                  <Loader2 className="spin" size={17} aria-hidden="true" />
                  {isRegister ? "Creating your account…" : "Signing in…"}
                </>
              ) : (
                <>
                  {isRegister ? "Create account" : "Sign in"}
                  <ArrowRight size={17} aria-hidden="true" />
                </>
              )}
            </Button>
          </form>

          <p className="auth-note">
            {isRegister
              ? "Already have an account? "
              : "New to watchlog? "}
            <button
              type="button"
              className="text-button auth-switch"
              onClick={() => switchMode(isRegister ? "signin" : "register")}
            >
              {isRegister ? "Sign in instead" : "Create an account"}
            </button>
          </p>

          <p className="auth-guest-note">
            Just here for tonight?{" "}
            <Link to="/start" className="text-link">
              Start a movie night as a guest
            </Link>
            .
          </p>
        </section>

        <aside className="auth-visual" aria-hidden="true">
          <div
            className="auth-visual-image"
            style={{ backgroundImage: `url(${movies["past-lives"].backdrop})` }}
          />
          <div className="auth-visual-scrim" />
          <div className="auth-visual-copy">
            <span className="section-kicker">Tonight's plan</span>
            <p className="display">
              One room.
              <br />
              One shortlist.
              <br />
              <em>One pick.</em>
            </p>
            <span className="auth-visual-note">
              No group chat. No spreadsheet. Just the room.
            </span>
          </div>
          <div className="auth-visual-poster">
            <img src={movies["past-lives"].poster} alt="" />
            <span className="auth-visual-poster-caption">Past Lives · 2023</span>
          </div>
        </aside>
      </div>

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

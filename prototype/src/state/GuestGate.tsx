import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Info } from "lucide-react";
import { Button } from "../components/Button";
import { Modal } from "../components/Modal";
import { useToast } from "./Toast";
import { useViewer } from "./Viewer";

export type GateReason = "save" | "leave" | "account";

type GateRequest = {
  reason: GateReason;
  onProceed?: () => void;
  onCancel?: () => void;
};

type GuestGateContextValue = {
  request: (request: GateRequest) => void;
  openAccount: () => void;
};

type GateCopy = {
  title: string;
  description: string;
  dismiss: string;
};

const GuestGateContext = createContext<GuestGateContextValue | null>(null);

const COPY: Record<GateReason, GateCopy> = {
  save: {
    title: "Keep this night?",
    description:
      "Create an account to keep tonight's pick and the crew. Your scores and groups stay in one place.",
    dismiss: "Not now",
  },
  leave: {
    title: "Leaving as a guest?",
    description:
      "Create an account to keep your place and tonight's picks. Or leave now — nothing is saved.",
    dismiss: "Leave as guest",
  },
  account: {
    title: "Create your account",
    description: "Save your nights, join clubs and keep every score in one place.",
    dismiss: "Not now",
  },
};

export function GuestGateProvider({ children }: { children: ReactNode }) {
  const { isGuest, isMember, person, createAccount, signIn } = useViewer();
  const { showToast } = useToast();
  const [request, setRequest] = useState<GateRequest | null>(null);
  const lastRequest = useRef<GateRequest | null>(null);

  const anonymous = !isGuest && !isMember;
  const activeReason = request?.reason ?? lastRequest.current?.reason ?? "account";
  const copy = COPY[activeReason];
  const title = anonymous && activeReason === "leave" ? "Leaving the room?" : copy.title;
  const dismissLabel = anonymous && activeReason === "leave" ? "Leave now" : copy.dismiss;

  const showRequest = useCallback((next: GateRequest) => {
    lastRequest.current = next;
    setRequest(next);
  }, []);

  const requestGate = useCallback(
    (next: GateRequest) => {
      if (isMember) {
        next.onProceed?.();
        return;
      }
      showRequest(next);
    },
    [isMember, showRequest],
  );

  const openAccount = useCallback(() => {
    if (isMember) return;
    showRequest({ reason: "account" });
  }, [isMember, showRequest]);

  const close = () => {
    const current = request;
    setRequest(null);
    current?.onCancel?.();
  };

  const decline = () => {
    const current = request;
    setRequest(null);
    if (current?.reason === "leave") {
      current.onProceed?.();
    } else {
      current?.onCancel?.();
    }
  };

  const handleSignIn = () => {
    const current = request;
    signIn();
    setRequest(null);
    showToast("Signed in.");
    current?.onProceed?.();
  };

  const handleCreate = (name: string) => {
    const current = request;
    createAccount(name);
    setRequest(null);
    showToast(
      current?.reason === "leave"
        ? "Account created — your room is waiting."
        : current?.reason === "save"
          ? "Account created — tonight is saved."
          : "Welcome to watchlog.",
    );
    current?.onProceed?.();
  };

  const value = useMemo(() => ({ request: requestGate, openAccount }), [requestGate, openAccount]);

  return (
    <GuestGateContext.Provider value={value}>
      {children}
      <GuestAccountDialog
        open={Boolean(request)}
        title={title}
        description={copy.description}
        dismissLabel={dismissLabel}
        defaultName={person?.name ?? ""}
        isGuest={isGuest}
        onClose={close}
        onDecline={decline}
        onSignIn={handleSignIn}
        onCreate={handleCreate}
      />
    </GuestGateContext.Provider>
  );
}

function GuestAccountDialog({
  open,
  title,
  description,
  dismissLabel,
  defaultName,
  isGuest,
  onClose,
  onDecline,
  onSignIn,
  onCreate,
}: {
  open: boolean;
  title: string;
  description: string;
  dismissLabel: string;
  defaultName: string;
  isGuest: boolean;
  onClose: () => void;
  onDecline: () => void;
  onSignIn: () => void;
  onCreate: (name: string) => void;
}) {
  const [name, setName] = useState(defaultName);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(defaultName);
    setEmail("");
    setPassword("");
    setError(null);
  }, [open, defaultName]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const cleanName = name.trim();
    const cleanEmail = email.trim();

    if (!cleanName) {
      setError("Add the name you want on your account.");
      return;
    }
    if (!cleanEmail.includes("@")) {
      setError("Add an email address.");
      return;
    }
    if (password.length < 6) {
      setError("Use at least 6 characters for your password.");
      return;
    }

    onCreate(cleanName);
  };

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="ghost" onClick={onDecline}>
            {dismissLabel}
          </Button>
          <Button type="submit" form="guest-account-form">
            Create account
          </Button>
        </>
      }
    >
      <form id="guest-account-form" onSubmit={handleSubmit} noValidate>
        <label className="field-label" htmlFor="guest-account-name">
          Your name
        </label>
        <input
          id="guest-account-name"
          className="text-input"
          type="text"
          autoComplete="name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            if (error) setError(null);
          }}
        />

        <label className="field-label field-label-spaced" htmlFor="guest-account-email">
          Email
        </label>
        <input
          id="guest-account-email"
          className="text-input"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            if (error) setError(null);
          }}
        />

        <label className="field-label field-label-spaced" htmlFor="guest-account-password">
          Password
        </label>
        <input
          id="guest-account-password"
          className="text-input"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            if (error) setError(null);
          }}
        />

        {error ? (
          <p className="field-error" role="alert">
            {error}
          </p>
        ) : (
          <p className="field-help">
            {isGuest
              ? "Your guest name comes with you. The email is only for the account."
              : "This is the name your clubs will see. The email is only for the account."}
          </p>
        )}
      </form>

      <button type="button" className="text-button guest-signin" onClick={onSignIn}>
        Already have an account? Sign in
      </button>

      <div className="dialog-note">
        <Info size={15} aria-hidden="true" />
        <span>
          {isGuest
            ? "Nothing is saved until you create an account. You can keep playing as a guest."
            : "No account needed to play. Creating one keeps your nights and scores."}
        </span>
      </div>
    </Modal>
  );
}

export function useGuestGate() {
  const context = useContext(GuestGateContext);
  if (!context) throw new Error("useGuestGate must be used within GuestGateProvider");
  return context;
}

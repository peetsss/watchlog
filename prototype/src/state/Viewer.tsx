import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { people, type Person } from "../data";

export type ViewerMode = "member" | "guest" | "anonymous";

type ViewerState = {
  mode: ViewerMode;
  person: Person | null;
};

type ViewerContextValue = ViewerState & {
  isMember: boolean;
  isGuest: boolean;
  startGuest: (name: string) => Person;
  createAccount: (name: string) => void;
  signIn: () => void;
  signOut: () => void;
};

const ViewerContext = createContext<ViewerContextValue | null>(null);
const STORAGE_KEY = "watchlog.prototype.viewer";
const GUEST_TONES = ["#d09a83", "#9bb39a", "#8fa6bf", "#e7b45a", "#b79ac9"];

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "G";
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function guestPerson(name: string): Person {
  const clean = name.trim() || "Guest";
  const tone =
    GUEST_TONES[
      Math.abs(
        Array.from(clean).reduce((total, character) => total + character.charCodeAt(0), 0),
      ) % GUEST_TONES.length
    ];

  return {
    id: "guest",
    name: clean,
    short: initials(clean),
    color: tone,
  };
}

function isPerson(value: unknown): value is Person {
  if (!value || typeof value !== "object") return false;
  const person = value as Person;
  return (
    typeof person.id === "string" &&
    typeof person.name === "string" &&
    typeof person.short === "string" &&
    typeof person.color === "string"
  );
}

function loadViewer(): ViewerState {
  try {
    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as ViewerState;
      if (parsed.mode === "member" && isPerson(parsed.person)) return parsed;
      if (parsed.mode === "guest" && isPerson(parsed.person)) return parsed;
      if (parsed.mode === "anonymous") return { mode: "anonymous", person: null };
    }
  } catch {
    // Session storage can be unavailable; fall back to the signed-in demo.
  }

  if (window.location.pathname.startsWith("/join/")) {
    return { mode: "anonymous", person: null };
  }

  return { mode: "member", person: people.alex };
}

export function ViewerProvider({ children }: { children: ReactNode }) {
  const [viewer, setViewer] = useState<ViewerState>(loadViewer);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(viewer));
    } catch {
      // The demo still works without persistence.
    }
  }, [viewer]);

  const startGuest = useCallback((name: string) => {
    const person = guestPerson(name);
    setViewer({ mode: "guest", person });
    return person;
  }, []);

  const createAccount = useCallback((name: string) => {
    const profile = guestPerson(name);
    setViewer({ mode: "member", person: { ...profile, id: people.alex.id } });
  }, []);

  const signIn = useCallback(() => {
    setViewer({ mode: "member", person: people.alex });
  }, []);

  const signOut = useCallback(() => {
    setViewer({ mode: "anonymous", person: null });
  }, []);

  return (
    <ViewerContext.Provider
      value={{
        ...viewer,
        isMember: viewer.mode === "member",
        isGuest: viewer.mode === "guest",
        startGuest,
        createAccount,
        signIn,
        signOut,
      }}
    >
      {children}
    </ViewerContext.Provider>
  );
}

export function useViewer() {
  const context = useContext(ViewerContext);
  if (!context) throw new Error("useViewer must be used within ViewerProvider");
  return context;
}

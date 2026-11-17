import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Person } from "../data";
import { api, unwrap } from "../lib/api";
import type { components } from "../lib/api-types";

type Viewer = components["schemas"]["Viewer"];
type ViewerStats = components["schemas"]["ViewerStats"];
type SessionViewer = components["schemas"]["SessionViewer"];
type SessionEnvelope = components["schemas"]["SessionEnvelope"];

export const SESSION_QUERY_KEY = ["session", "me"] as const;

export type SessionStatus = "loading" | "member" | "guest" | "anonymous" | "error";

const ANONYMOUS_SESSION: SessionEnvelope = {
  mode: "anonymous",
  viewer: null,
  stats: null,
  email: null,
};

const EMPTY_STATS = { titles_watched: 0, average_score: null };

type SessionContextValue = {
  status: SessionStatus;
  viewer: SessionViewer | null;
  stats: ViewerStats | null;
  email: string | null;
  emailVerified: boolean;
  /** Viewer shaped for the existing Avatar and member components. */
  person: Person | null;
  error: Error | null;
  signIn: (identifier: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  retry: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

async function loadSession(): Promise<SessionEnvelope> {
  return unwrap<SessionEnvelope>(api.GET("/api/auth/session"));
}

function toPerson(viewer: SessionViewer | null): Person | null {
  if (!viewer) return null;
  return {
    id: viewer.id,
    name: viewer.name,
    short: viewer.initials,
    color: viewer.color,
  };
}

function memberSession(viewer: Viewer, email: string | null): SessionEnvelope {
  return {
    mode: "member",
    viewer: {
      mode: "member",
      id: String(viewer.id),
      name: viewer.username,
      initials: viewer.initials,
      color: viewer.color,
      is_guest: false,
      email_verified: viewer.email_verified,
    },
    stats: EMPTY_STATS,
    email,
  };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const session = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: loadSession,
    retry: false,
    staleTime: 60_000,
  });

  const signIn = useCallback(
    async (identifier: string, password: string) => {
      const payload = await unwrap<components["schemas"]["ViewerEnvelope"]>(
        api.POST("/api/auth/login", { body: { identifier, password } }),
      );
      queryClient.setQueryData(SESSION_QUERY_KEY, memberSession(payload.viewer, null));
      void queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
    },
    [queryClient],
  );

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      const payload = await unwrap<components["schemas"]["ViewerEnvelope"]>(
        api.POST("/api/auth/register", { body: { username, email, password } }),
      );
      queryClient.setQueryData(SESSION_QUERY_KEY, memberSession(payload.viewer, email));
      void queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    try {
      await unwrap(api.POST("/api/auth/logout"));
    } finally {
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      queryClient.setQueryData(SESSION_QUERY_KEY, ANONYMOUS_SESSION);
    }
  }, [queryClient]);

  const retry = useCallback(() => {
    void session.refetch();
  }, [session]);

  const value = useMemo<SessionContextValue>(() => {
    let status: SessionStatus;
    if (session.isPending) status = "loading";
    else if (session.isError) status = "error";
    else status = session.data?.mode ?? "anonymous";

    return {
      status,
      viewer: session.data?.viewer ?? null,
      stats: session.data?.stats ?? null,
      email: session.data?.email ?? null,
      emailVerified: session.data?.viewer?.email_verified ?? false,
      person: toPerson(session.data?.viewer ?? null),
      error: session.error instanceof Error ? session.error : null,
      signIn,
      register,
      signOut,
      retry,
    };
  }, [session.isPending, session.isError, session.data, session.error, signIn, register, signOut, retry]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used within SessionProvider");
  return context;
}

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Person } from "../data";
import { api, ApiError, unwrap } from "../lib/api";
import type { components } from "../lib/api-types";

type Viewer = components["schemas"]["Viewer"];
type ViewerStats = components["schemas"]["ViewerStats"];
type MeEnvelope = components["schemas"]["MeEnvelope"];

export const SESSION_QUERY_KEY = ["session", "me"] as const;

export type SessionStatus = "loading" | "member" | "anonymous" | "error";

type SessionContextValue = {
  status: SessionStatus;
  viewer: Viewer | null;
  stats: ViewerStats | null;
  /** Viewer shaped for the existing Avatar and member components. */
  person: Person | null;
  error: ApiError | null;
  signIn: (username: string, password: string) => Promise<Viewer>;
  register: (username: string, password: string) => Promise<Viewer>;
  signOut: () => Promise<void>;
  retry: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

const EMPTY_STATS: ViewerStats = { titles_watched: 0, average_score: null };

async function loadMe(): Promise<MeEnvelope | null> {
  try {
    return await unwrap<MeEnvelope>(api.GET("/api/me"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

function toPerson(viewer: Viewer | null): Person | null {
  if (!viewer) return null;
  return {
    id: String(viewer.id),
    name: viewer.username,
    short: viewer.initials,
    color: viewer.color,
  };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const me = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: loadMe,
    retry: false,
    staleTime: 60_000,
  });

  const signIn = useCallback(
    async (username: string, password: string) => {
      const payload = await unwrap<components["schemas"]["ViewerEnvelope"]>(
        api.POST("/api/auth/login", { body: { username, password } }),
      );
      queryClient.setQueryData(SESSION_QUERY_KEY, {
        viewer: payload.viewer,
        stats: EMPTY_STATS,
      } satisfies MeEnvelope);
      void queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
      return payload.viewer;
    },
    [queryClient],
  );

  const register = useCallback(
    async (username: string, password: string) => {
      const payload = await unwrap<components["schemas"]["ViewerEnvelope"]>(
        api.POST("/api/auth/register", { body: { username, password } }),
      );
      queryClient.setQueryData(SESSION_QUERY_KEY, {
        viewer: payload.viewer,
        stats: EMPTY_STATS,
      } satisfies MeEnvelope);
      void queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
      return payload.viewer;
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
      queryClient.setQueryData(SESSION_QUERY_KEY, null);
    }
  }, [queryClient]);

  const retry = useCallback(() => {
    void me.refetch();
  }, [me]);

  const value = useMemo<SessionContextValue>(() => {
    let status: SessionStatus;
    if (me.isPending) status = "loading";
    else if (me.isError) status = "error";
    else status = me.data ? "member" : "anonymous";

    const error =
      me.error instanceof ApiError
        ? me.error
        : me.error
          ? new ApiError("Could not reach watchlog.", "network_error", 0)
          : null;

    return {
      status,
      viewer: me.data?.viewer ?? null,
      stats: me.data?.stats ?? null,
      person: toPerson(me.data?.viewer ?? null),
      error,
      signIn,
      register,
      signOut,
      retry,
    };
  }, [me.isPending, me.isError, me.data, me.error, signIn, register, signOut, retry]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used within SessionProvider");
  return context;
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { type LobbyView, lobbyToView } from "./adapters";
import {
  type LobbyAction,
  leaveLobby,
  lobbySocketUrl,
  performLobbyAction,
  useLobbyState,
} from "./api-lobby";
import { ApiError } from "./api";
import type { components } from "./api-types";
import { groupKeys, homeKeys, lobbyKeys } from "./query-keys";

type SocketMessage = {
  type?: string;
  lobby?: components["schemas"]["LobbyState"];
  code?: string;
  message?: string;
  new_lobby_uuid?: string;
};

export type LobbyConnection = "connecting" | "open" | "offline";
export type LobbyCloseReason =
  | "unauthorized"
  | "removed"
  | "forbidden"
  | "not_found"
  | "left"
  | null;

function actionError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The room couldn't complete that action.";
}

export function useLobbyRoom(lobbyId: string | undefined) {
  const queryClient = useQueryClient();
  const stateQuery = useLobbyState(lobbyId);
  const socketRef = useRef<WebSocket | null>(null);
  const [connection, setConnection] = useState<LobbyConnection>("connecting");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [closed, setClosed] = useState<LobbyCloseReason>(null);
  const [restartedTo, setRestartedTo] = useState<string | null>(null);

  const cacheKey = useMemo(() => lobbyKeys.state(lobbyId ?? ""), [lobbyId]);

  const applyState = useCallback(
    (next: LobbyView) => {
      if (!lobbyId) return;
      const previous = queryClient.getQueryData<LobbyView>(cacheKey);
      if (previous && next.version < previous.version) return;

      queryClient.setQueryData(cacheKey, next);
      if (!previous || previous.status !== next.status) {
        void queryClient.invalidateQueries({ queryKey: homeKeys.all });
        void queryClient.invalidateQueries({ queryKey: lobbyKeys.active() });
      }
      if (next.status === "finished" && next.groupId) {
        void queryClient.invalidateQueries({ queryKey: groupKeys.watchlist(next.groupId) });
        void queryClient.invalidateQueries({ queryKey: groupKeys.stats(next.groupId) });
        void queryClient.invalidateQueries({ queryKey: groupKeys.list() });
        void queryClient.invalidateQueries({ queryKey: groupKeys.detail(next.groupId) });
      }
    },
    [cacheKey, lobbyId, queryClient],
  );

  useEffect(() => {
    if (!lobbyId) return;
    let stopped = false;
    let attempts = 0;
    let retryTimer: number | undefined;
    let socket: WebSocket | null = null;

    setClosed(null);
    setRestartedTo(null);
    setActionMessage(null);
    setConnection("connecting");

    const connect = () => {
      if (stopped) return;
      setConnection("connecting");
      const current = new WebSocket(lobbySocketUrl(lobbyId));
      socket = current;
      socketRef.current = current;

      current.onopen = () => {
        if (stopped) return;
        attempts = 0;
        setConnection("open");
      };

      current.onmessage = (event) => {
        if (stopped) return;
        let message: SocketMessage;
        try {
          message = JSON.parse(String(event.data)) as SocketMessage;
        } catch {
          return;
        }

        if (message.type === "lobby.state" && message.lobby) {
          applyState(lobbyToView(message.lobby));
          setPendingAction(null);
          setActionMessage(null);
          return;
        }
        if (message.type === "lobby.error") {
          setPendingAction(null);
          setActionMessage(message.message ?? "The room rejected that action.");
          return;
        }
        if (message.type === "lobby.removed") {
          setPendingAction(null);
          setClosed("removed");
          return;
        }
        if (message.type === "lobby.left") {
          setClosed("left");
          return;
        }
        if (message.type === "lobby.restarted" && message.new_lobby_uuid) {
          setRestartedTo(message.new_lobby_uuid);
        }
      };

      current.onclose = (event) => {
        if (stopped) return;
        socket = null;
        socketRef.current = null;
        setConnection("offline");
        setPendingAction(null);

        if (event.code === 4401) {
          setClosed("unauthorized");
          void queryClient.invalidateQueries({ queryKey: ["session", "me"] });
          return;
        }
        if (event.code === 4403) {
          setClosed((value) => value ?? "forbidden");
          return;
        }
        if (event.code === 4404) {
          setClosed("not_found");
          return;
        }
        if (event.code === 4000) {
          setClosed("left");
          return;
        }
        if (event.code === 4001) {
          return;
        }

        attempts += 1;
        const delay = Math.min(10_000, 450 * 2 ** (attempts - 1)) + Math.random() * 300;
        retryTimer = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      stopped = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socketRef.current = null;
      if (socket) {
        socket.onclose = null;
        socket.close(1000, "leaving");
      }
    };
  }, [applyState, lobbyId, queryClient]);

  const send = useCallback(
    async (
      action: LobbyAction,
      payload: Record<string, unknown> = {},
    ): Promise<boolean> => {
      if (!lobbyId) return false;
      setActionMessage(null);
      setPendingAction(action);

      const socket = socketRef.current;
      if (socket?.readyState === WebSocket.OPEN) {
        try {
          socket.send(JSON.stringify({ action, ...payload }));
          return true;
        } catch {
          setActionMessage("The room connection dropped. Try again.");
          setPendingAction(null);
          return false;
        }
      }

      try {
        const next = await performLobbyAction(lobbyId, action, payload);
        if (next) applyState(next);
        return true;
      } catch (error) {
        setActionMessage(actionError(error));
        return false;
      } finally {
        setPendingAction(null);
      }
    },
    [applyState, lobbyId],
  );

  const leave = useCallback(async (): Promise<boolean> => {
    if (!lobbyId) return false;
    setPendingAction("leave");
    setActionMessage(null);
    try {
      await leaveLobby(lobbyId);
      setClosed("left");
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
      void queryClient.invalidateQueries({ queryKey: lobbyKeys.active() });
      return true;
    } catch (error) {
      setActionMessage(actionError(error));
      return false;
    } finally {
      setPendingAction(null);
    }
  }, [lobbyId, queryClient]);

  const end = useCallback(async (): Promise<boolean> => {
    if (!lobbyId) return false;
    setPendingAction("end");
    setActionMessage(null);
    try {
      const next = await performLobbyAction(lobbyId, "end");
      if (next) applyState(next);
      return true;
    } catch (error) {
      setActionMessage(actionError(error));
      return false;
    } finally {
      setPendingAction(null);
    }
  }, [applyState, lobbyId]);

  const restart = useCallback(async (): Promise<string | null> => {
    if (!lobbyId) return null;
    setPendingAction("restart");
    setActionMessage(null);
    try {
      const next = await performLobbyAction(lobbyId, "restart");
      if (next) {
        queryClient.setQueryData(lobbyKeys.state(next.uuid), next);
        setRestartedTo(next.uuid);
      }
      return next?.uuid ?? null;
    } catch (error) {
      setActionMessage(actionError(error));
      return null;
    } finally {
      setPendingAction(null);
    }
  }, [applyState, lobbyId]);

  return {
    lobby: stateQuery.data ?? null,
    isPending: stateQuery.isPending,
    error: stateQuery.error,
    refetch: stateQuery.refetch,
    connection,
    pendingAction,
    actionMessage,
    closed,
    restartedTo,
    send,
    leave,
    end,
    restart,
  };
}

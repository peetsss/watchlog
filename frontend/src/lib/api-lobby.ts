import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type LobbyPreviewView,
  type LobbySummaryView,
  type LobbyView,
  lobbyPreviewToView,
  lobbySummaryToView,
  lobbyToView,
} from "./adapters";
import { api, ApiError, unwrap } from "./api";
import type { components } from "./api-types";
import { lobbyKeys } from "./query-keys";

export type LobbyAction =
  | "ready"
  | "unready"
  | "start"
  | "vote"
  | "pick"
  | "advance"
  | "next-round"
  | "finalize";

type LobbyStateEnvelope = components["schemas"]["LobbyStateEnvelope"];

function retryUnlessDenied(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false;
  return failureCount < 1;
}

async function fetchLobbyState(lobbyId: string): Promise<LobbyView> {
  const payload = await unwrap<LobbyStateEnvelope>(
    api.GET("/api/lobby/{lobby_uuid}/", {
      params: { path: { lobby_uuid: lobbyId } },
    }),
  );
  return lobbyToView(payload.lobby);
}

async function fetchActiveLobby(): Promise<LobbySummaryView | null> {
  const payload = await unwrap<components["schemas"]["ActiveEnvelope"]>(
    api.GET("/api/lobby/active/"),
  );
  return payload.active ? lobbySummaryToView(payload.active) : null;
}

async function fetchLobbyPreview(lobbyId: string): Promise<LobbyPreviewView> {
  const payload = await unwrap<components["schemas"]["JoinPreviewEnvelope"]>(
    api.GET("/api/lobby/{lobby_uuid}/preview/", {
      params: { path: { lobby_uuid: lobbyId } },
    }),
  );
  return lobbyPreviewToView(payload.preview);
}

export function useLobbyState(lobbyId: string | undefined) {
  const queryClient = useQueryClient();
  const queryKey = lobbyKeys.state(lobbyId ?? "");
  return useQuery({
    queryKey,
    queryFn: async () => {
      const next = await fetchLobbyState(lobbyId as string);
      const cached = queryClient.getQueryData<LobbyView>(queryKey);
      return cached && cached.version > next.version ? cached : next;
    },
    enabled: Boolean(lobbyId),
    staleTime: 30_000,
    retry: retryUnlessDenied,
  });
}

export function useActiveLobby(enabled = true) {
  return useQuery({
    queryKey: lobbyKeys.active(),
    queryFn: fetchActiveLobby,
    enabled,
    staleTime: 10_000,
    refetchInterval: enabled ? 10_000 : false,
    retry: retryUnlessDenied,
  });
}

export function useLobbyPreview(lobbyId: string | undefined) {
  return useQuery({
    queryKey: lobbyKeys.preview(lobbyId ?? ""),
    queryFn: () => fetchLobbyPreview(lobbyId as string),
    enabled: Boolean(lobbyId),
    staleTime: 15_000,
    retry: retryUnlessDenied,
  });
}

export async function createLobby(groupId?: string): Promise<LobbyView> {
  const payload = groupId
    ? await unwrap<LobbyStateEnvelope>(
        api.POST("/api/groups/{group_id}/lobbies", {
          params: { path: { group_id: groupId } },
        }),
      )
    : await unwrap<LobbyStateEnvelope>(api.POST("/api/lobby/", { body: {} }));
  return lobbyToView(payload.lobby);
}

export async function joinLobby(lobbyId: string): Promise<LobbyView> {
  const payload = await unwrap<LobbyStateEnvelope>(
    api.POST("/api/lobby/{lobby_uuid}/join/", {
      params: { path: { lobby_uuid: lobbyId } },
    }),
  );
  return lobbyToView(payload.lobby);
}

export async function performLobbyAction(
  lobbyId: string,
  action: string,
  payload: Record<string, unknown> = {},
): Promise<LobbyView | null> {
  const result = await api.POST("/api/lobby/{lobby_uuid}/{action}/", {
    params: { path: { lobby_uuid: lobbyId, action } },
    // The action router reads a raw JSON body, so the generated schema has no
    // request body for this path.
    body: payload as never,
  });
  const data = await unwrap<LobbyStateEnvelope | undefined>(Promise.resolve(result));
  return data ? lobbyToView(data.lobby) : null;
}

export async function leaveLobby(lobbyId: string): Promise<void> {
  await unwrap(
    api.POST("/api/lobby/{lobby_uuid}/{action}/", {
      params: { path: { lobby_uuid: lobbyId, action: "leave" } },
      body: {} as never,
    }),
  );
}

export function lobbySocketUrl(lobbyId: string): string {
  const explicit = import.meta.env.VITE_WS_URL;
  if (explicit) {
    return `${explicit.replace(/\/$/, "")}/ws/lobby/${lobbyId}/`;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/lobby/${lobbyId}/`;
}

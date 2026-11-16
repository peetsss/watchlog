import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type GroupFilmView,
  type GroupPreviewView,
  type GroupStatsView,
  type GroupSummaryView,
  type MemberScoreView,
  groupFilmToView,
  groupPreviewToView,
  groupStatsToView,
  groupSummaryToView,
  scoreToPerson,
} from "./adapters";
import { api, ApiError, unwrap } from "./api";
import type { components } from "./api-types";
import { groupKeys, homeKeys } from "./query-keys";

type GroupDetail = components["schemas"]["GroupDetail"];
type GroupFilmScores = components["schemas"]["GroupFilmScores"];

function retryUnlessDenied(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false;
  return failureCount < 1;
}

async function fetchGroupList(): Promise<GroupSummaryView[]> {
  const payload = await unwrap<components["schemas"]["GroupList"]>(api.GET("/api/groups"));
  return payload.groups.map(groupSummaryToView);
}

async function fetchGroup(groupId: string): Promise<GroupSummaryView> {
  const payload = await unwrap<GroupDetail>(
    api.GET("/api/groups/{group_id}", { params: { path: { group_id: groupId } } }),
  );
  return groupSummaryToView(payload);
}

async function fetchGroupWatchlist(groupId: string): Promise<GroupFilmView[]> {
  const payload = await unwrap<components["schemas"]["GroupFilmList"]>(
    api.GET("/api/groups/{group_id}/watchlist", { params: { path: { group_id: groupId } } }),
  );
  return payload.films.map(groupFilmToView);
}

async function fetchGroupStats(groupId: string): Promise<GroupStatsView> {
  const payload = await unwrap<components["schemas"]["GroupStats"]>(
    api.GET("/api/groups/{group_id}/stats", { params: { path: { group_id: groupId } } }),
  );
  return groupStatsToView(payload);
}

async function fetchGroupPreview(groupId: string): Promise<GroupPreviewView> {
  const payload = await unwrap<components["schemas"]["GroupPreview"]>(
    api.GET("/api/groups/{group_id}/preview", { params: { path: { group_id: groupId } } }),
  );
  return groupPreviewToView(payload);
}

async function fetchFilmScores(groupId: string, filmId: number): Promise<MemberScoreView[]> {
  const payload = await unwrap<GroupFilmScores>(
    api.GET("/api/groups/{group_id}/films/{film_id}/scores", {
      params: { path: { group_id: groupId, film_id: filmId } },
    }),
  );
  return payload.scores.map((score) => ({ person: scoreToPerson(score), score: score.score }));
}

export function groupWatchlistQueryOptions(groupId: string) {
  return {
    queryKey: groupKeys.watchlist(groupId),
    queryFn: () => fetchGroupWatchlist(groupId),
    staleTime: 15_000,
    retry: retryUnlessDenied,
  };
}

export function useGroupList() {
  return useQuery({
    queryKey: groupKeys.list(),
    queryFn: fetchGroupList,
    staleTime: 15_000,
    retry: retryUnlessDenied,
  });
}

export function useGroup(groupId: string | undefined) {
  return useQuery({
    queryKey: groupKeys.detail(groupId ?? ""),
    queryFn: () => fetchGroup(groupId as string),
    enabled: Boolean(groupId),
    staleTime: 30_000,
    retry: retryUnlessDenied,
  });
}

export function useGroupWatchlist(groupId: string | undefined) {
  return useQuery({
    ...groupWatchlistQueryOptions(groupId ?? ""),
    enabled: Boolean(groupId),
  });
}

export function useGroupStats(groupId: string | undefined) {
  return useQuery({
    queryKey: groupKeys.stats(groupId ?? ""),
    queryFn: () => fetchGroupStats(groupId as string),
    enabled: Boolean(groupId),
    staleTime: 15_000,
    retry: retryUnlessDenied,
  });
}

export function useGroupPreview(groupId: string | undefined) {
  return useQuery({
    queryKey: groupKeys.preview(groupId ?? ""),
    queryFn: () => fetchGroupPreview(groupId as string),
    enabled: Boolean(groupId),
    staleTime: 30_000,
    retry: retryUnlessDenied,
  });
}

export function useGroupFilmScores(groupId: string, filmId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: groupKeys.scores(groupId, filmId ?? 0),
    queryFn: () => fetchFilmScores(groupId, filmId as number),
    enabled: enabled && filmId !== null,
    staleTime: 15_000,
    retry: retryUnlessDenied,
  });
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string; description?: string }) => {
      const payload = await unwrap<GroupDetail>(
        api.POST("/api/groups", {
          body: { name: input.name, description: input.description || null },
        }),
      );
      return groupSummaryToView(payload);
    },
    onSuccess: (group) => {
      queryClient.setQueryData(groupKeys.detail(group.id), group);
      void queryClient.invalidateQueries({ queryKey: groupKeys.list() });
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
    },
  });
}

export function useAddFilm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      groupId: string;
      tmdbId: number;
      mediaType: "movie" | "series";
    }) =>
      unwrap<components["schemas"]["GroupFilm"]>(
        api.POST("/api/groups/{group_id}/films", {
          params: { path: { group_id: input.groupId } },
          body: { tmdb_id: input.tmdbId, media_type: input.mediaType },
        }),
      ),
    onSuccess: (_film, input) => {
      void queryClient.invalidateQueries({ queryKey: groupKeys.watchlist(input.groupId) });
      void queryClient.invalidateQueries({ queryKey: groupKeys.stats(input.groupId) });
      void queryClient.invalidateQueries({ queryKey: groupKeys.list() });
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
    },
  });
}

export function useSetFilmScore() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { groupId: string; filmId: number; score: number }) =>
      unwrap<components["schemas"]["GroupFilm"]>(
        api.PUT("/api/groups/{group_id}/films/{film_id}/score", {
          params: { path: { group_id: input.groupId, film_id: input.filmId } },
          body: { score: input.score },
        }),
      ),
    onSuccess: (_film, input) => {
      void queryClient.invalidateQueries({ queryKey: groupKeys.watchlist(input.groupId) });
      void queryClient.invalidateQueries({ queryKey: groupKeys.stats(input.groupId) });
      void queryClient.invalidateQueries({
        queryKey: groupKeys.scores(input.groupId, input.filmId),
      });
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
    },
  });
}

export function useSetFilmStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      groupId: string;
      filmId: number;
      status: "up_next" | "watched";
    }) =>
      unwrap<components["schemas"]["GroupFilm"]>(
        api.PATCH("/api/groups/{group_id}/films/{film_id}", {
          params: { path: { group_id: input.groupId, film_id: input.filmId } },
          body: { status: input.status },
        }),
      ),
    onSuccess: (_film, input) => {
      void queryClient.invalidateQueries({ queryKey: groupKeys.watchlist(input.groupId) });
      void queryClient.invalidateQueries({ queryKey: groupKeys.stats(input.groupId) });
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
    },
  });
}

export function useJoinGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (groupId: string) => {
      const payload = await unwrap<GroupDetail>(
        api.POST("/api/groups/{group_id}/members", {
          params: { path: { group_id: groupId } },
        }),
      );
      return groupSummaryToView(payload);
    },
    onSuccess: (group) => {
      queryClient.setQueryData(groupKeys.detail(group.id), group);
      void queryClient.invalidateQueries({ queryKey: groupKeys.list() });
      void queryClient.invalidateQueries({ queryKey: groupKeys.preview(group.id) });
      void queryClient.invalidateQueries({ queryKey: homeKeys.all });
    },
  });
}

export async function getGroupInviteLink(groupId: string): Promise<string> {
  const payload = await unwrap<components["schemas"]["InviteLinkResponse"]>(
    api.GET("/api/groups/{group_id}/invite", { params: { path: { group_id: groupId } } }),
  );
  const invite = new URL(payload.invite_link);
  return `${window.location.origin}${invite.pathname}`;
}

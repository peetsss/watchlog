export const groupKeys = {
  all: ["groups"] as const,
  list: () => [...groupKeys.all, "list"] as const,
  detail: (groupId: string) => [...groupKeys.all, "detail", groupId] as const,
  watchlist: (groupId: string) => [...groupKeys.all, "watchlist", groupId] as const,
  stats: (groupId: string) => [...groupKeys.all, "stats", groupId] as const,
  preview: (groupId: string) => [...groupKeys.all, "preview", groupId] as const,
  invite: (groupId: string) => [...groupKeys.all, "invite", groupId] as const,
  scores: (groupId: string, filmId: number) =>
    [...groupKeys.all, "scores", groupId, filmId] as const,
};

export const movieKeys = {
  all: ["movies"] as const,
  search: (query: string) => [...movieKeys.all, "search", query] as const,
  detail: (movieId: number) => [...movieKeys.all, "detail", movieId] as const,
};

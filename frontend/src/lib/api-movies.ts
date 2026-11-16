import { useQuery } from "@tanstack/react-query";
import {
  type MovieDetailView,
  type MovieSearchView,
  movieDetailToView,
  movieSearchToView,
} from "./adapters";
import { api, ApiError, unwrap } from "./api";
import type { components } from "./api-types";
import { movieKeys } from "./query-keys";

function retryUnlessUnavailable(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  if (error instanceof ApiError && error.code === "tmdb_unavailable") return false;
  return failureCount < 1;
}

async function fetchMovieSearch(query: string): Promise<MovieSearchView[]> {
  const payload = await unwrap<components["schemas"]["MovieSearchEnvelope"]>(
    api.GET("/api/movies/search", { params: { query: { q: query } } }),
  );
  return payload.movies.map(movieSearchToView);
}

async function fetchMovieDetail(movieId: number): Promise<MovieDetailView> {
  const payload = await unwrap<components["schemas"]["MovieDetail"]>(
    api.GET("/api/movies/{movie_id}", { params: { path: { movie_id: movieId } } }),
  );
  return movieDetailToView(payload);
}

export function useMovieSearch(query: string) {
  return useQuery({
    queryKey: movieKeys.search(query),
    queryFn: () => fetchMovieSearch(query),
    enabled: query.trim().length > 0,
    staleTime: 60_000,
    retry: retryUnlessUnavailable,
  });
}

export function useMovieDetail(movieId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: movieKeys.detail(movieId ?? 0),
    queryFn: () => fetchMovieDetail(movieId as number),
    enabled: enabled && movieId !== null,
    staleTime: 5 * 60_000,
    retry: retryUnlessUnavailable,
  });
}

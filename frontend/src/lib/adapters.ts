import type { Person } from "../data";
import type { components } from "./api-types";

type ApiGroupMember = components["schemas"]["GroupMember"];
type ApiGroupSummary = components["schemas"]["GroupSummary"];
type ApiGroupFilm = components["schemas"]["GroupFilm"];
type ApiGroupPreview = components["schemas"]["GroupPreview"];
type ApiGroupStats = components["schemas"]["GroupStats"];
type ApiMemberScore = components["schemas"]["MemberScore"];
type ApiMovieSummary = components["schemas"]["MovieSummary"];
type ApiMovieDetail = components["schemas"]["MovieDetail"];
type ApiMovieSearchResult = components["schemas"]["MovieSearchResult"];

export type GroupMemberView = Person & {
  role: "admin" | "member";
};

export type GroupSummaryView = {
  id: string;
  name: string;
  description: string;
  members: GroupMemberView[];
  memberCount: number;
  filmCount: number;
};

export type GroupPreviewView = {
  id: string;
  name: string;
  description: string;
  memberCount: number;
  filmCount: number;
  isMember: boolean;
};

export type MovieSummaryView = {
  id: number;
  tmdbId: number | null;
  title: string;
  year: number | null;
  releaseDate: string | null;
  runtime: number | null;
  genres: string[];
  director: string | null;
  description: string;
  poster: string | null;
  backdrop: string | null;
};

export type MovieDetailView = MovieSummaryView & {
  tagline: string | null;
  writers: string[];
  cast: string[];
  language: string | null;
};

export type GroupFilmView = {
  id: number;
  movie: MovieSummaryView;
  status: "up_next" | "watched";
  addedAt: string;
  addedBy: string | null;
  clubScore: number | null;
  scoreCount: number;
  yourScore: number | null;
};

export type MemberScoreView = {
  person: Person;
  score: number;
};

export type GroupStatsView = {
  filmCount: number;
  watchedCount: number;
  upNextCount: number;
  memberCount: number;
  averageScore: number | null;
};

export type MovieSearchView = {
  key: string;
  tmdbId: number;
  movieId: number | null;
  title: string;
  year: string | null;
  poster: string | null;
  mediaType: "movie" | "series";
};

export function splitList(value: string | null | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function yearFromDate(value: string | null | undefined): number | null {
  if (!value) return null;
  const year = Number(value.slice(0, 4));
  return Number.isFinite(year) && year > 0 ? year : null;
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function memberToPerson(member: ApiGroupMember): GroupMemberView {
  return {
    id: String(member.id),
    name: member.username,
    short: member.initials,
    color: member.color,
    role: member.role,
  };
}

export function scoreToPerson(score: ApiMemberScore): Person {
  return {
    id: String(score.user_id),
    name: score.username,
    short: score.initials,
    color: score.color,
  };
}

export function groupSummaryToView(group: ApiGroupSummary): GroupSummaryView {
  return {
    id: group.id,
    name: group.name,
    description: group.description ?? "",
    members: group.members.map(memberToPerson),
    memberCount: group.member_count,
    filmCount: group.film_count,
  };
}

export function groupPreviewToView(preview: ApiGroupPreview): GroupPreviewView {
  return {
    id: preview.id,
    name: preview.name,
    description: preview.description ?? "",
    memberCount: preview.member_count,
    filmCount: preview.film_count,
    isMember: preview.is_member,
  };
}

export function movieSummaryToView(movie: ApiMovieSummary): MovieSummaryView {
  return {
    id: movie.id,
    tmdbId: movie.tmdb_id,
    title: movie.title,
    year: yearFromDate(movie.release_date),
    releaseDate: movie.release_date,
    runtime: movie.runtime,
    genres: splitList(movie.genres),
    director: movie.director,
    description: movie.description ?? "",
    poster: movie.poster_path,
    backdrop: movie.backdrop_path,
  };
}

export function movieDetailToView(movie: ApiMovieDetail): MovieDetailView {
  return {
    ...movieSummaryToView(movie),
    tagline: movie.tagline,
    writers: splitList(movie.writers),
    cast: splitList(movie.actors),
    language: movie.spoken_languages ?? movie.original_language,
  };
}

export function groupFilmToView(film: ApiGroupFilm): GroupFilmView {
  return {
    id: film.id,
    movie: movieSummaryToView(film.movie),
    status: film.status,
    addedAt: film.added_at,
    addedBy: film.added_by,
    clubScore: film.club_score,
    scoreCount: film.score_count,
    yourScore: film.your_score,
  };
}

export function groupStatsToView(stats: ApiGroupStats): GroupStatsView {
  return {
    filmCount: stats.film_count,
    watchedCount: stats.watched_count,
    upNextCount: stats.up_next_count,
    memberCount: stats.member_count,
    averageScore: stats.average_score,
  };
}

export function movieSearchToView(movie: ApiMovieSearchResult): MovieSearchView {
  return {
    key: `${movie.media_type}:${movie.tmdb_id}`,
    tmdbId: movie.tmdb_id,
    movieId: movie.movie_id ?? null,
    title: movie.title,
    year: movie.year,
    poster: movie.poster_url,
    mediaType: movie.media_type,
  };
}

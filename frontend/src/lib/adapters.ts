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
type ApiHomeResponse = components["schemas"]["HomeResponse"];
type ApiHomeLogEntry = components["schemas"]["HomeLogEntry"];
type ApiLobbyState = components["schemas"]["LobbyState"];
type ApiLobbySummary = components["schemas"]["LobbySummary"];
type ApiLobbyPreview = components["schemas"]["JoinPreview"];
type ApiMovieRef = components["schemas"]["MovieRef"];
type ApiWatchAvailability = components["schemas"]["WatchAvailability"];
type WatchOfferType = "flatrate" | "free" | "ads" | "rent" | "buy";

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
  activeLobby: LobbyPreviewView | null;
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

export type WatchProviderView = {
  id: number;
  name: string;
  logoUrl: string | null;
  priority: number;
};

export type WatchAvailabilityView = {
  region: string;
  link: string | null;
  fetchedAt: string | null;
  stale: boolean;
  offers: Record<WatchOfferType, WatchProviderView[]>;
};

export type MovieDetailView = MovieSummaryView & {
  tagline: string | null;
  writers: string[];
  cast: string[];
  language: string | null;
  tmdbScore: number | null;
  imdbId: string | null;
  imdbScore: number | null;
  rottentomatoScore: string | null;
  metacriticScore: string | null;
  filmwebScore: number | null;
  imdbUrl: string | null;
  rottentomatoUrl: string | null;
  metacriticUrl: string | null;
  filmwebUrl: string | null;
  homepage: string | null;
  voteCount: number | null;
  watch: WatchAvailabilityView | null;
};

export type GroupRefView = {
  id: string;
  name: string;
  status: "up_next" | "watched";
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
  alsoInGroups: GroupRefView[];
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
  overview: string;
  tmdbScore: number | null;
};

export type HomeLogEntryView = {
  filmId: number;
  groupId: string;
  groupName: string;
  movie: MovieSummaryView;
  watchedAt: string;
  clubScore: number | null;
  scoreCount: number;
};

export type HomeFeaturedGroupView = GroupSummaryView & {
  upNextCount: number;
  upNext: MovieSummaryView[];
  lastWatched: HomeLogEntryView | null;
};

export type HomeActiveLobbyView = {
  uuid: string;
  type: "group" | "open";
  status: string;
  groupName: string | null;
  hostUsername: string | null;
  playerCount: number;
  currentMovieTitle: string | null;
};

export type HomeView = {
  crews: {
    count: number;
    filmCount: number;
    watchedCount: number;
  };
  featuredGroup: HomeFeaturedGroupView | null;
  activeLobby: HomeActiveLobbyView | null;
  log: HomeLogEntryView[];
};

export type LobbyVote = "in" | "seen" | "out";
export type LobbyStatus = "ready" | "playing" | "final_round" | "finished";
export type LobbyStage = "waiting" | "playing" | "final" | "winner";

export type LobbyPlayerView = Person & {
  isHost: boolean;
  isGuest: boolean;
  isReady: boolean;
};

export type LobbyBallotEntryView = {
  person: Person;
  choice: LobbyVote;
};

export type LobbyFinalistView = {
  movie: MovieSummaryView;
  pickCount: number | null;
  viewerPicked: boolean;
  watch: WatchAvailabilityView | null;
};

export type LobbyCapabilitiesView = {
  canStart: boolean;
  canUnready: boolean;
  canAdvance: boolean;
  canNextRound: boolean;
  canFinalize: boolean;
  canEnd: boolean;
  canLeave: boolean;
  canRestart: boolean;
};

export type LobbyView = {
  uuid: string;
  type: "group" | "open";
  status: LobbyStatus;
  stage: LobbyStage;
  version: number;
  hostId: string | null;
  groupId: string | null;
  groupName: string | null;
  viewerId: string;
  viewerIsHost: boolean;
  viewerReady: boolean;
  players: LobbyPlayerView[];
  playerCount: number;
  readyCount: number;
  poolSize: number;
  poolIndex: number;
  roundNumber: number;
  remainingCount: number;
  currentMovie: MovieSummaryView | null;
  submittedCount: number;
  viewerVote: LobbyVote | null;
  revealed: boolean;
  voteTally: {
    interested: number;
    watched: number;
    notInterested: number;
    total: number;
  } | null;
  ballot: LobbyBallotEntryView[];
  finalists: LobbyFinalistView[];
  picksRevealed: boolean;
  viewerPick: number | null;
  winner: MovieSummaryView | null;
  winnerWatch: WatchAvailabilityView | null;
  shortlisted: boolean;
  tie: boolean;
  capabilities: LobbyCapabilitiesView;
};

export type LobbySummaryView = {
  uuid: string;
  type: "group" | "open";
  status: LobbyStatus;
  groupName: string | null;
  hostUsername: string | null;
  playerCount: number;
  currentMovieTitle: string | null;
};

export type LobbyPreviewView = {
  uuid: string;
  type: "group" | "open";
  status: LobbyStatus;
  groupId: string | null;
  groupName: string | null;
  hostUsername: string | null;
  playerCount: number;
  canJoin: boolean;
  isParticipant: boolean;
  isGroupMember: boolean;
};

const VOTE_FROM_API: Record<string, LobbyVote> = {
  interested: "in",
  watched: "seen",
  not_interested: "out",
};

export const VOTE_TO_API: Record<LobbyVote, string> = {
  in: "interested",
  seen: "watched",
  out: "not_interested",
};

function statusToStage(status: LobbyStatus): LobbyStage {
  if (status === "ready") return "waiting";
  if (status === "playing") return "playing";
  if (status === "final_round") return "final";
  return "winner";
}

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
    activeLobby: group.active_lobby ? lobbyPreviewToView(group.active_lobby) : null,
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

type MovieFields = {
  id: number;
  tmdb_id: number | null;
  title: string;
  release_date: string | null;
  runtime: number | null;
  genres: string | null;
  director: string | null;
  description: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
};

function movieFieldsToView(movie: MovieFields): MovieSummaryView {
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

export function movieSummaryToView(movie: ApiMovieSummary): MovieSummaryView {
  return movieFieldsToView(movie);
}


export function watchToView(watch: ApiWatchAvailability | null | undefined): WatchAvailabilityView | null {
  if (!watch) return null;
  const offers = {} as Record<WatchOfferType, WatchProviderView[]>;
  for (const type of ["flatrate", "free", "ads", "rent", "buy"] as const) {
    offers[type] = (watch.offers[type] ?? []).map((provider) => ({
      id: provider.provider_id,
      name: provider.name,
      logoUrl: provider.logo_url,
      priority: provider.priority,
    }));
  }
  return {
    region: watch.region,
    link: watch.link,
    fetchedAt: watch.fetched_at,
    stale: watch.stale,
    offers,
  };
}

export function movieDetailToView(movie: ApiMovieDetail): MovieDetailView {
  return {
    ...movieSummaryToView(movie),
    tagline: movie.tagline,
    writers: splitList(movie.writers),
    cast: splitList(movie.actors),
    language: movie.spoken_languages ?? movie.original_language,
    tmdbScore: movie.tmdb_score,
    imdbId: movie.imdb_id,
    imdbScore: movie.imdb_score,
    rottentomatoScore: movie.rottentomato_score,
    metacriticScore: movie.metacritic_score,
    filmwebScore: movie.filmweb_score,
    imdbUrl: movie.imdb_url,
    rottentomatoUrl: movie.rottentomato_url,
    metacriticUrl: movie.metacritic_url,
    filmwebUrl: movie.filmweb_url,
    homepage: movie.homepage,
    voteCount: movie.vote_count,
    watch: watchToView(movie.watch),
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
    alsoInGroups: (film.also_in_groups ?? []).map((group) => ({
      id: group.id,
      name: group.name,
      status: group.status,
    })),
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
    overview: movie.overview ?? "",
    tmdbScore: movie.tmdb_score ?? null,
  };
}

export function homeLogToView(entry: ApiHomeLogEntry): HomeLogEntryView {
  return {
    filmId: entry.film_id,
    groupId: entry.group_id,
    groupName: entry.group_name,
    movie: movieSummaryToView(entry.movie),
    watchedAt: entry.watched_at,
    clubScore: entry.club_score,
    scoreCount: entry.score_count,
  };
}

export function homeToView(home: ApiHomeResponse): HomeView {
  const featured = home.featured_group;
  return {
    crews: {
      count: home.crews.count,
      filmCount: home.crews.film_count,
      watchedCount: home.crews.watched_count,
    },
    activeLobby: home.active_lobby
      ? {
          uuid: home.active_lobby.uuid,
          type: home.active_lobby.type,
          status: home.active_lobby.status,
          groupName: home.active_lobby.group_name,
          hostUsername: home.active_lobby.host_username,
          playerCount: home.active_lobby.player_count,
          currentMovieTitle: home.active_lobby.current_movie_title,
        }
      : null,
    featuredGroup: featured
      ? {
          ...groupSummaryToView(featured),
          upNextCount: featured.up_next_count,
          upNext: featured.up_next.map(movieSummaryToView),
          lastWatched: featured.last_watched ? homeLogToView(featured.last_watched) : null,
        }
      : null,
    log: home.log.map(homeLogToView),
  };
}

export function movieRefToView(movie: ApiMovieRef): MovieSummaryView {
  return movieFieldsToView(movie);
}

export function lobbySummaryToView(summary: ApiLobbySummary): LobbySummaryView {
  return {
    uuid: summary.uuid,
    type: summary.type,
    status: summary.status as LobbyStatus,
    groupName: summary.group_name,
    hostUsername: summary.host_username,
    playerCount: summary.player_count,
    currentMovieTitle: summary.current_movie_title,
  };
}

export function lobbyPreviewToView(preview: ApiLobbyPreview): LobbyPreviewView {
  return {
    uuid: preview.uuid,
    type: preview.type,
    status: preview.status as LobbyStatus,
    groupId: preview.group_uuid ?? null,
    groupName: preview.group_name,
    hostUsername: preview.host_username,
    playerCount: preview.player_count,
    canJoin: preview.can_join,
    isParticipant: preview.is_participant,
    isGroupMember: preview.is_group_member,
  };
}

export function lobbyToView(state: ApiLobbyState): LobbyView {
  const status = state.status as LobbyStatus;
  const players: LobbyPlayerView[] = state.players.map((player) => ({
    id: player.id,
    name: player.name,
    short: player.initials,
    color: player.color,
    isHost: player.is_host,
    isGuest: player.is_guest,
    isReady: player.is_ready,
  }));
  const playerById = new Map(players.map((player) => [player.id, player]));
  const currentMovie = state.current_movie ? movieRefToView(state.current_movie) : null;
  const finalists: LobbyFinalistView[] = state.finalists.map((finalist) => ({
    movie: movieRefToView(finalist.movie),
    pickCount: finalist.pick_count,
    viewerPicked: finalist.viewer_picked,
    watch: watchToView(finalist.watch),
  }));
  const ballot: LobbyBallotEntryView[] = state.ballot.map((entry) => {
    const player = playerById.get(entry.participant_id);
    return {
      person: player ?? {
        id: entry.participant_id,
        name: entry.name,
        short: entry.name.slice(0, 2).toUpperCase(),
        color: "#8d8880",
      },
      choice: VOTE_FROM_API[entry.choice] ?? "out",
    };
  });

  const shortlisted = Boolean(
    state.revealed &&
      currentMovie &&
      finalists.some((finalist) => finalist.movie.id === currentMovie.id),
  );
  const revealedCounts = finalists
    .map((finalist) => finalist.pickCount)
    .filter((count): count is number => count !== null)
    .sort((a, b) => b - a);
  const tie =
    state.picks_revealed &&
    revealedCounts.length > 1 &&
    revealedCounts[0] > 0 &&
    revealedCounts[0] === revealedCounts[1];

  return {
    uuid: state.uuid,
    type: state.type === "group" ? "group" : "open",
    status,
    stage: statusToStage(status),
    version: state.version,
    hostId: state.host_id,
    groupId: state.group_uuid ?? null,
    groupName: state.group_name,
    viewerId: state.viewer_id,
    viewerIsHost: state.viewer_is_host,
    viewerReady: state.viewer_ready,
    players,
    playerCount: state.player_count,
    readyCount: state.ready_count,
    poolSize: state.pool_size,
    poolIndex: state.pool_index,
    roundNumber: state.round_number,
    remainingCount: state.remaining_count,
    currentMovie,
    submittedCount: state.submitted_count,
    viewerVote: state.viewer_vote ? (VOTE_FROM_API[state.viewer_vote] ?? null) : null,
    revealed: state.revealed,
    voteTally: state.vote_tally
      ? {
          interested: state.vote_tally.interested,
          watched: state.vote_tally.watched,
          notInterested: state.vote_tally.not_interested,
          total: state.vote_tally.total,
        }
      : null,
    ballot,
    finalists,
    picksRevealed: state.picks_revealed,
    viewerPick: state.viewer_pick,
    winner: state.winner ? movieRefToView(state.winner) : null,
    winnerWatch: watchToView(state.winner_watch),
    shortlisted,
    tie,
    capabilities: {
      canStart: state.capabilities.can_start,
      canUnready: state.capabilities.can_unready,
      canAdvance: state.capabilities.can_advance,
      canNextRound: state.capabilities.can_next_round,
      canFinalize: state.capabilities.can_finalize,
      canEnd: state.capabilities.can_end,
      canLeave: state.capabilities.can_leave,
      canRestart: state.capabilities.can_restart,
    },
  };
}

import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  Loader2,
  Plus,
  Search,
  X,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { MoviePoster } from "../components/MoviePoster";
import { SearchMovieDialog } from "../components/SearchMovieDialog";
import { type MovieSearchView } from "../lib/adapters";
import { useAddFilm, useGroupList, useGroupWatchlist } from "../lib/api-groups";
import { useMovieSearch } from "../lib/api-movies";
import { ApiError } from "../lib/api";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { cx } from "../lib/cx";
import { usePageTitle } from "../lib/usePageTitle";
import { useToast } from "../state/Toast";

type MediaFilter = "all" | "movie" | "series";

export function SearchPage() {
  usePageTitle("Search");
  const groupsQuery = useGroupList();
  const { showToast } = useToast();
  const [params] = useSearchParams();
  const requestedGroup = params.get("group");
  const [query, setQuery] = useState("");
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>("all");
  const [targetGroupId, setTargetGroupId] = useState("");
  const [addedKeys, setAddedKeys] = useState<Set<string>>(new Set());
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [detailMovie, setDetailMovie] = useState<MovieSearchView | null>(null);

  const groups = groupsQuery.data ?? [];
  const debouncedQuery = useDebouncedValue(query.trim(), 350);
  const search = useMovieSearch(debouncedQuery);
  const addFilm = useAddFilm();

  useEffect(() => {
    if (requestedGroup && groups.some((group) => group.id === requestedGroup)) {
      setTargetGroupId(requestedGroup);
    }
  }, [groups, requestedGroup]);

  useEffect(() => {
    if (!groups.some((group) => group.id === targetGroupId)) {
      setTargetGroupId(groups[0]?.id ?? "");
    }
  }, [groups, targetGroupId]);

  const targetGroup = groups.find((group) => group.id === targetGroupId);
  const watchlist = useGroupWatchlist(targetGroup?.id);

  const results = search.data ?? [];
  const filtered = useMemo(
    () => (mediaFilter === "all" ? results : results.filter((movie) => movie.mediaType === mediaFilter)),
    [mediaFilter, results],
  );
  const movieCount = results.filter((movie) => movie.mediaType === "movie").length;
  const seriesCount = results.filter((movie) => movie.mediaType === "series").length;

  const isAdded = (movie: MovieSearchView) => {
    if (addedKeys.has(`${targetGroupId}:${movie.key}`)) return true;
    return watchlist.data?.some((film) => film.movie.tmdbId === movie.tmdbId) ?? false;
  };

  const handleAdd = async (movie: MovieSearchView): Promise<boolean> => {
    if (!targetGroup) return false;
    setAddError(null);
    setPendingKey(movie.key);
    try {
      await addFilm.mutateAsync({
        groupId: targetGroup.id,
        tmdbId: movie.tmdbId,
        mediaType: movie.mediaType,
      });
      setAddedKeys((current) => {
        const next = new Set(current);
        next.add(`${targetGroup.id}:${movie.key}`);
        return next;
      });
      showToast(`Added ${movie.title} to ${targetGroup.name}.`);
      return true;
    } catch (error) {
      setAddError(
        error instanceof ApiError ? error.message : "Couldn't add the movie. Try again.",
      );
      return false;
    } finally {
      setPendingKey(null);
    }
  };

  const searchError = search.error instanceof ApiError ? search.error : null;

  return (
    <div className="page-inner search-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Find the next one</p>
          <h1 className="display page-title">Search</h1>
          <p className="lede page-lede">
            Look something up, then drop it straight into a watchlist.
          </p>
          {requestedGroup && targetGroup ? (
            <Link to={`/groups/${targetGroup.id}`} className="text-link search-back-link">
              <ArrowLeft size={13} /> Back to {targetGroup.name}
            </Link>
          ) : null}
        </div>
      </header>

      <div className="search-toolbar">
        <div className="search-field">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            aria-label="Search movies and series by title"
            placeholder="Title, e.g. Inception"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query ? (
            <button type="button" className="search-clear" onClick={() => setQuery("")} aria-label="Clear search">
              <X size={16} />
            </button>
          ) : null}
        </div>

        <label className="group-select">
          <span>Adding to</span>
          <span className="select-wrap">
            <select
              value={targetGroupId}
              onChange={(event) => setTargetGroupId(event.target.value)}
              aria-label="Choose a group to add movies to"
              disabled={!groups.length}
            >
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
            <ChevronDown size={15} aria-hidden="true" />
          </span>
        </label>
      </div>

      {results.length ? (
        <div className="filter-row" role="group" aria-label="Filter by type">
          {(
            [
              { value: "all", label: "All", count: results.length },
              { value: "movie", label: "Movies", count: movieCount },
              { value: "series", label: "Series", count: seriesCount },
            ] as const
          ).map((item) => (
            <button
              key={item.value}
              type="button"
              className={cx("filter-chip", mediaFilter === item.value && "is-active")}
              aria-pressed={mediaFilter === item.value}
              onClick={() => setMediaFilter(item.value)}
            >
              {item.label}
              <span className="chip-count">{item.count}</span>
            </button>
          ))}
        </div>
      ) : null}

      {addError ? (
        <p className="field-error search-add-error" role="alert">
          {addError}
        </p>
      ) : null}

      {!debouncedQuery ? (
        <EmptyState
          icon={<Search size={24} />}
          title="Start with a title."
          body="Search the catalog for a movie or series, then add it to the watchlist you're planning for."
        />
      ) : search.isPending ? (
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Searching the catalog…</span>
        </p>
      ) : search.isError ? (
        <EmptyState
          icon={<Search size={24} />}
          title={searchError?.code === "tmdb_unavailable" ? "Movie search is offline." : "Search didn't answer."}
          body={
            searchError?.code === "tmdb_unavailable"
              ? "The catalog service isn't configured or reachable right now. Add a TMDB API key to the API, then try again."
              : (searchError?.message ?? "Try again in a moment.")
          }
          action={<button type="button" className="btn btn-secondary btn-md" onClick={() => void search.refetch()}>Try again</button>}
        />
      ) : filtered.length ? (
        <>
          <div className="results-head">
            <p className="result-count" aria-live="polite">
              {filtered.length} {filtered.length === 1 ? "result" : "results"}
            </p>
            {mediaFilter !== "all" ? (
              <button
                type="button"
                className="text-button subtle"
                onClick={() => setMediaFilter("all")}
              >
                Clear filter
              </button>
            ) : null}
          </div>

          <div className="search-grid">
            {filtered.map((movie) => {
              const added = isAdded(movie);
              const pending = pendingKey === movie.key;

              return (
                <article className="search-card" key={movie.key}>
                  <button
                    type="button"
                    className="search-card-open"
                    onClick={() => setDetailMovie(movie)}
                    aria-label={`Details for ${movie.title}`}
                  />
                  <div className="search-poster">
                    <MoviePoster src={movie.poster} title={movie.title} />
                  </div>
                  <div className="search-card-body">
                    <h2 className="display">{movie.title}</h2>
                    <p className="search-meta">
                      {[movie.year, movie.mediaType === "series" ? "Series" : "Movie"]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    {movie.overview ? (
                      <p className="search-overview">{movie.overview}</p>
                    ) : null}
                    {movie.tmdbScore !== null ? (
                      <p className="search-rating">
                        TMDB <strong>{movie.tmdbScore.toFixed(1)}</strong>
                      </p>
                    ) : null}
                    <button
                      type="button"
                      className={cx("add-button", added && "is-added")}
                      onClick={() => handleAdd(movie)}
                      disabled={added || pending || !targetGroup}
                      aria-label={
                        added
                          ? `${movie.title} added to ${targetGroup?.name ?? "your group"}`
                          : `Add ${movie.title} to ${targetGroup?.name ?? "your group"}`
                      }
                    >
                      {pending ? (
                        <>
                          <Loader2 className="spin" size={15} /> Adding…
                        </>
                      ) : added ? (
                        <>
                          <Check size={15} /> Added
                        </>
                      ) : (
                        <>
                          <Plus size={15} /> Add
                        </>
                      )}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </>
      ) : (
        <EmptyState
          icon={<Search size={24} />}
          title="Nothing in this cut."
          body="No result matches this type. Clear the filter and the rest of the search is still there."
          action={
            <button type="button" className="btn btn-secondary btn-md" onClick={() => setMediaFilter("all")}>
              Clear filter
            </button>
          }
        />
      )}

      {!groupsQuery.isPending && !groups.length ? (
        <p className="search-note">Create a group before adding movies to a watchlist.</p>
      ) : null}

      <SearchMovieDialog
        movie={detailMovie}
        group={targetGroup ?? null}
        added={detailMovie ? isAdded(detailMovie) : false}
        pending={detailMovie ? pendingKey === detailMovie.key : false}
        open={Boolean(detailMovie)}
        onOpenChange={(open) => {
          if (!open) setDetailMovie(null);
        }}
        onAdd={() => {
          if (!detailMovie) return;
          void handleAdd(detailMovie).then((addedMovie) => {
            if (addedMovie) setDetailMovie(null);
          });
        }}
      />
    </div>
  );
}

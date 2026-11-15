import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, ChevronDown, Plus, Search, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { allMovies, type Movie } from "../data";
import { usePageTitle } from "../lib/usePageTitle";
import { cx } from "../lib/cx";
import { useGroups } from "../state/Groups";
import { useToast } from "../state/Toast";

const genres = ["All", "Drama", "Comedy", "Animation", "Action"];

export function SearchPage() {
  usePageTitle("Search");
  const { groups, addMovieToGroup } = useGroups();
  const { showToast } = useToast();
  const [params] = useSearchParams();
  const requestedGroup = params.get("group");
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState("All");
  const [targetGroupId, setTargetGroupId] = useState(
    requestedGroup && groups.some((group) => group.id === requestedGroup)
      ? requestedGroup
      : groups[0]?.id ?? "",
  );

  useEffect(() => {
    if (!groups.some((group) => group.id === targetGroupId)) {
      setTargetGroupId(groups[0]?.id ?? "");
    }
  }, [groups, targetGroupId]);

  useEffect(() => {
    if (requestedGroup && groups.some((group) => group.id === requestedGroup)) {
      setTargetGroupId(requestedGroup);
    }
  }, [groups, requestedGroup]);

  const targetGroup = groups.find((group) => group.id === targetGroupId);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return allMovies.filter((movie) => {
      const matchesGenre = genre === "All" || movie.genres.includes(genre);
      const haystack = `${movie.title} ${movie.director} ${movie.genres.join(" ")}`.toLowerCase();
      return matchesGenre && (!needle || haystack.includes(needle));
    });
  }, [query, genre]);

  const hasFilters = Boolean(query.trim()) || genre !== "All";

  const handleAdd = (movie: Movie) => {
    if (!targetGroup) return;
    addMovieToGroup(targetGroup.id, movie);
    showToast(`Added ${movie.title} to ${targetGroup.name}.`);
  };

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
            aria-label="Search films by title, director or genre"
            placeholder="Title, director or genre"
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
              aria-label="Choose a group to add films to"
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

      <div className="filter-row" role="group" aria-label="Filter by genre">
        {genres.map((item) => (
          <button
            key={item}
            type="button"
            className={cx("filter-chip", genre === item && "is-active")}
            aria-pressed={genre === item}
            onClick={() => setGenre(item)}
          >
            {item}
            {item === "All" ? <span className="chip-count">{allMovies.length}</span> : null}
          </button>
        ))}
      </div>

      <div className="results-head">
        <p className="result-count" aria-live="polite">
          {results.length} {results.length === 1 ? "film" : "films"}
        </p>
        {hasFilters ? (
          <button
            type="button"
            className="text-button subtle"
            onClick={() => {
              setQuery("");
              setGenre("All");
            }}
          >
            Clear filters
          </button>
        ) : null}
      </div>

      {results.length ? (
        <div className="search-grid">
          {results.map((movie) => {
            const isAdded = targetGroup?.watchlist.some((entry) => entry.id === movie.id) ?? false;
            return (
              <article className="search-card" key={movie.id}>
                <div className="search-poster">
                  <img src={movie.poster} alt={`${movie.title} poster`} loading="lazy" />
                </div>
                <div className="search-card-body">
                  <h2 className="display">{movie.title}</h2>
                  <p className="search-meta">
                    {movie.year} · {movie.runtime} min · {movie.genres.slice(0, 2).join(", ")}
                  </p>
                  <p className="search-director">Dir. {movie.director}</p>
                  <button
                    type="button"
                    className={cx("add-button", isAdded && "is-added")}
                    onClick={() => handleAdd(movie)}
                    disabled={isAdded || !targetGroup}
                    aria-label={
                      isAdded
                        ? `${movie.title} added to ${targetGroup?.name ?? "your group"}`
                        : `Add ${movie.title} to ${targetGroup?.name ?? "your group"}`
                    }
                  >
                    {isAdded ? (
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
      ) : (
        <EmptyState
          icon={<Search size={24} />}
          title="Nothing in the stacks."
          body="Try a different title or director, or clear the genre filter. The watchlist will still be there."
          action={
            <button
              type="button"
              className="btn btn-secondary btn-md"
              onClick={() => {
                setQuery("");
                setGenre("All");
              }}
            >
              Clear filters
            </button>
          }
        />
      )}

      {!targetGroup ? (
        <p className="search-note">Create a group before adding films to a watchlist.</p>
      ) : null}
    </div>
  );
}

import { useMemo, useState } from "react";
import {
  ChevronRight,
  Film,
  Link2,
  Loader2,
  Plus,
  Search,
  Star,
  X,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Avatar, AvatarStack } from "../../components/Avatar";
import { Button, buttonClass } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { MoviePoster } from "../../components/MoviePoster";
import { formatDate, type GroupFilmView } from "../../lib/adapters";
import {
  getGroupInviteLink,
  useGroup,
  useGroupStats,
  useGroupWatchlist,
  useSetFilmScore,
  useSetFilmStatus,
} from "../../lib/api-groups";
import { ApiError } from "../../lib/api";
import { copyText } from "../../lib/copy";
import { cx } from "../../lib/cx";
import { usePageTitle } from "../../lib/usePageTitle";
import { useToast } from "../../state/Toast";
import { GroupFilmSheet } from "./GroupFilmSheet";
import { GroupScoreDialog } from "./GroupScoreDialog";
import "./group.css";

type Filter = "all" | "up_next" | "watched";
type Sort = "recent" | "score" | "title";

function filmMeta(film: GroupFilmView): string {
  const movie = film.movie;
  return [
    movie.year,
    movie.runtime ? `${movie.runtime} min` : null,
    movie.genres.slice(0, 2).join(", "),
  ]
    .filter(Boolean)
    .join(" · ");
}

export function GroupPage() {
  const { id } = useParams<{ id: string }>();
  const groupQuery = useGroup(id);
  const watchlistQuery = useGroupWatchlist(id);
  const statsQuery = useGroupStats(id);
  const setScore = useSetFilmScore();
  const setStatus = useSetFilmStatus();
  const { showToast } = useToast();

  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("recent");
  const [sheetId, setSheetId] = useState<number | null>(null);
  const [scoreId, setScoreId] = useState<number | null>(null);
  const [inviting, setInviting] = useState(false);

  const group = groupQuery.data ?? null;
  const films = watchlistQuery.data ?? [];
  usePageTitle(group?.name ?? "Group");

  const sheetFilm = films.find((film) => film.id === sheetId) ?? null;
  const scoreFilm = films.find((film) => film.id === scoreId) ?? null;

  const stats = useMemo(() => {
    const upNext = films.filter((film) => film.status === "up_next").length;
    const watched = films.filter((film) => film.status === "watched").length;
    const scoreCount = films.reduce((sum, film) => sum + film.scoreCount, 0);
    return {
      total: statsQuery.data?.filmCount ?? films.length,
      upNext: statsQuery.data?.upNextCount ?? upNext,
      watched: statsQuery.data?.watchedCount ?? watched,
      average: statsQuery.data?.averageScore ?? null,
      scoreCount,
    };
  }, [films, statsQuery.data]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = films.filter((film) => {
      if (filter !== "all" && film.status !== filter) return false;
      if (!needle) return true;
      const haystack = `${film.movie.title} ${film.movie.director ?? ""} ${film.movie.genres.join(" ")}`;
      return haystack.toLowerCase().includes(needle);
    });

    if (sort === "title") {
      return [...filtered].sort((a, b) => a.movie.title.localeCompare(b.movie.title));
    }
    if (sort === "score") {
      return [...filtered].sort((a, b) => {
        if (a.clubScore === null && b.clubScore === null) {
          return a.movie.title.localeCompare(b.movie.title);
        }
        if (a.clubScore === null) return 1;
        if (b.clubScore === null) return -1;
        return b.clubScore - a.clubScore || a.movie.title.localeCompare(b.movie.title);
      });
    }
    return filtered;
  }, [films, filter, query, sort]);

  if (groupQuery.isPending || watchlistQuery.isPending) {
    return (
      <div className="page-inner group-page">
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Opening the watchlist…</span>
        </p>
      </div>
    );
  }

  if (groupQuery.isError || watchlistQuery.isError) {
    const error = groupQuery.error ?? watchlistQuery.error;
    const denied = error instanceof ApiError && [403, 404].includes(error.status);
    return (
      <div className="page-inner group-page">
        <EmptyState
          icon={<Film size={24} />}
          title={denied ? "This group isn't here." : "The group didn't load."}
          body={
            denied
              ? "The link may be old, or you're not a member. Your other crews are still where you left them."
              : error instanceof Error
                ? error.message
                : "Try again in a moment."
          }
          action={
            <div className="empty-actions">
              {!denied ? (
                <Button onClick={() => void Promise.all([groupQuery.refetch(), watchlistQuery.refetch()])}>
                  Try again
                </Button>
              ) : null}
              <Link to="/groups" className={buttonClass("primary", "md")}>
                Back to groups
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  if (!group) return null;

  const handleInvite = async () => {
    setInviting(true);
    try {
      const link = await getGroupInviteLink(group.id);
      const copied = await copyText(link);
      showToast(copied ? "Invite link copied." : "Couldn't copy the link — try again.");
    } catch (error) {
      showToast(
        error instanceof ApiError ? error.message : "Couldn't create an invite link.",
      );
    } finally {
      setInviting(false);
    }
  };

  const openScore = (film: GroupFilmView | null) => {
    if (!film) return;
    setSheetId(null);
    setScoreId(film.id);
  };

  const clearFilters = () => {
    setFilter("all");
    setQuery("");
  };

  return (
    <div className="page-inner group-page">
      <header className="group-head">
        <div>
          <p className="group-crumbs">
            <Link to="/groups">Groups</Link>
            <ChevronRight size={12} aria-hidden="true" />
            <span>{group.name}</span>
          </p>
          <p className="eyebrow">
            The watchlist <span className="dot-sep">·</span>{" "}
            {group.memberCount} {group.memberCount === 1 ? "member" : "members"}
          </p>
          <h1 className="display group-title">{group.name}</h1>
          <p className="group-desc">
            {group.description || "A group for the films you keep between you."}
          </p>
          <div className="group-members">
            <AvatarStack people={group.members} size={24} />
            <span>
              {group.memberCount} {group.memberCount === 1 ? "member" : "members"} ·{" "}
              <strong>{stats.total}</strong> {stats.total === 1 ? "film" : "films"} between you
            </span>
          </div>
        </div>

        <div className="group-actions">
          <Button variant="secondary" onClick={handleInvite} disabled={inviting}>
            {inviting ? <Loader2 className="spin" size={15} /> : <Link2 size={15} />} Invite
          </Button>
          <Link to={`/search?group=${group.id}`} className={buttonClass("secondary", "md")}>
            <Plus size={15} /> Add a film
          </Link>
        </div>
      </header>

      <div className="group-stats" aria-label="Watchlist summary">
        <div className="group-stat">
          <strong>{stats.total}</strong>
          <span>Films</span>
        </div>
        <div className="group-stat">
          <strong>{stats.upNext}</strong>
          <span>Up next</span>
        </div>
        <div className="group-stat">
          <strong>{stats.watched}</strong>
          <span>Watched</span>
        </div>
        <div className="group-stat">
          <strong>{stats.average !== null ? stats.average.toFixed(1) : "—"}</strong>
          <span>Club average</span>
          <em>{stats.scoreCount} scores</em>
        </div>
      </div>

      <div className="group-toolbar">
        <div className="group-tabs" role="group" aria-label="Filter the watchlist">
          <button
            type="button"
            className={cx("group-tab", filter === "all" && "is-active")}
            aria-pressed={filter === "all"}
            onClick={() => setFilter("all")}
          >
            All <span>{stats.total}</span>
          </button>
          <button
            type="button"
            className={cx("group-tab", filter === "up_next" && "is-active")}
            aria-pressed={filter === "up_next"}
            onClick={() => setFilter("up_next")}
          >
            Up next <span>{stats.upNext}</span>
          </button>
          <button
            type="button"
            className={cx("group-tab", filter === "watched" && "is-active")}
            aria-pressed={filter === "watched"}
            onClick={() => setFilter("watched")}
          >
            Watched <span>{stats.watched}</span>
          </button>
        </div>

        <div className="search-field group-search">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Find a film on the list"
            aria-label="Search the watchlist"
          />
          {query ? (
            <button type="button" className="search-clear" aria-label="Clear search" onClick={() => setQuery("")}>
              <X size={14} />
            </button>
          ) : null}
        </div>

        <label className="group-sort">
          <span>Sort</span>
          <select value={sort} onChange={(event) => setSort(event.target.value as Sort)} aria-label="Sort the watchlist">
            <option value="recent">Recently added</option>
            <option value="score">Highest score</option>
            <option value="title">Title</option>
          </select>
        </label>
      </div>

      {visible.length ? (
        <>
          <div className="watch-grid">
            {visible.map((film) => {
              const movie = film.movie;
              const watched = film.status === "watched";
              const addedBy = group.members.find((member) => member.name === film.addedBy);
              const average = film.clubScore;

              return (
                <article className="watch-card" key={film.id}>
                  <button
                    type="button"
                    className="watch-card-open"
                    onClick={() => setSheetId(film.id)}
                    aria-label={`About ${movie.title}, club average ${
                      average !== null ? average.toFixed(1) : "not scored yet"
                    }, ${film.scoreCount} ${film.scoreCount === 1 ? "score" : "scores"}`}
                  />
                  <div className="watch-card-poster">
                    <MoviePoster src={movie.poster} title={movie.title} />
                    <span className={cx("watch-card-status", `is-${film.status}`)}>
                      {watched ? "Watched" : "Up next"}
                    </span>
                  </div>

                  <div className="watch-card-body">
                    <h2>{movie.title}</h2>
                    <p className="watch-card-meta">{filmMeta(film)}</p>

                    <div className={cx("watch-score", !watched && "is-up-next")}>
                      <div className="watch-score-top">
                        <span className="watch-score-value">
                          {average !== null ? average.toFixed(1) : "—"}
                        </span>
                        <span className="watch-score-meta">
                          <Star size={11} fill="currentColor" aria-hidden="true" />{" "}
                          {film.scoreCount
                            ? `${film.scoreCount} ${film.scoreCount === 1 ? "score" : "scores"}`
                            : "No scores yet"}
                        </span>
                      </div>
                      <div className={cx("watch-score-track", !film.scoreCount && "is-empty")} aria-hidden="true">
                        {average !== null ? (
                          <span
                            className="watch-score-dot"
                            style={{ left: `${average * 10}%`, background: "var(--amber)" }}
                          />
                        ) : null}
                      </div>
                      <div className="watch-score-you">
                        {watched ? (
                          film.yourScore !== null ? (
                            <>
                              You <strong>{film.yourScore.toFixed(1)}</strong>
                            </>
                          ) : (
                            <span>You haven't scored it</span>
                          )
                        ) : (
                          <span>Not watched yet</span>
                        )}
                      </div>
                    </div>

                    <div className="watch-card-added">
                      {addedBy ? <Avatar person={addedBy} size={16} /> : null}
                      <span>
                        {film.addedBy ? `${film.addedBy} · ` : ""}
                        {formatDate(film.addedAt)}
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          <footer className="group-foot">
            <p>
              {stats.upNext} {stats.upNext === 1 ? "film is" : "films are"} waiting for the room.
            </p>
            <Link to={`/search?group=${group.id}`} className="text-link">
              Add another film <Plus size={13} />
            </Link>
          </footer>
        </>
      ) : (
        <EmptyState
          icon={filter === "all" && !query ? <Film size={24} /> : <Search size={24} />}
          title={filter === "all" && !query ? "The shelf is empty." : "Nothing in this cut."}
          body={
            filter === "all" && !query
              ? "A watchlist starts with one film somebody won't stop talking about. Add the first one."
              : "No film matches this filter. Clear it and the rest of the watchlist is still there."
          }
          action={
            filter === "all" && !query ? (
              <Link to={`/search?group=${group.id}`} className={buttonClass("primary", "md")}>
                <Plus size={16} /> Add the first film
              </Link>
            ) : (
              <Button variant="secondary" onClick={clearFilters}>
                Clear the filter
              </Button>
            )
          }
        />
      )}

      <GroupFilmSheet
        group={group}
        film={sheetFilm}
        open={Boolean(sheetFilm)}
        onOpenChange={(open) => {
          if (!open) setSheetId(null);
        }}
        onScore={() => openScore(sheetFilm)}
      />

      <GroupScoreDialog
        groupName={group.name}
        film={scoreFilm}
        open={Boolean(scoreFilm)}
        onOpenChange={(open) => {
          if (!open) setScoreId(null);
        }}
        onSave={async (score) => {
          if (!scoreFilm) return;
          if (scoreFilm.status === "up_next") {
            await setStatus.mutateAsync({
              groupId: group.id,
              filmId: scoreFilm.id,
              status: "watched",
            });
          }
          await setScore.mutateAsync({
            groupId: group.id,
            filmId: scoreFilm.id,
            score,
          });
          showToast(
            scoreFilm.status === "up_next"
              ? `${scoreFilm.movie.title} is watched and scored.`
              : "Your score is saved.",
          );
        }}
      />
    </div>
  );
}

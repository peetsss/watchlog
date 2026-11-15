import { useMemo, useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  ChevronRight,
  Film,
  Link2,
  Plus,
  Search,
  Star,
  X,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Avatar, AvatarStack } from "../../components/Avatar";
import { Button, buttonClass } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { StartNightDialog } from "../../components/StartNightDialog";
import { copyText, inviteUrl } from "../../lib/copy";
import { cx } from "../../lib/cx";
import { usePageTitle } from "../../lib/usePageTitle";
import {
  INVITE_CODE,
  YOU,
  movieById,
  type GroupFilm,
} from "../../data";
import { useGroups } from "../../state/Groups";
import { useToast } from "../../state/Toast";
import { GroupFilmSheet } from "./GroupFilmSheet";
import { GroupScoreDialog } from "./GroupScoreDialog";
import { filmAverage, groupScoreSummary, movieForFilm, scoredMembers } from "./score";
import "./group.css";

type Filter = "all" | "up-next" | "watched";
type Sort = "recent" | "score" | "title";

function filmTitle(film: GroupFilm) {
  return movieForFilm(film)?.title ?? "";
}

function filmMatches(film: GroupFilm, needle: string) {
  if (!needle) return true;
  const movie = movieForFilm(film);
  if (!movie) return false;
  return `${movie.title} ${movie.director} ${movie.genres.join(" ")}`
    .toLowerCase()
    .includes(needle);
}

export function GroupPage() {
  const { id } = useParams<{ id: string }>();
  const { groups, setGroupFilmScore } = useGroups();
  const { showToast } = useToast();
  const group = groups.find((entry) => entry.id === id) ?? null;
  usePageTitle(group?.name ?? "Group");

  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("recent");
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [scoreId, setScoreId] = useState<string | null>(null);
  const [startOpen, setStartOpen] = useState(false);

  const sheetFilm = group?.films.find((film) => film.movieId === sheetId) ?? null;
  const scoreFilm = group?.films.find((film) => film.movieId === scoreId) ?? null;

  const stats = useMemo(() => {
    if (!group) return null;
    const upNext = group.films.filter((film) => film.status === "up-next").length;
    const watched = group.films.filter((film) => film.status === "watched").length;
    const scores = groupScoreSummary(group);
    return { total: group.films.length, upNext, watched, average: scores.average, count: scores.count };
  }, [group]);

  const visible = useMemo(() => {
    if (!group) return [];
    const needle = query.trim().toLowerCase();
    const films = group.films.filter((film) => {
      if (filter !== "all" && film.status !== filter) return false;
      return filmMatches(film, needle);
    });

    if (sort === "title") {
      return [...films].sort((a, b) => filmTitle(a).localeCompare(filmTitle(b)));
    }
    if (sort === "score") {
      return [...films].sort((a, b) => {
        const averageA = filmAverage(group, a);
        const averageB = filmAverage(group, b);
        if (averageA === null && averageB === null) {
          return filmTitle(a).localeCompare(filmTitle(b));
        }
        if (averageA === null) return 1;
        if (averageB === null) return -1;
        return averageB - averageA || filmTitle(a).localeCompare(filmTitle(b));
      });
    }
    return films;
  }, [filter, group, query, sort]);

  if (!group || !stats) {
    return (
      <div className="page-inner group-page">
        <EmptyState
          icon={<Film size={24} />}
          title="This group isn't here."
          body="The link may be old, or the group moved. Your other crews are still where you left them."
          action={
            <Link to="/groups" className={buttonClass("primary", "md")}>
              Back to groups
            </Link>
          }
        />
      </div>
    );
  }

  const handleInvite = async () => {
    const copied = await copyText(inviteUrl(INVITE_CODE));
    showToast(copied ? "Invite link copied." : "Couldn't copy the link — select it instead.");
  };

  const openScore = (film: GroupFilm | null) => {
    if (!film) return;
    setSheetId(null);
    setScoreId(film.movieId);
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
            {group.nextNight ? `Next night ${group.nextNight}` : "The next film is yours"}
          </p>
          <h1 className="display group-title">{group.name}</h1>
          <p className="group-desc">{group.description}</p>
          <div className="group-members">
            <AvatarStack people={group.members} size={24} />
            <span>
              {group.members.length} {group.members.length === 1 ? "member" : "members"} ·{" "}
              <strong>{stats.total}</strong> {stats.total === 1 ? "film" : "films"} between you
            </span>
          </div>
        </div>

        <div className="group-actions">
          <Button variant="secondary" onClick={handleInvite}>
            <Link2 size={15} /> Invite
          </Button>
          <Link to={`/search?group=${group.id}`} className={buttonClass("secondary", "md")}>
            <Plus size={15} /> Add a film
          </Link>
          <Button onClick={() => setStartOpen(true)}>
            Start a night <ArrowRight size={16} />
          </Button>
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
          <strong>{stats.average ? stats.average.toFixed(1) : "—"}</strong>
          <span>Club average</span>
          <em>{stats.count} scores</em>
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
            className={cx("group-tab", filter === "up-next" && "is-active")}
            aria-pressed={filter === "up-next"}
            onClick={() => setFilter("up-next")}
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
              const movie = movieById(film.movieId);
              if (!movie) return null;
              const scored = scoredMembers(group, film);
              const average = filmAverage(group, film);
              const yourScore = film.scores[YOU];
              const addedBy = group.members.find((person) => person.id === film.addedBy);
              const watched = film.status === "watched";

              return (
                <article className="watch-card" key={film.movieId}>
                  <button
                    type="button"
                    className="watch-card-open"
                    onClick={() => setSheetId(film.movieId)}
                    aria-label={`About ${movie.title}, club average ${
                      average !== null ? average.toFixed(1) : "not scored yet"
                    }, ${scored.length} ${scored.length === 1 ? "score" : "scores"}`}
                  />
                  <div className="watch-card-poster">
                    <img src={movie.poster} alt={`${movie.title} poster`} loading="lazy" />
                    <span className={cx("watch-card-status", `is-${film.status}`)}>
                      {watched ? "Watched" : "Up next"}
                    </span>
                  </div>

                  <div className="watch-card-body">
                    <h2>{movie.title}</h2>
                    <p className="watch-card-meta">
                      {movie.year} · {movie.runtime} min · {movie.genres.slice(0, 2).join(", ")}
                    </p>

                    <div className={cx("watch-score", !watched && "is-up-next")}>
                      <div className="watch-score-top">
                        <span className="watch-score-value">
                          {average !== null ? average.toFixed(1) : "—"}
                        </span>
                        <span className="watch-score-meta">
                          <Star size={11} fill="currentColor" aria-hidden="true" />{" "}
                          {scored.length
                            ? `${scored.length} ${scored.length === 1 ? "score" : "scores"}`
                            : "No scores yet"}
                        </span>
                      </div>
                      <div className={cx("watch-score-track", !scored.length && "is-empty")} aria-hidden="true">
                        {scored.map(({ person, score }) => (
                          <span
                            key={person.id}
                            className="watch-score-dot"
                            style={{ left: `${score * 10}%`, background: person.color }}
                          />
                        ))}
                      </div>
                      <div className="watch-score-you">
                        {watched ? (
                          yourScore !== undefined ? (
                            <>
                              You <strong>{yourScore.toFixed(1)}</strong>
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
                        {addedBy ? `${addedBy.name.split(" ")[0]} · ` : ""}
                        {film.addedAt}
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          <footer className="group-foot">
            <p>
              <CalendarDays size={14} aria-hidden="true" />
              {group.nextNight ? `The next night is ${group.nextNight}.` : "The next night is yours to plan."}{" "}
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
        group={group}
        film={scoreFilm}
        open={Boolean(scoreFilm)}
        onOpenChange={(open) => {
          if (!open) setScoreId(null);
        }}
        onSave={(score) => {
          if (!scoreFilm) return;
          setGroupFilmScore(group.id, scoreFilm.movieId, score);
          setScoreId(null);
        }}
      />

      <StartNightDialog
        open={startOpen}
        onOpenChange={setStartOpen}
        initialGroupId={group.id}
      />
    </div>
  );
}

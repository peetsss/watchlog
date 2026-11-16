import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Film,
  Loader2,
  Search,
  Star,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar, AvatarStack } from "../components/Avatar";
import { EmptyState } from "../components/EmptyState";
import { MoviePoster } from "../components/MoviePoster";
import { NightDialog } from "../components/NightDialog";
import { PosterStack } from "../components/PosterStack";
import {
  formatDate,
  type HomeActiveLobbyView,
  type HomeLogEntryView,
  type MovieSummaryView,
} from "../lib/adapters";
import { useGroupFilmScores } from "../lib/api-groups";
import { useHome } from "../lib/api-home";
import { cx } from "../lib/cx";
import { usePageTitle } from "../lib/usePageTitle";
import "./hub.css";

function excerpt(text: string, limit = 150): string {
  const clean = text.trim();
  if (clean.length <= limit) return clean;
  return `${clean.slice(0, limit).replace(/\s+\S*$/, "")}…`;
}

function filmMeta(movie: MovieSummaryView): string {
  return [
    movie.year,
    movie.runtime ? `${movie.runtime} min` : null,
    movie.genres.slice(0, 2).join(", "),
    movie.director ? `Dir. ${movie.director}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function scoreLabel(score: number | null): string {
  return score !== null ? score.toFixed(1) : "—";
}

function activeHeadline(active: HomeActiveLobbyView): string {
  if (active.status === "ready") return "The room is filling up.";
  if (active.status === "playing") {
    return active.currentMovieTitle
      ? `${active.currentMovieTitle} is on the table.`
      : "One film is on the table.";
  }
  return "The shortlist is ready.";
}

function activeCopy(active: HomeActiveLobbyView): string {
  if (active.status === "ready") {
    return `${active.playerCount} in the room. Ready up and the host can start.`;
  }
  if (active.status === "playing") {
    return `${active.playerCount} in the room. Everyone votes before the reveal.`;
  }
  return `${active.playerCount} in the room. One pick each; picks stay hidden.`;
}

function activeStage(active: HomeActiveLobbyView): string {
  if (active.status === "ready") return "Waiting room";
  if (active.status === "playing") return "Voting";
  return "Final round";
}

export function HubPage() {
  usePageTitle("Home");
  const homeQuery = useHome();
  const [nightDetail, setNightDetail] = useState<HomeLogEntryView | null>(null);

  const home = homeQuery.data;
  const featured = home?.featuredGroup ?? null;
  const active = home?.activeLobby ?? null;
  const log = home?.log ?? [];
  const featureNight = log[0] ?? null;
  const archiveNights = log.slice(1);
  const featuredScores = useGroupFilmScores(
    featureNight?.groupId ?? "",
    featureNight?.filmId ?? null,
    Boolean(featureNight),
  );
  const scored = [...(featuredScores.data ?? [])].sort(
    (a, b) => b.score - a.score || a.person.name.localeCompare(b.person.name),
  );

  const today = new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  if (homeQuery.isPending) {
    return (
      <div className="page-inner hub-page">
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Opening your home…</span>
        </p>
      </div>
    );
  }

  if (homeQuery.isError || !home) {
    return (
      <div className="page-inner hub-page">
        <EmptyState
          icon={<Film size={24} />}
          title="Home didn't load."
          body={homeQuery.error?.message ?? "Try again in a moment."}
          action={<button type="button" className="btn btn-secondary btn-md" onClick={() => void homeQuery.refetch()}>Try again</button>}
        />
      </div>
    );
  }

  return (
    <div className="page-inner hub-page">
      <section className="hub-board" aria-labelledby="hub-board-title">
        <div className="hub-board-main">
          <p className="eyebrow">{today}</p>
          <h1 className="display hub-board-title" id="hub-board-title">
            What are we watching <em>tonight</em>?
          </h1>
          <p className="lede hub-board-lede">
            One room, one shortlist, one pick. Start with the club you already have — no
            twenty-message group chat required.
          </p>
          <div className="hub-board-actions">
            <Link to="/groups" className="btn btn-primary btn-lg">
              <Users size={17} /> Open your groups
            </Link>
            <Link to="/search" className="btn btn-secondary btn-lg">
              <Search size={17} /> Find a film
            </Link>
          </div>
        </div>

        <aside className="hub-board-live" aria-label="Tonight">
          {active ? (
            <>
              <div className="hub-board-live-top">
                <span className="live-pill">
                  <span className="live-dot" aria-hidden="true" /> Live
                </span>
                <span>{active.type === "open" ? "Open lobby" : "Group lobby"}</span>
              </div>
              <span className="section-kicker">
                {active.groupName ?? `Hosted by ${active.hostUsername ?? "a member"}`}
              </span>
              <h2 className="display">{activeHeadline(active)}</h2>
              <p className="hub-board-live-copy">{activeCopy(active)}</p>
              <div className="hub-board-live-players">
                <Users size={14} aria-hidden="true" />
                <span>
                  {active.playerCount} {active.playerCount === 1 ? "player" : "players"} ·{" "}
                  {activeStage(active)}
                </span>
              </div>
              <Link
                to={`/lobby/${active.uuid}`}
                className="btn btn-primary btn-md hub-board-rejoin"
              >
                Rejoin the room <ArrowRight size={16} />
              </Link>
            </>
          ) : featured ? (
            <>
              <div className="hub-board-live-top">
                <span className="section-kicker">On the watchlist</span>
                <span className="hub-board-club-name">{featured.name}</span>
              </div>
              <h2 className="display">
                {featured.upNextCount ? "A few good ones, waiting." : "The shelf is waiting."}
              </h2>
              <div className="hub-board-club">
                <AvatarStack people={featured.members} size={23} />
                <span>
                  {featured.memberCount} {featured.memberCount === 1 ? "member" : "members"}
                </span>
              </div>
              <div className="hub-board-watchlist">
                <PosterStack
                  movies={featured.upNext.map((movie) => ({
                    id: movie.id,
                    title: movie.title,
                    poster: movie.poster,
                  }))}
                  className="tonight-stack"
                />
                <div className="hub-board-up-next">
                  <span className="section-kicker">Up next</span>
                  {featured.upNext[0] ? (
                    <>
                      <strong className="display">{featured.upNext[0].title}</strong>
                      {featured.upNextCount > 1 ? (
                        <span>+{featured.upNextCount - 1} more waiting</span>
                      ) : null}
                    </>
                  ) : (
                    <span>Nothing waiting yet.</span>
                  )}
                </div>
              </div>
              {featured.lastWatched ? (
                <button
                  type="button"
                  className="hub-board-last is-link"
                  onClick={() => setNightDetail(featured.lastWatched)}
                  aria-label={`Revisit ${featured.lastWatched.movie.title}, club score ${scoreLabel(featured.lastWatched.clubScore)}`}
                >
                  <span className="section-kicker">Last watched</span>
                  <span className="hub-board-last-title">
                    {featured.lastWatched.movie.title}
                  </span>
                  <span className="hub-board-last-score">
                    <Star size={11} fill="currentColor" aria-hidden="true" />
                    {scoreLabel(featured.lastWatched.clubScore)}
                  </span>
                  <ArrowUpRight size={12} aria-hidden="true" />
                </button>
              ) : null}
              <div className="hub-board-idle-actions">
                <Link to={`/groups/${featured.id}`} className="btn btn-secondary btn-sm">
                  Open the watchlist <ArrowUpRight size={14} />
                </Link>
                <Link
                  to={`/search?group=${featured.id}`}
                  className="text-link hub-board-idle-link"
                >
                  Add a film <ArrowUpRight size={14} />
                </Link>
              </div>
            </>
          ) : (
            <>
              <div className="hub-board-live-top">
                <span className="section-kicker">Your first crew</span>
              </div>
              <h2 className="display">Start with the people.</h2>
              <p className="hub-board-live-copy">
                Make a group, add the first film, then send the invite. The room can wait.
              </p>
              <Link to="/groups" className="btn btn-primary btn-md hub-board-rejoin">
                Create your first group <ArrowRight size={16} />
              </Link>
            </>
          )}
        </aside>

        <div className="hub-board-foot">
          <span>
            <Film size={14} aria-hidden="true" />{" "}
            {home.crews.count === 0
              ? "No films on the shelves yet"
              : `${home.crews.watchedCount} watched · ${home.crews.filmCount} on the shelves`}
          </span>
          <Link to="/groups" className="hub-board-crews">
            {home.crews.count === 0
              ? "Make your first crew"
              : `${home.crews.count} ${home.crews.count === 1 ? "crew" : "crews"} between you`}{" "}
            <ArrowUpRight size={13} />
          </Link>
        </div>
      </section>

      <section className="hub-log" aria-labelledby="hub-log-title">
        <header className="hub-log-head">
          <div>
            <span className="section-kicker">Recently watched</span>
            <h2 className="display" id="hub-log-title">
              The log.
            </h2>
            <p className="hub-log-lede">
              Everything your crews have watched, rated and argued about. The next night is only
              ever one entry away.
            </p>
          </div>
          <span className="hub-log-count">
            {home.crews.watchedCount}{" "}
            {home.crews.watchedCount === 1 ? "night" : "nights"} logged
          </span>
        </header>

        {featureNight ? (
          <div className={cx("hub-log-spread", !archiveNights.length && "is-single")}>
            <button
              type="button"
              className="hub-log-feature"
              onClick={() => setNightDetail(featureNight)}
              aria-label={`Revisit ${featureNight.movie.title}, club score ${scoreLabel(featureNight.clubScore)}`}
            >
              <span className="hub-log-feature-poster">
                <MoviePoster src={featureNight.movie.poster} title={featureNight.movie.title} />
              </span>
              <span className="hub-log-feature-copy">
                <span className="hub-log-feature-top">
                  <span className="hub-log-feature-kicker">Latest night</span>
                  <span className="hub-log-feature-meta">
                    {featureNight.groupName} · {formatDate(featureNight.watchedAt)}
                  </span>
                </span>
                <strong className="display hub-log-feature-title">
                  {featureNight.movie.title}
                </strong>
                <span className="hub-log-feature-film-meta">
                  {filmMeta(featureNight.movie)}
                </span>
                <span className="hub-log-feature-note">
                  {excerpt(featureNight.movie.description, 165)}
                </span>
                {scored.length ? (
                  <span className="hub-log-feature-people" aria-label="Member scores">
                    {scored.map(({ person, score }) => (
                      <span
                        className="hub-log-feature-person"
                        key={person.id}
                        role="img"
                        aria-label={`${person.name}: ${score.toFixed(1)}`}
                        title={`${person.name}: ${score.toFixed(1)}`}
                      >
                        <Avatar person={person} size={19} />
                        <strong>{score.toFixed(1)}</strong>
                      </span>
                    ))}
                  </span>
                ) : null}
                <span className="hub-log-feature-foot">
                  <span
                    className="hub-log-feature-score"
                    aria-label={
                      featureNight.scoreCount
                        ? `Club score ${scoreLabel(featureNight.clubScore)} from ${featureNight.scoreCount} scores`
                        : "Not scored yet"
                    }
                  >
                    <span className="hub-log-score-label">
                      {featureNight.scoreCount ? "Club score" : "Not scored"}
                    </span>
                    <span className="hub-log-score-value">
                      <Star size={14} fill="currentColor" aria-hidden="true" />
                      <strong>{scoreLabel(featureNight.clubScore)}</strong>
                      {featureNight.scoreCount ? (
                        <span className="hub-log-score-count">
                          {featureNight.scoreCount}{" "}
                          {featureNight.scoreCount === 1 ? "score" : "scores"}
                        </span>
                      ) : null}
                    </span>
                    {scored.length ? (
                      <span className="hub-log-score-track" aria-hidden="true">
                        {scored.map(({ person, score }) => (
                          <span
                            key={person.id}
                            className="hub-log-score-dot"
                            style={{ left: `${score * 10}%`, background: person.color }}
                          />
                        ))}
                      </span>
                    ) : null}
                  </span>
                  <span className="hub-log-feature-read">
                    <span className="hub-log-feature-read-text">Revisit the night</span>
                    <ArrowRight size={13} aria-hidden="true" />
                  </span>
                </span>
              </span>
            </button>

            {archiveNights.length ? (
              <div className="hub-log-archive">
                {archiveNights.map((night) => (
                  <button
                    type="button"
                    className="hub-log-archive-entry"
                    key={`${night.groupId}-${night.filmId}`}
                    onClick={() => setNightDetail(night)}
                    aria-label={`Revisit ${night.movie.title}, club score ${scoreLabel(night.clubScore)}`}
                  >
                    <span className="hub-log-archive-poster">
                      <MoviePoster src={night.movie.poster} title={night.movie.title} />
                    </span>
                    <span className="hub-log-archive-copy">
                      <span className="hub-log-archive-meta">
                        {night.groupName} · {formatDate(night.watchedAt)}
                      </span>
                      <strong className="display hub-log-archive-title">
                        {night.movie.title}
                      </strong>
                      <span className="hub-log-archive-note">
                        {excerpt(night.movie.description, 110)}
                      </span>
                      <span className="hub-log-archive-foot">
                        <span className="hub-log-archive-score">
                          <Star size={11} fill="currentColor" aria-hidden="true" />
                          <strong>{scoreLabel(night.clubScore)}</strong>
                          {night.scoreCount ? (
                            <span>
                              {night.scoreCount}{" "}
                              {night.scoreCount === 1 ? "score" : "scores"}
                            </span>
                          ) : null}
                        </span>
                        <ArrowUpRight size={14} aria-hidden="true" />
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <p className="hub-log-empty">
            No nights logged yet. The first one is still ahead.
          </p>
        )}
      </section>

      <footer className="page-foot">
        <span className="foot-brand">
          watchlog<span>.</span>
        </span>
        <span>For the people who stay for the credits.</span>
      </footer>

      <NightDialog
        entry={nightDetail}
        open={Boolean(nightDetail)}
        onOpenChange={(open) => {
          if (!open) setNightDetail(null);
        }}
      />
    </div>
  );
}

import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Clapperboard,
  Link2,
  Star,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar, AvatarStack } from "../components/Avatar";
import { Button, buttonClass } from "../components/Button";
import { JoinDialog } from "../components/JoinDialog";
import { NightDialog } from "../components/NightDialog";
import { PosterStack } from "../components/PosterStack";
import { StartNightDialog } from "../components/StartNightDialog";
import {
  PLAY_ORDER,
  movieById,
  recentNights,
  stageLabel,
  type Group,
  type Lobby,
  type RecentNight,
} from "../data";
import { cx } from "../lib/cx";
import { usePageTitle } from "../lib/usePageTitle";
import { useGroups } from "../state/Groups";
import { useLobby } from "../state/Lobby";
import { filmAverage, scoredMembers, type ScoredMember } from "./group/score";
import "./hub.css";

type NightScore = {
  average: number;
  count: number;
  scored: ScoredMember[];
};

function nightScore(groups: Group[], night: RecentNight): NightScore {
  const group = groups.find((entry) => entry.id === night.groupId);
  const film = group?.films.find((entry) => entry.movieId === night.movie.id);
  if (!group || !film) {
    return { average: night.rating, count: 0, scored: [] };
  }
  const scored = scoredMembers(group, film);
  return {
    average: filmAverage(group, film) ?? night.rating,
    count: scored.length,
    scored,
  };
}

function activeHeadline(lobby: Lobby) {
  if (lobby.stage === "waiting") return "The room is filling up.";
  if (lobby.stage === "playing") {
    const movie = movieById(PLAY_ORDER[lobby.roundIndex]);
    return movie ? `${movie.title} is on the table.` : "One film is on the table.";
  }
  return "The shortlist is ready.";
}

function activeCopy(lobby: Lobby) {
  if (lobby.stage === "waiting") {
    return `${lobby.ready.length} of ${lobby.players.length} ready. The host starts when everyone's in.`;
  }
  if (lobby.stage === "playing") {
    return `Film ${lobby.roundIndex + 1} of ${PLAY_ORDER.length} · ${lobby.players.length} in the room.`;
  }
  return `${lobby.shortlist.length} ${lobby.shortlist.length === 1 ? "film" : "films"}, one pick each. Picks stay hidden.`;
}

function activeProgress(lobby: Lobby) {
  if (lobby.stage === "waiting") {
    return lobby.players.length ? lobby.ready.length / lobby.players.length : 0;
  }
  if (lobby.stage === "playing") return (lobby.roundIndex + 1) / PLAY_ORDER.length;
  return 1;
}

export function HubPage() {
  usePageTitle("Home");
  const { groups } = useGroups();
  const { lobby } = useLobby();
  const [startOpen, setStartOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [nightDetail, setNightDetail] = useState<RecentNight | null>(null);

  const today = new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  const featuredGroup = groups[0];
  const active = lobby && lobby.stage !== "winner" ? lobby : null;
  const winnerLobby = lobby && lobby.stage === "winner" ? lobby : null;
  const winner = winnerLobby ? movieById(winnerLobby.winnerId) : null;
  const winnerPicks =
    winnerLobby && winner
      ? winnerLobby.players.filter((person) => winnerLobby.picks[person.id] === winner.id)
      : [];
  const totalFilms = groups.reduce((sum, group) => sum + group.films.length, 0);
  const nextNight = featuredGroup?.nextNight ?? "Friday";
  const featureNight = recentNights[0] ?? null;
  const archiveNights = recentNights.slice(1);
  const featuredFilms = featuredGroup?.films ?? [];
  const upNextFilms = featuredFilms.filter((film) => film.status === "up-next");
  const nextUpMovie = upNextFilms[0] ? movieById(upNextFilms[0].movieId) : null;
  const lastNightFilm = featuredGroup?.lastNight
    ? featuredFilms.find((film) => film.movieId === featuredGroup.lastNight?.movie.id)
    : undefined;
  const lastNightAverage =
    featuredGroup && lastNightFilm ? filmAverage(featuredGroup, lastNightFilm) : null;
  const lastNightEntry = featuredGroup?.lastNight
    ? recentNights.find(
        (night) =>
          night.groupId === featuredGroup.id &&
          night.movie.id === featuredGroup.lastNight?.movie.id,
      )
    : undefined;

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
            <Button size="lg" onClick={() => setStartOpen(true)}>
              <Clapperboard size={18} /> Start a movie night
            </Button>
            <Button size="lg" variant="secondary" onClick={() => setJoinOpen(true)}>
              <Link2 size={17} /> Join with a link
            </Button>
          </div>
        </div>

        <aside className="hub-board-live" aria-label="Tonight">
          {active ? (
            <>
              <div className="hub-board-live-top">
                <span className="live-pill">
                  <span className="live-dot" aria-hidden="true" /> Live
                </span>
                <span>{active.privacy === "open" ? "Open lobby" : "Group lobby"}</span>
              </div>
              <span className="section-kicker">{active.groupName}</span>
              <h2 className="display">{activeHeadline(active)}</h2>
              <p className="hub-board-live-copy">{activeCopy(active)}</p>
              <div className="hub-board-live-players">
                <AvatarStack people={active.players} size={26} />
                <span>{stageLabel(active)}</span>
              </div>
              <div className="hub-board-progress" aria-hidden="true">
                <span style={{ transform: `scaleX(${activeProgress(active)})` }} />
              </div>
              <Link to={`/lobby/${active.id}`} className={buttonClass("primary", "md", "hub-board-rejoin")}>
                Rejoin the room <ArrowRight size={16} />
              </Link>
            </>
          ) : winnerLobby && winner ? (
            <>
              <div className="hub-board-live-top">
                <span className="section-kicker">Last night</span>
                <span>{winnerLobby.groupName}</span>
              </div>
              <div className="winner-mini">
                <img src={winner.poster} alt={`${winner.title} poster`} />
                <div>
                  <h2 className="display">{winner.title}</h2>
                  <p>
                    {winnerPicks.length} of {winnerLobby.players.length} picks · {winner.year}
                  </p>
                </div>
              </div>
              <div className="hub-board-winner-actions">
                <Button size="sm" onClick={() => setStartOpen(true)}>
                  Plan the next one
                </Button>
                <Link to={`/lobby/${winnerLobby.id}`} className="text-link">
                  See the room <ArrowUpRight size={14} />
                </Link>
              </div>
            </>
          ) : (
            <>
              <div className="hub-board-live-top">
                <span className="section-kicker">On the watchlist</span>
                {featuredGroup ? (
                  <span className="hub-board-club-name">{featuredGroup.name}</span>
                ) : null}
              </div>
              <h2 className="display">A few good ones, waiting.</h2>
              {featuredGroup ? (
                <>
                  <div className="hub-board-club">
                    <AvatarStack people={featuredGroup.members} size={23} />
                    <span>{featuredGroup.members.length} members</span>
                  </div>
                  <div className="hub-board-watchlist">
                    <PosterStack movies={featuredGroup.watchlist} className="tonight-stack" />
                    <div className="hub-board-up-next">
                      <span className="section-kicker">Up next</span>
                      {nextUpMovie ? (
                        <>
                          <strong className="display">{nextUpMovie.title}</strong>
                          {upNextFilms.length > 1 ? (
                            <span>+{upNextFilms.length - 1} more waiting</span>
                          ) : null}
                        </>
                      ) : (
                        <span>Nothing waiting yet.</span>
                      )}
                    </div>
                  </div>
                  {featuredGroup.lastNight && lastNightAverage !== null ? (
                    lastNightEntry ? (
                      <button
                        type="button"
                        className="hub-board-last is-link"
                        onClick={() => setNightDetail(lastNightEntry)}
                        aria-label={`Revisit ${featuredGroup.lastNight.movie.title}, club score ${lastNightAverage.toFixed(1)}`}
                      >
                        <span className="section-kicker">Last night</span>
                        <span className="hub-board-last-title">
                          {featuredGroup.lastNight.movie.title}
                        </span>
                        <span className="hub-board-last-score">
                          <Star size={11} fill="currentColor" aria-hidden="true" />
                          {lastNightAverage.toFixed(1)}
                        </span>
                        <ArrowUpRight size={12} aria-hidden="true" />
                      </button>
                    ) : (
                      <div className="hub-board-last">
                        <span className="section-kicker">Last night</span>
                        <span className="hub-board-last-title">
                          {featuredGroup.lastNight.movie.title}
                        </span>
                        <span className="hub-board-last-score">
                          <Star size={11} fill="currentColor" aria-hidden="true" />
                          {lastNightAverage.toFixed(1)}
                        </span>
                      </div>
                    )
                  ) : null}
                  <div className="hub-board-idle-actions">
                    <Button size="sm" variant="secondary" onClick={() => setStartOpen(true)}>
                      Start with {featuredGroup.name}
                    </Button>
                    <Link
                      to={`/groups/${featuredGroup.id}`}
                      className="text-link hub-board-idle-link"
                    >
                      Open the watchlist <ArrowUpRight size={14} />
                    </Link>
                  </div>
                </>
              ) : (
                <p className="hub-board-live-copy">
                  Start an open room and let the link do the inviting.
                </p>
              )}
            </>
          )}
        </aside>

        <div className="hub-board-foot">
          <span>
            <CalendarDays size={14} aria-hidden="true" /> Next night {nextNight}
          </span>
          <Link to="/groups" className="hub-board-crews">
            {groups.length} {groups.length === 1 ? "crew" : "crews"} · {totalFilms} films
            between you <ArrowUpRight size={13} />
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
              Everything the club has watched, rated and argued about. The next night is only ever
              one entry away.
            </p>
          </div>
          <span className="hub-log-count">
            {recentNights.length} {recentNights.length === 1 ? "night" : "nights"} logged
          </span>
        </header>

        {featureNight ? (
          <div className={cx("hub-log-spread", !archiveNights.length && "is-single")}>
            {(() => {
              const score = nightScore(groups, featureNight);
              return (
                <button
                  type="button"
                  className="hub-log-feature"
                  onClick={() => setNightDetail(featureNight)}
                  aria-label={`Revisit ${featureNight.movie.title}, club score ${score.average.toFixed(1)}`}
                >
                  <span className="hub-log-feature-poster">
                    <img
                      src={featureNight.movie.poster}
                      alt={`${featureNight.movie.title} poster`}
                      loading="lazy"
                    />
                  </span>
                  <span className="hub-log-feature-copy">
                    <span className="hub-log-feature-top">
                      <span className="hub-log-feature-kicker">Latest night</span>
                      <span className="hub-log-feature-meta">
                        {featureNight.group} · {featureNight.date}
                      </span>
                    </span>
                    <strong className="display hub-log-feature-title">
                      {featureNight.movie.title}
                    </strong>
                    <span className="hub-log-feature-film-meta">
                      {featureNight.movie.year} · {featureNight.movie.runtime} min ·{" "}
                      {featureNight.movie.genres.slice(0, 2).join(", ")} · Dir.{" "}
                      {featureNight.movie.director}
                    </span>
                    <span className="hub-log-feature-note">{featureNight.note}</span>
                    {score.scored.length ? (
                      <span className="hub-log-feature-people" aria-label="Member scores">
                        {score.scored.map(({ person, score: value }) => (
                          <span
                            className="hub-log-feature-person"
                            key={person.id}
                            role="img"
                            aria-label={`${person.name}: ${value.toFixed(1)}`}
                            title={`${person.name}: ${value.toFixed(1)}`}
                          >
                            <Avatar person={person} size={19} />
                            <strong>{value.toFixed(1)}</strong>
                          </span>
                        ))}
                      </span>
                    ) : null}
                    <span className="hub-log-feature-foot">
                      <span
                        className="hub-log-feature-score"
                        aria-label={
                          score.count
                            ? `Club score ${score.average.toFixed(1)} from ${score.count} scores`
                            : `Night score ${score.average.toFixed(1)}`
                        }
                      >
                        <span className="hub-log-score-label">
                          {score.count ? "Club score" : "Night score"}
                        </span>
                        <span className="hub-log-score-value">
                          <Star size={14} fill="currentColor" aria-hidden="true" />
                          <strong>{score.average.toFixed(1)}</strong>
                          {score.count ? (
                            <span className="hub-log-score-count">
                              {score.count} {score.count === 1 ? "score" : "scores"}
                            </span>
                          ) : null}
                        </span>
                        {score.scored.length ? (
                          <span className="hub-log-score-track" aria-hidden="true">
                            {score.scored.map(({ person, score: value }) => (
                              <span
                                key={person.id}
                                className="hub-log-score-dot"
                                style={{ left: `${value * 10}%`, background: person.color }}
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
              );
            })()}

            {archiveNights.length ? (
              <div className="hub-log-archive">
                {archiveNights.map((night) => {
                  const score = nightScore(groups, night);
                  return (
                    <button
                      type="button"
                      className="hub-log-archive-entry"
                      key={night.id}
                      onClick={() => setNightDetail(night)}
                      aria-label={`Revisit ${night.movie.title}, club score ${score.average.toFixed(1)}`}
                    >
                      <span className="hub-log-archive-poster">
                        <img
                          src={night.movie.poster}
                          alt={`${night.movie.title} poster`}
                          loading="lazy"
                        />
                      </span>
                      <span className="hub-log-archive-copy">
                        <span className="hub-log-archive-meta">
                          {night.group} · {night.date}
                        </span>
                        <strong className="display hub-log-archive-title">
                          {night.movie.title}
                        </strong>
                        <span className="hub-log-archive-note">{night.note}</span>
                        <span className="hub-log-archive-foot">
                          <span className="hub-log-archive-score">
                            <Star size={11} fill="currentColor" aria-hidden="true" />
                            <strong>{score.average.toFixed(1)}</strong>
                            {score.count ? (
                              <span>
                                {score.count} {score.count === 1 ? "score" : "scores"}
                              </span>
                            ) : null}
                          </span>
                          <ArrowUpRight size={14} aria-hidden="true" />
                        </span>
                      </span>
                    </button>
                  );
                })}
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

      <StartNightDialog
        open={startOpen}
        onOpenChange={setStartOpen}
        initialGroupId={featuredGroup?.id}
      />
      <JoinDialog open={joinOpen} onOpenChange={setJoinOpen} />
      <NightDialog
        night={nightDetail}
        score={nightDetail ? nightScore(groups, nightDetail) : null}
        open={Boolean(nightDetail)}
        onOpenChange={(open) => {
          if (!open) setNightDetail(null);
        }}
      />
    </div>
  );
}

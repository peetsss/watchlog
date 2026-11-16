import { useState } from "react";
import { ArrowRight, ArrowUpRight, Film, Loader2, Plus, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { AvatarStack } from "../components/Avatar";
import { Button, buttonClass } from "../components/Button";
import { CreateGroupDialog } from "../components/CreateGroupDialog";
import { EmptyState } from "../components/EmptyState";
import { PosterStack } from "../components/PosterStack";
import { StartNightDialog } from "../components/StartNightDialog";
import { groupWatchlistQueryOptions, useGroupList } from "../lib/api-groups";
import { usePageTitle } from "../lib/usePageTitle";

export function GroupsPage() {
  usePageTitle("Groups");
  const groupsQuery = useGroupList();
  const [createOpen, setCreateOpen] = useState(false);
  const [startGroupId, setStartGroupId] = useState<string | null>(null);

  const groups = groupsQuery.data ?? [];
  const watchlists = useQueries({
    queries: groups.map((group) => groupWatchlistQueryOptions(group.id)),
  });
  const filmsByGroup = new Map(
    groups.map((group, index) => [group.id, watchlists[index]?.data ?? []]),
  );

  if (groupsQuery.isPending) {
    return (
      <div className="page-inner groups-page">
        <p className="session-loading" role="status">
          <Loader2 className="spin" size={17} aria-hidden="true" />
          <span>Opening your groups…</span>
        </p>
      </div>
    );
  }

  if (groupsQuery.isError) {
    return (
      <div className="page-inner groups-page">
        <EmptyState
          icon={<Users size={24} />}
          title="Your groups didn't load."
          body={groupsQuery.error.message}
          action={<Button onClick={() => groupsQuery.refetch()}>Try again</Button>}
        />
      </div>
    );
  }

  return (
    <div className="page-inner groups-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Your crews</p>
          <h1 className="display page-title">Groups</h1>
          <p className="lede page-lede">
            The people you watch with, and everything you've watched together.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> Create a group
        </Button>
      </header>

      <div className="groups-layout">
        <div>
          {groups.length ? (
            <div className="group-list">
              {groups.map((group) => {
                const films = filmsByGroup.get(group.id) ?? [];
                const lastWatched = films.find((film) => film.status === "watched");

                return (
                  <article className="group-row" key={group.id}>
                    <PosterStack
                      movies={films.slice(0, 3).map((film) => ({
                        id: film.id,
                        title: film.movie.title,
                        poster: film.movie.poster,
                      }))}
                      className="group-row-posters"
                    />
                    <div className="group-row-body">
                      <div className="group-row-top">
                        <div>
                          <Link to={`/groups/${group.id}`} className="group-name-link">
                            <h2 className="display">{group.name}</h2>
                          </Link>
                          <p>
                            {group.description || "A group for the films you keep between you."}
                          </p>
                        </div>
                        <div className="group-row-actions">
                          <Button size="sm" onClick={() => setStartGroupId(group.id)}>
                            Start a night <ArrowRight size={15} />
                          </Button>
                          <Link
                            to={`/groups/${group.id}`}
                            className={buttonClass("secondary", "sm")}
                          >
                            Open <ArrowUpRight size={14} />
                          </Link>
                        </div>
                      </div>
                      <div className="group-row-meta">
                        <span className="meta-item">
                          <AvatarStack people={group.members} size={24} />
                          {group.memberCount} {group.memberCount === 1 ? "member" : "members"}
                        </span>
                        <span className="meta-item">
                          <Film size={14} aria-hidden="true" />
                          {group.filmCount} {group.filmCount === 1 ? "film" : "films"}
                        </span>
                        <span className="meta-item">
                          {lastWatched
                            ? `Last watched: ${lastWatched.movie.title}`
                            : "No films watched yet"}
                        </span>
                        <Link to={`/groups/${group.id}`} className="meta-item group-open-link">
                          Open watchlist <ArrowUpRight size={12} />
                        </Link>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <EmptyState
              icon={<Users size={24} />}
              title="No groups yet."
              body="A group is just the people you keep coming back to. Make one, then add the first film."
              action={
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus size={16} /> Create a group
                </Button>
              }
            />
          )}
        </div>

        <aside className="groups-aside">
          <div className="aside-card">
            <span className="section-kicker">How a night works</span>
            <h2 className="display aside-title">Three steps, one pick.</h2>
            <ol className="steps">
              <li>
                <span className="step-number">01</span>
                <div>
                  <strong>Open a room</strong>
                  <p>Pick a crew or share an open link. Everyone readies up.</p>
                </div>
              </li>
              <li>
                <span className="step-number">02</span>
                <div>
                  <strong>Everyone votes</strong>
                  <p>A film needs a unanimous yes to reach the shortlist.</p>
                </div>
              </li>
              <li>
                <span className="step-number">03</span>
                <div>
                  <strong>The room picks</strong>
                  <p>One film wins. It lands in the watchlist for next time.</p>
                </div>
              </li>
            </ol>
          </div>

          <div className="aside-note">
            <span className="aside-note-icon" aria-hidden="true">
              <Plus size={18} />
            </span>
            <p>
              <strong>No group yet?</strong> Make one, add the first film, then send the invite.
            </p>
            <Button size="sm" variant="secondary" onClick={() => setCreateOpen(true)}>
              Create a group
            </Button>
          </div>
        </aside>
      </div>

      <CreateGroupDialog open={createOpen} onOpenChange={setCreateOpen} />
      <StartNightDialog
        open={startGroupId !== null}
        onOpenChange={(open) => {
          if (!open) setStartGroupId(null);
        }}
        initialGroupId={startGroupId ?? undefined}
      />
    </div>
  );
}
